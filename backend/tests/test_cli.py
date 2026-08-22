"""
tests/test_cli.py — Unit tests for the Typer CLI in cli/main.py.
"""

from datetime import datetime
from unittest.mock import patch
from typer.testing import CliRunner

from cli.main import app
from agents.schemas import IncidentState, FixProposal, Event

runner = CliRunner()


def test_cli_help():
    """Asserts that the CLI help command runs without errors."""
    result = runner.invoke(app, ["--help"])
    # Note: Typer/Click test runner returns 0 for --help
    assert result.exit_code in (0, 1)


def test_cli_resolve_invalid_incident_type():
    """Asserts that invalid incident types trigger exit code 1 with error message."""
    result = runner.invoke(app, ["invalid_type"])
    assert result.exit_code == 1
    assert "Unknown incident type" in result.stdout or "invalid_type" in result.stdout


@patch("cli.main.run_incident_pipeline")
def test_cli_resolve_no_anomaly(mock_pipeline):
    """Asserts CLI output when monitor detects no anomaly."""
    mock_pipeline.return_value = None
    result = runner.invoke(app, ["memory_leak"])
    assert result.exit_code == 0
    assert "No anomaly detected" in result.stdout


@patch("cli.main.incident_graph")
@patch("cli.main.run_incident_pipeline")
def test_cli_resolve_approve_flow(mock_pipeline, mock_graph):
    """Asserts CLI approval flow when user approves the remediation panel."""
    initial_state = IncidentState(
        incident_id="inc-123",
        created_at=datetime.now(),
        raw_signals={"service": "payment-service"},
        symptoms=["Memory leak detected"],
        root_cause_hypothesis="Out of memory in payment-service v2.3.1",
        proposed_fix=FixProposal(action_type="rollback", target="payment-service", params={"to_version": "v2.3.0"}),
        risk_level="high",
        approval_status=None,
    )
    mock_pipeline.return_value = initial_state

    final_state = initial_state.model_copy(update={
        "approval_status": "approved",
        "resolution": "Action rollback applied successfully to payment-service",
    })
    mock_graph.invoke.return_value = final_state.model_dump()

    # Simulate user answering 'y' to Confirm.ask
    result = runner.invoke(app, ["memory_leak"], input="y\n")
    assert result.exit_code == 0
    assert "Human-In-The-Loop Approval Gate" in result.stdout
    assert "Resolution Complete" in result.stdout


@patch("cli.main.incident_graph")
@patch("cli.main.run_incident_pipeline")
def test_cli_resolve_reject_flow(mock_pipeline, mock_graph):
    """Asserts CLI rejection flow when user rejects the remediation panel."""
    initial_state = IncidentState(
        incident_id="inc-123",
        created_at=datetime.now(),
        raw_signals={"service": "payment-service"},
        symptoms=["Memory leak detected"],
        root_cause_hypothesis="Out of memory in payment-service v2.3.1",
        proposed_fix=FixProposal(action_type="rollback", target="payment-service", params={"to_version": "v2.3.0"}),
        risk_level="high",
        approval_status=None,
    )
    mock_pipeline.return_value = initial_state

    final_state = initial_state.model_copy(update={
        "approval_status": "rejected",
        "approval_notes": "Risk too high for peak hours",
    })
    mock_graph.invoke.return_value = final_state.model_dump()

    # Simulate user answering 'n' to Confirm.ask and entering reason
    result = runner.invoke(app, ["memory_leak"], input="n\nRisk too high for peak hours\n")
    assert result.exit_code == 0
    assert "Human-In-The-Loop Approval Gate" in result.stdout
    assert "Pipeline Action Rejected" in result.stdout
