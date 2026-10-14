# OpenAI SDK Version Resolution

## Problem Analysis

The project encountered conflicting requirements:
1. **gpt-6-luna model requirement**: Explicitly requires `max_completion_tokens` parameter
2. **Previous error report**: `TypeError: Completions.create() got an unexpected keyword argument 'max_completion_tokens'`

## Root Cause

Two different Python environments with different OpenAI SDK versions:

```
Global Python:  OpenAI SDK 1.35.0  ❌ Does NOT support max_completion_tokens
Project venv:   OpenAI SDK 3.29.0  ✅ DOES support max_completion_tokens
```

The previous TypeError occurred when someone ran the code using **global Python** (SDK 1.35.0) instead of the **project's virtual environment** (SDK 3.29.0).

## Investigation Results

### SDK Version Check
```bash
# Project virtual environment (CORRECT)
.venv\Scripts\python.exe -c "import openai; print(openai.__version__)"
Output: 3.29.0

# Global Python (WRONG environment)
python -c "import openai; print(openai.__version__)"
Output: 1.35.0
```

### Parameter Support in venv (SDK 3.29.0)
```
max_completion_tokens: ✅ Supported
max_tokens: ✅ Supported (legacy)
```

## Solution

**Use the project's virtual environment consistently** with `max_completion_tokens` as required by gpt-6-luna.

### File Changed: `driftshield/agents/llm.py`

**Line 113**:
```python
# CHANGED BACK TO:
request_params: dict[str, Any] = {
    "model": self.model,
    "messages": messages,
    "max_completion_tokens": 500,  # gpt-6-luna requires max_completion_tokens
}

# REASON: gpt-6-luna specifically requires this parameter
```

## Verification (No API Calls Made)

### Mocked Tests - All Pass
```bash
# LLM smoke tests (using venv)
.venv\Scripts\python.exe -m pytest tests/test_llm_smoke.py -v -k "not real_api"
Result: ✅ 4 passed, 1 deselected

# Healing agent mocked tests (using venv)
.venv\Scripts\python.exe -m pytest tests/test_healing_agent.py -v -k "mocked"
Result: ✅ 4 passed, 4 deselected
```

## Correct Usage

### ✅ ALWAYS Use Project Virtual Environment
```bash
# Correct - uses venv with SDK 3.29.0
.venv\Scripts\python.exe <script>
.venv\Scripts\python.exe -m pytest <tests>
```

### ❌ NEVER Use Global Python
```bash
# Wrong - uses global Python with old SDK 1.35.0
python <script>
python -m pytest <tests>
```

## Requirements.txt Confirmation

The project specifies:
```
openai>=1.0.0
```

SDK 3.29.0 in the venv satisfies this requirement and supports `max_completion_tokens`.

## Preserved Functionality

✅ Model: gpt-6-luna (unchanged)  
✅ Parameter: max_completion_tokens (as required by model)  
✅ Token limit: 500 (unchanged)  
✅ Temperature: Not passed (model default of 1)  
✅ Tool calling: reasoning_effort="none" for gpt-6-luna  
✅ Token accounting: Actual counts from response.usage  
✅ Budget integration: Shared Budget class  

## Summary

**Issue**: Mixed use of global Python (SDK 1.35.0) and venv (SDK 3.29.0)  
**Solution**: Always use project venv with `max_completion_tokens`  
**Changed**: Reverted parameter from `max_tokens` back to `max_completion_tokens`  
**Reason**: gpt-6-luna requires `max_completion_tokens`, and venv SDK 3.29.0 supports it  
**Verified**: 8 mocked tests pass without API calls  

The fix ensures consistency by using the project's virtual environment (SDK 3.29.0) which supports the `max_completion_tokens` parameter required by gpt-6-luna.
