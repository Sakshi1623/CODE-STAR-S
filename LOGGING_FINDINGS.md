# DriftShield Logging Investigation - Findings

## Issue
`D:\Sakshi\driftshield\patch_log.jsonl` does not exist after running all 17 healing tests.

## Investigation Results

### 1. Where Patch Events Are Written

**File:** `driftshield/healer/log.py`
**Path:** `LOG_FILE = Path("patch_log.jsonl")`
**Location:** Project root directory (`D:\Sakshi\driftshield\patch_log.jsonl`)

The log file is created in the **current working directory** where Python is executed.

### 2. When Log File Is Created

The log file is created **only when an event is logged** via `log.log_event()`.

**Trigger:** `log_event()` opens the file in append mode (`"a"`) which creates it if it doesn't exist.

**Code:** `healer/log.py` line 52-53:
```python
with LOG_FILE.open("a", encoding="utf-8") as f:
    f.write(json.dumps(redacted) + "\n")
```

### 3. Do Scripted Healing Tests Write to Audit Log?

**NO - Tests explicitly disable logging.**

**Evidence from `tests/test_healing_scripted.py`:**

Line 27:
```python
return HealingExecutor(registry, clean_api, budget, log_events=False)
```

Line 184:
```python
executor = HealingExecutor(registry, clean_api, budget, log_events=False)
```

Line 222:
```python
executor = HealingExecutor(registry, clean_api, budget, log_events=False)
```

**All 17 tests use `log_events=False`** which prevents any logging.

**Code:** `healer/retry.py` lines 431-433:
```python
def _log_event(...):
    """Log healing event."""
    if not self.log_events:
        return  # Early return - no logging
```

### 4. Verification - Manual Healing with Logging Enabled

**Command executed:**
```bash
.venv\Scripts\python.exe -c "from driftshield.healer.retry import HealingExecutor, Budget; from driftshield.healer.registry import create_default_registry; from fastapi.testclient import TestClient; from driftshield.mock_api.server import app; from driftshield.mock_api import contracts; contracts.set_active('v1'); client = TestClient(app); client.post('/admin/mutate', json={'to': 'v2_full'}); registry = create_default_registry(); budget = Budget(); executor = HealingExecutor(registry, client, budget, log_events=True); result = executor.execute('lookup_user', {'user_id': '123'}); print('Status:', result['status'])"
```

**Result:** File created successfully at `D:\Sakshi\driftshield\patch_log.jsonl`

**Log Entry Content:**
```json
{
  "timestamp": "2026-10-14T08:03:52.570119+00:00",
  "event": "healing",
  "tool": "lookup_user",
  "registry_version_before": 1,
  "registry_version_after": 2,
  "contract_hash_patched_against": "1b67b7224631e4cb029f3064f68c4163b7c8c1fd8805606a72e2adcf6a8c465b",
  "contract_hash_seen_on_retry": "1b67b7224631e4cb029f3064f68c4163b7c8c1fd8805606a72e2adcf6a8c465b",
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
      "tier": null,
      "name": "X-Tenant-Token"
    }
  ],
  "value_origins": ["converted", "config"],
  "outcome": "healed",
  "elapsed_seconds": 0.016770601272583008
}
```

## Summary

| Aspect | Status | Details |
|--------|--------|---------|
| **Log file path** | ✓ Correct | `patch_log.jsonl` in project root |
| **File creation** | ✓ Works | Created on first `log_event()` call |
| **Test logging** | ✗ Disabled | All tests use `log_events=False` |
| **Logging works** | ✓ Verified | Manual test with `log_events=True` succeeded |

## Why Tests Disable Logging

**Intentional design decision:**

1. **Test isolation** - Prevents tests from creating/modifying shared log file
2. **Fast execution** - No I/O overhead
3. **Cleanup simplicity** - No log files to clean up between test runs
4. **Focus** - Tests verify healing logic, not logging

The tests use a `clean_log` fixture in `test_registry.py` to explicitly test logging behavior in isolation.

## Command to Inspect Log After Healing

### View entire log:
```bash
Get-Content patch_log.jsonl
```

### View formatted JSON:
```bash
Get-Content patch_log.jsonl | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### View most recent entry:
```bash
Get-Content patch_log.jsonl | Select-Object -Last 1 | ConvertFrom-Json | ConvertTo-Json
```

### Count entries:
```bash
(Get-Content patch_log.jsonl | Measure-Object -Line).Lines
```

### Python-based inspection:
```python
from driftshield.healer import log
events = log.read_all()
for event in events:
    print(f"{event['timestamp']}: {event['tool']} {event['outcome']} (v{event['registry_version_before']}→v{event['registry_version_after']})")
```

## Recommended Next Steps

### Option 1: Add Test for Logging Behavior (Minimal)
Create a single test that verifies logging works end-to-end:

```python
def test_healing_writes_to_log(clean_api, tmp_path):
    """Test that successful healing writes to patch log."""
    # Use tmp_path for test isolation
    import driftshield.healer.log as log_module
    original_path = log_module.LOG_FILE
    log_module.LOG_FILE = tmp_path / "test_patch_log.jsonl"
    
    try:
        clean_api.post("/admin/mutate", json={"to": "v2_full"})
        registry = create_default_registry()
        budget = Budget()
        executor = HealingExecutor(registry, clean_api, budget, log_events=True)
        
        result = executor.execute("lookup_user", {"user_id": "123"})
        
        assert result["status"] == "healed"
        assert log_module.LOG_FILE.exists()
        
        events = log_module.read_all()
        assert len(events) == 1
        assert events[0]["event"] == "healing"
        assert events[0]["outcome"] == "healed"
    finally:
        log_module.LOG_FILE = original_path
```

### Option 2: Create Demonstration Script
Add `demo_healing_with_log.py` to show logging in action:

```python
"""Demonstrate healing with audit logging."""
from driftshield.healer.retry import HealingExecutor, Budget
from driftshield.healer.registry import create_default_registry
from driftshield.healer import log
from fastapi.testclient import TestClient
from driftshield.mock_api.server import app
from driftshield.mock_api import contracts

# Setup
contracts.set_active("v1")
client = TestClient(app)
client.post("/admin/mutate", json={"to": "v2_full"})

# Execute with logging enabled
registry = create_default_registry()
budget = Budget()
executor = HealingExecutor(registry, client, budget, log_events=True)

print("Executing with drift...")
result = executor.execute("lookup_user", {"user_id": "123"})

print(f"\nStatus: {result['status']}")
print(f"Version: {result['registry_version_before']} → {result['registry_version_after']}")

# Read log
print(f"\nLog entries: {len(log.read_all())}")
print("\nMost recent event:")
events = log.read_all()
if events:
    latest = events[-1]
    print(f"  Tool: {latest['tool']}")
    print(f"  Outcome: {latest['outcome']}")
    print(f"  Changes: {len(latest['changes'])}")
    print(f"  Origins: {latest['value_origins']}")
```

### Option 3: Document Current Behavior (No Code Changes)
Update README to clarify:
- Tests disable logging for isolation
- Logging must be explicitly enabled with `log_events=True`
- Production usage should enable logging
- Log file location is current working directory

## Conclusion

**No bug found.** The logging implementation works correctly. Tests intentionally disable logging via `log_events=False` for test isolation and performance. When logging is enabled with `log_events=True`, events are written to `patch_log.jsonl` as designed.

**Smallest appropriate next step:** Document this behavior in the README or add a single integration test that demonstrates logging works (Option 1 or 3).
