from pydantic import BaseModel, Field
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


# --- Phase 6: Postmortem Loop Schemas ---

class ThresholdAdjustment(BaseModel):
    """Describes a data-driven sensitivity adjustment produced by the Postmortem Agent."""
    service: str = Field(description="The service whose detection threshold should be adjusted.")
    metric: str = Field(description="The metric to tune, e.g. 'memory', 'error_rate', 'latency'.")
    multiplier: float = Field(
        description="Sensitivity multiplier applied to the existing threshold. "
                    "Values < 1.0 lower the trigger threshold (more sensitive). "
                    "Example: 0.8 means fire alert at 80%% of the old threshold."
    )
    reason: str = Field(description="One-sentence rationale for this adjustment.")


class PostmortemOutput(BaseModel):
    """Structured output of the Postmortem Agent."""
    summary: str = Field(description="Plain-English summary of what happened and how it was resolved.")
    root_cause: str = Field(description="Concise root cause statement (one sentence).")
    action_taken: str = Field(description="Description of the remediation action that was executed.")
    prevention_recommendations: list[str] = Field(
        description="Ordered list of concrete steps to prevent recurrence."
    )
    threshold_adjustment: ThresholdAdjustment = Field(
        description="A data-driven threshold adjustment to make the Monitor Agent more sensitive to this class of incident."
    )