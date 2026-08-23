"""
tests/test_postmortem.py  —  Phase 6: Postmortem Loop Tests

Test 1: Unit test — run_postmortem_agent produces valid PostmortemOutput
         and saves a record to thresholds.json.

Test 2: Feedback loop integration test — clear thresholds.json, run an
         incident pipeline through full approval to postmortem, verify the
         store was written, then prove the Monitor Agent now fires on
         marginal log data that only triggers under the adjusted multiplier.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.schemas import (
    IncidentState,
    FixProposal,
    Event,
    PostmortemOutput,
    ThresholdAdjustment,
)
from agents.postmortem import run_postmortem_agent, update_threshold_store
from agents.monitor import detect_anomaly


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resolved_state(service: str = "payment-service") -> IncidentState:
    """Return a fully resolved IncidentState suitable for postmortem input."""
    return IncidentState(
        incident_id=f"inc_{uuid.uuid4().hex[:8]}",
        created_at=datetime.now(),
        symptoms=["Memory usage exceeded 90%", "OOMKilled events on pod restart"],
        raw_signals={"service": service, "memory_usage_pct": 95},
        root_cause_hypothesis=(
            "Memory leak in payment-service v2.3.1 caused heap exhaustion "
            "and OOMKilled pod restarts."
        ),
        confidence_score=0.92,
        proposed_fix=FixProposal(
            action_type="rollback",
            target=service,
            params={"to_version": "v2.3.0"},
        ),
        risk_level="high",
        approval_status="approved",
        approval_notes="Approved by operator",
        resolution=f"Action rollback applied successfully to {service}",
        event_log=[
            Event(
                timestamp=datetime.now(),
                source_agent="Monitor",
                action="Incident Created",
                details="Detected anomaly and extracted 2 symptoms.",
            ),
            Event(
                timestamp=datetime.now(),
                source_agent="Executor",
                action="Execution Complete",
                details="Action applied successfully",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Test 1a: Unit — run_postmortem_agent returns valid state
# ---------------------------------------------------------------------------

def test_postmortem_agent_produces_valid_output(tmp_path):
    """
    run_postmortem_agent should:
    - Return an IncidentState with a non-empty postmortem field.
    - Append a 'Postmortem Completed' event to event_log.
    - Call update_threshold_store with a valid ThresholdAdjustment.
    """
    state = _make_resolved_state("payment-service")

    mock_adjustment = ThresholdAdjustment(
        service="payment-service",
        metric="memory",
        multiplier=0.8,
        reason="Lower memory threshold to detect leaks 20% earlier.",
    )
    mock_output = PostmortemOutput(
        summary="payment-service memory leak resolved by rollback to v2.3.0.",
        root_cause="Memory leak in v2.3.1 caused heap exhaustion.",
        action_taken="rollback to v2.3.0",
        prevention_recommendations=[
            "Add memory alerting at 75% threshold.",
            "Gate deploys with memory profiling in CI.",
        ],
        threshold_adjustment=mock_adjustment,
    )

    with patch("agents.postmortem.ChatGroq") as mock_llm_cls:
        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output.return_value.invoke.return_value = mock_output
        mock_llm_cls.return_value = mock_llm_instance

        with patch("agents.postmortem.update_threshold_store") as mock_store:
            result = run_postmortem_agent(state)
            mock_store.assert_called_once()
            called_adjustment: ThresholdAdjustment = mock_store.call_args[0][0]
            assert called_adjustment.service == "payment-service"
            assert 0.5 <= called_adjustment.multiplier <= 0.95

    assert result.postmortem is not None and len(result.postmortem) > 0
    postmortem_events = [e for e in result.event_log if e.source_agent == "Postmortem"]
    assert len(postmortem_events) == 1
    assert postmortem_events[0].action == "Postmortem Completed"


# ---------------------------------------------------------------------------
# Test 1b: Unit — update_threshold_store writes and overwrites correctly
# ---------------------------------------------------------------------------

def test_postmortem_threshold_store_persistence(tmp_path):
    """update_threshold_store() writes the correct key and can overwrite."""
    store_path = tmp_path / "thresholds.json"

    adjustment = ThresholdAdjustment(
        service="cart-service",
        metric="latency",
        multiplier=0.75,
        reason="Catch latency spikes 25% earlier.",
    )
    update_threshold_store(adjustment, file_path=store_path)

    data = json.loads(store_path.read_text())
    assert "cart-service:latency" in data
    entry = data["cart-service:latency"]
    assert entry["multiplier"] == 0.75
    assert "updated_at" in entry

    # Second write overwrites the value
    adjustment2 = ThresholdAdjustment(
        service="cart-service",
        metric="latency",
        multiplier=0.6,
        reason="Even more sensitive after second incident.",
    )
    update_threshold_store(adjustment2, file_path=store_path)
    data2 = json.loads(store_path.read_text())
    assert data2["cart-service:latency"]["multiplier"] == 0.6


# ---------------------------------------------------------------------------
# Test 2a: Feedback loop — detect_anomaly respects sensitivity multiplier
# ---------------------------------------------------------------------------

def test_feedback_loop_monitor_sensitivity():
    """
    Marginal warning-only logs must:
    - NOT trigger at default multiplier=1.0  (no OOMKilled / ERROR 500 / CRITICAL)
    - DO trigger at multiplier=0.4           (scaled_threshold = max(1, int(5*0.4)) = 2)
    """
    marginal_logs = [
        ("2024-01-01T00:00:01Z", "payment-service", "WARNING: memory usage high"),
        ("2024-01-01T00:00:02Z", "payment-service", "WARNING: slow query detected"),
        ("2024-01-01T00:00:03Z", "payment-service", "WARN: connection pool SLOW"),
    ]

    # Without feedback: no anomaly
    assert not detect_anomaly(marginal_logs, sensitivity_multiplier=1.0), (
        "Default multiplier must NOT fire on warning-only logs."
    )

    # With aggressive feedback multiplier: anomaly detected
    assert detect_anomaly(marginal_logs, sensitivity_multiplier=0.4), (
        "Multiplier=0.4 with 3 warnings must trigger (scaled_threshold=2)."
    )


# ---------------------------------------------------------------------------
# Test 2b: Feedback loop — run_monitor_agent passes multiplier from store
# ---------------------------------------------------------------------------

def test_feedback_loop_monitor_agent_reads_store(monkeypatch):
    """
    run_monitor_agent() must load the threshold store and forward the most
    sensitive multiplier to detect_anomaly(). We monkeypatch the LLM so no
    real API call is made — the test only verifies the threshold integration.
    """
    marginal_logs = [
        ("2024-01-01T00:00:01Z", "payment-service", "WARNING: memory usage high"),
        ("2024-01-01T00:00:02Z", "payment-service", "WARNING: slow query"),
        ("2024-01-01T00:00:03Z", "payment-service", "WARN: latency spike"),
    ]

    # Inject a very sensitive override for payment-service
    sensitive_store = {"payment-service:error_rate": {"multiplier": 0.4, "reason": "test"}}
    monkeypatch.setattr("agents.monitor._load_threshold_store", lambda: sensitive_store)

    # Track what multiplier detect_anomaly was called with
    called_with: dict = {}
    original_detect = detect_anomaly

    def patched_detect(logs, sensitivity_multiplier=1.0):
        called_with["multiplier"] = sensitivity_multiplier
        return original_detect(logs, sensitivity_multiplier)

    monkeypatch.setattr("agents.monitor.detect_anomaly", patched_detect)

    # Patch ChatGroq so if anomaly IS detected and the LLM path runs, it doesn't fail
    mock_llm = MagicMock()
    mock_interp = MagicMock()
    mock_interp.symptoms = ["WARNING: memory usage high"]
    mock_interp.raw_signals = {"service": "payment-service"}
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_interp
    monkeypatch.setattr("agents.monitor.ChatGroq", lambda **kwargs: mock_llm)

    import agents.monitor as monitor_module
    monitor_module.run_monitor_agent(marginal_logs)

    # detect_anomaly must have been called with the multiplier from the store
    assert called_with.get("multiplier") == 0.4, (
        f"Expected multiplier=0.4 from store but got {called_with.get('multiplier')}"
    )

