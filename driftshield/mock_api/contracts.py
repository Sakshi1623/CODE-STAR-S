"""API contract definitions with versioning and hashing."""

import json
import hashlib
from typing import Any, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired  # type: ignore


class Mapping(TypedDict):
    """Field mapping from old to new schema."""
    from_: str  # Use from_ to avoid Python keyword
    to: str


class Contract(TypedDict):
    """API contract with schema and metadata."""
    schema_version: str
    content_hash: str
    operation: str
    required_headers: list[str]
    body_schema: dict[str, Any]
    mappings: NotRequired[list[dict[str, str]]]  # Optional mappings with from/to keys


def compute_hash(contract_without_hash: dict[str, Any]) -> str:
    """
    Compute SHA256 hash of canonical JSON representation.
    
    Args:
        contract_without_hash: Contract dict WITHOUT content_hash field
        
    Returns:
        Hex string of SHA256 hash
    """
    canonical = json.dumps(contract_without_hash, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _build_contract(
    schema_version: str,
    operation: str,
    body_schema: dict[str, Any],
    required_headers: list[str] | None = None,
    mappings: list[dict[str, str]] | None = None,
) -> Contract:
    """
    Build a contract with computed content_hash.
    
    Args:
        schema_version: Version identifier
        operation: Operation name
        body_schema: JSON Schema for request body
        required_headers: List of required header names
        mappings: Optional list of field mappings
        
    Returns:
        Complete contract with content_hash
    """
    base: dict[str, Any] = {
        "schema_version": schema_version,
        "operation": operation,
        "required_headers": required_headers or [],
        "body_schema": body_schema,
    }
    if mappings:
        base["mappings"] = mappings
    
    content_hash = compute_hash(base)
    base["content_hash"] = content_hash
    return base  # type: ignore


# Named contracts for lookup_user operation
CONTRACTS: dict[str, Contract] = {
    "v1": _build_contract(
        schema_version="v1",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
            "required": ["user_id"],
            "additionalProperties": False,
        },
    ),
    
    "v2_full": _build_contract(
        schema_version="v2_full",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"}
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        required_headers=["X-Tenant-Token"],
        mappings=[{"from": "user_id", "to": "target.id"}],
    ),
    
    "rename_id": _build_contract(
        schema_version="rename_id",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"}
            },
            "required": ["id"],
            "additionalProperties": False,
        },
        mappings=[{"from": "user_id", "to": "id"}],
    ),
    
    "type_int": _build_contract(
        schema_version="type_int",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"}
            },
            "required": ["user_id"],
            "additionalProperties": False,
        },
    ),
    
    "nest_target": _build_contract(
        schema_version="nest_target",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"}
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        mappings=[{"from": "user_id", "to": "target.id"}],
    ),
    
    "header_tenant": _build_contract(
        schema_version="header_tenant",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
            "required": ["user_id"],
            "additionalProperties": False,
        },
        required_headers=["X-Tenant-Token"],
    ),
    
    "combo": _build_contract(
        schema_version="combo",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"}
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        required_headers=["X-Tenant-Token"],
        mappings=[{"from": "user_id", "to": "target.id"}],
    ),
    
    "header_billing": _build_contract(
        schema_version="header_billing",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"}
            },
            "required": ["user_id"],
            "additionalProperties": False,
        },
        required_headers=["X-Billing-Region"],
    ),
    
    "ambiguous": _build_contract(
        schema_version="ambiguous",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "ref_a": {"type": "string"},
                "ref_b": {"type": "string"}
            },
            "required": ["ref_a", "ref_b"],
            "additionalProperties": False,
        },
    ),
    
    "rename_uid": _build_contract(
        schema_version="rename_uid",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "uid": {"type": "string"}
            },
            "required": ["uid"],
            "additionalProperties": False,
        },
        mappings=[{"from": "user_id", "to": "uid"}],
    ),
    
    "nest_deep": _build_contract(
        schema_version="nest_deep",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"}
                            },
                            "required": ["id"],
                            "additionalProperties": False,
                        }
                    },
                    "required": ["user"],
                    "additionalProperties": False,
                }
            },
            "required": ["data"],
            "additionalProperties": False,
        },
        mappings=[{"from": "user_id", "to": "data.user.id"}],
    ),
    
    "header_rename": _build_contract(
        schema_version="header_rename",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"}
            },
            "required": ["id"],
            "additionalProperties": False,
        },
        required_headers=["X-Tenant-Token"],
        mappings=[{"from": "user_id", "to": "id"}],
    ),
    
    "combo_billing": _build_contract(
        schema_version="combo_billing",
        operation="lookup_user",
        body_schema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"}
                    },
                    "required": ["id"],
                    "additionalProperties": False,
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        required_headers=["X-Billing-Region"],
        mappings=[{"from": "user_id", "to": "target.id"}],
    ),
}


# Module-level active contract state
_active_contract: Contract = CONTRACTS["v1"]


def get_active() -> Contract:
    """Get the currently active contract."""
    return _active_contract


def set_active(name: str) -> None:
    """
    Set the active contract by name.
    
    Args:
        name: Contract name from CONTRACTS dict
        
    Raises:
        KeyError: If contract name not found
    """
    global _active_contract
    _active_contract = CONTRACTS[name]
