# DriftShield — Safety & Reliability Specification (Person 4)

## Overview
This specification details the architecture, interfaces, and integration points for the **Safety & Reliability** features designed and built by **Person 4** on branch `feature/integration-qa` (or `feature/safety-reliability`).

---

## 1. Modules Implemented

### 1.1 `FailedPatchMemory` (`driftshield/healer/patch_memory.py`)
- **Deterministic Fingerprinting**: Uses SHA-256 to hash schema diffs and candidate patches.
- **State Partitioning**: Failed patches are recorded against `(tool_name, contract_hash, registry_version, fingerprint)`.
- **Automatic State Invalidation**: If the live API contract updates (`contract_hash` changes) or the registry snapshot is bumped/rolled back (`registry_version` changes), fresh attempts are automatically allowed.
- **Expiry TTL**: Configurable memory expiration for temporary downstream outages.

### 1.2 `PatchSafetyGuard` (`driftshield/healer/safety_guard.py`)
- **Pre-flight Validation**: Validates proposed schema patches before the registry applies them.
- **Zero-Hallucination Enforced**:
  - Rejects synthetic defaults for missing business fields (`new_required_field`).
  - Rejects ambiguous mappings (`type == "ambiguous"`).
  - Rejects unsupported/lossy conversions (only allows lossless `integer <-> string`).
- **Provenance Integrity**: Rejects payloads containing unverified or untracked origins.
- **Pre-execution Memory Check**: Immediately blocks known-bad patches tracked in `FailedPatchMemory`.

### 1.3 `RecoveryCircuitBreaker` (`driftshield/healer/circuit_breaker.py`)
- **Tri-State State Machine**:
  - `CLOSED`: Normal operation; API calls and healing allowed.
  - `OPEN`: Repeated failures hit threshold (default 3); recovery blocked during cooldown.
  - `HALF_OPEN`: Cooldown elapsed; permits a single controlled read-only/dry-run probe.
- **Controlled Probes**: Successfully tested probes restore state to `CLOSED`; failed probes re-trip back to `OPEN`.
- **Audit Logging**: Emits transition reasons and tracks consecutive failure counts.

---

## 2. Interface Contract for Person 1 (Healing Engine)

Person 1 does not need to duplicate safety or circuit-breaker code. The integration requires only a non-breaking hook in `driftshield/healer/retry.py`:

```python
from driftshield.healer import PatchSafetyGuard, RecoveryCircuitBreaker

# 1. Initialize inside HealingExecutor.__init__():
self.circuit_breaker = circuit_breaker or RecoveryCircuitBreaker()
self.safety_guard = safety_guard or PatchSafetyGuard()

# 2. Check Circuit Breaker before recovery attempt:
can_recover, cb_reason = self.circuit_breaker.can_attempt_recovery(tool_name)
if not can_recover:
    return self._safe_stop(f"Circuit Breaker blocked recovery: {cb_reason}", ...)

# 3. Pre-flight check before self.registry.apply_patch():
guard_check = self.safety_guard.validate_patch(
    tool_name=tool_name,
    current_version=version_before,
    contract_hash=live_hash,
    changes=changes,
    payload=payload,
    provenance=combined_provenance,
)
if not guard_check.is_safe:
    # Record failed patch in memory so it's not retried
    self.safety_guard.memory.record_failure(tool_name, live_hash, version_before, changes, guard_check.reason)
    return self._safe_stop(f"Patch Safety Guard rejected: {guard_check.reason}", ...)

# 4. Record success/failure with Circuit Breaker:
if retry_result["ok"]:
    self.circuit_breaker.record_success(tool_name)
else:
    self.circuit_breaker.record_failure(tool_name, retry_result.get("error", "Unknown error"))
```

---

## 3. Test Coverage Summary

- **File**: `tests/test_safety_reliability.py`
- **Tests**: 12 dedicated unit tests covering:
  - `test_guard_approves_safe_patch` ✅
  - `test_guard_rejects_ambiguous_patch` ✅
  - `test_guard_rejects_invented_business_values` ✅
  - `test_guard_rejects_unsupported_type_conversion` ✅
  - `test_guard_rejects_untagged_payload_provenance` ✅
  - `test_failed_patch_memory_blocks_repeated_bad_patch` ✅
  - `test_failed_patch_memory_allows_fresh_attempt_on_contract_change` ✅
  - `test_failed_patch_memory_allows_fresh_attempt_on_registry_version_change` ✅
  - `test_failed_patch_memory_ttl_expiry` ✅
  - `test_circuit_breaker_trips_to_open_after_threshold` ✅
  - `test_circuit_breaker_probe_and_recovery` ✅
  - `test_circuit_breaker_probe_failure_reopens_circuit` ✅
- **Total Healer Test Suite**: 71/71 tests passing without errors.
