# Phase 3.1 Integration Guide

Quick reference for using the LLM wrapper and common structures in Phase 3.2+

---

## Basic Usage

### 1. Create LLM Client with Budget

```python
from driftshield.agents.llm import LLMClient, BudgetExhausted
from driftshield.healer.retry import Budget

# Create shared budget
budget = Budget(max_api_attempts=5, max_model_calls=8)

# Initialize LLM client
client = LLMClient(budget)
```

### 2. Make a Simple Chat Request

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"}
]

try:
    reply = client.chat(messages)
    print(f"Response: {reply.text}")
    print(f"Tokens: {reply.tokens_in} in, {reply.tokens_out} out")
except BudgetExhausted:
    print("Budget exhausted!")
```

### 3. Make a Chat Request with Tools

```python
# Define tools in OpenAI format
tools = [
    {
        "type": "function",
        "function": {
            "name": "lookup_user",
            "description": "Look up a user by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID"}
                },
                "required": ["user_id"]
            }
        }
    }
]

messages = [
    {"role": "user", "content": "Look up user 123"}
]

reply = client.chat(messages, tools=tools)

# Check if model wants to call a tool
if reply.tool_calls:
    for tool_call in reply.tool_calls:
        print(f"Tool: {tool_call.name}")
        print(f"Args: {tool_call.arguments}")
else:
    print(f"Text: {reply.text}")
```

### 4. Create AgentRun Result

```python
from driftshield.agents.common import AgentRun, is_correct
import time

start_time = time.time()

# ... agent execution ...

run = AgentRun(
    agent_name="baseline",
    success=True,
    final_text="The user's name is Asha Rao",
    status="ok",
    model_calls=2,
    api_attempts=2,
    tokens_in=50,
    tokens_out=20,
    elapsed_seconds=time.time() - start_time,
    registry_versions_seen=[],  # Empty for baseline without registry
    reason=None,
    correct=None  # Will be set by is_correct()
)

# Check correctness
run.correct = is_correct(run.final_text)
print(f"Correct: {run.correct}")  # True because contains "Asha Rao"
```

---

## Integration with Existing Components

### Tool Registry Integration

```python
from driftshield.healer.registry import ToolRegistry

# Get tool definitions for LLM
registry = ToolRegistry()
# ... register tools ...

# Build tools list (rebuilt on EVERY call - no caching per Rule 5)
tools = registry.build_tools()

# Convert to OpenAI format
openai_tools = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["body_schema"]
        }
    }
    for tool in tools
]

# Pass to LLM
reply = client.chat(messages, tools=openai_tools)
```

### Healing Executor Integration

```python
from driftshield.healer.retry import HealingExecutor
import httpx

# Create healing executor with shared budget
executor = HealingExecutor(
    registry=registry,
    client=httpx.Client(base_url="http://localhost:8000"),
    budget=budget,
    log_events=True
)

# When LLM requests a tool call
if reply.tool_calls:
    tool_call = reply.tool_calls[0]
    
    # Execute with automatic healing
    result = executor.execute(
        tool_name=tool_call.name,
        args=tool_call.arguments
    )
    
    # Check result status
    if result["status"] == "ok":
        print(f"Success: {result['result_body']}")
    elif result["status"] == "healed":
        print(f"Healed drift: {result['result_body']}")
        print(f"Version: {result['registry_version_before']} -> {result['registry_version_after']}")
    else:
        print(f"Failed: {result['reason']}")
```

### Tracking Registry Versions

```python
registry_versions_seen = []

# Before each model call
current_version = registry.version("lookup_user")
registry_versions_seen.append(current_version)

# After execution
run = AgentRun(
    # ...
    registry_versions_seen=registry_versions_seen,
    # ...
)
```

---

## Standard Task

```python
from driftshield.agents.common import STANDARD_TASK, is_correct

# The canonical task
print(STANDARD_TASK)
# Output: "Look up the user with id 123 and tell me their name."

# Correct answer: "Asha Rao"
# Check if response is correct
assert is_correct("The user's name is Asha Rao") == True
assert is_correct("User 123 is named Asha Rao") == True
assert is_correct("Their name is John Doe") == False
```

---

## Error Handling

### Budget Exhaustion

```python
from driftshield.agents.llm import BudgetExhausted

try:
    reply = client.chat(messages)
except BudgetExhausted:
    # Budget depleted
    run = AgentRun(
        agent_name="my_agent",
        success=False,
        final_text="",
        status="budget_exhausted",
        model_calls=budget.model_calls,
        api_attempts=budget.api_attempts,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        elapsed_seconds=elapsed,
        reason="Model call budget exhausted"
    )
```

### Missing API Key

```python
try:
    client = LLMClient(budget)
except ValueError as e:
    print(f"Configuration error: {e}")
    # "LLM_API_KEY not found in environment"
```

### Malformed Tool Arguments

```python
# Client handles malformed JSON gracefully
# Returns empty dict instead of crashing
reply = client.chat(messages, tools=tools)

if reply.tool_calls:
    tool_call = reply.tool_calls[0]
    if not tool_call.arguments:
        # Model returned malformed JSON
        # arguments = {} (empty dict)
        print("Warning: No valid arguments provided")
```

---

## Important Constraints

### Temperature
⚠️ **DO NOT pass temperature parameter**
- gpt-6-luna only supports default temperature (1)
- Passing temperature=0 will cause API error
- LLMClient handles this automatically

### Token Counts
✅ **Always use actual token counts**
- Extract from reply.tokens_in and reply.tokens_out
- Never estimate or hardcode values
- These come directly from API response

### Budget Tracking
✅ **Use shared Budget instance**
- Pass same Budget to both LLMClient and HealingExecutor
- Budget tracks both model calls and API attempts
- Check exhausted() before making calls if needed

### Tool List Rebuilding
✅ **Rebuild tools on EVERY model call (Rule 5)**
- Call registry.build_tools() before each chat()
- Never cache the tools list
- Registry may have been patched since last call

---

## Testing Patterns

### Mock LLM for Unit Tests

```python
from unittest.mock import Mock, patch

def test_my_agent():
    with patch('driftshield.agents.llm.OpenAI') as mock_openai:
        # Setup mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance
        
        # Test code here
        client = LLMClient(budget)
        reply = client.chat([{"role": "user", "content": "test"}])
        
        assert reply.text == "Test response"
        assert reply.tokens_in == 10
        assert reply.tokens_out == 5
```

### Skip Real API Tests When No Key

```python
import pytest
import os

@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY not configured"
)
def test_with_real_api():
    client = LLMClient(budget)
    reply = client.chat([{"role": "user", "content": "Hello"}])
    assert reply.text is not None
```

---

## Complete Example: Simple Agent

```python
import time
from driftshield.agents.llm import LLMClient, BudgetExhausted
from driftshield.agents.common import AgentRun, STANDARD_TASK, is_correct
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import ToolRegistry
import httpx

def run_simple_agent():
    """Example agent that uses healing executor."""
    start_time = time.time()
    
    # Setup
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    client = LLMClient(budget)
    
    registry = ToolRegistry()
    # ... register tools ...
    
    executor = HealingExecutor(
        registry=registry,
        client=httpx.Client(base_url="http://localhost:8000"),
        budget=budget,
        log_events=True
    )
    
    # Track metrics
    tokens_in_total = 0
    tokens_out_total = 0
    registry_versions = []
    
    try:
        # Build tool definitions
        tools_list = registry.build_tools()
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["body_schema"]
                }
            }
            for tool in tools_list
        ]
        
        # Track current version
        registry_versions.append(registry.version("lookup_user"))
        
        # First LLM call
        messages = [
            {"role": "user", "content": STANDARD_TASK}
        ]
        
        reply = client.chat(messages, tools=openai_tools)
        tokens_in_total += reply.tokens_in
        tokens_out_total += reply.tokens_out
        
        # Execute tool call
        if reply.tool_calls:
            tool_call = reply.tool_calls[0]
            result = executor.execute(tool_call.name, tool_call.arguments)
            
            if result["status"] in ["ok", "healed"]:
                # Track version after healing
                registry_versions.append(registry.version("lookup_user"))
                
                # Second LLM call with result
                messages.append({"role": "assistant", "content": str(reply.tool_calls)})
                messages.append({"role": "tool", "content": str(result["result_body"])})
                
                reply2 = client.chat(messages)
                tokens_in_total += reply2.tokens_in
                tokens_out_total += reply2.tokens_out
                
                final_text = reply2.text
                success = True
                status = result["status"]
            else:
                final_text = f"Tool execution failed: {result['reason']}"
                success = False
                status = result["status"]
        else:
            final_text = reply.text or ""
            success = True
            status = "ok"
        
        # Create run result
        run = AgentRun(
            agent_name="simple_agent",
            success=success,
            final_text=final_text,
            status=status,
            model_calls=budget.model_calls,
            api_attempts=budget.api_attempts,
            tokens_in=tokens_in_total,
            tokens_out=tokens_out_total,
            elapsed_seconds=time.time() - start_time,
            registry_versions_seen=registry_versions,
            correct=is_correct(final_text) if success else False
        )
        
        return run
        
    except BudgetExhausted:
        return AgentRun(
            agent_name="simple_agent",
            success=False,
            final_text="",
            status="budget_exhausted",
            model_calls=budget.model_calls,
            api_attempts=budget.api_attempts,
            tokens_in=tokens_in_total,
            tokens_out=tokens_out_total,
            elapsed_seconds=time.time() - start_time,
            registry_versions_seen=registry_versions,
            reason="Budget exhausted"
        )
```

---

**Phase 3.1 Integration Guide** - Ready for Phase 3.2+ implementation
