"""API routes for DriftShield Control Room."""

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from driftshield.api.sse import SSEBroadcaster
from driftshield.mock_api import contracts
from driftshield.shield import Shield

ALLOWED_DEMO_TOOLS = {"lookup_user"}


class DemoExecuteRequest(BaseModel):
    tool_name: str
    args: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None

    def get_effective_args(self) -> dict[str, Any]:
        """Resolve arguments whether passed as 'parameters' or 'args'."""
        if self.parameters is not None:
            return self.parameters
        if self.args is not None:
            return self.args
        return {}


def create_api_router(shield: Shield, broadcaster: SSEBroadcaster) -> APIRouter:
    """Create APIRouter bound to a Shield instance and SSE broadcaster."""
    router = APIRouter()

    def _get_shield(request: Request | None = None) -> Shield:
        if request is not None and hasattr(request, "app") and hasattr(request.app.state, "shield"):
            return request.app.state.shield
        return shield

    @router.get("/health")
    def get_health(request: Request) -> dict[str, Any]:
        """Health check endpoint."""
        active_shield = _get_shield(request)
        return {
            "status": "healthy",
            "service": "driftshield",
            "shield_closed": active_shield.is_closed,
        }

    @router.get("/status")
    def get_status(request: Request) -> dict[str, Any]:
        """Return runtime status of Shield, Sentinel, registry, and contracts."""
        active_shield = _get_shield(request)
        sentinel_enabled = False
        sentinel_running = False
        if active_shield.sentinel is not None:
            sentinel_enabled = True
            sentinel_running = active_shield.sentinel.is_running

        tools_dict = active_shield.registry.build_tools()
        tool_names = [t["name"] for t in tools_dict]
        versions = {}
        for name in tool_names:
            try:
                versions[name] = active_shield.registry.version(name)
            except Exception:
                pass

        active_contract = contracts.get_active()

        return {
            "status": "closed" if shield.is_closed else "active",
            "shield_status": "closed" if shield.is_closed else "active",
            "sentinel_enabled": sentinel_enabled,
            "sentinel_running": sentinel_running,
            "registered_tools": tool_names,
            "registry_versions": versions,
            "shield": {
                "status": "closed" if shield.is_closed else "active",
                "sentinel_enabled": sentinel_enabled,
                "sentinel_running": sentinel_running,
            },
            "registry": {
                "tools": tool_names,
                "versions": versions,
            },
            "upstream_contract": {
                "schema_version": active_contract.get("schema_version"),
                "content_hash": active_contract.get("content_hash"),
            },
        }

    @router.get("/events")
    async def get_events(request: Request, limit: int | None = None):
        """Stream structured runtime events via Server-Sent Events (SSE)."""
        q = await broadcaster.connect()
        return StreamingResponse(
            broadcaster.event_generator(q, request=request, limit=limit),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/demo/execute")
    def execute_demo_tool(req: DemoExecuteRequest, request: Request) -> dict[str, Any]:
        """Execute a specifically allowed demo tool through Shield.execute()."""
        active_shield = _get_shield(request)
        if req.tool_name not in ALLOWED_DEMO_TOOLS:
            raise HTTPException(
                status_code=400,
                detail=f"Disallowed tool '{req.tool_name}'. Allowed demo tools: {sorted(ALLOWED_DEMO_TOOLS)}",
            )

        effective_args = req.get_effective_args()
        if not isinstance(effective_args, dict):
            raise HTTPException(status_code=422, detail="Args or parameters must be a dictionary.")

        if active_shield.is_closed:
            raise HTTPException(status_code=503, detail="Shield instance is closed.")

        result = active_shield.execute(req.tool_name, effective_args)
        status_val = result.get("status")
        is_success = status_val in ("ok", "healed")

        return {
            "status": status_val,
            "success": is_success,
            "result": result.get("result_body"),
            "result_body": result.get("result_body"),
            "reason": result.get("reason"),
            "fix_proposal": result.get("fix_proposal"),
            "registry_version_before": result.get("registry_version_before"),
            "registry_version_after": result.get("registry_version_after"),
            "registryBefore": result.get("registry_version_before"),
            "registryAfter": result.get("registry_version_after"),
            "attempts": result.get("attempts"),
            "elapsed_seconds": result.get("elapsed_seconds"),
        }

    return router
