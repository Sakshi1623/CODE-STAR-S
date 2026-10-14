"""Schema difference detection and change analysis."""

from typing import Any, Literal


# Change types
ChangeType = Literal[
    "rename",
    "nesting",
    "type_change",
    "new_required_field",
    "new_header",
    "removed_header",
    "ambiguous",
]


class Change(dict):
    """
    Represents a single schema change.
    
    Fields vary by type:
    - rename: path, old_path, new_path, tier
    - nesting: path, old_path, new_path, tier
    - type_change: path, from_type, to_type, tier
    - new_required_field: path
    - new_header: name
    - removed_header: name
    - ambiguous: removed, candidates
    """
    pass


def _flatten_schema(schema: dict[str, Any], prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], str]:
    """
    Flatten JSON Schema to leaf paths with types.
    
    Args:
        schema: JSON Schema object
        prefix: Current path prefix
        
    Returns:
        Dict mapping path tuples to type strings
    """
    result: dict[tuple[str, ...], str] = {}
    
    if "properties" not in schema:
        return result
    
    for prop_name, prop_schema in schema["properties"].items():
        current_path = prefix + (prop_name,)
        
        # If property has nested properties, recurse
        if isinstance(prop_schema, dict) and "properties" in prop_schema:
            result.update(_flatten_schema(prop_schema, current_path))
        else:
            # Leaf node - record the type
            prop_type = prop_schema.get("type", "any") if isinstance(prop_schema, dict) else "any"
            result[current_path] = prop_type
    
    return result


def _path_to_dotted(path: tuple[str, ...]) -> str:
    """Convert path tuple to dotted string."""
    return ".".join(path)


def _dotted_to_path(dotted: str) -> tuple[str, ...]:
    """Convert dotted string to path tuple."""
    return tuple(dotted.split("."))


def _is_rename(old_path: tuple[str, ...], new_path: tuple[str, ...]) -> bool:
    """Check if change is a rename (only last segment changed)."""
    if len(old_path) != len(new_path):
        return False
    if len(old_path) == 0:
        return False
    # Same parent path, different last segment
    return old_path[:-1] == new_path[:-1] and old_path[-1] != new_path[-1]


def _is_nesting(old_path: tuple[str, ...], new_path: tuple[str, ...]) -> bool:
    """Check if change is a nesting (parent path changed)."""
    if len(old_path) == len(new_path):
        return old_path[:-1] != new_path[:-1]
    return True  # Different lengths means nesting changed


def diff(old_tool: dict[str, Any], live_contract: dict[str, Any]) -> list[Change]:
    """
    Compute differences between registry tool and live contract.
    
    Algorithm:
    1. Flatten body_schema to leaf paths
    2. Identify removed, added, and type-changed paths
    3. Pair removed/added using mappings or inference
    4. Classify changes as rename, nesting, type_change, etc.
    5. Detect header changes
    
    Args:
        old_tool: Tool definition from registry
        live_contract: Current contract from API
        
    Returns:
        List of Change dicts with type and tier fields
    """
    changes: list[Change] = []
    
    # Flatten schemas
    old_paths = _flatten_schema(old_tool["body_schema"])
    new_paths = _flatten_schema(live_contract["body_schema"])
    
    # Identify removed and added paths
    removed_paths = set(old_paths.keys()) - set(new_paths.keys())
    added_paths = set(new_paths.keys()) - set(old_paths.keys())
    common_paths = set(old_paths.keys()) & set(new_paths.keys())
    
    # Type changes in common paths
    for path in common_paths:
        if old_paths[path] != new_paths[path]:
            changes.append(Change({
                "type": "type_change",
                "path": _path_to_dotted(path),
                "from_type": old_paths[path],
                "to_type": new_paths[path],
                "tier": 1,
            }))
    
    # Build mapping index from live contract
    mappings = live_contract.get("mappings", [])
    mapping_index: dict[str, str] = {}  # from -> to
    for m in mappings:
        from_field = m.get("from", m.get("from_", ""))
        to_field = m.get("to", "")
        if from_field and to_field:
            mapping_index[from_field] = to_field
    
    # Track which paths have been paired
    paired_removed = set()
    paired_added = set()
    
    # Step 3a: Pair using declared mappings (tier 1)
    for removed_path in list(removed_paths):
        removed_dotted = _path_to_dotted(removed_path)
        if removed_dotted in mapping_index:
            to_dotted = mapping_index[removed_dotted]
            to_path = _dotted_to_path(to_dotted)
            
            if to_path in added_paths:
                # Found the mapping target
                paired_removed.add(removed_path)
                paired_added.add(to_path)
                
                old_type = old_paths[removed_path]
                new_type = new_paths[to_path]
                
                # Determine change type
                is_rename_change = _is_rename(removed_path, to_path)
                is_nesting_change = _is_nesting(removed_path, to_path)
                
                if is_rename_change and not is_nesting_change:
                    changes.append(Change({
                        "type": "rename",
                        "old_path": removed_dotted,
                        "new_path": to_dotted,
                        "tier": 1,
                    }))
                elif is_nesting_change and not is_rename_change:
                    changes.append(Change({
                        "type": "nesting",
                        "old_path": removed_dotted,
                        "new_path": to_dotted,
                        "tier": 1,
                    }))
                else:
                    # Both rename and nesting
                    changes.append(Change({
                        "type": "nesting",  # Nesting takes precedence
                        "old_path": removed_dotted,
                        "new_path": to_dotted,
                        "tier": 1,
                    }))
                
                # Also check for type change
                if old_type != new_type:
                    changes.append(Change({
                        "type": "type_change",
                        "path": to_dotted,
                        "from_type": old_type,
                        "to_type": new_type,
                        "tier": 1,
                    }))
    
    # Step 3b: Infer pairing if exactly one removed and one added with same type (tier 2)
    unpaired_removed = removed_paths - paired_removed
    unpaired_added = added_paths - paired_added
    
    if len(unpaired_removed) == 1 and len(unpaired_added) == 1:
        removed_path = list(unpaired_removed)[0]
        added_path = list(unpaired_added)[0]
        
        old_type = old_paths[removed_path]
        new_type = new_paths[added_path]
        
        if old_type == new_type:
            # Inferred pairing
            paired_removed.add(removed_path)
            paired_added.add(added_path)
            
            removed_dotted = _path_to_dotted(removed_path)
            added_dotted = _path_to_dotted(added_path)
            
            is_rename_change = _is_rename(removed_path, added_path)
            is_nesting_change = _is_nesting(removed_path, added_path)
            
            if is_rename_change and not is_nesting_change:
                changes.append(Change({
                    "type": "rename",
                    "old_path": removed_dotted,
                    "new_path": added_dotted,
                    "tier": 2,
                }))
            elif is_nesting_change:
                changes.append(Change({
                    "type": "nesting",
                    "old_path": removed_dotted,
                    "new_path": added_dotted,
                    "tier": 2,
                }))
    
    # Step 3c: Ambiguous removals (multiple candidates or type mismatch)
    unpaired_removed = removed_paths - paired_removed
    unpaired_added = added_paths - paired_added
    
    if unpaired_removed and unpaired_added:
        for removed_path in unpaired_removed:
            removed_dotted = _path_to_dotted(removed_path)
            candidates = [_path_to_dotted(p) for p in unpaired_added]
            changes.append(Change({
                "type": "ambiguous",
                "removed": removed_dotted,
                "candidates": candidates,
            }))
    
    # Step 5: New required fields (added paths that weren't paired)
    final_unpaired_added = unpaired_added - paired_added
    for added_path in final_unpaired_added:
        # Check if it's in required fields
        required_fields = live_contract["body_schema"].get("required", [])
        if added_path[0] in required_fields or len(added_path) > 1:
            # Either top-level required or nested (assume required)
            changes.append(Change({
                "type": "new_required_field",
                "path": _path_to_dotted(added_path),
            }))
    
    # Step 6: Header changes
    old_headers = set(old_tool.get("required_headers", []))
    new_headers = set(live_contract.get("required_headers", []))
    
    for header in new_headers - old_headers:
        changes.append(Change({
            "type": "new_header",
            "name": header,
        }))
    
    for header in old_headers - new_headers:
        changes.append(Change({
            "type": "removed_header",
            "name": header,
        }))
    
    return changes
