from typing import Literal


def classify_risk(action_type: str, target: str = "") -> Literal["low", "medium", "high"]:
    """
    Classifies the blast-radius risk level of a proposed remediation action.

    Logic:
    - 'rollback' -> 'high'
    - 'restart_service' or 'toggle_config_flag' -> 'medium'
    - 'scale_up' -> 'low'
    """
    if action_type == "rollback":
        return "high"
    elif action_type in ["restart_service", "toggle_config_flag"]:
        return "medium"
    elif action_type == "scale_up":
        return "low"
    return "low"
