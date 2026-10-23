from t7_guardrails.guardrails import (
    FILTER_SYSTEM_PROMPT,
    OUTPUT_VALIDATION_PROMPT,
    PROFILE_T3,
    WEAK_SYSTEM_PROMPT,
    Dial,
    Validation,
    validate_output,
)
from t7_guardrails.runner import main as run_cli

SYSTEM_PROMPT = WEAK_SYSTEM_PROMPT
PROFILE = PROFILE_T3
VALIDATION_PROMPT = OUTPUT_VALIDATION_PROMPT

__all__ = [
    "FILTER_SYSTEM_PROMPT",
    "PROFILE",
    "SYSTEM_PROMPT",
    "VALIDATION_PROMPT",
    "Validation",
    "main",
    "validate",
]


def validate(ai_response: str, dial: Dial | None = None) -> Validation:
    owns_client = dial is None
    active_dial = dial or Dial.from_env()
    try:
        return validate_output(active_dial, ai_response)
    finally:
        if owns_client:
            active_dial.close()


def main(soft_response: bool = True):
    run_cli("t3", default_soft=soft_response)


if __name__ == "__main__":
    main(soft_response=True)
