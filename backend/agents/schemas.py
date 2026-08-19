from pydantic import BaseModel
from typing import Literal, Any
from datetime import datetime

class FixProposal(BaseModel):
    action_type: Literal["rollback", "restart_service", "scale_up", "toggle_config_flag"]
    target: str
    params: dict

class Event(BaseModel):
    timestamp: datetime
    source_agent: str
    action: str
    details: str

class IncidentState(BaseModel):
    incident_id: str
    created_at: datetime
    symptoms: list[str]
    raw_signals: dict          # logs/metrics snapshot
    root_cause_hypothesis: str | None = None
    confidence_score: float | None = None
    proposed_fix: FixProposal | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    approval_status: Literal["pending", "approved", "rejected"] | None = None
    approval_notes: str | None = None
    event_log: list[Event] = []   # append-only audit trail
    resolution: str | None = None
    postmortem: str | None = None