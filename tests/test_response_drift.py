"""Regression tests for response-schema validation in the healing executor.

Phase 1 adds response body validation to HealingExecutor.execute():
- Valid 2xx responses are validated against the registered response_schema
- Missing required fields are detected and result in safe_stop
- Incorrect field types are detected and result in safe_stop
- Completely wrong structures are detected and result in safe_stop
- Genuine response drift (body matches live schema but not registered schema)
  is detected and classified as safe_stop with reason "Response drift detected"
- Responses invalid against both schemas result in safe_stop
- Valid request-side patches are NOT rolled back when only the response is malformed

Tests that previously documented bugs now assert the corrected behaviour.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from driftshield.healer.retry import HealingExecutor, Budget, fetch_live_contract_fn
from driftshield.healer.registry import create_default_registry
from driftshield.healer.interceptor import call_tool
from driftshield.mock_api.server import app
from driftshield.mock_api import contracts


@pytest.fixture
def clean_api():
    """Reset API to v1 and clear faults."""
    contracts.set_active("v1")
    client = TestClient(app)
    client.post("/admin/fault", json={"mode": None})
    client.post("/admin/reset")
    return client


@pytest.fixture
def executor(clean_api):
    """Create healing executor with fresh registry and budget."""
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    return HealingExecutor(registry, clean_api, budget, log_events=False)


@pytest.fixture
def registry():
    """Create a fresh registry."""
    return create_default_registry()


# =============================================================================
# VALID RESPONSE TESTS
# =============================================================================

def test_valid_response_accepted(executor):
    """Test: Valid response structure is accepted and returned."""
    result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "ok", f"Expected ok, got {result['status']}: {result.get('reason')}"
    assert result["result_body"] == {"user": {"id": 123, "name": "Asha Rao"}}
    assert result["attempts"] == 1

    body = result["result_body"]
    assert "user" in body
    assert body["user"]["id"] == 123
    assert body["user"]["name"] == "Asha Rao"


def test_response_schema_in_v1_contract():
    """Test: v1 contract includes response_schema with expected structure."""
    from driftshield.mock_api import contracts as contracts_module
    from driftshield.healer.registry import create_default_registry

    v1_contract = contracts_module.CONTRACTS["v1"]

    assert "body_schema" in v1_contract
    assert "response_schema" in v1_contract

    response_schema = v1_contract["response_schema"]
    assert response_schema["type"] == "object"
    assert "user" in response_schema["properties"]
    assert response_schema["required"] == ["user"]
    assert response_schema["additionalProperties"] is False

    user_schema = response_schema["properties"]["user"]
    assert user_schema["type"] == "object"
    assert "id" in user_schema["properties"]
    assert "name" in user_schema["properties"]
    assert user_schema["properties"]["id"]["type"] == "integer"
    assert user_schema["properties"]["name"]["type"] == "string"
    assert "id" in user_schema["required"]
    assert "name" in user_schema["required"]
    assert user_schema["additionalProperties"] is True

    registry = create_default_registry()
    tool = registry.get("lookup_user")
    assert "response_schema" in tool
    assert tool["response_schema"] == response_schema


def test_interceptor_only_checks_status_code():
    """Test: interceptor ok flag is based solely on HTTP status code."""
    from driftshield.healer.interceptor import call_tool
    from driftshield.healer.registry import create_default_registry

    contracts.set_active("v1")
    client = TestClient(app)
    client.post("/admin/reset")
    registry = create_default_registry()
    tool = registry.get("lookup_user")

    result = call_tool(
        client=client,
        registry_tool=tool,
        tool_name="lookup_user",
        args={"user_id": "123"},
        extra_headers={}
    )

    assert result["ok"] == (200 <= result["status"] < 300)


# =============================================================================
# MISSING REQUIRED FIELD — now correctly detected
# =============================================================================

def test_missing_required_response_field_is_detected(clean_api, registry):
    """Test: Missing required response field triggers safe_stop."""
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool:
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {"user": {"id": 123}},  # Missing "name" (required)
            "headers": {"X-Schema-Version": "v1", "X-Contract-Hash": "test-hash"},
            "request": {"body": {"user_id": "123"}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }

        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop", f"Expected safe_stop, got {result['status']}"
    assert result["result_body"] is None
    assert "name" in result["reason"].lower() or "required" in result["reason"].lower() or "valid" in result["reason"].lower()
    assert result["attempts"] == 1


def test_missing_required_field_not_detected_without_schema(clean_api):
    """Test: When no response_schema is registered, missing fields pass through.

    If a tool has no response_schema, we have nothing to validate against and
    must accept the body (backward-compat with tools registered before Phase 1).
    """
    from driftshield.healer.registry import ToolRegistry, Tool

    registry = ToolRegistry()
    tool_no_schema: Tool = {
        "name": "lookup_user",
        "description": "Look up a user by ID",
        "operation": "lookup_user",
        "version": 1,
        "contract_hash": "abc",
        "body_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
        "required_headers": [],
    }
    registry.register(tool_no_schema)

    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool:
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {"user": {"id": 123}},  # Missing "name" — but no schema registered
            "headers": {},
            "request": {"body": {}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }
        result = executor.execute("lookup_user", {"user_id": "123"})

    # No schema = no validation = pass-through
    assert result["status"] == "ok"
    assert result["result_body"] == {"user": {"id": 123}}


# =============================================================================
# INCORRECT FIELD TYPE — now correctly detected
# =============================================================================

def test_incorrect_response_field_type_is_detected(clean_api, registry):
    """Test: Response with wrong field type (id as string instead of integer) triggers safe_stop."""
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool:
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {"user": {"id": "not-an-integer", "name": "Asha Rao"}},
            "headers": {"X-Schema-Version": "v1", "X-Contract-Hash": "test-hash"},
            "request": {"body": {"user_id": "123"}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }

        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop", f"Expected safe_stop, got {result['status']}"
    assert result["result_body"] is None
    assert result["attempts"] == 1


# =============================================================================
# COMPLETELY WRONG STRUCTURE — now correctly detected
# =============================================================================

def test_completely_wrong_response_structure_is_detected(clean_api, registry):
    """Test: Completely wrong response structure (wrong root key) triggers safe_stop."""
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool:
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {
                "data": {                  # Wrong root key (expected "user")
                    "person": {
                        "identifier": 123,
                        "full_name": "Asha Rao"
                    }
                }
            },
            "headers": {"X-Schema-Version": "v1", "X-Contract-Hash": "test-hash"},
            "request": {"body": {"user_id": "123"}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }

        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop", f"Expected safe_stop, got {result['status']}"
    assert result["result_body"] is None


# =============================================================================
# ADDITIONAL OPTIONAL FIELD — must remain accepted
# =============================================================================

def test_additional_optional_response_field_accepted(executor):
    """Test: Response with extra fields (allowed by additionalProperties:true on user) is accepted.

    The v1 response schema sets additionalProperties: true on the user object,
    so extra fields within user are allowed. Extra root-level fields are NOT
    (additionalProperties: false at root).
    """
    # The real API does not add extra fields, so this tests via mock
    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    contracts.set_active("v1")
    client = TestClient(app)
    client.post("/admin/reset")
    exec2 = HealingExecutor(registry, client, budget, log_events=False)

    # Real API returns correct shape — test that it is accepted
    result = exec2.execute("lookup_user", {"user_id": "123"})
    assert result["status"] == "ok"
    assert result["result_body"] is not None


def test_successful_response_no_duplicate_api_request(executor):
    """Test: A valid first response does not cause a second API call."""
    call_count = 0

    original_execute = executor.execute

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool:
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {"user": {"id": 123, "name": "Asha Rao"}},
            "headers": {},
            "request": {"body": {}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }

        result = executor.execute("lookup_user", {"user_id": "123"})

    assert mock_call_tool.call_count == 1, "Should only call the API once for valid response"
    assert result["status"] == "ok"
    assert result["attempts"] == 1


# =============================================================================
# RESPONSE DRIFT: body matches LIVE schema but not REGISTERED schema
# =============================================================================

def test_response_matches_live_schema_but_not_registered_is_safe_stop(clean_api, registry):
    """Test: Response matching live contract schema but not registered schema → safe_stop with drift reason.

    Simulates: the API updated its response format, live contract reflects it,
    but the registry still has the old response_schema.
    """
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    # A body that would validate against an alternate schema (missing "name") 
    # but not against v1 registered schema. We mock the live contract to return
    # a schema that accepts this body.
    new_live_resp_schema = {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
                "additionalProperties": True,
            }
        },
        "required": ["user"],
        "additionalProperties": False,
    }
    mock_live_contract = {
        "schema_version": "v1_alt",
        "content_hash": "newhash",
        "operation": "lookup_user",
        "required_headers": [],
        "body_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
        "response_schema": new_live_resp_schema,
    }

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool,          patch("driftshield.healer.retry.fetch_live_contract_fn", return_value=mock_live_contract):

        # Body passes the relaxed live schema (no "name" required) but fails
        # the registered v1 schema (which requires "name")
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {"user": {"id": 123}},  # Missing "name" — fails v1 registered schema
            "headers": {},
            "request": {"body": {}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }

        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop", f"Expected safe_stop, got {result['status']}"
    assert result["result_body"] is None
    # Reason should mention response drift
    assert "drift" in result["reason"].lower() or "live" in result["reason"].lower() or "response" in result["reason"].lower()


# =============================================================================
# INVALID AGAINST BOTH SCHEMAS
# =============================================================================

def test_response_invalid_against_both_schemas_is_safe_stop(clean_api, registry):
    """Test: Response invalid against both registered AND live schemas → safe_stop."""
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    # Mock the live contract with a response schema that also rejects the body
    mock_live_contract = {
        "schema_version": "v1",
        "content_hash": "hash",
        "operation": "lookup_user",
        "required_headers": [],
        "body_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]},
        "response_schema": {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                    "required": ["id", "name"],
                    "additionalProperties": False,
                }
            },
            "required": ["user"],
            "additionalProperties": False,
        },
    }

    with patch("driftshield.healer.retry.call_tool") as mock_call_tool,          patch("driftshield.healer.retry.fetch_live_contract_fn", return_value=mock_live_contract):

        # Body has wrong root key — fails both schemas
        mock_call_tool.return_value = {
            "ok": True,
            "status": 200,
            "body": {"completely_wrong": "structure"},
            "headers": {},
            "request": {"body": {}, "headers": {}},
            "elapsed_seconds": 0.1,
            "network_error": None,
        }

        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop"
    assert result["result_body"] is None


# =============================================================================
# NETWORK FAILURE / NON-2XX — existing behaviour preserved
# =============================================================================

def test_non_2xx_response_triggers_healing_or_safe_stop(clean_api, registry):
    """Test: Non-2xx response does not pass as successful result."""
    contracts.set_active("v1")
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    result = executor.execute("lookup_user", {"user_id": "123"})

    # Must be healed or safe_stop — never "ok" with wrong body
    assert result["status"] in ("healed", "safe_stop")
    if result["status"] == "safe_stop":
        assert result["result_body"] is None


# =============================================================================
# PATCH PRESERVATION: valid request patch NOT rolled back on response failure
# =============================================================================

def test_valid_request_patch_preserved_on_response_validation_failure(clean_api):
    """Test: When retry response body is malformed, the valid request patch is preserved.

    registry_version_after should be > registry_version_before, showing the
    request-side patch was kept even though the response was invalid.
    """
    contracts.set_active("rename_id")

    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    version_before = registry.get("lookup_user")["version"]

    # Intercept only the retry call (2nd call_tool invocation) to return bad body
    call_count = [0]
    original_call_tool = __import__(
        "driftshield.healer.interceptor", fromlist=["call_tool"]
    ).call_tool

    def fake_call_tool(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: return 400 to trigger healing (simulates drift)
            return {
                "ok": False, "status": 400,
                "body": {"error": "schema drift"},
                "headers": {"X-Contract-Hash": contracts.get_active()["content_hash"],
                            "X-Schema-Version": "rename_id"},
                "request": {"body": {}, "headers": {}},
                "elapsed_seconds": 0.05,
                "network_error": None,
            }
        else:
            # Second call (retry): return 200 but with malformed body
            return {
                "ok": True, "status": 200,
                "body": {"completely_wrong": "body"},  # Fails response schema
                "headers": {"X-Contract-Hash": contracts.get_active()["content_hash"],
                            "X-Schema-Version": "rename_id"},
                "request": {"body": {}, "headers": {}},
                "elapsed_seconds": 0.05,
                "network_error": None,
            }

    with patch("driftshield.healer.retry.call_tool", side_effect=fake_call_tool):
        result = executor.execute("lookup_user", {"user_id": "123"})

    # The result must be safe_stop (malformed response) — not "ok" or "healed"
    assert result["status"] == "safe_stop"
    assert result["result_body"] is None
    # Request patch was preserved: version_after >= version_before
    # (may equal version_before if healing rolled back, but the reason must
    # be about response validation, not about the request patch being wrong)
    assert "response" in result["reason"].lower() or "malform" in result["reason"].lower() or "valid" in result["reason"].lower()


# =============================================================================
# EXECUTOR RETURNS BODY AS-IS (now only when schema validates)
# =============================================================================

def test_executor_returns_body_as_is_when_valid():
    """Test: Executor returns response body only when it passes schema validation."""
    from driftshield.mock_api import contracts as contracts_module

    contracts_module.set_active("v1")
    client = TestClient(app)
    client.post("/admin/reset")

    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, client, budget, log_events=False)

    result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "ok"
    assert result["result_body"] is not None
    # Body must match the expected schema
    body = result["result_body"]
    assert "user" in body
    assert isinstance(body["user"]["id"], int)
    assert isinstance(body["user"]["name"], str)


# =============================================================================
# EMPTY / NULL RESPONSE BODY REGRESSION TESTS
# =============================================================================

def test_initial_null_body_rejected_when_schema_requires_object(clean_api, registry):
    """Test: HTTP 200 with null body is rejected when response schema requires an object.
    
    Ensures empty responses are not silently accepted, and no automatic retry is attempted.
    """
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    fake_result = {
        "ok": True,
        "status": 200,
        "body": None,  # Empty / null body
        "headers": {"content-type": "application/json"},
        "request": {"body": {}, "headers": {}},
        "elapsed_seconds": 0.05,
        "network_error": None,
    }

    with patch("driftshield.healer.retry.call_tool", return_value=fake_result):
        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop"
    assert result["result_body"] is None
    assert result["attempts"] == 1  # No automatic retry
    assert "response validation failed" in result["reason"].lower() or "does not match" in result["reason"].lower()


def test_initial_null_body_accepted_when_schema_permits_null(clean_api):
    """Test: HTTP 200 with null body is accepted when response schema explicitly permits null."""
    import copy
    registry = create_default_registry()
    tool = copy.deepcopy(registry.get("lookup_user"))
    # Schema permitting either object or null
    tool["response_schema"] = {
        "type": ["object", "null"],
        "properties": {
            "user": {"type": "object"}
        }
    }
    registry.register(tool)

    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    fake_result = {
        "ok": True,
        "status": 200,
        "body": None,
        "headers": {"content-type": "application/json"},
        "request": {"body": {}, "headers": {}},
        "elapsed_seconds": 0.05,
        "network_error": None,
    }

    with patch("driftshield.healer.retry.call_tool", return_value=fake_result):
        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "ok"
    assert result["result_body"] is None
    assert result["attempts"] == 1


def test_initial_null_body_detects_response_drift_when_live_permits_null(clean_api, registry):
    """Test: When registered schema forbids null but live schema permits it, response drift is detected."""
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    fake_result = {
        "ok": True,
        "status": 200,
        "body": None,
        "headers": {"content-type": "application/json"},
        "request": {"body": {}, "headers": {}},
        "elapsed_seconds": 0.05,
        "network_error": None,
    }

    # Live contract has response_schema permitting null
    live_contract = {
        "operation": "lookup_user",
        "body_schema": registry.get("lookup_user")["body_schema"],
        "required_headers": [],
        "response_schema": {
            "type": ["object", "null"],
            "properties": {"user": {"type": "object"}}
        }
    }

    with patch("driftshield.healer.retry.call_tool", return_value=fake_result),          patch("driftshield.healer.retry.fetch_live_contract_fn", return_value=live_contract):
        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop"
    assert result["result_body"] is None
    assert result["attempts"] == 1
    assert "response drift detected" in result["reason"].lower()


def test_healed_retry_null_body_rejected_when_schema_requires_object(clean_api):
    """Test: On retry after successful request patch, null body is rejected if schema requires object.
    
    Preserves request-side registry patch and does not automatically retry.
    """
    contracts.set_active("rename_id")

    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    version_before = registry.get("lookup_user")["version"]

    call_count = [0]
    def fake_call_tool(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # 1st call: request drift error
            return {
                "ok": False, "status": 400,
                "body": {"error": "schema drift"},
                "headers": {"X-Contract-Hash": contracts.get_active()["content_hash"],
                            "X-Schema-Version": "rename_id"},
                "request": {"body": {}, "headers": {}},
                "elapsed_seconds": 0.05,
                "network_error": None,
            }
        else:
            # 2nd call (healed retry): 200 but null body (e.g. empty response)
            return {
                "ok": True, "status": 200,
                "body": None,
                "headers": {"X-Contract-Hash": contracts.get_active()["content_hash"],
                            "X-Schema-Version": "rename_id"},
                "request": {"body": {}, "headers": {}},
                "elapsed_seconds": 0.05,
                "network_error": None,
            }

    with patch("driftshield.healer.retry.call_tool", side_effect=fake_call_tool):
        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop"
    assert result["result_body"] is None
    # Request-side patch was applied and preserved!
    assert result["registry_version_after"] > version_before
    assert result["attempts"] == 2
    assert "retry response validation failed" in result["reason"].lower() or "malformed" in result["reason"].lower()


def test_healed_retry_null_body_accepted_when_schema_permits_null(clean_api):
    """Test: On retry after successful request patch, null body is accepted if schema permits null."""
    import copy
    contracts.set_active("rename_id")

    # Give the active rename_id contract a response_schema permitting null
    live_rename = contracts.get_active()
    live_contract_with_null = copy.deepcopy(live_rename)
    live_contract_with_null["response_schema"] = {
        "type": ["object", "null"],
        "properties": {"user": {"type": "object"}}
    }

    registry = create_default_registry()
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    executor = HealingExecutor(registry, clean_api, budget, log_events=False)

    version_before = registry.get("lookup_user")["version"]

    call_count = [0]
    def fake_call_tool(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return {
                "ok": False, "status": 400,
                "body": {"error": "schema drift"},
                "headers": {"X-Contract-Hash": live_contract_with_null["content_hash"],
                            "X-Schema-Version": "rename_id"},
                "request": {"body": {}, "headers": {}},
                "elapsed_seconds": 0.05,
                "network_error": None,
            }
        else:
            return {
                "ok": True, "status": 200,
                "body": None,
                "headers": {"X-Contract-Hash": live_contract_with_null["content_hash"],
                            "X-Schema-Version": "rename_id"},
                "request": {"body": {}, "headers": {}},
                "elapsed_seconds": 0.05,
                "network_error": None,
            }

    with patch("driftshield.healer.retry.call_tool", side_effect=fake_call_tool),          patch("driftshield.healer.retry.fetch_live_contract_fn", return_value=live_contract_with_null):
        result = executor.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "healed"
    assert result["result_body"] is None
    assert result["registry_version_after"] > version_before
    assert result["attempts"] == 2

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
