import threading
"""Tests for DriftShield Backend API and SSE Integration."""

import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from driftshield.api.server import create_app
from driftshield.api.sse import SSEBroadcaster
from driftshield.mock_api import contracts
from driftshield.mock_api.server import app as mock_server_app
from driftshield.shield import Shield


@pytest.fixture
def clean_api():
    """Reset mock API contracts before each test."""
    contracts.set_active("v1")
    client = TestClient(mock_server_app)
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/reset")
    return client


@pytest.fixture
def test_app(clean_api):
    """Create test application instance using clean_api client."""
    broadcaster = SSEBroadcaster(heartbeat_interval=0.05, queue_maxsize=10)
    shield = Shield(client=clean_api, on_event=broadcaster.on_shield_event)
    app = create_app(shield=shield, broadcaster=broadcaster)
    return app


@pytest.fixture
def client(test_app):
    """FastAPI TestClient for the test application."""
    return TestClient(test_app)


def test_health_endpoint(client):
    """Test: GET /api/health returns 200 with service status."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "driftshield"
    assert data["shield_closed"] is False


def test_status_endpoint(client):
    """Test: GET /api/status returns Shield, Sentinel, registry, and contract status."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["shield"]["status"] == "active"
    assert data["shield"]["sentinel_enabled"] is False
    assert "lookup_user" in data["registry"]["tools"]
    assert data["registry"]["versions"]["lookup_user"] == 1
    assert data["upstream_contract"]["schema_version"] == "v1"


def test_demo_execution_success(client):
    """Test: POST /api/demo/execute executes approved tool and returns business result."""
    resp = client.post(
        "/api/demo/execute",
        json={"tool_name": "lookup_user", "args": {"user_id": "123"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["result_body"]["user"]["id"] == 123
    assert data["attempts"] == 1


def test_demo_execution_reactive_healing(client, clean_api):
    """Test: POST /api/demo/execute reactively heals through the API endpoint."""
    # Mutate upstream contract to rename_id
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    resp = client.post(
        "/api/demo/execute",
        json={"tool_name": "lookup_user", "args": {"user_id": "123"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healed"
    assert data["result_body"]["user"]["id"] == 123
    assert data["registry_version_after"] > data["registry_version_before"]


def test_safe_stop_response_propagation(client, clean_api):
    """Test: Ambiguous drift safe-stop propagates cleanly as a structured 200 response."""
    clean_api.post("/admin/mutate", json={"to": "ambiguous"})

    resp = client.post(
        "/api/demo/execute",
        json={"tool_name": "lookup_user", "args": {"user_id": "123"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "safe_stop"
    assert data["result_body"] is None
    assert "ambiguous" in data["reason"].lower()


def test_disallowed_tool_rejected(client):
    """Test: Unapproved tools are rejected with 400 Bad Request."""
    resp = client.post(
        "/api/demo/execute",
        json={"tool_name": "arbitrary_tool_call", "args": {"foo": "bar"}},
    )
    assert resp.status_code == 400
    assert "disallowed tool" in resp.json()["detail"].lower()


def test_invalid_request_body_rejected(client):
    """Test: Malformed request payload returns 422 Unprocessable Entity."""
    resp = client.post(
        "/api/demo/execute",
        json={"tool_name": "lookup_user", "args": "not_a_dictionary"},
    )
    assert resp.status_code == 422


def test_sse_event_delivery(test_app, client):
    """Test: SSE endpoint streams valid formatted event messages."""
    broadcaster = test_app.state.broadcaster

    def emit_events():
        import time
        for _ in range(100):
            if broadcaster.subscriber_count > 0:
                break
            time.sleep(0.01)
        broadcaster.on_shield_event("intercepted", {"tool_name": "lookup_user", "status": 200})
        broadcaster.on_shield_event("success", {"tool_name": "lookup_user", "status": "ok"})

    t = threading.Thread(target=emit_events)
    t.start()

    with client.stream("GET", "/api/events?limit=2") as stream:
        lines = list(stream.iter_lines())

    t.join(timeout=2.0)

    assert "event: intercepted" in lines
    assert "event: success" in lines

    # Verify JSON structure
    data_lines = [line for line in lines if line.startswith("data: ")]
    assert len(data_lines) >= 2
    for line in data_lines:
        payload = json.loads(line[len("data: "):])
        assert "tool_name" in payload


def test_multiple_sse_subscribers_independent_copies():
    """Test: Multiple subscribers receive separate, independent copies of events."""
    async def run_test():
        broadcaster = SSEBroadcaster(queue_maxsize=10)
        q1 = await broadcaster.connect()
        q2 = await broadcaster.connect()
        assert broadcaster.subscriber_count == 2

        broadcaster.on_shield_event("drift_detected", {"old": "v1", "new": "v2"})

        ev1 = await q1.get()
        ev2 = await q2.get()

        assert ev1 == ev2 == {"event": "drift_detected", "data": {"old": "v1", "new": "v2"}}

        await broadcaster.disconnect(q1)
        await broadcaster.disconnect(q2)
        assert broadcaster.subscriber_count == 0

    asyncio.run(run_test())


def test_client_disconnection_and_cleanup():
    """Test: Disconnecting clients removes them from subscriber registry."""
    async def run_test():
        broadcaster = SSEBroadcaster(queue_maxsize=5)
        q = await broadcaster.connect()
        assert broadcaster.subscriber_count == 1

        await broadcaster.disconnect(q)
        assert broadcaster.subscriber_count == 0

    asyncio.run(run_test())


def test_sse_heartbeats(test_app, client):
    """Test: SSE stream yields periodic heartbeat comments on idle connections."""
    # When limit=1 and no events are queued, heartbeat timeout fires
    with client.stream("GET", "/api/events?limit=1") as stream:
        lines = list(stream.iter_lines())

    assert ": heartbeat" in lines


def test_bounded_queue_overflow_drops_oldest():
    """Test: Slow-consumer queue overflow drops the oldest events, keeping queue bounded."""
    async def run_test():
        broadcaster = SSEBroadcaster(queue_maxsize=2)
        q = await broadcaster.connect()

        # Emit 4 events
        for i in range(4):
            broadcaster.on_shield_event("step", {"num": i})

        # Queue should contain only the latest 2 events (2 and 3)
        items = []
        while not q.empty():
            items.append(q.get_nowait()["data"]["num"])

        assert items == [2, 3]
        await broadcaster.disconnect(q)

    asyncio.run(run_test())


def test_application_lifecycle_shutdown(clean_api):
    """Test: Application shutdown properly closes Shield and resources."""
    app = create_app(client=clean_api)
    with TestClient(app) as tc:
        resp = tc.get("/api/health")
        assert resp.status_code == 200
        assert not app.state.shield.is_closed

    # On exiting TestClient context, lifespan shuts down owned shield
    assert app.state.shield.is_closed


def test_cors_preflight(client):
    """Test: OPTIONS preflight request respects configured CORS origins."""
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in resp.headers.get("access-control-allow-methods", "")


def test_demo_execution_with_parameters_and_aliases(client, clean_api):
    """Test: POST /api/demo/execute accepts 'parameters' (frontend/OpenAPI format) and returns aliases."""
    payload = {
        "tool_name": "lookup_user",
        "parameters": {"user_id": "123"},
    }
    resp = client.post("/api/demo/execute", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Verify status and success boolean
    assert data["status"] == "ok"
    assert data["success"] is True

    # Verify both camelCase and snake_case aliases are present
    assert data["result"] == data["result_body"]
    assert data["result"]["user"]["name"] == "Asha Rao"
    assert data["registryBefore"] == data["registry_version_before"]
    assert data["registryAfter"] == data["registry_version_after"]


def test_status_endpoint_flat_and_nested_keys(client):
    """Test: GET /api/status exposes both top-level and structured nested keys."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys for simple clients
    assert data["status"] == "active"
    assert "lookup_user" in data["registered_tools"]
    assert isinstance(data["registry_versions"], dict)
    assert data["sentinel_enabled"] is False

    # Structured nested objects
    assert data["shield"]["status"] == "active"
    assert "lookup_user" in data["registry"]["tools"]


def test_sse_broadcaster_event_safety_without_loop():
    """Test: SSEBroadcaster handles events safely before loop starts or after loop closes."""
    broadcaster = SSEBroadcaster(queue_maxsize=10)

    # 1. Event before any subscriber or loop
    broadcaster.on_shield_event("pre_startup", {"key": "val"})

    # 2. Add subscriber queue manually
    loop = asyncio.new_event_loop()
    try:
        q = loop.run_until_complete(broadcaster.connect())
        assert broadcaster.subscriber_count == 1

        # Emit event while loop is NOT running (safe fallback)
        broadcaster.on_shield_event("offline_event", {"n": 1})
        item = loop.run_until_complete(q.get())
        assert item["event"] == "offline_event"
        assert item["data"] == {"n": 1}
    finally:
        loop.close()

    # 3. Emit event after loop has closed (must not raise RuntimeError)
    broadcaster.on_shield_event("post_shutdown", {"n": 2})
