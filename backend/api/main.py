"""
api/main.py — FastAPI Web Application for Agentic-SRE backend.

Provides REST APIs to simulate incidents, check pipeline status, approve/reject
HITL proposals, and retrieve Langfuse trace URLs.
"""

import uuid
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langgraph.types import Command

from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

from agents.schemas import IncidentState
from agents.graph import run_incident_pipeline, incident_graph
from simulator.incident_generator import IncidentGenerator

load_dotenv()

app = FastAPI(
    title="Agentic-SRE API",
    description="Multi-Agent Incident Response & HITL Remediation API",
    version="1.0.0",
)

# CORS setup for frontend dev (e.g. Vite on localhost:5173 or localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global In-Memory Store for Incident States
INCIDENT_STORE: Dict[str, Dict[str, Any]] = {}


# --- Request Models ---

class SimulateRequest(BaseModel):
    incident_type: Optional[str] = Field(
        default="bad_deploy",
        description="Type of incident: memory_leak, bad_deploy, dependency_timeout, traffic_spike, config_drift",
    )


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(
        default="Rejected by operator",
        description="Reason for rejecting the proposed remediation action.",
    )


# --- Background Worker Function ---

def _background_run_pipeline(incident_id: str, incident_type: str) -> None:
    """
    Background worker function that generates synthetic logs, invokes the pipeline,
    and updates INCIDENT_STORE with serialized IncidentState dict.
    """
    generator = IncidentGenerator()
    try:
        logs = generator.get_incident(incident_type)
    except Exception as exc:
        INCIDENT_STORE[incident_id] = {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "error": f"Failed to generate logs for incident_type '{incident_type}': {exc}",
            "status": "error",
        }
        return

    # Run the pipeline (pauses at HITL gate if anomaly detected)
    final_state: Optional[IncidentState] = run_incident_pipeline(logs, thread_id=incident_id)

    if final_state is None:
        INCIDENT_STORE[incident_id] = {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "status": "no_anomaly",
            "message": "Monitor returned None — logs did not trigger an anomaly",
        }
    else:
        state_dict = final_state.model_dump(mode="json")
        state_dict["incident_id"] = incident_id
        state_dict["incident_type"] = incident_type
        INCIDENT_STORE[incident_id] = state_dict


# --- API Endpoints ---

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "agentic-sre-api"}


@app.get("/incidents")
def list_incidents():
    """Returns a list of all simulated incidents in the store."""
    return list(INCIDENT_STORE.values())


@app.post("/incidents/simulate", status_code=202)
def simulate_incident(
    payload: Optional[SimulateRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    POST /incidents/simulate:
    Accepts an optional incident_type (default: bad_deploy). Generates a UUID incident_id,
    stores an initial pending state, runs the pipeline in background, and returns incident_id.
    """
    inc_type = payload.incident_type if payload and payload.incident_type else "bad_deploy"
    incident_id = str(uuid.uuid4())

    INCIDENT_STORE[incident_id] = {
        "incident_id": incident_id,
        "incident_type": inc_type,
        "status": "pending",
        "message": "Incident investigation initiated",
    }

    background_tasks.add_task(_background_run_pipeline, incident_id, inc_type)

    return {
        "incident_id": incident_id,
        "incident_type": inc_type,
        "status": "pending",
    }


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """
    GET /incidents/{incident_id}:
    Returns the current IncidentState (as a dict) from INCIDENT_STORE.
    """
    if incident_id not in INCIDENT_STORE:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return INCIDENT_STORE[incident_id]


@app.post("/incidents/{incident_id}/approve")
def approve_incident(incident_id: str):
    """
    POST /incidents/{incident_id}/approve:
    Resumes the LangGraph interrupt via incident_graph.invoke(Command(resume={"action": "approve"})).
    Updates INCIDENT_STORE and returns the updated state.
    """
    if incident_id not in INCIDENT_STORE:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    langfuse_handler = LangfuseCallbackHandler(
        session_id=incident_id,
        tags=["agentic-sre-sim", "hitl-approve"],
    )
    config: Dict[str, Any] = {
        "configurable": {"thread_id": incident_id},
        "callbacks": [langfuse_handler],
    }

    resume_cmd = Command(resume={"action": "approve", "reason": "Approved via API"})

    try:
        raw_final = incident_graph.invoke(resume_cmd, config=config)
        langfuse_handler.flush()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resume pipeline: {exc}")

    final_state: IncidentState = (
        IncidentState.model_validate(raw_final) if isinstance(raw_final, dict) else raw_final
    )

    state_dict = final_state.model_dump(mode="json")
    state_dict["incident_id"] = incident_id
    if "incident_type" in INCIDENT_STORE[incident_id]:
        state_dict["incident_type"] = INCIDENT_STORE[incident_id]["incident_type"]

    INCIDENT_STORE[incident_id] = state_dict

    return {
        "status": "success",
        "approval_status": final_state.approval_status,
        "state": state_dict,
    }


@app.post("/incidents/{incident_id}/reject")
def reject_incident(
    incident_id: str,
    payload: Optional[RejectRequest] = None,
):
    """
    POST /incidents/{incident_id}/reject:
    Accepts a reason payload. Resumes the graph with Command(resume={"action": "reject", "reason": reason}).
    Updates INCIDENT_STORE and returns the updated state.
    """
    if incident_id not in INCIDENT_STORE:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    reason = payload.reason if payload and payload.reason else "Rejected by operator"
    langfuse_handler = LangfuseCallbackHandler(
        session_id=incident_id,
        tags=["agentic-sre-sim", "hitl-reject"],
    )
    config: Dict[str, Any] = {
        "configurable": {"thread_id": incident_id},
        "callbacks": [langfuse_handler],
    }

    resume_cmd = Command(resume={"action": "reject", "reason": reason})

    try:
        raw_final = incident_graph.invoke(resume_cmd, config=config)
        langfuse_handler.flush()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resume pipeline: {exc}")

    final_state: IncidentState = (
        IncidentState.model_validate(raw_final) if isinstance(raw_final, dict) else raw_final
    )

    state_dict = final_state.model_dump(mode="json")
    state_dict["incident_id"] = incident_id
    if "incident_type" in INCIDENT_STORE[incident_id]:
        state_dict["incident_type"] = INCIDENT_STORE[incident_id]["incident_type"]

    INCIDENT_STORE[incident_id] = state_dict

    return {
        "status": "success",
        "approval_status": final_state.approval_status,
        "state": state_dict,
    }


@app.get("/incidents/{incident_id}/trace")
def get_incident_trace(incident_id: str):
    """
    GET /incidents/{incident_id}/trace:
    Returns a dummy URL linking out to Langfuse trace viewer.
    """
    if incident_id not in INCIDENT_STORE:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    trace_url = f"https://us.cloud.langfuse.com/project/agentic-sre/traces/{incident_id}"
    return {
        "incident_id": incident_id,
        "trace_url": trace_url,
    }
