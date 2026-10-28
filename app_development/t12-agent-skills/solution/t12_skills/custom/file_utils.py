from pathlib import Path


def get_file_content(path: Path) -> str:
    try:
        if not path.is_file():
            raise ValueError("Skill path must identify an existing regular file")
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ValueError("Skill file is unreadable or is not UTF-8") from None


def resolve_skill_path(skills_dir: Path, path: str) -> Path:
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        raise ValueError("A nonempty string skill path is required")
    root = skills_dir.resolve()
    relative = Path(path.lstrip("/"))
    if ".." in relative.parts or relative.is_absolute():
        raise ValueError("Skill path traversal is not allowed")
    try:
        candidate = (root / relative).resolve()
    except (OSError, RuntimeError):
        raise ValueError("Cannot resolve skill path") from None
    if not candidate.is_relative_to(root):
        raise ValueError("Skill path escapes the configured root")
    if not candidate.is_file():
        raise ValueError("Skill path must identify an existing regular file")
    return candidate
