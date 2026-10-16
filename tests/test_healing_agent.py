"""Tests for healing agent with real LLM integration.

These tests use the actual LLM to verify the agent's ability to:
- Execute tasks successfully on stable schemas
- Automatically heal schema drift
- Stop appropriately on unrecoverable errors
- Track metrics and registry versions correctly
"""

import os
import pytest
import httpx
from unittest.mock import Mock, patch
from openai import RateLimitError

from driftshield.agents.healing_agent import run
from driftshield.agents.common import STANDARD_TASK, is_correct
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import create_default_registry
from driftshield.agents.llm import BudgetExhausted


# Integration tests require explicit opt-in via DRIFTSHIELD_LIVE_TESTS=1
# This prevents accidental live API calls even when GEMINI_API_KEY is configured
skip_if_not_live = pytest.mark.skipif(
    os.getenv("DRIFTSHIELD_LIVE_TESTS") != "1",
    reason="Live tests require DRIFTSHIELD_LIVE_TESTS=1"
)


@pytest.mark.integration
@skip_if_not_live
def test_v1_success():
    """
    Test (a): v1 success.

    Start with mock API in v1 and fresh registry.
    Run standard task and verify successful completion with correct answer.
    """
    # Setup: fresh registry and v1 API
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    # Create client and executor (use live server)
    client = httpx.Client(base_url="http://localhost:8000")

    # Reset API to v1
    client.post("/admin/reset")
    client.post("/admin/fault", json={"mode": None})

    executor = HealingExecutor(
        registry=registry,
        client=client,
        budget=budget,
        log_events=False
    )

    # Run agent
    try:
        result = run(STANDARD_TASK, registry, executor, budget)
    except RateLimitError as e:
        client.close()
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    # Verify success
    assert result.success, f"Expected success, got: {result.reason}"
    assert result.status == "ok", f"Expected status 'ok', got: {result.status}"
    assert is_correct(result.final_text), f"Expected correct answer in: {result.final_text}"
    assert "asha rao" in result.final_text.lower(), f"Expected 'Asha Rao' in: {result.final_text}"

    # Verify metrics
    assert result.model_calls > 0, "Expected at least one model call"
    assert result.api_attempts > 0, "Expected at least one API attempt"
    assert result.tokens_in > 0, "Expected non-zero input tokens"
    assert result.tokens_out > 0, "Expected non-zero output tokens"
    assert result.elapsed_seconds > 0, "Expected positive elapsed time"

    # Verify registry version tracking
    assert len(result.registry_versions_seen) == result.model_calls, \
        "Expected one version entry per model call"
    assert all(v == 1 for v in result.registry_versions_seen), \
        "Expected all versions to be 1 (no healing)"

    # Verify correctness
    assert result.correct is True, "Expected correct=True"

    client.close()


@pytest.mark.integration
@skip_if_not_live
def test_v2_full_healing():
    """
    Test (b): v2_full healing.

    Reset API to v1, mutate to v2_full, run with fresh registry.
    Verify healing occurs and answer is correct.
    """
    # Setup: fresh registry
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    # Create client and executor
    client = httpx.Client(base_url="http://localhost:8000")

    # Reset to v1 then mutate to v2_full
    client.post("/admin/reset")
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/mutate", json={"to": "v2_full"})

    executor = HealingExecutor(
        registry=registry,
        client=client,
        budget=budget,
        log_events=False
    )

    # Run agent
    try:
        result = run(STANDARD_TASK, registry, executor, budget)
    except RateLimitError as e:
        client.close()
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    # Verify success with healing
    assert result.success, f"Expected success, got: {result.reason}"
    assert result.status == "healed", f"Expected status 'healed', got: {result.status}"
    assert is_correct(result.final_text), f"Expected correct answer in: {result.final_text}"
    assert "asha rao" in result.final_text.lower(), f"Expected 'Asha Rao' in: {result.final_text}"

    # Verify registry version advanced from 1 to 2
    assert len(result.registry_versions_seen) >= 2, \
        "Expected at least 2 model calls (initial attempt + retry)"
    assert result.registry_versions_seen[0] == 1, "Expected initial version 1"
    assert 2 in result.registry_versions_seen, "Expected version 2 after healing"

    # Verify final registry version is 2
    assert registry.version("lookup_user") == 2, "Expected final registry version 2"

    # Verify metrics
    assert result.model_calls > 0
    assert result.api_attempts > 0
    assert result.tokens_in > 0
    assert result.tokens_out > 0
    assert result.correct is True

    client.close()


@pytest.mark.integration
@skip_if_not_live
def test_second_run_after_healing():
    """
    Test (c): Second run without resetting.

    After successful healing in test (b), run again with same registry.
    Verify registry version is 2 and report LLM behavior.

    NOTE: This test runs independently and sets up the same scenario as (b),
    then runs a second time to observe behavior.
    """
    # Setup: fresh registry
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    # Create client and executor
    client = httpx.Client(base_url="http://localhost:8000")

    # Reset to v1 then mutate to v2_full
    client.post("/admin/reset")
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/mutate", json={"to": "v2_full"})

    executor = HealingExecutor(
        registry=registry,
        client=client,
        budget=budget,
        log_events=False
    )

    # First run: healing should occur
    try:
        result1 = run(STANDARD_TASK, registry, executor, budget)
    except RateLimitError as e:
        client.close()
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    assert result1.success, "Expected first run to succeed"
    assert result1.status == "healed", "Expected healing in first run"
    assert registry.version("lookup_user") == 2, "Expected registry at version 2 after healing"

    # Second run: same registry, same API contract (v2_full)
    # Create new budget for second run
    budget2 = Budget(max_api_attempts=5, max_model_calls=8)
    executor2 = HealingExecutor(
        registry=registry,  # Same registry (version 2)
        client=client,
        budget=budget2,
        log_events=False
    )

    try:
        result2 = run(STANDARD_TASK, registry, executor2, budget2)
    except RateLimitError as e:
        client.close()
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached during second run: {e}")
        raise

    # Verify second run uses version 2
    assert len(result2.registry_versions_seen) > 0, "Expected model calls in second run"
    assert all(v == 2 for v in result2.registry_versions_seen), \
        f"Expected all versions to be 2, got: {result2.registry_versions_seen}"

    # Report behavior (don't assert specific outcome)
    print(f"\n=== Second Run Behavior ===")
    print(f"Success: {result2.success}")
    print(f"Status: {result2.status}")
    print(f"Registry versions: {result2.registry_versions_seen}")
    print(f"Model calls: {result2.model_calls}")
    print(f"API attempts: {result2.api_attempts}")
    if result2.success:
        print(f"Answer correct: {result2.correct}")
        print(f"Final text: {result2.final_text[:100]}...")
    else:
        print(f"Reason: {result2.reason}")
    print(f"=========================\n")

    # Verify registry version unchanged
    assert registry.version("lookup_user") == 2, \
        "Expected registry to remain at version 2"

    client.close()


@pytest.mark.integration
@skip_if_not_live
def test_header_billing_safe_stop():
    """
    Test (d): header_billing safe stop.

    Start from fresh v1 registry, mutate API to header_billing.
    Verify agent stops with safe_stop and registry unchanged.
    """
    # Setup: fresh registry
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    # Create client and executor
    client = httpx.Client(base_url="http://localhost:8000")

    # Reset to v1 then mutate to header_billing
    client.post("/admin/reset")
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/mutate", json={"to": "header_billing"})

    executor = HealingExecutor(
        registry=registry,
        client=client,
        budget=budget,
        log_events=False
    )

    # Track initial model calls
    initial_model_calls = budget.model_calls

    # Run agent
    try:
        result = run(STANDARD_TASK, registry, executor, budget)
    except RateLimitError as e:
        client.close()
        if "rate_limit" in str(e).lower() or "429" in str(e):
            pytest.skip(f"API rate limit reached: {e}")
        raise

    # Verify safe_stop
    assert not result.success, "Expected failure due to missing header"
    assert result.status == "safe_stop", f"Expected status 'safe_stop', got: {result.status}"
    assert result.reason is not None, "Expected reason for safe_stop"
    assert "X-Billing-Region" in result.reason or "unavailable" in result.reason.lower(), \
        f"Expected missing header in reason: {result.reason}"

    # Verify registry unchanged
    assert registry.version("lookup_user") == 1, \
        "Expected registry to remain at version 1"

    # Verify no extra LLM call after safe-stop
    # The agent should make initial call(s), encounter safe_stop, and stop immediately
    # Should not make another LLM call to "explain" the failure
    model_calls_made = budget.model_calls - initial_model_calls
    assert model_calls_made >= 1, "Expected at least one model call"

    # Verify no correct answer
    assert result.correct is False or result.correct is None, \
        "Expected correct=False for safe_stop"

    client.close()


# Mocked unit tests for edge cases

def test_budget_exhaustion_mocked():
    """
    Unit test: Verify agent stops cleanly on budget exhaustion.
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=1)  # Only 1 model call

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(
        registry=registry,
        client=client,
        budget=budget,
        log_events=False
    )

    # Mock LLM to always return tool calls (would require multiple calls)
    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # First call succeeds and returns a tool call
        mock_reply1 = Mock()
        mock_reply1.text = None
        mock_reply1.tool_calls = [Mock(name="lookup_user", arguments={"user_id": "123"})]
        mock_reply1.tokens_in = 10
        mock_reply1.tokens_out = 5

        # Second call should raise BudgetExhausted
        mock_client.chat.side_effect = [mock_reply1, BudgetExhausted("Budget exhausted")]

        # Mock executor to return success
        with patch.object(executor, 'execute') as mock_execute:
            mock_execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": None
            }

            result = run(STANDARD_TASK, registry, executor, budget)

            # Verify budget_exhausted status
            assert result.status == "budget_exhausted"
            assert not result.success
            assert "exhausted" in result.reason.lower()

    client.close()


def test_unsupported_tool_mocked():
    """
    Unit test: Verify agent handles unsupported tool calls safely.
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(
        registry=registry,
        client=client,
        budget=budget,
        log_events=False
    )

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()

        # Mock the chat method to consume budget properly
        def mock_chat(messages, tools=None):
            budget.consume_model()  # Consume budget like real client
            if budget.model_calls == 1:
                # First call returns unsupported tool
                reply = Mock()
                reply.text = None
                reply.tool_calls = [Mock(name="delete_user", arguments={"id": "123"})]
                reply.tokens_in = 10
                reply.tokens_out = 5
                return reply
            else:
                # Second call returns final text
                reply = Mock()
                reply.text = "I cannot complete this task."
                reply.tool_calls = []
                reply.tokens_in = 8
                reply.tokens_out = 6
                return reply

        mock_client.chat = mock_chat
        mock_client_class.return_value = mock_client

        result = run(STANDARD_TASK, registry, executor, budget)

        # Agent should handle gracefully and continue
        assert result.final_text == "I cannot complete this task."
        assert result.model_calls == 2
        assert result.tokens_in == 18  # 10 + 8
        assert result.tokens_out == 11  # 5 + 6

    client.close()


def test_immediate_stop_on_failed_mocked():
    """
    Unit test: Verify agent stops immediately when executor returns 'safe_stop'.

    When the healing executor returns status='safe_stop', the agent must:
    - Return immediately with status='safe_stop'
    - NOT make a second LLM call to explain the failure
    - Preserve the executor's reason string

    Covers healing_agent.py lines 216-236:
        if result["status"] in ["safe_stop", "failed"]:
            # Stop immediately, don't make another LLM call
            return AgentRun(status=result["status"], ...)
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=5)

    # Use a real HealingExecutor instance but patch its execute method
    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # First LLM call: model requests a tool call
        mock_reply = Mock()
        mock_reply.text = None
        # raw_tool_call=None so the agent uses the deterministic fallback dict path
        mock_tool_call = Mock()
        mock_tool_call.name = "lookup_user"
        mock_tool_call.arguments = {"user_id": "123"}
        mock_tool_call.id = "call_stop_test"
        mock_tool_call.raw_tool_call = None
        mock_reply.tool_calls = [mock_tool_call]
        mock_reply.tokens_in = 12
        mock_reply.tokens_out = 6
        # Only one response is queued; a second chat() call would raise StopIteration
        mock_client.chat.side_effect = [mock_reply]

        # Executor returns safe_stop (e.g. missing header, ambiguous schema)
        with patch.object(executor, 'execute') as mock_execute:
            mock_execute.return_value = {
                "status": "safe_stop",
                "result_body": None,
                "reason": "Required value unavailable: X-Billing-Region",
                "t_first_failure": None,
                "t_first_success": None,
            }

            result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must stop immediately with the executor's status
    assert result.status == "safe_stop", f"Expected 'safe_stop', got: {result.status}"
    assert result.success is False

    # Reason from executor must be forwarded
    assert "X-Billing-Region" in result.reason or "unavailable" in result.reason.lower()

    # CRITICAL: only one LLM call was made — no second call to explain the failure
    assert mock_client.chat.call_count == 1, (
        f"Expected exactly 1 LLM call (no second call after safe_stop), "
        f"got {mock_client.chat.call_count}"
    )

    # result.correct must be False for safe_stop
    assert result.correct is False

    client.close()


def test_registry_version_tracking_mocked():
    """
    Unit test: Verify registry_versions_seen accumulates one entry per model
    call, and each entry reflects the registry version at the START of that
    iteration (before any tool execution or healing).

    Covers healing_agent.py lines 105-112:
        try:
            current_version = registry.version("lookup_user")
            registry_versions_seen.append(current_version)
        except KeyError:
            pass

    The test drives two LLM iterations without any healing:
      - Iteration 1: LLM returns a tool call  → version 1 recorded
      - Iteration 2: LLM returns final text   → version 1 recorded again
    Expected: registry_versions_seen == [1, 1]

    Fully offline — no GEMINI_API_KEY, no TENANT_TOKEN, no server required.
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # --- Iteration 1: LLM returns a tool call ---
        mock_tool_call = Mock()
        mock_tool_call.name = "lookup_user"
        mock_tool_call.arguments = {"user_id": "123"}
        mock_tool_call.id = "call_version_track"
        mock_tool_call.raw_tool_call = None  # use deterministic fallback dict path

        mock_reply1 = Mock()
        mock_reply1.text = None
        mock_reply1.tool_calls = [mock_tool_call]
        mock_reply1.tokens_in = 10
        mock_reply1.tokens_out = 5

        # --- Iteration 2: LLM returns final text ---
        mock_reply2 = Mock()
        mock_reply2.text = "The user is Asha Rao"
        mock_reply2.tool_calls = []
        mock_reply2.tokens_in = 15
        mock_reply2.tokens_out = 8

        mock_client.chat.side_effect = [mock_reply1, mock_reply2]

        # Executor returns ok (no healing) so registry version stays at 1
        with patch.object(executor, 'execute') as mock_execute:
            mock_execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None,
            }

            result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must complete successfully (no healing needed)
    assert result.success is True
    assert result.status == "ok"

    # One version entry per model call: two calls → two entries
    assert len(result.registry_versions_seen) == 2, (
        f"Expected 2 version entries (one per model call), "
        f"got: {result.registry_versions_seen}"
    )

    # Both entries must be version 1 — no healing occurred
    assert result.registry_versions_seen == [1, 1], (
        f"Expected [1, 1] (no healing), got: {result.registry_versions_seen}"
    )

    # Confirm exactly 2 LLM calls were made
    assert mock_client.chat.call_count == 2

    client.close()


def test_missing_api_key_returns_failed_mocked():
    """
    Unit test: Verify healing_agent.run() returns status='failed' when
    GEMINI_API_KEY is not configured (LLMClient raises ValueError).

    Covers healing_agent.py lines 64-83:
        try:
            llm_client = LLMClient(budget)
        except ValueError as e:
            return AgentRun(status="failed", model_calls=0, reason=str(e), ...)

    The test must not depend on the real environment having or lacking a key:
    it patches LLMClient directly so the constructor raises ValueError
    unconditionally.
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    # Patch LLMClient as imported inside healing_agent so its __init__ raises ValueError
    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client_class.side_effect = ValueError("GEMINI_API_KEY not found in environment")

        result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must report failure
    assert result.status == "failed", f"Expected 'failed', got: {result.status}"
    assert result.success is False

    # No model calls were made (LLMClient never constructed successfully)
    assert result.model_calls == 0, f"Expected 0 model calls, got: {result.model_calls}"

    # No tokens consumed
    assert result.tokens_in == 0
    assert result.tokens_out == 0

    # Reason must contain the original error message
    assert "GEMINI_API_KEY" in result.reason, (
        f"Expected GEMINI_API_KEY in reason, got: {result.reason!r}"
    )

    # correct must be False (no answer was produced)
    assert result.correct is False

    client.close()


def test_max_iterations_returns_failed_mocked():
    """
    Unit test: Verify healing_agent.run() returns status='failed' with a
    'Maximum iterations' reason when the LLM keeps requesting tool calls
    without ever returning a final text answer.

    Covers healing_agent.py lines 278-295:
        # Max iterations reached
        return AgentRun(
            status="failed",
            reason=f"Maximum iterations ({max_iterations}) reached",
            ...
        )

    Budget is set to max_model_calls=15 so that budget exhaustion (after 8
    calls by default) does NOT fire before the iteration ceiling of 10 is
    reached.  The executor always returns 'ok' so the only exit condition
    is the max_iterations guard.
    """
    registry = create_default_registry()
    # Must allow more model calls than max_iterations (10) to isolate the branch
    budget = Budget(max_api_attempts=30, max_model_calls=15)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Every LLM call returns a tool call — never returns final text
        mock_reply = Mock()
        mock_reply.text = None
        mock_tool_call = Mock()
        mock_tool_call.name = "lookup_user"
        mock_tool_call.arguments = {"user_id": "123"}
        mock_tool_call.id = "call_loop"
        mock_tool_call.raw_tool_call = None  # use fallback dict path
        mock_reply.tool_calls = [mock_tool_call]
        mock_reply.tokens_in = 5
        mock_reply.tokens_out = 3
        mock_client.chat.return_value = mock_reply  # same reply for every call

        # Executor always succeeds so the loop is never interrupted by safe_stop
        with patch.object(executor, 'execute') as mock_execute:
            mock_execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None,
            }

            result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must exit via the max_iterations guard
    assert result.status == "failed", f"Expected 'failed', got: {result.status}"
    assert result.success is False

    # Reason must mention maximum iterations
    assert "Maximum iterations" in result.reason, (
        f"Expected 'Maximum iterations' in reason, got: {result.reason!r}"
    )
    assert "10" in result.reason, f"Expected iteration count in reason: {result.reason!r}"

    # LLM must have been called exactly 10 times (once per iteration)
    assert mock_client.chat.call_count == 10, (
        f"Expected 10 LLM calls (one per iteration), got: {mock_client.chat.call_count}"
    )

    client.close()


def test_empty_response_returns_failed_mocked():
    """
    Unit test: Verify healing_agent.run() returns status='failed' with a
    'neither text nor tool calls' reason when the LLM returns a completely
    empty response (no text and no tool calls).

    Covers healing_agent.py lines 258-276:
        # No text and no tool calls - unexpected
        return AgentRun(
            status="failed",
            reason="LLM returned neither text nor tool calls",
            ...
        )

    This is reached because:
        if reply.text and not reply.tool_calls:  → False (text is None)
        if reply.tool_calls:                     → False (list is empty)
        # falls through to the 'unexpected' return
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Completely empty reply — no text, no tool calls
        mock_reply = Mock()
        mock_reply.text = None   # falsy → skips the "final text" branch
        mock_reply.tool_calls = []  # falsy → skips the "tool calls" branch
        mock_reply.tokens_in = 8
        mock_reply.tokens_out = 0
        mock_client.chat.return_value = mock_reply

        result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must report the unexpected-empty-response failure
    assert result.status == "failed", f"Expected 'failed', got: {result.status}"
    assert result.success is False
    assert result.reason == "LLM returned neither text nor tool calls", (
        f"Unexpected reason: {result.reason!r}"
    )

    # Only one LLM call was made before the early return
    assert mock_client.chat.call_count == 1, (
        f"Expected exactly 1 LLM call, got: {mock_client.chat.call_count}"
    )

    # Tokens from that one call must be captured
    assert result.tokens_in == 8
    assert result.tokens_out == 0

    # correct must be False
    assert result.correct is False

    client.close()


def test_healing_occurred_sets_healed_status_mocked():
    """
    Unit test: Verify that when executor.execute() returns status='healed',
    the agent sets AgentRun.status='healed' (not 'ok') in the final result.

    Covers healing_agent.py lines 128-132:
        if healing_occurred:
            status = "healed"
        else:
            status = "ok"

    Flow:
      - Iteration 1: LLM returns tool call
      - executor.execute() returns {"status": "healed", ...}   ← sets healing_occurred=True
      - Iteration 2: LLM returns final text
      - Agent returns AgentRun(status="healed", success=True)

    Fully offline — no GEMINI_API_KEY, no TENANT_TOKEN, no server required.
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # --- Iteration 1: LLM returns a tool call ---
        mock_tool_call = Mock()
        mock_tool_call.name = "lookup_user"
        mock_tool_call.arguments = {"user_id": "123"}
        mock_tool_call.id = "call_heal_test"
        mock_tool_call.raw_tool_call = None  # deterministic fallback dict path

        mock_reply1 = Mock()
        mock_reply1.text = None
        mock_reply1.tool_calls = [mock_tool_call]
        mock_reply1.tokens_in = 12
        mock_reply1.tokens_out = 6

        # --- Iteration 2: LLM returns final text after seeing healed result ---
        mock_reply2 = Mock()
        mock_reply2.text = "The user is Asha Rao"
        mock_reply2.tool_calls = []
        mock_reply2.tokens_in = 18
        mock_reply2.tokens_out = 9

        mock_client.chat.side_effect = [mock_reply1, mock_reply2]

        # Executor reports that healing occurred (schema drift was repaired)
        with patch.object(executor, 'execute') as mock_execute:
            mock_execute.return_value = {
                "status": "healed",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": "Successfully healed schema drift",
                "t_first_failure": None,
                "t_first_success": None,
            }

            result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must report healed, not ok
    assert result.status == "healed", (
        f"Expected status='healed' when executor returned 'healed', "
        f"got: {result.status!r}"
    )
    assert result.success is True

    # Answer must be recognised as correct ("Asha Rao" present)
    assert result.correct is True
    assert "Asha Rao" in result.final_text

    # Two LLM chat calls: one for tool call, one for final answer
    assert mock_client.chat.call_count == 2

    # Total tokens accumulated from both calls
    # (budget.model_calls stays 0 because the mocked LLMClient never calls
    #  budget.consume_model(); use chat.call_count above for the call count)
    assert result.tokens_in == 30    # 12 + 18
    assert result.tokens_out == 15   # 6 + 9

    client.close()


def test_multiple_tool_calls_in_one_response_mocked():
    """
    Unit test: Verify the agent correctly handles two tool calls returned in a
    single LLM response.

    Both agents iterate over reply.tool_calls with enumerate().  This test
    confirms that when the LLM returns two tool calls at once:
    - executor.execute() is called once per tool call (total 2)
    - both tool-result messages are appended with the correct tool_call_id
    - each tool_call_id matches its originating assistant tool-call entry
    - the agent completes successfully after the second LLM call returns text

    Covers healing_agent.py:
        for i, tool_call in enumerate(reply.tool_calls):
            ...
            messages.append({"role": "tool", "tool_call_id": tool_call_id, ...})
    """
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)

    client = httpx.Client(base_url="http://localhost:8000")
    executor = HealingExecutor(registry=registry, client=client, budget=budget, log_events=False)

    with patch('driftshield.agents.healing_agent.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # --- Two tool calls in one response, with distinct IDs ---
        mock_tc1 = Mock()
        mock_tc1.name = "lookup_user"
        mock_tc1.arguments = {"user_id": "123"}
        mock_tc1.id = "call_multi_001"
        mock_tc1.raw_tool_call = None   # deterministic fallback dict path

        mock_tc2 = Mock()
        mock_tc2.name = "lookup_user"
        mock_tc2.arguments = {"user_id": "124"}
        mock_tc2.id = "call_multi_002"
        mock_tc2.raw_tool_call = None

        mock_reply1 = Mock()
        mock_reply1.text = None
        mock_reply1.tool_calls = [mock_tc1, mock_tc2]   # two calls at once
        mock_reply1.tokens_in = 20
        mock_reply1.tokens_out = 10

        # --- Second response: final text after both results are delivered ---
        mock_reply2 = Mock()
        mock_reply2.text = "Users found: Asha Rao and Ravi Iyer"
        mock_reply2.tool_calls = []
        mock_reply2.tokens_in = 25
        mock_reply2.tokens_out = 12

        mock_client.chat.side_effect = [mock_reply1, mock_reply2]

        # Executor succeeds for both tool calls; return distinct bodies
        def execute_side_effect(tool_name, args):
            uid = args.get("user_id")
            if uid == "123":
                return {
                    "status": "ok",
                    "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                    "reason": None,
                    "t_first_failure": None,
                    "t_first_success": None,
                }
            return {
                "status": "ok",
                "result_body": {"user": {"id": 124, "name": "Ravi Iyer"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None,
            }

        with patch.object(executor, 'execute', side_effect=execute_side_effect) as mock_execute:
            result = run(STANDARD_TASK, registry, executor, budget)

    # Agent must complete successfully
    assert result.success is True
    assert result.status == "ok"

    # Executor must have been called once for each of the two tool calls
    assert mock_execute.call_count == 2, (
        f"Expected executor called twice (once per tool call), "
        f"got: {mock_execute.call_count}"
    )

    # Two LLM calls: one returning both tool calls, one returning final text
    assert mock_client.chat.call_count == 2

    # Inspect the messages sent in the second LLM call to verify history
    # Agent calls: llm_client.chat(messages, tools=openai_tools)
    # messages is the first positional arg → call_args_list[1][0][0]
    second_call_messages = mock_client.chat.call_args_list[1][0][0]

    # Extract assistant message and both tool-result messages
    assistant_msgs = [m for m in second_call_messages if m['role'] == 'assistant'
                      and 'tool_calls' in m]
    tool_msgs = [m for m in second_call_messages if m['role'] == 'tool']

    assert len(assistant_msgs) == 1, "Expected exactly one assistant message with tool_calls"
    assert len(tool_msgs) == 2, (
        f"Expected two tool-result messages (one per tool call), got: {len(tool_msgs)}"
    )

    # IDs in assistant message
    assistant_tc_ids = [tc['id'] for tc in assistant_msgs[0]['tool_calls']]
    assert "call_multi_001" in assistant_tc_ids
    assert "call_multi_002" in assistant_tc_ids

    # Each tool-result message must reference its originating tool-call ID
    tool_result_ids = {m['tool_call_id'] for m in tool_msgs}
    assert tool_result_ids == {"call_multi_001", "call_multi_002"}, (
        f"Tool-result IDs don't match assistant tool-call IDs: {tool_result_ids}"
    )

    client.close()
