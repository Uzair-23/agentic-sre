from datetime import datetime
from pathlib import Path
import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents.schemas import IncidentState, FixProposal
from agents.remediation import RemediationOutput, run_remediation_agent

VALID_ACTION_TYPES = ["rollback", "restart_service", "scale_up", "toggle_config_flag"]


@pytest.fixture
def mock_diagnosed_state() -> IncidentState:
    """Construct a mock IncidentState with a diagnosed hypothesis."""
    return IncidentState(
        incident_id="inc_rem_2026",
        created_at=datetime.now(),
        symptoms=["Memory usage climbing steadily to 96%", "OOMKilled restart on payment-service"],
        raw_signals={"service": "payment-service", "metric": "memory", "peak": "96%"},
        root_cause_hypothesis="Memory leak introduced in deploy v2.3.1 on payment-service",
        confidence_score=0.87,
        event_log=[],
    )


def test_successful_remediation(mock_diagnosed_state: IncidentState):
    """Test run_remediation_agent proposes a valid FixProposal without mutating initial state."""
    updated_state = run_remediation_agent(mock_diagnosed_state)

    # 1. Returned state is not None
    assert updated_state is not None

    # 2. proposed_fix is an instance of FixProposal
    assert updated_state.proposed_fix is not None
    assert isinstance(updated_state.proposed_fix, FixProposal)

    # 3. proposed_fix.action_type is one of approved action types
    assert updated_state.proposed_fix.action_type in VALID_ACTION_TYPES

    # 4. proposed_fix.target is not empty
    assert updated_state.proposed_fix.target is not None
    assert isinstance(updated_state.proposed_fix.target, str)
    assert len(updated_state.proposed_fix.target.strip()) > 0

    # 5. event_log has a new event with source_agent == 'Remediation'
    assert len(updated_state.event_log) == 1
    remediation_event = updated_state.event_log[0]
    assert remediation_event.source_agent == "Remediation"
    assert remediation_event.action == "Fix Proposed"

    # 6. Original state was not mutated in place
    assert mock_diagnosed_state.proposed_fix is None
    assert len(mock_diagnosed_state.event_log) == 0


def test_remediation_output_validation():
    """Test schema validation for RemediationOutput."""
    valid_output = RemediationOutput(
        action_type="rollback",
        target="payment-service",
        params={"to_version": "v2.3.0"},
        justification="Rollback recent deployment to resolve memory leak.",
    )
    assert valid_output.action_type == "rollback"
    assert valid_output.target == "payment-service"

    with pytest.raises(ValidationError):
        RemediationOutput(
            action_type="unauthorized_command",  # Invalid action type
            target="payment-service",
            params={},
            justification="Arbitrary command attempt",
        )
