"""Test that tool call conversation messages can be JSON serialized.

This regression test ensures tool calls in conversation history are serializable
for multi-turn conversations with the OpenAI SDK.

CRITICAL: The OpenAI SDK requires messages to be JSON-serializable dicts.
SDK objects like ChatCompletionMessageToolCall cannot be serialized and will
cause failures in multi-turn conversations.
"""

import json
import pytest
from unittest.mock import Mock, patch
import os

from driftshield.agents.healing_agent import run as healing_run
from driftshield.agents.baseline_agent import run as baseline_run
from driftshield.agents.common import STANDARD_TASK
from driftshield.healer.retry import Budget
from driftshield.healer.registry import create_default_registry


def test_healing_agent_conversation_is_json_serializable():
    """
    Test that healing agent conversation history can be JSON serialized.
    
    This verifies that tool calls are converted to dicts rather than
    keeping SDK objects, which cannot be serialized.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Create mock tool call with Gemini metadata
        mock_tool_call = Mock()
        mock_tool_call.id = "call_test_001"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "gemini_sig"
        
        # Add model_dump method to simulate real SDK behavior
        def model_dump():
            return {
                'id': mock_tool_call.id,
                'type': mock_tool_call.type,
                'function': {
                    'name': mock_tool_call.function.name,
                    'arguments': mock_tool_call.function.arguments
                },
                'thought_signature': mock_tool_call.thought_signature
            }
        mock_tool_call.model_dump = model_dump
        
        # First response: tool call
        mock_response1 = Mock()
        mock_response1.choices = [Mock()]
        mock_response1.choices[0].message = Mock()
        mock_response1.choices[0].message.content = None
        mock_response1.choices[0].message.tool_calls = [mock_tool_call]
        mock_response1.usage = Mock()
        mock_response1.usage.prompt_tokens = 20
        mock_response1.usage.completion_tokens = 10
        
        # Second response: final text
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
        
        # Get the second call's messages
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        
        # CRITICAL TEST: Verify messages can be JSON serialized
        try:
            serialized = json.dumps(messages)
            deserialized = json.loads(serialized)
        except TypeError as e:
            pytest.fail(f"Messages are not JSON serializable: {e}")
        
        # Verify structure after round-trip
        assert len(deserialized) >= 3
        assert deserialized[0]['role'] == 'user'
        assert deserialized[1]['role'] == 'assistant'
        assert 'tool_calls' in deserialized[1]
        assert isinstance(deserialized[1]['tool_calls'][0], dict)
        assert deserialized[1]['tool_calls'][0]['id'] == "call_test_001"
        assert deserialized[2]['role'] == 'tool'


def test_baseline_agent_conversation_is_json_serializable():
    """
    Test that baseline agent conversation history can be JSON serialized.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Create mock tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_baseline_001"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "baseline_sig"
        
        # Add model_dump method
        def model_dump():
            return {
                'id': mock_tool_call.id,
                'type': mock_tool_call.type,
                'function': {
                    'name': mock_tool_call.function.name,
                    'arguments': mock_tool_call.function.arguments
                },
                'thought_signature': mock_tool_call.thought_signature
            }
        mock_tool_call.model_dump = model_dump
        
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
        
        # Mock HTTP client
        from fastapi.testclient import TestClient
        from driftshield.mock_api.server import app
        
        mock_client = TestClient(app)
        mock_client.post("/admin/reset")
        
        result = baseline_run(STANDARD_TASK, budget, mock_client)
        
        # Get messages
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        
        # CRITICAL TEST: Verify JSON serialization
        try:
            serialized = json.dumps(messages)
            deserialized = json.loads(serialized)
        except TypeError as e:
            pytest.fail(f"Messages are not JSON serializable: {e}")
        
        # Verify structure
        assert isinstance(deserialized[1]['tool_calls'][0], dict)
        assert deserialized[1]['tool_calls'][0]['id'] == "call_baseline_001"


def test_thought_signature_preserved_in_serialized_dict():
    """
    Test that Gemini-specific metadata like thought_signature is preserved
    when tool calls are converted to dicts for serialization.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Create mock with thought_signature
        mock_tool_call = Mock()
        mock_tool_call.id = "call_metadata_001"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "important_gemini_metadata"
        mock_tool_call.custom_field = "test_value"  # Additional metadata
        
        # Add model_dump method
        def model_dump():
            return {
                'id': mock_tool_call.id,
                'type': mock_tool_call.type,
                'function': {
                    'name': mock_tool_call.function.name,
                    'arguments': mock_tool_call.function.arguments
                },
                'thought_signature': mock_tool_call.thought_signature,
                'custom_field': mock_tool_call.custom_field
            }
        mock_tool_call.model_dump = model_dump
        
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
        mock_response2.choices[0].message.content = "Done"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage = Mock()
        mock_response2.usage.prompt_tokens = 30
        mock_response2.usage.completion_tokens = 8
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai.return_value = mock_client_instance
        
        registry = create_default_registry()
        
        with patch('driftshield.healer.retry.HealingExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Test"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None
            }
            mock_executor_class.return_value = mock_executor
            
            result = healing_run(STANDARD_TASK, registry, mock_executor, budget)
        
        # Get messages and serialize
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        serialized = json.dumps(messages)
        deserialized = json.loads(serialized)
        
        # Verify Gemini metadata is preserved
        tool_call_dict = deserialized[1]['tool_calls'][0]
        assert 'thought_signature' in tool_call_dict
        assert tool_call_dict['thought_signature'] == "important_gemini_metadata"
        # custom_field should also be preserved
        assert 'custom_field' in tool_call_dict
        assert tool_call_dict['custom_field'] == "test_value"


def test_nested_metadata_preserved_with_model_dump():
    """
    Test that nested Gemini-specific metadata is preserved using model_dump().
    
    This tests that model_dump() correctly handles nested structures.
    """
    budget = Budget(max_model_calls=2, max_api_attempts=5)
    
    with patch('driftshield.agents.llm.load_dotenv'), \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}), \
         patch('driftshield.agents.llm.OpenAI') as mock_openai:
        
        # Create mock with nested metadata and model_dump method
        mock_tool_call = Mock()
        mock_tool_call.id = "call_nested_001"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "lookup_user"
        mock_tool_call.function.arguments = '{"user_id": "123"}'
        mock_tool_call.thought_signature = "gemini_signature"
        mock_tool_call.nested_metadata = {'level1': {'level2': {'level3': 'deep_value'}}}
        
        # Add model_dump method to simulate real SDK
        def model_dump():
            return {
                'id': mock_tool_call.id,
                'type': mock_tool_call.type,
                'function': {
                    'name': mock_tool_call.function.name,
                    'arguments': mock_tool_call.function.arguments
                },
                'thought_signature': mock_tool_call.thought_signature,
                'nested_metadata': mock_tool_call.nested_metadata
            }
        mock_tool_call.model_dump = model_dump
        
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
        mock_response2.choices[0].message.content = "Done"
        mock_response2.choices[0].message.tool_calls = None
        mock_response2.usage = Mock()
        mock_response2.usage.prompt_tokens = 30
        mock_response2.usage.completion_tokens = 8
        
        mock_client_instance = Mock()
        mock_client_instance.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai.return_value = mock_client_instance
        
        registry = create_default_registry()
        
        with patch('driftshield.healer.retry.HealingExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute.return_value = {
                "status": "ok",
                "result_body": {"user": {"id": 123, "name": "Test"}},
                "reason": None,
                "t_first_failure": None,
                "t_first_success": None
            }
            mock_executor_class.return_value = mock_executor
            
            result = healing_run(STANDARD_TASK, registry, mock_executor, budget)
        
        # Get messages and verify serialization
        second_call = mock_client_instance.chat.completions.create.call_args_list[1]
        messages = second_call[1]['messages']
        
        # Serialize and deserialize
        serialized = json.dumps(messages)
        deserialized = json.loads(serialized)
        
        # Verify nested metadata preserved
        tool_call_dict = deserialized[1]['tool_calls'][0]
        assert 'nested_metadata' in tool_call_dict
        assert tool_call_dict['nested_metadata']['level1']['level2']['level3'] == 'deep_value'
        assert 'thought_signature' in tool_call_dict
        assert tool_call_dict['thought_signature'] == 'gemini_signature'


def test_real_sdk_tool_call_with_extra_fields():
    """
    Test serialization with real OpenAI SDK ChatCompletionMessageToolCall
    object that has extra fields.
    
    This verifies model_dump() preserves extra fields as expected.
    """
    from openai.types.chat import ChatCompletionMessageToolCall
    
    # Create real SDK object with extra fields
    real_tc = ChatCompletionMessageToolCall(
        id='call_real_001',
        type='function',
        function={'name': 'test', 'arguments': '{}'},
        thought_signature='gemini_signature_value',
        custom_field='custom_value'
    )
    
    # Verify extra fields are accessible
    assert hasattr(real_tc, 'thought_signature')
    assert real_tc.thought_signature == 'gemini_signature_value'
    assert hasattr(real_tc, 'custom_field')
    assert real_tc.custom_field == 'custom_value'
    
    # Test model_dump preserves extra fields
    dumped = real_tc.model_dump()
    assert isinstance(dumped, dict)
    assert dumped['id'] == 'call_real_001'
    assert dumped['type'] == 'function'
    assert dumped['function']['name'] == 'test'
    assert 'thought_signature' in dumped
    assert dumped['thought_signature'] == 'gemini_signature_value'
    assert 'custom_field' in dumped
    assert dumped['custom_field'] == 'custom_value'
    
    # Verify JSON serialization works
    json_str = json.dumps(dumped)
    deserialized = json.loads(json_str)
    assert deserialized['thought_signature'] == 'gemini_signature_value'
    assert deserialized['custom_field'] == 'custom_value'
