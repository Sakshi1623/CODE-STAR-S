"""Value provenance and header resolution.

This module ensures all values have valid provenance and resolves required
headers from configuration, never from untrusted sources.
"""

from typing import Any, Callable
from driftshield  import config


def resolve_headers(
    needed_headers: list[str],
    get_value: Callable[[str], tuple[str, str] | None] | None = None
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """
    Resolve header values from configuration.
    
    Uses config.get_header_value by default, or custom getter if provided.
    Headers with no value go in missing list.
    NEVER takes values from LLM or error messages.
    
    Args:
        needed_headers: List of header names to resolve
        get_value: Optional custom getter function (header_name -> (value, origin) or None)
                   Defaults to config.get_header_value
        
    Returns:
        Tuple of (headers dict, provenance dict, missing list)
        - headers: {header_name: value} for found headers
        - provenance: {header_name: origin} for found headers
        - missing: [header_name] for headers with no value
    """
    if get_value is None:
        get_value = config.get_header_value
    
    headers: dict[str, str] = {}
    provenance: dict[str, str] = {}
    missing: list[str] = []
    
    for header_name in needed_headers:
        result = get_value(header_name)
        
        if result is None:
            # No value found - add to missing
            missing.append(header_name)
        else:
            # Value found - add to headers and provenance
            value, origin = result
            headers[header_name] = value
            provenance[header_name] = origin
    
    return (headers, provenance, missing)


def check_provenance(payload: dict[str, Any], provenance: dict[str, Any]) -> bool:
    """
    Check that every leaf value in payload has a valid provenance tag.
    
    Valid tags: original_arg, converted, config, human
    Any untagged value returns False (indicates invented value).
    Safely handles malformed provenance structures by returning False.
    Rejects extra provenance paths not associated with payload values.
    
    Args:
        payload: Request payload with nested structure
        provenance: Provenance dict with same structure as payload
        
    Returns:
        True if all values are tagged correctly, False otherwise
    """
    valid_tags = {"original_arg", "converted", "config", "human"}
    
    # Handle malformed inputs safely
    if not isinstance(payload, dict) or not isinstance(provenance, dict):
        return False
    
    def check_recursive(data: Any, prov: Any, path: str = "") -> bool:
        """
        Recursively check provenance for nested structures.
        Returns False on any malformed structure instead of raising exceptions.
        """
        try:
            if isinstance(data, dict):
                # Provenance must also be a dict for nested structures
                if not isinstance(prov, dict):
                    return False
                
                # Check each key in payload
                for key, value in data.items():
                    # Key must exist in provenance
                    if key not in prov:
                        return False
                    
                    # Recurse if value is dict, otherwise check tag
                    if isinstance(value, dict):
                        # For nested dicts, provenance must also be dict
                        if not isinstance(prov[key], dict):
                            return False
                        if not check_recursive(value, prov[key], f"{path}.{key}" if path else key):
                            return False
                    else:
                        # Leaf value - check provenance tag
                        tag = prov[key]
                        if not isinstance(tag, str) or tag not in valid_tags:
                            return False
                
                # Check for extra provenance keys not in payload (invented provenance)
                for key in prov.keys():
                    if key not in data:
                        return False
                
                return True
            else:
                # Non-dict payload value - provenance must be a valid tag string
                return isinstance(prov, str) and prov in valid_tags
        except (TypeError, AttributeError, KeyError):
            # Any exception indicates malformed structure
            return False
    
    return check_recursive(payload, provenance)
