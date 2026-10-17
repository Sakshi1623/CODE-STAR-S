"""Smoke tests for LLM client with real and mocked API calls.

These tests verify the LLM client integration with Google Gemini API
(through OpenAI-compatible endpoint) and budget tracking, using both
real API calls (when configured) and mocked calls for unit testing.
"""

import os
import pytest
from unittest.mock import Mock, patch
from openai import RateLimitError

from driftshield.agents.llm import LLMClient, LLMReply, ToolCall, BudgetExhausted
from driftshield.healer.retry import Budget


# Integration tests require explicit opt-in via DRIFTSHIELD_LIVE_TESTS=1
# This prevents accidental live API calls even when GEMINI_API_KEY is configured
skip_if_not_live = pytest.mark.skipif(
    os.getenv("DRIFTSHIELD_LIVE_TESTS") != "1",
    reason="Live tests require DRIFTSHIELD_LIVE_TESTS=1"
)


@pytest.mark.integration
@skip_if_not_live
def test_llm_real_api_text_response():
    """
    Real API smoke test: Make one short request and verify response.

    This test makes an actual API call to verify:
    - Non-empty text response is returned
    - Actual input and output token counts are available and non-zero

    Run with: DRIFTSHIELD_LIVE_TESTS=1 pytest -m integration
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

    # Mock the OpenAI client and load_dotenv
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

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

        # Verify Gemini configuration
        mock_openai.assert_called_once_with(
            api_key='test-key',
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        assert client.model == "gemini-3.8-flash"

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

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

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

        # Verify max_tokens parameter is used (not max_completion_tokens)
        call_args = mock_client_instance.chat.completions.create.call_args
        assert 'max_tokens' in call_args[1]
        assert call_args[1]['max_tokens'] == 500
        assert 'reasoning_effort' not in call_args[1]  # Should not be present for Gemini

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

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

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


def test_llm_empty_string_response():
    """Test LLMClient handles empty string response correctly."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # Create mock response with empty string content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = ""  # Empty string
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)
        reply = client.chat([{"role": "user", "content": "Test"}])

        # Empty string should be converted to None
        assert reply.text is None
        assert reply.tokens_in == 10
        assert reply.tokens_out == 5


def test_llm_whitespace_only_response():
    """Test LLMClient handles whitespace-only response."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # Create mock response with whitespace
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "   \n  "  # Whitespace only
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 2

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)
        reply = client.chat([{"role": "user", "content": "Test"}])

        # Whitespace-only string should be preserved (not None)
        assert reply.text == "   \n  "
        assert reply.tokens_in == 10
        assert reply.tokens_out == 2


def test_llm_none_content_response():
    """Test LLMClient handles None content (e.g., tool-only response)."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # Create mock response with None content but tool call
        mock_tool_call = Mock()
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"arg": "value"}'

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None  # Explicitly None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)
        reply = client.chat([{"role": "user", "content": "Test"}])

        # None content should stay None
        assert reply.text is None
        assert len(reply.tool_calls) == 1
        assert reply.tool_calls[0].name == "test_tool"
        assert reply.tokens_in == 15
        assert reply.tokens_out == 10


def test_llm_client_requires_api_key():
    """
    Unit test: Verify client requires GEMINI_API_KEY.

    Tests that client initialization fails gracefully without API key.
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    # Temporarily remove API key from environment
    original_key = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]

    try:
        # Mock load_dotenv to not reload the key
        with patch('driftshield.agents.llm.load_dotenv'):
            with pytest.raises(ValueError, match="GEMINI_API_KEY not found"):
                LLMClient(budget)
    finally:
        # Restore original key
        if original_key:
            os.environ["GEMINI_API_KEY"] = original_key


def test_llm_preserves_tool_call_metadata():
    """Test that raw tool_call objects are preserved for Gemini compatibility."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # Create mock tool call with custom metadata (simulating thought_signature)
        mock_tool_call = Mock()
        mock_tool_call.id = "call_abc123"
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "custom_gemini_metadata"  # Gemini-specific field

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
        reply = client.chat([{"role": "user", "content": "Test"}])

        # Verify tool call extracted
        assert len(reply.tool_calls) == 1
        tc = reply.tool_calls[0]

        # Verify standard fields
        assert tc.name == "lookup_user"
        assert tc.arguments == {"user_id": "123"}
        assert tc.id == "call_abc123"

        # Verify raw object preserved (for Gemini metadata)
        assert tc.raw_tool_call is mock_tool_call
        assert hasattr(tc.raw_tool_call, 'thought_signature')
        assert tc.raw_tool_call.thought_signature == "custom_gemini_metadata"


def test_llm_quota_error_handling():
    """Test that 429 quota errors are properly wrapped."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        from driftshield.agents.llm import QuotaError

        mock_client_instance = Mock()
        # Simulate 429 error
        mock_client_instance.chat.completions.create.side_effect = Exception("HTTP 429: Rate limit exceeded")
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)

        with pytest.raises(QuotaError) as exc_info:
            client.chat([{"role": "user", "content": "Test"}])

        assert exc_info.value.status_code == 429
        assert "quota" in str(exc_info.value).lower() or "rate limit" in str(exc_info.value).lower()


def test_llm_bad_request_error_handling():
    """Test that 400 bad request errors are properly wrapped."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        from driftshield.agents.llm import BadRequestError

        mock_client_instance = Mock()
        # Simulate 400 error (thought_signature issue)
        mock_client_instance.chat.completions.create.side_effect = Exception(
            "HTTP 400: Function call is missing a thought_signature in functionCall parts"
        )
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)

        with pytest.raises(BadRequestError) as exc_info:
            client.chat([{"role": "user", "content": "Test"}])

        assert exc_info.value.status_code == 400
        assert "bad request" in str(exc_info.value).lower()


def test_llm_transient_error_handling():
    """Test that 5xx server errors are properly wrapped."""
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        from driftshield.agents.llm import TransientError

        mock_client_instance = Mock()
        # Simulate 503 error
        mock_client_instance.chat.completions.create.side_effect = Exception("HTTP 503: Service unavailable")
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)

        with pytest.raises(TransientError) as exc_info:
            client.chat([{"role": "user", "content": "Test"}])

        assert exc_info.value.status_code == 500
        assert "server error" in str(exc_info.value).lower()



def test_integration_tests_require_opt_in():
    """
    Test that integration tests are skipped by default.

    This test verifies the isolation mechanism: even if GEMINI_API_KEY is present,
    integration tests must not run unless DRIFTSHIELD_LIVE_TESTS=1 is explicitly set.
    """
    # Verify DRIFTSHIELD_LIVE_TESTS is not set to "1" (normal test run)
    assert os.getenv("DRIFTSHIELD_LIVE_TESTS") != "1", \
        "This test must run with DRIFTSHIELD_LIVE_TESTS unset or not '1'"

    # The skip_if_not_live marker should prevent live tests from running
    # This is verified by the test suite completing without making API calls


def test_mocked_tests_work_without_api_key():
    """
    Test that mocked tests can run without GEMINI_API_KEY.

    This verifies that the normal offline test suite doesn't require
    API credentials to be configured.
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)

    # Remove API key temporarily
    original_key = os.environ.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]

    try:
        with patch('driftshield.agents.llm.load_dotenv'), \
             patch.dict(os.environ, {}, clear=True), \
             patch('driftshield.agents.llm.OpenAI') as mock_openai:

            # With mocked OpenAI, we can bypass the API key requirement
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "Mocked response"
            mock_response.choices[0].message.tool_calls = None
            mock_response.usage = Mock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5

            mock_client_instance = Mock()
            mock_client_instance.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client_instance

            # Create client with mocked key in environment
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'mocked-key'}):
                client = LLMClient(budget)
                reply = client.chat([{"role": "user", "content": "Test"}])

                assert reply.text == "Mocked response"
                assert reply.tokens_in == 10
                assert reply.tokens_out == 5
    finally:
        # Restore original key
        if original_key:
            os.environ["GEMINI_API_KEY"] = original_key


def test_llm_connection_error_handling():
    """
    Test that APIConnectionError (network failure before HTTP response) is
    classified as TransientError with status_code=None.

    Covers the new explicit except clause in llm.py:
        except APIConnectionError as e:
            raise TransientError(f"Connection error: {e}", status_code=None) from e
    """
    import httpx as _httpx
    from openai import APIConnectionError as _APIConnectionError
    from driftshield.agents.llm import TransientError

    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # APIConnectionError requires a request keyword argument
        dummy_request = _httpx.Request("POST", "https://generativelanguage.googleapis.com/")
        connection_error = _APIConnectionError(
            message="Connection refused",
            request=dummy_request,
        )

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = connection_error
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)

        with pytest.raises(TransientError) as exc_info:
            client.chat([{"role": "user", "content": "Test"}])

        assert exc_info.value.status_code is None
        assert "connection" in str(exc_info.value).lower()


def test_llm_timeout_error_handling():
    """
    Test that APITimeoutError (request timed out) is classified as
    TransientError with status_code=None.

    Covers the new explicit except clause in llm.py:
        except APITimeoutError as e:
            raise TransientError(f"Request timed out: {e}", status_code=None) from e
    """
    import httpx as _httpx
    from openai import APITimeoutError as _APITimeoutError
    from driftshield.agents.llm import TransientError

    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # APITimeoutError requires a request positional argument
        dummy_request = _httpx.Request("POST", "https://generativelanguage.googleapis.com/")
        timeout_error = _APITimeoutError(request=dummy_request)

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = timeout_error
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)

        with pytest.raises(TransientError) as exc_info:
            client.chat([{"role": "user", "content": "Test"}])

        assert exc_info.value.status_code is None
        assert "timed out" in str(exc_info.value).lower()


def test_llm_not_found_error_handling():
    """
    Test that openai.NotFoundError (404 — wrong model name or endpoint)
    is classified as BadRequestError with status_code=404.

    This is a permanent client-side error (wrong configuration), not
    a transient failure. Covers the new explicit except clause in llm.py:
        except NotFoundError as e:
            raise BadRequestError(f"Not found ...: {e}", status_code=404) from e
    """
    import httpx as _httpx
    from openai import NotFoundError as _NotFoundError
    from driftshield.agents.llm import BadRequestError

    budget = Budget(max_model_calls=1, max_api_attempts=5)

    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:

        # NotFoundError requires message, response, and body
        dummy_request = _httpx.Request("POST", "https://generativelanguage.googleapis.com/")
        dummy_response = _httpx.Response(
            status_code=404,
            request=dummy_request,
        )
        not_found_error = _NotFoundError(
            message="Model 'gemini-3.8-flash' not found",
            response=dummy_response,
            body={"error": {"message": "Model not found"}},
        )

        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = not_found_error
        mock_openai.return_value = mock_client_instance

        client = LLMClient(budget)

        with pytest.raises(BadRequestError) as exc_info:
            client.chat([{"role": "user", "content": "Test"}])

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value).lower()
