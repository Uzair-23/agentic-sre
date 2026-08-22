"""
cli/main.py — Command-Line Interface for the agentic-sre pipeline.

Allows SRE operators to trigger simulated incident investigations, view autonomous
agent diagnoses and proposed remediation actions, and approve or reject actions via HITL gate.
"""

import uuid
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from langgraph.types import Command

from simulator.incident_generator import IncidentGenerator
from agents.graph import run_incident_pipeline, incident_graph
from agents.schemas import IncidentState

# App setup
app = typer.Typer(help="Agentic-SRE CLI: Multi-Agent Incident Response & Remediation Engine")
console = Console()


@app.command()
def resolve(
    incident_type: str = typer.Argument(
        ...,
        help="Type of incident: memory_leak, bad_deploy, dependency_timeout, traffic_spike, config_drift",
    )
) -> None:
    """
    Triggers an incident investigation for the specified incident type.
    """
    thread_id = str(uuid.uuid4())
    generator = IncidentGenerator()

    try:
        logs = generator.get_incident(incident_type)
    except (ValueError, KeyError) as err:
        console.print(f"[bold red]Error:[/bold red] {err}")
        raise typer.Exit(code=1)

    console.print(
        f"[bold blue]Starting Investigation[/bold blue] for incident type: [yellow]{incident_type}[/yellow] "
        f"(thread_id: [dim]{thread_id[:8]}...[/dim])"
    )

    # 1. Run Pipeline — pauses at approval_gate_node if incident detected
    state: IncidentState | None = run_incident_pipeline(logs, thread_id=thread_id)

    if state is None:
        console.print("[bold green]No anomaly detected.[/bold green]")
        return

    # 2. Human-In-The-Loop (HITL) Display & Execution
    if state.proposed_fix and not state.approval_status:
        hypothesis = state.root_cause_hypothesis or "N/A"
        action = state.proposed_fix.action_type
        target = state.proposed_fix.target
        risk = state.risk_level.upper() if state.risk_level else "UNKNOWN"

        panel_content = (
            f"[bold cyan]Root Cause Hypothesis:[/bold cyan] {hypothesis}\n"
            f"[bold cyan]Action:[/bold cyan] {action}\n"
            f"[bold cyan]Target:[/bold cyan] {target}\n"
            f"[bold cyan]Risk Level:[/bold cyan] {risk}"
        )

        console.print(
            Panel(
                panel_content,
                title="[bold yellow]Human-In-The-Loop Approval Gate[/bold yellow]",
                expand=False,
            )
        )

        approved = Confirm.ask("Do you approve this remediation action?")

        config = {"configurable": {"thread_id": thread_id}}

        if approved:
            resume_cmd = Command(resume={"action": "approve", "reason": "Approved via CLI"})
            raw_final = incident_graph.invoke(resume_cmd, config=config)
        else:
            reason = Prompt.ask("Enter rejection reason")
            resume_cmd = Command(resume={"action": "reject", "reason": reason})
            raw_final = incident_graph.invoke(resume_cmd, config=config)

        final_state: IncidentState = (
            IncidentState.model_validate(raw_final) if isinstance(raw_final, dict) else raw_final
        )
    else:
        final_state = state

    # 3. Final Output
    if final_state.approval_status == "approved":
        console.print(
            f"[bold green]Pipeline Resolution Complete:[/bold green] {final_state.resolution}"
        )
    else:
        console.print(
            f"[bold red]Pipeline Action Rejected:[/bold red] {final_state.approval_notes}"
        )


if __name__ == "__main__":
    app()
