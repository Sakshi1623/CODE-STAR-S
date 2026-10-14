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


# Skip real API tests if LLM_API_KEY is not configured
skip_if_no_key = pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY not configured"
)


@pytest.fixture
def clean_api():
    """Reset API to v1."""
    contracts.set_active("v1")
    client = TestClient(app)
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/reset")
    return client


@skip_if_no_key
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


@skip_if_no_key
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


@skip_if_no_key
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
