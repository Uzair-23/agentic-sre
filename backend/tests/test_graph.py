from pathlib import Path
from dotenv import load_dotenv

# Setup: Load environment variables using python-dotenv
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from simulator.incident_generator import IncidentGenerator
from agents.graph import run_incident_pipeline, incident_graph
from agents.schemas import IncidentState, FixProposal

VALID_ACTION_TYPES = ["rollback", "restart_service", "scale_up", "toggle_config_flag"]


def test_graph_export():
    """Verify that incident_graph is compiled and exported correctly."""
    assert incident_graph is not None


def test_memory_leak_incident():
    """Test 1: End-to-end Memory Leak Incident."""
    generator = IncidentGenerator()
    logs = generator.get_incident("memory_leak")

    final_state = run_incident_pipeline(logs)

    assert final_state is not None
    assert isinstance(final_state, IncidentState)
    assert final_state.root_cause_hypothesis is not None
    assert len(final_state.root_cause_hypothesis.strip()) > 0
    assert final_state.confidence_score is not None
    assert 0.0 <= final_state.confidence_score <= 1.0

    assert final_state.proposed_fix is not None
    assert isinstance(final_state.proposed_fix, FixProposal)
    assert final_state.proposed_fix.action_type in VALID_ACTION_TYPES

    # Assert event_log contains entries from all participating agents
    participating_agents = {evt.source_agent for evt in final_state.event_log}
    assert {"Monitor", "Diagnosis", "Remediation"}.issubset(participating_agents)


def test_bad_deploy_incident():
    """Test 2: End-to-end Bad Deploy Incident."""
    generator = IncidentGenerator()
    logs = generator.get_incident("bad_deploy")

    final_state = run_incident_pipeline(logs)

    assert final_state is not None
    assert isinstance(final_state, IncidentState)
    assert final_state.root_cause_hypothesis is not None
    assert final_state.confidence_score is not None

    assert final_state.proposed_fix is not None
    assert final_state.proposed_fix.action_type in VALID_ACTION_TYPES

    participating_agents = {evt.source_agent for evt in final_state.event_log}
    assert {"Monitor", "Diagnosis", "Remediation"}.issubset(participating_agents)


def test_dependency_timeout_incident():
    """Test 3: End-to-end Dependency Timeout Incident."""
    generator = IncidentGenerator()
    logs = generator.get_incident("dependency_timeout")

    final_state = run_incident_pipeline(logs)

    assert final_state is not None
    assert isinstance(final_state, IncidentState)
    assert final_state.root_cause_hypothesis is not None
    assert final_state.confidence_score is not None

    assert final_state.proposed_fix is not None
    assert final_state.proposed_fix.action_type in VALID_ACTION_TYPES

    participating_agents = {evt.source_agent for evt in final_state.event_log}
    assert {"Monitor", "Diagnosis", "Remediation"}.issubset(participating_agents)


def test_normal_traffic_benign():
    """Test 4: Normal Traffic (Benign)."""
    generator = IncidentGenerator()
    normal_logs = generator._generate_noise("payment-service", 10)

    result = run_incident_pipeline(normal_logs)
    assert result is None
