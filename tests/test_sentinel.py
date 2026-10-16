"""Tests for proactive Sentinel (Drift Radar)."""

import copy
import threading
import time
from typing import Any
import pytest
from fastapi.testclient import TestClient

from driftshield.healer.sentinel import Sentinel, compute_canonical_hash
from driftshield.healer.registry import create_default_registry, ToolRegistry
from driftshield.healer.retry import HealingExecutor, Budget
from driftshield.mock_api.server import app
from driftshield.mock_api import contracts


@pytest.fixture
def clean_api():
    """Reset API to v1 and clear faults."""
    contracts.set_active("v1")
    client = TestClient(app)
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/reset")
    return client


@pytest.fixture
def registry():
    """Create fresh registry."""
    return create_default_registry()


def test_sentinel_initial_baseline_creation(clean_api, registry):
    """Test: Initial baseline is established and matches canonical hash of contract."""
    sentinel = Sentinel(registry, clean_api, tool_name="lookup_user", log_events=False)

    assert sentinel.baseline_hash is not None
    assert sentinel.last_known_hash == sentinel.baseline_hash

    # Verify baseline hash matches canonical hash of v1 contract
    v1_contract = contracts.get_active()
    expected_hash = compute_canonical_hash(v1_contract)
    assert sentinel.baseline_hash == expected_hash


def test_sentinel_no_drift_for_unchanged_contract(clean_api, registry):
    """Test: Polling an unchanged contract produces no drift and no registry changes."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    result = sentinel.poll_once()

    assert result["status"] == "unchanged"
    assert registry.version("lookup_user") == 1
    # No drift or reconciliation events emitted
    assert len(events) == 0


def test_sentinel_no_false_drift_from_json_key_ordering(clean_api, registry):
    """Test: Contracts with shuffled JSON keys have identical canonical hash and cause no drift."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    # Mock client that returns v1 contract with reversed / non-standard key ordering
    v1_raw = contracts.get_active()
    shuffled_contract = {k: v1_raw[k] for k in reversed(list(v1_raw.keys()))}
    if "body_schema" in shuffled_contract:
        shuffled_contract["body_schema"] = {
            k: shuffled_contract["body_schema"][k]
            for k in reversed(list(shuffled_contract["body_schema"].keys()))
        }

    class ShuffledClient:
        def get(self, url):
            class Resp:
                status_code = 200
                def json(self):
                    return shuffled_contract
            return Resp()

    sentinel.client = ShuffledClient()
    result = sentinel.poll_once()

    assert result["status"] == "unchanged"
    assert len(events) == 0
    assert registry.version("lookup_user") == 1


def test_sentinel_detection_of_genuine_schema_change(clean_api, registry):
    """Test: Genuine schema mutation emits drift_detected event with old and new hashes."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    old_hash = sentinel.baseline_hash

    # Mutate API to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    result = sentinel.poll_once()

    # Drift detected and reconciled
    assert result["status"] == "reconciled"
    drift_events = [data for name, data in events if name == "drift_detected"]
    assert len(drift_events) == 1
    assert drift_events[0]["tool_name"] == "lookup_user"
    assert drift_events[0]["old_hash"] == old_hash
    assert drift_events[0]["new_hash"] == result["hash"]


def test_sentinel_verified_safe_patch_applied(clean_api, registry):
    """Test: Verified safe contract change (rename_id) is proactively reconciled into registry."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    assert registry.version("lookup_user") == 1

    # Mutate API to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    result = sentinel.poll_once()

    assert result["status"] == "reconciled"
    assert result["version_before"] == 1
    assert result["version_after"] == 2

    # Registry tool version was bumped
    assert registry.version("lookup_user") == 2

    # Registry tool body_schema has been updated to rename_id (requires "id", not "user_id")
    patched_tool = registry.get("lookup_user")
    assert "id" in patched_tool["body_schema"]["properties"]
    assert "user_id" not in patched_tool["body_schema"]["properties"]

    # reconciliation_succeeded event emitted
    reconciled_events = [data for name, data in events if name == "reconciliation_succeeded"]
    assert len(reconciled_events) == 1
    assert reconciled_events[0]["version_after"] == 2


def test_sentinel_ambiguous_patch_rejected_without_registry_change(clean_api, registry):
    """Test: Ambiguous field mappings are rejected, preserving the registry."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    # Mutate API to ambiguous contract
    clean_api.post("/admin/mutate", json={"to": "ambiguous"})

    result = sentinel.poll_once()

    assert result["status"] == "rejected"
    assert "ambiguous" in result["reason"].lower()

    # Registry remains untouched at version 1
    assert registry.version("lookup_user") == 1
    tool = registry.get("lookup_user")
    assert "user_id" in tool["body_schema"]["properties"]

    # reconciliation_rejected event emitted
    rejected_events = [data for name, data in events if name == "reconciliation_rejected"]
    assert len(rejected_events) == 1
    assert "ambiguous" in rejected_events[0]["reason"].lower()


def test_sentinel_invalid_header_patch_rejected(clean_api, registry):
    """Test: Contract requiring unresolvable headers is rejected without modifying registry."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    # Mutate API to header_billing (requires unconfigured X-Billing-Region)
    clean_api.post("/admin/mutate", json={"to": "header_billing"})

    result = sentinel.poll_once()

    assert result["status"] == "rejected"
    assert "required header" in result["reason"].lower()

    # Registry unchanged
    assert registry.version("lookup_user") == 1


def test_sentinel_new_required_field_rejected(clean_api, registry):
    """Test: Contract introducing new required field cannot be derived and is rejected."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    # Create mock client returning contract with brand new required field
    v1_raw = contracts.get_active()
    new_field_contract = copy.deepcopy(v1_raw)
    new_field_contract["schema_version"] = "new_field_v2"
    new_field_contract["body_schema"]["properties"]["secret_pin"] = {"type": "string"}
    new_field_contract["body_schema"]["required"].append("secret_pin")

    class NewFieldClient:
        def get(self, url):
            class Resp:
                status_code = 200
                def json(self):
                    return new_field_contract
            return Resp()

    sentinel.client = NewFieldClient()
    result = sentinel.poll_once()

    assert result["status"] == "rejected"
    assert "required field" in result["reason"].lower()
    assert registry.version("lookup_user") == 1


def test_sentinel_malformed_live_contract(clean_api, registry):
    """Test: Malformed live contracts are caught safely without crashing or modifying registry."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    class MalformedClient:
        def get(self, url):
            class Resp:
                status_code = 200
                def json(self):
                    # Missing body_schema and operation
                    return {"garbage": "payload"}
            return Resp()

    sentinel.client = MalformedClient()
    result = sentinel.poll_once()

    assert result["status"] == "error"
    assert "malformed" in result["error"].lower()
    assert registry.version("lookup_user") == 1

    error_events = [data for name, data in events if name == "monitoring_error"]
    assert len(error_events) == 1


def test_sentinel_network_failure_followed_by_successful_later_polling(clean_api, registry):
    """Test: Network error fails cleanly, subsequent poll succeeds when network is restored."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    class FailingClient:
        def get(self, url):
            raise ConnectionResetError("Connection refused by server")

    sentinel.client = FailingClient()
    result1 = sentinel.poll_once()

    assert result1["status"] == "error"
    assert "connection" in result1["error"].lower()
    assert registry.version("lookup_user") == 1

    # Network restored with mutate to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})
    sentinel.client = clean_api

    result2 = sentinel.poll_once()

    assert result2["status"] == "reconciled"
    assert registry.version("lookup_user") == 2


def test_sentinel_concurrent_access_during_registry_updates(clean_api, registry):
    """Test: Thread-safe atomic updates: concurrent readers never observe corrupted state."""
    sentinel = Sentinel(registry, clean_api, tool_name="lookup_user", log_events=False)

    stop_threads = threading.Event()
    errors = []

    def reader_task():
        while not stop_threads.is_set():
            try:
                tool = registry.get("lookup_user")
                if tool is not None:
                    assert "name" in tool
                    assert "version" in tool
                    assert "body_schema" in tool
                tools = registry.build_tools()
                assert isinstance(tools, list)
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=reader_task) for _ in range(4)]
    for t in threads:
        t.start()

    try:
        # Perform mutations and proactive reconciliation
        for target in ["rename_id", "v1", "rename_uid", "v1"]:
            clean_api.post("/admin/mutate", json={"to": target})
            sentinel.poll_once()
            time.sleep(0.01)
    finally:
        stop_threads.set()
        for t in threads:
            t.join(timeout=2.0)

    assert len(errors) == 0, f"Concurrent access encountered errors: {errors}"


def test_sentinel_clean_start_stop_behavior(clean_api, registry):
    """Test: Sentinel starts background thread and stops cleanly on request."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        poll_interval=0.05,
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    assert not sentinel.is_running
    sentinel.start()
    assert sentinel.is_running

    started_events = [data for name, data in events if name == "monitoring_started"]
    assert len(started_events) == 1

    time.sleep(0.1)

    sentinel.stop(timeout=1.0)
    assert not sentinel.is_running

    stopped_events = [data for name, data in events if name == "monitoring_stopped"]
    assert len(stopped_events) == 1


def test_sentinel_no_duplicate_reconciliation_events_for_unchanged_contracts(clean_api, registry):
    """Test: Multiple polls on unchanged contracts do not duplicate reconciliation events."""
    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    # Mutate to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    # First poll: reconciled
    res1 = sentinel.poll_once()
    assert res1["status"] == "reconciled"

    # Second poll: contract has not changed
    res2 = sentinel.poll_once()
    assert res2["status"] == "unchanged"

    # Third poll: still unchanged
    res3 = sentinel.poll_once()
    assert res3["status"] == "unchanged"

    # Check event counts: exactly 1 drift_detected and 1 reconciliation_succeeded
    drift_events = [e for e in events if e[0] == "drift_detected"]
    succeeded_events = [e for e in events if e[0] == "reconciliation_succeeded"]
    assert len(drift_events) == 1
    assert len(succeeded_events) == 1


def test_sentinel_reactive_healing_remains_available_after_sentinel_error(clean_api, registry):
    """Test: Reactive healing continues to function normally even after Sentinel errors."""
    sentinel = Sentinel(registry, clean_api, tool_name="lookup_user", log_events=False)

    # Simulate sentinel error (e.g. malformed response from schema endpoint)
    class BrokenSchemaClient:
        def get(self, url):
            if url == "/schema":
                raise ConnectionError("Schema endpoint down")
            return clean_api.get(url)
        def post(self, url, **kwargs):
            return clean_api.post(url, **kwargs)

    sentinel.client = BrokenSchemaClient()
    res = sentinel.poll_once()
    assert res["status"] == "error"

    # Now run an actual tool execution with reactive healing
    # Mutate API to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    # Initial call with v1 args: reactive healer intercepts 400, fetches schema, adapts, and succeeds
    exec_result = executor.execute("lookup_user", {"user_id": "123"})

    assert exec_result["status"] == "healed"
    assert exec_result["result_body"] is not None
    assert exec_result["registry_version_after"] > exec_result["registry_version_before"]


def test_sentinel_rejects_stale_candidate_when_registry_updated_concurrently(clean_api, registry):
    """Regression test: A stale candidate cannot overwrite a newer registry update.

    Simulates another thread modifying the registry tool (version 1 -> version 2)
    after Sentinel reads version 1 and builds a candidate snapshot. Sentinel must
    detect the concurrency conflict, reject the stale candidate, and leave the
    newer version intact.
    """
    from unittest.mock import patch
    import driftshield.healer.sentinel as sentinel_mod

    events = []
    sentinel = Sentinel(
        registry,
        clean_api,
        tool_name="lookup_user",
        on_event=lambda name, data: events.append((name, data)),
        log_events=False,
    )

    assert registry.version("lookup_user") == 1

    # Mutate API to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    # Hook build_new_snapshot: simulate another thread patching the registry
    # right while Sentinel is in the middle of preparing its candidate snapshot
    original_build = sentinel_mod.build_new_snapshot

    def concurrent_patch_interceptor(*args, **kwargs):
        # Another thread concurrently updates the registry tool
        concurrent_tool = copy.deepcopy(registry.get("lookup_user"))
        concurrent_tool["description"] = "Newer update from concurrent thread"
        registry.apply_patch("lookup_user", concurrent_tool, "concurrent modification")
        return original_build(*args, **kwargs)

    with patch.object(sentinel_mod, "build_new_snapshot", side_effect=concurrent_patch_interceptor):
        result = sentinel.poll_once()

    # Sentinel must reject the stale candidate
    assert result["status"] == "rejected"
    assert "concurrency conflict" in result["reason"].lower()

    # The newer registry update (version 2) was preserved and NOT overwritten!
    assert registry.version("lookup_user") == 2
    current_in_registry = registry.get("lookup_user")
    assert current_in_registry["description"] == "Newer update from concurrent thread"

    # Reconciliation rejected event was emitted
    rejected_events = [data for name, data in events if name == "reconciliation_rejected"]
    assert len(rejected_events) == 1
    assert "concurrency conflict" in rejected_events[0]["reason"].lower()
