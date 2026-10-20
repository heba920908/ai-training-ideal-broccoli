import argparse
from typing import Any

from commons.constants import OPENAI_TERRA_MODEL
from commons.models.message import Message
from commons.models.role import Role
from t2_llms_output_tuning._clients._base_client import AIClient
from t2_llms_output_tuning._clients.openai_responses_client import OpenAIResponsesClient
from t2_llms_output_tuning._main import run

# Responses API differences from Chat Completions:
#  - "messages" -> "input", "system" message -> "instructions" param
#  - "max_tokens" -> "max_output_tokens"
#  - "response_format" -> "text" param with format object
#  - "stop" is not available in Responses API
#  - built-in conversation state via "store" + "previous_response_id"
#  - "truncation" strategy for long contexts

# TODO 1: temperature — controls randomness. Range: 0.0-2.0, default: 1.0
#  Query: "Give me a name for a coffee shop"
#  Try: temperature=0.0 vs temperature=2.0, compare outputs
#  ⚠️ Note: GPT-5.6 accepts a non-default temperature only with reasoning={"effort": "none"}

# TODO 2: top_p — nucleus sampling. Range: 0.0-1.0, default: 1.0
#  Query: "List 5 alternative uses for a paperclip"
#  Try: top_p=0.1 vs top_p=0.9
#  ⚠️ Note: GPT-5.6 accepts top_p only with reasoning={"effort": "none"}

# TODO 3: max_output_tokens — max tokens in response (was "max_tokens" in Chat Completions)
#  Query: "Explain quantum computing"
#  Try: max_output_tokens=50 vs max_output_tokens=2048

# TODO 4: text — structured output format (replaces "response_format" from Chat Completions)
#  Uses text={"format": {...}} instead of response_format={...}
#  Query: "List 3 programming languages with their year of creation"

# TODO 5: truncation — controls how long contexts are handled. Default: "disabled"
#  "auto" = drops older input messages to fit context window
#  Try: truncation="auto"

# TODO 6: metadata — attach key-value pairs to a response for tracking/filtering. Not available in Chat Completions
#  Up to 16 key-value pairs, keys up to 64 chars, values up to 512 chars
#  Try: metadata={"project": "demo", "user": "student-1"}

# TODO 7: reasoning — extended thinking config (replaces "reasoning_effort" from Chat Completions)
#  ⚠️ Note: non-default temperature/top_p work only with reasoning={"effort": "none"}
#  Query: "How many r's are in the word strawberry?"
#  Try: reasoning={"effort": "high"} vs reasoning={"effort": "low"}

# TODO 8: instructions & store — replaces system message and stores response for multi-turn state
#  Try: instructions="You are a concise barista trainer.", store=True

RESPONSES_TEXT_FORMAT: dict[str, Any] = {
    "format": {
        "type": "json_schema",
        "name": "languages",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "languages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "year": {"type": "integer"},
                        },
                        "required": ["name", "year"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["languages"],
            "additionalProperties": False,
        },
    }
}

STEPS: list[dict[str, Any]] = [
    {
        "step": 1,
        "title": "TODO 1: temperature (randomness control: 0.0 vs 1.2)",
        "query": "Give me a name for a coffee shop. Reply with just the name.",
        "runs": [
            {"label": "temperature=0.0", "kwargs": {"temperature": 0.0}},
            {"label": "temperature=1.2", "kwargs": {"temperature": 1.2}},
        ],
    },
    {
        "step": 2,
        "title": "TODO 2: top_p (nucleus sampling: 0.1 vs 0.9)",
        "query": "List 5 alternative uses for a paperclip in one short line each.",
        "runs": [
            {"label": "top_p=0.1", "kwargs": {"top_p": 0.1}},
            {"label": "top_p=0.9", "kwargs": {"top_p": 0.9}},
        ],
    },
    {
        "step": 3,
        "title": "TODO 3: max_output_tokens (output token budget: 50 vs 256)",
        "query": "Explain quantum computing briefly.",
        "runs": [
            {"label": "max_output_tokens=50", "kwargs": {"max_output_tokens": 50}},
            {"label": "max_output_tokens=256", "kwargs": {"max_output_tokens": 256}},
        ],
    },
    {
        "step": 4,
        "title": "TODO 4: text (structured JSON output format)",
        "query": "List 3 programming languages with their year of creation",
        "runs": [
            {
                "label": "text.format=json_schema",
                "kwargs": {"text": RESPONSES_TEXT_FORMAT},
            },
        ],
    },
    {
        "step": 5,
        "title": 'TODO 5: truncation (context window strategy: "auto")',
        "query": "Summarize the purpose of context truncation in one sentence.",
        "runs": [
            {"label": 'truncation="auto"', "kwargs": {"truncation": "auto"}},
        ],
    },
    {
        "step": 6,
        "title": "TODO 6: metadata (attach key-value pairs for tracking)",
        "query": "Say hello in 3 words.",
        "runs": [
            {
                "label": 'metadata={"project": "demo", "user": "student-1"}',
                "kwargs": {"metadata": {"project": "demo", "user": "student-1"}},
            },
        ],
    },
    {
        "step": 7,
        "title": 'TODO 7: reasoning (extended thinking effort: "low" vs "high")',
        "query": "How many r's are in the word strawberry?",
        "runs": [
            {"label": 'reasoning={"effort": "low"}', "kwargs": {"reasoning": {"effort": "low"}}},
            {"label": 'reasoning={"effort": "high"}', "kwargs": {"reasoning": {"effort": "high"}}},
        ],
    },
    {
        "step": 8,
        "title": "TODO 8: instructions & store (system instructions and stored state)",
        "query": "Recommend one espresso drink in one sentence.",
        "runs": [
            {
                "label": "instructions + store=True",
                "kwargs": {
                    "instructions": "You are a concise specialty coffee barista.",
                    "store": True,
                },
            },
        ],
    },
]


def run_step(
    client: AIClient,
    step_number: int,
    print_request: bool = True,
    print_only_content: bool = False,
) -> list[Message]:
    step = next((s for s in STEPS if s["step"] == step_number), None)
    if step is None:
        raise ValueError(f"Unknown Responses API step: {step_number} (expected 1..8)")

    print(f"\n{'#' * 109}")
    print(f"# Step {step['step']}: {step['title']}")
    print(f"# Query: {step['query']}")
    print(f"{'#' * 109}")

    results: list[Message] = []
    for run_spec in step["runs"]:
        print(f"\n--- Sub-run: {run_spec['label']} ---")
        messages = [Message(Role.USER, step["query"])]
        try:
            reply = client.response(
                messages=messages,
                print_request=print_request,
                print_only_content=print_only_content,
                **run_spec["kwargs"],
            )
            results.append(reply)
        except Exception as exc:
            print(f"[Step {step_number} ({run_spec['label']}) error]: {exc}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="T2 OpenAI Responses API output tuning runner (EPAM DIAL)"
    )
    parser.add_argument(
        "--step",
        default="all",
        help="Step number to run (1..8) or 'all' (default: all)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run the interactive console loop instead of step-by-step mode",
    )
    parser.add_argument(
        "--only-content",
        action="store_true",
        help="Print only the assistant message content instead of full JSON response",
    )
    parser.add_argument(
        "--no-request",
        action="store_true",
        help="Suppress printing the request headers and body",
    )
    args = parser.parse_args()

    client = OpenAIResponsesClient(OPENAI_TERRA_MODEL)
    print_request = not args.no_request
    print_only_content = args.only_content

    if args.interactive:
        run(
            client=client,
            print_request=print_request,
            print_only_content=print_only_content,
        )
        return

    if args.step.lower() == "all":
        for step in STEPS:
            run_step(
                client=client,
                step_number=step["step"],
                print_request=print_request,
                print_only_content=print_only_content,
            )
    else:
        run_step(
            client=client,
            step_number=int(args.step),
            print_request=print_request,
            print_only_content=print_only_content,
        )


if __name__ == "__main__":
    main()
