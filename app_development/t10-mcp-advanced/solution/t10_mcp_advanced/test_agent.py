import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from commons.models.message import Message
from commons.models.role import Role
from t10_mcp_advanced.agent.agent import CustomAgentMCP


@pytest.mark.parametrize(
    "arguments,name", [("{", "echo"), ("[]", "echo"), ("{}", "missing")]
)
def test_invalid_tool_calls_become_correlated_tool_errors(arguments, name):
    agent = CustomAgentMCP(
        "offline-fixture",
        "configured-model",
        [],
        {},
        base_url="https://dial.example.invalid",
    )
    call = {
        "id": "call-7",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
    messages = []

    async def scenario():
        try:
            await agent._call_tools(
                Message(Role.ASSISTANT, "", tool_calls=[call]), messages
            )
        finally:
            await agent.openai.close()

    asyncio.run(scenario())
    assert messages[0].tool_call_id == "call-7"
    assert "error" in messages[0].content.lower()


def test_tool_round_limit_stops_repeated_model_calls():
    agent = CustomAgentMCP(
        "offline-fixture",
        "configured-model",
        [],
        {},
        base_url="https://dial.example.invalid",
        max_tool_rounds=2,
    )
    call = {
        "id": "loop",
        "type": "function",
        "function": {"name": "missing", "arguments": "{}"},
    }
    agent._stream_response = AsyncMock(
        return_value=Message(Role.ASSISTANT, "", tool_calls=[call])
    )

    async def scenario():
        try:
            return await agent.get_completion([])
        finally:
            await agent.openai.close()

    assert "limit" in asyncio.run(scenario()).content
    assert agent._stream_response.await_count == 2


def test_dial_request_uses_configured_model_and_api_key_without_model_parameters():
    async def scenario():
        def handler(request):
            assert (
                str(request.url)
                == "https://dial.example.invalid/openai/deployments/test/chat/completions"
            )
            assert request.headers["Api-Key"] == "offline-fixture"
            body = json.loads(request.content)
            assert body["model"] == "configured-model"
            assert "temperature" not in body and "reasoning_effort" not in body
            data = {
                "id": "offline",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "configured-model",
                "choices": [
                    {"index": 0, "delta": {"content": "ok"}, "finish_reason": None}
                ],
            }
            return httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                text=f"data: {json.dumps(data)}\n\ndata: [DONE]\n\n",
            )

        agent = CustomAgentMCP(
            "offline-fixture",
            "configured-model",
            [],
            {},
            base_url="https://dial.example.invalid/openai/deployments/test",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            assert (
                await agent._stream_response([Message(Role.USER, "hello")])
            ).content == "ok"
        finally:
            await agent.openai.close()

    asyncio.run(scenario())


def test_ancestor_environment_loading_preserves_exports(tmp_path, monkeypatch):
    from t10_mcp_advanced.config import load_settings

    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=offline-fixture\nOPENAI_BASE_URL=https://dial.example.invalid/deployment\nOPENAI_MODEL=from-file\n"
    )
    child = tmp_path / "nested"
    child.mkdir()
    monkeypatch.setenv("OPENAI_MODEL", "exported")
    settings = load_settings(child)
    assert settings.model == "exported"
    assert settings.base_url == "https://dial.example.invalid/deployment"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://dial.example.invalid",
        "https://user:password@dial.example.invalid",
        "https://dial.example.invalid/path?token=value",
    ],
)
def test_unsafe_provider_urls_rejected(url):
    from t10_mcp_advanced.config import validate_base_url

    with pytest.raises(ValueError):
        validate_base_url(url)


def test_duplicate_tool_names_are_rejected():
    from t10_mcp_advanced.agent.app import register_tools

    schema = {
        "type": "function",
        "function": {"name": "echo", "parameters": {"type": "object"}},
    }
    tools, owners = [], {}
    register_tools(tools, owners, [schema], "first")
    with pytest.raises(ValueError, match="Duplicate"):
        register_tools(tools, owners, [schema], "second")
    assert owners["echo"] == "first"
