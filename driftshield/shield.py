"""Shield facade: Simple, unified public interface for DriftShield.

Coordinates the ToolRegistry, HealingExecutor, and proactive Sentinel.
"""

from typing import Any, Callable
import httpx

from driftshield import config
from driftshield.healer.registry import ToolRegistry, create_default_registry
from driftshield.healer.retry import HealingExecutor, Budget, HealResult
from driftshield.healer.sentinel import Sentinel


class Shield:
    """Public facade for DriftShield runtime resilience and self-healing.

    Provides a clean entry point for AI agents to invoke external API tools
    with transparent schema drift detection, automatic healing, and proactive
    background contract monitoring.
    """

    def __init__(
        self,
        client: Any | None = None,
        registry: ToolRegistry | None = None,
        budget: Budget | dict[str, int] | None = None,
        enable_sentinel: bool = False,
        sentinel_poll_interval: float = 10.0,
        sentinel_tool_name: str = "lookup_user",
        sentinel_schema_url: str = "/schema",
        log_events: bool = True,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        base_url: str | None = None,
    ):
        # 1. Configuration validation
        if not isinstance(sentinel_poll_interval, (int, float)) or sentinel_poll_interval <= 0:
            raise ValueError(
                f"Invalid sentinel_poll_interval: {sentinel_poll_interval}. Must be a positive number."
            )

        if budget is not None:
            if isinstance(budget, dict):
                max_api = budget.get("max_api_attempts", 5)
                max_model = budget.get("max_model_calls", 8)
                if not isinstance(max_api, int) or max_api < 1:
                    raise ValueError(f"Invalid max_api_attempts: {max_api}. Must be an integer >= 1.")
                if not isinstance(max_model, int) or max_model < 0:
                    raise ValueError(f"Invalid max_model_calls: {max_model}. Must be an integer >= 0.")
                self._budget = Budget(max_api_attempts=max_api, max_model_calls=max_model)
            elif isinstance(budget, Budget):
                if budget.max_api_attempts < 1:
                    raise ValueError(f"Invalid max_api_attempts: {budget.max_api_attempts}. Must be >= 1.")
                if budget.max_model_calls < 0:
                    raise ValueError(f"Invalid max_model_calls: {budget.max_model_calls}. Must be >= 0.")
                self._budget = budget
            else:
                raise TypeError(f"Invalid budget type: {type(budget)}. Expected Budget instance or dict.")
        else:
            self._budget = Budget(max_api_attempts=5, max_model_calls=8)

        # 2. Registry setup
        self._registry = registry if registry is not None else create_default_registry()

        # 3. HTTP Client setup (track ownership)
        if client is None:
            effective_base_url = base_url or config.BASE_URL
            self._client = httpx.Client(base_url=effective_base_url)
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False

        self._log_events = log_events
        self._subscribers: list[Callable[[str, dict[str, Any]], None]] = []
        if on_event is not None:
            self._subscribers.append(on_event)

        # 4. Executor setup
        self._executor = HealingExecutor(
            registry=self._registry,
            client=self._client,
            budget=self._budget,
            log_events=self._log_events,
            on_event=self._dispatch_event,
        )

        # 5. Sentinel setup
        self._enable_sentinel = enable_sentinel
        self._sentinel_poll_interval = sentinel_poll_interval
        self._sentinel_tool_name = sentinel_tool_name
        self._sentinel_schema_url = sentinel_schema_url
        self._sentinel: Sentinel | None = None

        if self._enable_sentinel:
            self._sentinel = Sentinel(
                registry=self._registry,
                client=self._client,
                tool_name=self._sentinel_tool_name,
                poll_interval=self._sentinel_poll_interval,
                schema_url=self._sentinel_schema_url,
                on_event=self._dispatch_event,
                log_events=self._log_events,
                auto_baseline=True,
            )
            self._sentinel.start()

        self._is_closed = False

    @property
    def registry(self) -> ToolRegistry:
        """Access the underlying ToolRegistry."""
        return self._registry

    @property
    def client(self) -> Any:
        """Access the HTTP client."""
        return self._client

    @property
    def budget(self) -> Budget:
        """Access the execution budget."""
        return self._budget

    @property
    def sentinel(self) -> Sentinel | None:
        """Access the Sentinel monitor if enabled, or None."""
        return self._sentinel

    @property
    def is_closed(self) -> bool:
        """Check if the Shield instance has been closed."""
        return self._is_closed

    def subscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Subscribe a callback to receive all structured telemetry and audit events.

        Args:
            callback: Function accepting (event_name: str, event_data: dict)
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Remove an event subscriber callback."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _dispatch_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        """Forward events to all registered subscribers without failing on subscriber errors."""
        for subscriber in list(self._subscribers):
            try:
                subscriber(event_name, event_data)
            except Exception:
                pass

    def execute(self, tool_name: str, args: dict[str, Any]) -> HealResult:
        """Execute a registered tool call with automatic drift healing.

        Delegates to the HealingExecutor while enforcing facade lifecycle checks.

        Args:
            tool_name: Name of tool registered in registry.
            args: Arguments provided for the tool call.

        Returns:
            HealResult with status ('ok', 'healed', 'safe_stop', 'failed'),
            result_body, versions, timing, and explanations.

        Raises:
            RuntimeError: If Shield has been closed.
        """
        if self._is_closed:
            raise RuntimeError("Cannot execute tool: Shield instance is closed.")

        return self._executor.execute(tool_name, args)

    def start_sentinel(self) -> None:
        """Start background Sentinel monitoring if not already running."""
        if self._is_closed:
            raise RuntimeError("Cannot start Sentinel: Shield instance is closed.")

        if self._sentinel is None:
            self._sentinel = Sentinel(
                registry=self._registry,
                client=self._client,
                tool_name=self._sentinel_tool_name,
                poll_interval=self._sentinel_poll_interval,
                schema_url=self._sentinel_schema_url,
                on_event=self._dispatch_event,
                log_events=self._log_events,
                auto_baseline=True,
            )
        self._sentinel.start()

    def stop_sentinel(self, timeout: float = 2.0) -> None:
        """Stop background Sentinel monitoring if active."""
        if self._sentinel is not None:
            self._sentinel.stop(timeout=timeout)

    def close(self) -> None:
        """Release resources cleanly.

        Stops Sentinel background thread if running.
        Closes HTTP client ONLY IF it was created and owned by Shield.
        """
        if self._is_closed:
            return

        self.stop_sentinel()

        if self._owns_client and self._client is not None:
            try:
                if hasattr(self._client, "close"):
                    self._client.close()
            except Exception:
                pass

        self._is_closed = True

    def __enter__(self) -> "Shield":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
