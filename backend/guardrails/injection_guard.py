import re

# Strict rule-based patterns for detecting prompt injection attempts
MALICIOUS_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"system\s+prompt",
    r"mark\s+this\s+as\s+resolved",
    r"disregard\s+all\s+prior",
    r"override\s+system",
    r"forget\s+all\s+instructions",
]


def detect_prompt_injection(logs: str) -> bool:
    """
    Scans log strings for prompt injection attempts using strict regex matching.
    Returns True if an injection attempt is detected, otherwise False.
    """
    if not logs:
        return False

    logs_lower = logs.lower()
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, logs_lower):
            return True

    return False
