import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from commons.models.message import Message
from commons.models.role import Role
from t2_llms_output_tuning._clients.openai_chat_completions_client import (
    OpenAIChatCompletionsClient,
)
from t2_llms_output_tuning._clients.openai_responses_client import (
    OpenAIResponsesClient,
)


def _import_task_module(module_name: str) -> Any:
    import importlib
    with patch("builtins.input", return_value="exit"), patch.dict(
        os.environ, {"OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY") or "dummy-key-123456"}
    ), patch("t2_llms_output_tuning._clients.openai_chat_completions_client.OPENAI_API_KEY", "dummy-key-123456"), patch(
        "t2_llms_output_tuning._clients.openai_responses_client.OPENAI_API_KEY", "dummy-key-123456"
    ):
        return importlib.import_module(module_name)


class RecordingClient:
    """Fake AIClient that records calls to response()."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def response(
        self,
        messages: list[Message],
        print_request: bool,
        print_only_content: bool,
        **kwargs: Any,
    ) -> Message:
        self.calls.append(
            {
                "messages": [m.to_dict() for m in messages],
                "print_request": print_request,
                "print_only_content": print_only_content,
                "kwargs": kwargs,
            }
        )
        return Message(Role.ASSISTANT, "recorded-reply")


def test_openai_responses_client_derives_base_url_from_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "t2_llms_output_tuning._clients.openai_responses_client.OPENAI_API_KEY",
        "fake-key-123",
    )
    monkeypatch.setattr(
        "t2_llms_output_tuning._clients.openai_responses_client.OPENAI_RESPONSES_ENDPOINT",
        "https://ai-proxy.lab.epam.com/openai/deployments/test-model/responses",
    )

    client = OpenAIResponsesClient(model_name="test-model")
    assert str(client._client.base_url).rstrip("/") == (
        "https://ai-proxy.lab.epam.com/openai/deployments/test-model"
    )


def test_safe_headers_redacts_api_key_completely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "t2_llms_output_tuning._clients.openai_chat_completions_client.OPENAI_API_KEY",
        "fake-key-9999",
    )
    client = OpenAIChatCompletionsClient(model_name="test-model")
    safe = client._safe_headers({"Authorization": client._api_key})
    assert "9999" not in safe["Authorization"]
    assert "fake" not in safe["Authorization"]
    assert safe["Authorization"] == "Bearer <redacted>"


def test_chat_completions_steps_cover_todos_1_to_10() -> None:
    chat_task = _import_task_module("t2_llms_output_tuning.openai_chat_completions_task")
    assert hasattr(chat_task, "STEPS"), "STEPS catalog missing in openai_chat_completions_task"
    step_numbers = [step["step"] for step in chat_task.STEPS]
    assert step_numbers == list(range(1, 11))

    fake_client = RecordingClient()
    for step in chat_task.STEPS:
        chat_task.run_step(
            client=fake_client,  # type: ignore[arg-type]
            step_number=step["step"],
            print_request=False,
            print_only_content=True,
        )

    all_kwarg_keys = {
        key
        for call in fake_client.calls
        for key in call["kwargs"].keys()
    }
    expected_keys = {
        "n",
        "temperature",
        "top_p",
        "max_tokens",
        "stop",
        "response_format",
        "frequency_penalty",
        "presence_penalty",
        "seed",
        "reasoning_effort",
    }
    assert expected_keys.issubset(all_kwarg_keys)


def test_responses_steps_cover_todos_1_to_8() -> None:
    responses_task = _import_task_module("t2_llms_output_tuning.openai_responses_task")
    assert hasattr(responses_task, "STEPS"), "STEPS catalog missing in openai_responses_task"
    step_numbers = [step["step"] for step in responses_task.STEPS]
    assert step_numbers == list(range(1, 9))

    fake_client = RecordingClient()
    for step in responses_task.STEPS:
        responses_task.run_step(
            client=fake_client,  # type: ignore[arg-type]
            step_number=step["step"],
            print_request=False,
            print_only_content=True,
        )

    all_kwarg_keys = {
        key
        for call in fake_client.calls
        for key in call["kwargs"].keys()
    }
    expected_keys = {
        "temperature",
        "top_p",
        "max_output_tokens",
        "text",
        "truncation",
        "metadata",
        "reasoning",
        "instructions",
        "store",
    }
    assert expected_keys.issubset(all_kwarg_keys)


def test_run_step_handles_http_or_model_error_gracefully(capsys: pytest.CaptureFixture[str]) -> None:
    chat_task = _import_task_module("t2_llms_output_tuning.openai_chat_completions_task")
    failing_client = MagicMock()
    failing_client.response.side_effect = Exception("HTTP 400: unsupported parameter")

    chat_task.run_step(
        client=failing_client,
        step_number=1,
        print_request=False,
        print_only_content=True,
    )
    captured = capsys.readouterr().out
    assert "HTTP 400: unsupported parameter" in captured


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "").startswith("<"),
    reason="Requires live OPENAI_API_KEY in environment (.env)",
)
def test_live_chat_completions_steps() -> None:
    chat_task = _import_task_module("t2_llms_output_tuning.openai_chat_completions_task")
    model_name = os.getenv("OPENAI_MODEL", "")
    client = OpenAIChatCompletionsClient(model_name=model_name)
    for step in chat_task.STEPS:
        chat_task.run_step(
            client=client,
            step_number=step["step"],
            print_request=True,
            print_only_content=True,
        )


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "").startswith("<"),
    reason="Requires live OPENAI_API_KEY in environment (.env)",
)
def test_live_responses_steps() -> None:
    responses_task = _import_task_module("t2_llms_output_tuning.openai_responses_task")
    model_name = os.getenv("OPENAI_MODEL", "")
    client = OpenAIResponsesClient(model_name=model_name)
    for step in responses_task.STEPS:
        responses_task.run_step(
            client=client,
            step_number=step["step"],
            print_request=True,
            print_only_content=True,
        )
