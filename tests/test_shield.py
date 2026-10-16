"""Tests for the Shield facade."""

import pytest
from fastapi.testclient import TestClient

from driftshield import Shield, Budget, ToolRegistry, create_default_registry
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


def test_shield_successful_execution(clean_api):
    """Test: Normal tool execution succeeds with status 'ok'."""
    shield = Shield(client=clean_api)
    result = shield.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "ok"
    assert result["result_body"]["user"]["id"] == 123
    assert result["attempts"] == 1
    assert shield.registry.version("lookup_user") == 1


def test_shield_reactive_healing_through_facade(clean_api):
    """Test: Tool call under schema drift reactively heals through the facade."""
    clean_api.post("/admin/mutate", json={"to": "rename_id"})

    shield = Shield(client=clean_api)
    result = shield.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "healed"
    assert result["result_body"]["user"]["id"] == 123
    assert result["registry_version_after"] > result["registry_version_before"]
    assert shield.registry.version("lookup_user") == 2


def test_shield_safe_stop_propagation(clean_api):
    """Test: Ambiguous drift halts in safe_stop without corrupting registry."""
    clean_api.post("/admin/mutate", json={"to": "ambiguous"})

    shield = Shield(client=clean_api)
    result = shield.execute("lookup_user", {"user_id": "123"})

    assert result["status"] == "safe_stop"
    assert result["result_body"] is None
    assert "ambiguous" in result["reason"].lower()
    assert shield.registry.version("lookup_user") == 1


def test_shield_sentinel_disabled_by_default(clean_api):
    """Test: Sentinel is not initialized when enable_sentinel=False."""
    shield = Shield(client=clean_api)
    assert shield.sentinel is None


def test_shield_sentinel_enabled_and_lifecycle(clean_api):
    """Test: Sentinel monitoring starts, stops, and cleans up through Shield."""
    shield = Shield(client=clean_api, enable_sentinel=True, sentinel_poll_interval=0.05)

    assert shield.sentinel is not None
    assert shield.sentinel.is_running is True

    shield.stop_sentinel()
    assert shield.sentinel.is_running is False

    shield.start_sentinel()
    assert shield.sentinel.is_running is True

    shield.close()
    assert shield.sentinel.is_running is False
    assert shield.is_closed is True


def test_shield_context_manager_behavior(clean_api):
    """Test: Shield works cleanly as a context manager and enforces closed state."""
    with Shield(client=clean_api, enable_sentinel=True, sentinel_poll_interval=0.05) as shield:
        assert not shield.is_closed
        assert shield.sentinel.is_running is True

        res = shield.execute("lookup_user", {"user_id": "123"})
        assert res["status"] == "ok"

    assert shield.is_closed
    assert shield.sentinel.is_running is False

    with pytest.raises(RuntimeError) as exc_info:
        shield.execute("lookup_user", {"user_id": "123"})
    assert "closed" in str(exc_info.value).lower()


def test_shield_caller_owned_client_not_closed(clean_api):
    """Test: Shield does not close caller-provided clients."""
    class CallerClient:
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True
        def get(self, *args, **kwargs):
            return clean_api.get(*args, **kwargs)
        def post(self, *args, **kwargs):
            return clean_api.post(*args, **kwargs)

    caller_client = CallerClient()
    shield = Shield(client=caller_client)
    assert not shield._owns_client

    shield.close()
    assert caller_client.closed is False


def test_shield_owned_client_closed_on_close():
    """Test: Shield closes internally created HTTP client on close()."""
    shield = Shield(client=None)
    assert shield._owns_client
    internal_client = shield.client

    assert hasattr(internal_client, "is_closed")
    assert not internal_client.is_closed

    shield.close()
    assert internal_client.is_closed is True


def test_shield_invalid_configuration():
    """Test: Invalid configurations raise clear exceptions."""
    with pytest.raises(ValueError) as exc:
        Shield(sentinel_poll_interval=0)
    assert "positive number" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Shield(sentinel_poll_interval=-5.0)
    assert "positive number" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Shield(sentinel_poll_interval="invalid")  # type: ignore
    assert "positive number" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Shield(budget={"max_api_attempts": 0})
    assert "max_api_attempts" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Shield(budget={"max_model_calls": -1})
    assert "max_model_calls" in str(exc.value)

    with pytest.raises(TypeError) as exc:
        Shield(budget="invalid_budget")  # type: ignore
    assert "Expected Budget" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        Shield(budget=Budget(max_api_attempts=0))
    assert "max_api_attempts" in str(exc.value)


def test_shield_event_forwarding(clean_api):
    """Test: Events are properly forwarded to on_event and subscribers."""
    events_init = []
    events_sub = []

    def sub_func(name, data):
        events_sub.append((name, data))

    shield = Shield(client=clean_api, on_event=lambda name, data: events_init.append((name, data)))
    shield.subscribe(sub_func)

    shield.execute("lookup_user", {"user_id": "123"})

    assert len(events_init) > 0
    names_init = [e[0] for e in events_init]
    assert "intercepted" in names_init
    assert "success" in names_init

    # Both subscribers received identical events
    assert events_sub == events_init

    # Unsubscribe test
    shield.unsubscribe(sub_func)
    count_before = len(events_sub)
    shield.execute("lookup_user", {"user_id": "123"})
    assert len(events_sub) == count_before
    assert len(events_init) > count_before


def test_shield_default_construction(clean_api):
    """Test: Default construction provisions registry and budget without duplicating logic."""
    shield = Shield(client=clean_api)
    assert isinstance(shield.registry, ToolRegistry)
    assert isinstance(shield.budget, Budget)
    assert shield.budget.max_api_attempts == 5
    assert shield.budget.max_model_calls == 8
    assert shield.registry.get("lookup_user") is not None


def test_shield_dict_budget_construction(clean_api):
    """Test: Constructing Shield with a dict budget applies limits correctly."""
    shield = Shield(client=clean_api, budget={"max_api_attempts": 2, "max_model_calls": 3})
    assert shield.budget.max_api_attempts == 2
    assert shield.budget.max_model_calls == 3


def test_shield_package_imports():
    """Test: Shield is cleanly exported from top-level driftshield package."""
    import driftshield
    from driftshield import Shield, Budget, Sentinel, HealingExecutor

    assert hasattr(driftshield, "Shield")
    assert driftshield.Shield is Shield
    assert Shield is not None
