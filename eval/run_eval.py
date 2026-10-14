"""Evaluation harness for DriftShield agents.

Usage:
    python -m eval.run_eval --runs 3
    python -m eval.run_eval --runs 3 --report-only

This harness runs evaluation cases against available agents (healing_agent and baseline_agent)
and generates comprehensive metrics including ZTAR, MTTR, token overhead, and data corruption rates.
"""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Literal
from dataclasses import asdict
from statistics import mean

import httpx
from rich.console import Console
from rich.table import Table

from driftshield import config
from driftshield.agents.common import AgentRun, STANDARD_TASK
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import create_default_registry
from driftshield.mock_api import contracts
from eval.cases import EVAL_CASES


# Available agents
AGENTS = {
    "healing_agent": "driftshield.agents.healing_agent",
    "baseline_agent": "driftshield.agents.baseline_agent",
}

# Check if naive healer exists
if Path("driftshield/agents/naive_healer.py").exists():
    AGENTS["naive_healer"] = "driftshield.agents.naive_healer"


Outcome = Literal["correctly_healed", "correctly_refused", "falsely_healed", "wrongly_refused", "failed"]


def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()[:8]
    except Exception:
        return "unknown"


def reset_api(client: httpx.Client) -> None:
    """
    Reset API to v1 and clear faults.
    
    Raises:
        RuntimeError: If either reset operation fails
    """
    reset_response = client.post("/admin/reset")
    if reset_response.status_code != 200:
        raise RuntimeError(f"Failed to reset API: status {reset_response.status_code}")
    
    fault_response = client.post("/admin/fault", json={"mode": None})
    if fault_response.status_code != 200:
        raise RuntimeError(f"Failed to clear faults: status {fault_response.status_code}")


def apply_case_setup(client: httpx.Client, case: dict[str, Any]) -> None:
    """Apply contract mutation and fault injection for a case."""
    # Apply contract mutation
    if case["contract"]:
        response = client.post("/admin/mutate", json={"to": case["contract"]})
        if response.status_code != 200:
            raise RuntimeError(f"Failed to mutate to {case['contract']}")
    
    # Apply fault injection
    if case["fault"]:
        response = client.post("/admin/fault", json={"mode": case["fault"]})
        if response.status_code != 200:
            raise RuntimeError(f"Failed to set fault {case['fault']}")


def run_agent_on_case(
    agent_name: str,
    task: str,
    client: httpx.Client,
) -> AgentRun:
    """
    Run a single agent on a single task.
    
    Creates fresh registry and budget for each run.
    """
    # Create fresh budget
    budget = Budget(max_api_attempts=5, max_model_calls=8)
    
    if agent_name == "healing_agent":
        # Import healing agent
        from driftshield.agents import healing_agent
        
        # Create fresh registry
        registry = create_default_registry()
        
        # Create healing executor
        executor = HealingExecutor(
            registry=registry,
            client=client,
            budget=budget,
            log_events=True
        )
        
        # Run healing agent
        return healing_agent.run(task, registry, executor, budget)
    
    elif agent_name == "baseline_agent":
        # Import baseline agent
        from driftshield.agents import baseline_agent
        
        # Run baseline agent
        return baseline_agent.run(task, budget, client)
    
    elif agent_name == "naive_healer":
        # Import naive healer (if it exists)
        from driftshield.agents import naive_healer
        
        # Create fresh registry
        registry = create_default_registry()
        
        # Run naive healer
        return naive_healer.run(task, registry, budget, client)
    
    else:
        raise ValueError(f"Unknown agent: {agent_name}")


def get_normal_tokens(
    agent_name: str,
    client: httpx.Client,
    normal_cache: dict[str, int]
) -> int:
    """
    Get normal token count for an agent on v1 (cached per session).
    
    Returns the total tokens (tokens_in + tokens_out) for a normal v1 run.
    """
    if agent_name in normal_cache:
        return normal_cache[agent_name]
    
    # Reset to v1
    reset_api(client)
    
    # Run on standard task with v1
    result = run_agent_on_case(agent_name, STANDARD_TASK, client)
    
    # Cache total tokens
    normal_tokens = result.tokens_in + result.tokens_out
    normal_cache[agent_name] = normal_tokens
    
    return normal_tokens


def classify_outcome(
    case: dict[str, Any],
    run: AgentRun
) -> Outcome:
    """
    Classify the outcome of an agent run into one of five buckets.
    
    Buckets:
    - correctly_healed: heal case, success, answer contains expected text
    - correctly_refused: refusal case, stopped safely with no answer presented
    - falsely_healed: refusal case but produced a successful lookup or answer
    - wrongly_refused: heal case but stopped safely
    - failed: crash, budget exhausted, or heal-case success with wrong answer
    """
    expected_action = case["expected_action"]
    expected_text = case["expected_text"]
    
    if expected_action == "heal":
        # This is a drift case - should heal successfully
        if run.success and run.status in ["ok", "healed"]:
            # Check if answer contains expected text
            if expected_text and expected_text.lower() in run.final_text.lower():
                return "correctly_healed"
            else:
                # Success but wrong answer
                return "failed"
        elif run.status == "budget_exhausted":
            # Budget exhausted - always failed
            return "failed"
        elif run.status in ["safe_stop", "failed"]:
            # Stopped but should have healed
            return "wrongly_refused"
        else:
            return "failed"
    
    else:  # expected_action == "refuse"
        # This is a refuse case - should stop safely
        if run.status in ["safe_stop", "budget_exhausted", "failed"]:
            # Stopped safely (correct)
            return "correctly_refused"
        elif run.success and run.status in ["ok", "healed"]:
            # Produced a successful answer when it shouldn't have
            return "falsely_healed"
        else:
            return "failed"


def run_evaluation(runs_per_case: int) -> None:
    """
    Run complete evaluation across all cases, agents, and runs.
    
    For each case, agent, and run:
    1. Reset API to v1
    2. Get normal token count (cached per agent)
    3. Apply case setup (contract + fault)
    4. Run agent on case task
    5. Classify outcome
    6. Record results to results/runs.jsonl
    """
    # Create results directory
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    
    # Output file
    runs_file = results_dir / "runs.jsonl"
    
    # Create HTTP client
    client = httpx.Client(base_url=config.BASE_URL, timeout=30.0)
    
    # Cache for normal token counts (one per agent per session)
    normal_token_cache: dict[str, int] = {}
    
    # Track setup failures
    setup_failures = 0
    
    console = Console()
    
    try:
        with open(runs_file, "w") as f:
            total_runs = len(EVAL_CASES) * len(AGENTS) * runs_per_case
            current_run = 0
            
            for case in EVAL_CASES:
                for agent_name in AGENTS.keys():
                    # Get normal tokens (cached)
                    normal_tokens = get_normal_tokens(agent_name, client, normal_token_cache)
                    
                    for run_num in range(runs_per_case):
                        current_run += 1
                        console.print(f"[{current_run}/{total_runs}] Running {agent_name} on {case['case_id']} (run {run_num + 1})...")
                        
                        # Reset API and apply case setup
                        try:
                            reset_api(client)
                            apply_case_setup(client, case)
                        except Exception as e:
                            console.print(f"  [red]Setup failed: {e}[/red]")
                            console.print(f"  [yellow]Skipping this run due to setup failure[/yellow]")
                            setup_failures += 1
                            continue
                        
                        # Run agent
                        try:
                            agent_run = run_agent_on_case(agent_name, case["task"], client)
                        except Exception as e:
                            console.print(f"  [red]Error running agent: {e}[/red]")
                            # Create failed run
                            agent_run = AgentRun(
                                agent_name=agent_name,
                                success=False,
                                final_text="",
                                status="failed",
                                model_calls=0,
                                api_attempts=0,
                                tokens_in=0,
                                tokens_out=0,
                                elapsed_seconds=0.0,
                                registry_versions_seen=[],
                                reason=str(e),
                                correct=False,
                                t_first_failure=None,
                                t_first_success=None,
                            )
                        
                        # Classify outcome
                        outcome = classify_outcome(case, agent_run)
                        
                        # Check data correctness (for successful answers)
                        data_correct = None
                        if agent_run.success and agent_run.status in ["ok", "healed"]:
                            # Check if answer is correct
                            if case["expected_text"]:
                                data_correct = case["expected_text"].lower() in agent_run.final_text.lower()
                            else:
                                # Refuse case but produced answer - data is wrong
                                data_correct = False
                        
                        # Build result record
                        result = {
                            "case_id": case["case_id"],
                            "case_group": case["group"],
                            "run_number": run_num + 1,
                            "agent_name": agent_name,
                            "model_name": os.getenv("MODEL_NAME", "gemini-3.8-flash"),
                            "normal_tokens": normal_tokens,
                            "outcome": outcome,
                            "data_correct": data_correct,
                            **asdict(agent_run)
                        }
                        
                        # Write to JSONL
                        f.write(json.dumps(result) + "\n")
                        f.flush()
                        
                        # Print summary
                        console.print(f"  Outcome: {outcome}, Status: {agent_run.status}, Tokens: {agent_run.tokens_in + agent_run.tokens_out}")
            
            # Report completion status
            if setup_failures > 0:
                console.print(f"\n[yellow]⚠ Evaluation incomplete: {setup_failures} run(s) skipped due to setup failures[/yellow]")
                console.print(f"[yellow]  Results written to {runs_file} but may not be complete[/yellow]")
            else:
                console.print(f"\n[green]✓ Evaluation complete! Results written to {runs_file}[/green]")
    
    finally:
        client.close()


def compute_metrics(runs_file: Path) -> dict[str, Any]:
    """
    Compute metrics from results/runs.jsonl.
    
    Metrics per agent:
    - ZTAR: correctly healed / total heal runs
    - Correct-refusal rate: correctly refused / total refusal runs  
    - False-heal rate: falsely healed / total refusal runs
    - MTTR: mean(t_first_success - t_first_failure) for recovered runs
    - Token overhead: mean((tokens - normal_tokens) / normal_tokens * 100) for heal runs
    - Data corruption rate: successful wrong-data answers / all successful answers
    - Outcome bucket counts
    """
    # Load all runs
    runs = []
    with open(runs_file) as f:
        for line in f:
            runs.append(json.loads(line))
    
    # Group by agent
    agents = {}
    for run in runs:
        agent_name = run["agent_name"]
        if agent_name not in agents:
            agents[agent_name] = []
        agents[agent_name].append(run)
    
    # Compute metrics for each agent
    metrics = {}
    for agent_name, agent_runs in agents.items():
        # Separate heal and refusal runs
        heal_runs = [r for r in agent_runs if r["case_group"] == "drift"]
        refusal_runs = [r for r in agent_runs if r["case_group"] == "refuse"]
        
        # ZTAR: correctly healed / total heal runs
        correctly_healed = len([r for r in heal_runs if r["outcome"] == "correctly_healed"])
        ztar = (correctly_healed / len(heal_runs) * 100) if heal_runs else 0.0
        
        # Correct-refusal rate
        correctly_refused = len([r for r in refusal_runs if r["outcome"] == "correctly_refused"])
        correct_refusal_rate = (correctly_refused / len(refusal_runs) * 100) if refusal_runs else 0.0
        
        # False-heal rate
        falsely_healed = len([r for r in refusal_runs if r["outcome"] == "falsely_healed"])
        false_heal_rate = (falsely_healed / len(refusal_runs) * 100) if refusal_runs else 0.0
        
        # MTTR: mean time to recover (for runs with both failure and success)
        recovered_runs = [
            r for r in agent_runs
            if r["t_first_failure"] is not None and r["t_first_success"] is not None
        ]
        if recovered_runs:
            mttrs = [(r["t_first_success"] - r["t_first_failure"]) for r in recovered_runs]
            mttr_mean = mean(mttrs)
            mttr_min = min(mttrs)
            mttr_max = max(mttrs)
            mttr_str = f"{mttr_mean:.3f}s (min: {mttr_min:.3f}s, max: {mttr_max:.3f}s)"
        else:
            mttr_str = "n/a"
        
        # Token overhead for heal runs
        heal_runs_with_tokens = [r for r in heal_runs if r["tokens_in"] + r["tokens_out"] > 0]
        if heal_runs_with_tokens:
            overheads = []
            total_tokens = []
            for r in heal_runs_with_tokens:
                total = r["tokens_in"] + r["tokens_out"]
                normal = r["normal_tokens"]
                if normal > 0:
                    overhead = (total - normal) / normal * 100
                    overheads.append(overhead)
                total_tokens.append(total)
            
            token_overhead_pct = mean(overheads) if overheads else 0.0
            token_mean_total = mean(total_tokens)
        else:
            token_overhead_pct = 0.0
            token_mean_total = 0.0
        
        # Data corruption rate
        successful_runs = [r for r in agent_runs if r["success"] and r["status"] in ["ok", "healed"]]
        if successful_runs:
            wrong_data_count = len([r for r in successful_runs if r["data_correct"] is False])
            data_corruption_rate = (wrong_data_count / len(successful_runs) * 100)
        else:
            data_corruption_rate = 0.0
        
        # Outcome bucket counts
        outcome_counts = {
            "correctly_healed": len([r for r in agent_runs if r["outcome"] == "correctly_healed"]),
            "correctly_refused": correctly_refused,
            "falsely_healed": falsely_healed,
            "wrongly_refused": len([r for r in agent_runs if r["outcome"] == "wrongly_refused"]),
            "failed": len([r for r in agent_runs if r["outcome"] == "failed"]),
        }
        
        metrics[agent_name] = {
            "total_runs": len(agent_runs),
            "heal_runs": len(heal_runs),
            "refusal_runs": len(refusal_runs),
            "ztar": ztar,
            "ztar_count": f"{correctly_healed}/{len(heal_runs)}",
            "correct_refusal_rate": correct_refusal_rate,
            "false_heal_rate": false_heal_rate,
            "mttr": mttr_str,
            "token_overhead_pct": token_overhead_pct,
            "token_mean_total": token_mean_total,
            "data_corruption_rate": data_corruption_rate,
            "outcome_counts": outcome_counts,
        }
    
    return metrics


def generate_report(runs_file: Path, metrics: dict[str, Any]) -> None:
    """Generate results/metrics.md report."""
    # Read first run to get metadata
    with open(runs_file) as f:
        first_run = json.loads(f.readline())
    
    model_name = first_run["model_name"]
    
    # Get budget and runs info from config/runs
    budget_api = 5
    budget_model = 8
    
    # Count runs per case
    with open(runs_file) as f:
        runs = [json.loads(line) for line in f]
    
    runs_per_case = len([r for r in runs if r["case_id"] == runs[0]["case_id"] and r["agent_name"] == runs[0]["agent_name"]])
    
    # Get git commit
    git_commit = get_git_commit()
    
    # Get date
    date_str = time.strftime("%Y-%m-%d")
    
    # Build report
    report_lines = [
        f"# DriftShield Evaluation Results",
        f"",
        f"**Date**: {date_str}  ",
        f"**Model**: {model_name}  ",
        f"**Temperature**: Model default (parameter omitted)  ",
        f"**Budget**: {budget_api} API attempts, {budget_model} model calls  ",
        f"**Runs per case**: {runs_per_case}  ",
        f"**Git commit**: {git_commit}  ",
        f"",
        f"---",
        f"",
        f"## Metrics by Agent",
        f"",
    ]
    
    # Create table for each agent
    for agent_name, agent_metrics in metrics.items():
        report_lines.extend([
            f"### {agent_name}",
            f"",
            f"- **Total runs**: {agent_metrics['total_runs']}",
            f"- **Heal runs**: {agent_metrics['heal_runs']}",
            f"- **Refusal runs**: {agent_metrics['refusal_runs']}",
            f"",
            f"#### ZTAR (Zero-Touch Adaptation Rate)",
            f"- **Rate**: {agent_metrics['ztar']:.1f}% ({agent_metrics['ztar_count']})",
            f"",
            f"#### Refusal Metrics",
            f"- **Correct-refusal rate**: {agent_metrics['correct_refusal_rate']:.1f}%",
            f"- **False-heal rate**: {agent_metrics['false_heal_rate']:.1f}%",
            f"",
            f"#### MTTR (Mean Time to Recovery)",
            f"- **MTTR**: {agent_metrics['mttr']}",
            f"",
            f"#### Token Overhead",
            f"- **Mean overhead**: {agent_metrics['token_overhead_pct']:.1f}%",
            f"- **Mean total tokens per heal run**: {agent_metrics['token_mean_total']:.0f}",
            f"",
            f"#### Data Corruption Rate",
            f"- **Rate**: {agent_metrics['data_corruption_rate']:.1f}%",
            f"",
            f"#### Outcome Buckets",
            f"- **Correctly healed**: {agent_metrics['outcome_counts']['correctly_healed']}",
            f"- **Correctly refused**: {agent_metrics['outcome_counts']['correctly_refused']}",
            f"- **Falsely healed**: {agent_metrics['outcome_counts']['falsely_healed']}",
            f"- **Wrongly refused**: {agent_metrics['outcome_counts']['wrongly_refused']}",
            f"- **Failed**: {agent_metrics['outcome_counts']['failed']}",
            f"",
            f"---",
            f"",
        ])
    
    # Write report
    report_file = Path("results/metrics.md")
    report_file.write_text("\n".join(report_lines))
    
    # Also print to console with rich
    console = Console()
    
    table = Table(title="DriftShield Evaluation Metrics")
    table.add_column("Agent", style="cyan")
    table.add_column("ZTAR", justify="right")
    table.add_column("Correct Refusal", justify="right")
    table.add_column("False Heal", justify="right")
    table.add_column("MTTR", justify="right")
    table.add_column("Token Overhead", justify="right")
    table.add_column("Data Corruption", justify="right")
    
    for agent_name, agent_metrics in metrics.items():
        table.add_row(
            agent_name,
            f"{agent_metrics['ztar']:.1f}%",
            f"{agent_metrics['correct_refusal_rate']:.1f}%",
            f"{agent_metrics['false_heal_rate']:.1f}%",
            agent_metrics["mttr"],
            f"{agent_metrics['token_overhead_pct']:.1f}%",
            f"{agent_metrics['data_corruption_rate']:.1f}%",
        )
    
    console.print(table)
    console.print(f"\n[green]✓ Report written to {report_file}[/green]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run DriftShield evaluation")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per case")
    parser.add_argument("--report-only", action="store_true", help="Generate report from existing runs.jsonl without running evaluations")
    
    args = parser.parse_args()
    
    # Validate --runs argument
    if not args.report_only and args.runs <= 0:
        print(f"Error: --runs must be a positive integer, got {args.runs}")
        return
    
    runs_file = Path("results/runs.jsonl")
    
    if args.report_only:
        # Generate report from existing runs
        if not runs_file.exists():
            print(f"Error: {runs_file} not found. Run evaluation first.")
            return
        
        print("Generating report from existing runs...")
        metrics = compute_metrics(runs_file)
        generate_report(runs_file, metrics)
    else:
        # Run evaluation
        print(f"Running evaluation with {args.runs} runs per case...")
        print(f"Base URL: {config.BASE_URL}")
        print(f"Agents: {', '.join(AGENTS.keys())}")
        print(f"Cases: {len(EVAL_CASES)}")
        print(f"Total runs: {len(EVAL_CASES) * len(AGENTS) * args.runs}")
        print()
        
        run_evaluation(args.runs)
        
        # Generate report
        print("\nGenerating report...")
        metrics = compute_metrics(runs_file)
        generate_report(runs_file, metrics)


if __name__ == "__main__":
    main()
