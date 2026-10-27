import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def _sensitive(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    return any(
        part in normalized
        for part in (
            "authorization",
            "apikey",
            "token",
            "password",
            "secret",
            "verifier",
        )
    ) or normalized in {
        "code",
        "state",
        "error",
        "errordescription",
        "cookie",
        "setcookie",
    }


def redact(value, secrets=()):
    known = {secret for secret in secrets if isinstance(secret, str) and secret}
    known.update(
        value for name, value in os.environ.items() if _sensitive(name) and value
    )

    def collect(item):
        if isinstance(item, dict):
            for name, content in item.items():
                if _sensitive(str(name)) and isinstance(content, str) and content:
                    known.add(content)
                    if content.lower().startswith("bearer "):
                        known.add(content[7:])
                collect(content)
        elif isinstance(item, (list, tuple)):
            for content in item:
                collect(content)

    collect(value)

    def scrub(item):
        if isinstance(item, dict):
            return {
                str(name): "<redacted>" if _sensitive(str(name)) else scrub(content)
                for name, content in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [scrub(content) for content in item]
        if not isinstance(item, str):
            return item
        if item.lstrip().startswith(("{", "[")):
            try:
                return json.dumps(redact(json.loads(item), secrets=known))
            except (ValueError, RecursionError):
                pass
        for secret in sorted(known, key=len, reverse=True):
            item = item.replace(secret, "<redacted>")
        item = re.sub(r"(?i)\bBearer\s+[^\s,;\"'<>]+", "Bearer <redacted>", item)
        item = re.sub(
            r"(?i)\b(authorization|x-api-key|api[-_]key|access_token|refresh_token|"
            r"password|code_verifier|client_secret|code|state|error_description|token_endpoint_error)"
            r"[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s&;,\"'<>]+)",
            r"\1=<redacted>",
            item,
        )
        return item

    return scrub(value)


def load_environment(start: Path | None = None) -> Path | None:
    location = (start if start is not None else Path(__file__)).resolve()
    if not location.is_dir():
        location = location.parent
    for ancestor in (location, *location.parents):
        candidate = ancestor / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate
    return None


def required(name: str) -> str:
    value = os.getenv(name, "")
    if not value.strip():
        raise ValueError(f"{name} is required")
    return value


def dial_base_url(value: str | None = None) -> str:
    value = required("OPENAI_BASE_URL") if value is None else value
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        valid = (
            parsed.scheme == "https"
            and bool(host)
            and host != "openai.com"
            and not host.endswith(".openai.com")
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and "?" not in value
            and "#" not in value
            and not any(character.isspace() for character in value)
            and "\\" not in value
            and parsed.port in (None, 443)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("OPENAI_BASE_URL must be a safe HTTPS DIAL endpoint")
    return value
