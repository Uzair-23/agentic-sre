"""
evals/harness.py — Evaluation harness for the agentic-sre pipeline.

Runs each incident in the golden dataset through the full pipeline,
auto-approves the HITL gate, and scores results using the LLM-as-a-judge.
"""

import json
import time
from pathlib import Path
from typing import Any

from langgraph.types import Command

from agents.graph import run_incident_pipeline, incident_graph
from simulator.incident_generator import IncidentGenerator
from evals.judges import evaluate_hypothesis


def run_eval_harness(golden_dataset_path: str) -> list[dict[str, Any]]:
    """
    Runs the eval pipeline for every incident in the golden dataset JSON.

    For each incident:
      1. Generates synthetic logs via IncidentGenerator.
      2. Runs run_incident_pipeline(), which pauses at approval_gate_node.
      3. Programmatically resumes with action='approve' (HITL bypass).
      4. Scores the result: action accuracy, risk accuracy, LLM judge score.

    Returns a list of per-incident result dicts.
    """
    path = Path(golden_dataset_path)
    with open(path, "r", encoding="utf-8") as f:
        golden_set: list[dict] = json.load(f)

    generator = IncidentGenerator()
    results: list[dict[str, Any]] = []

    for item in golden_set:
        incident_id: str = item["incident_id"]
        incident_type: str = item["incident_type"]
        gt_root_cause: str = item["ground_truth_root_cause"]
        gt_action: str = item["ground_truth_action"]
        gt_risk: str = item["ground_truth_risk"]

        print(f"\n{'='*60}")
        print(f"[HARNESS] Running eval for: {incident_id} ({incident_type})")

        result: dict[str, Any] = {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "ground_truth_action": gt_action,
            "ground_truth_risk": gt_risk,
            "predicted_action": None,
            "predicted_risk": None,
            "hypothesis": None,
            "action_match": False,
            "risk_match": False,
            "judge_score": 0.0,
            "judge_justification": "Not evaluated",
            "error": None,
            "latency_seconds": 0.0,
        }

        t0 = time.perf_counter()
        try:
            # Step 1: Generate synthetic logs for this incident type
            logs = generator.get_incident(incident_type)

            # Step 2: Run pipeline — pauses at approval_gate_node (HITL interrupt)
            paused_state = run_incident_pipeline(logs, thread_id=incident_id)

            if paused_state is None:
                result["error"] = "Monitor returned None — logs did not trigger an incident"
                results.append(result)
                continue

            # Step 3: HITL Bypass — programmatically approve the proposal
            config = {"configurable": {"thread_id": incident_id}}
            resume_cmd = Command(resume={"action": "approve", "reason": "Automated eval harness approval"})
            raw = incident_graph.invoke(resume_cmd, config=config)

            from agents.schemas import IncidentState
            final_state: IncidentState = (
                IncidentState.model_validate(raw) if isinstance(raw, dict) else raw
            )

            # Step 4: Capture predictions
            predicted_action = (
                final_state.proposed_fix.action_type if final_state.proposed_fix else None
            )
            predicted_risk = final_state.risk_level
            hypothesis = final_state.root_cause_hypothesis or ""

            result["predicted_action"] = predicted_action
            result["predicted_risk"] = predicted_risk
            result["hypothesis"] = hypothesis
            result["action_match"] = predicted_action == gt_action
            result["risk_match"] = predicted_risk == gt_risk
            result["approval_status"] = final_state.approval_status

            # Step 5: LLM-as-a-Judge semantic scoring of root cause hypothesis
            print(f"  [JUDGE] Scoring hypothesis for {incident_id}...")
            judge = evaluate_hypothesis(hypothesis, gt_root_cause)
            result["judge_score"] = judge.score
            result["judge_justification"] = judge.justification

        except Exception as exc:
            result["error"] = str(exc)
            print(f"  [ERROR] {incident_id}: {exc}")

        result["latency_seconds"] = round(time.perf_counter() - t0, 2)
        results.append(result)

        action_mark = "OK" if result['action_match'] else "FAIL"
        risk_mark = "OK" if result['risk_match'] else "FAIL"
        safe_justification = result['judge_justification'].encode("ascii", errors="replace").decode("ascii")
        print(f"  Action: {result['predicted_action']} (expected: {gt_action}) -> [{action_mark}]")
        print(f"  Risk:   {result['predicted_risk']} (expected: {gt_risk}) -> [{risk_mark}]")
        print(f"  Judge score: {result['judge_score']:.2f} - {safe_justification}")
        print(f"  Latency: {result['latency_seconds']}s")

        time.sleep(3)

    return results
