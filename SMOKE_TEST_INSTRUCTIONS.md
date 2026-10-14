# OpenAI API Smoke Test Instructions

## Prerequisites

1. **Install OpenAI SDK:**
   ```bash
   pip install openai
   ```

2. **Verify .env file has LLM_API_KEY:**
   ```bash
   # .env file should contain:
   LLM_API_KEY=sk-...
   ```

## Option 1: Run Smoke Test Script (Recommended)

```bash
python smoke_test_llm.py
```

**What it does:**
- ✓ Loads .env with python-dotenv
- ✓ Reads LLM_API_KEY (without printing it)
- ✓ Creates OpenAI client
- ✓ Makes ONE request to gpt-6-luna at temperature 0
- ✓ Prints response text and token usage
- ✓ Reports errors clearly (auth, model access, quota)

**Expected Output:**
```
✓ API key loaded: sk-proj...syE8A
✓ OpenAI package imported
✓ OpenAI client created

Making test request to gpt-6-luna (temperature=0)...

============================================================
RESPONSE:
============================================================
Hello from DriftShield

============================================================
TOKEN USAGE:
============================================================
  Prompt tokens:     15
  Completion tokens: 4
  Total tokens:      19
============================================================

✅ SUCCESS: OpenAI API access verified
   Model: gpt-6-luna
   Temperature: 0
```

## Option 2: One-Line Python Command

```bash
python -c "import os; from dotenv import load_dotenv; from openai import OpenAI; load_dotenv(override=True); api_key = os.getenv('LLM_API_KEY'); client = OpenAI(api_key=api_key); resp = client.chat.completions.create(model='gpt-6-luna', messages=[{'role': 'user', 'content': 'Say: API test successful'}], temperature=0, max_tokens=20); print(f'Response: {resp.choices[0].message.content}'); print(f'Tokens: prompt={resp.usage.prompt_tokens} completion={resp.usage.completion_tokens} total={resp.usage.total_tokens}')"
```

## Option 3: Manual Python Session

```bash
python
```

Then paste:

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv(override=True)

# Get API key
api_key = os.getenv("LLM_API_KEY")
print(f"Key loaded: {api_key[:7]}...{api_key[-4:]}")

# Create client
client = OpenAI(api_key=api_key)

# Test request
response = client.chat.completions.create(
    model="gpt-6-luna",
    messages=[{"role": "user", "content": "Reply: Hello from DriftShield"}],
    temperature=0,
    max_tokens=50
)

# Display
print(f"\nResponse: {response.choices[0].message.content}")
print(f"\nToken usage:")
print(f"  Prompt: {response.usage.prompt_tokens}")
print(f"  Completion: {response.usage.completion_tokens}")
print(f"  Total: {response.usage.total_tokens}")
```

## Common Error Messages

### Authentication Error
```
❌ AUTHENTICATION ERROR
   The API key may be invalid or expired
   Check LLM_API_KEY in .env file
```

**Fix:** Verify API key in .env file

### Model Access Error
```
❌ MODEL ACCESS ERROR
   Model 'gpt-6-luna' may not be available
   Check your OpenAI account permissions
```

**Fix:** 
- Check if gpt-6-luna is available to your account
- Try fallback model: gpt-4o or gpt-4-turbo

### Quota/Rate Limit Error
```
❌ QUOTA/RATE LIMIT ERROR
   API quota exceeded or rate limit hit
   Check your OpenAI account billing/limits
```

**Fix:** Check OpenAI account billing and usage limits

### Network Error
```
❌ NETWORK ERROR
   Could not connect to OpenAI API
   Check your internet connection
```

**Fix:** Check internet connectivity

## What to Check if Test Fails

1. **API Key Format:**
   - Should start with `sk-proj-` or `sk-`
   - Should be ~200 characters long
   - No extra spaces or newlines

2. **OpenAI Package Version:**
   ```bash
   pip show openai
   # Should be >= 1.0.0
   ```

3. **Environment Loading:**
   ```python
   from dotenv import load_dotenv
   import os
   load_dotenv(override=True)
   print(f"Key exists: {bool(os.getenv('LLM_API_KEY'))}")
   print(f"Key length: {len(os.getenv('LLM_API_KEY', ''))}")
   ```

4. **OpenAI Account:**
   - Log in to platform.openai.com
   - Check API keys are active
   - Check billing/usage limits
   - Verify model access permissions

## Security Notes

- ✓ API key never printed in full
- ✓ Only masked version displayed (sk-proj...E8A)
- ✓ No repeated API calls (single test request)
- ✓ .env file not modified
- ✓ Credentials not hardcoded

## Next Steps After Successful Test

Once smoke test passes:
1. Proceed with Phase 3 implementation
2. Use OpenAI Agents SDK for agent framework
3. Configure gpt-6-luna as default model
4. Set temperature=0 for deterministic responses
5. Implement DriftShield healing agent integration
