from typing import List, Tuple, Optional
from langgraph.graph import StateGraph, START, END

from agents.schemas import IncidentState
from agents.monitor import run_monitor_agent
from agents.diagnosis import run_diagnosis_agent
from agents.remediation import run_remediation_agent


# --- Node Wrappers ---

def diagnosis_node(state: IncidentState) -> IncidentState:
    """Node wrapper for Diagnosis Agent."""
    return run_diagnosis_agent(state)


def remediation_node(state: IncidentState) -> IncidentState:
    """Node wrapper for Remediation Agent."""
    return run_remediation_agent(state)


# --- Graph Construction ---

builder = StateGraph(IncidentState)

# Add nodes
builder.add_node("diagnosis", diagnosis_node)
builder.add_node("remediation", remediation_node)

# Define edges
builder.add_edge(START, "diagnosis")
builder.add_edge("diagnosis", "remediation")
builder.add_edge("remediation", END)

# Compile graph
incident_graph = builder.compile()


# --- Pipeline Execution Function ---

def run_incident_pipeline(logs: List[Tuple[str, str, str]]) -> Optional[IncidentState]:
    """
    Executes the multi-agent incident response pipeline.
    1. Monitor Agent detects anomalies in logs and initializes IncidentState.
    2. If an anomaly is detected, invokes incident_graph (Diagnosis -> Remediation).
    3. Returns the updated final IncidentState (or None if no anomaly detected).
    """
    initial_state = run_monitor_agent(logs)
    if initial_state is None:
        return None

    result = incident_graph.invoke(initial_state)
    if isinstance(result, dict):
        return IncidentState.model_validate(result)

    return result
