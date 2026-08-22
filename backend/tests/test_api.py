"""
tests/test_api.py — Unit tests for the FastAPI backend application in api/main.py.
"""

from datetime import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient

from api.main import app, INCIDENT_STORE
from agents.schemas import IncidentState, FixProposal

client = TestClient(app)


def test_health_check():
    """Asserts health check endpoint returns 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_simulate_incident_endpoint():
    """Asserts POST /incidents/simulate returns 202 with generated incident_id."""
    with patch("api.main._background_run_pipeline"):
        response = client.post("/incidents/simulate", json={"incident_type": "bad_deploy"})
        assert response.status_code == 202
        data = response.json()
        assert "incident_id" in data
        assert data["incident_type"] == "bad_deploy"
        assert data["status"] == "pending"

        # Verify incident is recorded in store
        inc_id = data["incident_id"]
        assert inc_id in INCIDENT_STORE


def test_get_incident_endpoint():
    """Asserts GET /incidents/{incident_id} retrieves recorded state."""
    INCIDENT_STORE["test-inc-1"] = {
        "incident_id": "test-inc-1",
        "incident_type": "memory_leak",
        "status": "pending",
    }

    response = client.get("/incidents/test-inc-1")
    assert response.status_code == 200
    assert response.json()["incident_id"] == "test-inc-1"


def test_get_incident_not_found():
    """Asserts GET /incidents/{invalid_id} returns 404."""
    response = client.get("/incidents/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@patch("api.main.incident_graph")
def test_approve_incident_endpoint(mock_graph):
    """Asserts POST /incidents/{incident_id}/approve resumes pipeline with approval."""
    INCIDENT_STORE["test-inc-approve"] = {
        "incident_id": "test-inc-approve",
        "incident_type": "bad_deploy",
    }

    final_state = IncidentState(
        incident_id="test-inc-approve",
        created_at=datetime.now(),
        raw_signals={"service": "web"},
        symptoms=["Broken deployment"],
        root_cause_hypothesis="Bad code deploy in web v2.3.1",
        proposed_fix=FixProposal(action_type="rollback", target="web", params={"to_version": "v2.3.0"}),
        risk_level="high",
        approval_status="approved",
        resolution="Action rollback applied successfully to web",
    )
    mock_graph.invoke.return_value = final_state.model_dump()

    response = client.post("/incidents/test-inc-approve/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["approval_status"] == "approved"
    assert INCIDENT_STORE["test-inc-approve"]["approval_status"] == "approved"


@patch("api.main.incident_graph")
def test_reject_incident_endpoint(mock_graph):
    """Asserts POST /incidents/{incident_id}/reject resumes pipeline with rejection."""
    INCIDENT_STORE["test-inc-reject"] = {
        "incident_id": "test-inc-reject",
        "incident_type": "bad_deploy",
    }

    final_state = IncidentState(
        incident_id="test-inc-reject",
        created_at=datetime.now(),
        raw_signals={"service": "web"},
        symptoms=["Broken deployment"],
        root_cause_hypothesis="Bad code deploy in web v2.3.1",
        proposed_fix=FixProposal(action_type="rollback", target="web", params={"to_version": "v2.3.0"}),
        risk_level="high",
        approval_status="rejected",
        approval_notes="Manual rejection via test",
    )
    mock_graph.invoke.return_value = final_state.model_dump()

    response = client.post("/incidents/test-inc-reject/reject", json={"reason": "Manual rejection via test"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["approval_status"] == "rejected"
    assert INCIDENT_STORE["test-inc-reject"]["approval_status"] == "rejected"


def test_get_incident_trace_endpoint():
    """Asserts GET /incidents/{incident_id}/trace returns Langfuse trace URL."""
    INCIDENT_STORE["test-inc-trace"] = {"incident_id": "test-inc-trace"}

    response = client.get("/incidents/test-inc-trace/trace")
    assert response.status_code == 200
    data = response.json()
    assert "trace_url" in data
    assert "test-inc-trace" in data["trace_url"]
