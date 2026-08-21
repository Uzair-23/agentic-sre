from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import pytest
from pydantic import ValidationError

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents.schemas import IncidentState, FixProposal
from agents.remediation import RemediationOutput, run_remediation_agent


def test_remediation_output_validation():
    valid = RemediationOutput(
        action_type="rollback",
        target="payment-service",
        params={"to_version": "v2.3.0"},
        justification="Rollback recent deploy to resolve memory leak.",
    )
    assert valid.action_type == "rollback"
    assert valid.target == "payment-service"

    with pytest.raises(ValidationError):
        RemediationOutput(
            action_type="rm -rf /",  # Invalid action type
            target="payment-service",
            params={},
            justification="Arbitrary command",
        )


def test_run_remediation_agent_state_update_and_immutability():
    initial_state = IncidentState(
        incident_id="inc_rem_101",
        created_at=datetime.now(),
        symptoms=["OOMKilled process terminated", "Memory usage 96%"],
        raw_signals={"service": "payment-service", "metric": "memory"},
        root_cause_hypothesis="Memory leak introduced in deploy v2.3.1",
        confidence_score=0.9,
        event_log=[],
    )

    updated_state = run_remediation_agent(initial_state)

    # Immutability check
    assert initial_state.proposed_fix is None
    assert len(initial_state.event_log) == 0

    # Updated state checks
    assert updated_state.proposed_fix is not None
    assert isinstance(updated_state.proposed_fix, FixProposal)
    assert updated_state.proposed_fix.action_type in ["rollback", "restart_service", "scale_up", "toggle_config_flag"]
    assert updated_state.proposed_fix.target == "payment-service"

    # Event log check
    assert len(updated_state.event_log) == 1
    assert updated_state.event_log[0].source_agent == "Remediation"
    assert updated_state.event_log[0].action == "Fix Proposed"
