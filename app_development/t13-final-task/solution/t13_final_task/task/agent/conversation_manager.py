import json
import logging
import uuid
from datetime import UTC, datetime
from typing import AsyncGenerator, Optional

import redis.asyncio as redis
from t13_final_task.task.agent.models import Message, Role
from t13_final_task.task.agent.ums_agent import UMSAgent

logger = logging.getLogger(__name__)

_CONVERSATION_PREFIX = "conversation:"
_CONVERSATION_LIST_KEY = "conversations:list"


def _now() -> datetime:
    return datetime.now(UTC)


def _consistent(messages: list[Message]) -> list[Message]:
    """Drop a trailing assistant tool-call turn whose tool replies are incomplete."""
    keep, pending = 0, set()
    for index, message in enumerate(messages):
        if message.role == Role.ASSISTANT and message.tool_calls:
            pending = {call["id"] for call in message.tool_calls}
        elif message.role == Role.TOOL:
            pending.discard(message.tool_call_id)
        if not pending:
            keep = index + 1
    return messages[:keep]


class ConversationManager:
    """Manages conversation lifecycle including AI interactions and persistence"""

    def __init__(self, ums_agent: UMSAgent, redis_client: redis.Redis, system_prompt: str):
        self.ums_agent = ums_agent
        self.redis = redis_client
        self._system_prompt = system_prompt
        logger.info("ConversationManager initialized")

    async def create_conversation(self, title: str) -> dict:
        """Create a new conversation"""
        now = _now().isoformat()
        conversation = {
            "id": str(uuid.uuid4()),
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        await self._save_conversation(conversation)
        return conversation

    async def list_conversations(self) -> list[dict]:
        """List all conversations sorted by last update time"""
        summaries = []
        for conversation_id in await self.redis.zrevrange(_CONVERSATION_LIST_KEY, 0, -1):
            conversation = await self.get_conversation(conversation_id)
            if conversation is None:
                continue
            summaries.append(
                {
                    "id": conversation["id"],
                    "title": conversation["title"],
                    "created_at": conversation["created_at"],
                    "updated_at": conversation["updated_at"],
                    "message_count": len(conversation["messages"]),
                }
            )
        return summaries

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get a specific conversation"""
        raw = await self.redis.get(f"{_CONVERSATION_PREFIX}{conversation_id}")
        return json.loads(raw) if raw else None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        deleted = await self.redis.delete(f"{_CONVERSATION_PREFIX}{conversation_id}")
        if deleted == 0:
            return False
        await self.redis.zrem(_CONVERSATION_LIST_KEY, conversation_id)
        return True

    async def chat(self, user_message: Message, conversation_id: str, stream: bool = False):
        """
        Process chat messages and return AI response.
        Automatically saves conversation state.
        """
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        messages = [
            Message(**{**message, "role": Role(message["role"])})
            for message in conversation["messages"]
        ]
        if not messages:
            messages.append(Message(role=Role.SYSTEM, content=self._system_prompt))
        messages.append(user_message)

        if stream:
            return self._stream_chat(conversation_id, messages)
        return await self._non_stream_chat(conversation_id, messages)

    async def _stream_chat(
        self,
        conversation_id: str,
        messages: list[Message],
    ) -> AsyncGenerator[str, None]:
        """Handle streaming chat with automatic saving"""
        try:
            yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
            async for chunk in self.ums_agent.stream_response(messages):
                yield chunk
        finally:
            await self._save_conversation_messages(conversation_id, messages)

    async def _non_stream_chat(
        self,
        conversation_id: str,
        messages: list[Message],
    ) -> dict:
        """Handle non-streaming chat"""
        try:
            ai_message = await self.ums_agent.response(messages)
        finally:
            await self._save_conversation_messages(conversation_id, messages)
        return {"content": ai_message.content, "conversation_id": conversation_id}

    async def _save_conversation_messages(self, conversation_id: str, messages: list[Message]):
        """Save or update conversation messages"""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            logger.warning("Conversation deleted before save", extra={"id": conversation_id})
            return
        conversation["messages"] = [message.to_dict() for message in _consistent(messages)]
        conversation["updated_at"] = _now().isoformat()
        await self._save_conversation(conversation)

    async def _save_conversation(self, conversation: dict):
        """Internal method to persist conversation to Redis"""
        await self.redis.set(
            f"{_CONVERSATION_PREFIX}{conversation['id']}", json.dumps(conversation)
        )
        await self.redis.zadd(_CONVERSATION_LIST_KEY, {conversation["id"]: _now().timestamp()})
