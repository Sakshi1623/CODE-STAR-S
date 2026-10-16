"""DriftShield live demonstration with rich terminal output.

Demonstrates healing agent capabilities against a running mock API.
Supports --record to save a session and --replay for offline playback.

Usage:
    python demo.py                # Live demo (requires running mock API)
    python demo.py --record       # Live demo + save recording
    python demo.py --replay       # Replay saved recording (no network/LLM)
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich import box

from driftshield import config
from driftshield.agents.common import STANDARD_TASK
from driftshield.agents import healing_agent, baseline_agent
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import create_default_registry
from eval.run_eval import compute_metrics


console = Console()


class DemoRecorder:
    """Records demo events for replay."""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.events = []
        self.start_time = time.time()
    
    def record(self, event_type: str, data: Any):
        """Record an event with timestamp."""
        if self.enabled:
            self.events.append({
                "type": event_type,
                "timestamp": time.time() - self.start_time,
                "data": data
            })
    
    def save(self, path: Path):
        """Save recording to file."""
        if self.enabled:
            path.parent.mkdir(exist_ok=True)
            with open(path, "w") as f:
                json.dump({
                    "version": "1.0",
                    "total_duration": time.time() - self.start_time,
                    "events": self.events
                }, f, indent=2)
            console.print(f"\n[green]✓ Recording saved to {path}[/green]")


class DemoPlayer:
    """Plays back a recorded demo."""
    
    def __init__(self, path: Path):
        with open(path) as f:
            recording = json.load(f)
        self.events = recording["events"]
        self.index = 0
        self.start_time = time.time()
    
    def get_next(self) -> tuple[str, Any] | None:
        """Get next event if its time has come."""
        if self.index >= len(self.events):
            return None
        
        event = self.events[self.index]
        elapsed = time.time() - self.start_time
        
        if elapsed >= event["timestamp"]:
            self.index += 1
            return event["type"], event["data"]
        
        return None


def wait_for_enter(message: str = "Press ENTER to continue..."):
    """Wait for user to press ENTER."""
    console.print(f"\n[dim]{message}[/dim]")
    input()


def print_scene_header(title: str, description: str, replay: bool = False):
    """Print a scene header."""
    console.print()
    if replay:
        title = f"[dim]▶[/dim] {title} [dim][REPLAY][/dim]"
    console.print(Panel(
        f"[bold]{title}[/bold]\n{description}",
        border_style="cyan",
        box=box.DOUBLE
    ))
    console.print()


def run_demo_live():
    """Run live demonstration."""
    recorder = DemoRecorder(enabled="--record" in sys.argv)
    client = httpx.Client(base_url=config.BASE_URL, timeout=30.0)
    
    try:
        # ===== SCENE 1: API v1 - Both agents succeed =====
        print_scene_header(
            "Scene 1: API v1 - Baseline",
            "The API is at v1. Both agents work correctly."
        )
        
        # Reset to v1
        console.print("[cyan]→[/cyan] Resetting API to v1...")
        client.post("/admin/reset")
        client.post("/admin/fault", json={"mode": None})
        recorder.record("reset", {"version": "v1"})
        console.print("[green]✓[/green] API reset to v1\n")
        
        # Run baseline agent
        console.print("[cyan]→[/cyan] Running baseline agent...")
        baseline_budget = Budget(max_api_attempts=5, max_model_calls=8)
        baseline_result = baseline_agent.run(STANDARD_TASK, baseline_budget, client)
        
        recorder.record("baseline_v1", {
            "success": baseline_result.success,
            "status": baseline_result.status,
            "tokens": baseline_result.tokens_in + baseline_result.tokens_out,
            "final_text": baseline_result.final_text[:100]
        })
        
        console.print(f"[green]✓[/green] Success: {baseline_result.success}")
        console.print(f"  Status: [yellow]{baseline_result.status}[/yellow]")
        console.print(f"  Tokens: {baseline_result.tokens_in + baseline_result.tokens_out}")
        console.print(f"  Answer: [italic]{baseline_result.final_text}[/italic]")
        console.print(f"  Registry: N/A (baseline has no registry)\n")
        
        # Run healing agent
        console.print("[cyan]→[/cyan] Running healing agent...")
        healing_budget = Budget(max_api_attempts=5, max_model_calls=8)
        healing_registry = create_default_registry()
        healing_executor = HealingExecutor(
            registry=healing_registry,
            client=client,
            budget=healing_budget,
            log_events=True
        )
        healing_result = healing_agent.run(STANDARD_TASK, healing_registry, healing_executor, healing_budget)
        
        recorder.record("healing_v1", {
            "success": healing_result.success,
            "status": healing_result.status,
            "tokens": healing_result.tokens_in + healing_result.tokens_out,
            "registry_version": healing_registry.version("lookup_user"),
            "final_text": healing_result.final_text[:100]
        })
        
        console.print(f"[green]✓[/green] Success: {healing_result.success}")
        console.print(f"  Status: [yellow]{healing_result.status}[/yellow]")
        console.print(f"  Tokens: {healing_result.tokens_in + healing_result.tokens_out}")
        console.print(f"  Answer: [italic]{healing_result.final_text}[/italic]")
        console.print(f"  Registry: version [bold]1[/bold]\n")
        
        wait_for_enter()
        
        # ===== SCENE 2: The Break - Mutate to v2_full =====
        print_scene_header(
            "Scene 2: The Break",
            "The API contract changes from v1 to v2_full. Tool definitions unchanged."
        )
        
        # Get old hash
        schema_response = client.get("/schema")
        old_hash = schema_response.json()["content_hash"]
        console.print(f"[dim]Old contract hash: {old_hash}[/dim]")
        
        # Mutate
        console.print("\n[cyan]→[/cyan] Mutating API to v2_full...")
        mutate_response = client.post("/admin/mutate", json={"to": "v2_full"})
        
        # Get new hash
        schema_response = client.get("/schema")
        new_hash = schema_response.json()["content_hash"]
        
        recorder.record("mutate", {
            "contract": "v2_full",
            "old_hash": old_hash,
            "new_hash": new_hash
        })
        
        console.print(f"[green]✓[/green] API mutated to v2_full")
        console.print(f"  New contract hash: [bold]{new_hash}[/bold]")
        console.print(f"  Old contract hash: [dim]{old_hash}[/dim]\n")
        console.print("[yellow]ℹ[/yellow] Tool definition unchanged (still 'lookup_user')")
        console.print("[yellow]ℹ[/yellow] But the request/response schema changed\n")
        
        wait_for_enter()
        
        # ===== SCENE 3: Baseline Fails =====
        print_scene_header(
            "Scene 3: Baseline Agent Fails",
            "Baseline has no healing. It tries the old v1 format and fails."
        )
        
        console.print("[cyan]→[/cyan] Running baseline agent on v2_full...")
        baseline_budget2 = Budget(max_api_attempts=5, max_model_calls=8)
        
        # Track each API attempt
        console.print("\n[bold]API Attempts:[/bold]")
        
        baseline_result2 = baseline_agent.run(STANDARD_TASK, baseline_budget2, client)
        
        # Show what happened
        console.print(f"  Attempt 1: [red]Status {baseline_result2.status}[/red]")
        console.print(f"  API calls: {baseline_result2.api_attempts}")
        console.print(f"  Model calls: {baseline_result2.model_calls}")
        console.print(f"  Tokens used: {baseline_result2.tokens_in + baseline_result2.tokens_out}\n")
        
        recorder.record("baseline_v2", {
            "success": baseline_result2.success,
            "status": baseline_result2.status,
            "api_attempts": baseline_result2.api_attempts,
            "model_calls": baseline_result2.model_calls,
            "tokens": baseline_result2.tokens_in + baseline_result2.tokens_out
        })
        
        console.print(f"[red]✗[/red] Final result: {baseline_result2.status}")
        if baseline_result2.reason:
            console.print(f"  Reason: [italic]{baseline_result2.reason}[/italic]\n")
        
        wait_for_enter()
        
        # ===== SCENE 4: DriftShield Heals =====
        print_scene_header(
            "Scene 4: DriftShield Heals",
            "The healing agent detects drift and adapts automatically."
        )
        
        console.print("[cyan]→[/cyan] Running healing agent with event monitoring...\n")
        
        # Create event handler
        events_shown = []
        
        def on_event(event_name: str, event_data: dict[str, Any]):
            """Handle healing events."""
            events_shown.append((event_name, event_data))
            
            if event_name == "intercepted":
                if not event_data["ok"]:
                    console.print(f"  [yellow]⚡[/yellow] Intercepted failed call (status {event_data['status_code']})")
            
            elif event_name == "classified":
                console.print(f"  [cyan]🔍[/cyan] Classified as: [bold]{event_data['kind']}[/bold]")
            
            elif event_name == "contract_fetched":
                console.print(f"  [cyan]📄[/cyan] Fetched live contract: [dim]{event_data['contract_hash'][:16]}...[/dim]")
            
            elif event_name == "diff":
                console.print(f"  [cyan]📊[/cyan] Detected {len(event_data['changes'])} change(s):")
                for change in event_data['changes']:
                    if change["type"] == "renamed":
                        console.print(f"      • Renamed: {change['removed']} → {change['added']}")
                    elif change["type"] == "nested":
                        console.print(f"      • Nested under: {change['added']}")
            
            elif event_name == "provenance_checked":
                console.print(f"  [cyan]🔐[/cyan] Provenance checked")
            
            elif event_name == "validated":
                console.print(f"  [green]✓[/green] Payload validated")
            
            elif event_name == "patched":
                console.print(f"  [green]🔧[/green] Registry patched: v{event_data['version_before']} → v[bold]{event_data['version_after']}[/bold]")
            
            elif event_name == "retried":
                if event_data["ok"]:
                    console.print(f"  [green]✓[/green] Retry succeeded (status {event_data['status_code']})")
                else:
                    console.print(f"  [red]✗[/red] Retry failed (status {event_data['status_code']})")
            
            elif event_name == "safe_stop":
                console.print(f"  [red]⚠[/red] Safe stop: {event_data['reason']}")
        
        healing_budget3 = Budget(max_api_attempts=5, max_model_calls=8)
        healing_registry3 = create_default_registry()
        healing_executor3 = HealingExecutor(
            registry=healing_registry3,
            client=client,
            budget=healing_budget3,
            log_events=True,
            on_event=on_event
        )
        
        start_time = time.time()
        healing_result3 = healing_agent.run(STANDARD_TASK, healing_registry3, healing_executor3, healing_budget3)
        recovery_time = time.time() - start_time
        
        recorder.record("healing_v2", {
            "success": healing_result3.success,
            "status": healing_result3.status,
            "registry_version": healing_registry3.version("lookup_user"),
            "recovery_time": recovery_time,
            "tokens": healing_result3.tokens_in + healing_result3.tokens_out,
            "events": [(e, d) for e, d in events_shown]
        })
        
        console.print(f"\n[green]✓[/green] Final result: {healing_result3.status}")
        console.print(f"  Registry: v1 → v[bold]{healing_registry3.version('lookup_user')}[/bold]")
        console.print(f"  Recovery time: [bold]{recovery_time:.2f}s[/bold]")
        console.print(f"  Answer: [italic]{healing_result3.final_text}[/italic]\n")
        
        # Show last patch log entry
        patch_log = Path("patch_log.jsonl")
        if patch_log.exists():
            with open(patch_log) as f:
                lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    console.print("[cyan]→[/cyan] Last patch log entry:")
                    console.print(f"  Tool: [bold]{last_entry['tool']}[/bold]")
                    console.print(f"  Version: {last_entry['registry_version_before']} → {last_entry['registry_version_after']}")
                    console.print(f"  Outcome: [bold]{last_entry['outcome']}[/bold]")
                    console.print(f"  Hash: [dim]{last_entry['contract_hash_patched_against'][:16]}...[/dim]\n")
                    
                    recorder.record("patch_log", last_entry)
        
        wait_for_enter()
        
        # ===== SCENE 5: Safe Stop =====
        print_scene_header(
            "Scene 5: Safe Stop",
            "Some drifts cannot be healed safely. The agent refuses gracefully."
        )
        
        console.print("[cyan]→[/cyan] Mutating to header_billing (requires unavailable header)...")
        client.post("/admin/reset")
        client.post("/admin/mutate", json={"to": "header_billing"})
        console.print("[green]✓[/green] API mutated to header_billing\n")
        
        recorder.record("mutate_billing", {"contract": "header_billing"})
        
        console.print("[cyan]→[/cyan] Running healing agent...\n")
        
        safe_stop_events = []
        
        def on_safe_stop_event(event_name: str, event_data: dict[str, Any]):
            """Handle safe stop events."""
            safe_stop_events.append((event_name, event_data))
            
            if event_name == "safe_stop":
                console.print(f"  [yellow]⚠[/yellow] Safe stop triggered")
                console.print(f"      Reason: {event_data['reason']}")
                if "missing_headers" in event_data:
                    console.print(f"      Missing: [bold]{', '.join(event_data['missing_headers'])}[/bold]")
        
        healing_budget4 = Budget(max_api_attempts=5, max_model_calls=8)
        healing_registry4 = create_default_registry()
        healing_executor4 = HealingExecutor(
            registry=healing_registry4,
            client=client,
            budget=healing_budget4,
            log_events=True,
            on_event=on_safe_stop_event
        )
        
        healing_result4 = healing_agent.run(STANDARD_TASK, healing_registry4, healing_executor4, healing_budget4)
        
        recorder.record("safe_stop", {
            "status": healing_result4.status,
            "reason": healing_result4.reason
        })
        
        console.print(f"\n[red]⚠[/red] Status: [bold]{healing_result4.status}[/bold]")
        console.print(f"  Reason: [italic]{healing_result4.reason}[/italic]\n")
        
        console.print("[cyan]💡[/cyan] Fix proposal:")
        console.print("  Add X-Billing-Region header to configuration")
        console.print("  or have human operator provide the value\n")
        
        # Check for naive healer
        naive_healer_path = Path("driftshield/agents/naive_healer.py")
        if naive_healer_path.exists():
            console.print("[yellow]⚠[/yellow] Naive healer detected - demonstrating unsafe behavior...\n")
            from driftshield.agents import naive_healer
            
            naive_budget = Budget(max_api_attempts=5, max_model_calls=8)
            naive_registry = create_default_registry()
            naive_result = naive_healer.run(STANDARD_TASK, naive_registry, naive_budget, client)
            
            console.print(f"  Naive healer result: {naive_result.status}")
            if naive_result.success:
                console.print(f"  [red]✗[/red] Invented value without authorization!")
                console.print(f"  Answer: [italic]{naive_result.final_text}[/italic]\n")
            
            recorder.record("naive_healer", {
                "success": naive_result.success,
                "status": naive_result.status,
                "invented": True
            })
        
        wait_for_enter()
        
        # ===== SCENE 6: Results =====
        print_scene_header(
            "Scene 6: Evaluation Results",
            "Summary of agent performance from evaluation runs."
        )
        
        # Check if results exist
        runs_file = Path("results/runs.jsonl")
        if not runs_file.exists():
            console.print("[yellow]⚠[/yellow] No evaluation results found. Run:")
            console.print("  [cyan]python -m eval.run_eval --runs 3[/cyan]\n")
        else:
            console.print("[cyan]→[/cyan] Loading evaluation results...\n")
            
            metrics = compute_metrics(runs_file)
            
            # Create table
            table = Table(title="Agent Performance Metrics", box=box.ROUNDED)
            table.add_column("Agent", style="cyan")
            table.add_column("ZTAR", justify="right")
            table.add_column("Correct Refusal", justify="right")
            table.add_column("False Heal", justify="right")
            table.add_column("MTTR", justify="right")
            table.add_column("Token Overhead", justify="right")
            
            for agent_name, agent_metrics in metrics.items():
                table.add_row(
                    agent_name,
                    f"{agent_metrics['ztar']:.1f}%",
                    f"{agent_metrics['correct_refusal_rate']:.1f}%",
                    f"{agent_metrics['false_heal_rate']:.1f}%",
                    agent_metrics['mttr'],
                    f"{agent_metrics['token_overhead_pct']:.1f}%"
                )
            
            console.print(table)
            console.print()
            
            recorder.record("results", {
                "metrics": {k: {
                    "ztar": v["ztar"],
                    "correct_refusal_rate": v["correct_refusal_rate"],
                    "mttr": v["mttr"]
                } for k, v in metrics.items()}
            })
        
        console.print("\n[green]✓[/green] Demo complete!\n")
        
        # Save recording if enabled
        if recorder.enabled:
            recorder.save(Path("results/demo_recording.json"))
    
    finally:
        client.close()


def run_demo_replay():
    """Run demonstration from recording (fully offline - no network or LLM calls)."""
    recording_path = Path("results/demo_recording.json")
    
    if not recording_path.exists():
        console.print(f"[red]✗ Error: Recording not found[/red]")
        console.print(f"\nExpected file: {recording_path}")
        console.print("\nTo create a recording:")
        console.print("  1. Start the mock API: [cyan]python -m uvicorn driftshield.mock_api.server:app[/cyan]")
        console.print("  2. Run with recording: [cyan]python demo.py --record[/cyan]")
        console.print("\nThis will save a recording to results/demo_recording.json")
        console.print("Then you can replay offline with: [cyan]python demo.py --replay[/cyan]\n")
        sys.exit(1)
    
    console.print(f"[cyan]▶[/cyan] Replaying recording from {recording_path}")
    console.print("[dim]Replay mode: No network or LLM calls will be made[/dim]\n")
    
    player = DemoPlayer(recording_path)
    
    # Process events
    while True:
        event = player.get_next()
        if event is None:
            time.sleep(0.01)  # Small delay
            if player.index >= len(player.events):
                break
            continue
        
        event_type, data = event
        
        if event_type == "reset":
            print_scene_header(
                "Scene 1: API v1 - Baseline",
                "The API is at v1. Both agents work correctly.",
                replay=True
            )
            console.print("[cyan]→[/cyan] Resetting API to v1...")
            console.print("[green]✓[/green] API reset to v1\n")
        
        elif event_type == "baseline_v1":
            console.print("[cyan]→[/cyan] Running baseline agent...")
            console.print(f"[green]✓[/green] Success: {data['success']}")
            console.print(f"  Status: [yellow]{data['status']}[/yellow]")
            console.print(f"  Tokens: {data['tokens']}")
            console.print(f"  Answer: [italic]{data['final_text']}...[/italic]")
            console.print(f"  Registry: N/A (baseline has no registry)\n")
        
        elif event_type == "healing_v1":
            console.print("[cyan]→[/cyan] Running healing agent...")
            console.print(f"[green]✓[/green] Success: {data['success']}")
            console.print(f"  Status: [yellow]{data['status']}[/yellow]")
            console.print(f"  Tokens: {data['tokens']}")
            console.print(f"  Answer: [italic]{data['final_text']}...[/italic]")
            console.print(f"  Registry: version [bold]{data['registry_version']}[/bold]\n")
            wait_for_enter()
        
        elif event_type == "mutate":
            print_scene_header(
                "Scene 2: The Break",
                "The API contract changes from v1 to v2_full. Tool definitions unchanged.",
                replay=True
            )
            console.print(f"[dim]Old contract hash: {data['old_hash']}[/dim]")
            console.print("\n[cyan]→[/cyan] Mutating API to v2_full...")
            console.print(f"[green]✓[/green] API mutated to v2_full")
            console.print(f"  New contract hash: [bold]{data['new_hash']}[/bold]")
            console.print(f"  Old contract hash: [dim]{data['old_hash']}[/dim]\n")
            console.print("[yellow]ℹ[/yellow] Tool definition unchanged (still 'lookup_user')")
            console.print("[yellow]ℹ[/yellow] But the request/response schema changed\n")
            wait_for_enter()
        
        elif event_type == "baseline_v2":
            print_scene_header(
                "Scene 3: Baseline Agent Fails",
                "Baseline has no healing. It tries the old v1 format and fails.",
                replay=True
            )
            console.print("[cyan]→[/cyan] Running baseline agent on v2_full...")
            console.print("\n[bold]API Attempts:[/bold]")
            console.print(f"  Attempt 1: [red]Status {data['status']}[/red]")
            console.print(f"  API calls: {data['api_attempts']}")
            console.print(f"  Model calls: {data['model_calls']}")
            console.print(f"  Tokens used: {data['tokens']}\n")
            console.print(f"[red]✗[/red] Final result: {data['status']}\n")
            wait_for_enter()
        
        elif event_type == "healing_v2":
            print_scene_header(
                "Scene 4: DriftShield Heals",
                "The healing agent detects drift and adapts automatically.",
                replay=True
            )
            console.print("[cyan]→[/cyan] Running healing agent with event monitoring...\n")
            
            # Replay events
            for event_name, event_data in data['events']:
                if event_name == "intercepted" and not event_data["ok"]:
                    console.print(f"  [yellow]⚡[/yellow] Intercepted failed call (status {event_data['status_code']})")
                elif event_name == "classified":
                    console.print(f"  [cyan]🔍[/cyan] Classified as: [bold]{event_data['kind']}[/bold]")
                elif event_name == "contract_fetched":
                    console.print(f"  [cyan]📄[/cyan] Fetched live contract: [dim]{event_data['contract_hash'][:16]}...[/dim]")
                elif event_name == "diff":
                    console.print(f"  [cyan]📊[/cyan] Detected {len(event_data['changes'])} change(s):")
                    for change in event_data['changes']:
                        if change["type"] == "renamed":
                            console.print(f"      • Renamed: {change['removed']} → {change['added']}")
                        elif change["type"] == "nested":
                            console.print(f"      • Nested under: {change['added']}")
                elif event_name == "provenance_checked":
                    console.print(f"  [cyan]🔐[/cyan] Provenance checked")
                elif event_name == "validated":
                    console.print(f"  [green]✓[/green] Payload validated")
                elif event_name == "patched":
                    console.print(f"  [green]🔧[/green] Registry patched: v{event_data['version_before']} → v[bold]{event_data['version_after']}[/bold]")
                elif event_name == "retried":
                    if event_data["ok"]:
                        console.print(f"  [green]✓[/green] Retry succeeded (status {event_data['status_code']})")
                time.sleep(0.1)
            
            console.print(f"\n[green]✓[/green] Final result: {data['status']}")
            console.print(f"  Registry: v1 → v[bold]{data['registry_version']}[/bold]")
            console.print(f"  Recovery time: [bold]{data['recovery_time']:.2f}s[/bold]\n")
            wait_for_enter()
        
        elif event_type == "patch_log":
            console.print("[cyan]→[/cyan] Last patch log entry:")
            console.print(f"  Tool: [bold]{data['tool']}[/bold]")
            console.print(f"  Version: {data['registry_version_before']} → {data['registry_version_after']}")
            console.print(f"  Outcome: [bold]{data['outcome']}[/bold]")
            console.print(f"  Hash: [dim]{data['contract_hash_patched_against'][:16]}...[/dim]\n")
            wait_for_enter()
        
        elif event_type == "mutate_billing":
            print_scene_header(
                "Scene 5: Safe Stop",
                "Some drifts cannot be healed safely. The agent refuses gracefully.",
                replay=True
            )
            console.print("[cyan]→[/cyan] Mutating to header_billing (requires unavailable header)...")
            console.print("[green]✓[/green] API mutated to header_billing\n")
            console.print("[cyan]→[/cyan] Running healing agent...\n")
        
        elif event_type == "safe_stop":
            console.print(f"  [yellow]⚠[/yellow] Safe stop triggered")
            console.print(f"      Reason: {data['reason']}\n")
            console.print(f"[red]⚠[/red] Status: [bold]{data['status']}[/bold]")
            console.print(f"  Reason: [italic]{data['reason']}[/italic]\n")
            console.print("[cyan]💡[/cyan] Fix proposal:")
            console.print("  Add X-Billing-Region header to configuration")
            console.print("  or have human operator provide the value\n")
            wait_for_enter()
        
        elif event_type == "results":
            print_scene_header(
                "Scene 6: Evaluation Results",
                "Summary of agent performance from evaluation runs.",
                replay=True
            )
            console.print("[cyan]→[/cyan] Loading evaluation results...\n")
            
            table = Table(title="Agent Performance Metrics", box=box.ROUNDED)
            table.add_column("Agent", style="cyan")
            table.add_column("ZTAR", justify="right")
            table.add_column("Correct Refusal", justify="right")
            table.add_column("MTTR", justify="right")
            
            for agent_name, metrics in data['metrics'].items():
                table.add_row(
                    agent_name,
                    f"{metrics['ztar']:.1f}%",
                    f"{metrics['correct_refusal_rate']:.1f}%",
                    metrics['mttr']
                )
            
            console.print(table)
            console.print()
    
    console.print("\n[green]✓[/green] Replay complete!\n")


def create_offline_recording():
    """Create a demo recording from predefined fixtures (no API calls).
    
    This generates a complete demo recording without making any network calls,
    LLM calls, or starting agents. Perfect for creating presentation videos
    without consuming API quota.
    
    All events are clearly labeled as simulated demo data.
    """
    console.print("[cyan]Creating offline demo recording from fixtures...[/cyan]")
    console.print("[dim]No API calls or network activity will be made[/dim]\n")
    
    output_path = Path("results/demo_recording.json")
    output_path.parent.mkdir(exist_ok=True)
    
    # Deterministic timestamps for consistent replay
    events = []
    t = 0.0
    
    # ===== SCENE 1: API v1 - Both agents succeed =====
    events.append({
        "type": "reset",
        "timestamp": t,
        "data": {
            "version": "v1",
            "_note": "SIMULATED: Demo fixture data, not from live API"
        }
    })
    t += 0.5
    
    events.append({
        "type": "baseline_v1",
        "timestamp": t,
        "data": {
            "success": True,
            "status": "ok",
            "tokens": 87,
            "final_text": "The user's name is Asha Rao",
            "_note": "SIMULATED: Demo fixture data, not from live Gemini"
        }
    })
    t += 0.5
    
    events.append({
        "type": "healing_v1",
        "timestamp": t,
        "data": {
            "success": True,
            "status": "ok",
            "tokens": 92,
            "registry_version": 1,
            "final_text": "The user's name is Asha Rao",
            "_note": "SIMULATED: Demo fixture data, not from live Gemini"
        }
    })
    t += 2.0
    
    # ===== SCENE 2: The Break - Mutate to v2_full =====
    events.append({
        "type": "mutate",
        "timestamp": t,
        "data": {
            "contract": "v2_full",
            "old_hash": "a1b2c3d4e5f67890",
            "new_hash": "f09e8d7c6b5a4321",
            "_note": "SIMULATED: Demo fixture hashes"
        }
    })
    t += 2.0
    
    # ===== SCENE 3: Baseline Fails =====
    events.append({
        "type": "baseline_v2",
        "timestamp": t,
        "data": {
            "success": False,
            "status": "failed",
            "api_attempts": 3,
            "model_calls": 2,
            "tokens": 156,
            "_note": "SIMULATED: Demo shows baseline failing on drift"
        }
    })
    t += 2.0
    
    # ===== SCENE 4: DriftShield Heals =====
    # Simulate the healing workflow events
    healing_events = [
        ("intercepted", {
            "ok": False,
            "status_code": 400,
            "_note": "SIMULATED: Demo shows API returning error"
        }),
        ("classified", {
            "kind": "drift",
            "_note": "SIMULATED: Demo shows drift classification"
        }),
        ("contract_fetched", {
            "contract_hash": "f09e8d7c6b5a4321abcd",
            "_note": "SIMULATED: Demo shows contract fetch"
        }),
        ("diff", {
            "changes": [
                {"type": "renamed", "removed": "user_id", "added": "id"},
                {"type": "nested", "added": "target"}
            ],
            "_note": "SIMULATED: Demo shows schema diff detection"
        }),
        ("provenance_checked", {
            "_note": "SIMULATED: Demo shows provenance validation"
        }),
        ("validated", {
            "_note": "SIMULATED: Demo shows payload validation"
        }),
        ("patched", {
            "version_before": 1,
            "version_after": 2,
            "_note": "SIMULATED: Demo shows registry patch"
        }),
        ("retried", {
            "ok": True,
            "status_code": 200,
            "_note": "SIMULATED: Demo shows successful retry"
        })
    ]
    
    events.append({
        "type": "healing_v2",
        "timestamp": t,
        "data": {
            "success": True,
            "status": "healed",
            "registry_version": 2,
            "recovery_time": 2.34,
            "tokens": 245,
            "events": healing_events,
            "_note": "SIMULATED: Demo fixture showing healing workflow"
        }
    })
    t += 0.5
    
    # Patch log entry
    events.append({
        "type": "patch_log",
        "timestamp": t,
        "data": {
            "tool": "lookup_user",
            "registry_version_before": 1,
            "registry_version_after": 2,
            "outcome": "success",
            "contract_hash_patched_against": "f09e8d7c6b5a4321",
            "_note": "SIMULATED: Demo fixture patch log"
        }
    })
    t += 2.0
    
    # ===== SCENE 5: Safe Stop =====
    events.append({
        "type": "mutate_billing",
        "timestamp": t,
        "data": {
            "contract": "header_billing",
            "_note": "SIMULATED: Demo shows mutation to unsafe schema"
        }
    })
    t += 0.5
    
    events.append({
        "type": "safe_stop",
        "timestamp": t,
        "data": {
            "status": "safe_stop",
            "reason": "Cannot resolve required header: X-Billing-Region",
            "_note": "SIMULATED: Demo shows safe refusal of unheatable drift"
        }
    })
    t += 2.0
    
    # ===== SCENE 6: Results =====
    events.append({
        "type": "results",
        "timestamp": t,
        "data": {
            "metrics": {
                "healing_agent": {
                    "ztar": 93.3,
                    "correct_refusal_rate": 100.0,
                    "mttr": "2.1s"
                },
                "baseline_agent": {
                    "ztar": 33.3,
                    "correct_refusal_rate": 0.0,
                    "mttr": "N/A"
                }
            },
            "_note": "SIMULATED: Demo fixture metrics for presentation"
        }
    })
    
    # Create recording structure
    recording = {
        "version": "1.0",
        "total_duration": t,
        "events": events,
        "_metadata": {
            "source": "offline_fixture_generator",
            "created_for": "presentation_demo",
            "note": "All data is simulated for demonstration purposes. Not from live API calls."
        }
    }
    
    # Save recording
    with open(output_path, "w") as f:
        json.dump(recording, f, indent=2)
    
    console.print(f"[green]✓[/green] Offline recording created: {output_path}")
    console.print(f"  Total events: {len(events)}")
    console.print(f"  Duration: {t:.1f}s")
    console.print(f"  All scenes included: 1-6")
    console.print(f"\n[cyan]→[/cyan] To replay: [bold]python demo.py --replay[/bold]")
    console.print(f"[dim]Note: All data is simulated demo fixtures, not from live API[/dim]\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DriftShield demonstration")
    parser.add_argument("--record", action="store_true", help="Record demo for replay")
    parser.add_argument("--replay", action="store_true", help="Replay recorded demo")
    parser.add_argument("--create-offline-recording", action="store_true", 
                       help="Create demo recording from fixtures (no API calls)")
    
    args = parser.parse_args()
    
    if args.create_offline_recording:
        create_offline_recording()
    elif args.replay:
        run_demo_replay()
    else:
        run_demo_live()


if __name__ == "__main__":
    main()

