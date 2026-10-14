# DriftShield Phase 3.1: Common Agent Structure and LLM Wrapper - COMPLETE ✅

## Implementation Date
Context transfer continuation - Phase 3.1 delivery

## Status
**All requirements implemented and tested. All 91 tests passing (86 existing + 5 new).**

---

## Files Created

### 1. `driftshield/agents/__init__.py`
- Package initialization for agents module

### 2. `driftshield/agents/common.py`
- **AgentRun dataclass** with complete execution tracking:
  - `agent_name`: Agent identifier
  - `success`: Completion status
  - `final_text`: Agent's final response
  - `status`: One of ok, healed, safe_stop, failed, budget_exhausted
  - `model_calls`: Number of LLM calls made
  - `api_attempts`: Total API attempts including retries
  - `tokens_in`: Total input tokens consumed (from actual API responses)
  - `tokens_out`: Total output tokens generated (from actual API responses)
  - `elapsed_seconds`: Total execution time
  - `registry_versions_seen`: List of versions observed (one per model call, empty for baseline)
  - `reason`: Optional explanation of outcome
  - `correct`: Optional boolean for answer correctness
  
- **Standard task**: "Look up the user with id 123 and tell me their name."
  
- **is_correct() function**: Returns True only when final_text contains "Asha Rao" (case-insensitive)

### 3. `driftshield/agents/llm.py`
- **LLMClient class**: Thin wrapper around OpenAI Python SDK
  - Reads `LLM_API_KEY` from environment via existing config pattern
  - Uses `gpt-6-luna` model
  - **DOES NOT pass temperature parameter** (gpt-6-luna only supports default temperature=1)
  - Uses `max_completion_tokens` parameter (OpenAI API v3+)
  - Integrates with existing `Budget` class from `driftshield.healer.retry`
  - Consumes one model call per request via `budget.consume_model()`
  - Raises `BudgetExhausted` exception when budget is depleted
  
- **BudgetExhausted exception**: Custom exception for budget exhaustion
  
- **LLMReply dataclass**: Response structure
  - `text`: Text response (None if only tool calls)
  - `tool_calls`: List of ToolCall objects
  - `tokens_in`: Actual input tokens from API response
  - `tokens_out`: Actual output tokens from API response
  
- **ToolCall dataclass**: Tool call structure
  - `name`: Tool name
  - `arguments`: Tool arguments as dict
  
- **chat() method**: Main API interface
  - Parameters: messages (list), tools (optional list)
  - Returns: LLMReply with actual token counts from API
  - Handles text responses and tool calls
  - Safely parses tool arguments (returns empty dict if malformed JSON)
  - Never fabricates tool arguments

### 4. `tests/test_llm_smoke.py`
- **5 comprehensive tests** (all passing):
  
  1. **test_llm_real_api_text_response** (skips if no API key):
     - Makes one real API call to gpt-6-luna
     - Verifies non-empty text response
     - Confirms actual token counts are non-zero
     - Validates budget consumption
     
  2. **test_llm_budget_integration_mocked**:
     - Verifies budget checking before calls
     - Tests budget consumption tracking
     - Confirms BudgetExhausted exception on depletion
     
  3. **test_llm_tool_calls_mocked**:
     - Tests tool definition passing
     - Verifies tool call extraction
     - Validates argument parsing
     
  4. **test_llm_malformed_tool_arguments_mocked**:
     - Tests graceful handling of malformed JSON
     - Verifies empty dict returned instead of crash
     
  5. **test_llm_client_requires_api_key**:
     - Tests initialization without API key
     - Verifies ValueError with clear message

---

## Key Design Decisions

### 1. Temperature Parameter Omission
**Issue**: gpt-6-luna rejects `temperature=0` with error:
```
"'temperature' does not support 0 with this model. Only the default (1) value is supported."
```

**Solution**: Do not pass temperature parameter at all. Let model use its default (1).

**Documentation**: This deviation from the original Phase 3 specification (which requested temperature=0) is documented in:
- Module docstring in `llm.py`
- Inline comment in `chat()` method
- This implementation document
- `PHASE3_READY.md` (created earlier)

### 2. Budget Integration
Reused existing `Budget` class from `driftshield.healer.retry`:
- Same interface: `consume_model()`, `exhausted()`
- Custom `BudgetExhausted` exception in agents module
- Budget checked BEFORE making API call
- Budget consumed IMMEDIATELY after check (before API response)
- Prevents unbounded LLM costs

### 3. Token Count Accuracy
**Never estimate tokens**:
- Extract from `response.usage.prompt_tokens`
- Extract from `response.usage.completion_tokens`
- Return actual values in LLMReply
- Tests verify non-zero values from real API

### 4. Tool Argument Safety
Handles malformed tool arguments gracefully:
- Attempts to parse JSON from `tool_call.function.arguments`
- On `json.JSONDecodeError`, returns empty dict `{}`
- Never silently fabricates arguments
- Tests verify this behavior

### 5. Configuration Reuse
Uses existing patterns from Phase 1/2:
- `load_dotenv(override=True)` from config.py pattern
- `os.getenv("LLM_API_KEY")` for key retrieval
- Never prints or logs API key
- ValueError with clear message if key missing

### 6. Test Isolation
- Real API test uses `@skip_if_no_key` decorator
- Unit tests use mocked OpenAI client
- No unnecessary real API calls during test suite runs
- Mocked tests use pytest's `unittest.mock` library

---

## Compatibility Verification

### Existing Code Preserved
- ✅ No modifications to Phase 1 or Phase 2 code
- ✅ All 86 existing tests still pass
- ✅ Budget class reused (not reimplemented)
- ✅ Configuration pattern followed

### New Tests Integrated
- ✅ 5 new LLM smoke tests added
- ✅ Total: 91 tests passing
- ✅ Execution time: 9.06 seconds (reasonable)

### Dependencies
All required packages already installed:
- `openai>=1.0.0` (version 3.29.0 installed)
- `python-dotenv>=1.0.0`
- `pytest>=7.4.0`

---

## Test Results

### LLM Smoke Tests Only
```
.venv\Scripts\python.exe -m pytest tests/test_llm_smoke.py -v

====================== 5 passed in 2.85s =======================
```

**Tests:**
1. test_llm_real_api_text_response - PASSED (real API call)
2. test_llm_budget_integration_mocked - PASSED
3. test_llm_tool_calls_mocked - PASSED
4. test_llm_malformed_tool_arguments_mocked - PASSED
5. test_llm_client_requires_api_key - PASSED

### Complete Test Suite
```
.venv\Scripts\python.exe -m pytest -v

====================== 91 passed in 9.06s ======================
```

**Breakdown:**
- 8 audit log tests ✅
- 9 classifier tests ✅
- 14 differ tests ✅
- 17 healing scripted tests ✅
- 5 LLM smoke tests ✅ (NEW)
- 8 mock API tests ✅
- 18 patcher tests ✅
- 12 registry tests ✅

---

## Security Compliance

### No Secret Exposure
- ✅ API key never printed or logged
- ✅ Masked in smoke_test_llm.py output (sk-proj...E8A format)
- ✅ ValueError message doesn't expose key
- ✅ Test output doesn't show key
- ✅ Error messages don't leak key

### Secure Configuration
- ✅ Uses .env file with load_dotenv
- ✅ Checks for key presence before creating client
- ✅ Fails fast with clear error if missing

---

## API Usage Characteristics

### Real API Call Results (from test_llm_real_api_text_response)
- **Model**: gpt-6-luna
- **Temperature**: 1 (default, only supported value)
- **Request**: "Reply with exactly: Hello"
- **Response**: Contains "hello" (case-insensitive check)
- **Prompt tokens**: > 0 (verified non-zero)
- **Completion tokens**: > 0 (verified non-zero)
- **Budget consumed**: 1 model call

### Token Parameter Compatibility
- ✅ Uses `max_completion_tokens` (not deprecated `max_tokens`)
- ✅ Compatible with OpenAI API v3+
- ✅ Tested with openai package version 3.29.0

---

## Architecture Integration

### Preparation for Phase 3.2+
The LLM client is ready to integrate with:
1. **Tool Registry**: `registry.build_tools()` returns tool definitions in correct format
2. **Healing Executor**: `HealingExecutor.execute()` handles tool calls with automatic drift healing
3. **Budget Tracking**: Shared Budget tracks both model calls and API attempts
4. **Agent Runs**: AgentRun dataclass ready to track complete execution metrics

### No Blocking Issues
- ✅ Real API access verified
- ✅ Budget integration working
- ✅ Tool call extraction validated
- ✅ Token counting accurate
- ✅ Error handling robust

---

## Next Steps for Phase 3.2

Phase 3.1 provides the foundation:
- **Common structures**: AgentRun with all required fields
- **LLM wrapper**: Working integration with gpt-6-luna
- **Budget control**: Prevents runaway costs
- **Standard task**: Defined with correctness check
- **Testing infrastructure**: Patterns established for real and mocked tests

Ready to implement agents that use these components to interact with the healing system.

---

## Important Notes

### Temperature Constraint
⚠️ **CRITICAL**: gpt-6-luna does NOT support temperature=0. It only accepts the default temperature of 1. This is a model-specific limitation discovered during implementation and documented throughout the codebase.

### Token Counting
✅ All token counts are extracted from actual API responses via `response.usage.prompt_tokens` and `response.usage.completion_tokens`. No estimation is used.

### Test Execution
- Real API test skips cleanly if `LLM_API_KEY` not configured
- Unit tests use mocking to avoid unnecessary API calls
- Complete suite runs in ~9 seconds (acceptable for 91 tests)

---

**Phase 3.1 Status**: ✅ COMPLETE and ready for Phase 3.2
