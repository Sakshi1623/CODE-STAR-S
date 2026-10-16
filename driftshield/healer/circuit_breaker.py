"""Recovery Circuit Breaker to prevent recovery thrashing and endless repair loops."""

import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple


class CircuitState(str, Enum):
    CLOSED = "CLOSED"          # Normal operation, recovery permitted
    OPEN = "OPEN"              # Breaker tripped, recovery blocked
    HALF_OPEN = "HALF_OPEN"    # Testing recovery via controlled probe


class RecoveryCircuitBreaker:
    """
    Stops repeated recovery attempts when an API consistently fails.
    
    Features:
    - Enforces retry limits per tool/endpoint
    - Temporarily blocks recovery attempts after repeated failures (OPEN state)
    - Permits a controlled probe using a read-only or dry-run operation in HALF_OPEN
    - Records state transition reasons and failure audit logs
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        on_state_change: Optional[Callable[[str, CircuitState, CircuitState, str], None]] = None,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.on_state_change = on_state_change
        
        # State per endpoint/tool: {tool_name: {"state": ..., "consecutive_failures": int, "last_failure_time": float, "last_reason": str}}
        self._circuits: Dict[str, Dict[str, Any]] = {}

    def _get_record(self, key: str) -> Dict[str, Any]:
        if key not in self._circuits:
            self._circuits[key] = {
                "state": CircuitState.CLOSED,
                "consecutive_failures": 0,
                "last_failure_time": 0.0,
                "last_reason": "",
            }
        return self._circuits[key]

    def _transition(self, key: str, new_state: CircuitState, reason: str) -> None:
        record = self._get_record(key)
        old_state = record["state"]
        if old_state != new_state:
            record["state"] = new_state
            if self.on_state_change:
                self.on_state_change(key, old_state, new_state, reason)

    def can_attempt_recovery(self, key: str) -> Tuple[bool, str]:
        """
        Check if recovery is currently allowed for this tool/endpoint.
        """
        record = self._get_record(key)
        state = record["state"]

        if state == CircuitState.CLOSED:
            return True, "Circuit is CLOSED (normal operation)"

        if state == CircuitState.OPEN:
            elapsed = time.time() - record["last_failure_time"]
            if elapsed >= self.cooldown_seconds:
                self._transition(
                    key,
                    CircuitState.HALF_OPEN,
                    f"Cooldown expired ({elapsed:.1f}s >= {self.cooldown_seconds}s)"
                )
                return True, "Circuit entered HALF_OPEN (probing allowed)"
            return (
                False,
                f"Circuit is OPEN (cooldown remaining: {self.cooldown_seconds - elapsed:.1f}s). Reason: {record['last_reason']}"
            )

        if state == CircuitState.HALF_OPEN:
            # One probe at a time allowed
            return True, "Circuit is HALF_OPEN (probe permitted)"

        return False, "Unknown circuit state"

    def record_success(self, key: str) -> None:
        """Call when an API call or recovery probe succeeds."""
        record = self._get_record(key)
        old_state = record["state"]
        record["consecutive_failures"] = 0
        record["last_reason"] = ""
        if old_state != CircuitState.CLOSED:
            self._transition(key, CircuitState.CLOSED, "Recovery probe succeeded; circuit reset to CLOSED")

    def record_failure(self, key: str, reason: str) -> None:
        """Call when a recovery attempt fails."""
        record = self._get_record(key)
        record["consecutive_failures"] += 1
        record["last_failure_time"] = time.time()
        record["last_reason"] = reason

        if record["state"] == CircuitState.HALF_OPEN:
            self._transition(key, CircuitState.OPEN, f"Controlled probe failed: {reason}")
        elif record["consecutive_failures"] >= self.failure_threshold:
            self._transition(
                key,
                CircuitState.OPEN,
                f"Failure threshold reached ({record['consecutive_failures']}/{self.failure_threshold}): {reason}"
            )

    def execute_probe(self, key: str, probe_fn: Callable[[], bool], dry_run_name: str = "dry_run") -> bool:
        """
        Execute a controlled read-only or dry-run probe when in HALF_OPEN.
        """
        try:
            success = probe_fn()
            if success:
                self.record_success(key)
                return True
            else:
                self.record_failure(key, f"Probe '{dry_run_name}' returned false")
                return False
        except Exception as e:
            self.record_failure(key, f"Probe '{dry_run_name}' raised exception: {str(e)}")
            return False

    def get_state(self, key: str) -> CircuitState:
        record = self._get_record(key)
        return record["state"]

    def reset(self, key: Optional[str] = None) -> None:
        """Reset circuit breaker state for a tool or all tools."""
        if key is None:
            self._circuits.clear()
        elif key in self._circuits:
            self._circuits[key] = {
                "state": CircuitState.CLOSED,
                "consecutive_failures": 0,
                "last_failure_time": 0.0,
                "last_reason": "",
            }
