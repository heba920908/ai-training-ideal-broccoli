from t7_guardrails.guardrails import HARDENED_SYSTEM_PROMPT, PROFILE_T1
from t7_guardrails.runner import main as run_cli

SYSTEM_PROMPT = HARDENED_SYSTEM_PROMPT
PROFILE = PROFILE_T1


def main():
    run_cli("t1")


if __name__ == "__main__":
    main()
