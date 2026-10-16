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


def fetch_live_contract_fn(client) -> "dict | None":
    """Fetch the live contract from /schema endpoint.

    Used by both the initial success path (response drift detection) and
    the request-failure path (error classification). Returns None on any error.

    Args:
        client: httpx.Client or FastAPI TestClient

    Returns:
        Contract dict or None
    """
    try:
        if hasattr(client, "get"):
            response = client.get("/schema")
        else:
            response = client.get(f"{client.base_url}/schema")
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


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
    - t_first_failure: Time of first non-2xx response (or None)
    - t_first_success: Time of first 2xx response after failure (or None)
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
        log_events: bool = True,
        on_event: callable = None
    ):
        """
        Initialize healing executor.

        Args:
            registry: Tool registry
            client: HTTP client
            budget: Shared budget
            log_events: Whether to log healing events
            on_event: Optional callback(event_name, event_data) for live monitoring
        """
        self.registry = registry
        self.client = client
        self.budget = budget
        self.log_events = log_events
        self.on_event = on_event

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
        t_first_failure: float | None = None
        t_first_success: float | None = None

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
                "t_first_failure": None,
                "t_first_success": None,
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

        self._emit_event("intercepted", {
            "tool_name": tool_name,
            "status_code": result["status"],
            "ok": result["ok"]
        })

        if result["ok"]:
            # HTTP 2xx: validate the response body against the registered
            # response schema before accepting it as a valid business result.
            response_schema = tool.get("response_schema")
            if response_schema is not None:
                try:
                    jsonschema.validate(instance=result["body"], schema=response_schema)
                except jsonschema.ValidationError as _resp_err:
                    # Response body violates the registered schema.
                    # Attempt to determine whether this is genuine response drift
                    # (live contract changed) or a broken API response.
                    live_contract_for_resp = fetch_live_contract_fn(self.client)
                    live_resp_schema = (
                        live_contract_for_resp.get("response_schema")
                        if live_contract_for_resp else None
                    )
                    if live_resp_schema is not None:
                        try:
                            jsonschema.validate(instance=result["body"], schema=live_resp_schema)
                            # Body matches live schema but NOT registered schema.
                            # This is genuine response drift: the API changed its
                            # response format and the registry is stale.
                            # Record the event but do NOT auto-retry (operation may
                            # not be idempotent) and do NOT expose an unverified body.
                            self._emit_event("response_drift_detected", {
                                "tool_name": tool_name,
                                "registered_schema": response_schema,
                                "live_schema": live_resp_schema,
                                "validation_error": str(_resp_err.message),
                            })
                            if self.log_events:
                                log.log_event({
                                    "event": "response_validation_failure",
                                    "tool": tool_name,
                                    "kind": "response_drift",
                                    "reason": "body matches live contract response_schema but not registered schema",
                                    "validation_error": str(_resp_err.message),
                                })
                            return HealResult({
                                "status": "safe_stop",
                                "result_body": None,
                                "reason": (
                                    "Response drift detected: API returned HTTP 200 but the "
                                    "response body matches the live contract schema rather than "
                                    f"the registered schema. Validation error: {_resp_err.message}"
                                ),
                                "fix_proposal": "Update registry response_schema to match live contract",
                                "registry_version_before": version_before,
                                "registry_version_after": version_before,
                                "elapsed_seconds": time.time() - start_time,
                                "attempts": attempts,
                                "t_first_failure": None,
                                "t_first_success": None,
                            })
                        except jsonschema.ValidationError:
                            pass  # Fall through: body fails both schemas (broken API)
                    # Body fails registered schema AND (live schema unavailable OR
                    # body also fails live schema). Safe-stop: do not expose invalid body.
                    self._emit_event("response_validation_failed", {
                        "tool_name": tool_name,
                        "validation_error": str(_resp_err.message),
                    })
                    if self.log_events:
                        log.log_event({
                            "event": "response_validation_failure",
                            "tool": tool_name,
                            "kind": "invalid_response",
                            "reason": "body fails registered and live response schemas",
                            "validation_error": str(_resp_err.message),
                        })
                    return HealResult({
                        "status": "safe_stop",
                        "result_body": None,
                        "reason": (
                            "Response validation failed: HTTP 200 but body does not match "
                            f"registered or live response schema. Validation error: {_resp_err.message}"
                        ),
                        "fix_proposal": None,
                        "registry_version_before": version_before,
                        "registry_version_after": version_before,
                        "elapsed_seconds": time.time() - start_time,
                        "attempts": attempts,
                        "t_first_failure": None,
                        "t_first_success": None,
                    })

            # Response is valid (or no schema to validate against)
            self._emit_event("success", {
                "tool_name": tool_name,
                "attempts": attempts,
                "version": version_before
            })
            return HealResult({
                "status": "ok",
                "result_body": result["body"],
                "reason": "Success on first attempt",
                "fix_proposal": None,
                "registry_version_before": version_before,
                "registry_version_after": version_before,
                "elapsed_seconds": time.time() - start_time,
                "attempts": attempts,
                "t_first_failure": None,
                "t_first_success": None,
            })

        # First failure occurred
        t_first_failure = time.time()

        # Step 2: Classify error
        classification = classify(result, tool, lambda: fetch_live_contract_fn(self.client))
        kind = classification["kind"]

        self._emit_event("classified", {
            "tool_name": tool_name,
            "kind": kind
        })

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
                    t_first_success = time.time()
                    return HealResult({
                        "status": "ok",
                        "result_body": result["body"],
                        "reason": f"Succeeded after {retry_num + 1} network retries",
                        "fix_proposal": None,
                        "registry_version_before": version_before,
                        "registry_version_after": version_before,
                        "elapsed_seconds": time.time() - start_time,
                        "attempts": attempts,
                        "t_first_failure": t_first_failure,
                        "t_first_success": t_first_success,
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
                "t_first_failure": t_first_failure,
                "t_first_success": None,
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
                "t_first_failure": t_first_failure,
                "t_first_success": None,
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
                "t_first_failure": t_first_failure,
                "t_first_success": None,
            })

        # Step 3: Handle drift
        if kind == "drift":
            live_contract = classification["live_contract"]
            if live_contract is None:
                return self._safe_stop("Could not fetch live contract", version_before, start_time, attempts, t_first_failure)

            live_hash = live_contract["content_hash"]

            self._emit_event("contract_fetched", {
                "tool_name": tool_name,
                "contract_hash": live_hash
            })

            # Diff
            changes = diff(tool, live_contract)

            self._emit_event("diff", {
                "tool_name": tool_name,
                "changes": [{
                    "type": c.get("type"),
                    "tier": c.get("tier"),
                    "removed": c.get("removed"),
                    "added": c.get("added"),
                    "candidates": c.get("candidates")
                } for c in changes]
            })

            # Check for ambiguous or errors
            for change in changes:
                if change.get("type") == "ambiguous":
                    return self._safe_stop(
                        f"Ambiguous change: {change['removed']} → {change['candidates']}",
                        version_before,
                        start_time,
                        attempts,
                        t_first_failure
                    )

            # Adapt
            adapt_result = adapt(args, changes)
            if adapt_result["error"] is not None:
                return self._safe_stop(
                    f"Adaptation error: {adapt_result['error']}",
                    version_before,
                    start_time,
                    attempts,
                    t_first_failure
                )

            payload = adapt_result["payload"]
            provenance = adapt_result["provenance"]
            needed_headers = adapt_result["needed_headers"]

            # Resolve headers
            headers, header_provenance, missing = resolve_headers(needed_headers)

            self._emit_event("provenance_checked", {
                "tool_name": tool_name,
                "needed_headers": needed_headers,
                "missing": missing
            })

            if missing:
                self._emit_event("safe_stop", {
                    "tool_name": tool_name,
                    "reason": f"Required value unavailable: {', '.join(missing)}",
                    "missing_headers": missing
                })
                return HealResult({
                    "status": "safe_stop",
                    "result_body": None,
                    "reason": f"Required value unavailable: {', '.join(missing)}",
                    "fix_proposal": f"Missing headers: {missing}",
                    "registry_version_before": version_before,
                    "registry_version_after": version_before,
                    "elapsed_seconds": time.time() - start_time,
                    "attempts": attempts,
                    "t_first_failure": t_first_failure,
                    "t_first_success": None,
                })

            # Check provenance
            combined_provenance = {**provenance, **header_provenance}
            if not check_provenance(payload, provenance):
                return self._safe_stop(
                    "Provenance check failed - untagged values",
                    version_before,
                    start_time,
                    attempts,
                    t_first_failure
                )

            # Validate locally against live contract
            try:
                jsonschema.validate(instance=payload, schema=live_contract["body_schema"])
                self._emit_event("validated", {
                    "tool_name": tool_name,
                    "payload_valid": True
                })
            except jsonschema.ValidationError as e:
                return self._safe_stop(
                    f"Local validation failed: {e.message}",
                    version_before,
                    start_time,
                    attempts,
                    t_first_failure
                )

            # Step 4: Build new snapshot and apply patch
            new_snapshot, snapshot_error = build_new_snapshot(tool, changes, live_contract)
            if new_snapshot is None:
                return self._safe_stop(
                    f"Could not build new snapshot: {snapshot_error}",
                    version_before,
                    start_time,
                    attempts,
                    t_first_failure
                )

            # Apply patch (version bump)
            self.registry.apply_patch(tool_name, new_snapshot, "schema drift detected")
            version_after = self.registry.version(tool_name)

            self._emit_event("patched", {
                "tool_name": tool_name,
                "version_before": version_before,
                "version_after": version_after
            })

            # Step 5: Retry once with adapted payload
            if self.budget.exhausted():
                self.registry.rollback(tool_name)
                return self._safe_stop("Budget exhausted before retry", version_before, start_time, attempts, t_first_failure)

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

            self._emit_event("retried", {
                "tool_name": tool_name,
                "status_code": retry_result["status"],
                "ok": retry_result["ok"]
            })

            # Check if retry succeeded
            if retry_result["ok"]:
                t_first_success = time.time()

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
                        "t_first_failure": t_first_failure,
                        "t_first_success": t_first_success,
                    })

                # Validate response body against patched tool's response schema.
                # IMPORTANT: do NOT roll back the valid request-side patch if
                # only the response body is malformed.  The patch was correct;
                # the response failure is a separate problem.
                patched_resp_schema = patched_tool.get("response_schema") if patched_tool else None
                if patched_resp_schema is not None:
                    try:
                        jsonschema.validate(instance=retry_result["body"], schema=patched_resp_schema)
                    except jsonschema.ValidationError as _retry_resp_err:
                        # Retry response is malformed.  Keep the request patch in place
                        # (registry_version_after is preserved) but do not expose the body.
                        self._emit_event("response_validation_failed", {
                            "tool_name": tool_name,
                            "phase": "retry",
                            "validation_error": str(_retry_resp_err.message),
                        })
                        self._log_event(
                            tool_name, version_before, version_after, live_hash, response_hash,
                            changes, combined_provenance, "response_validation_failed",
                            time.time() - start_time
                        )
                        return HealResult({
                            "status": "safe_stop",
                            "result_body": None,
                            "reason": (
                                "Retry response validation failed: request-side patch was correct "
                                "but the response body is malformed. "
                                f"Validation error: {_retry_resp_err.message}"
                            ),
                            "fix_proposal": None,
                            # Preserve version_after: the request patch is valid and stays
                            "registry_version_before": version_before,
                            "registry_version_after": version_after,
                            "elapsed_seconds": time.time() - start_time,
                            "attempts": attempts,
                            "t_first_failure": t_first_failure,
                            "t_first_success": t_first_success,
                        })

                # Retry body is valid (or no schema).  Healing complete.
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
                    "t_first_failure": t_first_failure,
                    "t_first_success": t_first_success,
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
                    "t_first_failure": t_first_failure,
                    "t_first_success": None,
                })

        # Should not reach here
        return self._safe_stop("Unexpected classification result", version_before, start_time, attempts, t_first_failure)

    def _safe_stop(self, reason: str, version: int, start_time: float, attempts: int, t_first_failure: float | None = None) -> HealResult:
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
            "t_first_failure": t_first_failure,
            "t_first_success": None,
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

    def _emit_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        """Emit event to callback if configured (never includes secrets)."""
        if self.on_event:
            self.on_event(event_name, event_data)
