from t7_guardrails.guardrails import (
    PROFILE_T4,
    WEAK_SYSTEM_PROMPT,
    PresidioStreamingPIIGuardrail,
    StreamingPIIGuardrail,
)
from t7_guardrails.runner import main as run_cli

SYSTEM_PROMPT = WEAK_SYSTEM_PROMPT
PROFILE = PROFILE_T4

__all__ = [
    "PROFILE",
    "SYSTEM_PROMPT",
    "PresidioStreamingPIIGuardrail",
    "StreamingPIIGuardrail",
    "main",
]


def main():
    run_cli("t4")


if __name__ == "__main__":
    main()
