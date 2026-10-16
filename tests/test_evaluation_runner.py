"""Tests for Phase 5 deterministic evaluation harness and report generation."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from driftshield.mock_api.server import app as mock_server_app
from driftshield.mock_api import contracts
from eval.deterministic_eval import (
    reset_environment,
    run_baseline_call,
    run_driftshield_call,
    run_all_scenarios,
    _generate_markdown_report,
)


@pytest.fixture
def client():
    """Create test client and reset environment."""
    c = TestClient(mock_server_app)
    reset_environment(c)
    return c


def test_reset_environment(client):
    """Test: reset_environment restores v1 and clears faults."""
    client.post("/admin/mutate", json={"to": "rename_id"})
    client.post("/admin/fault", json={"mode": "server_down"})
    assert contracts.get_active()["schema_version"] != "v1"

    reset_environment(client)
    assert contracts.get_active()["schema_version"] == "v1"
    resp = client.get("/schema")
    assert resp.status_code == 200
    assert resp.json()["schema_version"] == "v1"


def test_baseline_call_success_on_v1(client):
    """Test: Baseline call succeeds on unmutated v1 contract."""
    reset_environment(client)
    res = run_baseline_call(client, "lookup_user", {"user_id": "123"})
    assert res["status"] == "success"
    assert res["success"] is True
    assert res["attempts"] == 1
    assert res["result"]["user"]["name"] == "Asha Rao"


def test_baseline_call_fails_on_schema_drift(client):
    """Test: Baseline call fails and exhausts retries on schema drift."""
    reset_environment(client)
    client.post("/admin/mutate", json={"to": "rename_id"})
    res = run_baseline_call(client, "lookup_user", {"user_id": "123"}, max_attempts=3)
    assert res["status"] == "failed"
    assert res["success"] is False
    assert res["attempts"] == 3


def test_driftshield_heals_unambiguous_drift(client):
    """Test: DriftShield heals unambiguous rename."""
    reset_environment(client)
    client.post("/admin/mutate", json={"to": "rename_id"})
    res, _ = run_driftshield_call(client, "lookup_user", {"user_id": "123"})
    assert res["status"] == "healed"
    assert res["success"] is True
    assert res["registry_version_before"] == 1
    assert res["registry_version_after"] == 2
    assert res["result"]["user"]["name"] == "Asha Rao"


def test_driftshield_safe_stops_on_ambiguous(client):
    """Test: DriftShield safe stops on ambiguous drift without hallucinating."""
    reset_environment(client)
    client.post("/admin/mutate", json={"to": "ambiguous"})
    res, _ = run_driftshield_call(client, "lookup_user", {"user_id": "123"})
    assert res["status"] == "safe_stop"
    assert res["success"] is False
    assert "ambiguous" in res["reason"].lower() or "ref_" in res["reason"].lower()
    assert res["registry_version_before"] == 1
    assert res["registry_version_after"] == 1


def test_driftshield_safe_stops_on_missing_required_header(client):
    """Test: DriftShield safe stops when required header is missing."""
    reset_environment(client)
    client.post("/admin/mutate", json={"to": "header_billing"})
    res, _ = run_driftshield_call(client, "lookup_user", {"user_id": "123"})
    assert res["status"] == "safe_stop"
    assert res["success"] is False
    assert "X-Billing-Region" in res["reason"]
    assert res["fix_proposal"] is not None


def test_run_all_scenarios_outputs_valid_artifacts(client, tmp_path):
    """Test: run_all_scenarios produces machine-readable JSON and Markdown."""
    json_out = tmp_path / "eval_results.json"
    md_out = tmp_path / "eval_report.md"

    report = run_all_scenarios(
        client=client,
        output_json=json_out,
        output_md=md_out,
        quiet=True,
    )

    assert report["summary"]["total_scenarios"] == 6
    assert report["summary"]["correct_outcomes"] == 6
    assert report["summary"]["unsafe_recoveries_avoided"] == 6

    # Verify JSON file
    assert json_out.exists()
    with open(json_out, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["execution_mode"] == "deterministic_mock_api"
        assert len(data["scenarios"]) == 6

    # Verify Markdown file
    assert md_out.exists()
    content = md_out.read_text(encoding="utf-8")
    assert "# DriftShield End-to-End Evaluation Report" in content
    assert "Scenario Breakdown" in content
