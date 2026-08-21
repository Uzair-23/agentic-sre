from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Initialize globally to prevent cold-start overhead per invocation
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def scrub_pii(text: str) -> str:
    """
    Analyzes input text for EMAIL_ADDRESS, PHONE_NUMBER, and PERSON entities.
    Anonymizes detected entities by replacing them with <REDACTED>.
    """
    if not text:
        return text

    results = analyzer.analyze(
        text=text,
        entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"],
        language="en",
    )

    operators = {
        "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})
    }

    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )

    return anonymized_result.text
