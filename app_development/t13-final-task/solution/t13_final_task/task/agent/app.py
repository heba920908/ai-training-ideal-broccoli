import logging
import re
import sys
import xml.etree.ElementTree as ET
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from starlette.middleware.cors import CORSMiddleware
from t13_final_task.task.agent.clients.http_mcp_client import HttpMcpClient
from t13_final_task.task.agent.clients.stdio_mcp_client import StdioMcpClient
from t13_final_task.task.agent.config import (
    ALLOWED_ORIGINS,
    APP_HOST,
    APP_PORT,
    DDG_MCP_IMAGE,
    REDIS_URL,
    UMS_MCP_URL,
    dial_settings,
)
from t13_final_task.task.agent.conversation_manager import ConversationManager
from t13_final_task.task.agent.models import Message, Role, SkillMetadata, load_skills
from t13_final_task.task.agent.tools.base import BaseTool
from t13_final_task.task.agent.tools.mcp_tool import McpTool
from t13_final_task.task.agent.tools.read_skill_tool import ReadSkillTool
from t13_final_task.task.agent.ums_agent import UMSAgent

SKILLS_DIR = Path(__file__).parent.parent / "_skills"
INDEX_HTML = Path(__file__).parent.parent / "index.html"
_XML_TAG = re.compile(r"^[A-Za-z_][\w.-]*$")


def _build_available_skills_xml(skills: list[SkillMetadata]) -> str:
    root = ET.Element("available_skills")
    for skill in skills:
        element = ET.SubElement(root, "skill", name=skill.name)
        ET.SubElement(element, "description").text = skill.description
        if skill.license:
            ET.SubElement(element, "license").text = str(skill.license)
        if skill.compatibility:
            ET.SubElement(element, "compatibility").text = skill.compatibility
        if skill.metadata:
            metadata = ET.SubElement(element, "metadata")
            for key, value in skill.metadata.items():
                if _XML_TAG.match(str(key)):
                    ET.SubElement(metadata, str(key)).text = str(value)
        if skill.allowed_tools:
            ET.SubElement(element, "allowed-tools").text = " ".join(skill.allowed_tools)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode")


def build_system_prompt(skills: list[SkillMetadata]) -> str:
    return f"""You are an AI assistant with access to agent skills that extend your capabilities.

{_build_available_skills_xml(skills)}

How to use skills:
1. When a request matches a skill description, first call the `read_skill` tool with
   path="/<skill-name>/SKILL.md" to load that skill's full instructions.
2. Follow the loaded SKILL.md precisely, including its tools, workflows, confirmation
   rules, and boundaries.
Only metadata is shown above; never assume skill instructions you have not read."""


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

conversation_manager: Optional[ConversationManager] = None


def _create_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP clients, Redis, and ConversationManager on startup"""
    global conversation_manager

    settings = dial_settings()
    skills = load_skills(SKILLS_DIR)
    system_prompt = build_system_prompt(skills)
    tools: list[BaseTool] = [ReadSkillTool(skills_dir=SKILLS_DIR)]

    async with AsyncExitStack() as stack:
        ums_client = await HttpMcpClient.create(UMS_MCP_URL)
        stack.push_async_callback(ums_client.close)
        tools.extend(McpTool(ums_client, model) for model in await ums_client.get_tools())

        ddg_client = await StdioMcpClient.create(DDG_MCP_IMAGE)
        stack.push_async_callback(ddg_client.close)
        tools.extend(McpTool(ddg_client, model) for model in await ddg_client.get_tools())

        redis_client = _create_redis()
        stack.push_async_callback(redis_client.aclose)
        await redis_client.ping()

        ums_agent = UMSAgent(
            api_key=settings.api_key,
            model=settings.model,
            tools=tools,
            base_url=settings.base_url,
        )
        conversation_manager = ConversationManager(ums_agent, redis_client, system_prompt)
        logger.info("Application started", extra={"tools": [tool.name for tool in tools]})
        try:
            yield
        finally:
            conversation_manager = None


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


# Request/Response Models
class ChatRequest(BaseModel):
    message: Message
    stream: bool = True

    @field_validator("message")
    @classmethod
    def user_message_only(cls, message: Message) -> Message:
        if message.role != Role.USER or not message.content.strip():
            raise ValueError("message must be a non-empty user message")
        return Message(role=Role.USER, content=message.content)


class ChatResponse(BaseModel):
    content: str
    conversation_id: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


def _manager() -> ConversationManager:
    if conversation_manager is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return conversation_manager


# Endpoints
@app.get("/")
async def index():
    return FileResponse(INDEX_HTML, media_type="text/html")


@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "conversation_manager_initialized": conversation_manager is not None,
    }


@app.post("/conversations")
async def create_conversation(request: CreateConversationRequest):
    title = (request.title or "").strip() or "New conversation"
    return await _manager().create_conversation(title)


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations():
    return await _manager().list_conversations()


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conversation = await _manager().get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if not await _manager().delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": f"Conversation {conversation_id} deleted"}


@app.post("/conversations/{conversation_id}/chat")
async def chat(conversation_id: str, request: ChatRequest):
    try:
        result = await _manager().chat(request.message, conversation_id, request.stream)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if request.stream:
        return StreamingResponse(
            result, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )
    return ChatResponse(**result)


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting uvicorn server")
    uvicorn.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        log_level="info",
    )
