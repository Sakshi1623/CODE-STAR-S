"""HTTP interceptor for tool calls with error handling."""

import time
from typing import Any, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired  # type: ignore

import httpx

from driftshield import config
from driftshield.healer.registry import Tool


class CallResult(TypedDict):
    """Result of a tool call."""
    ok: bool
    status: int | None
    body: dict[str, Any] | None
    headers: dict[str, str]
    request: dict[str, Any]
    elapsed_seconds: float
    network_error: NotRequired[str | None]


def _redact_header_values(headers: dict[str, str]) -> dict[str, str]:
    """
    Redact header values for logging.
    
    Args:
        headers: Headers dict
        
    Returns:
        Dict with header names but redacted values
    """
    return {name: "<redacted>" for name in headers.keys()}


def call_tool(
    client: httpx.Client,
    registry_tool: Tool,
    tool_name: str,
    args: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> CallResult:
    """
    Call a tool via HTTP with full error handling.
    
    Args:
        client: httpx.Client or FastAPI TestClient
        registry_tool: Tool definition from registry
        tool_name: Name of tool being called
        args: Arguments to send as JSON body
        extra_headers: Additional HTTP headers to include
        
    Returns:
        CallResult with status, body, headers, timing, and error info
        
    Note:
        Never raises exceptions. Network errors are captured in network_error field.
    """
    start_time = time.time()
    
    # Prepare headers
    headers = extra_headers.copy() if extra_headers else {}
    
    # Build request info (redact header values)
    request_info = {
        "body": args,
        "headers": _redact_header_values(headers),
    }
    
    # Make the HTTP call
    try:
        # Handle TestClient vs httpx.Client base_url
        if hasattr(client, 'base_url') and client.base_url:
            url = f"{client.base_url}/users/lookup"
        else:
            url = f"{config.BASE_URL}/users/lookup"
        
        response = client.post(url, json=args, headers=headers)
        
        elapsed = time.time() - start_time
        
        # Try to parse response body as JSON
        try:
            body = response.json()
        except Exception:
            body = None
        
        return CallResult(
            ok=(200 <= response.status_code < 300),
            status=response.status_code,
            body=body,
            headers=dict(response.headers),
            request=request_info,
            elapsed_seconds=elapsed,
            network_error=None,
        )
    
    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        elapsed = time.time() - start_time
        
        return CallResult(
            ok=False,
            status=None,
            body=None,
            headers={},
            request=request_info,
            elapsed_seconds=elapsed,
            network_error=str(e),
        )
    
    except Exception as e:
        # Catch any other unexpected errors
        elapsed = time.time() - start_time
        
        return CallResult(
            ok=False,
            status=None,
            body=None,
            headers={},
            request=request_info,
            elapsed_seconds=elapsed,
            network_error=f"Unexpected error: {str(e)}",
        )
