"""FastAPI server with runtime schema mutations."""

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import jsonschema
from jsonschema import ValidationError as JsonSchemaValidationError

from . import contracts


app = FastAPI()


# In-memory user database
USERS = {
    123: {"id": 123, "name": "Asha Rao"},
    124: {"id": 124, "name": "Ravi Iyer"},
}


# Execution counter
_execution_stats = {"successful_lookups": 0}


# Fault injection state
_fault_mode: str | None = None


class MutateRequest(BaseModel):
    """Request to change active contract."""
    to: str


class FaultRequest(BaseModel):
    """Request to inject faults."""
    mode: str | None


def _add_contract_headers(response: Response) -> None:
    """Add schema version and hash headers to response."""
    contract = contracts.get_active()
    response.headers["X-Schema-Version"] = contract["schema_version"]
    response.headers["X-Contract-Hash"] = contract["content_hash"]


@app.get("/schema")
def get_schema(response: Response) -> dict:
    """Return the active contract."""
    contract = contracts.get_active()
    _add_contract_headers(response)
    return contract


@app.post("/users/lookup")
async def lookup_user(request: Request, response: Response) -> JSONResponse:
    """
    Look up user by ID with active contract validation.

    Validates required headers and body schema against active contract.
    Returns 200 with user data on success, 400/422/404 on errors.
    """
    # Check fault injection first
    if _fault_mode == "expired_token":
        _add_contract_headers(response)
        return JSONResponse(
            status_code=401,
            content={"error": "token_expired"},
            headers=response.headers,
        )
    elif _fault_mode == "server_down":
        _add_contract_headers(response)
        return JSONResponse(
            status_code=503,
            content={"error": "unavailable"},
            headers=response.headers,
        )

    contract = contracts.get_active()

    # Validate required headers
    for header_name in contract["required_headers"]:
        if header_name not in request.headers:
            _add_contract_headers(response)
            return JSONResponse(
                status_code=400,
                content={"error": "missing_header", "header": header_name},
                headers=response.headers,
            )

    # Parse and validate body
    try:
        body = await request.json()
    except Exception:
        _add_contract_headers(response)
        return JSONResponse(
            status_code=422,
            content={"detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}]},
            headers=response.headers,
        )

    # Validate against body_schema
    try:
        jsonschema.validate(instance=body, schema=contract["body_schema"])
    except JsonSchemaValidationError as e:
        _add_contract_headers(response)
        # Format error similar to FastAPI's validation errors
        error_path = list(e.path) if e.path else ["body"]
        return JSONResponse(
            status_code=422,
            content={
                "detail": [{
                    "loc": error_path,
                    "msg": e.message,
                    "type": "value_error.jsonschemamismatch"
                }]
            },
            headers=response.headers,
        )

    # Extract user ID from body based on schema structure
    user_id = None
    if "user_id" in body:
        # v1, type_int, header_tenant, header_billing schemas
        user_id = body["user_id"]
    elif "uid" in body:
        # rename_uid schema
        user_id = body["uid"]
    elif "id" in body:
        # rename_id, header_rename schemas
        user_id = body["id"]
    elif "target" in body and "id" in body["target"]:
        # v2_full, nest_target, combo, combo_billing schemas
        user_id = body["target"]["id"]
    elif "data" in body and "user" in body["data"] and "id" in body["data"]["user"]:
        # nest_deep schema
        user_id = body["data"]["user"]["id"]
    elif "ref_a" in body:
        # ambiguous schema - use ref_a arbitrarily for testing
        user_id = body["ref_a"]

    # Convert to int if needed
    if isinstance(user_id, str):
        try:
            user_id = int(user_id)
        except ValueError:
            _add_contract_headers(response)
            return JSONResponse(
                status_code=404,
                content={"error": "user_not_found"},
                headers=response.headers,
            )

    # Look up user
    if user_id not in USERS:
        _add_contract_headers(response)
        return JSONResponse(
            status_code=404,
            content={"error": "user_not_found"},
            headers=response.headers,
        )

    # Success
    _execution_stats["successful_lookups"] += 1
    _add_contract_headers(response)
    return JSONResponse(
        status_code=200,
        content={"user": USERS[user_id]},
        headers=response.headers,
    )


@app.post("/admin/mutate")
def mutate_contract(req: MutateRequest, response: Response) -> dict:
    """Switch to a different contract."""
    try:
        contracts.set_active(req.to)
        _add_contract_headers(response)
        return {"status": "ok", "active": req.to}
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown contract: {req.to}")


@app.post("/admin/reset")
def reset_contract(response: Response) -> dict:
    """Reset to v1 contract."""
    contracts.set_active("v1")
    _add_contract_headers(response)
    return {"status": "ok", "active": "v1"}


@app.post("/admin/fault")
def set_fault(req: FaultRequest) -> dict:
    """Set or clear fault injection mode."""
    global _fault_mode
    _fault_mode = req.mode
    return {"status": "ok", "fault_mode": _fault_mode}


@app.get("/admin/stats")
def get_stats() -> dict:
    """Get execution statistics."""
    return _execution_stats


# =============================================================================
# Control Room Backend API & SSE Integration
# =============================================================================
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from driftshield.api.routes import create_api_router
from driftshield.api.sse import SSEBroadcaster
from driftshield.shield import Shield

_raw_cors = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://localhost:8000",
)
_cors_origins = [o.strip() for o in _raw_cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_broadcaster = SSEBroadcaster()
_shield = Shield(
    client=TestClient(app),
    on_event=_broadcaster.on_shield_event,
    enable_sentinel=False,
)
_api_router = create_api_router(_shield, _broadcaster)
app.include_router(_api_router, prefix="/api")

# Expose references on app.state
app.state.shield = _shield
app.state.broadcaster = _broadcaster

from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def _app_lifespan(app_instance: FastAPI):
    global _shield
    try:
        loop = asyncio.get_running_loop()
        _broadcaster.set_loop(loop)
    except Exception:
        pass
    if _shield.is_closed:
        _shield = Shield(
            client=TestClient(app),
            on_event=_broadcaster.on_shield_event,
            enable_sentinel=False,
        )
        app.state.shield = _shield
    yield
    if not _shield.is_closed:
        _shield.close()

app.router.lifespan_context = _app_lifespan
