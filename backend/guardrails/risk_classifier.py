from typing import Literal


def classify_risk(action_type: str, target: str) -> Literal["low", "medium", "high"]:
    """
    Classifies the blast-radius risk level of a proposed remediation action.

    Logic:
    - Returns 'high' if action_type is 'rollback' or target contains 'payment'.
    - Returns 'medium' if action_type is 'restart_service'.
    - Returns 'low' otherwise.
    """
    target_lower = target.lower() if target else ""

    if action_type == "rollback" or "payment" in target_lower:
        return "high"
    if action_type == "restart_service":
        return "medium"
    return "low"
