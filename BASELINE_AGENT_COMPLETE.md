# Baseline Agent Implementation - Complete ✅

## Summary
Built `agents/baseline_agent.py` and `tests/test_baseline_agent.py` - a standard tool-calling agent without healing capabilities for comparison with the healing agent.

---

## Implementation

### `driftshield/agents/baseline_agent.py` (253 lines)

**Key Features:**
- ✅ Uses existing `LLMClient` from agents/llm.py (not OpenAI Agents SDK)
- ✅ Single tool: `lookup_user` with hard-coded v1 schema
- ✅ NO healing, NO classification, NO contract check, NO registry
- ✅ Returns raw status code and response body to model
- ✅ Budget enforcement (5 API attempts, 8 model calls)
- ✅ Real token usage tracking from provider
- ✅ Returns same AgentRun structure as healing agent

**Hard-Coded V1 Schema:**
```python
V1_LOOKUP_USER_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {"type": "string"}
    },
    "required": ["user_id"],
    "additionalProperties": False,
}
```

**Function Signature:**
```python
def run(task: str, budget: Budget, client: httpx.Client) -> AgentRun:
    """
    Execute task with baseline agent (no healing).
    
    Args:
        task: Natural language task description
        budget: Shared budget for API and model calls
        client: HTTP client for API calls
        
    Returns:
        AgentRun with execution results
    """
```

**Tool Execution (No Healing):**
```python
# Make raw API call - return status code and body as text
response = client.post("/lookup", json=tool_call.arguments, headers={})

# Return raw status and response to model
result_text = f"Status: {response.status_code}\nResponse: {response.text}"
```

**Key Differences from Healing Agent:**
- ❌ No registry (no version tracking)
- ❌ No healing on schema drift
- ❌ No classification of errors
- ❌ No contract verification
- ❌ No adaptation of arguments
- ❌ No header resolution
- ❌ Just raw API calls with hard-coded schema

---

## Test Coverage

### `tests/test_baseline_agent.py` (149 lines)

**Tests:**

1. ✅ **test_baseline_v1_succeeds** (Real LLM)
   - Baseline agent succeeds on v1 schema
   - Hard-coded schema matches API
   - Verifies correct answer "Asha Rao"
   - Skips on rate limit

2. ✅ **test_baseline_v2_full_behavior** (Real LLM)
   - Observes baseline agent behavior on v2_full drift
   - Prints actual attempts, tokens, status, answer
   - **Does NOT assert failure** - just observes
   - Verifies budget respected
   - Skips on rate limit

3. ✅ **test_baseline_budget_respected** (Real LLM)
   - Verifies budget limits enforced
   - Tests with tight budget
   - Skips on rate limit

4. ✅ **test_baseline_budget_exhausted_mocked** (Mocked)
   - Tests budget_exhausted status
   - No API calls required
   - Always runnable

---

## Test Results

### Mocked Test (Always Runnable)
```bash
.venv\Scripts\python.exe -m pytest tests/test_baseline_agent.py::test_baseline_budget_exhausted_mocked -v
========================= 1 passed in 1.06s ==========================
```

### Real LLM Tests (Skip on Rate Limit)
**Requires LLM_API_KEY and available quota**

When rate limited:
- Tests skip cleanly with informative message
- No impact on other tests

When quota available:
- `test_baseline_v1_succeeds` - Verifies success on v1
- `test_baseline_v2_full_behavior` - Observes drift behavior
- `test_baseline_budget_respected` - Verifies budget enforcement

---

## Expected Behavior

### On v1 Schema (Matching)
```
✅ SUCCESS
- Agent uses hard-coded v1 schema: {"user_id": "123"}
- API expects v1 format: {"user_id": "123"}
- Schema matches → API call succeeds
- Model gets successful response
- Returns correct answer: "Asha Rao"
```

### On v2_full Schema (Drift)
```
❌ EXPECTED FAILURE (or partial success with retries)
- Agent uses hard-coded v1 schema: {"user_id": "123"}
- API expects v2_full format: {"target": {"id": 123}}
- Schema mismatch → API returns 422 error
- Model sees: "Status: 422\nResponse: {...validation error...}"
- Model may retry with different formats (wasting budget)
- NO healing available to adapt
- Eventually fails or gives incorrect answer
```

**Test prints actual behavior for observation:**
```
=== Baseline Agent on v2_full ===
Status: failed/ok
Success: False/True
Model calls: X
API attempts: Y
Tokens in: XXX
Tokens out: YYY
Elapsed: X.XXXs
Final answer: [whatever model produces]
Correct: False/True
=================================
```

---

## Comparison with Healing Agent

### Baseline Agent (No Healing)
- Hard-coded v1 schema
- Raw API calls
- No adaptation
- Fails on drift
- Wastes budget on retries
- Returns incorrect/no answer on drift

### Healing Agent (With Healing)
- Dynamic registry
- Drift detection
- Automatic adaptation
- Succeeds on drift
- Efficient budget use
- Returns correct answer after healing

---

## Budget Enforcement

Both agents use the same Budget class:

```python
budget = Budget(max_api_attempts=5, max_model_calls=8)
```

**Baseline agent respects:**
- ✅ max_api_attempts = 5
- ✅ max_model_calls = 8
- ✅ Returns "budget_exhausted" when limits reached
- ✅ Tracks real token usage from provider
- ✅ Tracks real API attempts

---

## AgentRun Structure

Both agents return the same structure:

```python
AgentRun({
    "agent_name": "baseline_agent",  # or "healing_agent"
    "success": bool,
    "final_text": str,
    "status": "ok" | "healed" | "safe_stop" | "failed" | "budget_exhausted",
    "model_calls": int,
    "api_attempts": int,
    "tokens_in": int,
    "tokens_out": int,
    "elapsed_seconds": float,
    "registry_versions_seen": [],  # Empty for baseline
    "reason": str | None,
    "correct": bool
})
```

**Baseline differences:**
- `agent_name`: "baseline_agent"
- `status`: Never "healed" or "safe_stop"
- `registry_versions_seen`: Always empty []

---

## Integration

### Imports
```python
from driftshield.agents.baseline_agent import run
from driftshield.agents.common import AgentRun, STANDARD_TASK
from driftshield.healer.retry import Budget  # Shared budget only
```

**No imports from:**
- ❌ healer/registry.py
- ❌ healer/classifier.py
- ❌ healer/differ.py
- ❌ healer/patcher.py
- ❌ healer/guard.py
- ❌ healer/interceptor.py

**Only shared:**
- ✅ Budget from healer/retry.py
- ✅ LLMClient from agents/llm.py
- ✅ AgentRun from agents/common.py

---

## Running Tests

### Run Mocked Test (No API Key Required)
```bash
.venv\Scripts\python.exe -m pytest tests/test_baseline_agent.py::test_baseline_budget_exhausted_mocked -v
```

### Run All Tests (Requires LLM_API_KEY)
```bash
.venv\Scripts\python.exe -m pytest tests/test_baseline_agent.py -v -s
```

### Run v1 Success Test Only
```bash
.venv\Scripts\python.exe -m pytest tests/test_baseline_agent.py::test_baseline_v1_succeeds -v -s
```

### Run v2_full Observation Test
```bash
.venv\Scripts\python.exe -m pytest tests/test_baseline_agent.py::test_baseline_v2_full_behavior -v -s
```

**The v2_full test will print detailed output showing actual behavior.**

---

## Key Design Decisions

### 1. Hard-Coded v1 Schema
**Why:** Simulates a typical agent that doesn't adapt to schema changes.

**Impact:** Agent fails when API schema evolves.

### 2. Raw Status and Response
**Why:** Shows model exactly what API returned, including errors.

**Format:**
```
Status: 422
Response: {"detail":[{"loc":["body","user_id"],"msg":"field required"...}]}
```

**Impact:** Model sees validation errors but has no way to adapt.

### 3. No Error Handling
**Why:** Demonstrates behavior without intelligent error classification.

**Impact:** All errors treated the same - model must figure out what went wrong.

### 4. Single Tool Definition
**Why:** Keeps baseline simple and focused.

**Impact:** Easy to compare with healing agent's dynamic tool building.

### 5. Same Budget Class
**Why:** Fair comparison - both agents have same resource limits.

**Impact:** Shows efficiency differences in budget usage.

---

## Expected Usage Pattern

```python
from fastapi.testclient import TestClient
from driftshield.agents.baseline_agent import run
from driftshield.agents.common import STANDARD_TASK
from driftshield.healer.retry import Budget
from driftshield.mock_api.server import app

# Setup
client = TestClient(app)
budget = Budget(max_api_attempts=5, max_model_calls=8)

# Run baseline agent
result = run(STANDARD_TASK, budget, client)

print(f"Status: {result.status}")
print(f"Success: {result.success}")
print(f"Answer: {result.final_text}")
print(f"Correct: {result.correct}")
print(f"Resources: {result.model_calls} calls, {result.api_attempts} attempts")
print(f"Tokens: {result.tokens_in} in, {result.tokens_out} out")
```

---

## Files Created

### New Files
- `driftshield/agents/baseline_agent.py` (253 lines)
- `tests/test_baseline_agent.py` (149 lines)
- `BASELINE_AGENT_COMPLETE.md` (this file)

### Modified Files
- None (no changes to existing files)

---

## Status: ✅ COMPLETE

**Implementation:** Complete with all requirements met  
**Testing:** 4 tests (1 mocked passing, 3 real LLM skip on rate limit)  
**Integration:** Uses existing conventions  
**Comparison:** Ready to compare with healing agent  

**Key Features:**
- ✅ Hard-coded v1 schema
- ✅ No healing capabilities
- ✅ Budget enforcement
- ✅ Real token tracking
- ✅ Same AgentRun structure
- ✅ Raw status/response to model
- ✅ Only imports shared Budget

**Ready for:** Phase 3 comparison and benchmarking

Date: Baseline agent implementation complete
