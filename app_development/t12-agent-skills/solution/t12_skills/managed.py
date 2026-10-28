import argparse
import json
from pathlib import Path

from t12_skills.config import token_limit

ALLOWLIST = {
    "calculator": ("SKILL.md", "scripts/calculate.py"),
    "style-guide": ("SKILL.md", "EXAMPLES.md", "REFERENCE.md"),
}


def skill_files(directory: Path) -> list[tuple[str, bytes, str]]:
    directory = Path(directory)
    if directory.name not in ALLOWLIST or directory.is_symlink():
        raise ValueError("Select an allowlisted skill directory")
    root = directory.resolve()
    for candidate in directory.rglob("*"):
        if candidate.is_symlink() and not candidate.resolve().is_relative_to(root):
            raise ValueError("Skill upload contains an escaping symlink")
    files = []
    for relative in sorted(ALLOWLIST[directory.name]):
        path = directory / relative
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("Required skill upload file is missing or outside its root")
        mime = "text/x-python" if path.suffix == ".py" else "text/markdown"
        files.append((f"{directory.name}/{relative}", path.read_bytes(), mime))
    return files


def pages(page):
    for _ in range(1000):
        yield from page.data
        if not page.has_next_page():
            return
        page = page.get_next_page()
    raise RuntimeError("Skill discovery exceeded the page limit")


def cleanup_owned(api, owned, *, anthropic=False):
    errors = []
    for skill_id, versions in list(owned.items()):
        try:
            current = list(pages(api.versions.list(skill_id=skill_id)))
            identifiers = {
                str(
                    getattr(version, "id", None) if anthropic else getattr(version, "version", None)
                )
                for version in current
            }
            if not identifiers <= versions:
                for version in identifiers & versions:
                    api.versions.delete(version, skill_id=skill_id)
                errors.append(f"Preserved {skill_id}: versions not owned by this invocation")
                continue
            api.delete(skill_id=skill_id)
            del owned[skill_id]
        except Exception as error:
            errors.append(f"Owned skill cleanup failed ({type(error).__name__})")
    for error in errors:
        print(f"WARNING: {error}")
    return errors


def arguments(argv=None):
    parser = argparse.ArgumentParser(description="Managed skill example; paid API calls")
    parser.add_argument("--skill", choices=sorted(ALLOWLIST), default="calculator")
    parser.add_argument("--query")
    parser.add_argument("--max-tokens", type=lambda value: token_limit(int(value)), default=1024)
    return parser.parse_args(argv)


def interact(conversation, query=None, input_fn=input):
    responses = []
    while True:
        try:
            text = query if query is not None else input_fn("You: ")
        except EOFError:
            break
        if text.strip().lower() in {"exit", "quit"}:
            break
        if text.strip():
            response = conversation.ask(text.strip())
            responses.append(response)
            print(conversation.text(response))
            usage = getattr(response, "usage", None)
            if usage:
                print("Usage: " + json.dumps(usage.model_dump()))
        if query is not None:
            break
    return responses
