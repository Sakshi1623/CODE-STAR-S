"""Retry logic with budget tracking and healing execution."""

import time
from typing import Any, Literal

import httpx
import jsonschema

from driftshield.healer import log
from driftshield.healer.interceptor import call_tool
from driftshield.healer.classifier import classify
from driftshield.healer.differ import diff
from driftshield.healer.patcher import adapt, build_new_snapshot
from driftshield.healer.guard import resolve_headers, check_provenance
from driftshield.healer.registry import ToolRegistry


HealStatus = Literal["ok", "healed", "safe_stop", "failed"]


class Budget:
    """
    Shared budget for API and model calls.
    
    Enforces hard limits to prevent unbounded retries.
    """
    
    def __init__(self, max_api_attempts: int = 5, max_model_calls: int = 8):
        """
        Initialize budget.
        
        Args:
            max_api_attempts: Maximum API attempts allowed
            max_model_calls: Maximum model calls allowed
        """
        self.max_api_attempts = max_api_attempts
        self.max_model_calls = max_model_calls
        self.api_attempts = 0
        self.model_calls = 0
    
    def consume_api(self) -> None:
        """Consume one API attempt."""
        self.api_attempts += 1
    
    def consume_model(self) -> None:
        """Consume one model call."""
        self.model_calls += 1
    
    def exhausted(self) -> bool:
        """Check if budget is exhausted."""
        return (
            self.api_attempts >= self.max_api_attempts or
            self.model_calls >= self.max_model_calls
        )


class HealResult(dict):
    """
    Result of healing execution.
    
    Fields:
    - status: ok, healed, safe_stop, or failed
    - result_body: Response body on success
    - reason: Explanation of outcome
    - fix_proposal: What's needed to proceed (for safe_stop)
    - registry_version_before: Version before healing
    - registry_version_after: Version after healing (if patched)
    - elapsed_seconds: Total time from first failure to success
    - attempts: Number of API calls made
    """
    pass


class HealingExecutor:
    """
    Executes tool calls with automatic healing on drift.
    
    Combines all healing components into a complete flow.
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        client: httpx.Client,
        budget: Budget,
        log_events: bool = True
    ):
        """
        Initialize healing executor.
        
        Args:
            registry: Tool registry
            client: HTTP client
            budget: Shared budget
            log_events: Whether to log healing events
        """
        self.registry = registry
        self.client = client
        self.budget = budget
        self.log_events = log_events
    
    def execute(self, tool_name: str, args: dict[str, Any]) -> HealResult:
        """
        Execute tool with automatic healing.
        
        Args:
            tool_name: Name of tool to call
            args: Arguments for tool
            
        Returns:
            HealResult with status and details
        """
        start_time = time.time()
        attempts = 0
        
        # Get tool from registry
        tool = self.registry.get(tool_name)
        if tool is None:
            return HealResult({
                "status": "failed",
                "result_body": None,
                "reason": f"Tool {tool_name} not found in registry",
                "fix_proposal": None,
                "registry_version_before": None,
                "registry_version_after": None,
                "elapsed_seconds": time.time() - start_time,
                "attempts": 0,
            })
        
        version_before = tool["version"]
        
        # Step 1: Initial call
        self.budget.consume_api()
        attempts += 1
        
        result = call_tool(
            client=self.client,
            registry_tool=tool,
            tool_name=tool_name,
            args=args,
            extra_headers={},
        )
        
        if result["ok"]:
            # Success - no healing needed
            return HealResult({
                "status": "ok",
                "result_body": result["body"],
                "reason": "Success on first attempt",
                "fix_proposal": None,
                "registry_version_before": version_before,
                "registry_version_after": version_before,
                "elapsed_seconds": time.time() - start_time,
                "attempts": attempts,
            })
        
        # Step 2: Classify error
        def fetch_live_contract():
            try:
                # Handle TestClient vs httpx.Client
                if hasattr(self.client, 'get'):
                    response = self.client.get("/schema")
                else:
                    response = self.client.get(f"{self.client.base_url}/schema")
                
                if response.status_code == 200:
                    return response.json()
            except Exception:
                pass
            return None
        
        classification = classify(result, tool, fetch_live_contract)
        kind = classification["kind"]
        
        # Handle network errors with bounded retry
        if kind == "network":
            # Max 2 extra tries with short backoff
            for retry_num in range(2):
                if self.budget.exhausted():
                    break
                
                time.sleep(0.1 * (retry_num + 1))  # Short backoff
                self.budget.consume_api()
                attempts += 1
                
                result = call_tool(
                    client=self.client,
                    registry_tool=tool,
                    tool_name=tool_name,
                    args=args,
                    extra_headers={},
                )
                
                if result["ok"]:
                    return HealResult({
                        "status": "ok",
                        "result_body": result["body"],
                        "reason": f"Succeeded after {retry_num + 1} network retries",
                        "fix_proposal": None,
                        "registry_version_before": version_before,
                        "registry_version_after": version_before,
                        "elapsed_seconds": time.time() - start_time,
                        "attempts": attempts,
                    })
            
            # Network retries exhausted
            return HealResult({
                "status": "safe_stop",
                "result_body": None,
                "reason": "Network error persists after retries",
                "fix_proposal": None,
                "registry_version_before": version_before,
                "registry_version_after": version_before,
                "elapsed_seconds": time.time() - start_time,
                "attempts": attempts,
            })
        
        # Auth errors - no refresh in prototype
        if kind == "auth":
            return HealResult({
                "status": "safe_stop",
                "result_body": None,
                "reason": "Authentication error - no refresh flow",
                "fix_proposal": None,
                "registry_version_before": version_before,
                "registry_version_after": version_before,
                "elapsed_seconds": time.time() - start_time,
                "attempts": attempts,
            })
        
        # Invalid data or unknown - not drift
        if kind in ["invalid_data", "unknown"]:
            return HealResult({
                "status": "safe_stop",
                "result_body": None,
                "reason": f"Error kind: {kind} (not drift)",
                "fix_proposal": None,
                "registry_version_before": version_before,
                "registry_version_after": version_before,
                "elapsed_seconds": time.time() - start_time,
                "attempts": attempts,
            })
        
        # Step 3: Handle drift
        if kind == "drift":
            live_contract = classification["live_contract"]
            if live_contract is None:
                return self._safe_stop("Could not fetch live contract", version_before, start_time, attempts)
            
            live_hash = live_contract["content_hash"]
            
            # Diff
            changes = diff(tool, live_contract)
            
            # Check for ambiguous or errors
            for change in changes:
                if change.get("type") == "ambiguous":
                    return self._safe_stop(
                        f"Ambiguous change: {change['removed']} → {change['candidates']}",
                        version_before,
                        start_time,
                        attempts
                    )
            
            # Adapt
            adapt_result = adapt(args, changes)
            if adapt_result["error"] is not None:
                return self._safe_stop(
                    f"Adaptation error: {adapt_result['error']}",
                    version_before,
                    start_time,
                    attempts
                )
            
            payload = adapt_result["payload"]
            provenance = adapt_result["provenance"]
            needed_headers = adapt_result["needed_headers"]
            
            # Resolve headers
            headers, header_provenance, missing = resolve_headers(needed_headers)
            if missing:
                return HealResult({
                    "status": "safe_stop",
                    "result_body": None,
                    "reason": f"Required value unavailable: {', '.join(missing)}",
                    "fix_proposal": f"Missing headers: {missing}",
                    "registry_version_before": version_before,
                    "registry_version_after": version_before,
                    "elapsed_seconds": time.time() - start_time,
                    "attempts": attempts,
                })
            
            # Check provenance
            combined_provenance = {**provenance, **header_provenance}
            if not check_provenance(payload, provenance):
                return self._safe_stop(
                    "Provenance check failed - untagged values",
                    version_before,
                    start_time,
                    attempts
                )
            
            # Validate locally against live contract
            try:
                jsonschema.validate(instance=payload, schema=live_contract["body_schema"])
            except jsonschema.ValidationError as e:
                return self._safe_stop(
                    f"Local validation failed: {e.message}",
                    version_before,
                    start_time,
                    attempts
                )
            
            # Step 4: Build new snapshot and apply patch
            new_snapshot, snapshot_error = build_new_snapshot(tool, changes, live_contract)
            if new_snapshot is None:
                return self._safe_stop(
                    f"Could not build new snapshot: {snapshot_error}",
                    version_before,
                    start_time,
                    attempts
                )
            
            # Apply patch (version bump)
            self.registry.apply_patch(tool_name, new_snapshot, "schema drift detected")
            version_after = self.registry.version(tool_name)
            
            # Step 5: Retry once with adapted payload
            if self.budget.exhausted():
                self.registry.rollback(tool_name)
                return self._safe_stop("Budget exhausted before retry", version_before, start_time, attempts)
            
            self.budget.consume_api()
            attempts += 1
            
            patched_tool = self.registry.get(tool_name)
            retry_result = call_tool(
                client=self.client,
                registry_tool=patched_tool,
                tool_name=tool_name,
                args=payload,
                extra_headers=headers,
            )
            
            # Check if retry succeeded
            if retry_result["ok"]:
                # Verify contract hash matches (headers are case-insensitive)
                response_hash = retry_result["headers"].get("X-Contract-Hash") or retry_result["headers"].get("x-contract-hash")
                if response_hash != live_hash:
                    # Hash mismatch - rollback
                    self.registry.rollback(tool_name)
                    self._log_event(
                        tool_name, version_before, version_after, live_hash, response_hash,
                        changes, combined_provenance, "hash_mismatch", time.time() - start_time
                    )
                    return HealResult({
                        "status": "safe_stop",
                        "result_body": None,
                        "reason": f"Contract hash mismatch: patched against {live_hash}, saw {response_hash}",
                        "fix_proposal": None,
                        "registry_version_before": version_before,
                        "registry_version_after": version_before,
                        "elapsed_seconds": time.time() - start_time,
                        "attempts": attempts,
                    })
                
                # Success!
                self._log_event(
                    tool_name, version_before, version_after, live_hash, response_hash,
                    changes, combined_provenance, "healed", time.time() - start_time
                )
                
                return HealResult({
                    "status": "healed",
                    "result_body": retry_result["body"],
                    "reason": "Successfully healed schema drift",
                    "fix_proposal": None,
                    "registry_version_before": version_before,
                    "registry_version_after": version_after,
                    "elapsed_seconds": time.time() - start_time,
                    "attempts": attempts,
                })
            else:
                # Retry failed - rollback
                self.registry.rollback(tool_name)
                self._log_event(
                    tool_name, version_before, version_after, live_hash, None,
                    changes, combined_provenance, "retry_failed", time.time() - start_time
                )
                
                return HealResult({
                    "status": "safe_stop",
                    "result_body": None,
                    "reason": f"Retry failed with status {retry_result['status']}",
                    "fix_proposal": None,
                    "registry_version_before": version_before,
                    "registry_version_after": version_before,
                    "elapsed_seconds": time.time() - start_time,
                    "attempts": attempts,
                })
        
        # Should not reach here
        return self._safe_stop("Unexpected classification result", version_before, start_time, attempts)
    
    def _safe_stop(self, reason: str, version: int, start_time: float, attempts: int) -> HealResult:
        """Create a safe_stop result."""
        return HealResult({
            "status": "safe_stop",
            "result_body": None,
            "reason": reason,
            "fix_proposal": None,
            "registry_version_before": version,
            "registry_version_after": version,
            "elapsed_seconds": time.time() - start_time,
            "attempts": attempts,
        })
    
    def _log_event(
        self,
        tool_name: str,
        version_before: int,
        version_after: int,
        patched_hash: str,
        retry_hash: str | None,
        changes: list,
        provenance: dict,
        outcome: str,
        elapsed: float
    ) -> None:
        """Log healing event."""
        if not self.log_events:
            return
        
        # Extract all leaf provenance values from nested structure
        def extract_leaf_values(prov: Any) -> list[str]:
            """Recursively extract leaf string values from provenance dict."""
            result = []
            if isinstance(prov, dict):
                for value in prov.values():
                    result.extend(extract_leaf_values(value))
            elif isinstance(prov, str):
                result.append(prov)
            return result
        
        event = {
            "event": "healing",
            "tool": tool_name,
            "registry_version_before": version_before,
            "registry_version_after": version_after,
            "contract_hash_patched_against": patched_hash,
            "contract_hash_seen_on_retry": retry_hash,
            "changes": [
                {
                    "type": c.get("type"),
                    "tier": c.get("tier"),
                    **{k: v for k, v in c.items() if k not in ["type", "tier"]}
                }
                for c in changes
            ],
            "value_origins": list(set(extract_leaf_values(provenance))),
            "outcome": outcome,
            "elapsed_seconds": elapsed,
        }
        
        log.log_event(event)
