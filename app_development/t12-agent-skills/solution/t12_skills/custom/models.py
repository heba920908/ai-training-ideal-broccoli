import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SkillMetadata:
    name: str
    description: str
    skill_dir: Path
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Optional[dict[str, str]] = None
    allowed_tools: Optional[list[str]] = None


_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def _validate(
    name: str, description: str, compatibility: Optional[str], dir_name: str
) -> list[str]:
    errors: list[str] = []

    if not name:
        errors.append("name is empty")
    elif len(name) > 64:
        errors.append(f"name exceeds 64 chars ({len(name)})")
    elif not _NAME_RE.match(name):
        errors.append("name contains invalid characters or starts/ends with a hyphen")
    elif "--" in name:
        errors.append("name contains consecutive hyphens")

    if name != dir_name:
        errors.append(f"name '{name}' does not match directory name '{dir_name}'")

    if not description:
        errors.append("description is empty")
    elif len(description) > 1024:
        errors.append(f"description exceeds 1024 chars ({len(description)})")

    if compatibility is not None and len(compatibility) > 500:
        errors.append(f"compatibility exceeds 500 chars ({len(compatibility)})")

    return errors


def load_skills(skills_dir: Path) -> list[SkillMetadata]:
    """Load and validate all skills from the skills directory."""
    skills: list[SkillMetadata] = []

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            print(f"WARN: skipping '{skill_dir.name}' — no SKILL.md")
            continue

        if not skill_md.resolve().is_relative_to(skills_dir.resolve()):
            print(f"WARN: skipping '{skill_dir.name}': outside skill root")
            continue
        try:
            content = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            print(f"WARN: skipping '{skill_dir.name}': unreadable skill")
            continue
        if not content.startswith("---"):
            print(f"WARN: skipping '{skill_dir.name}' — missing YAML frontmatter")
            continue

        try:
            match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.DOTALL)
            fm = yaml.safe_load(match.group(1)) if match else None
            if not isinstance(fm, dict):
                raise ValueError("frontmatter must be a mapping")
            for key in ("name", "description"):
                if not isinstance(fm.get(key), str):
                    raise ValueError("name and description must be strings")
            for key in ("license", "compatibility"):
                if key in fm and not isinstance(fm[key], str):
                    raise ValueError("optional text fields must be strings")
            metadata = fm.get("metadata")
            if metadata is not None and (
                not isinstance(metadata, dict)
                or not all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in metadata.items()
                )
            ):
                raise ValueError("metadata must map strings to strings")
            tools = fm.get("allowed-tools")
            if tools is not None and not (
                isinstance(tools, str)
                or isinstance(tools, list)
                and all(isinstance(tool, str) for tool in tools)
            ):
                raise ValueError("allowed-tools must contain strings")
        except (ValueError, yaml.YAMLError):
            print(f"WARN: skipping '{skill_dir.name}': invalid frontmatter")
            continue

        name = str(fm.get("name", ""))
        description = str(fm.get("description", "")).strip()
        compatibility = str(fm["compatibility"]).strip() if fm.get("compatibility") else None

        errors = _validate(name, description, compatibility, skill_dir.name)
        if errors:
            print(f"WARN: skipping '{skill_dir.name}' — {'; '.join(errors)}")
            continue

        raw_at = fm.get("allowed-tools")
        if isinstance(raw_at, str):
            allowed_tools = raw_at.split() or None
        elif isinstance(raw_at, list):
            allowed_tools = raw_at or None
        else:
            allowed_tools = None

        skills.append(
            SkillMetadata(
                name=name,
                description=description,
                skill_dir=skill_dir,
                license=fm.get("license"),
                compatibility=compatibility,
                metadata=fm.get("metadata"),
                allowed_tools=allowed_tools,
            )
        )

    return skills
