import pytest
from dotenv import load_dotenv
from simulator.incident_generator import IncidentGenerator
from agents.monitor import run_monitor_agent, detect_anomaly

# Load environment variables (GROQ_API_KEY)
load_dotenv()

def test_deterministic_detection():
    gen = IncidentGenerator()
    
    # Normal logs should not trigger anomaly
    # Using private method just for testing the noise
    normal_logs = gen._generate_noise("web-service", 5)
    assert detect_anomaly(normal_logs) is False
    
    # Incident logs should trigger anomaly
    incident_logs = gen.get_incident("bad_deploy")
    assert detect_anomaly(incident_logs) is True

def test_monitor_agent_llm_call():
    gen = IncidentGenerator()
    incident_logs = gen.get_incident("dependency_timeout")
    
    # Run the agent (this calls Groq)
    initial_state = run_monitor_agent(incident_logs)
    
    assert initial_state is not None
    assert initial_state.incident_id.startswith("inc_")
    assert len(initial_state.symptoms) > 0
    assert isinstance(initial_state.raw_signals, dict)
    assert len(initial_state.event_log) == 1
    assert initial_state.event_log[0].source_agent == "Monitor"