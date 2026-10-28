from pathlib import Path
from typing import Any

from t12_skills.custom.file_utils import get_file_content, resolve_skill_path
from t12_skills.custom.tools.base import BaseTool


class ReadSkillTool(BaseTool):
    """Reads files from the local skills directory by path."""

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir.resolve()

    @property
    def name(self) -> str:
        return "read_skill"

    @property
    def description(self) -> str:
        return "Read SKILL.md or supporting files on demand. Use a skill-relative path such as /unit-converter/SKILL.md."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Skill-relative file path, optionally starting with /.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        }

    async def _execute(self, arguments: dict[str, Any]) -> str:
        return get_file_content(resolve_skill_path(self._skills_dir, arguments.get("path")))
