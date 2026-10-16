"""Focused audit verification: Real healing executor with audit logging."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from driftshield.healer.retry import HealingExecutor, Budget
from driftshield.healer.registry import create_default_registry
from driftshield.healer import log
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
def executor_with_logging(clean_api):
    """Create healing executor with logging enabled."""
    registry = create_default_registry()
    budget = Budget(max_api_attempts=10, max_model_calls=10)
    return HealingExecutor(registry, clean_api, budget, log_events=True)


def test_end_to_end_healing_with_audit_log(executor_with_logging, clean_api):
    """Test: Mutate to v2_full, drift detected and healed, WITH AUDIT LOGGING."""
    # Clean up any existing log
    log_file = Path("patch_log.jsonl")
    if log_file.exists():
        log_file.unlink()
    
    executor = executor_with_logging
    
    # Mutate API to v2_full
    clean_api.post("/admin/mutate", json={"to": "v2_full"})
    
    # Execute with v1 args
    result = executor.execute("lookup_user", {"user_id": "123"})
    
    print(f"\nResult status: {result['status']}")
    print(f"Result attempts: {result['attempts']}")
    print(f"Registry version: {result['registry_version_before']} -> {result['registry_version_after']}")
    if result['status'] != 'healed':
        print(f"Reason: {result.get('reason')}")
    
    # Should heal
    assert result["status"] == "healed"
    assert result["result_body"]["user"]["id"] == 123
    assert result["registry_version_before"] == 1
    assert result["registry_version_after"] == 2
    assert result["attempts"] == 2  # Initial + retry
    
    # Verify audit log has events
    events = log.read_all()
    print(f"\nAudit log events: {len(events)}")
    assert len(events) > 0, "Expected audit log entries"
    
    # Verify lookup was counted
    stats = clean_api.get("/admin/stats").json()
    assert stats["successful_lookups"] >= 1
    
    print("\n[PASS] End-to-end healing with audit logging verified!")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
