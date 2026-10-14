"""Tests for tool registry and logging."""

import pytest
from pathlib import Path

from driftshield.healer.registry import ToolRegistry, Tool, create_default_registry
from driftshield.healer import log
from driftshield import config


@pytest.fixture
def registry():
    """Fresh registry for each test."""
    return ToolRegistry()


@pytest.fixture
def sample_tool() -> Tool:
    """Sample tool definition."""
    return {
        "name": "test_tool",
        "description": "A test tool",
        "operation": "test_op",
        "version": 1,
        "contract_hash": "abc123",
        "body_schema": {
            "type": "object",
            "properties": {"param1": {"type": "string"}},
            "required": ["param1"],
        },
        "required_headers": [],
    }


@pytest.fixture
def clean_log():
    """Clean log file before and after test."""
    if log.LOG_FILE.exists():
        log.LOG_FILE.unlink()
    yield
    if log.LOG_FILE.exists():
        log.LOG_FILE.unlink()


def test_registry_register_and_get(registry, sample_tool):
    """Test registering and retrieving a tool."""
    registry.register(sample_tool)
    
    retrieved = registry.get("test_tool")
    assert retrieved is not None
    assert retrieved["name"] == "test_tool"
    assert retrieved["version"] == 1
    assert retrieved["description"] == "A test tool"


def test_build_tools_reflects_patch_immediately(registry, sample_tool):
    """Test that build_tools reflects a patch immediately."""
    registry.register(sample_tool)
    
    # Initial build
    tools = registry.build_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "test_tool"
    assert tools[0]["parameters"]["properties"]["param1"]["type"] == "string"
    
    # Apply patch with changed schema
    patched_tool = sample_tool.copy()
    patched_tool["body_schema"] = {
        "type": "object",
        "properties": {"param1": {"type": "integer"}},
        "required": ["param1"],
    }
    registry.apply_patch("test_tool", patched_tool, "changed type")
    
    # Build again - should reflect patch immediately
    tools_after = registry.build_tools()
    assert len(tools_after) == 1
    assert tools_after[0]["parameters"]["properties"]["param1"]["type"] == "integer"


def test_version_increases_on_patch(registry, sample_tool):
    """Test that version increases on patch."""
    registry.register(sample_tool)
    assert registry.version("test_tool") == 1
    
    # Apply first patch
    patched_tool = sample_tool.copy()
    patched_tool["body_schema"] = {"type": "object", "properties": {}}
    registry.apply_patch("test_tool", patched_tool, "first patch")
    assert registry.version("test_tool") == 2
    
    # Apply second patch
    registry.apply_patch("test_tool", patched_tool, "second patch")
    assert registry.version("test_tool") == 3


def test_version_increases_on_rollback(registry, sample_tool):
    """Test that version increases on rollback."""
    registry.register(sample_tool)
    assert registry.version("test_tool") == 1
    
    # Apply patch
    patched_tool = sample_tool.copy()
    patched_tool["body_schema"] = {"type": "object", "properties": {"new_field": {"type": "string"}}}
    registry.apply_patch("test_tool", patched_tool, "patch")
    assert registry.version("test_tool") == 2
    
    # Rollback
    registry.rollback("test_tool")
    assert registry.version("test_tool") == 3  # Version continues to increase


def test_rollback_restores_old_schema(registry, sample_tool):
    """Test that rollback restores the previous body_schema."""
    registry.register(sample_tool)
    
    original_schema = sample_tool["body_schema"].copy()
    
    # Apply patch with new schema
    patched_tool = sample_tool.copy()
    patched_tool["body_schema"] = {
        "type": "object",
        "properties": {"new_param": {"type": "integer"}},
        "required": ["new_param"],
    }
    registry.apply_patch("test_tool", patched_tool, "change schema")
    
    # Verify patch applied
    assert registry.get("test_tool")["body_schema"]["properties"].get("new_param") is not None
    
    # Rollback
    registry.rollback("test_tool")
    
    # Verify original schema restored
    restored = registry.get("test_tool")
    assert restored["body_schema"]["properties"].get("param1") is not None
    assert restored["body_schema"]["properties"].get("new_param") is None
    assert restored["body_schema"] == original_schema


def test_rollback_without_history_raises(registry, sample_tool):
    """Test that rollback raises when no history exists."""
    registry.register(sample_tool)
    
    with pytest.raises(KeyError, match="No history available"):
        registry.rollback("test_tool")


def test_log_redacts_secrets(clean_log):
    """Test that log redacts value, token, and secret keys."""
    event = {
        "action": "test",
        "value": "sensitive_value",
        "token": "secret_token",
        "secret": "api_secret",
        "safe_data": "this_is_ok",
    }
    
    log.log_event(event)
    
    # Read back
    events = log.read_all()
    assert len(events) == 1
    
    logged = events[0]
    assert logged["value"] == "<redacted>"
    assert logged["token"] == "<redacted>"
    assert logged["secret"] == "<redacted>"
    assert logged["safe_data"] == "this_is_ok"
    assert "timestamp" in logged


def test_log_redacts_nested_secrets(clean_log):
    """Test that log redacts secrets in nested structures."""
    event = {
        "action": "nested_test",
        "data": {
            "user_id": "123",
            "token": "nested_secret",
            "metadata": {
                "value": "deep_secret"
            }
        },
        "list_data": [
            {"secret": "list_secret"},
            {"public": "ok"}
        ]
    }
    
    log.log_event(event)
    
    events = log.read_all()
    logged = events[0]
    
    assert logged["data"]["token"] == "<redacted>"
    assert logged["data"]["metadata"]["value"] == "<redacted>"
    assert logged["list_data"][0]["secret"] == "<redacted>"
    assert logged["list_data"][1]["public"] == "ok"


def test_create_default_registry():
    """Test that default registry contains lookup_user tool."""
    registry = create_default_registry()
    
    tool = registry.get("lookup_user")
    assert tool is not None
    assert tool["name"] == "lookup_user"
    assert tool["version"] == 1
    assert tool["operation"] == "lookup_user"
    assert "user_id" in tool["body_schema"]["properties"]


def test_build_tools_no_caching(registry, sample_tool):
    """Test that build_tools returns fresh list on every call."""
    registry.register(sample_tool)
    
    tools1 = registry.build_tools()
    tools2 = registry.build_tools()
    
    # Should be equal but not the same object
    assert tools1 == tools2
    assert tools1 is not tools2


def test_config_get_header_value():
    """Test that config.get_header_value returns correct values."""
    # Known header with config value
    result = config.get_header_value("X-Tenant-Token")
    assert result is not None
    value, origin = result
    assert origin == "config"
    assert value == "test-tenant-token-123"
    
    # Unknown header
    result = config.get_header_value("X-Billing-Region")
    assert result is None
    
    # Random header
    result = config.get_header_value("X-Random-Header")
    assert result is None


def test_config_base_url():
    """Test that BASE_URL is loaded from config."""
    assert config.BASE_URL == "http://localhost:8000"
