import os
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_groq import ChatGroq

from agents.schemas import IncidentState, Event


# --- Mock Tools ---

@tool
def query_deploy_history(service: str) -> str:
    """Query recent deployment history for a given service."""
    if service in ["payment-service", "auth-service"]:
        return "v2.3.1 deployed 10 mins ago"
    return "No recent deploys"


@tool
def query_service_dependencies(service: str) -> str:
    """Query service dependencies for a given service."""
    if service == "cart-service":
        return "Depends on: inventory-db, payment-service"
    return "No known dependencies"


@tool
def query_recent_logs(service: str, window_minutes: int = 15) -> str:
    """Query recent logs for a given service within a time window in minutes."""
    if service in ["cart-service", "payment-service"]:
        return "ERROR 500"
    return "OOMKilled"


# --- Output Schema ---

class DiagnosisOutput(BaseModel):
    root_cause_hypothesis: str = Field(
        description="Detailed hypothesis explaining the probable root cause of the incident."
    )
    confidence_score: float = Field(
        description="Confidence score for the diagnosis, between 0.0 and 1.0.",
        ge=0.0,
        le=1.0,
    )
    evidence: List[str] = Field(
        description="List of evidence strings citing tool outputs or observations."
    )


# --- Agent Function ---

def run_diagnosis_agent(state: IncidentState) -> IncidentState:
    """
    Investigates an incident using state symptoms, raw signals, and tools.
    Returns an updated IncidentState with root_cause_hypothesis, confidence_score,
    and a new Event appended to event_log without mutating the original state.
    """
    api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.1,
    )

    tools = [query_deploy_history, query_service_dependencies, query_recent_logs]
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    system_prompt = (
        "You are an expert SRE Diagnosis Agent. Your job is to investigate production incidents, "
        "formulate a root cause hypothesis, provide evidence, and assign a confidence score between 0.0 and 1.0.\n"
        "Use available tools (query_deploy_history, query_service_dependencies, query_recent_logs) to investigate services."
    )

    user_prompt = (
        f"Incident Symptoms: {state.symptoms}\n"
        f"Raw Signals: {state.raw_signals}\n"
        "Investigate using the available tools and determine the root cause hypothesis, evidence, and confidence score."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    # Tool calling loop
    max_iterations = 5
    for _ in range(max_iterations):
        try:
            response = llm_with_tools.invoke(messages)
        except Exception as e:
            print(f"Error during LLM tool invocation: {e}")
            break

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            break

        messages.append(response)
        for tc in tool_calls:
            tool_name = tc.get("name")
            tool_args = tc.get("args", {})
            tool_id = tc.get("id", "")
            if tool_name in tools_by_name:
                try:
                    tool_output = tools_by_name[tool_name].invoke(tool_args)
                except Exception as err:
                    tool_output = f"Error executing {tool_name}: {err}"
            else:
                tool_output = f"Unknown tool: {tool_name}"

            messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))

    # Force final output to match DiagnosisOutput schema
    structured_llm = llm.with_structured_output(DiagnosisOutput)
    try:
        diagnosis: DiagnosisOutput = structured_llm.invoke(messages)
    except Exception as e:
        print(f"Error invoking structured LLM output: {e}")
        # Deterministic fallback if API fails or cannot format
        target_service = state.raw_signals.get("service", "payment-service")
        deploy_info = query_deploy_history.invoke({"service": target_service})
        deps_info = query_service_dependencies.invoke({"service": target_service})
        logs_info = query_recent_logs.invoke({"service": target_service, "window_minutes": 15})
        diagnosis = DiagnosisOutput(
            root_cause_hypothesis=f"Failure in {target_service} correlated with deployment '{deploy_info}' and logs '{logs_info}'.",
            confidence_score=0.85,
            evidence=[f"Deploy: {deploy_info}", f"Logs: {logs_info}", f"Dependencies: {deps_info}"]
        )

    # Append new Event documenting the diagnosis
    diagnosis_event = Event(
        timestamp=datetime.now(),
        source_agent="Diagnosis",
        action="Diagnosis Completed",
        details=f"Hypothesis: {diagnosis.root_cause_hypothesis} | Confidence: {diagnosis.confidence_score:.2f}",
    )

    updated_event_log = list(state.event_log) + [diagnosis_event]

    # Return updated state without mutating original
    return state.model_copy(update={
        "root_cause_hypothesis": diagnosis.root_cause_hypothesis,
        "confidence_score": diagnosis.confidence_score,
        "event_log": updated_event_log,
    })
