"""Tests for interceptor and classifier."""

import pytest
import httpx
from fastapi.testclient import TestClient

from driftshield.healer.interceptor import call_tool
from driftshield.healer.classifier import classify
from driftshield.healer.registry import create_default_registry
from driftshield.mock_api.server import app
from driftshield.mock_api import contracts


@pytest.fixture
def client():
    """FastAPI test client for mock API."""
    # Reset to v1 before each test
    contracts.set_active("v1")
    # Clear any fault modes
    test_client = TestClient(app)
    test_client.post("/admin/fault", json={"mode": None})
    return test_client


@pytest.fixture
def registry():
    """Fresh registry on v1."""
    return create_default_registry()


def fetch_live_contract_factory(client):
    """Create a fetch_live_contract function for the classifier."""
    def fetch_live_contract():
        try:
            response = client.get("/schema")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    return fetch_live_contract


def test_drift_detected_when_api_schema_changes(client, registry):
    """Test (a): Mutate to v2_full and send old request -> drift."""
    # Mutate API to v2_full
    client.post("/admin/mutate", json={"to": "v2_full"})
    
    # Registry still on v1
    tool = registry.get("lookup_user")
    assert tool is not None
    
    # Try to call with v1 args (no header, wrong body structure)
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={},
    )
    
    # Should fail
    assert result["ok"] is False
    assert result["status"] in [400, 422]
    
    # Classify
    fetch_contract = fetch_live_contract_factory(client)
    classification = classify(result, tool, fetch_contract)
    
    # Should be drift
    assert classification["kind"] == "drift"
    assert classification["live_contract"] is not None
    assert classification["evidence"]["registry_hash"] != classification["evidence"]["live_hash"]
    assert classification["evidence"]["schema_differs"] or classification["evidence"]["headers_differ"]


def test_invalid_data_when_registry_matches_contract(client, registry):
    """Test (b): On v1, send wrong type -> invalid_data (registry matches live)."""
    # API and registry both on v1
    tool = registry.get("lookup_user")
    assert tool is not None
    
    # Send integer where schema expects string
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": 123},  # Wrong type
        extra_headers={},
    )
    
    # Should fail
    assert result["ok"] is False
    assert result["status"] == 422
    
    # Classify
    fetch_contract = fetch_live_contract_factory(client)
    classification = classify(result, tool, fetch_contract)
    
    # Should be invalid_data (registry hash matches live hash)
    assert classification["kind"] == "invalid_data"
    assert classification["evidence"]["registry_hash"] == classification["evidence"]["live_hash"]


def test_auth_error_on_expired_token(client, registry):
    """Test (c): Fault mode expired_token -> auth."""
    # Set fault mode
    client.post("/admin/fault", json={"mode": "expired_token"})
    
    tool = registry.get("lookup_user")
    assert tool is not None
    
    # Make request
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={},
    )
    
    # Should fail with 401
    assert result["ok"] is False
    assert result["status"] == 401
    
    # Classify
    fetch_contract = fetch_live_contract_factory(client)
    classification = classify(result, tool, fetch_contract)
    
    # Should be auth
    assert classification["kind"] == "auth"
    assert classification["evidence"]["status"] == 401


def test_network_error_on_server_down(client, registry):
    """Test (d): Fault mode server_down -> network."""
    # Set fault mode
    client.post("/admin/fault", json={"mode": "server_down"})
    
    tool = registry.get("lookup_user")
    assert tool is not None
    
    # Make request
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={},
    )
    
    # Should fail with 503
    assert result["ok"] is False
    assert result["status"] == 503
    
    # Classify
    fetch_contract = fetch_live_contract_factory(client)
    classification = classify(result, tool, fetch_contract)
    
    # Should be network
    assert classification["kind"] == "network"
    assert classification["evidence"]["status"] == 503


def test_network_error_on_connection_failure(registry):
    """Test (e): Closed port -> network with status None."""
    # Create client pointing to closed port
    closed_port_client = httpx.Client(base_url="http://localhost:9999")
    
    tool = registry.get("lookup_user")
    assert tool is not None
    
    # Try to make request to closed port
    result = call_tool(
        client=closed_port_client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={},
    )
    
    # Should capture network error
    assert result["ok"] is False
    assert result["status"] is None
    assert result["network_error"] is not None
    
    # Classify (no need to fetch contract)
    def fake_fetch():
        return None
    
    classification = classify(result, tool, fake_fetch)
    
    # Should be network
    assert classification["kind"] == "network"
    assert "network_error" in classification["evidence"]


def test_call_tool_redacts_header_values():
    """Test that call_tool redacts header values in request info."""
    client = TestClient(app)
    contracts.set_active("v1")
    
    registry = create_default_registry()
    tool = registry.get("lookup_user")
    
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={"X-Secret-Token": "super-secret-value"},
    )
    
    # Header names should be present but values redacted
    assert "X-Secret-Token" in result["request"]["headers"]
    assert result["request"]["headers"]["X-Secret-Token"] == "<redacted>"


def test_call_tool_tracks_elapsed_time(client, registry):
    """Test that call_tool tracks elapsed time."""
    tool = registry.get("lookup_user")
    
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={},
    )
    
    # Should have elapsed time
    assert "elapsed_seconds" in result
    assert result["elapsed_seconds"] >= 0
    assert result["elapsed_seconds"] < 5.0  # Should be fast


def test_call_tool_successful_request(client, registry):
    """Test that call_tool handles successful requests."""
    tool = registry.get("lookup_user")
    
    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={},
    )
    
    # Should succeed
    assert result["ok"] is True
    assert result["status"] == 200
    assert result["body"] is not None
    assert result["body"]["user"]["id"] == 123
    assert result["network_error"] is None


def test_classifier_unknown_status(registry):
    """Test classifier returns unknown for unexpected status codes."""
    tool = registry.get("lookup_user")
    
    # Create a result with unexpected status
    result = {
        "ok": False,
        "status": 418,  # I'm a teapot
        "body": {"error": "teapot"},
        "headers": {},
        "request": {},
        "elapsed_seconds": 0.1,
        "network_error": None,
    }
    
    def fake_fetch():
        return None
    
    classification = classify(result, tool, fake_fetch)
    
    assert classification["kind"] == "unknown"
    assert classification["evidence"]["status"] == 418
