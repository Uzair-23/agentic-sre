"""
evals/run_regression.py — CI regression gate for the agentic-sre evaluation suite.

Usage (from backend/ directory):
    python -m evals.run_regression

Exit codes:
    0 — All metrics pass thresholds and beat or match baseline.
    1 — Regression detected (below threshold or below baseline).
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env before importing any agents
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from evals.harness import run_eval_harness

# --- Configuration ---
GOLDEN_DATASET_PATH = Path(__file__).resolve().parent.parent / "simulator" / "golden_set.json"
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"
PASS_THRESHOLD = 75.0  # Minimum acceptable % for any metric


def _pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _load_baseline() -> dict:
    if BASELINE_PATH.exists() and BASELINE_PATH.stat().st_size > 0:
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "avg_hypothesis_score_pct": 0.0,
        "action_accuracy_pct": 0.0,
        "risk_accuracy_pct": 0.0,
    }


def _save_baseline(metrics: dict) -> None:
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Baseline updated -> {BASELINE_PATH}")


def _print_scorecard(results: list[dict], metrics: dict, baseline: dict) -> None:
    width = 64
    print("\n" + "=" * width)
    print("  AGENTIC-SRE EVALUATION SCORECARD")
    print("=" * width)
    print(f"  {'Incident ID':<28} {'Action':^8} {'Risk':^6} {'Score':^7}")
    print(f"  {'-'*28} {'-'*8} {'-'*6} {'-'*7}")

    for r in results:
        action_str = "OK" if r["action_match"] else "FAIL"
        risk_str = "OK" if r["risk_match"] else "FAIL"
        score_str = f"{r['judge_score']:.2f}" if r["error"] is None else "ERROR"
        err = f"  ! {r['error'][:55]}" if r.get("error") else ""
        print(f"  {r['incident_id']:<28} {action_str:^8} {risk_str:^6} {score_str:^7}{err}")

    print("=" * width)
    print("\n  AGGREGATE METRICS")
    print(f"  {'Metric':<35} {'Current':>8}  {'Baseline':>10}  {'Delta':>6}")
    print(f"  {'-'*35} {'-'*8}  {'-'*10}  {'-'*6}")

    for key, label in [
        ("avg_hypothesis_score_pct", "Avg Hypothesis Score (%)"),
        ("action_accuracy_pct", "Action Accuracy (%)"),
        ("risk_accuracy_pct", "Risk Accuracy (%)"),
    ]:
        curr = metrics[key]
        base = baseline.get(key, 0.0)
        delta = curr - base
        delta_str = f"{'+' if delta >= 0 else ''}{delta:.1f}"
        line = f"  {label:<35} {curr:>7.1f}%  {base:>9.1f}%  {delta_str:>6}"
        print(line.encode("ascii", errors="replace").decode("ascii"))

    print("=" * width)


def main() -> None:
    print("\n[REGRESSION] Loading golden dataset and running harness...")
    results = run_eval_harness(str(GOLDEN_DATASET_PATH))

    valid = [r for r in results if r.get("error") is None]
    total = len(results)

    # --- Aggregate Metrics ---
    action_correct = sum(1 for r in valid if r["action_match"])
    risk_correct = sum(1 for r in valid if r["risk_match"])
    hypothesis_scores = [r["judge_score"] for r in valid]

    avg_hypothesis_score_pct = round(
        (sum(hypothesis_scores) / len(hypothesis_scores)) * 100, 2
    ) if hypothesis_scores else 0.0
    action_accuracy_pct = _pct(action_correct, total)
    risk_accuracy_pct = _pct(risk_correct, total)

    current_metrics = {
        "avg_hypothesis_score_pct": avg_hypothesis_score_pct,
        "action_accuracy_pct": action_accuracy_pct,
        "risk_accuracy_pct": risk_accuracy_pct,
    }

    baseline = _load_baseline()
    _print_scorecard(results, current_metrics, baseline)

    # --- Regression Gate ---
    failures: list[str] = []

    for key, label in [
        ("avg_hypothesis_score_pct", "Avg Hypothesis Score"),
        ("action_accuracy_pct", "Action Accuracy"),
        ("risk_accuracy_pct", "Risk Accuracy"),
    ]:
        curr = current_metrics[key]
        base = baseline.get(key, 0.0)

        if curr < PASS_THRESHOLD:
            failures.append(f"  [FAIL] {label} {curr:.1f}% is below threshold ({PASS_THRESHOLD}%)")
        if curr < base:
            failures.append(f"  [REGRESS] {label}: {curr:.1f}% < baseline {base:.1f}%")

    if failures:
        print("\n  [FAIL] Regression detected:")
        for f in failures:
            print(f)
        print()
        sys.exit(1)

    print(f"\n  [PASS] All metrics above {PASS_THRESHOLD}% threshold and at or above baseline.")
    _save_baseline(current_metrics)
    sys.exit(0)


if __name__ == "__main__":
    main()
