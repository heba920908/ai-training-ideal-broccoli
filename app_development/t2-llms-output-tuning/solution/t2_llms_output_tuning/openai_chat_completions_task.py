import argparse
from typing import Any

from commons.constants import OPENAI_TERRA_MODEL
from commons.models.message import Message
from commons.models.role import Role
from t2_llms_output_tuning._clients._base_client import AIClient
from t2_llms_output_tuning._clients.openai_chat_completions_client import (
    OpenAIChatCompletionsClient,
)
from t2_llms_output_tuning._main import run

# TODO 1: n — number of completions to generate per request. Default: 1
#  ⚠️ Note: NOT available in Responses API
#  Query: "Give me a name for a coffee shop"
#  Try: n=3 — returns 3 different completions in choices[]

# TODO 2: temperature — controls randomness. Range: 0.0-2.0, default: 1.0
#  Lower = more deterministic, higher = more creative
#  Query: "Why white is white?"
#  Try: temperature=0.0 vs temperature=2.0, compare outputs
#  ⚠️ Note: GPT-5.6 accepts a non-default temperature only with reasoning_effort="none"
#  ⚠️ Note: it is okay that after temperature=1.5 you get some odd characters in output 😅

# TODO 3: top_p — nucleus sampling, keeps tokens within cumulative probability. Range: 0.0-1.0, default: 1.0
#  Lower = fewer token choices, more focused output
#  Query: "List 5 alternative uses for a paperclip"
#  Try: top_p=0.1 vs top_p=0.9
#  ⚠️ Note: GPT-5.6 accepts top_p only with reasoning_effort="none"

# TODO 4: max_tokens — max number of tokens in the response. Default: model-dependent
#  ⚠️ Note: Will work for models like gpt-4o. For gpt-5+ - `max_completion_tokens`.
#  Query: "Explain quantum computing"
#  Try: max_tokens=50 vs max_tokens=2048

# TODO 5: stop — list of strings (up to 4) that stop generation when encountered
#  ⚠️ Note: Will work for models like gpt-4o
#  Query: "Count from 1 to 20, comma separated"
#  Try: stop=["5"] — generation stops before reaching 5

# TODO 6: response_format — enforce structured output format
#  "text" (default) or "json_schema" with a schema definition
#  Query: "List 3 programming languages with their year of creation"
#  Try: response_format={"type": "json_schema", ...}

# TODO 7: frequency_penalty — penalizes tokens based on how often they appeared so far. Range: -2.0 to 2.0, default: 0
#  ⚠️ Note: Will work for models like gpt-4o
#  Positive = reduces repetition, negative = encourages repetition
#  Query: "Write a paragraph about the ocean"
#  Try: frequency_penalty=0.0 vs frequency_penalty=1.5

# TODO 8: presence_penalty — penalizes tokens based on whether they appeared at all. Range: -2.0 to 2.0, default: 0
#  ⚠️ Note: Will work for models like gpt-4o
#  Positive = encourages new topics, negative = stays on topic
#  Query: "Write a paragraph about the ocean"
#  Try: presence_penalty=0.0 vs presence_penalty=1.5

# TODO 9: seed — attempts deterministic output. Same seed + same input = same output (best effort)
#  ⚠️ Note: Will work for models like gpt-4o
#  Query: "Give me a name for a coffee shop"
#  Try: seed=42 — run twice with the same seed and compare outputs

# TODO 10: reasoning_effort — controls how much thinking the model does. Values: "none", "low", "medium" (default), "high", "xhigh"
#  Lower effort = faster, cheaper responses; higher = more thorough reasoning
#  ⚠️ Note: non-default temperature/top_p work only with reasoning_effort="none"
#  Query: "How many r's are in the word strawberry?"
#  Try: reasoning_effort="low" vs reasoning_effort="high"

LANGUAGES_JSON_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
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
    },
}

STEPS: list[dict[str, Any]] = [
    {
        "step": 1,
        "title": "TODO 1: n (multiple completion choices)",
        "query": "Give me a name for a coffee shop. Reply with just the name.",
        "runs": [
            {"label": "n=3", "kwargs": {"n": 3}},
        ],
    },
    {
        "step": 2,
        "title": "TODO 2: temperature (randomness control: 0.0 vs 1.2)",
        "query": "Why white is white? Reply in 2 short sentences.",
        "runs": [
            {"label": "temperature=0.0", "kwargs": {"temperature": 0.0}},
            {"label": "temperature=1.2", "kwargs": {"temperature": 1.2}},
        ],
    },
    {
        "step": 3,
        "title": "TODO 3: top_p (nucleus sampling: 0.1 vs 0.9)",
        "query": "List 5 alternative uses for a paperclip in one short line each.",
        "runs": [
            {"label": "top_p=0.1", "kwargs": {"top_p": 0.1}},
            {"label": "top_p=0.9", "kwargs": {"top_p": 0.9}},
        ],
    },
    {
        "step": 4,
        "title": "TODO 4: max_tokens (output token budget: 50 vs 256)",
        "query": "Explain quantum computing briefly.",
        "runs": [
            {"label": "max_tokens=50", "kwargs": {"max_tokens": 50}},
            {"label": "max_tokens=256", "kwargs": {"max_tokens": 256}},
        ],
    },
    {
        "step": 5,
        "title": "TODO 5: stop (custom stop sequences)",
        "query": "Count from 1 to 20, comma separated",
        "runs": [
            {"label": 'stop=["5"]', "kwargs": {"stop": ["5"]}},
        ],
    },
    {
        "step": 6,
        "title": "TODO 6: response_format (structured JSON output with json_schema)",
        "query": "List 3 programming languages with their year of creation",
        "runs": [
            {
                "label": "response_format=json_schema",
                "kwargs": {"response_format": LANGUAGES_JSON_SCHEMA},
            },
        ],
    },
    {
        "step": 7,
        "title": "TODO 7: frequency_penalty (0.0 vs 1.5)",
        "query": "Write a short 3-sentence paragraph about the ocean.",
        "runs": [
            {"label": "frequency_penalty=0.0", "kwargs": {"frequency_penalty": 0.0}},
            {"label": "frequency_penalty=1.5", "kwargs": {"frequency_penalty": 1.5}},
        ],
    },
    {
        "step": 8,
        "title": "TODO 8: presence_penalty (0.0 vs 1.5)",
        "query": "Write a short 3-sentence paragraph about the ocean.",
        "runs": [
            {"label": "presence_penalty=0.0", "kwargs": {"presence_penalty": 0.0}},
            {"label": "presence_penalty=1.5", "kwargs": {"presence_penalty": 1.5}},
        ],
    },
    {
        "step": 9,
        "title": "TODO 9: seed (best-effort determinism: seed=42 run twice)",
        "query": "Give me a name for a coffee shop. Reply with just the name.",
        "runs": [
            {"label": "seed=42 (run 1)", "kwargs": {"seed": 42, "temperature": 0.0}},
            {"label": "seed=42 (run 2)", "kwargs": {"seed": 42, "temperature": 0.0}},
        ],
    },
    {
        "step": 10,
        "title": 'TODO 10: reasoning_effort ("low" vs "high")',
        "query": "How many r's are in the word strawberry?",
        "runs": [
            {"label": 'reasoning_effort="low"', "kwargs": {"reasoning_effort": "low"}},
            {"label": 'reasoning_effort="high"', "kwargs": {"reasoning_effort": "high"}},
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
        raise ValueError(f"Unknown Chat Completions step: {step_number} (expected 1..10)")

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
        description="T2 OpenAI Chat Completions output tuning runner (EPAM DIAL)"
    )
    parser.add_argument(
        "--step",
        default="all",
        help="Step number to run (1..10) or 'all' (default: all)",
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

    client = OpenAIChatCompletionsClient(model_name=OPENAI_TERRA_MODEL)
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
