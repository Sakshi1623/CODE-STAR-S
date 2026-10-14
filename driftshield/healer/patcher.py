"""Schema adaptation and registry patching.

This module transforms tool call arguments to match new schemas and builds
updated registry snapshots after healing.
"""

from typing import Any, TypedDict, Literal


class AdaptResult(TypedDict):
    """Result of adapting arguments to a new schema."""
    payload: dict[str, Any] | None
    """Adapted request payload, or None on error"""
    
    provenance: dict[str, Any]
    """Provenance tags for each value (origin tracking)"""
    
    needed_headers: list[str]
    """Header names that need values from config/human"""
    
    error: str | None
    """Error message if adaptation failed, None on success"""


OriginTag = Literal["original_arg", "converted", "config", "human"]


def _get_nested(obj: dict[str, Any], path: str) -> Any:
    """Get value from nested dict using dotted path."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"Path {path} not found")
        current = current[part]
    return current


def _set_nested(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set value in nested dict using dotted path, creating intermediate dicts."""
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _is_lossless_conversion(value: Any, from_type: str, to_type: str) -> tuple[bool, Any]:
    """
    Check if type conversion is lossless and return converted value.
    
    Args:
        value: Original value
        from_type: Source type (string/integer)
        to_type: Target type (string/integer)
        
    Returns:
        Tuple of (is_lossless, converted_value)
    """
    # String to integer: only if string contains only digits
    if from_type == "string" and to_type == "integer":
        if isinstance(value, str) and value.isdigit():
            return (True, int(value))
        return (False, value)
    
    # Integer to string: always lossless
    if from_type == "integer" and to_type == "string":
        if isinstance(value, int):
            return (True, str(value))
        return (False, value)
    
    # Same type or unsupported conversion
    return (False, value)


def adapt(args: dict[str, Any], changes: list[dict[str, Any]]) -> AdaptResult:
    """
    Adapt agent's original arguments to match new schema.
    
    Algorithm:
    - Start with empty payload and provenance
    - For each change:
      - rename/nesting: Move value from old_path to new_path, tag as "converted"
      - type_change: Convert if lossless, error otherwise
      - new_required_field: Error (no source value)
      - ambiguous: Error (cannot determine mapping)
      - new_header: Add to needed_headers
    - Fields not mentioned in changes keep original values, tagged "original_arg"
    
    Args:
        args: Original arguments from LLM
        changes: List of Change dicts from differ
        
    Returns:
        AdaptResult with payload, provenance, needed_headers, and error
    """
    payload: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    needed_headers: list[str] = []
    
    # Track which paths have been moved/changed
    moved_paths: set[str] = set()
    renamed_paths: dict[str, str] = {}  # old_path -> new_path
    
    # Process changes
    for change in changes:
        change_type = change["type"]
        
        if change_type == "rename":
            old_path = change["old_path"]
            new_path = change["new_path"]
            
            # Get value from old path in original args
            try:
                value = _get_nested(args, old_path)
                _set_nested(payload, new_path, value)
                _set_nested(provenance, new_path, "converted")
                moved_paths.add(old_path)
                renamed_paths[old_path] = new_path
            except KeyError:
                # Field not in original args - this is an error
                return AdaptResult(
                    payload=None,
                    provenance={},
                    needed_headers=[],
                    error=f"Cannot rename: field {old_path} not in original arguments"
                )
        
        elif change_type == "nesting":
            old_path = change["old_path"]
            new_path = change["new_path"]
            
            # Get value from old path in original args
            try:
                value = _get_nested(args, old_path)
                _set_nested(payload, new_path, value)
                _set_nested(provenance, new_path, "converted")
                moved_paths.add(old_path)
                renamed_paths[old_path] = new_path
            except KeyError:
                # Field not in original args - this is an error
                return AdaptResult(
                    payload=None,
                    provenance={},
                    needed_headers=[],
                    error=f"Cannot nest: field {old_path} not in original arguments"
                )
        
        elif change_type == "type_change":
            path = change["path"]
            from_type = change["from_type"]
            to_type = change["to_type"]
            
            # Check if this path was renamed/nested
            source_path = path
            for old, new in renamed_paths.items():
                if new == path:
                    source_path = old
                    break
            
            # Get current value (from payload if already moved, otherwise from args)
            try:
                if path in [val for val in renamed_paths.values()]:
                    # Already in payload
                    value = _get_nested(payload, path)
                else:
                    # Still in original args
                    value = _get_nested(args, source_path)
                
                # Check if conversion is lossless
                is_lossless, converted = _is_lossless_conversion(value, from_type, to_type)
                
                if not is_lossless:
                    return AdaptResult(
                        payload=None,
                        provenance={},
                        needed_headers=[],
                        error=f"Cannot convert {path} from {from_type} to {to_type}: lossy conversion"
                    )
                
                # Apply conversion
                _set_nested(payload, path, converted)
                _set_nested(provenance, path, "converted")
                moved_paths.add(source_path)
                
            except KeyError:
                # Field not found
                return AdaptResult(
                    payload=None,
                    provenance={},
                    needed_headers=[],
                    error=f"Cannot convert {path}: field not found"
                )
        
        elif change_type == "new_required_field":
            # No source value - error
            path = change["path"]
            return AdaptResult(
                payload=None,
                provenance={},
                needed_headers=[],
                error=f"Cannot satisfy new required field {path}: no source value"
            )
        
        elif change_type == "ambiguous":
            # Cannot determine mapping - error
            removed = change["removed"]
            return AdaptResult(
                payload=None,
                provenance={},
                needed_headers=[],
                error=f"Ambiguous schema change: cannot map removed field {removed}"
            )
        
        elif change_type == "new_header":
            # Add to needed_headers list
            header_name = change["name"]
            needed_headers.append(header_name)
    
    # Copy unchanged fields from original args
    def copy_unchanged(src: dict[str, Any], dst: dict[str, Any], prov: dict[str, Any], prefix: str = "") -> None:
        """Recursively copy unchanged fields."""
        for key, value in src.items():
            current_path = f"{prefix}.{key}" if prefix else key
            
            # Skip if already moved
            if current_path in moved_paths:
                continue
            
            # If value is dict, recurse
            if isinstance(value, dict):
                if key not in dst:
                    dst[key] = {}
                if key not in prov:
                    prov[key] = {}
                copy_unchanged(value, dst[key], prov[key], current_path)
            else:
                # Copy leaf value
                dst[key] = value
                prov[key] = "original_arg"
    
    copy_unchanged(args, payload, provenance)
    
    return AdaptResult(
        payload=payload,
        provenance=provenance,
        needed_headers=needed_headers,
        error=None
    )


def build_new_snapshot(
    old_tool: dict[str, Any],
    changes: list[dict[str, Any]],
    live_contract: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Build new registry snapshot by applying changes to old tool.
    
    Algorithm:
    1. Start with copy of old tool
    2. Apply only the diffed changes
    3. Assert result matches live contract's body_schema and required_headers
    4. Return error if schemas don't match (incomplete diff)
    
    Args:
        old_tool: Current tool definition from registry
        changes: List of Change dicts from differ
        live_contract: Live contract from API
        
    Returns:
        Tuple of (new_snapshot, error). Snapshot is None on error.
    """
    import copy
    
    # Start with copy of old tool
    new_snapshot = copy.deepcopy(old_tool)
    
    # Update contract hash
    new_snapshot["contract_hash"] = live_contract["content_hash"]
    
    # Apply schema changes
    new_schema = copy.deepcopy(old_tool["body_schema"])
    
    # Track field movements for schema updates
    removed_fields: set[str] = set()
    added_fields: dict[str, dict[str, Any]] = {}
    
    for change in changes:
        change_type = change["type"]
        
        if change_type in ["rename", "nesting"]:
            old_path = change["old_path"]
            new_path = change["new_path"]
            
            # Mark old field as removed
            removed_fields.add(old_path.split(".")[0])
            
            # Track new field
            new_field = new_path.split(".")[0]
            if new_field not in added_fields:
                # Get schema from live contract for this field
                if new_field in live_contract["body_schema"]["properties"]:
                    added_fields[new_field] = live_contract["body_schema"]["properties"][new_field]
        
        elif change_type == "type_change":
            path = change["path"]
            to_type = change["to_type"]
            
            # Update type in schema
            parts = path.split(".")
            if len(parts) == 1:
                # Top-level field
                if parts[0] in new_schema["properties"]:
                    new_schema["properties"][parts[0]]["type"] = to_type
            else:
                # Nested field - update in nested object
                current = new_schema["properties"]
                for part in parts[:-1]:
                    if part in current:
                        current = current[part].get("properties", {})
                if parts[-1] in current:
                    current[parts[-1]]["type"] = to_type
        
        elif change_type == "new_required_field":
            path = change["path"]
            field = path.split(".")[0]
            
            # Add from live contract
            if field in live_contract["body_schema"]["properties"]:
                added_fields[field] = live_contract["body_schema"]["properties"][field]
    
    # Remove old fields
    for field in removed_fields:
        if field in new_schema["properties"]:
            del new_schema["properties"][field]
    
    # Add new fields
    for field, schema in added_fields.items():
        new_schema["properties"][field] = schema
    
    # Update required fields to match live contract
    new_schema["required"] = live_contract["body_schema"]["required"]
    
    # Update snapshot with new schema
    new_snapshot["body_schema"] = new_schema
    
    # Update headers from live contract
    new_snapshot["required_headers"] = live_contract["required_headers"]
    
    # Verify schema matches live contract
    if new_snapshot["body_schema"] != live_contract["body_schema"]:
        return (None, "Schema mismatch: diff incomplete or incorrect")
    
    if new_snapshot["required_headers"] != live_contract["required_headers"]:
        return (None, "Headers mismatch: diff incomplete")
    
    return (new_snapshot, None)
