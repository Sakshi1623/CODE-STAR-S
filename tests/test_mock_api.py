"""Tests for mock API contracts and server."""

import pytest
from fastapi.testclient import TestClient

from driftshield.mock_api import contracts
from driftshield.mock_api.server import app


@pytest.fixture
def client():
    """FastAPI test client."""
    # Reset to v1 before each test
    contracts.set_active("v1")
    return TestClient(app)


def test_v1_accepts_user_id(client):
    """Test 1: v1 accepts {"user_id": "123"} and returns 200."""
    response = client.post("/users/lookup", json={"user_id": "123"})
    assert response.status_code == 200
    assert response.json() == {"user": {"id": 123, "name": "Asha Rao"}}


def test_v2_full_migration(client):
    """Test 2: After mutating to v2_full, old request fails and new format succeeds."""
    # Mutate to v2_full
    client.post("/admin/mutate", json={"to": "v2_full"})
    
    # Old request should fail (missing header and wrong body format)
    response = client.post("/users/lookup", json={"user_id": "123"})
    assert response.status_code in [400, 422]
    
    # New format with header should succeed
    response = client.post(
        "/users/lookup",
        json={"target": {"id": 123}},
        headers={"X-Tenant-Token": "test-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"user": {"id": 123, "name": "Asha Rao"}}


def test_hash_stability(client):
    """Test 3: Same contract gives same hash; different contracts differ."""
    v1_contract = contracts.CONTRACTS["v1"]
    v2_contract = contracts.CONTRACTS["v2_full"]
    
    # Recompute hash for v1 to verify stability
    v1_without_hash = {k: v for k, v in v1_contract.items() if k != "content_hash"}
    recomputed_hash = contracts.compute_hash(v1_without_hash)
    assert recomputed_hash == v1_contract["content_hash"]
    
    # v1 and v2_full should have different hashes
    assert v1_contract["content_hash"] != v2_contract["content_hash"]


def test_hash_parity_with_response_header(client):
    """Test 4: X-Contract-Hash response header matches GET /schema hash."""
    schema_response = client.get("/schema")
    schema_hash = schema_response.json()["content_hash"]
    header_hash = schema_response.headers["X-Contract-Hash"]
    assert schema_hash == header_hash
    
    # Also check on /users/lookup
    lookup_response = client.post("/users/lookup", json={"user_id": "123"})
    lookup_hash = lookup_response.headers["X-Contract-Hash"]
    assert lookup_hash == schema_hash


def test_all_contracts_valid_requests(client):
    """Test 5: For every contract, valid request returns 200, invalid returns 4xx."""
    test_cases = [
        ("v1", {"user_id": "123"}, {}, True),
        ("v1", {"user_id": 999}, {}, False),  # Wrong type
        
        ("v2_full", {"target": {"id": 123}}, {"X-Tenant-Token": "token"}, True),
        ("v2_full", {"target": {"id": 123}}, {}, False),  # Missing header
        
        ("rename_id", {"id": "124"}, {}, True),
        ("rename_id", {"user_id": "124"}, {}, False),  # Wrong field name
        
        ("type_int", {"user_id": 123}, {}, True),
        ("type_int", {"user_id": "123"}, {}, False),  # Wrong type
        
        ("nest_target", {"target": {"id": "123"}}, {}, True),
        ("nest_target", {"user_id": "123"}, {}, False),  # Not nested
        
        ("header_tenant", {"user_id": "123"}, {"X-Tenant-Token": "token"}, True),
        ("header_tenant", {"user_id": "123"}, {}, False),  # Missing header
        
        ("combo", {"target": {"id": 124}}, {"X-Tenant-Token": "token"}, True),
        ("combo", {"target": {"id": "124"}}, {"X-Tenant-Token": "token"}, False),  # Wrong type
        
        ("header_billing", {"user_id": "123"}, {"X-Billing-Region": "us-east"}, True),
        ("header_billing", {"user_id": "123"}, {}, False),  # Missing header
        
        ("ambiguous", {"ref_a": "123", "ref_b": "456"}, {}, True),
        ("ambiguous", {"user_id": "123"}, {}, False),  # Wrong fields
        
        ("rename_uid", {"uid": "123"}, {}, True),
        ("rename_uid", {"user_id": "123"}, {}, False),  # Wrong field name
        
        ("nest_deep", {"data": {"user": {"id": "123"}}}, {}, True),
        ("nest_deep", {"user_id": "123"}, {}, False),  # Not nested
        
        ("header_rename", {"id": "123"}, {"X-Tenant-Token": "token"}, True),
        ("header_rename", {"id": "123"}, {}, False),  # Missing header
        
        ("combo_billing", {"target": {"id": 123}}, {"X-Billing-Region": "us-east"}, True),
        ("combo_billing", {"target": {"id": 123}}, {}, False),  # Missing header
    ]
    
    for contract_name, body, headers, should_succeed in test_cases:
        client.post("/admin/mutate", json={"to": contract_name})
        response = client.post("/users/lookup", json=body, headers=headers)
        
        if should_succeed:
            assert response.status_code == 200, \
                f"{contract_name} with {body} and {headers} should succeed but got {response.status_code}"
        else:
            assert response.status_code >= 400, \
                f"{contract_name} with {body} and {headers} should fail but got {response.status_code}"


def test_fault_modes(client):
    """Test 6: Fault modes return 401 and 503 and clear correctly."""
    # Set expired_token fault
    client.post("/admin/fault", json={"mode": "expired_token"})
    response = client.post("/users/lookup", json={"user_id": "123"})
    assert response.status_code == 401
    assert response.json() == {"error": "token_expired"}
    
    # Set server_down fault
    client.post("/admin/fault", json={"mode": "server_down"})
    response = client.post("/users/lookup", json={"user_id": "123"})
    assert response.status_code == 503
    assert response.json() == {"error": "unavailable"}
    
    # Clear fault
    client.post("/admin/fault", json={"mode": None})
    response = client.post("/users/lookup", json={"user_id": "123"})
    assert response.status_code == 200
    assert response.json() == {"user": {"id": 123, "name": "Asha Rao"}}


def test_execution_stats(client):
    """Test that successful lookups are counted."""
    stats_before = client.get("/admin/stats").json()
    
    client.post("/users/lookup", json={"user_id": "123"})
    client.post("/users/lookup", json={"user_id": "124"})
    
    stats_after = client.get("/admin/stats").json()
    assert stats_after["successful_lookups"] == stats_before["successful_lookups"] + 2


def test_user_differentiation(client):
    """Test that different user IDs return different users."""
    response_123 = client.post("/users/lookup", json={"user_id": "123"})
    response_124 = client.post("/users/lookup", json={"user_id": "124"})
    
    assert response_123.json()["user"]["name"] == "Asha Rao"
    assert response_124.json()["user"]["name"] == "Ravi Iyer"
    
    # Unknown user returns 404
    response_999 = client.post("/users/lookup", json={"user_id": "999"})
    assert response_999.status_code == 404
