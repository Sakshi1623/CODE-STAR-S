"""LLM wrapper for OpenAI gpt-6-luna with budget integration.

This module provides a thin wrapper around the OpenAI Python SDK, integrating
with DriftShield's existing Budget system and configuration.

IMPORTANT: gpt-6-luna only supports default temperature (1).
Do not explicitly pass temperature=0, as it will be rejected by the API.
"""

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

from driftshield.healer.retry import Budget


# Custom exception for budget exhaustion
class BudgetExhausted(Exception):
    """Raised when the shared budget is exhausted."""
    pass


@dataclass
class ToolCall:
    """A single tool call from the LLM."""
    name: str
    """Tool name to invoke"""
    
    arguments: dict[str, Any]
    """Tool arguments as a dictionary"""


@dataclass
class LLMReply:
    """Response from the LLM."""
    
    text: str | None
    """Text response (None if only tool calls)"""
    
    tool_calls: list[ToolCall]
    """List of tool calls requested by the LLM"""
    
    tokens_in: int
    """Input tokens consumed (from API response)"""
    
    tokens_out: int
    """Output tokens generated (from API response)"""


class LLMClient:
    """
    Thin wrapper around OpenAI SDK for gpt-6-luna.
    
    Integrates with DriftShield's Budget system and extracts actual
    token counts from API responses.
    """
    
    def __init__(self, budget: Budget):
        """
        Initialize LLM client.
        
        Args:
            budget: Shared budget for tracking model calls
            
        Raises:
            ValueError: If LLM_API_KEY is not configured
        """
        # Load .env to ensure LLM_API_KEY is available
        load_dotenv(override=True)
        
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=api_key)
        self.budget = budget
        self.model = "gpt-6-luna"
    
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None
    ) -> LLMReply:
        """
        Make a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions in OpenAI format
            
        Returns:
            LLMReply with text, tool_calls, and actual token counts
            
        Raises:
            BudgetExhausted: If budget does not allow another model call
        """
        # Check budget before making the call
        if self.budget.exhausted():
            raise BudgetExhausted("Model call budget exhausted")
        
        # Consume one model call
        self.budget.consume_model()
        
        # Prepare request parameters
        # IMPORTANT: Do not pass temperature=0 for gpt-6-luna
        # The model only supports its default temperature of 1
        request_params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": 500,  # gpt-6-luna requires max_completion_tokens
        }
        
        # Add tools if provided
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"
            # gpt-6-luna requires reasoning_effort='none' for function tools
            request_params["reasoning_effort"] = "none"
        
        # Make the API call
        response = self.client.chat.completions.create(**request_params)
        
        # Extract token counts from actual API response
        usage = response.usage
        tokens_in = usage.prompt_tokens
        tokens_out = usage.completion_tokens
        
        # Extract message content
        choice = response.choices[0]
        message = choice.message
        
        # Extract text content
        text = message.content if message.content else None
        
        # Extract tool calls
        tool_calls_list: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments safely
                import json
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    # If arguments are malformed, use empty dict
                    args = {}
                
                tool_calls_list.append(ToolCall(
                    name=tc.function.name,
                    arguments=args
                ))
        
        return LLMReply(
            text=text,
            tool_calls=tool_calls_list,
            tokens_in=tokens_in,
            tokens_out=tokens_out
        )
