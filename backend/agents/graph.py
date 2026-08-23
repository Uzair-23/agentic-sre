from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

from agents.schemas import IncidentState, Event
from agents.monitor import run_monitor_agent
from agents.diagnosis import run_diagnosis_agent
from agents.remediation import run_remediation_agent
from agents.postmortem import run_postmortem_agent

from guardrails.risk_classifier import classify_risk
from guardrails.pii_scrubber import scrub_pii
from guardrails.injection_guard import detect_prompt_injection


# --- Node Definitions ---

def diagnosis_node(state: IncidentState) -> IncidentState:
    """
    Diagnosis node wrapper with prompt injection defense check.
    If prompt injection is detected in raw_signals or symptoms, aborts further reasoning.
    """
    raw_signals_text = str(state.raw_signals)
    symptoms_text = " ".join(state.symptoms)

    if detect_prompt_injection(raw_signals_text) or detect_prompt_injection(symptoms_text):
        abort_event = Event(
            timestamp=datetime.now(),
            source_agent="Diagnosis",
            action="Pipeline Aborted",
            details="Prompt injection detected, aborting",
        )
        return state.model_copy(update={
            "root_cause_hypothesis": "Prompt injection attempt detected",
            "confidence_score": 1.0,
            "event_log": list(state.event_log) + [abort_event],
        })

    return run_diagnosis_agent(state)


def remediation_node(state: IncidentState) -> IncidentState:
    """
    Remediation node wrapper.
    Generates a remediation proposal and classifies the risk level.
    """
    if state.root_cause_hypothesis == "Prompt injection attempt detected":
        return state

    updated_state = run_remediation_agent(state)

    if updated_state.proposed_fix:
        risk = classify_risk(
            updated_state.proposed_fix.action_type,
            updated_state.proposed_fix.target,
        )
        updated_state = updated_state.model_copy(update={"risk_level": risk})

    return updated_state


def approval_gate_node(state: IncidentState) -> IncidentState:
    """
    Human-In-The-Loop (HITL) approval gate node.
    Pauses execution via interrupt() waiting for human approval/rejection.
    """
    if state.root_cause_hypothesis == "Prompt injection attempt detected":
        return state.model_copy(update={
            "approval_status": "rejected",
            "approval_notes": "Aborted due to security policy violation",
        })

    human_response = interrupt({
        "proposal": state.proposed_fix,
        "risk": state.risk_level,
    })

    action = human_response.get("action") if isinstance(human_response, dict) else "reject"
    reason = human_response.get("reason", "") if isinstance(human_response, dict) else ""

    if action == "approve":
        status = "approved"
        notes = reason or "Approved by operator"
        event_details = "Fix proposal approved by operator"
    else:
        status = "rejected"
        notes = reason or "Rejected by operator"
        event_details = f"Fix proposal rejected. Reason: {notes}"

    approval_event = Event(
        timestamp=datetime.now(),
        source_agent="ApprovalGate",
        action=status.capitalize(),
        details=event_details,
    )

    return state.model_copy(update={
        "approval_status": status,
        "approval_notes": notes,
        "event_log": list(state.event_log) + [approval_event],
    })


def executor_node(state: IncidentState) -> IncidentState:
    """
    Simulates execution of approved remediation actions.
    """
    target = state.proposed_fix.target if state.proposed_fix else "unknown"
    action = state.proposed_fix.action_type if state.proposed_fix else "remediation"
    res_str = f"Action {action} applied successfully to {target}"

    exec_event = Event(
        timestamp=datetime.now(),
        source_agent="Executor",
        action="Execution Complete",
        details="Action applied successfully",
    )

    return state.model_copy(update={
        "resolution": res_str,
        "event_log": list(state.event_log) + [exec_event],
    })


def postmortem_node(state: IncidentState) -> IncidentState:
    """
    Phase 6 Postmortem node.
    Runs after executor_node on the approved path.
    Generates a structured postmortem and persists a threshold adjustment
    to simulator/thresholds.json for the Monitor feedback loop.
    """
    # Skip postmortem for security-aborted incidents
    if state.root_cause_hypothesis == "Prompt injection attempt detected":
        return state
    return run_postmortem_agent(state)


# --- Conditional Routing ---

def route_after_approval(state: IncidentState) -> str:
    """
    Routes after approval gate:
    - If approved (or security abort), route to executor.
    - If rejected, route back to diagnosis for second pass.
    """
    if state.approval_status == "approved" or state.root_cause_hypothesis == "Prompt injection attempt detected":
        return "executor"
    return "diagnosis"


# --- Graph Construction ---

builder = StateGraph(IncidentState)

# Add nodes
builder.add_node("diagnosis", diagnosis_node)
builder.add_node("remediation", remediation_node)
builder.add_node("approval_gate", approval_gate_node)
builder.add_node("executor", executor_node)
builder.add_node("postmortem", postmortem_node)

# Define edges
builder.add_edge(START, "diagnosis")
builder.add_edge("diagnosis", "remediation")
builder.add_edge("remediation", "approval_gate")

# Conditional edge after approval gate
builder.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {
        "executor": "executor",
        "diagnosis": "diagnosis",
    },
)

# Route: executor -> postmortem -> END
builder.add_edge("executor", "postmortem")
builder.add_edge("postmortem", END)

# Compile graph with InMemorySaver checkpointer
checkpointer = InMemorySaver()
incident_graph = builder.compile(checkpointer=checkpointer)


# --- Pipeline Execution Function ---

def run_incident_pipeline(
    logs: List[Tuple[str, str, str]],
    thread_id: str = "default_thread",
    resume_command: Optional[Command] = None,
) -> Optional[IncidentState]:
    """
    Executes the multi-agent incident response pipeline.
    Pre-processes logs with PII scrubber, runs Monitor agent, and executes the checkpointed graph.
    Supports thread_id and resumption via Command.
    All node invocations are traced to Langfuse; the global client is flushed after every
    invoke to guarantee spans are delivered before the caller gets a response.
    """
    langfuse_handler = LangfuseCallbackHandler(
        session_id=thread_id,
        tags=["agentic-sre-sim"],
    )
    config: Dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler],
    }

    if resume_command is not None:
        result = incident_graph.invoke(resume_command, config=config)
        langfuse_handler.flush()
    else:
        # Pre-process logs to scrub PII
        scrubbed_logs = [(ts, service, scrub_pii(msg)) for ts, service, msg in logs]
        initial_state = run_monitor_agent(scrubbed_logs)

        if initial_state is None:
            return None

        result = incident_graph.invoke(initial_state, config=config)
        langfuse_handler.flush()

    if isinstance(result, dict):
        return IncidentState.model_validate(result)

    return result
