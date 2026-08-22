import os
import json
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from agents.schemas import IncidentState, Event


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
        description="List of evidence strings derived strictly from the provided symptoms and raw signals."
    )


# --- Agent Function ---

def run_diagnosis_agent(state: IncidentState) -> IncidentState:
    """
    Diagnoses an incident based strictly on the state's symptoms and raw_signals.
    Uses temperature 0.0 for strict deterministic JSON generation.
    Returns an updated IncidentState with root_cause_hypothesis, confidence_score,
    and a new Event appended to event_log without mutating the original state.
    """
    api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.0,
    )

    structured_llm = llm.with_structured_output(DiagnosisOutput)

    system_prompt = (
        "You are an expert SRE. Diagnose the root cause based STRICTLY on the provided symptoms "
        "and raw signals. You MUST include specific details in your hypothesis, such as exact deployment "
        "version numbers (e.g., v2.3.1), specific HTTP error codes, or precise failure mechanisms "
        "(e.g., connection exhaustion, memory leak). Return strictly valid JSON with no markdown "
        "and no trailing commas."
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            system_prompt,
        ),
        (
            "user",
            "Incident Symptoms:\n{symptoms}\n\n"
            "Raw Signals:\n{raw_signals}\n\n"
            "Based solely on the above information, provide your root cause hypothesis, supporting evidence "
            "drawn only from what is stated above, and a confidence score between 0.0 and 1.0.",
        ),
    ])

    chain = prompt | structured_llm

    symptoms_str = "\n".join(f"- {s}" for s in state.symptoms) if state.symptoms else "No symptoms provided."
    raw_signals_str = json.dumps(state.raw_signals, indent=2) if state.raw_signals else "No raw signals provided."

    try:
        diagnosis: DiagnosisOutput = chain.invoke({
            "symptoms": symptoms_str,
            "raw_signals": raw_signals_str,
        })
    except Exception as e:
        print(f"Error invoking structured LLM output: {e}")
        # Deterministic fallback that stays faithful to the actual signals
        primary_symptom = state.symptoms[0] if state.symptoms else "Unknown incident"
        diagnosis = DiagnosisOutput(
            root_cause_hypothesis=f"Unable to complete LLM diagnosis. Primary symptom observed: {primary_symptom}",
            confidence_score=0.3,
            evidence=[f"Symptom: {s}" for s in state.symptoms],
        )

    # Append a new Event documenting the diagnosis result
    diagnosis_event = Event(
        timestamp=datetime.now(),
        source_agent="Diagnosis",
        action="Diagnosis Completed",
        details=f"Hypothesis: {diagnosis.root_cause_hypothesis} | Confidence: {diagnosis.confidence_score:.2f}",
    )

    # Return updated state — original state is not mutated
    return state.model_copy(update={
        "root_cause_hypothesis": diagnosis.root_cause_hypothesis,
        "confidence_score": diagnosis.confidence_score,
        "event_log": list(state.event_log) + [diagnosis_event],
    })
