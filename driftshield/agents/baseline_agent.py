"""Baseline agent without healing - for comparison.

This agent uses a hard-coded v1 schema and has no healing capability.
It demonstrates the behavior of a standard tool-calling agent when faced
with schema drift.
"""

import time
import json
from typing import Any

import httpx

from driftshield.agents.llm import LLMClient, BudgetExhausted
from driftshield.agents.common import AgentRun, is_correct
from driftshield.healer.retry import Budget


# Hard-coded v1 schema - never updates
V1_LOOKUP_USER_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {"type": "string"}
    },
    "required": ["user_id"],
    "additionalProperties": False,
}


def run(task: str, budget: Budget, client: httpx.Client) -> AgentRun:
    """
    Execute task with baseline agent (no healing).

    Uses hard-coded v1 schema for lookup_user tool.
    NO healing, NO classification, NO contract check, NO registry.

    Args:
        task: Natural language task description
        budget: Shared budget for API and model calls
        client: HTTP client for API calls

    Returns:
        AgentRun with execution results
    """
    start_time = time.time()

    # Track metrics
    tokens_in_total = 0
    tokens_out_total = 0
    api_attempts = 0

    # Track timing for MTTR calculation
    t_first_failure: float | None = None
    t_first_success: float | None = None

    # Initialize conversation
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": task}
    ]

    # Create LLM client
    try:
        llm_client = LLMClient(budget)
    except ValueError as e:
        # API key not configured
        return AgentRun(
            agent_name="baseline_agent",
            success=False,
            final_text="",
            status="failed",
            model_calls=budget.model_calls,
            api_attempts=api_attempts,
            tokens_in=0,
            tokens_out=0,
            elapsed_seconds=time.time() - start_time,
            registry_versions_seen=[],
            reason=str(e),
            correct=False,
            t_first_failure=None,
            t_first_success=None,
        )

    # Define tool with hard-coded v1 schema
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_user",
                "description": "Look up a user by ID and return their information",
                "parameters": V1_LOOKUP_USER_SCHEMA
            }
        }
    ]

    # Main agent loop
    max_iterations = 10
    iteration = 0

    try:
        while iteration < max_iterations:
            iteration += 1

            # Make LLM call
            reply = llm_client.chat(messages, tools=tools)

            # Track tokens
            tokens_in_total += reply.tokens_in
            tokens_out_total += reply.tokens_out

            # Check if LLM returned final text
            if reply.text and not reply.tool_calls:
                # Final answer received
                elapsed = time.time() - start_time

                return AgentRun(
                    agent_name="baseline_agent",
                    success=True,
                    final_text=reply.text,
                    status="ok",
                    model_calls=budget.model_calls,
                    api_attempts=api_attempts,
                    tokens_in=tokens_in_total,
                    tokens_out=tokens_out_total,
                    elapsed_seconds=elapsed,
                    registry_versions_seen=[],  # No registry
                    reason=None,
                    correct=is_correct(reply.text),
                    t_first_failure=t_first_failure,
                    t_first_success=t_first_success,
                )

            # Process tool calls
            if reply.tool_calls:
                # Add assistant message with tool calls
                assistant_msg = {
                    "role": "assistant",
                    "content": reply.text if reply.text else None,
                }

                # Convert tool calls to dict format for serialization
                # Use model_dump() to preserve all provider-specific metadata (e.g., thought_signature)
                tool_calls_for_msg = []
                for i, tc in enumerate(reply.tool_calls):
                    if tc.raw_tool_call:
                        # Use SDK's model_dump() to get JSON-serializable dict
                        # This preserves all extra fields including nested Gemini metadata
                        if hasattr(tc.raw_tool_call, 'model_dump'):
                            tc_dict = tc.raw_tool_call.model_dump()
                        else:
                            # Fallback for non-Pydantic objects (shouldn't happen with real SDK)
                            tc_dict = {
                                "id": tc.raw_tool_call.id,
                                "type": tc.raw_tool_call.type,
                                "function": {
                                    "name": tc.raw_tool_call.function.name,
                                    "arguments": tc.raw_tool_call.function.arguments,
                                }
                            }
                        tool_calls_for_msg.append(tc_dict)
                    else:
                        # Fallback: manual construction (for backward compatibility)
                        tool_calls_for_msg.append({
                            "id": tc.id if tc.id else f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments)
                            }
                        })

                if tool_calls_for_msg:
                    assistant_msg["tool_calls"] = tool_calls_for_msg

                messages.append(assistant_msg)

                # Execute each tool call
                for i, tool_call in enumerate(reply.tool_calls):
                    if tool_call.name != "lookup_user":
                        # Unknown tool
                        tool_call_id = tool_call.id if tool_call.id else f"call_{i}"
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": f"Unknown tool: {tool_call.name}"})
                        })
                        continue

                    # Execute lookup_user by POSTing to API
                    # NO healing, NO classification - just raw API call
                    if budget.exhausted():
                        # Budget exhausted
                        elapsed = time.time() - start_time
                        return AgentRun(
                            agent_name="baseline_agent",
                            success=False,
                            final_text="",
                            status="budget_exhausted",
                            model_calls=budget.model_calls,
                            api_attempts=api_attempts,
                            tokens_in=tokens_in_total,
                            tokens_out=tokens_out_total,
                            elapsed_seconds=elapsed,
                            registry_versions_seen=[],
                            reason="Budget exhausted before API call",
                            correct=False,
                            t_first_failure=t_first_failure,
                            t_first_success=t_first_success,
                        )

                    budget.consume_api()
                    api_attempts += 1

                    # Make raw API call - return status code and body as text
                    try:
                        response = client.post(
                            "/lookup",
                            json=tool_call.arguments,
                            headers={}  # No extra headers
                        )

                        # Track timing
                        if response.status_code < 200 or response.status_code >= 300:
                            # Non-2xx response
                            if t_first_failure is None:
                                t_first_failure = time.time()
                        else:
                            # 2xx response
                            if t_first_failure is not None and t_first_success is None:
                                # First success after a failure
                                t_first_success = time.time()

                        # Return raw status code and response body as text to model
                        result_text = f"Status: {response.status_code}\nResponse: {response.text}"

                    except Exception as e:
                        # Network error
                        if t_first_failure is None:
                            t_first_failure = time.time()
                        result_text = f"Error: {str(e)}"

                    # Add tool result to conversation
                    tool_call_id = tool_call.id if tool_call.id else f"call_{i}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_text
                    })

                # Continue to next iteration
                continue

            # No text and no tool calls - unexpected
            elapsed = time.time() - start_time
            return AgentRun(
                agent_name="baseline_agent",
                success=False,
                final_text="",
                status="failed",
                model_calls=budget.model_calls,
                api_attempts=api_attempts,
                tokens_in=tokens_in_total,
                tokens_out=tokens_out_total,
                elapsed_seconds=elapsed,
                registry_versions_seen=[],
                reason="LLM returned neither text nor tool calls",
                correct=False,
                t_first_failure=t_first_failure,
                t_first_success=t_first_success,
            )

        # Max iterations reached
        elapsed = time.time() - start_time
        return AgentRun(
            agent_name="baseline_agent",
            success=False,
            final_text="",
            status="failed",
            model_calls=budget.model_calls,
            api_attempts=api_attempts,
            tokens_in=tokens_in_total,
            tokens_out=tokens_out_total,
            elapsed_seconds=elapsed,
            registry_versions_seen=[],
            reason=f"Maximum iterations ({max_iterations}) reached",
            correct=False,
            t_first_failure=t_first_failure,
            t_first_success=t_first_success,
        )

    except BudgetExhausted:
        # Budget exhausted
        elapsed = time.time() - start_time

        return AgentRun(
            agent_name="baseline_agent",
            success=False,
            final_text="",
            status="budget_exhausted",
            model_calls=budget.model_calls,
            api_attempts=api_attempts,
            tokens_in=tokens_in_total,
            tokens_out=tokens_out_total,
            elapsed_seconds=elapsed,
            registry_versions_seen=[],
            reason="Budget exhausted",
            correct=False,
            t_first_failure=t_first_failure,
            t_first_success=t_first_success,
        )
