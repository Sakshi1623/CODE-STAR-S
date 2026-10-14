"""Tests for schema differ."""

import pytest

from driftshield.healer.differ import diff
from driftshield.healer.registry import create_default_registry
from driftshield.mock_api.contracts import CONTRACTS


@pytest.fixture
def v1_tool():
    """Tool on v1 contract."""
    registry = create_default_registry()
    return registry.get("lookup_user")


def test_diff_equal_schemas_returns_empty(v1_tool):
    """Test that identical schemas produce no changes."""
    # Compare v1 tool with v1 contract
    changes = diff(v1_tool, CONTRACTS["v1"])
    assert len(changes) == 0


def test_diff_rename_id(v1_tool):
    """Test rename_id contract: user_id -> id."""
    changes = diff(v1_tool, CONTRACTS["rename_id"])
    
    # Should detect rename
    rename_changes = [c for c in changes if c["type"] == "rename"]
    assert len(rename_changes) == 1
    
    change = rename_changes[0]
    assert change["old_path"] == "user_id"
    assert change["new_path"] == "id"
    assert change["tier"] == 1  # From mapping


def test_diff_type_int(v1_tool):
    """Test type_int contract: string -> integer."""
    changes = diff(v1_tool, CONTRACTS["type_int"])
    
    # Should detect type change
    type_changes = [c for c in changes if c["type"] == "type_change"]
    assert len(type_changes) == 1
    
    change = type_changes[0]
    assert change["path"] == "user_id"
    assert change["from_type"] == "string"
    assert change["to_type"] == "integer"
    assert change["tier"] == 1


def test_diff_nest_target(v1_tool):
    """Test nest_target contract: user_id -> target.id."""
    changes = diff(v1_tool, CONTRACTS["nest_target"])
    
    # Should detect nesting
    nesting_changes = [c for c in changes if c["type"] == "nesting"]
    assert len(nesting_changes) == 1
    
    change = nesting_changes[0]
    assert change["old_path"] == "user_id"
    assert change["new_path"] == "target.id"
    assert change["tier"] == 1  # From mapping


def test_diff_header_tenant(v1_tool):
    """Test header_tenant contract: adds X-Tenant-Token header."""
    changes = diff(v1_tool, CONTRACTS["header_tenant"])
    
    # Should detect new header
    header_changes = [c for c in changes if c["type"] == "new_header"]
    assert len(header_changes) == 1
    
    change = header_changes[0]
    assert change["name"] == "X-Tenant-Token"


def test_diff_v2_full(v1_tool):
    """Test v2_full contract: nesting + type_change + new_header."""
    changes = diff(v1_tool, CONTRACTS["v2_full"])
    
    # Should detect nesting (user_id -> target.id)
    nesting_changes = [c for c in changes if c["type"] == "nesting"]
    assert len(nesting_changes) == 1
    assert nesting_changes[0]["old_path"] == "user_id"
    assert nesting_changes[0]["new_path"] == "target.id"
    
    # Should detect type change (string -> integer)
    type_changes = [c for c in changes if c["type"] == "type_change"]
    assert len(type_changes) == 1
    assert type_changes[0]["from_type"] == "string"
    assert type_changes[0]["to_type"] == "integer"
    
    # Should detect new header (X-Tenant-Token)
    header_changes = [c for c in changes if c["type"] == "new_header"]
    assert len(header_changes) == 1
    assert header_changes[0]["name"] == "X-Tenant-Token"


def test_diff_combo(v1_tool):
    """Test combo contract: same as v2_full (nesting + type + header)."""
    changes = diff(v1_tool, CONTRACTS["combo"])
    
    # Should have same changes as v2_full
    nesting_changes = [c for c in changes if c["type"] == "nesting"]
    assert len(nesting_changes) == 1
    
    type_changes = [c for c in changes if c["type"] == "type_change"]
    assert len(type_changes) == 1
    
    header_changes = [c for c in changes if c["type"] == "new_header"]
    assert len(header_changes) == 1


def test_diff_header_billing(v1_tool):
    """Test header_billing contract: adds X-Billing-Region header."""
    changes = diff(v1_tool, CONTRACTS["header_billing"])
    
    # Should detect new header
    header_changes = [c for c in changes if c["type"] == "new_header"]
    assert len(header_changes) == 1
    
    change = header_changes[0]
    assert change["name"] == "X-Billing-Region"


def test_diff_ambiguous(v1_tool):
    """Test ambiguous contract: no mappings, multiple new fields."""
    changes = diff(v1_tool, CONTRACTS["ambiguous"])
    
    # Should detect ambiguous change (user_id removed, ref_a and ref_b added)
    ambiguous_changes = [c for c in changes if c["type"] == "ambiguous"]
    assert len(ambiguous_changes) == 1
    
    change = ambiguous_changes[0]
    assert change["removed"] == "user_id"
    assert "ref_a" in change["candidates"]
    assert "ref_b" in change["candidates"]


def test_diff_inferred_pairing_same_type():
    """Test that single removed + single added with same type are paired (tier 2)."""
    old_tool = {
        "body_schema": {
            "type": "object",
            "properties": {
                "old_field": {"type": "string"}
            },
            "required": ["old_field"],
        },
        "required_headers": [],
    }
    
    new_contract = {
        "body_schema": {
            "type": "object",
            "properties": {
                "new_field": {"type": "string"}
            },
            "required": ["new_field"],
        },
        "required_headers": [],
    }
    
    changes = diff(old_tool, new_contract)
    
    # Should infer rename
    rename_changes = [c for c in changes if c["type"] == "rename"]
    assert len(rename_changes) == 1
    assert rename_changes[0]["tier"] == 2  # Inferred
    assert rename_changes[0]["old_path"] == "old_field"
    assert rename_changes[0]["new_path"] == "new_field"


def test_diff_no_pairing_different_types():
    """Test that single removed + single added with different types are NOT paired."""
    old_tool = {
        "body_schema": {
            "type": "object",
            "properties": {
                "old_field": {"type": "string"}
            },
            "required": ["old_field"],
        },
        "required_headers": [],
    }
    
    new_contract = {
        "body_schema": {
            "type": "object",
            "properties": {
                "new_field": {"type": "integer"}
            },
            "required": ["new_field"],
        },
        "required_headers": [],
    }
    
    changes = diff(old_tool, new_contract)
    
    # Should NOT infer pairing due to type mismatch
    rename_changes = [c for c in changes if c["type"] == "rename"]
    assert len(rename_changes) == 0
    
    # Should be ambiguous
    ambiguous_changes = [c for c in changes if c["type"] == "ambiguous"]
    assert len(ambiguous_changes) == 1


def test_diff_removed_header():
    """Test detection of removed headers."""
    old_tool = {
        "body_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
        },
        "required_headers": ["X-Old-Header"],
    }
    
    new_contract = {
        "body_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
        },
        "required_headers": [],
    }
    
    changes = diff(old_tool, new_contract)
    
    removed_headers = [c for c in changes if c["type"] == "removed_header"]
    assert len(removed_headers) == 1
    assert removed_headers[0]["name"] == "X-Old-Header"


def test_diff_new_required_field():
    """Test detection of new required fields."""
    old_tool = {
        "body_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
            "required": ["user_id"],
        },
        "required_headers": [],
    }
    
    new_contract = {
        "body_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "extra_field": {"type": "string"}
            },
            "required": ["user_id", "extra_field"],
        },
        "required_headers": [],
    }
    
    changes = diff(old_tool, new_contract)
    
    new_field_changes = [c for c in changes if c["type"] == "new_required_field"]
    assert len(new_field_changes) == 1
    assert new_field_changes[0]["path"] == "extra_field"


def test_diff_deeply_nested_paths():
    """Test that deeply nested paths are handled correctly."""
    old_tool = {
        "body_schema": {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"}
                            }
                        }
                    }
                }
            },
        },
        "required_headers": [],
    }
    
    new_contract = {
        "body_schema": {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "integer"}
                            }
                        }
                    }
                }
            },
        },
        "required_headers": [],
    }
    
    changes = diff(old_tool, new_contract)
    
    type_changes = [c for c in changes if c["type"] == "type_change"]
    assert len(type_changes) == 1
    assert type_changes[0]["path"] == "level1.level2.field"
    assert type_changes[0]["from_type"] == "string"
    assert type_changes[0]["to_type"] == "integer"
