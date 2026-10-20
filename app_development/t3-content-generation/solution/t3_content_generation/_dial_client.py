"""EPAM DIAL adapter for the T3 content-generation tasks.

DIAL only routes ``/chat/completions`` for multimodal deployments (``/images/*`` and ``/audio/*`` return
``403 Forbidden route``). Binary inputs travel as ``custom_content.attachments`` (inline base64 ``data``) and binary
outputs come back as attachment ``url``s that are downloaded from the DIAL files API (``GET {host}/v1/{url}``).
"""

import base64
import json
import mimetypes
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests

from commons.constants import OPENAI_API_KEY, OPENAI_HOST, OPENAI_MODEL

MAX_ATTEMPTS = 3

PACKAGE_DIR = Path(__file__).resolve().parent
# Course assets (logo.png, *.mp3) live in the fork; the committed solution only keeps code.
FORK_ASSETS_DIR = (
    PACKAGE_DIR.parents[3] / "workspace" / "ai-applications-development-from-api-to-agents" / "t3_content_generation"
    if len(PACKAGE_DIR.parents) > 3 else PACKAGE_DIR
)


def asset(relative: str) -> Path:
    for base in (PACKAGE_DIR, FORK_ASSETS_DIR):
        candidate = base / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Asset '{relative}' not found in {PACKAGE_DIR} or {FORK_ASSETS_DIR}")


def dial_root(base_url: str = OPENAI_HOST) -> str:
    """``https://host/openai/deployments/<model>`` -> ``https://host/openai``."""
    return re.sub(r"/deployments/[^/]+.*$", "", base_url.rstrip("/"))


def redact(text: str) -> str:
    """Hide the API key, per-key DIAL bucket ids and long base64 payloads from logs."""
    if OPENAI_API_KEY:
        text = text.replace(OPENAI_API_KEY, "<redacted>")
    text = re.sub(r"files/[A-Za-z0-9]{20,}/", "files/<bucket>/", text)
    text = re.sub(r'"thought_signature":\s*"[^"]+"', '"thought_signature": "<omitted>"', text)
    return re.sub(r"[A-Za-z0-9+/=_-]{300,}", lambda m: f"<{len(m.group(0))} b64 chars>", text)


class Logger:
    """Prints to stdout and mirrors everything into a log file."""

    def __init__(self, log_file: Path | None = None):
        self._file = log_file.open("w", encoding="utf-8") if log_file else None

    def __call__(self, *parts: Any) -> None:
        line = redact(" ".join(str(p) for p in parts))
        print(line)
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()


class DialError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


@dataclass
class Attempt:
    model: str
    ok: bool
    reason: str


@dataclass
class Resolution:
    model: str | None
    result: Any
    attempts: list[Attempt] = field(default_factory=list)


class DialClient:

    def __init__(self, log: Logger | None = None, session: Any = None, base_url: str = OPENAI_HOST):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY cannot be null or empty")
        self._root = dial_root(base_url)
        self._host = self._root.removesuffix("/openai")
        self._headers = {"Api-Key": OPENAI_API_KEY}
        self._http = session or requests.Session()
        self._models: dict[str, dict] | None = None
        self.log = log or Logger()

    def endpoint(self, model: str) -> str:
        return f"{self._root}/deployments/{model}/chat/completions"

    def models(self) -> dict[str, dict]:
        if self._models is None:
            r = self._http.get(f"{self._root}/models", headers=self._headers, timeout=60)
            self._models = {m["id"]: m for m in r.json().get("data", [])} if r.status_code == 200 else {}
        return self._models

    def accepts(self, model: str, mime: str) -> bool:
        info = self.models().get(model)
        if info is None:
            return False
        types = info.get("input_attachment_types") or []
        family = mime.split("/")[0]
        return any(t in (mime, f"{family}/*", "*/*") for t in types)

    def chat(self, model: str, messages: list[dict], print_request: bool = True, **extra: Any) -> dict:
        payload = {"messages": messages, **extra}
        self.log(f"🔗 POST {self.endpoint(model)}")
        if print_request:
            self.log("📤 Request:", json.dumps(payload, indent=2))
        r = self._http.post(self.endpoint(model), headers=self._headers, json=payload, timeout=300)
        if r.status_code != 200:
            raise DialError(r.status_code, r.text[:500])
        data = r.json()
        self.log("📥 Response:", json.dumps(data, indent=2))
        return data

    def download(self, url: str) -> bytes:
        r = self._http.get(f"{self._host}/v1/{url}", headers=self._headers, timeout=300)
        if r.status_code != 200:
            raise DialError(r.status_code, r.text[:500])
        return r.content

    @staticmethod
    def attachment(path: Path, mime: str | None = None) -> dict:
        mime = mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return {"type": mime, "title": path.name, "data": base64.b64encode(path.read_bytes()).decode("utf-8")}

    @staticmethod
    def content(response: dict) -> str:
        return response["choices"][0]["message"].get("content") or ""

    @staticmethod
    def attachments(response: dict, mime_prefix: str = "") -> list[dict]:
        message = response["choices"][0]["message"]
        found = (message.get("custom_content") or {}).get("attachments") or []
        return [a for a in found if a.get("type", "").startswith(mime_prefix)]

    def resolve(
            self,
            task: str,
            candidates: list[str],
            run: Callable[[str], Any],
            input_mime: str | None = None,
    ) -> Resolution:
        """Try up to MAX_ATTEMPTS distinct candidates; ``run`` raises to reject a model as unsuitable."""
        resolution = Resolution(model=None, result=None)
        for model in list(dict.fromkeys(m for m in candidates if m))[:MAX_ATTEMPTS]:
            self.log(f"\n🧪 [{task}] attempt {len(resolution.attempts) + 1}/{MAX_ATTEMPTS}: {model}")
            if model not in self.models():
                reason = "not deployed on DIAL"
            elif input_mime and not self.accepts(model, input_mime):
                reason = f"does not accept '{input_mime}' attachments ({self.models()[model].get('input_attachment_types')})"
            else:
                try:
                    resolution.result = run(model)
                    resolution.model = model
                    resolution.attempts.append(Attempt(model, True, "ok"))
                    self.log(f"✅ [{task}] {model} is suitable")
                    return resolution
                except Exception as e:  # noqa: BLE001 - any failure means "try the next candidate"
                    reason = str(e)
            resolution.attempts.append(Attempt(model, False, reason))
            self.log(f"❌ [{task}] {model} rejected: {reason}")
        self.log(f"⛔ [{task}] no suitable model after {len(resolution.attempts)} attempts")
        return resolution


def default_candidates(*fallbacks: str) -> list[str]:
    """``OPENAI_MODEL`` from ``.env`` is always tried first, then the DIAL deployments found suitable for the task."""
    return [OPENAI_MODEL, *fallbacks]


def output_dir(path: str | None = None) -> Path:
    target = Path(path) if path else PACKAGE_DIR.parent.parent / "output"
    target.mkdir(parents=True, exist_ok=True)
    return target


def main_logger(name: str, out: Path) -> Logger:
    log = Logger(out / f"{name}.log")
    log(f"# {name} | DIAL root: {dial_root()} | OPENAI_MODEL: {OPENAI_MODEL or '<unset>'} | python {sys.version.split()[0]}")
    return log
