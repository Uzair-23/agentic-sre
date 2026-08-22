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
        description="Parameters required for the action (e.g., {'to_version': 'v2.3.0'}, {'replicas': 3}, {'flag': 'enable_strict_auth', 'value': False})."
    )
    justification: str = Field(
        description="One-paragraph explanation justifying why this action fits the diagnosis."
    )


# --- Agent Function ---

def run_remediation_agent(state: IncidentState) -> IncidentState:
    """
    Consumes an IncidentState containing diagnosis hypothesis and symptoms.
    Selects an appropriate remediation action based on strict SRE heuristics
    and appends the proposal to the state without mutating the original state.
    """
    api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.1,
    )

    structured_llm = llm.with_structured_output(RemediationOutput)

    system_prompt = (
        "You are an expert SRE Remediation Agent. Select the most appropriate remediation action "
        "strictly matching these rules:\n"
        "- If the diagnosis involves a bad deploy, broken code, or memory leak from a new version, propose rollback.\n"
        "- If the diagnosis involves a traffic spike or resource exhaustion without a leak, propose scale_up.\n"
        "- If the diagnosis involves a dependency timeout or frozen process, propose restart_service.\n"
        "- If the diagnosis involves config drift or feature flags, propose toggle_config_flag.\n\n"
        "Never propose dangerous or arbitrary shell commands. Select only from the approved action types: "
        "['rollback', 'restart_service', 'scale_up', 'toggle_config_flag']."
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            system_prompt,
        ),
        (
            "user",
            "Incident Context:\n"
            "Symptoms: {symptoms}\n"
            "Root Cause Hypothesis: {hypothesis}\n\n"
            "Select the single best remediation action, specify the target service name and relevant parameters, "
            "and provide a clear justification.",
        ),
    ])

    chain = prompt | structured_llm

    symptoms_str = "\n".join(f"- {s}" for s in state.symptoms) if state.symptoms else "No symptoms provided."
    hypothesis_str = state.root_cause_hypothesis or "No root cause hypothesis provided."

    try:
        remediation: RemediationOutput = chain.invoke({
            "symptoms": symptoms_str,
            "hypothesis": hypothesis_str,
        })
    except Exception as e:
        print(f"Error invoking Groq LLM for remediation: {e}")
        # Deterministic fallback logic adhering to the same heuristics
        target_service = state.raw_signals.get("service", "payment-service") if state.raw_signals else "payment-service"
        hyp_lower = hypothesis_str.lower()
        symp_lower = symptoms_str.lower()
        combined = f"{hyp_lower} {symp_lower}"

        if any(k in combined for k in ["config", "flag", "feature_flag", "toggle"]):
            action_type = "toggle_config_flag"
            params = {"flag": "enable_strict_auth", "value": False}
        elif any(k in combined for k in ["traffic", "spike", "surge", "queue", "capacity"]):
            action_type = "scale_up"
            params = {"replicas": 3}
        elif any(k in combined for k in ["timeout", "dependency", "exhaustion", "frozen", "deadlock"]):
            action_type = "restart_service"
            params = {"reason": "Dependency timeout recovery"}
        else:
            action_type = "rollback"
            params = {"to_version": "v2.3.0"}

        remediation = RemediationOutput(
            action_type=action_type,
            target=target_service,
            params=params,
            justification=f"Automated fallback remediation for {target_service} based on hypothesis: {hypothesis_str}",
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

    # Return new copy of state without in-place mutation
    return state.model_copy(update={
        "proposed_fix": fix_proposal,
        "event_log": list(state.event_log) + [remediation_event],
    })
