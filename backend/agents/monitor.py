import os
import re
from datetime import datetime
from typing import List, Tuple, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

# We import the shared state schema we defined earlier
from agents.schemas import IncidentState

# Structured output schema for the LLM
class MonitorInterpretation(BaseModel):
    symptoms: List[str] = Field(description="List of observed symptoms from the logs.")
    raw_signals: Dict[str, Any] = Field(
        description="A dictionary of key/value pairs summarizing the anomaly. Example: {'service': 'cart-service', 'error_type': 'timeout'}. DO NOT return a raw string."
    )

def detect_anomaly(logs: List[Tuple[str, str, str]]) -> bool:
    """
    Deterministic check: Looks for OOMKilled, ERROR 500, or CRITICAL timeouts.
    In a real system, this would be a Prometheus alert or Datadog monitor.
    """
    anomaly_keywords = ["OOMKilled", "ERROR 500", "CRITICAL"]
    for _, _, message in logs:
        if any(keyword in message for keyword in anomaly_keywords):
            return True
    return False

def extract_anomalous_logs(logs: List[Tuple[str, str, str]]) -> str:
    """Helper to format logs for the LLM prompt."""
    return "\n".join([f"[{ts}] {service}: {msg}" for ts, service, msg in logs[-10:]]) # Send last 10 logs

def run_monitor_agent(logs: List[Tuple[str, str, str]]) -> IncidentState | None:
    """
    The main Monitor Agent function.
    Returns a new IncidentState if an anomaly is detected, otherwise None.
    """
    # 1. Deterministic Detection
    if not detect_anomaly(logs):
        return None
    
    # 2. LLM Interpretation (Only triggered if anomaly is found)
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="openai/gpt-oss-20b", # Groq's fast, capable model
        temperature=0.1 # Low temperature for factual extraction
    )
    
    structured_llm = llm.with_structured_output(MonitorInterpretation)
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system", 
            "You are an expert SRE Monitor Agent. An alert has triggered. Analyze the provided logs. "
            "Extract symptoms as a list. Extract raw_signals as a structured dictionary of key metrics, services, or entities. "
            "Do not return raw log strings in raw_signals."
        ),
        ("user", "Recent logs:\n{logs}")
    ])
    
    chain = prompt | structured_llm
    
    log_text = extract_anomalous_logs(logs)
    
    try:
        interpretation = chain.invoke({"logs": log_text})
        
        # 3. Initialize Shared State
        return IncidentState(
            incident_id=f"inc_{int(datetime.now().timestamp())}",
            created_at=datetime.now(),
            symptoms=interpretation.symptoms,
            raw_signals=interpretation.raw_signals,
            event_log=[{
                "timestamp": datetime.now(),
                "source_agent": "Monitor",
                "action": "Incident Created",
                "details": f"Detected anomaly and extracted {len(interpretation.symptoms)} symptoms."
            }]
        )
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return None