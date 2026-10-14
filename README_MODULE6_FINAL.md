# DriftShield Module 6 - Retry & Healing (FINAL)

## 🎉 Complete End-to-End Healing Implementation

All 78 tests passing - full prototype complete!

## Files Created

### driftshield/healer/retry.py
Complete healing execution flow with budget tracking and safe stops.

**Class:** `Budget(max_api_attempts=5, max_model_calls=8)`

Shared budget enforces hard limits to prevent unbounded retries.

**Methods:**
- `consume_api()` - Increment API attempt counter
- `consume_model()` - Increment model call counter
- `exhausted()` - Check if budget exceeded

**Class:** `HealingExecutor(registry, client, budget, log_events=True)`

Executes tool calls with automatic schema drift healing.

**Method:** `execute(tool_name, args) -> HealResult`

Complete healing flow:

1. **Initial Call** via interceptor
   - If ok → return status="ok"
   - Otherwise → classify error

2. **Error Classification**
   - **network** → Bounded retry (max 2 extra, short backoff), never patch
   - **auth** → safe_stop (no refresh flow)
   - **invalid_data/unknown** → safe_stop (not drift)
   - **drift** → proceed to healing

3. **Drift Healing**
   - Fetch live contract, record hash
   - Diff registry vs live
   - If ambiguous or error → safe_stop
   - Adapt args with lossless conversions
   - If adapter errors → safe_stop
   - Resolve headers from config
   - If any header missing → safe_stop with fix_proposal
   - Check provenance (all values tagged?)
   - If False → safe_stop
   - Validate adapted payload locally against live schema
   - If invalid → safe_stop

4. **Apply Patch**
   - Build new snapshot
   - Apply to registry (version bump)
   - Retry ONCE with adapted payload + headers

5. **Verify Retry**
   - If success → Check X-Contract-Hash matches
     - Match → status="healed", log event
     - Mismatch → rollback, safe_stop
   - If failure → rollback, safe_stop

**HealResult fields:**
- `status`: "ok" | "healed" | "safe_stop" | "failed"
- `result_body`: Response on success
- `reason`: Explanation
- `fix_proposal`: What's needed (for safe_stop)
- `registry_version_before`: Version before
- `registry_version_after`: Version after (if patched)
- `elapsed_seconds`: Total time
- `attempts`: Number of API calls

---

## Tests Created

### tests/test_healing_scripted.py (17 tests, all passing)

**End-to-end healing scenarios without LLM:**

1. ✓ **test_v1_call_succeeds_no_healing**
   - v1 call succeeds immediately
   - status="ok", no healing needed

2. ✓ **test_drift_to_v2_full_heals_successfully**
   - Mutate to v2_full
   - Execute {"user_id": "123"}
   - status="healed"
   - Version 1 → 2
   - Successful lookup counted

3. ✓ **test_second_call_after_healing_uses_new_definition**
   - After healing, registry updated
   - Version remains 2
   - Schema matches live contract

4. ✓ **test_header_billing_safe_stop_missing_header**
   - Mutate to header_billing
   - X-Billing-Region not in config
   - status="safe_stop"
   - fix_proposal names missing header
   - Version unchanged

5. ✓ **test_ambiguous_safe_stop**
   - Mutate to ambiguous
   - user_id → ref_a or ref_b?
   - status="safe_stop"
   - Version unchanged

6. ✓ **test_auth_error_safe_stop**
   - Fault: expired_token
   - status="safe_stop"
   - Schema untouched

7. ✓ **test_network_error_bounded_retries**
   - Fault: server_down
   - Bounded retries (max 3 attempts total)
   - status="safe_stop"
   - Schema untouched

8. ✓ **test_budget_not_exceeded**
   - Multiple operations respect limits
   - api_attempts ≤ 5
   - model_calls ≤ 8
   - Not exhausted

9. ✓ **test_invalid_data_safe_stop**
   - Send wrong type (integer vs string)
   - Registry matches contract
   - status="safe_stop"

10. ✓ **test_registry_rollback_on_retry_failure**
    - If healing succeeds → version 2
    - If healing fails → rollback to version 1

11. ✓ **test_multiple_healings_in_sequence**
    - v1 → type_int (version 2)
    - type_int → v1 (version 3)
    - Multiple healings work

12. ✓ **test_heal_result_includes_elapsed_time**
    - HealResult tracks elapsed time
    - > 0 and < 5 seconds

13. ✓ **test_tool_not_found_returns_failed**
    - Unknown tool → status="failed"

14. ✓ **test_network_error_eventual_success**
    - Network retries attempted
    - Eventually safe_stop

15. ✓ **test_drift_with_lossless_conversion**
    - type_int contract
    - "123" → 123 conversion
    - status="healed"

16. ✓ **test_drift_with_lossy_conversion_safe_stop**
    - type_int contract
    - "abc" cannot convert
    - status="safe_stop"

17. ✓ **test_successful_healing_increments_api_stats**
    - Healed call counted in stats
    - successful_lookups increments

---

## Complete Test Summary

```
================================ 78 passed in 6.43s =================================
```

**All modules:**
- 8 mock_api tests ✓
- 12 registry tests ✓
- 9 classifier tests ✓
- 14 differ tests ✓
- 18 patcher/guard tests ✓
- 17 healing tests ✓ (NEW)

**Total: 78 tests, 0 failures**

---

## Running Tests

```bash
# All tests
.venv\Scripts\python.exe -m pytest tests\ -v

# Healing tests only
.venv\Scripts\python.exe -m pytest tests\test_healing_scripted.py -v

# Specific test
.venv\Scripts\python.exe -m pytest tests\test_healing_scripted.py::test_drift_to_v2_full_heals_successfully -v
```

---

## Key Features Demonstrated

### 1. Drift Detection & Healing

```
API: v1 → v2_full
Registry: v1
Call: {"user_id": "123"}

→ Detect drift
→ Diff: nesting + type_change + new_header
→ Adapt: {"target": {"id": 123}}
→ Resolve: X-Tenant-Token from config
→ Patch registry v1 → v2
→ Retry with adapted payload
→ Success! status="healed"
```

### 2. Safe Stops (Never Guess)

**Ambiguous:**
```
user_id → ref_a or ref_b?
→ safe_stop (cannot choose)
```

**Missing Header:**
```
X-Billing-Region required
Not in config
→ safe_stop with fix_proposal
```

**Lossy Conversion:**
```
"abc" → integer?
→ safe_stop (not lossless)
```

### 3. Budget Enforcement

```
max_api_attempts: 5
max_model_calls: 8

Every call: budget.consume_api()
Check: budget.exhausted()
→ Prevents unbounded loops
```

### 4. Rollback on Failure

```
Apply patch → version 2
Retry fails
→ rollback() → version 3 (forward)
→ Restores old schema
→ Versions never decrease
```

### 5. Network Resilience

```
503 Server Down
→ Retry with backoff (max 2 extra)
→ Total 3 attempts
→ Never patch schema
→ safe_stop if persists
```

---

## Compliance with Build Rules

### Rule 2: "A 400 or 422 is not proof of schema drift"
✓ Classifier fetches live contract and compares hashes + schemas

### Rule 3: "Never invent a value"
✓ Provenance check rejects untagged values
✓ Ambiguous → safe_stop
✓ New required field → safe_stop
✓ Missing header → safe_stop with fix_proposal

### Rule 4: "Patch minimally"
✓ build_new_snapshot only changes schema/headers/hash
✓ Preserves name, description, operation

### Rule 5: "Tool list rebuilt on EVERY model call"
✓ Registry.build_tools() constructs fresh list
✓ No caching proven by tests

### Rule 6: "One patched attempt per drift event"
✓ Retry ONCE after patch
✓ If fails → rollback, safe_stop
✓ Never retry again

### Rule 7: "Never log secret values"
✓ Headers resolved but values not logged
✓ Provenance logs origin, not value
✓ log.py redacts value/token/secret keys

### Rule 8: "Healing is deterministic code"
✓ No LLM calls in healing flow
✓ Pure functions, no randomness

### Rule 9: "Plain Python with type hints"
✓ All modules typed
✓ Short functions with clear responsibilities

---

## Healing Flow Diagram

```
┌─────────────────┐
│  Agent Call     │
│  {"user_id":..} │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Interceptor    │
│  POST /users/   │
│  lookup         │
└────────┬────────┘
         │
         ▼
    ┌───────┐
    │ 200?  │──Yes──► OK (done)
    └───┬───┘
        │ No
        ▼
┌─────────────────┐
│   Classifier    │
│  - network?     │
│  - auth?        │
│  - drift?       │
└────────┬────────┘
         │
    ┌────┴────┐
    │  drift? │──No──► safe_stop
    └────┬────┘
         │ Yes
         ▼
┌─────────────────┐
│     Differ      │
│  Compare schemas│
└────────┬────────┘
         │
    ┌────┴────┐
    │ambiguous│──Yes──► safe_stop
    └────┬────┘
         │ No
         ▼
┌─────────────────┐
│    Patcher      │
│  Adapt args     │
│  - Move values  │
│  - Convert types│
└────────┬────────┘
         │
    ┌────┴────┐
    │  error? │──Yes──► safe_stop
    └────┬────┘
         │ No
         ▼
┌─────────────────┐
│     Guard       │
│  - Resolve hdrs │
│  - Check prov   │
└────────┬────────┘
         │
    ┌────┴────┐
    │missing? │──Yes──► safe_stop
    └────┬────┘          + fix_proposal
         │ No
         ▼
┌─────────────────┐
│  Apply Patch    │
│  Version bump   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Retry Call     │
│  + adapted args │
│  + headers      │
└────────┬────────┘
         │
    ┌────┴────┐
    │success? │──No───► Rollback
    └────┬────┘         safe_stop
         │ Yes
         ▼
    ┌────┴────┐
    │hash OK? │──No───► Rollback
    └────┬────┘         safe_stop
         │ Yes
         ▼
┌─────────────────┐
│    HEALED ✓     │
│  Log event      │
└─────────────────┘
```

---

## Example Healing Log Entry

```json
{
  "timestamp": "2026-10-14T12:00:00.000Z",
  "event": "healing",
  "tool": "lookup_user",
  "registry_version_before": 1,
  "registry_version_after": 2,
  "contract_hash_patched_against": "1b67b722...",
  "contract_hash_seen_on_retry": "1b67b722...",
  "changes": [
    {
      "type": "nesting",
      "tier": 1,
      "old_path": "user_id",
      "new_path": "target.id"
    },
    {
      "type": "type_change",
      "tier": 1,
      "path": "target.id",
      "from_type": "string",
      "to_type": "integer"
    },
    {
      "type": "new_header",
      "name": "X-Tenant-Token"
    }
  ],
  "value_origins": ["converted", "config"],
  "outcome": "healed",
  "elapsed_seconds": 0.15
}
```

---

## Usage Example

```python
from driftshield.healer.retry import HealingExecutor, Budget
from driftshield.healer.registry import create_default_registry
import httpx

# Setup
registry = create_default_registry()
client = httpx.Client(base_url="http://localhost:8000")
budget = Budget(max_api_attempts=5, max_model_calls=8)
executor = HealingExecutor(registry, client, budget)

# Execute with automatic healing
result = executor.execute("lookup_user", {"user_id": "123"})

if result["status"] == "ok":
    print("Success:", result["result_body"])
elif result["status"] == "healed":
    print(f"Healed! v{result['registry_version_before']} → v{result['registry_version_after']}")
    print("Result:", result["result_body"])
elif result["status"] == "safe_stop":
    print("Stopped safely:", result["reason"])
    if result["fix_proposal"]:
        print("Fix:", result["fix_proposal"])
else:
    print("Failed:", result["reason"])
```

---

## Project Complete! 🎉

**DriftShield prototype is fully functional:**
- ✓ Mock API with runtime schema mutations
- ✓ Contract-based validation
- ✓ Versioned tool registry
- ✓ Error classification (drift vs invalid_data)
- ✓ Intelligent schema diffing
- ✓ Safe argument adaptation (never invent values)
- ✓ Provenance tracking
- ✓ Automatic healing with rollback
- ✓ Budget enforcement
- ✓ Comprehensive logging
- ✓ **78 tests, all passing**

Ready for integration with LLM agents!
