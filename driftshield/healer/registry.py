"""Tool registry with versioning and patching."""

import threading
from typing import Any, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired  # type: ignore


class StaleVersionError(ValueError):
    """Raised when applying a patch against a stale expected tool version."""
    pass


class Tool(TypedDict):
    """Tool definition in registry."""
    name: str
    description: str
    operation: str
    version: int
    contract_hash: str
    body_schema: dict[str, Any]
    required_headers: list[str]
    response_schema: NotRequired[dict[str, Any]]  # Optional response body schema


class ToolRegistry:
    """
    Registry holding versioned tool definitions.

    Each tool has a version that increases on every patch or rollback.
    History stores previous versions for rollback capability.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._lock = threading.RLock()
        self._tools: dict[str, Tool] = {}
        self._history: dict[str, list[Tool]] = {}

    @property
    def lock(self) -> threading.RLock:
        """Lock for atomic multi-operation sequences."""
        return self._lock

    def register(self, tool: Tool) -> None:
        """
        Register a new tool or replace existing one.

        Args:
            tool: Tool definition with all required fields
        """
        with self._lock:
            name = tool["name"]

            # If tool exists, save to history before replacing
            if name in self._tools:
                if name not in self._history:
                    self._history[name] = []
                self._history[name].append(self._tools[name].copy())

            self._tools[name] = tool.copy()

    def get(self, name: str) -> Tool | None:
        """
        Get tool by name.

        Args:
            name: Tool name

        Returns:
            Tool definition or None if not found
        """
        with self._lock:
            tool = self._tools.get(name)
            return tool.copy() if tool is not None else None

    def build_tools(self) -> list[dict[str, Any]]:
        """
        Build tool list for LLM function calling.

        Returns fresh list on every call with no caching.
        Format matches OpenAI/Anthropic function calling spec.

        Returns:
            List of function-calling dicts with name, description, parameters
        """
        with self._lock:
            result = []
            for tool in self._tools.values():
                params = tool["body_schema"].copy() if isinstance(tool.get("body_schema"), dict) else tool.get("body_schema")
                result.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": params,
                })
            return result

    def apply_patch(
        self,
        name: str,
        new_snapshot: Tool,
        reason: str,
        expected_version: int | None = None,
    ) -> None:
        """
        Apply a patch to a tool by creating a new version.

        Bumps version by 1 and stores previous version in history.

        Args:
            name: Tool name to patch
            new_snapshot: New tool definition
            reason: Reason for the patch (for logging)
            expected_version: Optional expected version for concurrency validation.
                If provided and the tool's current version differs, raises StaleVersionError.

        Raises:
            KeyError: If tool not found
            StaleVersionError: If current tool version does not match expected_version
        """
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"Tool {name} not found")

            current_version = self._tools[name]["version"]
            if expected_version is not None and current_version != expected_version:
                raise StaleVersionError(
                    f"Stale version for tool '{name}': expected {expected_version}, "
                    f"found {current_version}"
                )

            # Save current version to history
            if name not in self._history:
                self._history[name] = []
            self._history[name].append(self._tools[name].copy())

            # Apply patch with incremented version
            new_version = current_version + 1
            patched = new_snapshot.copy()
            patched["version"] = new_version
            patched["name"] = name  # Ensure name stays consistent

            self._tools[name] = patched

    def rollback(self, name: str) -> None:
        """
        Rollback to previous version.

        Restores previous version from history but bumps version forward
        (versions always increase, never decrease).

        Args:
            name: Tool name to rollback

        Raises:
            KeyError: If tool not found or no history available
        """
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"Tool {name} not found")

            if name not in self._history or not self._history[name]:
                raise KeyError(f"No history available for tool {name}")

            # Get previous version from history
            previous = self._history[name].pop()

            # Bump version forward (never go backward)
            new_version = self._tools[name]["version"] + 1
            previous["version"] = new_version

            self._tools[name] = previous

    def version(self, name: str) -> int:
        """
        Get current version of a tool.

        Args:
            name: Tool name

        Returns:
            Current version number

        Raises:
            KeyError: If tool not found
        """
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"Tool {name} not found")

            return self._tools[name]["version"]


# Create initial registry with lookup_user tool matching v1 contract
def create_default_registry() -> ToolRegistry:
    """
    Create registry with default lookup_user tool.

    Returns:
        ToolRegistry with lookup_user tool registered
    """
    registry = ToolRegistry()

    # Import here to avoid circular dependency
    from driftshield.mock_api.contracts import CONTRACTS

    v1_contract = CONTRACTS["v1"]

    lookup_user_tool: Tool = {
        "name": "lookup_user",
        "description": "Look up a user by ID",
        "operation": "lookup_user",
        "version": 1,
        "contract_hash": v1_contract["content_hash"],
        "body_schema": v1_contract["body_schema"],
        "required_headers": v1_contract["required_headers"],
    }

    # Propagate response_schema if present in contract
    if "response_schema" in v1_contract:
        lookup_user_tool["response_schema"] = v1_contract["response_schema"]

    registry.register(lookup_user_tool)
    return registry
