import re
from pathlib import Path

from t13_final_task.task.agent.models import load_skills

SKILLS_DIR = Path(__file__).parent / "task" / "_skills"
SKILL_FILE = SKILLS_DIR / "ums-user-management" / "SKILL.md"
DISCOVERED_TOOLS = {
    "get_user_by_id",
    "search_user",
    "add_user",
    "update_user",
    "delete_user",
    "search",
    "fetch_content",
}


def body() -> str:
    text = SKILL_FILE.read_text(encoding="utf-8")
    return text[text.index("---", 3) + 3 :]


def test_skill_loads_with_valid_metadata():
    skills = load_skills(SKILLS_DIR)
    assert [skill.name for skill in skills] == ["ums-user-management"]
    skill = skills[0]
    description = skill.description.lower()
    for term in ("create", "update", "delete", "search", "duckduckgo"):
        assert term in description
    assert skill.license
    assert skill.metadata and skill.metadata.get("author") and skill.metadata.get("version")


def test_no_todo_placeholders_remain():
    text = SKILL_FILE.read_text(encoding="utf-8")
    assert "TODO" not in text
    assert "<!--" not in text


def test_documented_tools_exist_and_all_are_documented():
    documented = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", body(), flags=re.MULTILINE))
    assert documented == DISCOVERED_TOOLS


def test_sections_and_confirmation_rules_present():
    text = body()
    for heading in (
        "## MCP Server Connections",
        "## Operating Rules",
        "### Finding a User",
        "### Adding a User",
        "### Updating a User",
        "### Deleting a User",
        "## Boundaries",
    ):
        assert heading in text
    lowered = " ".join(text.lower().split())
    assert "confirmation before calling `add_user`" in lowered
    assert "permanent and cannot be undone" in lowered
    assert "stdio" in lowered and "podman" in lowered
