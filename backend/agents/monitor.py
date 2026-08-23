import os
import re
import json
from datetime import datetime
from pathlib import Path
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

def detect_anomaly(logs: List[Tuple[str, str, str]], sensitivity_multiplier: float = 1.0) -> bool:
    """
    Deterministic check: Looks for OOMKilled, ERROR 500, or CRITICAL timeouts.
    The sensitivity_multiplier (from the Postmortem feedback loop) can lower the
    effective threshold — e.g. a multiplier of 0.8 makes the detector 20%% more
    aggressive by also counting warning-level signals when there are enough of them.
    In a real system this would scale a Prometheus alert threshold.
    """
    anomaly_keywords = ["OOMKilled", "ERROR 500", "CRITICAL"]
    warning_keywords = ["WARN", "WARNING", "HIGH", "SLOW", "TIMEOUT"]

    for _, _, message in logs:
        if any(keyword in message for keyword in anomaly_keywords):
            return True

    # Feedback loop: when sensitivity_multiplier < 1.0, count accumulated warnings
    # as an anomaly if they exceed a scaled threshold.
    if sensitivity_multiplier < 1.0:
        warn_count = sum(
            1
            for _, _, message in logs
            if any(w in message for w in warning_keywords)
        )
        # Base threshold: fire if >=5 warnings. Scaled: fire if >= (5 * multiplier).
        scaled_threshold = max(1, int(5 * sensitivity_multiplier))
        if warn_count >= scaled_threshold:
            return True

    return False

def extract_anomalous_logs(logs: List[Tuple[str, str, str]]) -> str:
    """Helper to format logs for the LLM prompt."""
    return "\n".join([f"[{ts}] {service}: {msg}" for ts, service, msg in logs[-10:]]) # Send last 10 logs

def _load_threshold_store() -> Dict[str, Any]:
    """
    Loads the persisted threshold multipliers written by the Postmortem Agent.
    Returns {} if the file is missing or empty.
    """
    store_path = Path(__file__).resolve().parent.parent / "simulator" / "thresholds.json"
    try:
        text = store_path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_monitor_agent(logs: List[Tuple[str, str, str]]) -> IncidentState | None:
    """
    The main Monitor Agent function.
    Returns a new IncidentState if an anomaly is detected, otherwise None.
    Applies threshold multipliers from the Postmortem feedback loop.
    """
    # Phase 6: load threshold overrides from last postmortem run
    threshold_store = _load_threshold_store()

    # Determine the most sensitive multiplier among all services present in the logs
    # (a lower multiplier = more sensitive detection)
    services_in_logs = {svc for _, svc, _ in logs}
    active_multiplier = 1.0
    for key, entry in threshold_store.items():
        svc, _metric = key.split(":", 1) if ":" in key else (key, "")
        if svc in services_in_logs:
            m = float(entry.get("multiplier", 1.0))
            active_multiplier = min(active_multiplier, m)  # take the most sensitive

    # 1. Deterministic Detection (with optional sensitivity boost)
    if not detect_anomaly(logs, sensitivity_multiplier=active_multiplier):
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
        symptoms = [msg for _, _, msg in logs if any(k in msg for k in ["OOMKilled", "ERROR 500", "CRITICAL"])]
        service = logs[0][1] if logs else "unknown-service"
        return IncidentState(
            incident_id=f"inc_{int(datetime.now().timestamp())}",
            created_at=datetime.now(),
            symptoms=symptoms or ["Anomaly detected in log stream"],
            raw_signals={"service": service, "status": "anomaly_flagged"},
            event_log=[{
                "timestamp": datetime.now(),
                "source_agent": "Monitor",
                "action": "Incident Created",
                "details": f"Detected anomaly and extracted {len(symptoms)} symptoms."
            }]
        )