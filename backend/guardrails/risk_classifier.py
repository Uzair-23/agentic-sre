from typing import Literal


def classify_risk(action_type: str, target: str = "") -> Literal["low", "medium", "high"]:
    """
    Classifies the blast-radius risk level of a proposed remediation action.

    Logic:
    - If action is 'rollback', return 'high'.
    - If action is 'restart_service', return 'medium'.
    - If action is 'scale_up' or 'toggle_config_flag', return 'low'.
    """
    if action_type == "rollback":
        return "high"
    elif action_type == "restart_service":
        return "medium"
    elif action_type in ["scale_up", "toggle_config_flag"]:
        return "low"
    return "low"
