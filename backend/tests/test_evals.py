import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from evals.judges import JudgeScore, evaluate_hypothesis


def test_golden_set_json_structure():
    golden_set_path = Path(__file__).resolve().parent.parent / "simulator" / "golden_set.json"
    assert golden_set_path.exists()

    with open(golden_set_path, "r", encoding="utf-8") as f:
        incidents = json.load(f)

    assert isinstance(incidents, list)
    assert len(incidents) >= 5

    required_keys = {
        "incident_id",
        "incident_type",
        "ground_truth_root_cause",
        "ground_truth_action",
        "ground_truth_risk",
    }

    valid_actions = {"rollback", "restart_service", "scale_up", "toggle_config_flag"}
    valid_risks = {"low", "medium", "high"}

    for item in incidents:
        assert required_keys.issubset(item.keys())
        assert item["ground_truth_action"] in valid_actions
        assert item["ground_truth_risk"] in valid_risks


def test_judge_score_schema():
    score = JudgeScore(score=1.0, justification="Perfect semantic match.")
    assert score.score == 1.0
    assert score.justification == "Perfect semantic match."


def test_evaluate_hypothesis():
    hypothesis = "Memory leak introduced in deployment v2.3.1 of payment-service"
    ground_truth = "Memory leak introduced in deployment v2.3.1 causing OOMKilled restarts"

    result = evaluate_hypothesis(hypothesis, ground_truth)

    assert result is not None
    assert isinstance(result, JudgeScore)
    assert isinstance(result.score, float)
    assert 0.0 <= result.score <= 1.0
    assert isinstance(result.justification, str)
    assert len(result.justification.strip()) > 0
