"""Error classification for tool call failures."""

from typing import Any, Callable, TypedDict, Literal

from driftshield.healer.interceptor import CallResult
from driftshield.healer.registry import Tool


ErrorKind = Literal["drift", "invalid_data", "auth", "network", "unknown"]


class Classification(TypedDict):
    """Classification result for a failed tool call."""
    kind: ErrorKind
    evidence: dict[str, Any]
    live_contract: dict[str, Any] | None


def classify(
    result: CallResult,
    registry_tool: Tool,
    fetch_live_contract: Callable[[], dict[str, Any] | None],
) -> Classification:
    """
    Classify a tool call failure.
    
    Classification rules:
    1. network_error set OR status >= 500 -> network
    2. status 401 or 403 -> auth
    3. status 400 or 422 -> fetch live contract:
       - If content_hash differs AND (body_schema OR required_headers differ) -> drift
       - If registry already matches live contract -> invalid_data
    4. Anything else -> unknown
    
    Args:
        result: CallResult from interceptor
        registry_tool: Tool definition from registry
        fetch_live_contract: Function to fetch current contract from API
        
    Returns:
        Classification with kind, evidence, and optional live_contract
    """
    evidence: dict[str, Any] = {}
    
    # Rule 1: Network errors
    if result.get("network_error") is not None:
        return Classification(
            kind="network",
            evidence={"network_error": result["network_error"]},
            live_contract=None,
        )
    
    status = result["status"]
    
    if status is not None and status >= 500:
        return Classification(
            kind="network",
            evidence={"status": status, "body": result["body"]},
            live_contract=None,
        )
    
    # Rule 2: Auth errors
    if status in [401, 403]:
        return Classification(
            kind="auth",
            evidence={"status": status, "body": result["body"]},
            live_contract=None,
        )
    
    # Rule 3: Potential drift or invalid data
    if status in [400, 422]:
        live_contract = fetch_live_contract()
        
        if live_contract is None:
            return Classification(
                kind="unknown",
                evidence={"status": status, "reason": "could not fetch live contract"},
                live_contract=None,
            )
        
        registry_hash = registry_tool["contract_hash"]
        live_hash = live_contract.get("content_hash")
        
        evidence["registry_hash"] = registry_hash
        evidence["live_hash"] = live_hash
        evidence["status"] = status
        
        # Hash differs - check if schema or headers actually differ
        if registry_hash != live_hash:
            schema_differs = (
                registry_tool["body_schema"] != live_contract.get("body_schema")
            )
            headers_differ = (
                registry_tool["required_headers"] != live_contract.get("required_headers", [])
            )
            
            evidence["schema_differs"] = schema_differs
            evidence["headers_differ"] = headers_differ
            
            if schema_differs or headers_differ:
                # True drift: registry is outdated
                return Classification(
                    kind="drift",
                    evidence=evidence,
                    live_contract=live_contract,
                )
        
        # Registry matches live contract, so the data itself is invalid
        return Classification(
            kind="invalid_data",
            evidence=evidence,
            live_contract=live_contract,
        )
    
    # Rule 4: Unknown
    return Classification(
        kind="unknown",
        evidence={"status": status, "body": result["body"]},
        live_contract=None,
    )
