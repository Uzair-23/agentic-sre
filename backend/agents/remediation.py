import os
from datetime import datetime
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from agents.schemas import IncidentState, FixProposal, Event


# --- Output Schema ---

class RemediationOutput(BaseModel):
    action_type: Literal["rollback", "restart_service", "scale_up", "toggle_config_flag"] = Field(
        description="The action type to perform, strictly restricted to the approved enum."
    )
    target: str = Field(
        description="The target service name for the action."
    )
    params: Dict[str, Any] = Field(
        description="Parameters required for the action (e.g., {'to_version': 'v2.3.0'} or {'replicas': 3})."
    )
    justification: str = Field(
        description="One-paragraph explanation justifying why this action fits the diagnosis."
    )


# --- Agent Function ---

def run_remediation_agent(state: IncidentState) -> IncidentState:
    """
    Consumes an IncidentState containing diagnosis hypothesis and symptoms.
    Selects an appropriate remediation action and appends the proposal to the state.
    Returns a new copy of IncidentState without mutating the original in place.
    """
    api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.1,
    )

    structured_llm = llm.with_structured_output(RemediationOutput)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert SRE Remediation Agent. "
            "Given the diagnosis hypothesis and symptoms, propose the best remediation action. "
            "Never propose dangerous/arbitrary shell commands. Select only from the approved action types."
        ),
        (
            "user",
            "Incident Details:\n"
            "Symptoms: {symptoms}\n"
            "Root Cause Hypothesis: {hypothesis}\n"
            "Raw Signals: {raw_signals}\n\n"
            "Propose an appropriate remediation action."
        ),
    ])

    chain = prompt | structured_llm

    try:
        remediation: RemediationOutput = chain.invoke({
            "symptoms": state.symptoms,
            "hypothesis": state.root_cause_hypothesis or "Unknown root cause",
            "raw_signals": state.raw_signals,
        })
    except Exception as e:
        print(f"Error invoking Groq LLM for remediation: {e}")
        # Deterministic fallback logic
        target_service = state.raw_signals.get("service", "payment-service")
        hypothesis_lower = (state.root_cause_hypothesis or "").lower()

        if "deploy" in hypothesis_lower or "v2." in hypothesis_lower or "version" in hypothesis_lower:
            action_type = "rollback"
            params = {"to_version": "v2.3.0"}
        elif "memory" in hypothesis_lower or "oom" in hypothesis_lower or "leak" in hypothesis_lower:
            action_type = "restart_service"
            params = {"reason": "OOM recovery"}
        elif "traffic" in hypothesis_lower or "latency" in hypothesis_lower or "load" in hypothesis_lower:
            action_type = "scale_up"
            params = {"replicas": 3}
        else:
            action_type = "restart_service"
            params = {"reason": "Default restart recovery"}

        remediation = RemediationOutput(
            action_type=action_type,
            target=target_service,
            params=params,
            justification=f"Automated fallback remediation for {target_service} based on hypothesis: {state.root_cause_hypothesis}",
        )

    fix_proposal = FixProposal(
        action_type=remediation.action_type,
        target=remediation.target,
        params=remediation.params,
    )

    remediation_event = Event(
        timestamp=datetime.now(),
        source_agent="Remediation",
        action="Fix Proposed",
        details=f"Proposed Action: {remediation.action_type} on '{remediation.target}'. Justification: {remediation.justification}",
    )

    updated_event_log = list(state.event_log) + [remediation_event]

    # Return new copy of state without in-place mutation
    return state.model_copy(update={
        "proposed_fix": fix_proposal,
        "event_log": updated_event_log,
    })
