"""Tests for Person 4's Safety Guard, Failed-Patch Memory, and Circuit Breaker."""

import time
import pytest
from driftshield.healer.patch_memory import FailedPatchMemory
from driftshield.healer.safety_guard import PatchSafetyGuard
from driftshield.healer.circuit_breaker import RecoveryCircuitBreaker, CircuitState


# ==========================================
# 1. Patch Safety Guard Tests
# ==========================================

def test_guard_approves_safe_patch():
    """Verify that a well-formed patch with valid changes passes all checks."""
    guard = PatchSafetyGuard()
    changes = [
        {"type": "rename", "old_path": "user_id", "new_path": "id"},
        {"type": "type_change", "path": "id", "from_type": "string", "to_type": "integer"}
    ]
    payload = {"id": 123}
    provenance = {"id": "converted"}

    result = guard.validate_patch(
        tool_name="update_user",
        current_version=1,
        contract_hash="hash1",
        changes=changes,
        payload=payload,
        provenance=provenance,
    )
    assert result.is_safe is True
    assert "passed" in result.reason.lower()


def test_guard_rejects_ambiguous_patch():
    """Verify that patches with ambiguous mappings are rejected immediately."""
    guard = PatchSafetyGuard()
    changes = [
        {"type": "ambiguous", "removed": "target", "candidates": ["target_id", "target_obj"]}
    ]
    result = guard.validate_patch("update_user", 1, "hash1", changes)
    assert result.is_safe is False
    assert any("Ambiguous" in v for v in result.violations)


def test_guard_rejects_invented_business_values():
    """Verify that patches requiring invented/fabricated business values are blocked."""
    guard = PatchSafetyGuard()
    changes = [
        {"type": "new_required_field", "field": "organization_id"}
    ]
    result = guard.validate_patch("update_user", 1, "hash1", changes)
    assert result.is_safe is False
    assert any("Cannot invent value" in v for v in result.violations)


def test_guard_rejects_unsupported_type_conversion():
    """Verify that lossy/unsupported conversions (e.g. string to boolean) are rejected."""
    guard = PatchSafetyGuard()
    changes = [
        {"type": "type_change", "path": "score", "from_type": "string", "to_type": "boolean"}
    ]
    result = guard.validate_patch("update_user", 1, "hash1", changes)
    assert result.is_safe is False
    assert any("Unsupported type conversion" in v for v in result.violations)


def test_guard_rejects_untagged_payload_provenance():
    """Verify that payload values without legitimate provenance are detected and blocked."""
    guard = PatchSafetyGuard()
    payload = {"user_id": "user_123", "secret_key": "hallucinated_value"}
    provenance = {"user_id": "original_arg"}  # missing secret_key provenance tag!

    result = guard.validate_patch("test_tool", 1, "hash1", [], payload=payload, provenance=provenance)
    assert result.is_safe is False
    assert any("provenance" in v for v in result.violations)


# ==========================================
# 2. Failed-Patch Memory Tests
# ==========================================

def test_failed_patch_memory_blocks_repeated_bad_patch():
    """Verify that previously failed patches are recorded and blocked from re-application."""
    memory = FailedPatchMemory()
    guard = PatchSafetyGuard(memory=memory)
    changes = [{"type": "rename", "old_path": "a", "new_path": "b"}]

    # 1. First attempt is safe
    result = guard.validate_patch("api_tool", 1, "v1_hash", changes)
    assert result.is_safe is True

    # 2. Record failure after applying
    memory.record_failure("api_tool", "v1_hash", 1, changes, reason="Endpoint rejected format")

    # 3. Repeated attempt is now blocked
    result_repeat = guard.validate_patch("api_tool", 1, "v1_hash", changes)
    assert result_repeat.is_safe is False
    assert any("previously failed" in v for v in result_repeat.violations)


def test_failed_patch_memory_allows_fresh_attempt_on_contract_change():
    """Verify that a contract update invalidates memory and allows a fresh attempt."""
    memory = FailedPatchMemory()
    changes = [{"type": "rename", "old_path": "a", "new_path": "b"}]
    memory.record_failure("api_tool", "v1_hash", 1, changes, reason="Failed on v1_hash")

    # When live contract hash changes to v2_hash, retry is permitted
    is_bad, _ = memory.is_known_bad("api_tool", "v2_hash", 1, changes)
    assert is_bad is False


def test_failed_patch_memory_allows_fresh_attempt_on_registry_version_change():
    """Verify that registry version bump permits a fresh attempt."""
    memory = FailedPatchMemory()
    changes = [{"type": "rename", "old_path": "a", "new_path": "b"}]
    memory.record_failure("api_tool", "v1_hash", 1, changes, reason="Failed on version 1")

    # When registry version changes from 1 to 2, attempt is permitted
    is_bad, _ = memory.is_known_bad("api_tool", "v1_hash", 2, changes)
    assert is_bad is False


def test_failed_patch_memory_ttl_expiry():
    """Verify that memory expires after TTL."""
    memory = FailedPatchMemory(ttl_seconds=0.1)
    changes = [{"type": "rename", "old_path": "a", "new_path": "b"}]
    memory.record_failure("api_tool", "v1_hash", 1, changes, reason="Temporary failure")

    time.sleep(0.15)
    is_bad, _ = memory.is_known_bad("api_tool", "v1_hash", 1, changes)
    assert is_bad is False


# ==========================================
# 3. Recovery Circuit Breaker Tests
# ==========================================

def test_circuit_breaker_trips_to_open_after_threshold():
    """Verify that breaker trips to OPEN upon hitting consecutive failure threshold."""
    transitions = []
    def log_transition(key, old, new, reason):
        transitions.append((key, old, new, reason))

    cb = RecoveryCircuitBreaker(failure_threshold=3, cooldown_seconds=2.0, on_state_change=log_transition)
    tool = "payment_api"

    # Initial state
    assert cb.get_state(tool) == CircuitState.CLOSED
    can_run, _ = cb.can_attempt_recovery(tool)
    assert can_run is True

    # 1st failure
    cb.record_failure(tool, "HTTP 500")
    assert cb.get_state(tool) == CircuitState.CLOSED

    # 2nd failure
    cb.record_failure(tool, "HTTP 500")
    assert cb.get_state(tool) == CircuitState.CLOSED

    # 3rd failure -> TRIPS
    cb.record_failure(tool, "HTTP 500")
    assert cb.get_state(tool) == CircuitState.OPEN
    assert len(transitions) == 1
    assert transitions[0][2] == CircuitState.OPEN

    # Breaker immediately blocks recovery
    can_run, msg = cb.can_attempt_recovery(tool)
    assert can_run is False
    assert "Circuit is OPEN" in msg


def test_circuit_breaker_probe_and_recovery():
    """Verify probe execution in HALF_OPEN and transition back to CLOSED on success."""
    cb = RecoveryCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    tool = "data_api"

    cb.record_failure(tool, "Fail 1")
    cb.record_failure(tool, "Fail 2")
    assert cb.get_state(tool) == CircuitState.OPEN

    # Wait for cooldown
    time.sleep(0.15)

    # Cooldown passed -> enters HALF_OPEN
    can_run, msg = cb.can_attempt_recovery(tool)
    assert can_run is True
    assert cb.get_state(tool) == CircuitState.HALF_OPEN

    # Run successful controlled probe
    probe_called = False
    def mock_probe():
        nonlocal probe_called
        probe_called = True
        return True

    success = cb.execute_probe(tool, mock_probe, "schema_dry_run")
    assert success is True
    assert probe_called is True

    # Reset to CLOSED
    assert cb.get_state(tool) == CircuitState.CLOSED


def test_circuit_breaker_probe_failure_reopens_circuit():
    """Verify failed probe in HALF_OPEN immediately returns to OPEN state."""
    cb = RecoveryCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    tool = "data_api"

    cb.record_failure(tool, "Fail 1")
    cb.record_failure(tool, "Fail 2")
    assert cb.get_state(tool) == CircuitState.OPEN

    time.sleep(0.15)
    assert cb.can_attempt_recovery(tool)[0] is True
    assert cb.get_state(tool) == CircuitState.HALF_OPEN

    # Probe fails
    success = cb.execute_probe(tool, lambda: False, "schema_dry_run")
    assert success is False
    assert cb.get_state(tool) == CircuitState.OPEN
