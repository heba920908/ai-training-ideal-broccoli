import json

import pytest
from t13_final_task.task.agent.conversation_manager import ConversationManager
from t13_final_task.task.agent.models import Message, Role


class FakeRedis:
    def __init__(self):
        self.values, self.sorted = {}, {}
        self.closed = False

    async def set(self, key, value):
        self.values[key] = value

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        return 1 if self.values.pop(key, None) is not None else 0

    async def zadd(self, key, mapping):
        self.sorted.setdefault(key, {}).update(mapping)

    async def zrevrange(self, key, start, end):
        items = sorted(self.sorted.get(key, {}).items(), key=lambda kv: kv[1], reverse=True)
        stop = None if end == -1 else end + 1
        return [member for member, _ in items[start:stop]]

    async def zrem(self, key, member):
        self.sorted.get(key, {}).pop(member, None)

    async def ping(self):
        return True

    async def aclose(self):
        self.closed = True


class FakeAgent:
    def __init__(self, interrupt=False):
        self.seen, self.interrupt = [], interrupt

    async def response(self, messages):
        self.seen.append([m.role for m in messages])
        reply = Message(role=Role.ASSISTANT, content="answer")
        messages.append(reply)
        return reply

    async def stream_response(self, messages):
        self.seen.append([m.role for m in messages])
        messages.append(
            Message(
                role=Role.ASSISTANT,
                content="",
                tool_calls=[
                    {"id": "a", "type": "function", "function": {"name": "t", "arguments": "{}"}},
                    {"id": "b", "type": "function", "function": {"name": "t", "arguments": "{}"}},
                ],
            )
        )
        messages.append(Message(role=Role.TOOL, tool_call_id="a", content="r1"))
        yield 'data: {"tool_activity": {}}\n\n'
        if self.interrupt:
            return
        messages.append(Message(role=Role.TOOL, tool_call_id="b", content="r2"))
        messages.append(Message(role=Role.ASSISTANT, content="final"))
        yield "data: [DONE]\n\n"


@pytest.fixture
def redis_client():
    return FakeRedis()


def manager(redis_client, agent=None):
    return ConversationManager(agent or FakeAgent(), redis_client, "SYSTEM PROMPT")


async def test_create_list_get_delete(redis_client):
    cm = manager(redis_client)
    first = await cm.create_conversation("first")
    second = await cm.create_conversation("second")

    assert first["messages"] == [] and first["created_at"].endswith("+00:00")
    assert f"conversation:{first['id']}" in redis_client.values
    summaries = await cm.list_conversations()
    assert [s["id"] for s in summaries] == [second["id"], first["id"]]
    assert summaries[0] == {
        "id": second["id"],
        "title": "second",
        "created_at": second["created_at"],
        "updated_at": second["updated_at"],
        "message_count": 0,
    }
    assert (await cm.get_conversation(first["id"]))["title"] == "first"

    assert await cm.delete_conversation(first["id"]) is True
    assert await cm.get_conversation(first["id"]) is None
    assert first["id"] not in redis_client.sorted["conversations:list"]
    assert await cm.delete_conversation(first["id"]) is False


async def test_unknown_conversation_chat_raises(redis_client):
    with pytest.raises(ValueError):
        await manager(redis_client).chat(Message(role=Role.USER, content="x"), "nope")
    assert redis_client.values == {}


async def test_non_stream_chat_injects_system_once_and_persists(redis_client):
    agent = FakeAgent()
    cm = manager(redis_client, agent)
    conversation = await cm.create_conversation("t")

    result = await cm.chat(Message(role=Role.USER, content="one"), conversation["id"], stream=False)
    await cm.chat(Message(role=Role.USER, content="two"), conversation["id"], stream=False)

    assert result == {"content": "answer", "conversation_id": conversation["id"]}
    assert agent.seen[0] == [Role.SYSTEM, Role.USER]
    assert agent.seen[1] == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.USER]
    stored = await cm.get_conversation(conversation["id"])
    assert stored["messages"][0] == {"role": "system", "content": "SYSTEM PROMPT"}
    assert len(stored["messages"]) == 5
    assert stored["updated_at"] >= stored["created_at"]


async def test_stream_chat_emits_conversation_id_first_and_saves(redis_client):
    cm = manager(redis_client)
    conversation = await cm.create_conversation("t")
    stream = await cm.chat(Message(role=Role.USER, content="hi"), conversation["id"], stream=True)
    lines = [line async for line in stream]

    assert json.loads(lines[0][6:]) == {"conversation_id": conversation["id"]}
    assert lines[-1] == "data: [DONE]\n\n"
    stored = (await cm.get_conversation(conversation["id"]))["messages"]
    assert [m["role"] for m in stored] == [
        "system",
        "user",
        "assistant",
        "tool",
        "tool",
        "assistant",
    ]
    assert stored[2]["tool_calls"][1]["id"] == "b"


async def test_interrupted_stream_trims_unanswered_tool_calls(redis_client):
    cm = manager(redis_client, FakeAgent(interrupt=True))
    conversation = await cm.create_conversation("t")
    stream = await cm.chat(Message(role=Role.USER, content="hi"), conversation["id"], stream=True)
    [line async for line in stream]

    stored = (await cm.get_conversation(conversation["id"]))["messages"]
    assert [m["role"] for m in stored] == ["system", "user"]


async def test_client_disconnect_still_saves_consistent_history(redis_client):
    cm = manager(redis_client)
    conversation = await cm.create_conversation("t")
    stream = await cm.chat(Message(role=Role.USER, content="hi"), conversation["id"], stream=True)
    await stream.__anext__()
    await stream.__anext__()
    await stream.aclose()

    stored = (await cm.get_conversation(conversation["id"]))["messages"]
    assert [m["role"] for m in stored] == ["system", "user"]
