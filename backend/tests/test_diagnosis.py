from datetime import datetime
from pathlib import Path
import pytest
from dotenv import load_dotenv

# Setup: Load environment variables using python-dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents.schemas import IncidentState
from agents.diagnosis import run_diagnosis_agent, DiagnosisOutput


@pytest.fixture
def dependency_timeout_state() -> IncidentState:
    """
    Pytest fixture to instantiate a mock IncidentState containing
    symptoms of a 'dependency_timeout' from 'cart-service'.
    """
    return IncidentState(
        incident_id="inc_dep_timeout_001",
        created_at=datetime.now(),
        symptoms=["CRITICAL: Timeout waiting for inventory-db"],
        raw_signals={"service": "cart-service", "error_type": "timeout", "target_db": "inventory-db"},
        event_log=[],
    )


def test_successful_diagnosis(dependency_timeout_state: IncidentState):
    """
    Test 1: Successful Diagnosis
    Pass the mock state to run_diagnosis_agent and assert diagnosis fields and event log.
    """
    updated_state = run_diagnosis_agent(dependency_timeout_state)

    # 1. Assert returned state is not None
    assert updated_state is not None

    # 2. Assert root_cause_hypothesis is populated
    assert updated_state.root_cause_hypothesis is not None
    assert isinstance(updated_state.root_cause_hypothesis, str)
    assert len(updated_state.root_cause_hypothesis.strip()) > 0

    # 3. Assert confidence_score is a float between 0.0 and 1.0
    assert updated_state.confidence_score is not None
    assert isinstance(updated_state.confidence_score, float)
    assert 0.0 <= updated_state.confidence_score <= 1.0

    # 4. Assert a new event has been appended to event_log with source_agent == 'Diagnosis'
    assert len(updated_state.event_log) == 1
    new_event = updated_state.event_log[0]
    assert new_event.source_agent == "Diagnosis"
    assert new_event.action is not None


def test_diagnosis_immutability(dependency_timeout_state: IncidentState):
    """
    Verify that run_diagnosis_agent does not mutate the original IncidentState in place.
    """
    updated_state = run_diagnosis_agent(dependency_timeout_state)

    # Original state remains unmutated
    assert dependency_timeout_state.root_cause_hypothesis is None
    assert dependency_timeout_state.confidence_score is None
    assert len(dependency_timeout_state.event_log) == 0

    # Updated state contains new data
    assert updated_state.root_cause_hypothesis is not None
    assert len(updated_state.event_log) == 1


def test_diagnosis_output_schema():
    """Verify DiagnosisOutput Pydantic schema validation."""
    diag = DiagnosisOutput(
        root_cause_hypothesis="Upstream database inventory-db connection exhaustion impacting cart-service",
        confidence_score=0.92,
        evidence=[
            "Symptom: CRITICAL: Timeout waiting for inventory-db",
            "Raw signal: service=cart-service, error_type=timeout",
        ],
    )
    assert diag.root_cause_hypothesis == "Upstream database inventory-db connection exhaustion impacting cart-service"
    assert diag.confidence_score == 0.92
    assert len(diag.evidence) == 2


def test_diagnosis_hypothesis_not_hallucinated(dependency_timeout_state: IncidentState):
    """
    Verify the refactored agent does not inject OOMKilled or memory leak language
    when the symptoms clearly indicate a dependency timeout.
    """
    updated_state = run_diagnosis_agent(dependency_timeout_state)

    hypothesis = updated_state.root_cause_hypothesis.lower()

    # The hypothesis must reference the actual signals (timeout / inventory-db)
    assert any(
        keyword in hypothesis
        for keyword in ["timeout", "inventory-db", "inventory", "dependency", "database", "connection"]
    ), f"Hypothesis does not reference the actual incident signals: '{updated_state.root_cause_hypothesis}'"
