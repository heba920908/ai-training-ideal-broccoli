import argparse
import asyncio
import json
import math
import re
from contextlib import AsyncExitStack
from pathlib import Path

from openai import AsyncOpenAI
from t12_skills.config import dial_settings
from t12_skills.custom.agent import T12Agent
from t12_skills.custom.custom_app import (
    MCP_TOOL_NAME,
    MCP_URL,
    SKILLS_DIR,
    build_system_prompt,
    run_chat,
)
from t12_skills.custom.mcp.mcp_client import T12MCPClient
from t12_skills.custom.models import load_skills
from t12_skills.custom.tools.py_interpreter.python_code_interpreter_tool import (
    PythonCodeInterpreterTool,
)
from t12_skills.custom.tools.skills.read_skill_tool import ReadSkillTool

SAMPLES = [
    ("Convert 98.6 degrees Fahrenheit to Celsius and Kelvin", [37, 310.15]),
    ("How many MB is 1.5 TB?", [1572864]),
    ("I'm driving 127 km/h, what's that in mph and knots?", [78.91414141414141, 68.57457354157507]),
    ("Convert 577 acres to hectares and square meters", [233.503822, 2335038.22]),
    ("My recipe needs 3 cups of milk - how many ml is that?", [709.764]),
]


def validate_history(history, expected):
    read = False
    execution_ids = set()
    outputs, sessions, executed = [], [], False
    for message in history:
        for call in message.get("tool_calls") or []:
            name = call["function"]["name"]
            arguments = json.loads(call["function"]["arguments"])
            if name == "read_skill" and arguments.get("path", "").endswith("SKILL.md"):
                read = True
            if name == "execute_code":
                assert read, "execution must follow a skill read"
                execution_ids.add(call["id"])
                executed = True
        if message.get("role") == "tool" and message.get("tool_call_id") in execution_ids:
            result = json.loads(message["content"])
            assert result["success"], "interpreter execution failed"
            outputs.extend(result.get("output") or [])
            if result.get("result") is not None:
                outputs.append(str(result["result"]))
            session = (result.get("session_info") or {}).get("session_id")
            if session:
                sessions.append(session)
    assert executed, "no real interpreter execution in trace"
    numbers = [
        float(value)
        for value in re.findall(
            r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", "\n".join(outputs).replace(",", "")
        )
    ]
    for value in expected:
        assert any(math.isclose(value, actual, rel_tol=1e-5, abs_tol=1e-6) for actual in numbers), (
            f"numeric result missing: {value}"
        )
    return {"read_before_execute": read, "numeric_pass": True, "session_ids": sessions}


async def interpreter_probe(url):
    client = await T12MCPClient.create(url)
    try:
        tools = await client.get_tools()
        first = json.loads(
            await client.call_tool(
                "execute_code", {"code": "probe_marker = 42\nprint(probe_marker)", "session_id": ""}
            )
        )
        assert first["success"]
        session_id = first["session_info"]["session_id"]
        second = json.loads(
            await client.call_tool(
                "execute_code", {"code": "print(probe_marker * 2)", "session_id": session_id}
            )
        )
        assert second["success"] and "84" in "".join(second["output"])
        if any(tool.name == "clear_session" for tool in tools):
            await client.call_tool("clear_session", {"session_id": session_id})
        return {
            "tools": [tool.name for tool in tools],
            "session_id": session_id,
            "first": first,
            "second": second,
            "state_reused": True,
        }
    finally:
        await client.close()


async def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Custom DIAL live acceptance only; no managed calls"
    )
    parser.add_argument("--mcp-url", default=MCP_URL)
    parser.add_argument("--output", type=Path, default=Path("output/t12-custom"))
    parser.add_argument("--sample", type=int, choices=range(len(SAMPLES)), action="append")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"managed": "deferred by user", "samples": [], "exit_status": 1}
    try:
        report["interpreter"] = await interpreter_probe(args.mcp_url)
        settings = dial_settings()
        report["model"] = settings.model
        skills = load_skills(SKILLS_DIR)
        prompt = build_system_prompt(skills)
        body = (SKILLS_DIR / "unit-converter/SKILL.md").read_text()
        script = (SKILLS_DIR / "unit-converter/scripts/convert.py").read_text()
        assert body not in prompt and script not in prompt
        report["metadata_only_startup"] = True
        async with AsyncExitStack() as stack:
            client = await stack.enter_async_context(AsyncOpenAI(**settings.client_kwargs()))
            interpreter = await PythonCodeInterpreterTool.create(
                args.mcp_url, MCP_TOOL_NAME, SKILLS_DIR
            )
            stack.push_async_callback(interpreter.close)
            for index in args.sample if args.sample is not None else range(len(SAMPLES)):
                query, expected = SAMPLES[index]
                agent = T12Agent(client, settings.model, [ReadSkillTool(SKILLS_DIR), interpreter])
                history = [message.to_dict() for message in await run_chat(agent, skills, query)]
                capture = {
                    "sample": index,
                    "query": query,
                    "history": history,
                    "usage": agent.usage,
                }
                (args.output / f"sample-{index}.json").write_text(
                    json.dumps(capture, indent=2) + "\n"
                )
                report["samples"].append({"sample": index, **validate_history(history, expected)})
                print(f"Sample {index}: numeric and read-before-execute checks passed")
        report["exit_status"] = 0
    except Exception as error:
        report["error_type"] = type(error).__name__
        print(f"Probe failed ({type(error).__name__}); no provider error body captured")
        raise
    finally:
        (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (Exception, KeyboardInterrupt):
        raise SystemExit(1) from None
