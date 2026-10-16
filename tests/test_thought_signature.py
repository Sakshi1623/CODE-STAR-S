"""Tests for Gemini thought_signature preservation across multi-turn conversations.

These tests verify that tool call metadata (including thought_signature) is
correctly preserved when constructing assistant messages and continuing
conversations with tool results.
"""

import json
import os
import pytest
from unittest.mock import Mock, patch

from driftshield.agents.llm import LLMClient, BudgetExhausted
from driftshield.agents.healing_agent import run as healing_run
from driftshield.agents.baseline_agent import run as baseline_run
from driftshield.agents.common import STANDARD_TASK
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import create_default_registry


def test_tool_call_preserves_thought_signature():
    """
    Test that raw_tool_call objects preserve thought_signature metadata.
    
    This test verifies the first step: LLMClient extracts tool calls
    and stores the raw SDK object with all Gemini metadata intact.
    """
    budget = Budget(max_model_calls=1, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Simulate Gemini SDK response with thought_signature
        mock_tool_call = Mock()
        mock_tool_call.id = "call_xyz789"
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "gemini_internal_signature_abc123"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 10
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client_instance
        
        client = LLMClient(budget)
        reply = client.chat([{"role": "user", "content": "Test"}])
        
        # Verify tool call was extracted
        assert len(reply.tool_calls) == 1
        tc = reply.tool_calls[0]
        
        # Verify raw object preserved
        assert tc.raw_tool_call is mock_tool_call
        assert tc.raw_tool_call.thought_signature == "gemini_internal_signature_abc123"


def test_assistant_message_uses_raw_tool_call():
    """
    Test that agents use raw_tool_call objects when building assistant messages.
    
    This test verifies the second step: when constructing the assistant message
    for conversation history, the agent reuses the raw SDK object rather than
    manually reconstructing it.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # First response: tool call with thought_signature
        mock_tool_call = Mock()
        mock_tool_call.id = "call_abc123"
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "gemini_sig_xyz"
        mock_tool_call.type = "function"
        # Add model_dump method that returns a dict
        mock_tool_call.model_dump.return_value = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "lookup_user",
                "arguments": '{"user_id": "123"}'
            },
            "thought_signature": "gemini_sig_xyz"
        }
        
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message = Mock()
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage = Mock()
        mock_response1.usage.prompt_tokens = 20
        mock_response1.usage.completion_tokens = 10
        
        # Second response: final answer
        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message = Mock()
        mock_response2.choices[0].message.content = "The user is Asha Rao"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage = Mock()
        mock_response2.usage.prompt_tokens = 30
        mock_response2.usage.completion_tokens = 8
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai.return_value = mock_client_instance
        
        # Create healing agent scenario
        registry = create_default_registry()
        
        # Mock the executor to return success
        with patch('driftshield.healer.retry.HealingExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None
            }
            mock_executor_class.return_value = mock_executor
            
            result = healing_run(STANDARD_TASK, registry, mock_executor, budget)
        
        # Verify the agent made two calls
        assert mock_client_instance.chat.completions.create.call_count == 2
        
        # Inspect the second call's messages to verify raw_tool_call was used
        second_call_args = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call_args[1]['messages']
        
        # Find the assistant message
        assistant_msg = None
        for msg in messages:
            if msg['role'] == 'assistant' and 'tool_calls' in msg:
                assistant_msg = msg
                break
        
        assert assistant_msg is not None, "Expected assistant message with tool_calls"
        assert len(assistant_msg['tool_calls']) == 1
        
        # Verify the tool call in the message is now a dict (for serialization)
        tool_call_in_msg = assistant_msg['tool_calls'][0]
        assert isinstance(tool_call_in_msg, dict), "Tool call should be converted to dict for serialization"
        assert tool_call_in_msg['id'] == "call_abc123"
        assert tool_call_in_msg['type'] in ('function', mock_tool_call.type)  # Could be string or mock
        assert tool_call_in_msg['function']['name'] == "lookup_user"
        assert tool_call_in_msg['function']['arguments'] == '{"user_id": "123"}'
        # Verify Gemini metadata is preserved
        assert 'thought_signature' in tool_call_in_msg, "Expected thought_signature to be preserved"
        assert tool_call_in_msg['thought_signature'] == "gemini_sig_xyz"


def test_multi_turn_conversation_preserves_metadata():
    """
    Test complete multi-turn conversation with tool calls and results.
    
    This test verifies the full flow:
    1. User message -> LLM returns tool call with thought_signature
    2. Assistant message built with raw tool call
    3. Tool result added to conversation
    4. Second LLM call receives complete history with metadata
    5. LLM returns final answer
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Create mock tool call with Gemini metadata
        mock_tool_call = Mock()
        mock_tool_call.id = "call_gemini_001"
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "gemini_thought_abc"
        mock_tool_call.type = "function"
        # Add model_dump method that returns a dict
        mock_tool_call.model_dump.return_value = {
            "id": "call_gemini_001",
            "type": "function",
            "function": {
                "name": "lookup_user",
                "arguments": '{"user_id": "123"}'
            },
            "thought_signature": "gemini_thought_abc"
        }
        
        # First response: tool call
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message = Mock()
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage = Mock()
        mock_response1.usage.prompt_tokens = 25
        mock_response1.usage.completion_tokens = 12
        
        # Second response: final text
        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message = Mock()
        mock_response2.choices[0].message.content = "The user is Asha Rao"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage = Mock()
        mock_response2.usage.prompt_tokens = 40
        mock_response2.usage.completion_tokens = 6
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai.return_value = mock_client_instance
        
        # Run with mocked executor
        registry = create_default_registry()
        
        with patch('driftshield.healer.retry.HealingExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None
            }
            mock_executor_class.return_value = mock_executor
            
            result = healing_run(STANDARD_TASK, registry, mock_executor, budget)
        
        # Verify success
        assert result.success
        assert "Asha Rao" in result.final_text
        
        # Verify conversation structure in second call
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        
        # Expected structure:
        # 1. User message
        # 2. Assistant message with tool_calls
        # 3. Tool message with result
        assert len(messages) >= 3, f"Expected at least 3 messages, got {len(messages)}"
        
        # Verify user message
        assert messages[0]['role'] == 'user'
        
        # Verify assistant message with tool call (now as dict)
        assert messages[1]['role'] == 'assistant'
        assert 'tool_calls' in messages[1]
        tool_call_dict = messages[1]['tool_calls'][0]
        assert isinstance(tool_call_dict, dict), "Tool call should be dict for serialization"
        assert tool_call_dict['id'] == "call_gemini_001"
        assert tool_call_dict['function']['name'] == "lookup_user"
        assert 'thought_signature' in tool_call_dict
        assert tool_call_dict['thought_signature'] == "gemini_thought_abc"
        
        # Verify tool result message
        assert messages[2]['role'] == 'tool'
        assert messages[2]['tool_call_id'] == "call_gemini_001"


def test_fallback_when_raw_tool_call_missing():
    """
    Test that agents fall back to manual construction when raw_tool_call is None.
    
    This ensures backward compatibility if raw_tool_call is somehow missing.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Mock LLMClient.chat to return ToolCall without raw_tool_call
        with patch('driftshield.agents.llm.LLMClient.chat') as mock_chat:
            # First call: tool call without raw object
            from driftshield.agents.llm import LLMReply, ToolCall
            
            tool_call_no_raw = ToolCall(
                name="lookup_user",
                arguments={"user_id": "123"},
                id="call_manual_001",
                raw_tool_call=None  # Explicitly None
            )
            
            reply1 = LLMReply(
                text=None,
                tool_calls=[tool_call_no_raw],
                tokens_in=20,
                tokens_out=10
            )
            
            reply2 = LLMReply(
                text="The user is Asha Rao",
                tool_calls=[],
                tokens_in=30,
                tokens_out=8
            )
            
            mock_chat.side_effect = [reply1, reply2]
            
            # Run with mocked executor
            registry = create_default_registry()
            
            with patch('driftshield.healer.retry.HealingExecutor') as mock_executor_class:
                mock_executor = Mock()
                mock_executor.execute.return_value = {
                    "status": "ok",
                    "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                    "reason": None,
                    "t_first_failure": None,
                    "t_first_success": None
                }
                mock_executor_class.return_value = mock_executor
                
                result = healing_run(STANDARD_TASK, registry, mock_executor, budget)
            
            # Should still succeed using fallback construction
            assert result.success
            assert "Asha Rao" in result.final_text
            
            # Verify manual construction was used in second call
            second_call_messages = mock_chat.call_args_list[1][0][0]
            assistant_msg = None
            for msg in second_call_messages:
                if msg['role'] == 'assistant' and 'tool_calls' in msg:
                    assistant_msg = msg
                    break
            
            assert assistant_msg is not None
            # With fallback, tool_calls should be a dict with standard fields
            tool_call_dict = assistant_msg['tool_calls'][0]
            assert isinstance(tool_call_dict, dict)
            assert tool_call_dict['id'] == "call_manual_001"
            assert tool_call_dict['type'] == "function"
            assert tool_call_dict['function']['name'] == "lookup_user"


def test_tool_call_id_continuity():
    """
    Test that tool_call_id is properly maintained across messages.
    
    The tool call ID from the assistant message must match the tool_call_id
    in the tool result message for proper conversation continuity.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Mock tool call with specific ID
        mock_tool_call = Mock()
        mock_tool_call.id = "call_continuity_test_123"
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "sig_continuity"
        mock_tool_call.type = "function"
        # Add model_dump method that returns a dict
        mock_tool_call.model_dump.return_value = {
            "id": "call_continuity_test_123",
            "type": "function",
            "function": {
                "name": "lookup_user",
                "arguments": '{"user_id": "123"}'
            },
            "thought_signature": "sig_continuity"
        }
        
        # Responses
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message = Mock()
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage = Mock()
        mock_response1.usage.prompt_tokens = 20
        mock_response1.usage.completion_tokens = 10
        
        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message = Mock()
        mock_response2.choices[0].message.content = "The user is Asha Rao"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage = Mock()
        mock_response2.usage.prompt_tokens = 35
        mock_response2.usage.completion_tokens = 7
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai.return_value = mock_client_instance
        
        # Run agent
        registry = create_default_registry()
        
        with patch('driftshield.healer.retry.HealingExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Asha Rao"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None
            }
            mock_executor_class.return_value = mock_executor
            
            result = healing_run(STANDARD_TASK, registry, mock_executor, budget)
        
        # Verify ID continuity in messages
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        
        # Find assistant and tool messages
        assistant_msg = None
        tool_msg = None
        for msg in messages:
            if msg['role'] == 'assistant' and 'tool_calls' in msg:
                assistant_msg = msg
            elif msg['role'] == 'tool':
                tool_msg = msg
        
        assert assistant_msg is not None
        assert tool_msg is not None
        
        # Verify ID matches (tool call is now a dict)
        assert assistant_msg['tool_calls'][0]['id'] == "call_continuity_test_123"
        assert tool_msg['tool_call_id'] == "call_continuity_test_123"


def test_baseline_agent_preserves_metadata():
    """
    Test that baseline agent also preserves thought_signature metadata.
    
    Ensures both agents handle tool calls consistently.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_baseline_001"
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "baseline_sig_xyz"
        mock_tool_call.type = "function"
        # Add model_dump method that returns a dict
        mock_tool_call.model_dump.return_value = {
            "id": "call_baseline_001",
            "type": "function",
            "function": {
                "name": "lookup_user",
                "arguments": '{"user_id": "123"}'
            },
            "thought_signature": "baseline_sig_xyz"
        }
        
        # Responses
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message = Mock()
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage = Mock()
        mock_response1.usage.prompt_tokens = 22
        mock_response1.usage.completion_tokens = 11
        
        mock_response2 = Mock()
        mock_response2.choices = [Mock()]
        mock_response2.choices[0].message = Mock()
        mock_response2.choices[0].message.content = "The user is Asha Rao"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage = Mock()
        mock_response2.usage.prompt_tokens = 38
        mock_response2.usage.completion_tokens = 6
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai.return_value = mock_client_instance
        
        # Mock HTTP client for baseline agent
        from fastapi.testclient import TestClient
        from driftshield.mock_api.server import app
        
        mock_client = TestClient(app)
        mock_client.post("/admin/reset")
        
        result = baseline_run(STANDARD_TASK, budget, mock_client)
        
        # Verify success
        assert result.success
        
        # Verify raw tool call was used
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        
        assistant_msg = None
        for msg in messages:
            if msg['role'] == 'assistant' and 'tool_calls' in msg:
                assistant_msg = msg
                break
        
        assert assistant_msg is not None
        # Verify tool call is now a dict (serializable)
        tool_call_dict = assistant_msg['tool_calls'][0]
        assert isinstance(tool_call_dict, dict), "Tool call should be dict for serialization"
        assert tool_call_dict['id'] == "call_baseline_001"
        assert tool_call_dict['function']['name'] == "lookup_user"
        assert 'thought_signature' in tool_call_dict
        assert tool_call_dict['thought_signature'] == "baseline_sig_xyz"
