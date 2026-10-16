"""Proactive Sentinel (Drift Radar) for monitoring API contract drift.

Monitors authoritative API contracts, detects schema changes using canonical
serialization and hashing, verifies candidate modifications via existing differ
and patcher components, and atomically reconciles safe changes into the tool registry.
"""

import hashlib
import json
import threading
from typing import Any, Callable

from driftshield import config
from driftshield.healer import log
from driftshield.healer.differ import diff
from driftshield.healer.guard import resolve_headers
from driftshield.healer.patcher import build_new_snapshot
from driftshield.healer.registry import ToolRegistry, StaleVersionError


def compute_canonical_hash(contract: dict[str, Any]) -> str:
    """Compute stable SHA256 hash of canonical JSON representation.

    Excludes volatile metadata like content_hash and sorts all keys recursively
    so irrelevant JSON key order changes never produce false drift.

    Args:
        contract: Contract dictionary

    Returns:
        Hex-encoded SHA256 string
    """
    cleaned = {k: v for k, v in contract.items() if k not in ("content_hash",)}
    canonical = json.dumps(cleaned, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fetch_contract(client: Any, schema_url: str = "/schema") -> dict[str, Any] | None:
    """Fetch authoritative contract from API client.

    Args:
        client: httpx.Client or FastAPI TestClient
        schema_url: URL path to schema endpoint

    Returns:
        Contract dict if successful, None if non-200 or unparseable
    """
    if hasattr(client, "get"):
        response = client.get(schema_url)
    else:
        base = getattr(client, "base_url", None) or config.BASE_URL
        response = client.get(f"{base}{schema_url}")

    if response.status_code == 200:
        return response.json()
    return None


class Sentinel:
    """Proactive API contract monitor and safe registry reconciler.

    Runs in a background thread or via deterministic poll_once() steps.
    Never invents values or guesses ambiguous mappings. Reconciles only safe,
    verified changes into the registry.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        client: Any,
        tool_name: str = "lookup_user",
        poll_interval: float = 10.0,
        schema_url: str = "/schema",
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        log_events: bool = True,
        auto_baseline: bool = True,
    ):
        self.registry = registry
        self.client = client
        self.tool_name = tool_name
        self.poll_interval = poll_interval
        self.schema_url = schema_url
        self.on_event = on_event
        self.log_events = log_events

        self.baseline_hash: str | None = None
        self.last_known_hash: str | None = None
        self._last_evaluated_hash: str | None = None

        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._is_running = False

        if auto_baseline:
            self.establish_baseline()

    @property
    def is_running(self) -> bool:
        """Check if background polling thread is currently running."""
        with self._thread_lock:
            return self._is_running and self._thread is not None and self._thread.is_alive()

    def establish_baseline(self) -> str | None:
        """Establish baseline contract hash from the registry or live API."""
        tool = self.registry.get(self.tool_name)
        if tool and tool.get("contract_hash"):
            self.baseline_hash = tool["contract_hash"]
            self.last_known_hash = tool["contract_hash"]
            self._last_evaluated_hash = tool["contract_hash"]
            return self.baseline_hash

        try:
            live = fetch_contract(self.client, self.schema_url)
            if live and isinstance(live, dict) and "body_schema" in live:
                h = compute_canonical_hash(live)
                self.baseline_hash = h
                self.last_known_hash = h
                self._last_evaluated_hash = h
                return h
        except Exception:
            pass
        return None

    def poll_once(self) -> dict[str, Any]:
        """Execute a single deterministic polling and reconciliation cycle.

        Returns:
            Dict containing status:
            - 'unchanged': No contract change detected
            - 'reconciled': Safe drift detected and applied to registry
            - 'rejected': Drift detected but rejected by verification rules
            - 'error': Network failure, missing tool, or malformed contract
        """
        tool = self.registry.get(self.tool_name)
        if tool is None:
            err = f"Tool '{self.tool_name}' not found in registry"
            self._emit_event("monitoring_error", {
                "tool_name": self.tool_name,
                "error": err,
            })
            return {"status": "error", "error": err}

        # 1. Fetch authoritative live contract
        try:
            live_contract = fetch_contract(self.client, self.schema_url)
        except Exception as e:
            err = f"Exception fetching live contract: {e}"
            self._emit_event("monitoring_error", {
                "tool_name": self.tool_name,
                "error": err,
            })
            return {"status": "error", "error": err}

        if live_contract is None:
            err = "Failed to fetch live contract: schema endpoint returned non-200 or unparseable response"
            self._emit_event("monitoring_error", {
                "tool_name": self.tool_name,
                "error": err,
            })
            return {"status": "error", "error": err}

        # Validate basic schema structure (guard against malformed contract)
        if not isinstance(live_contract, dict) or "body_schema" not in live_contract or not isinstance(live_contract.get("body_schema"), dict) or "operation" not in live_contract:
            err = "Malformed live contract: missing body_schema or operation field"
            self._emit_event("monitoring_error", {
                "tool_name": self.tool_name,
                "error": err,
            })
            return {"status": "error", "error": err}

        # 2. Canonical serialization & hash comparison
        current_hash = compute_canonical_hash(live_contract)

        # Baseline capture if uninitialized
        if self.baseline_hash is None:
            self.baseline_hash = current_hash
            self.last_known_hash = current_hash
            self._last_evaluated_hash = current_hash

        # Avoid repeated duplicate checks/events if contract has not changed
        if current_hash == self._last_evaluated_hash:
            return {"status": "unchanged", "hash": current_hash}

        # Check if the registry tool already reflects this exact contract
        if current_hash == tool.get("contract_hash"):
            self.last_known_hash = current_hash
            self._last_evaluated_hash = current_hash
            return {"status": "unchanged", "hash": current_hash}

        # Mark current hash as evaluated to avoid duplicate events on subsequent runs
        self._last_evaluated_hash = current_hash

        # 3. Drift detected
        old_hash = self.last_known_hash or tool.get("contract_hash")
        schema_version = live_contract.get("schema_version")

        self._emit_event("drift_detected", {
            "tool_name": self.tool_name,
            "old_hash": old_hash,
            "new_hash": current_hash,
            "schema_version": schema_version,
        })

        # 4. Differ: compute candidate changes
        changes = diff(tool, live_contract)
        self._emit_event("diff", {
            "tool_name": self.tool_name,
            "changes": [
                {
                    "type": c.get("type"),
                    "tier": c.get("tier"),
                    "old_path": c.get("old_path"),
                    "new_path": c.get("new_path"),
                    "path": c.get("path"),
                    "removed": c.get("removed"),
                    "candidates": c.get("candidates"),
                }
                for c in changes
            ],
        })

        # 5. Verification & Safe Reconciliation Rules

        # Rule 5a: Ambiguous changes cannot be guessed
        for change in changes:
            if change.get("type") == "ambiguous":
                reason = f"Ambiguous change detected: {change.get('removed')} -> {change.get('candidates')}"
                self._emit_event("reconciliation_rejected", {
                    "tool_name": self.tool_name,
                    "reason": reason,
                    "contract_hash": current_hash,
                    "schema_version": schema_version,
                })
                return {"status": "rejected", "reason": reason, "changes": changes, "hash": current_hash}

        # Rule 5b: New required fields cannot be invented
        for change in changes:
            if change.get("type") == "new_required_field":
                reason = f"New required field cannot be derived without inventing values: {change.get('path')}"
                self._emit_event("reconciliation_rejected", {
                    "tool_name": self.tool_name,
                    "reason": reason,
                    "contract_hash": current_hash,
                    "schema_version": schema_version,
                })
                return {"status": "rejected", "reason": reason, "changes": changes, "hash": current_hash}

        # Rule 5c: Required headers must be resolvable from configuration
        required_headers = live_contract.get("required_headers", [])
        if required_headers:
            _, _, missing_headers = resolve_headers(required_headers)
            if missing_headers:
                reason = f"Required headers unavailable in configuration: {', '.join(missing_headers)}"
                self._emit_event("reconciliation_rejected", {
                    "tool_name": self.tool_name,
                    "reason": reason,
                    "contract_hash": current_hash,
                    "schema_version": schema_version,
                    "missing_headers": missing_headers,
                })
                return {"status": "rejected", "reason": reason, "changes": changes, "hash": current_hash}

        # Rule 5d: Candidate snapshot build and validation
        new_snapshot, snapshot_error = build_new_snapshot(tool, changes, live_contract)
        if new_snapshot is None:
            reason = f"Candidate snapshot validation failed: {snapshot_error}"
            self._emit_event("reconciliation_rejected", {
                "tool_name": self.tool_name,
                "reason": reason,
                "contract_hash": current_hash,
                "schema_version": schema_version,
            })
            return {"status": "rejected", "reason": reason, "changes": changes, "hash": current_hash}

        # 6. Atomic Registry Update with Concurrency Validation
        with self.registry.lock:
            current_tool = self.registry.get(self.tool_name)
            if current_tool is None:
                err = f"Tool '{self.tool_name}' not found in registry"
                self._emit_event("monitoring_error", {
                    "tool_name": self.tool_name,
                    "error": err,
                })
                return {"status": "error", "error": err}

            # Check if another thread already reconciled to this exact contract
            if current_tool.get("contract_hash") == current_hash:
                self.last_known_hash = current_hash
                self._last_evaluated_hash = current_hash
                return {"status": "unchanged", "hash": current_hash}

            # Reject candidate if registry was updated concurrently after Sentinel read snapshot
            if current_tool["version"] != tool["version"]:
                reason = (
                    f"Concurrency conflict: tool '{self.tool_name}' updated from "
                    f"version {tool['version']} to {current_tool['version']} during reconciliation"
                )
                self._emit_event("reconciliation_rejected", {
                    "tool_name": self.tool_name,
                    "reason": reason,
                    "contract_hash": current_hash,
                    "schema_version": schema_version,
                })
                return {"status": "rejected", "reason": reason, "changes": changes, "hash": current_hash}

            version_before = tool["version"]
            try:
                self.registry.apply_patch(
                    self.tool_name,
                    new_snapshot,
                    f"proactive reconciliation to schema {schema_version or current_hash[:8]}",
                    expected_version=version_before,
                )
            except StaleVersionError as sve:
                reason = f"Concurrency conflict: {sve}"
                self._emit_event("reconciliation_rejected", {
                    "tool_name": self.tool_name,
                    "reason": reason,
                    "contract_hash": current_hash,
                    "schema_version": schema_version,
                })
                return {"status": "rejected", "reason": reason, "changes": changes, "hash": current_hash}

            version_after = self.registry.version(self.tool_name)
            self.last_known_hash = current_hash

        self._emit_event("reconciliation_succeeded", {
            "tool_name": self.tool_name,
            "version_before": version_before,
            "version_after": version_after,
            "contract_hash": current_hash,
            "schema_version": schema_version,
        })

        return {
            "status": "reconciled",
            "version_before": version_before,
            "version_after": version_after,
            "changes": changes,
            "hash": current_hash,
        }

    def start(self) -> None:
        """Start the proactive background polling thread."""
        with self._thread_lock:
            if self._is_running:
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"Sentinel-{self.tool_name}",
                daemon=True,
            )
            self._is_running = True
            self._thread.start()

        self._emit_event("monitoring_started", {
            "tool_name": self.tool_name,
            "poll_interval": self.poll_interval,
            "baseline_hash": self.baseline_hash,
        })

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the proactive background polling thread cleanly."""
        with self._thread_lock:
            if not self._is_running:
                return
            self._stop_event.set()
            thread = self._thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout)

        with self._thread_lock:
            self._is_running = False
            self._thread = None

        self._emit_event("monitoring_stopped", {
            "tool_name": self.tool_name,
        })

    def _run_loop(self) -> None:
        """Background thread target that loops until stop_event is set."""
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception as e:
                self._emit_event("monitoring_error", {
                    "tool_name": self.tool_name,
                    "error": str(e),
                })
            # Sleep using event wait so stop() interrupts immediately
            if self._stop_event.wait(self.poll_interval):
                break

    def _emit_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        """Emit structured event to callback and audit logger."""
        if self.on_event:
            try:
                self.on_event(event_name, event_data)
            except Exception:
                pass

        if self.log_events:
            try:
                log.log_event({
                    "event": event_name,
                    **event_data,
                })
            except Exception:
                pass

    def __enter__(self) -> "Sentinel":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
