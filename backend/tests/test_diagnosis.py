from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents.schemas import IncidentState
from agents.diagnosis import (
    query_deploy_history,
    query_service_dependencies,
    query_recent_logs,
    DiagnosisOutput,
    run_diagnosis_agent,
)


def test_mock_tools():
    # query_deploy_history
    assert query_deploy_history.invoke({"service": "payment-service"}) == "v2.3.1 deployed 10 mins ago"
    assert query_deploy_history.invoke({"service": "auth-service"}) == "v2.3.1 deployed 10 mins ago"
    assert query_deploy_history.invoke({"service": "other-service"}) == "No recent deploys"

    # query_service_dependencies
    assert query_service_dependencies.invoke({"service": "cart-service"}) == "Depends on: inventory-db, payment-service"
    assert query_service_dependencies.invoke({"service": "other-service"}) == "No known dependencies"

    # query_recent_logs
    assert query_recent_logs.invoke({"service": "payment-service", "window_minutes": 15}) in ["ERROR 500", "OOMKilled"]
    assert query_recent_logs.invoke({"service": "other-service", "window_minutes": 10}) in ["ERROR 500", "OOMKilled"]


def test_diagnosis_output_schema():
    diag = DiagnosisOutput(
        root_cause_hypothesis="Memory leak in payment-service",
        confidence_score=0.85,
        evidence=["v2.3.1 deployed 10 mins ago", "OOMKilled logs"],
    )
    assert diag.root_cause_hypothesis == "Memory leak in payment-service"
    assert diag.confidence_score == 0.85
    assert len(diag.evidence) == 2


def test_run_diagnosis_agent_immutability_and_state_update():
    initial_state = IncidentState(
        incident_id="inc_test_101",
        created_at=datetime.now(),
        symptoms=["High latency on cart-service", "500 Internal Server Errors"],
        raw_signals={"service": "payment-service", "error_rate": "25%"},
        event_log=[],
    )

    updated_state = run_diagnosis_agent(initial_state)

    # Check that initial state was NOT mutated in place
    assert initial_state.root_cause_hypothesis is None
    assert initial_state.confidence_score is None
    assert len(initial_state.event_log) == 0

    # Check updated state has new diagnosis values
    assert updated_state.root_cause_hypothesis is not None
    assert isinstance(updated_state.root_cause_hypothesis, str)
    assert updated_state.confidence_score is not None
    assert 0.0 <= updated_state.confidence_score <= 1.0

    # Check event log was appended to
    assert len(updated_state.event_log) == 1
    assert updated_state.event_log[0].source_agent == "Diagnosis"
    assert updated_state.event_log[0].action == "Diagnosis Completed"
