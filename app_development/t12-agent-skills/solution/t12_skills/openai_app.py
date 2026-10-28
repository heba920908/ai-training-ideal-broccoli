import io
import zipfile
from pathlib import Path

from openai import OpenAI
from t12_skills.config import MAX_ROUNDS, dial_settings, token_limit
from t12_skills.managed import arguments, cleanup_owned, interact, pages, skill_files


def zip_skill(skill_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content, _mime in skill_files(skill_dir):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, content)
    buf.seek(0)
    return buf.read()


def get_or_create_skill(skill_name: str, skill_dir: Path, client: OpenAI, *, owned: dict):
    if not hasattr(client, "skills"):
        raise RuntimeError("DIAL Skills capability is unavailable in this SDK; no public fallback")
    try:
        for skill in pages(client.skills.list()):
            if skill.name == skill_name:
                return skill.id
        skill = client.skills.create(
            files=[(f"{skill_name}.zip", zip_skill(skill_dir), "application/zip")]
        )
    except Exception as error:
        raise RuntimeError(
            f"DIAL Skills capability/request failed ({type(error).__name__}); no public fallback"
        ) from None
    owned[skill.id] = {str(skill.default_version)}
    return skill.id


class Conversation:
    def __init__(self, client, skill_id, model, max_tokens=1024):
        self.client, self.skill_id, self.model = client, skill_id, model
        self.max_tokens = token_limit(max_tokens)
        self.previous_response_id, self.container_id, self.usage = None, None, []

    def ask(self, query):
        if not hasattr(self.client, "responses"):
            raise RuntimeError(
                "DIAL Responses/hosted-shell capability unavailable; no public fallback"
            )
        environment = {
            "type": "container_auto",
            "skills": [{"type": "skill_reference", "skill_id": self.skill_id}],
            "network_policy": {"type": "disabled"},
        }
        if self.container_id:
            environment = {"type": "container_reference", "container_id": self.container_id}
        request = {
            "model": self.model,
            "input": [{"role": "user", "content": query}],
            "tools": [{"type": "shell", "environment": environment}],
            "max_output_tokens": self.max_tokens,
        }
        if self.previous_response_id:
            request["previous_response_id"] = self.previous_response_id
        response = None
        for _ in range(MAX_ROUNDS):
            try:
                if response is None:
                    response = self.client.responses.create(**request)
                else:
                    response = self.client.responses.retrieve(response.id)
            except Exception as error:
                raise RuntimeError(
                    f"DIAL Responses/hosted-shell capability/request failed ({type(error).__name__}); no public fallback"
                ) from None
            self.previous_response_id = response.id
            if response.usage:
                self.usage.append(response.usage.model_dump())
            for item in response.output:
                container_id = getattr(getattr(item, "environment", None), "container_id", None)
                if container_id:
                    self.container_id = container_id
            if response.status == "completed":
                return response
            if response.status not in {"in_progress", "queued"}:
                raise RuntimeError("DIAL Responses returned a failed or incomplete result")
        raise RuntimeError(f"DIAL Responses continuation stopped after {MAX_ROUNDS} requests")

    @staticmethod
    def text(response):
        return response.output_text


def chat(
    client,
    skill_id,
    log_request=False,
    log_response=False,
    *,
    model=None,
    query=None,
    max_tokens=1024,
    input_fn=input,
):
    return interact(
        Conversation(client, skill_id, model or dial_settings().model, max_tokens), query, input_fn
    )


def delete_skills(client: OpenAI, owned: dict):
    if not owned:
        return []
    return cleanup_owned(client.skills, owned)


STYLE_SKILL_NAME = "style-guide"
STYLE_SKILL_DIR = Path(__file__).parent / "_skills" / STYLE_SKILL_NAME

CALCULATOR_SKILL_NAME = "calculator"
CALCULATOR_SKILL_DIR = Path(__file__).parent / "_skills" / CALCULATOR_SKILL_NAME


def main(argv=None):
    args = arguments(argv)
    settings = dial_settings()
    owned = {}
    with OpenAI(**settings.client_kwargs()) as client:
        try:
            skill_id = get_or_create_skill(
                args.skill, Path(__file__).parent / "_skills" / args.skill, client, owned=owned
            )
            return chat(
                client, skill_id, model=settings.model, query=args.query, max_tokens=args.max_tokens
            )
        finally:
            delete_skills(client, owned)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(
            f"ERROR: DIAL managed run stopped ({type(error).__name__}); Skills/Responses hosted shell may be unsupported. No public fallback."
        )
        raise SystemExit(1) from None
