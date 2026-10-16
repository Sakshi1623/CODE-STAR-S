"""Tests for baseline agent without healing."""

import os
import pytest
from fastapi.testclient import TestClient
from openai import RateLimitError

from driftshield.agents.baseline_agent import run
from driftshield.agents.common import STANDARD_TASK
from driftshield.healer.retry import Budget
from driftshield.mock_api.server import app
from driftshield.mock_api import contracts


# Integration tests require explicit opt-in via DRIFTSHIELD_LIVE_TESTS=1
# This prevents accidental live API calls even when GEMINI_API_KEY is configured
skip_if_not_live = pytest.mark.skipif(
    os.getenv("DRIFTSHIELD_LIVE_TESTS") != "1",
    reason="Live tests require DRIFTSHIELD_LIVE_TESTS=1"
)


@pytest.fixture
def clean_api():
    """Reset API to v1."""
    contracts.set_active("v1")
    client = TestClient(app)
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/reset")
    return client


@pytest.mark.integration
@skip_if_not_live
def test_baseline_v1_succeeds(clean_api):
    """
    Test: Baseline agent succeeds on v1 schema.

    The hard-coded v1 schema matches the API, so the agent should succeed.
    """
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    try:
        result = run(STANDARD_TASK, budget, clean_api)
    except RateLimitError as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    # Should succeed
    assert result.success, f"Expected success on v1, got: {result.reason}"
    assert result.status == "ok"
    assert "asha rao" in result.final_text.lower(), f"Expected name in: {result.final_text}"

    # Verify metrics
    assert result.model_calls > 0
    assert result.api_attempts > 0
    assert result.tokens_in > 0
    assert result.tokens_out > 0
    assert result.elapsed_seconds > 0

    # Baseline has no registry
    assert result.registry_versions_seen == []

    # Should be correct
    assert result.correct is True


@pytest.mark.integration
@skip_if_not_live
def test_baseline_v2_full_behavior(clean_api):
    """
    Test: Baseline agent behavior on v2_full schema drift.

    The hard-coded v1 schema does NOT match v2_full API.
    This test observes and prints the behavior without asserting failure.

    Expected: Agent will likely fail or produce incorrect results because:
    - Agent sends v1 format: {"user_id": "123"}
    - API expects v2_full format: {"target": {"id": 123}}
    - No healing available to adapt
    """
    # Mutate API to v2_full
    clean_api.post("/admin/mutate", json={"to": "v2_full"})

    budget = Budget(max_api_attempts=5, max_model_calls=8)

    try:
        result = run(STANDARD_TASK, budget, clean_api)
    except RateLimitError as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    # Print actual behavior for observation
    print(f"\n=== Baseline Agent on v2_full ===")
    print(f"Status: {result.status}")
    print(f"Success: {result.success}")
    print(f"Model calls: {result.model_calls}")
    print(f"API attempts: {result.api_attempts}")
    print(f"Tokens in: {result.tokens_in}")
    print(f"Tokens out: {result.tokens_out}")
    print(f"Elapsed: {result.elapsed_seconds:.3f}s")
    if result.final_text:
        print(f"Final answer: {result.final_text[:200]}")
    if result.reason:
        print(f"Reason: {result.reason}")
    print(f"Correct: {result.correct}")
    print(f"=================================\n")

    # Verify metrics are tracked
    assert result.model_calls > 0, "Expected at least one model call"
    assert result.api_attempts > 0, "Expected at least one API attempt"
    assert result.tokens_in > 0, "Expected non-zero input tokens"
    assert result.tokens_out > 0, "Expected non-zero output tokens"

    # Verify budget was respected
    assert result.model_calls <= 8, f"Model calls exceeded budget: {result.model_calls}"
    assert result.api_attempts <= 5, f"API attempts exceeded budget: {result.api_attempts}"

    # No assertions about success/failure - just observe behavior


@pytest.mark.integration
@skip_if_not_live
def test_baseline_budget_respected(clean_api):
    """
    Test: Baseline agent respects budget limits.
    """
    # Create tight budget
    budget = Budget(max_api_attempts=1, max_model_calls=2)

    try:
        result = run(STANDARD_TASK, budget, clean_api)
    except RateLimitError as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    # Verify budget limits were not exceeded
    assert result.model_calls <= 2, f"Exceeded model call budget: {result.model_calls}"
    assert result.api_attempts <= 1, f"Exceeded API attempt budget: {result.api_attempts}"


# Mocked test for budget exhaustion
def test_baseline_budget_exhausted_mocked(clean_api):
    """
    Test: Baseline agent returns budget_exhausted status when budget runs out.
    """
    from unittest.mock import Mock, patch

    # Create very tight budget
    budget = Budget(max_api_attempts=5, max_model_calls=1)

    with patch('driftshield.agents.baseline_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # First call succeeds and returns a tool call
        mock_reply1 = Mock()
        mock_reply1.text = None
        mock_reply1.tool_calls = [Mock(name="lookup_user", arguments={"user_id": "123"})]
        mock_reply1.tokens_in = 10
        mock_reply1.tokens_out = 5

        # Second call would exhaust budget
        from driftshield.agents.llm import BudgetExhausted
        mock_client.chat.side_effect = [mock_reply1, BudgetExhausted("Budget exhausted")]

        result = run(STANDARD_TASK, budget, clean_api)

        # Should return budget_exhausted status
        assert result.status == "budget_exhausted"
        assert not result.success
        assert "exhausted" in result.reason.lower()


def test_baseline_missing_api_key_returns_failed_mocked(clean_api):
    """
    Unit test: Verify baseline_agent.run() returns status='failed' when
    GEMINI_API_KEY is not configured (LLMClient raises ValueError).

    Covers baseline_agent.py lines 65-83:
        try:
            llm_client = LLMClient(budget)
        except ValueError as e:
            return AgentRun(status="failed", model_calls=budget.model_calls,
                            reason=str(e), ...)

    The test patches LLMClient inside baseline_agent so the constructor
    raises ValueError unconditionally — no dependency on real env vars.
    """
    from unittest.mock import patch

    budget = Budget(max_api_attempts=5, max_model_calls=8)

    with patch('driftshield.agents.baseline_agent.LLMClient') as mock_client_class:
        mock_client_class.side_effect = ValueError("GEMINI_API_KEY not found in environment")

        result = run(STANDARD_TASK, budget, clean_api)

    assert result.status == "failed", f"Expected 'failed', got: {result.status}"
    assert result.success is False

    # baseline_agent returns model_calls=budget.model_calls (see baseline_agent.py:71).
    # budget.model_calls is 0 here because budget.consume_model() is only called
    # inside LLMClient.chat(), which is never reached when LLMClient.__init__
    # raises ValueError before the agent loop begins.
    assert result.model_calls == 0, f"Expected 0 model calls, got: {result.model_calls}"

    # No tokens consumed
    assert result.tokens_in == 0
    assert result.tokens_out == 0

    # Reason must propagate the ValueError message
    assert "GEMINI_API_KEY" in result.reason, (
        f"Expected 'GEMINI_API_KEY' in reason, got: {result.reason!r}"
    )

    assert result.correct is False


def test_baseline_empty_response_returns_failed_mocked(clean_api):
    """
    Unit test: Verify baseline_agent.run() returns status='failed' with the
    'neither text nor tool calls' reason when the LLM returns a completely
    empty response.

    Covers baseline_agent.py lines 253-265:
        # No text and no tool calls - unexpected
        return AgentRun(
            status="failed",
            reason="LLM returned neither text nor tool calls",
            ...
        )

    The branch is reached because:
        if reply.text and not reply.tool_calls:  → False (text is None)
        if reply.tool_calls:                     → False (list is empty)
        # falls through to the unexpected return
    """
    from unittest.mock import Mock, patch

    budget = Budget(max_api_attempts=5, max_model_calls=8)

    with patch('driftshield.agents.baseline_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Empty reply — no text, no tool calls
        mock_reply = Mock()
        mock_reply.text = None      # falsy → skips "final text" branch
        mock_reply.tool_calls = []  # falsy → skips "tool calls" branch
        mock_reply.tokens_in = 8
        mock_reply.tokens_out = 0
        mock_client.chat.return_value = mock_reply

        result = run(STANDARD_TASK, budget, clean_api)

    assert result.status == "failed", f"Expected 'failed', got: {result.status}"
    assert result.success is False
    assert result.reason == "LLM returned neither text nor tool calls", (
        f"Unexpected reason: {result.reason!r}"
    )

    # Only one LLM call before early return
    assert mock_client.chat.call_count == 1, (
        f"Expected 1 LLM call, got: {mock_client.chat.call_count}"
    )

    # Tokens from the one call must be captured
    assert result.tokens_in == 8
    assert result.tokens_out == 0

    assert result.correct is False


def test_baseline_max_iterations_returns_failed_mocked(clean_api):
    """
    Unit test: Verify baseline_agent.run() returns status='failed' with a
    'Maximum iterations' reason when the LLM keeps requesting tool calls
    without ever returning a final text answer.

    Covers baseline_agent.py lines 272-284:
        # Max iterations reached
        return AgentRun(
            status="failed",
            reason=f"Maximum iterations ({max_iterations}) reached",
            ...
        )

    Budget is set to max_model_calls=15 so budget exhaustion does not fire
    before the iteration ceiling of 10 is hit.  The mock HTTP client always
    returns a successful API response so the agent never stops for network
    reasons; only the iteration guard terminates the loop.
    """
    from unittest.mock import Mock, patch

    # Budget must exceed max_iterations (10) to isolate the correct branch
    budget = Budget(max_api_attempts=30, max_model_calls=15)

    with patch('driftshield.agents.baseline_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Every LLM call returns a tool call — never returns final text
        mock_tool_call = Mock()
        mock_tool_call.name = "lookup_user"
        mock_tool_call.arguments = {"user_id": "123"}
        mock_tool_call.id = "call_baseline_loop"
        mock_tool_call.raw_tool_call = None  # deterministic fallback dict path

        mock_reply = Mock()
        mock_reply.text = None
        mock_reply.tool_calls = [mock_tool_call]
        mock_reply.tokens_in = 5
        mock_reply.tokens_out = 3
        mock_client.chat.return_value = mock_reply  # same reply every call

        result = run(STANDARD_TASK, budget, clean_api)

    assert result.status == "failed", f"Expected 'failed', got: {result.status}"
    assert result.success is False

    assert "Maximum iterations" in result.reason, (
        f"Expected 'Maximum iterations' in reason, got: {result.reason!r}"
    )
    assert "10" in result.reason, (
        f"Expected iteration count '10' in reason: {result.reason!r}"
    )

    # LLM called exactly 10 times (once per iteration before the guard fires)
    assert mock_client.chat.call_count == 10, (
        f"Expected 10 LLM calls, got: {mock_client.chat.call_count}"
    )
