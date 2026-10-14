"""Tests for evaluation runner outcome classification and metrics."""

import json
from pathlib import Path
import tempfile

import pytest

from driftshield.agents.common import AgentRun
from eval.run_eval import classify_outcome, compute_metrics


def test_correctly_healed_outcome():
    """Test correctly_healed classification."""
    case = {
        "case_id": "rename_id",
        "group": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    }
    
    run = AgentRun(
        agent_name="healing_agent",
        success=True,
        final_text="The user's name is Asha Rao.",
        status="healed",
        model_calls=3,
        api_attempts=2,
        tokens_in=100,
        tokens_out=50,
        elapsed_seconds=1.5,
        registry_versions_seen=[1, 2],
        t_first_failure=None,
        t_first_success=None,
    )
    
    assert classify_outcome(case, run) == "correctly_healed"


def test_correctly_refused_outcome():
    """Test correctly_refused classification."""
    case = {
        "case_id": "header_billing",
        "group": "refuse",
        "expected_action": "refuse",
        "expected_text": None,
    }
    
    run = AgentRun(
        agent_name="healing_agent",
        success=False,
        final_text="",
        status="safe_stop",
        model_calls=2,
        api_attempts=1,
        tokens_in=80,
        tokens_out=20,
        elapsed_seconds=0.8,
        registry_versions_seen=[1],
        reason="Required value unavailable: X-Billing-Region",
        t_first_failure=1000.0,
        t_first_success=None,
    )
    
    assert classify_outcome(case, run) == "correctly_refused"


def test_falsely_healed_outcome():
    """Test falsely_healed classification (refuse case but produced answer)."""
    case = {
        "case_id": "combo_billing",
        "group": "refuse",
        "expected_action": "refuse",
        "expected_text": None,
    }
    
    run = AgentRun(
        agent_name="baseline_agent",
        success=True,
        final_text="The user is Asha Rao.",
        status="ok",
        model_calls=2,
        api_attempts=1,
        tokens_in=100,
        tokens_out=30,
        elapsed_seconds=1.0,
        registry_versions_seen=[],
        t_first_failure=None,
        t_first_success=None,
    )
    
    assert classify_outcome(case, run) == "falsely_healed"


def test_wrongly_refused_outcome():
    """Test wrongly_refused classification (heal case but stopped)."""
    case = {
        "case_id": "v2_full",
        "group": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    }
    
    run = AgentRun(
        agent_name="baseline_agent",
        success=False,
        final_text="",
        status="safe_stop",
        model_calls=2,
        api_attempts=1,
        tokens_in=80,
        tokens_out=20,
        elapsed_seconds=0.8,
        registry_versions_seen=[],
        reason="Schema mismatch",
        t_first_failure=1000.0,
        t_first_success=None,
    )
    
    assert classify_outcome(case, run) == "wrongly_refused"


def test_failed_outcome_budget_exhausted():
    """Test failed classification for budget exhaustion."""
    case = {
        "case_id": "rename_id",
        "group": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    }
    
    run = AgentRun(
        agent_name="healing_agent",
        success=False,
        final_text="",
        status="budget_exhausted",
        model_calls=8,
        api_attempts=5,
        tokens_in=400,
        tokens_out=200,
        elapsed_seconds=5.0,
        registry_versions_seen=[1, 1, 1],
        reason="Budget exhausted",
        t_first_failure=1000.0,
        t_first_success=None,
    )
    
    assert classify_outcome(case, run) == "failed"


def test_failed_outcome_wrong_answer():
    """Test failed classification for successful but wrong answer."""
    case = {
        "case_id": "rename_id",
        "group": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    }
    
    run = AgentRun(
        agent_name="healing_agent",
        success=True,
        final_text="The user is John Doe.",
        status="healed",
        model_calls=3,
        api_attempts=2,
        tokens_in=100,
        tokens_out=50,
        elapsed_seconds=1.5,
        registry_versions_seen=[1, 2],
        t_first_failure=1000.0,
        t_first_success=1001.5,
    )
    
    assert classify_outcome(case, run) == "failed"


def test_compute_metrics_basic():
    """Test basic metrics computation."""
    # Create temporary runs file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        runs_file = Path(f.name)
        
        # Write sample runs
        runs = [
            # Correctly healed run
            {
                "case_id": "rename_id",
                "case_group": "drift",
                "run_number": 1,
                "agent_name": "healing_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 150,
                "outcome": "correctly_healed",
                "data_correct": True,
                "agent_name": "healing_agent",
                "success": True,
                "final_text": "Asha Rao",
                "status": "healed",
                "model_calls": 3,
                "api_attempts": 2,
                "tokens_in": 120,
                "tokens_out": 60,
                "elapsed_seconds": 1.5,
                "registry_versions_seen": [1, 2],
                "reason": None,
                "correct": True,
                "t_first_failure": 1000.0,
                "t_first_success": 1001.0,
            },
            # Correctly refused run
            {
                "case_id": "header_billing",
                "case_group": "refuse",
                "run_number": 1,
                "agent_name": "healing_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 150,
                "outcome": "correctly_refused",
                "data_correct": None,
                "agent_name": "healing_agent",
                "success": False,
                "final_text": "",
                "status": "safe_stop",
                "model_calls": 2,
                "api_attempts": 1,
                "tokens_in": 80,
                "tokens_out": 20,
                "elapsed_seconds": 0.8,
                "registry_versions_seen": [1],
                "reason": "Missing header",
                "correct": False,
                "t_first_failure": 1000.0,
                "t_first_success": None,
            },
        ]
        
        for run in runs:
            f.write(json.dumps(run) + "\n")
    
    try:
        # Compute metrics
        metrics = compute_metrics(runs_file)
        
        # Verify structure
        assert "healing_agent" in metrics
        agent_metrics = metrics["healing_agent"]
        
        # Check basic counts
        assert agent_metrics["total_runs"] == 2
        assert agent_metrics["heal_runs"] == 1
        assert agent_metrics["refusal_runs"] == 1
        
        # Check ZTAR
        assert agent_metrics["ztar"] == 100.0
        assert agent_metrics["ztar_count"] == "1/1"
        
        # Check refusal rates
        assert agent_metrics["correct_refusal_rate"] == 100.0
        assert agent_metrics["false_heal_rate"] == 0.0
        
        # Check MTTR
        assert "1.000s" in agent_metrics["mttr"]
        
        # Check token overhead
        # Total: 180, Normal: 150, Overhead: (180-150)/150 * 100 = 20%
        assert abs(agent_metrics["token_overhead_pct"] - 20.0) < 0.1
        
        # Check data corruption
        assert agent_metrics["data_corruption_rate"] == 0.0
        
        # Check outcome counts
        assert agent_metrics["outcome_counts"]["correctly_healed"] == 1
        assert agent_metrics["outcome_counts"]["correctly_refused"] == 1
        assert agent_metrics["outcome_counts"]["falsely_healed"] == 0
        assert agent_metrics["outcome_counts"]["wrongly_refused"] == 0
        assert agent_metrics["outcome_counts"]["failed"] == 0
    
    finally:
        # Clean up
        runs_file.unlink()


def test_compute_metrics_multiple_agents():
    """Test metrics computation with multiple agents."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        runs_file = Path(f.name)
        
        # Write runs for two agents
        runs = [
            # Healing agent - correctly healed
            {
                "case_id": "rename_id",
                "case_group": "drift",
                "run_number": 1,
                "agent_name": "healing_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 150,
                "outcome": "correctly_healed",
                "data_correct": True,
                "success": True,
                "final_text": "Asha Rao",
                "status": "healed",
                "model_calls": 3,
                "api_attempts": 2,
                "tokens_in": 120,
                "tokens_out": 60,
                "elapsed_seconds": 1.5,
                "registry_versions_seen": [1, 2],
                "reason": None,
                "correct": True,
                "t_first_failure": 1000.0,
                "t_first_success": 1001.0,
            },
            # Baseline agent - wrongly refused
            {
                "case_id": "rename_id",
                "case_group": "drift",
                "run_number": 1,
                "agent_name": "baseline_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 140,
                "outcome": "wrongly_refused",
                "data_correct": None,
                "success": False,
                "final_text": "",
                "status": "failed",
                "model_calls": 2,
                "api_attempts": 1,
                "tokens_in": 100,
                "tokens_out": 30,
                "elapsed_seconds": 1.0,
                "registry_versions_seen": [],
                "reason": "Schema mismatch",
                "correct": False,
                "t_first_failure": 1000.0,
                "t_first_success": None,
            },
        ]
        
        for run in runs:
            f.write(json.dumps(run) + "\n")
    
    try:
        metrics = compute_metrics(runs_file)
        
        # Verify both agents present
        assert "healing_agent" in metrics
        assert "baseline_agent" in metrics
        
        # Healing agent should have 100% ZTAR
        assert metrics["healing_agent"]["ztar"] == 100.0
        
        # Baseline agent should have 0% ZTAR
        assert metrics["baseline_agent"]["ztar"] == 0.0
        assert metrics["baseline_agent"]["outcome_counts"]["wrongly_refused"] == 1
    
    finally:
        runs_file.unlink()


def test_compute_metrics_data_corruption():
    """Test data corruption rate calculation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        runs_file = Path(f.name)
        
        # Write runs with data corruption
        runs = [
            # Correct answer
            {
                "case_id": "rename_id",
                "case_group": "drift",
                "run_number": 1,
                "agent_name": "healing_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 150,
                "outcome": "correctly_healed",
                "data_correct": True,
                "success": True,
                "final_text": "Asha Rao",
                "status": "healed",
                "model_calls": 3,
                "api_attempts": 2,
                "tokens_in": 120,
                "tokens_out": 60,
                "elapsed_seconds": 1.5,
                "registry_versions_seen": [1, 2],
                "reason": None,
                "correct": True,
                "t_first_failure": 1000.0,
                "t_first_success": 1001.0,
            },
            # Wrong answer (data corruption)
            {
                "case_id": "type_int",
                "case_group": "drift",
                "run_number": 1,
                "agent_name": "healing_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 150,
                "outcome": "failed",
                "data_correct": False,
                "success": True,
                "final_text": "John Doe",
                "status": "healed",
                "model_calls": 3,
                "api_attempts": 2,
                "tokens_in": 120,
                "tokens_out": 60,
                "elapsed_seconds": 1.5,
                "registry_versions_seen": [1, 2],
                "reason": None,
                "correct": False,
                "t_first_failure": 1000.0,
                "t_first_success": 1001.0,
            },
        ]
        
        for run in runs:
            f.write(json.dumps(run) + "\n")
    
    try:
        metrics = compute_metrics(runs_file)
        
        # Data corruption rate: 1 wrong / 2 total = 50%
        assert metrics["healing_agent"]["data_corruption_rate"] == 50.0
    
    finally:
        runs_file.unlink()


def test_compute_metrics_no_mttr():
    """Test MTTR when no runs have recovery."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        runs_file = Path(f.name)
        
        # Write run with no recovery
        runs = [
            {
                "case_id": "header_billing",
                "case_group": "refuse",
                "run_number": 1,
                "agent_name": "healing_agent",
                "model_name": "gpt-4o-mini",
                "normal_tokens": 150,
                "outcome": "correctly_refused",
                "data_correct": None,
                "success": False,
                "final_text": "",
                "status": "safe_stop",
                "model_calls": 2,
                "api_attempts": 1,
                "tokens_in": 80,
                "tokens_out": 20,
                "elapsed_seconds": 0.8,
                "registry_versions_seen": [1],
                "reason": "Missing header",
                "correct": False,
                "t_first_failure": 1000.0,
                "t_first_success": None,
            },
        ]
        
        for run in runs:
            f.write(json.dumps(run) + "\n")
    
    try:
        metrics = compute_metrics(runs_file)
        
        # MTTR should be n/a
        assert metrics["healing_agent"]["mttr"] == "n/a"
    
    finally:
        runs_file.unlink()
