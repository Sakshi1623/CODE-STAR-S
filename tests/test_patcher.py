"""Tests for patcher and guard modules."""

import pytest
from driftshield.healer.patcher import adapt, build_new_snapshot
from driftshield.healer.guard import resolve_headers, check_provenance
from driftshield.healer.differ import diff
from driftshield.healer.registry import create_default_registry
from driftshield.mock_api.contracts import CONTRACTS


# ===== adapt() tests =====

def test_adapt_v1_to_v2_full():
    """
    Test adapting v1 args (user_id) to v2_full (target.id with type change).
    
    Expected:
    - payload: {"target": {"id": 123}}
    - id tagged as "converted" (both nesting and type conversion)
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    v2_contract = CONTRACTS["v2_full"]
    
    changes = diff(v1_tool, v2_contract)
    
    # Original args from LLM
    args = {"user_id": "123"}
    
    result = adapt(args, changes)
    
    # Should succeed
    assert result["error"] is None, f"Unexpected error: {result['error']}"
    assert result["payload"] == {"target": {"id": 123}}
    
    # Check provenance - id should be tagged "converted"
    assert result["provenance"]["target"]["id"] == "converted"
    
    # Check needed_headers includes X-Tenant-Token
    assert "X-Tenant-Token" in result["needed_headers"]


def test_adapt_non_numeric_user_id_fails():
    """
    Test that non-numeric user_id cannot convert to integer (lossy).
    
    Should return error for lossy conversion.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    v2_contract = CONTRACTS["v2_full"]
    
    changes = diff(v1_tool, v2_contract)
    
    # Non-numeric user_id
    args = {"user_id": "abc"}
    
    result = adapt(args, changes)
    
    # Should fail with error
    assert result["error"] is not None
    assert "lossy" in result["error"].lower() or "convert" in result["error"].lower()
    assert result["payload"] is None


def test_adapt_ambiguous_fails():
    """
    Test that ambiguous schema changes return error.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    ambiguous_contract = CONTRACTS["ambiguous"]
    
    changes = diff(v1_tool, ambiguous_contract)
    
    args = {"user_id": "123"}
    
    result = adapt(args, changes)
    
    # Should fail with error about ambiguous change
    assert result["error"] is not None
    assert "ambiguous" in result["error"].lower()
    assert result["payload"] is None


def test_adapt_rename_preserves_value():
    """
    Test simple rename (user_id -> id) preserves value and tags as converted.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    rename_contract = CONTRACTS["rename_id"]
    
    changes = diff(v1_tool, rename_contract)
    
    args = {"user_id": "456"}
    
    result = adapt(args, changes)
    
    # Should succeed
    assert result["error"] is None
    assert result["payload"] == {"id": "456"}
    assert result["provenance"]["id"] == "converted"


def test_adapt_nesting_creates_structure():
    """
    Test nesting (user_id -> target.id) creates nested structure.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    nest_contract = CONTRACTS["nest_target"]
    
    changes = diff(v1_tool, nest_contract)
    
    args = {"user_id": "789"}
    
    result = adapt(args, changes)
    
    # Should succeed
    assert result["error"] is None
    assert result["payload"] == {"target": {"id": "789"}}
    assert result["provenance"]["target"]["id"] == "converted"


def test_adapt_lossless_int_to_string():
    """
    Test integer to string conversion (always lossless).
    """
    # Create a custom scenario: integer user_id in args, but schema expects string
    # This requires manually crafting changes
    changes = [
        {
            "type": "type_change",
            "path": "user_id",
            "from_type": "integer",
            "to_type": "string",
            "tier": 1,
        }
    ]
    
    args = {"user_id": 999}
    
    result = adapt(args, changes)
    
    # Should succeed with string conversion
    assert result["error"] is None
    assert result["payload"] == {"user_id": "999"}
    assert result["provenance"]["user_id"] == "converted"


def test_adapt_multiple_changes():
    """
    Test combo: rename + nesting + type change + new header.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    combo_contract = CONTRACTS["combo"]
    
    changes = diff(v1_tool, combo_contract)
    
    args = {"user_id": "555"}
    
    result = adapt(args, changes)
    
    # Should succeed
    assert result["error"] is None
    assert result["payload"] == {"target": {"id": 555}}
    assert result["provenance"]["target"]["id"] == "converted"
    assert "X-Tenant-Token" in result["needed_headers"]


# ===== resolve_headers() tests =====

def test_resolve_headers_from_config():
    """
    Test resolving X-Tenant-Token from config with origin "config".
    """
    headers, provenance, missing = resolve_headers(["X-Tenant-Token"])
    
    # Should find value in config
    assert "X-Tenant-Token" in headers
    assert headers["X-Tenant-Token"] is not None
    assert provenance["X-Tenant-Token"] == "config"
    assert len(missing) == 0


def test_resolve_headers_missing():
    """
    Test that X-Billing-Region is missing (not in config).
    """
    headers, provenance, missing = resolve_headers(["X-Billing-Region"])
    
    # Should be missing
    assert "X-Billing-Region" not in headers
    assert "X-Billing-Region" in missing
    assert len(headers) == 0


def test_resolve_headers_custom_getter():
    """
    Test using custom header value getter.
    """
    def custom_getter(header_name: str) -> tuple[str, str] | None:
        if header_name == "X-Custom-Header":
            return ("custom-value", "human")
        return None
    
    headers, provenance, missing = resolve_headers(
        ["X-Custom-Header", "X-Missing-Header"],
        get_value=custom_getter
    )
    
    assert headers["X-Custom-Header"] == "custom-value"
    assert provenance["X-Custom-Header"] == "human"
    assert "X-Missing-Header" in missing


# ===== check_provenance() tests =====

def test_check_provenance_rejects_untagged_value():
    """
    Test that check_provenance rejects payload with untagged value.
    
    Simulates an invented value with no provenance tag.
    """
    payload = {
        "target": {
            "id": 123,
            "extra_field": "invented"  # This has no tag
        }
    }
    
    provenance = {
        "target": {
            "id": "converted"
            # extra_field is missing - invented value!
        }
    }
    
    # Should reject
    assert check_provenance(payload, provenance) is False


def test_check_provenance_accepts_fully_tagged():
    """
    Test that check_provenance accepts payload with all values tagged.
    """
    payload = {
        "target": {
            "id": 123
        }
    }
    
    provenance = {
        "target": {
            "id": "converted"
        }
    }
    
    # Should accept
    assert check_provenance(payload, provenance) is True


def test_check_provenance_with_nested_structure():
    """
    Test provenance checking with deeper nesting.
    """
    payload = {
        "level1": {
            "level2": {
                "field": "value"
            }
        }
    }
    
    provenance = {
        "level1": {
            "level2": {
                "field": "original_arg"
            }
        }
    }
    
    # Should accept
    assert check_provenance(payload, provenance) is True


def test_check_provenance_rejects_partial_tagging():
    """
    Test that partial tagging is rejected (some fields tagged, some not).
    """
    payload = {
        "field_a": "value_a",
        "field_b": "value_b"
    }
    
    provenance = {
        "field_a": "original_arg"
        # field_b is missing!
    }
    
    # Should reject
    assert check_provenance(payload, provenance) is False


def test_check_provenance_accepts_multiple_origins():
    """
    Test that different valid origin tags all work.
    """
    payload = {
        "original": "from_llm",
        "converted": 123,
        "from_config": "config_value",
        "from_human": "human_value"
    }
    
    provenance = {
        "original": "original_arg",
        "converted": "converted",
        "from_config": "config",
        "from_human": "human"
    }
    
    # Should accept all valid tags
    assert check_provenance(payload, provenance) is True


def test_check_provenance_rejects_invalid_origin():
    """
    Test that invalid origin tag is rejected.
    """
    payload = {
        "field": "value"
    }
    
    provenance = {
        "field": "invented"  # Invalid tag!
    }
    
    # Should reject
    assert check_provenance(payload, provenance) is False


def test_check_provenance_handles_malformed_provenance_safely():
    """
    Test that check_provenance safely returns False for malformed provenance.
    
    Should not raise exceptions for:
    - Provenance as string when dict expected
    - Provenance as None
    - Provenance with wrong structure
    - Missing provenance dict
    """
    payload = {"field": "value"}
    
    # Provenance as string instead of dict
    assert check_provenance(payload, "converted") is False
    
    # Provenance as None
    assert check_provenance(payload, None) is False  # type: ignore
    
    # Provenance as list
    assert check_provenance(payload, []) is False  # type: ignore
    
    # Empty provenance when payload has values
    assert check_provenance(payload, {}) is False
    
    # Provenance with wrong structure (dict instead of string for leaf)
    payload_nested = {"target": {"id": 123}}
    provenance_wrong = {"target": "converted"}  # Should be dict
    assert check_provenance(payload_nested, provenance_wrong) is False


def test_check_provenance_rejects_extra_provenance_keys():
    """
    Test that extra provenance keys not in payload are rejected.
    
    This prevents invented provenance entries that don't correspond to actual values.
    """
    payload = {
        "field_a": "value_a"
    }
    
    provenance = {
        "field_a": "original_arg",
        "field_b": "converted"  # Extra key not in payload!
    }
    
    # Should reject - provenance has extra key
    assert check_provenance(payload, provenance) is False


def test_check_provenance_rejects_nested_structure_mismatch():
    """
    Test that structural mismatches between payload and provenance are rejected.
    """
    # Payload has nested dict, provenance has string
    payload = {"target": {"id": 123}}
    provenance = {"target": "converted"}  # Should be dict with "id" key
    assert check_provenance(payload, provenance) is False
    
    # Payload has string, provenance has dict
    payload2 = {"field": "value"}
    provenance2 = {"field": {"nested": "converted"}}  # Should be string
    assert check_provenance(payload2, provenance2) is False


def test_check_provenance_non_dict_payload():
    """
    Test that non-dict payloads are handled safely.
    """
    # Top-level non-dict payload
    assert check_provenance("string", "converted") is False  # type: ignore
    assert check_provenance(123, "converted") is False  # type: ignore
    assert check_provenance([], []) is False  # type: ignore


def test_resolve_headers_records_config_origin():
    """
    Test that resolve_headers records origin as 'config' for configured headers.
    
    Verifies the origin tag is exactly 'config' from config.get_header_value.
    """
    headers, provenance, missing = resolve_headers(["X-Tenant-Token"])
    
    # Should find value in config
    assert "X-Tenant-Token" in headers
    assert headers["X-Tenant-Token"] is not None
    
    # Origin must be exactly "config"
    assert "X-Tenant-Token" in provenance
    assert provenance["X-Tenant-Token"] == "config"
    
    # No missing headers
    assert len(missing) == 0


def test_resolve_headers_no_fallback_values():
    """
    Test that resolve_headers does NOT create fallback, placeholder, or guessed values.
    
    Missing configuration must remain a missing header.
    """
    headers, provenance, missing = resolve_headers(["X-Billing-Region", "X-Unknown-Header"])
    
    # Should NOT have any values for unconfigured headers
    assert "X-Billing-Region" not in headers
    assert "X-Unknown-Header" not in headers
    
    # Should NOT have provenance entries for missing headers
    assert "X-Billing-Region" not in provenance
    assert "X-Unknown-Header" not in provenance
    
    # Both should be in missing list
    assert "X-Billing-Region" in missing
    assert "X-Unknown-Header" in missing
    
    # Verify headers dict has no extra keys
    assert len(headers) == 0
    assert len(provenance) == 0


# ===== build_new_snapshot() tests =====

def test_build_new_snapshot_matches_contract():
    """
    Test that build_new_snapshot produces snapshot matching live contract.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    v2_contract = CONTRACTS["v2_full"]
    
    changes = diff(v1_tool, v2_contract)
    
    snapshot, error = build_new_snapshot(v1_tool, changes, v2_contract)
    
    # Should succeed
    assert error is None, f"Unexpected error: {error}"
    assert snapshot is not None
    
    # Check schema matches
    assert snapshot["body_schema"] == v2_contract["body_schema"]
    assert snapshot["required_headers"] == v2_contract["required_headers"]
    assert snapshot["contract_hash"] == v2_contract["content_hash"]


def test_build_new_snapshot_unchanged_fields_preserved():
    """
    Test that unchanged fields (name, description, operation) are preserved.
    
    This is the minimal patch test.
    """
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    rename_contract = CONTRACTS["rename_id"]
    
    changes = diff(v1_tool, rename_contract)
    
    snapshot, error = build_new_snapshot(v1_tool, changes, rename_contract)
    
    # Should succeed
    assert error is None
    assert snapshot is not None
    
    # Unchanged fields preserved
    assert snapshot["name"] == v1_tool["name"]
    assert snapshot["description"] == v1_tool["description"]
    assert snapshot["operation"] == v1_tool["operation"]
    
    # Schema updated
    assert snapshot["body_schema"] == rename_contract["body_schema"]


def test_build_new_snapshot_response_schema_copied_and_verified():
    """Test: When live contract has response_schema, new snapshot has matching response_schema."""
    import copy
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    v2_contract = copy.deepcopy(CONTRACTS["v2_full"])
    v2_contract["response_schema"] = {
        "type": "object",
        "properties": {"result": {"type": "string"}},
        "required": ["result"],
    }

    changes = diff(v1_tool, v2_contract)
    snapshot, error = build_new_snapshot(v1_tool, changes, v2_contract)

    assert error is None
    assert snapshot is not None
    assert snapshot["response_schema"] == v2_contract["response_schema"]


def test_build_new_snapshot_preserves_old_response_schema_when_live_omits():
    """Test: When live contract omits response_schema, old tool's response_schema is preserved."""
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    rename_contract = CONTRACTS["rename_id"]
    assert "response_schema" not in rename_contract
    assert "response_schema" in v1_tool

    changes = diff(v1_tool, rename_contract)
    snapshot, error = build_new_snapshot(v1_tool, changes, rename_contract)

    assert error is None
    assert snapshot is not None
    assert snapshot["response_schema"] == v1_tool["response_schema"]


def test_build_new_snapshot_absent_response_schema_in_both():
    """Test: When neither old tool nor live contract has response_schema, snapshot has none."""
    import copy
    registry = create_default_registry()
    v1_tool = copy.deepcopy(registry.get("lookup_user"))
    v1_tool.pop("response_schema", None)
    rename_contract = CONTRACTS["rename_id"]

    changes = diff(v1_tool, rename_contract)
    snapshot, error = build_new_snapshot(v1_tool, changes, rename_contract)

    assert error is None
    assert snapshot is not None
    assert "response_schema" not in snapshot


def test_build_new_snapshot_fails_verification_on_response_schema_mismatch():
    """Test: Snapshot verification fails if response_schema does not match live contract."""
    import copy
    from unittest.mock import patch
    registry = create_default_registry()
    v1_tool = registry.get("lookup_user")
    live_contract = copy.deepcopy(CONTRACTS["v2_full"])
    live_contract["response_schema"] = {
        "type": "object",
        "properties": {"data": {"type": "string"}},
    }

    changes = diff(v1_tool, live_contract)

    # Intercept copy.deepcopy to simulate a corrupted/mismatched response_schema in snapshot
    original_deepcopy = copy.deepcopy

    def fake_deepcopy(obj):
        res = original_deepcopy(obj)
        if isinstance(obj, dict) and "data" in obj.get("properties", {}):
            return {"type": "object", "properties": {"mismatched": {"type": "integer"}}}
        return res

    with patch("copy.deepcopy", side_effect=fake_deepcopy):
        snapshot, error = build_new_snapshot(v1_tool, changes, live_contract)

    assert snapshot is None
    assert error == "Response schema mismatch: diff incomplete"
