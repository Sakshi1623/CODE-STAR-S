"""Healing agent with automatic drift recovery.

This agent executes tasks using the LLM and tool system, automatically
handling schema drift through the healing executor.
"""

import time
from typing import Any

from driftshield.agents.llm import LLMClient, BudgetExhausted
from driftshield.agents.common import AgentRun, is_correct
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import ToolRegistry


def run(
    task: str,
    registry: ToolRegistry,
    executor: HealingExecutor,
    budget: Budget
) -> AgentRun:
    """
    Execute a task with automatic healing.

    This agent:
    - Rebuilds tool list on every iteration (no caching per Rule 5)
    - Tracks registry versions before each model call
    - Executes tools through the healing executor
    - Stops immediately on safe_stop or failed
    - Returns final text when LLM provides it
    - Tracks all metrics: tokens, calls, versions, time

    Args:
        task: Natural language task description
        registry: Tool registry (will be queried/patched during execution)
        executor: Healing executor for tool calls
        budget: Shared budget for model and API calls

    Returns:
        AgentRun with complete execution metrics and results
    """
    start_time = time.time()

    # Track metrics
    tokens_in_total = 0
    tokens_out_total = 0
    registry_versions_seen: list[int] = []

    # Track if any healing occurred
    healing_occurred = False

    # Track timing for MTTR calculation
    t_first_failure: float | None = None
    t_first_success: float | None = None

    # Initialize conversation
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": task}
    ]

    # Create LLM client with shared budget
    try:
        llm_client = LLMClient(budget)
    except ValueError as e:
        # API key not configured
        return AgentRun(
            agent_name="healing_agent",
            success=False,
            final_text="",
            status="failed",
            model_calls=0,
            api_attempts=budget.api_attempts,
            tokens_in=0,
            tokens_out=0,
            elapsed_seconds=time.time() - start_time,
            registry_versions_seen=[],
            reason=str(e),
            correct=False,
            t_first_failure=None,
            t_first_success=None,
        )

    try:
        # Main agent loop with iteration limit
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            # Fresh tools every iteration (Rule 5: never cache)
            tools_list = registry.build_tools()

            # Convert to OpenAI format
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"]
                    }
                }
                for tool in tools_list
            ]

            # Track current registry version before model call
            try:
                current_version = registry.version("lookup_user")
                registry_versions_seen.append(current_version)
            except KeyError:
                # Tool not in registry
                pass

            # Make LLM call
            reply = llm_client.chat(messages, tools=openai_tools)

            # Track tokens
            tokens_in_total += reply.tokens_in
            tokens_out_total += reply.tokens_out

            # Check if LLM returned final text
            if reply.text and not reply.tool_calls:
                # Final answer received
                elapsed = time.time() - start_time

                # Determine status based on whether healing occurred
                if healing_occurred:
                    status = "healed"
                else:
                    status = "ok"

                return AgentRun(
                    agent_name="healing_agent",
                    success=True,
                    final_text=reply.text,
                    status=status,
                    model_calls=budget.model_calls,
                    api_attempts=budget.api_attempts,
                    tokens_in=tokens_in_total,
                    tokens_out=tokens_out_total,
                    elapsed_seconds=elapsed,
                    registry_versions_seen=registry_versions_seen,
                    reason=None,
                    correct=is_correct(reply.text),
                    t_first_failure=t_first_failure,
                    t_first_success=t_first_success,
                )

            # Process tool calls
            if reply.tool_calls:
                # Add assistant message with tool calls to conversation
                # Format for OpenAI: assistant message with tool_calls
                assistant_msg = {
                    "role": "assistant",
                    "content": reply.text if reply.text else None,
                }

                # Add tool_calls in OpenAI format
                tool_calls_for_msg = []
                for i, tc in enumerate(reply.tool_calls):
                    import json
                    tool_calls_for_msg.append({
                        "id": f"call_{i}",
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
                    # Check if tool is supported
                    if tool_call.name != "lookup_user":
                        # Unsupported tool - add error message
                        messages.append({
                            "role": "tool",
                            "tool_call_id": f"call_{i}",
                            "content": json.dumps({"error": f"Unsupported tool: {tool_call.name}"})
                        })
                        continue

                    # Execute through healing executor
                    result = executor.execute(tool_call.name, tool_call.arguments)

                    # Capture timing information
                    if result.get("t_first_failure") is not None and t_first_failure is None:
                        t_first_failure = result["t_first_failure"]
                    if result.get("t_first_success") is not None and t_first_success is None:
                        t_first_success = result["t_first_success"]

                    # Check result status - immediate stopping
                    if result["status"] in ["safe_stop", "failed"]:
                        # Stop immediately, don't make another LLM call
                        elapsed = time.time() - start_time

                        return AgentRun(
                            agent_name="healing_agent",
                            success=False,
                            final_text="",
                            status=result["status"],
                            model_calls=budget.model_calls,
                            api_attempts=budget.api_attempts,
                            tokens_in=tokens_in_total,
                            tokens_out=tokens_out_total,
                            elapsed_seconds=elapsed,
                            registry_versions_seen=registry_versions_seen,
                            reason=result["reason"],
                            correct=False,
                            t_first_failure=t_first_failure,
                            t_first_success=t_first_success,
                        )

                    # Check if healing occurred
                    if result["status"] == "healed":
                        healing_occurred = True

                    # Add tool result to conversation
                    if result["result_body"]:
                        tool_content = json.dumps(result["result_body"])
                    else:
                        tool_content = json.dumps({"status": result["status"]})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": f"call_{i}",
                        "content": tool_content
                    })

                # Continue to next iteration for LLM to process tool results
                continue

            # No text and no tool calls - unexpected
            elapsed = time.time() - start_time
            return AgentRun(
                agent_name="healing_agent",
                success=False,
                final_text="",
                status="failed",
                model_calls=budget.model_calls,
                api_attempts=budget.api_attempts,
                tokens_in=tokens_in_total,
                tokens_out=tokens_out_total,
                elapsed_seconds=elapsed,
                registry_versions_seen=registry_versions_seen,
                reason="LLM returned neither text nor tool calls",
                correct=False,
                t_first_failure=t_first_failure,
                t_first_success=t_first_success,
            )

        # Max iterations reached
        elapsed = time.time() - start_time
        return AgentRun(
            agent_name="healing_agent",
            success=False,
            final_text="",
            status="failed",
            model_calls=budget.model_calls,
            api_attempts=budget.api_attempts,
            tokens_in=tokens_in_total,
            tokens_out=tokens_out_total,
            elapsed_seconds=elapsed,
            registry_versions_seen=registry_versions_seen,
            reason=f"Maximum iterations ({max_iterations}) reached",
            correct=False,
            t_first_failure=t_first_failure,
            t_first_success=t_first_success,
        )

    except BudgetExhausted:
        # Budget exhausted
        elapsed = time.time() - start_time

        return AgentRun(
            agent_name="healing_agent",
            success=False,
            final_text="",
            status="budget_exhausted",
            model_calls=budget.model_calls,
            api_attempts=budget.api_attempts,
            tokens_in=tokens_in_total,
            tokens_out=tokens_out_total,
            elapsed_seconds=elapsed,
            registry_versions_seen=registry_versions_seen,
            reason="Budget exhausted",
            correct=False,
            t_first_failure=t_first_failure,
            t_first_success=t_first_success,
        )
