"""Integration tests for the canonical DriftShield server (driftshield.mock_api.server:app).

Verifies the unified ASGI application hosting both mock upstream tool endpoints
and Control Room backend APIs on a single port.
"""

import json
import pytest
from starlette.testclient import TestClient

from driftshield.mock_api.server import app as canonical_app
from driftshield.mock_api import contracts


@pytest.fixture
def clean_canonical():
    """Reset canonical server state and contract to v1."""
    contracts.set_active("v1")
    client = TestClient(canonical_app)
    client.post("/admin/reset")
    client.post("/admin/fault", json={"mode": None})
    return client


def test_canonical_health_endpoint(clean_canonical):
    """Test: /api/health on canonical ASGI application."""
    resp = clean_canonical.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "driftshield"
    assert data["shield_closed"] is False


def test_canonical_status_endpoint(clean_canonical):
    """Test: /api/status on canonical ASGI application."""
    resp = clean_canonical.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "lookup_user" in data["registered_tools"]
    assert "lookup_user" in data["registry"]["tools"]
    assert data["shield"]["status"] == "active"


def test_canonical_demo_execution_and_healing(clean_canonical):
    """Test: /api/demo/execute triggers reactive healing on mutated schema."""
    clean_canonical.post("/admin/mutate", json={"to": "rename_id"})

    resp = clean_canonical.post(
        "/api/demo/execute",
        json={"tool_name": "lookup_user", "parameters": {"user_id": "123"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healed"
    assert data["success"] is True
    assert data["result"]["user"]["name"] == "Asha Rao"
    assert data["registryBefore"] == 1
    assert data["registryAfter"] == 2


def test_canonical_disallowed_tool(clean_canonical):
    """Test: Disallowed tools are rejected with 400 on canonical app."""
    resp = clean_canonical.post(
        "/api/demo/execute",
        json={"tool_name": "arbitrary_tool", "parameters": {}},
    )
    assert resp.status_code == 400
    assert "Disallowed tool" in resp.json()["detail"]


def test_canonical_repeated_startup_and_shutdown():
    """Test: Repeated ASGI lifespan startup and shutdown cycles on canonical app."""
    for cycle in range(2):
        with TestClient(canonical_app) as client:
            resp = client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["shield_closed"] is False


def test_canonical_sse_stream_receives_heartbeats(clean_canonical):
    """Test: /api/events SSE stream works on canonical ASGI application."""
    with clean_canonical.stream("GET", "/api/events?limit=1") as stream:
        lines = list(stream.iter_lines())
        assert any(line.startswith("event:") or line.startswith(":") for line in lines)
