import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def validate_base_url(value):
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or host == "openai.com"
        or host.endswith(".openai.com")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "OPENAI_BASE_URL must be an HTTPS DIAL URL without credentials, query, or fragment"
        )
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    api_key: str


def load_settings(start=None):
    directory = Path(start or __file__).resolve()
    if directory.is_file():
        directory = directory.parent
    for parent in (directory, *directory.parents):
        if (parent / ".env").is_file():
            load_dotenv(parent / ".env", override=False)
            break
    missing = [
        key
        for key in ("OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY")
        if not os.getenv(key)
    ]
    if missing:
        raise ValueError(f"Missing provider settings: {', '.join(missing)}")
    return Settings(
        validate_base_url(os.environ["OPENAI_BASE_URL"]),
        os.environ["OPENAI_MODEL"],
        os.environ["OPENAI_API_KEY"],
    )
