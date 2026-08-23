"""
agents/postmortem.py  —  Phase 6: Postmortem Loop Agent

Consumes a completed IncidentState (after executor has run) and:
1. Asks the LLM to write a structured incident postmortem.
2. Extracts a ThresholdAdjustment and persists it to simulator/thresholds.json
   so that run_monitor_agent() picks it up on the next run (feedback loop).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from langchain_groq import ChatGroq

from agents.schemas import (
    IncidentState,
    Event,
    PostmortemOutput,
    ThresholdAdjustment,
)

# ---------------------------------------------------------------------------
# Threshold store helpers
# ---------------------------------------------------------------------------

_DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent / "simulator" / "thresholds.json"


def _load_store(file_path: Path) -> dict:
    """Reads the JSON threshold store; returns {} if file is missing or empty."""
    try:
        text = file_path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def update_threshold_store(
    adjustment: ThresholdAdjustment,
    file_path: str | Path = _DEFAULT_STORE_PATH,
) -> None:
    """
    Persists a threshold multiplier override.

    Key format:  "<service>:<metric>"
    Value:       {"multiplier": float, "reason": str, "updated_at": ISO timestamp}
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    store = _load_store(path)
    key = f"{adjustment.service}:{adjustment.metric}"
    store[key] = {
        "multiplier": adjustment.multiplier,
        "reason": adjustment.reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Postmortem agent
# ---------------------------------------------------------------------------

def run_postmortem_agent(state: IncidentState) -> IncidentState:
    """
    Phase 6 Postmortem Agent.

    Called after executor_node runs. Generates a structured PostmortemOutput
    using the full audit trail, then persists the threshold adjustment so
    the Monitor Agent becomes more sensitive to this class of incident.
    """
    api_key = os.getenv("GROQ_API_KEY")

    llm = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.0,
    )

    structured_llm = llm.with_structured_output(PostmortemOutput)

    # Build a human-readable event log string for the prompt
    event_log_text = "\n".join(
        f"[{evt.timestamp}] [{evt.source_agent}] {evt.action}: {evt.details}"
        for evt in (state.event_log or [])
    )

    fix_text = (
        f"action_type={state.proposed_fix.action_type}, "
        f"target={state.proposed_fix.target}, "
        f"params={state.proposed_fix.params}"
        if state.proposed_fix
        else "No fix was proposed."
    )

    system_prompt = (
        "You are an expert SRE Postmortem Analyst. "
        "Given the full audit trail of a resolved incident, produce a structured postmortem.\n\n"
        "Rules:\n"
        "- Be concise and factual. Do NOT hallucinate details.\n"
        "- prevention_recommendations must be actionable and specific.\n"
        "- threshold_adjustment.multiplier must be between 0.5 and 0.95. "
        "  Choose a value that makes the Monitor Agent fire earlier for this class of incident.\n"
        "- Return strictly valid JSON matching the PostmortemOutput schema.\n"
        "- The threshold_adjustment.service must be the EXACT service name from the incident."
    )

    user_prompt = (
        f"Root Cause Hypothesis:\n{state.root_cause_hypothesis or 'Unknown'}\n\n"
        f"Proposed Fix:\n{fix_text}\n\n"
        f"Approval Status: {state.approval_status}\n"
        f"Resolution: {state.resolution or 'None'}\n\n"
        f"Full Audit Trail:\n{event_log_text or '(empty)'}"
    )

    try:
        output: PostmortemOutput = structured_llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as exc:
        print(f"[Postmortem] LLM call failed ({exc}); using deterministic fallback.")
        # Deterministic fallback so the loop never breaks
        service = (
            state.proposed_fix.target
            if state.proposed_fix
            else state.raw_signals.get("service", "unknown-service")
        )
        output = PostmortemOutput(
            summary=(
                f"Incident {state.incident_id} was resolved by "
                f"{state.proposed_fix.action_type if state.proposed_fix else 'unknown action'} "
                f"on {service}."
            ),
            root_cause=state.root_cause_hypothesis or "Root cause not determined.",
            action_taken=fix_text,
            prevention_recommendations=[
                "Add alerting for early-stage symptoms.",
                "Review deployment pipeline to catch regressions earlier.",
                "Increase observability coverage on the affected service.",
            ],
            threshold_adjustment=ThresholdAdjustment(
                service=service,
                metric="error_rate",
                multiplier=0.8,
                reason="Lower error_rate trigger to catch similar incidents 20% earlier.",
            ),
        )

    # Persist threshold adjustment (feedback loop)
    update_threshold_store(output.threshold_adjustment)

    postmortem_event = Event(
        timestamp=datetime.now(),
        source_agent="Postmortem",
        action="Postmortem Completed",
        details=(
            f"Postmortem completed. Adjusted {output.threshold_adjustment.service} "
            f"{output.threshold_adjustment.metric} sensitivity "
            f"(multiplier={output.threshold_adjustment.multiplier})."
        ),
    )

    return state.model_copy(update={
        "postmortem": output.summary,
        "event_log": list(state.event_log) + [postmortem_event],
    })
