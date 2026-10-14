"""Common agent structures and task definitions for Phase 3.1.

This module defines the standard AgentRun dataclass and the canonical task
for evaluating agents against the DriftShield healing system.
"""

from dataclasses import dataclass, field
from typing import Literal


# Standard task for agent evaluation
STANDARD_TASK = "Look up the user with id 123 and tell me their name."


@dataclass
class AgentRun:
    """
    Result of an agent execution run.
    
    Tracks success, resource consumption, and healing activity across
    a complete agent interaction with the tool system.
    """
    
    agent_name: str
    """Name/identifier of the agent that ran"""
    
    success: bool
    """Whether the agent completed successfully"""
    
    final_text: str
    """Final text response from the agent"""
    
    status: Literal["ok", "healed", "safe_stop", "failed", "budget_exhausted"]
    """Overall execution status"""
    
    model_calls: int
    """Number of LLM model calls made"""
    
    api_attempts: int
    """Number of API attempts made (including retries)"""
    
    tokens_in: int
    """Total input tokens consumed"""
    
    tokens_out: int
    """Total output tokens generated"""
    
    elapsed_seconds: float
    """Total execution time in seconds"""
    
    registry_versions_seen: list[int] = field(default_factory=list)
    """
    Registry versions observed during execution.
    One entry per model call. Empty for baseline agent without registry access.
    """
    
    reason: str | None = None
    """Explanation of outcome (especially for failures or safe_stops)"""
    
    correct: bool | None = None
    """Whether the final answer is correct (set by is_correct)"""


def is_correct(final_text: str) -> bool:
    """
    Check if the agent's final text contains the correct answer.
    
    For the standard task, the correct answer is "Asha Rao" (user id 123's name).
    
    Args:
        final_text: The agent's final response text
        
    Returns:
        True if the text contains "Asha Rao", False otherwise
    """
    if not final_text:
        return False
    
    # Case-insensitive check for the expected name
    return "asha rao" in final_text.lower()
