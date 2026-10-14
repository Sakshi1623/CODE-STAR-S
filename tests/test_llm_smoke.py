"""Smoke tests for LLM client with real and mocked API calls.

These tests verify the LLM client integration with OpenAI API
and budget tracking, using both real API calls (when configured)
and mocked calls for unit testing.
"""

import os
import pytest
from unittest.mock import Mock, patch
from openai import RateLimitError

from driftshield.agents.llm import LLMClient, LLMReply, ToolCall, BudgetExhausted
from driftshield.healer.retry import Budget


# Skip real API tests if LLM_API_KEY is not configured
skip_if_no_key = pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY not configured"
)


@skip_if_no_key
def test_llm_real_api_text_response():
    """
    Real API smoke test: Make one short request and verify response.
    
    This test makes an actual API call to verify:
    - Non-empty text response is returned
    - Actual input and output token counts are available and non-zero
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)
    client = LLMClient(budget)
    
    messages = [
        {"role": "user", "content": "Reply with exactly: Hello"}
    ]
    
    try:
        reply = client.chat(messages)
    except RateLimitError as e:
        # Skip if rate limited (429), but let other errors fail the test
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise
    
    # Check text response
    assert reply.text is not None, "Expected non-empty text response"
    assert len(reply.text) > 0, "Expected non-empty text"
    assert "hello" in reply.text.lower(), "Expected response to contain 'hello'"
    
    # Check token counts are real and non-zero
    assert reply.tokens_in > 0, "Expected non-zero input tokens"
    assert reply.tokens_out > 0, "Expected non-zero output tokens"
    
    # Verify budget was consumed
    assert budget.model_calls == 1, "Expected one model call"


def test_llm_budget_integration_mocked():
    """
    Unit test: Verify budget integration with mocked API.
    
    Tests that:
    - Budget is checked before making calls
    - Budget is consumed on each call
    - BudgetExhausted is raised when budget is depleted
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    # Mock the OpenAI client
    with patch('driftshield.agents.llm.OpenAI') as mock_openai:
        # Create mock response
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
        
        client = LLMClient(budget)
        
        # First call should succeed
        reply1 = client.chat([{"role": "user", "content": "Hello"}])
        assert reply1.text == "Test response"
        assert reply1.tokens_in == 10
        assert reply1.tokens_out == 5
        assert budget.model_calls == 1
        
        # Second call should succeed
        reply2 = client.chat([{"role": "user", "content": "Hello again"}])
        assert budget.model_calls == 2
        
        # Third call should raise BudgetExhausted
        with pytest.raises(BudgetExhausted):
            client.chat([{"role": "user", "content": "Too many"}])


def test_llm_tool_calls_mocked():
    """
    Unit test: Verify tool call extraction with mocked API.
    
    Tests that tool calls are properly extracted and parsed.
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.OpenAI') as mock_openai:
        # Create mock response with tool calls
        mock_tool_call = Mock()
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 8
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance
        
        client = LLMClient(budget)
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "lookup_user",
                    "description": "Look up user by ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string"}
                        },
                        "required": ["user_id"]
                    }
                }
            }
        ]
        
        reply = client.chat([{"role": "user", "content": "Look up user 123"}], tools=tools)
        
        # Check tool calls
        assert reply.text is None
        assert len(reply.tool_calls) == 1
        assert reply.tool_calls[0].name == "lookup_user"
        assert reply.tool_calls[0].arguments == {"user_id": "123"}
        
        # Check token counts
        assert reply.tokens_in == 15
        assert reply.tokens_out == 8


def test_llm_malformed_tool_arguments_mocked():
    """
    Unit test: Verify graceful handling of malformed tool arguments.
    
    Tests that malformed JSON in tool arguments doesn't crash,
    but returns empty dict instead.
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.OpenAI') as mock_openai:
        # Create mock response with malformed tool arguments
        mock_tool_call = Mock()
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{invalid json'
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance
        
        client = LLMClient(budget)
        
        # Should not crash, but return empty arguments
        reply = client.chat([{"role": "user", "content": "Test"}])
        
        assert len(reply.tool_calls) == 1
        assert reply.tool_calls[0].name == "lookup_user"
        assert reply.tool_calls[0].arguments == {}


def test_llm_client_requires_api_key():
    """
    Unit test: Verify client requires LLM_API_KEY.
    
    Tests that client initialization fails gracefully without API key.
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)
    
    # Temporarily remove API key from environment
    original_key = os.environ.get("LLM_API_KEY")
    if "LLM_API_KEY" in os.environ:
        del os.environ["LLM_API_KEY"]
    
    try:
        # Mock load_dotenv to not reload the key
        with patch('driftshield.agents.llm.load_dotenv'):
            with pytest.raises(ValueError, match="LLM_API_KEY not found"):
                LLMClient(budget)
    finally:
        # Restore original key
        if original_key:
            os.environ["LLM_API_KEY"] = original_key
