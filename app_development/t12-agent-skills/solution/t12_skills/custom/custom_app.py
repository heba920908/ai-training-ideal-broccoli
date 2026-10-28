import argparse
import asyncio
import os
import xml.etree.ElementTree as ET
from contextlib import AsyncExitStack
from pathlib import Path

from commons.models.message import Message
from commons.models.role import Role
from openai import AsyncOpenAI
from t12_skills.config import dial_settings
from t12_skills.custom.agent import T12Agent
from t12_skills.custom.models import SkillMetadata, load_skills
from t12_skills.custom.tools.py_interpreter.python_code_interpreter_tool import (
    PythonCodeInterpreterTool,
)
from t12_skills.custom.tools.skills.read_skill_tool import ReadSkillTool

SKILLS_DIR = Path(__file__).parent / "_skills"
MCP_URL = "http://localhost:8050/mcp"
MCP_TOOL_NAME = "execute_code"


def _build_available_skills_xml(skills: list[SkillMetadata]) -> str:
    root = ET.Element("available_skills")
    for skill in skills:
        el = ET.SubElement(root, "skill", attrib={"name": skill.name})
        ET.SubElement(el, "description").text = skill.description
        if skill.license:
            ET.SubElement(el, "license").text = skill.license
        if skill.compatibility:
            ET.SubElement(el, "compatibility").text = skill.compatibility
        if skill.metadata:
            meta = ET.SubElement(el, "metadata")
            for k, v in skill.metadata.items():
                ET.SubElement(meta, "entry", attrib={"key": k}).text = str(v)
        if skill.allowed_tools:
            ET.SubElement(el, "allowed-tools").text = " ".join(skill.allowed_tools)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


def build_system_prompt(skills: list[SkillMetadata]) -> str:
    return f"""\
You are an AI assistant with access to agent skills.

{_build_available_skills_xml(skills)}

## How to use skills

When the user's request matches a skill, activate it:
1. Call `read_skill` with the skill's SKILL.md path (e.g. path="/<skill-name>/SKILL.md") to load
   its full instructions.
2. Follow the instructions in the loaded SKILL.md precisely.
3. If the instructions reference additional files (scripts, references, assets), read them on demand
   using `read_skill` (e.g. path="/<skill-name>/scripts/calculate.py").
4. If the skill requires running a Python script, use `{MCP_TOOL_NAME}` with script_path
    and code. Script source is prepended locally; do not read it just to execute it.
5. Reuse the returned session_info.session_id. Do not silently restart or replay failed code.

Always read the relevant SKILL.md before performing the task.\
"""


async def run_chat(agent, skills, query=None, input_fn=input, trace=False):
    messages = [Message(Role.SYSTEM, build_system_prompt(skills))]
    while True:
        if query is None:
            try:
                user_input = await asyncio.to_thread(input_fn, "You: ")
            except EOFError:
                break
        else:
            user_input = query
        user_input = user_input.strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            if query is not None:
                break
            continue
        messages.append(Message(Role.USER, user_input))
        reply = await agent.chat_completion(messages, log_messages=trace)
        messages.append(reply)
        print(f"Assistant: {reply.content}")
        if query is not None:
            break
    return messages


async def main(argv=None):
    parser = argparse.ArgumentParser(description="DIAL skill agent with a local MCP interpreter")
    parser.add_argument("--query")
    parser.add_argument("--mcp-url", default=os.getenv("T12_MCP_URL", MCP_URL))
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args(argv)
    settings = dial_settings()
    skills = load_skills(SKILLS_DIR)
    if not skills:
        raise ValueError("No valid skills found")
    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(AsyncOpenAI(**settings.client_kwargs()))
        interpreter = await PythonCodeInterpreterTool.create(
            args.mcp_url, MCP_TOOL_NAME, SKILLS_DIR
        )
        stack.push_async_callback(interpreter.close)
        tools = [ReadSkillTool(SKILLS_DIR), interpreter]
        agent = T12Agent(client, settings.model, tools)
        return await run_chat(agent, skills, args.query, trace=args.trace)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (Exception, KeyboardInterrupt) as error:
        print(
            f"ERROR: Custom agent stopped ({type(error).__name__}); check provider configuration and MCP availability."
        )
        raise SystemExit(1) from None
