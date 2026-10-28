import json
from copy import deepcopy

import pytest
from t12_skills.custom.mcp.mcp_tool_model import MCPToolModel
from t12_skills.custom.tools.py_interpreter.python_code_interpreter_tool import (
    PythonCodeInterpreterTool,
)
from t12_skills.custom.tools.skills.read_skill_tool import ReadSkillTool


@pytest.fixture
def skill_root(tmp_path):
    root = tmp_path / "skills"
    directory = root / "sample"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text("skill instructions")
    (directory / "script.py").write_text("answer = 42")
    (directory / "binary").write_bytes(b"\xff\xfe")
    outside = tmp_path / "outside"
    outside.write_text("outside-content")
    (directory / "escape").symlink_to(outside)
    return root


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["sample/SKILL.md", "/sample/SKILL.md"])
async def test_read_accepts_skill_relative_paths_with_string_schema(skill_root, path):
    tool = ReadSkillTool(skill_root)
    assert tool.name == "read_skill"
    assert tool.parameters["required"] == ["path"]
    assert tool.parameters["properties"]["path"]["type"] == "string"
    message = await tool.execute("read-1", {"path": path})
    assert message.content == "skill instructions"
    assert message.tool_call_id == "read-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/../outside",
        "/etc/passwd",
        "sample/escape",
        "missing",
        "sample",
        "sample/binary",
        "",
        42,
        None,
    ],
)
async def test_read_rejects_escape_and_unreadable_inputs_without_leaking(skill_root, path):
    message = await ReadSkillTool(skill_root).execute("read-bad", {"path": path})
    assert message.content.startswith("ERROR")
    assert "outside-content" not in message.content
    assert str(skill_root.parent) not in message.content
    assert message.tool_call_id == "read-bad"


def execution_payload(**updates):
    return json.dumps(
        {
            "success": True,
            "output": ["42\n"],
            "result": "42",
            "error": None,
            "traceback": [],
            "files": [
                {
                    "uri": "kernel://session/answer.txt",
                    "mime_type": "text/plain",
                    "name": "answer.txt",
                    "size": 2,
                }
            ],
            "session_info": {
                "session_id": "returned-session",
                "instructions": "Reuse this session",
            },
            **updates,
        }
    )


class Interpreter:
    def __init__(self, response=None):
        self.calls = []
        self.response = response if response is not None else execution_payload()

    async def call_tool(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        return self.response


def interpreter_tool(root, client=None):
    model = MCPToolModel(
        name="execute_code",
        description="Run Python",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "session_id": {"type": "string", "default": ""},
            },
            "required": ["code"],
        },
    )
    return PythonCodeInterpreterTool(client or Interpreter(), [model], "execute_code", root), model


def test_missing_discovered_tool_lists_available_names(skill_root):
    with pytest.raises(ValueError, match="execute_code"):
        PythonCodeInterpreterTool(Interpreter(), [], "execute_code", skill_root)


def test_schema_extensions_do_not_mutate_discovery_or_each_other(skill_root):
    tool, model = interpreter_tool(skill_root)
    original = deepcopy(model.parameters)
    first = tool.parameters
    assert first["properties"]["script_path"]["type"] == "string"
    assert "script_path" not in first["required"]
    first["properties"]["code"]["type"] = "broken"
    assert tool.parameters["properties"]["code"]["type"] == "string"
    assert model.parameters == original


@pytest.mark.asyncio
async def test_script_is_prepended_once_and_session_and_full_result_preserved(skill_root):
    client = Interpreter()
    tool, _ = interpreter_tool(skill_root, client)
    first = await tool.execute(
        "first", {"script_path": "/sample/script.py", "code": "print(answer)"}
    )
    parsed = json.loads(first.content)
    assert parsed == json.loads(execution_payload())
    second = await tool.execute(
        "second", {"code": "print(answer + 1)", "session_id": parsed["session_info"]["session_id"]}
    )
    assert json.loads(second.content)["success"]
    assert client.calls == [
        ("execute_code", {"code": "answer = 42\n\nprint(answer)", "session_id": ""}),
        ("execute_code", {"code": "print(answer + 1)", "session_id": "returned-session"}),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["../outside", "sample/escape", "missing", "sample/binary"])
async def test_failed_script_read_never_submits_code(skill_root, path):
    client = Interpreter()
    tool, _ = interpreter_tool(skill_root, client)
    result = await tool.execute("bad-script", {"script_path": path, "code": "print(answer)"})
    assert result.content.startswith("ERROR")
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["not-json", "{}", '{"success": "maybe"}', "[]"])
async def test_invalid_execution_results_become_correlated_tool_errors(skill_root, payload):
    tool, _ = interpreter_tool(skill_root, Interpreter(payload))
    result = await tool.execute("bad-result", {"code": "42"})
    assert result.content.startswith("ERROR")
    assert result.tool_call_id == "bad-result"
