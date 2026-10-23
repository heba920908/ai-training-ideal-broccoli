from t7_guardrails.guardrails import (
    INPUT_VALIDATION_PROMPT,
    PROFILE_T1,
    WEAK_SYSTEM_PROMPT,
    Dial,
    Validation,
    validate_input,
)
from t7_guardrails.runner import main as run_cli

SYSTEM_PROMPT = WEAK_SYSTEM_PROMPT
PROFILE = PROFILE_T1
VALIDATION_PROMPT = INPUT_VALIDATION_PROMPT


def validate(user_input: str, dial: Dial | None = None) -> Validation:
    owns_client = dial is None
    active_dial = dial or Dial.from_env()
    try:
        return validate_input(active_dial, user_input)
    finally:
        if owns_client:
            active_dial.close()


def main():
    run_cli("t2")


if __name__ == "__main__":
    main()
