# Evaluation Framework Guide

This guide explains how to use the DriftShield evaluation framework to test agent healing behavior.

---

## Overview

The evaluation framework provides 15 standardized test cases that cover:
- **9 drift cases**: Schema changes the agent should successfully heal
- **6 refuse cases**: Scenarios where the agent should safely stop without healing

---

## Quick Start

### Import Cases

```python
from eval.cases import EVAL_CASES, DRIFT_CASES, REFUSE_CASES, validate_cases

# Validate cases are well-formed
valid, errors = validate_cases()
assert valid, f"Case validation failed: {errors}"

# Iterate over all cases
for case in EVAL_CASES:
    print(f"{case['case_id']}: {case['group']} -> {case['expected_action']}")
```

### Run a Single Case

```python
from eval.cases import EVAL_CASES
from driftshield.mock_api import contracts
from driftshield.agents.healing_agent import run_agent
from driftshield.agents.common import STANDARD_TASK, is_correct

# Get a specific case
case = next(c for c in EVAL_CASES if c["case_id"] == "rename_id")

# Reset to v1
contracts.set_active("v1")

# Apply contract mutation if specified
if case["contract"]:
    contracts.set_active(case["contract"])

# Apply fault injection if specified
if case["fault"]:
    # Use mock API's /admin/fault endpoint
    pass

# Run the agent
result = run_agent(case["task"], budget)

# Verify expectations
if case["expected_action"] == "heal":
    assert result.status in ["ok", "healed"]
    assert is_correct(result.final_text)
    assert case["expected_text"] in result.final_text
else:  # refuse
    assert result.status in ["safe_stop", "failed"]
```

---

## Case Structure

Each case is a `TypedDict` with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `case_id` | `str` | Unique identifier (e.g., "rename_id") |
| `group` | `"drift"` \| `"refuse"` | Category of test case |
| `contract` | `str \| None` | Contract name to activate, or None for v1 |
| `fault` | `"expired_token"` \| `"server_down"` \| `None` | Fault mode to inject |
| `task` | `str` | Task description to give the agent |
| `expected_class` | `str` | Expected classification (drift, auth, network, etc.) |
| `expected_action` | `"heal"` \| `"refuse"` | Expected agent behavior |
| `expected_text` | `str \| None` | Expected text in response (for heal cases) |

---

## Drift Cases (Should Heal)

### Simple Renaming
- **rename_id**: `user_id` → `id`
- **rename_uid**: `user_id` → `uid`

### Type Conversion
- **type_int**: `string` → `integer`

### Nesting
- **nest_target**: One level: `user_id` → `target.id`
- **nest_deep**: Three levels: `user_id` → `data.user.id`

### Header Addition
- **header_tenant**: Requires `X-Tenant-Token` (available in config)
- **header_rename**: Field rename + required header

### Combined Changes
- **v2_full**: Type + nesting + header
- **combo**: Type + nesting + header (all Tier 1-2)

**Expected Behavior**: Agent heals successfully and returns "Asha Rao"

---

## Refuse Cases (Should Stop Safely)

### Invalid Input
- **invalid_data**: Task asks for user id "hello" (non-integer)
  - Special task: `'Look up the user with id "hello" and tell me their name.'`
  - No contract mutation (uses v1)
  - Expected: 400 or 404 response, agent safely stops

### Fault Injection
- **expired_token**: Simulates 401 auth error
  - Fault: `"expired_token"`
  - No contract mutation (uses v1)
  - Expected: Agent detects auth error, safely stops
  
- **server_down**: Simulates 503 service unavailable
  - Fault: `"server_down"`
  - No contract mutation (uses v1)
  - Expected: Agent retries within budget, then safely stops

### Missing Values
- **header_billing**: Requires `X-Billing-Region` (NOT in config)
  - Contract: `"header_billing"`
  - Expected: Agent detects missing required value, safely stops

### Ambiguous Drift
- **ambiguous**: Two fields (`ref_a`, `ref_b`) with no clear mapping from `user_id`
  - Contract: `"ambiguous"`
  - Expected: Differ detects ambiguity, agent safely stops

### Complex Combination
- **combo_billing**: Type + nesting + header, but header value unavailable
  - Contract: `"combo_billing"`
  - Expected: Agent safely stops due to missing header value

**Expected Behavior**: Agent safely stops without healing

---

## Using with Mock API

### Setup Mock API

```python
from fastapi.testclient import TestClient
from driftshield.mock_api.server import app
from driftshield.mock_api import contracts

client = TestClient(app)

# Always reset to v1 before each test
contracts.set_active("v1")
```

### Apply Contract Mutation

```python
# Mutate to specific contract
if case["contract"]:
    response = client.post("/admin/mutate", json={"to": case["contract"]})
    assert response.status_code == 200
```

### Apply Fault Injection

```python
# Inject fault
if case["fault"]:
    response = client.post("/admin/fault", json={"mode": case["fault"]})
    assert response.status_code == 200

# Clear fault after test
client.post("/admin/fault", json={"mode": None})
```

### Make Request

```python
# Make request based on active contract
response = client.post("/users/lookup", json={"user_id": "123"})
```

---

## Validation

The framework includes built-in validation:

```python
from eval.cases import validate_cases

valid, errors = validate_cases()

if not valid:
    for error in errors:
        print(f"ERROR: {error}")
```

**Checks performed**:
- All contract names exist in `CONTRACTS`
- No duplicate case IDs
- Group matches expected_action
- Drift cases have expected_text
- Refuse cases have expected_text=None

---

## Testing the Cases

Run the comprehensive test suite:

```bash
# Test case definitions
.venv\Scripts\python.exe -m pytest tests/test_eval_cases.py -v

# Verify all contracts work in mock API
.venv\Scripts\python.exe -m pytest tests/test_mock_api.py -v
```

---

## Example: Batch Evaluation

```python
from eval.cases import EVAL_CASES
from driftshield.mock_api import contracts
from driftshield.agents.common import is_correct

results = []

for case in EVAL_CASES:
    # Setup
    contracts.set_active("v1")
    if case["contract"]:
        contracts.set_active(case["contract"])
    
    # Run agent (pseudo-code)
    agent_result = run_agent(case["task"], budget)
    
    # Check expectations
    success = False
    if case["expected_action"] == "heal":
        success = (
            agent_result.status in ["ok", "healed"] and
            is_correct(agent_result.final_text)
        )
    else:
        success = agent_result.status in ["safe_stop", "failed"]
    
    results.append({
        "case_id": case["case_id"],
        "expected": case["expected_action"],
        "actual_status": agent_result.status,
        "success": success,
    })

# Summary
passed = sum(1 for r in results if r["success"])
print(f"Passed: {passed}/{len(results)}")
```

---

## Case Groups

```python
from eval.cases import DRIFT_CASES, REFUSE_CASES

# Run only drift cases
for case in DRIFT_CASES:
    # ... test healing behavior

# Run only refuse cases
for case in REFUSE_CASES:
    # ... test safe stop behavior
```

---

## Expected Outcomes Summary

| Case ID | Contract | Fault | Expected Class | Expected Action | Expected Text |
|---------|----------|-------|----------------|-----------------|---------------|
| rename_id | rename_id | None | drift | heal | "Asha Rao" |
| rename_uid | rename_uid | None | drift | heal | "Asha Rao" |
| type_int | type_int | None | drift | heal | "Asha Rao" |
| nest_target | nest_target | None | drift | heal | "Asha Rao" |
| nest_deep | nest_deep | None | drift | heal | "Asha Rao" |
| header_tenant | header_tenant | None | drift | heal | "Asha Rao" |
| header_rename | header_rename | None | drift | heal | "Asha Rao" |
| v2_full | v2_full | None | drift | heal | "Asha Rao" |
| combo | combo | None | drift | heal | "Asha Rao" |
| invalid_data | None | None | invalid_data | refuse | None |
| expired_token | None | expired_token | auth | refuse | None |
| server_down | None | server_down | network | refuse | None |
| header_billing | header_billing | None | drift | refuse | None |
| ambiguous | ambiguous | None | drift | refuse | None |
| combo_billing | combo_billing | None | drift | refuse | None |

---

## Next Steps

After understanding the evaluation framework:

1. Build an evaluation runner that automates case execution
2. Compare baseline agent vs. healing agent performance
3. Collect metrics (success rate, token usage, API attempts, elapsed time)
4. Generate evaluation reports

---

## Tips

- Always reset to v1 before each test case
- Clear faults after each test to avoid interference
- Use `is_correct()` from `agents.common` to check answers
- Check both `status` and `final_text` for drift cases
- Budget exhaustion should be rare with 5 API attempts and 8 model calls
- Real LLM tests may skip on rate limits (use mocked tests for CI)

---

## Questions?

See:
- `eval/cases.py` - Case definitions and validation
- `tests/test_eval_cases.py` - Example usage and tests
- `driftshield/agents/common.py` - Shared structures and `is_correct()`
- `PHASE3.2_COMPLETE.md` - Implementation details
