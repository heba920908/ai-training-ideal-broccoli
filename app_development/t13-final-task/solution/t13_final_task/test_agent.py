import json

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from t13_final_task.task.agent.models import Message, Role
from t13_final_task.task.agent.tools.base import BaseTool
from t13_final_task.task.agent.ums_agent import UMSAgent


def completion(content=None, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {"id": cid, "type": "function", "function": {"name": name, "arguments": args}}
            for cid, name, args in tool_calls
        ]
    return ChatCompletion.model_validate(
        {
            "id": "c",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }
            ],
        }
    )


def chunk(content=None, tool_calls=None, finish=None):
    delta = {}
    if content is not None:
        delta["content"] = content
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    return ChatCompletionChunk.model_validate(
        {
            "id": "k",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
    )


class AsyncStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for item in self._chunks:
            if isinstance(item, Exception):
                raise item
            yield item


class FakeCompletions:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return AsyncStream(item) if isinstance(item, list) else item


class FakeOpenAI:
    def __init__(self, scripted):
        self.chat = type("Chat", (), {})()
        self.chat.completions = FakeCompletions(scripted)


class FakeGuardrail:
    def redact(self, text):
        return text.replace("SECRET", "***")


class EchoTool(BaseTool):
    def __init__(self, name="search_user", result="user SECRET", error=None):
        self._name, self._result, self._error, self.calls = name, result, error, []

    async def _execute(self, arguments):
        self.calls.append(arguments)
        if self._error:
            raise self._error
        return self._result

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return "d"

    @property
    def parameters(self):
        return {"type": "object", "properties": {}}


def make_agent(scripted, tools=None, max_tool_rounds=10):
    client = FakeOpenAI(scripted)
    agent = UMSAgent(
        api_key="k",
        model="any-model",
        tools=tools if tools is not None else [EchoTool()],
        client=client,
        guardrail=FakeGuardrail(),
        max_tool_rounds=max_tool_rounds,
    )
    return agent, client.chat.completions


def user(text="hi"):
    return [Message(role=Role.SYSTEM, content="sys"), Message(role=Role.USER, content=text)]


async def test_final_answer_without_tools_uses_configured_model_only():
    agent, api = make_agent([completion("hello")])
    messages = user()
    result = await agent.response(messages)

    assert result.content == "hello" and result.role == Role.ASSISTANT
    request = api.requests[0]
    assert request["model"] == "any-model"
    assert request["stream"] is False
    assert request["tools"][0]["function"]["name"] == "search_user"
    assert set(request) == {"model", "messages", "tools", "stream"}


async def test_tool_round_then_answer_keeps_order_and_redacts():
    tool = EchoTool()
    agent, api = make_agent(
        [completion(tool_calls=[("call-1", "search_user", '{"q": 1}')]), completion("done")],
        tools=[tool],
    )
    messages = user()
    result = await agent.response(messages)

    assert tool.calls == [{"q": 1}]
    roles = [m.role for m in messages]
    assert roles == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.TOOL, Role.ASSISTANT]
    assert messages[2].tool_calls[0]["id"] == "call-1"
    assert messages[3].tool_call_id == "call-1" and messages[3].content == "user ***"
    assert "SECRET" not in json.dumps(api.requests[1]["messages"])
    assert result.content == "done"


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("missing_tool", "{}", "unknown tool"),
        ("search_user", "{not json", "invalid"),
        ("search_user", "[1, 2]", "invalid"),
    ],
)
async def test_bad_tool_calls_become_correlated_errors(name, arguments, expected):
    tool = EchoTool()
    agent, _ = make_agent(
        [completion(tool_calls=[("id-x", name, arguments)]), completion("ok")], tools=[tool]
    )
    messages = user()
    await agent.response(messages)
    tool_message = messages[3]
    assert tool_message.tool_call_id == "id-x"
    assert expected in tool_message.content.lower()
    assert tool.calls == []


async def test_tool_exception_is_reported_and_loop_continues():
    agent, _ = make_agent(
        [completion(tool_calls=[("id-1", "search_user", "{}")]), completion("recovered")],
        tools=[EchoTool(error=RuntimeError("down"))],
    )
    messages = user()
    result = await agent.response(messages)
    assert messages[3].content.startswith("ERROR")
    assert result.content == "recovered"


async def test_round_limit_stops_without_another_call():
    looping = [completion(tool_calls=[(f"id-{i}", "search_user", "{}")]) for i in range(2)]
    agent, api = make_agent(looping, max_tool_rounds=2)
    messages = user()
    result = await agent.response(messages)

    assert len(api.requests) == 2
    assert "limit" in result.content.lower()
    assert messages[-1] is result
    assert messages[-2].role == Role.TOOL


def events(lines):
    parsed = []
    for line in lines:
        assert line.startswith("data: ") and line.endswith("\n\n")
        payload = line[6:].strip()
        parsed.append(payload if payload == "[DONE]" else json.loads(payload))
    return parsed


async def collect(agent, messages):
    return events([line async for line in agent.stream_response(messages)])


async def test_stream_forwards_content_and_finishes():
    agent, api = make_agent([[chunk("Hel"), chunk("lo"), chunk(finish="stop")]])
    messages = user()
    result = await collect(agent, messages)

    contents = [e["choices"][0]["delta"].get("content") for e in result[:-1]]
    assert contents[:2] == ["Hel", "lo"]
    assert result[-2]["choices"][0]["finish_reason"] == "stop"
    assert result[-1] == "[DONE]"
    assert api.requests[0]["stream"] is True
    assert messages[-1].role == Role.ASSISTANT and messages[-1].content == "Hello"


async def test_stream_reassembles_fragmented_tool_call_and_notifies():
    tool = EchoTool()
    first = [
        chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call-7",
                    "type": "function",
                    "function": {"name": "search_", "arguments": '{"sur'},
                }
            ]
        ),
        chunk(
            tool_calls=[{"index": 0, "function": {"name": "user", "arguments": 'name": "Smith"}'}}]
        ),
        chunk(finish="tool_calls"),
    ]
    agent, api = make_agent([first, [chunk("Found."), chunk(finish="stop")]], tools=[tool])
    messages = user()
    result = await collect(agent, messages)

    assert tool.calls == [{"surname": "Smith"}]
    activity = [e["tool_activity"] for e in result if isinstance(e, dict) and "tool_activity" in e]
    assert activity == [
        {"type": "call", "name": "search_user", "arguments": {"surname": "Smith"}},
        {"type": "result", "name": "search_user", "content": "user ***"},
    ]
    assert messages[2].tool_calls == [
        {
            "id": "call-7",
            "type": "function",
            "function": {"name": "search_user", "arguments": '{"surname": "Smith"}'},
        }
    ]
    assert messages[3].content == "user ***"
    assert messages[-1].content == "Found."
    assert result.count("[DONE]") == 1 and result[-1] == "[DONE]"
    assert len(api.requests) == 2


async def test_stream_provider_failure_emits_safe_error():
    agent, _ = make_agent([[chunk("partial"), RuntimeError("api-key=leaky")]])
    result = await collect(agent, user())
    errors = [e for e in result if isinstance(e, dict) and "error" in e]
    assert errors and "leaky" not in errors[0]["error"]
    assert result[-1] == "[DONE]"


async def test_stream_round_limit():
    loop_chunk = [
        chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "a",
                    "type": "function",
                    "function": {"name": "search_user", "arguments": "{}"},
                }
            ]
        ),
    ]
    agent, api = make_agent([loop_chunk, loop_chunk], max_tool_rounds=2)
    messages = user()
    result = await collect(agent, messages)
    assert len(api.requests) == 2
    assert "limit" in messages[-1].content.lower()
    assert result[-1] == "[DONE]"
