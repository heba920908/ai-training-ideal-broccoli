from pathlib import Path

import anthropic
from t12_skills.config import MAX_ROUNDS, anthropic_settings, token_limit
from t12_skills.managed import arguments, cleanup_owned, interact, pages, skill_files

SKILLS_VERSION = "skills-2025-10-02"


def get_or_create_skill(
    skill_title: str, skill_dir: Path, client: anthropic.Anthropic, *, owned: dict
) -> str:
    if not hasattr(client, "skills"):
        raise RuntimeError("Anthropic Skills capability is unavailable in this SDK")
    for skill in pages(client.skills.list(source="custom")):
        if skill.display_name == skill_title:
            return skill.id
    skill = client.skills.create(display_name=skill_title, files=skill_files(skill_dir))
    owned[skill.id] = {str(skill.latest_version_id)}
    return skill.id


def delete_skills(client: anthropic.Anthropic, owned: dict):
    if not owned:
        return []
    return cleanup_owned(client.skills, owned, anthropic=True)


class Conversation:
    def __init__(self, client, skill_id, model, max_tokens=1024):
        self.client, self.skill_id, self.model = client, skill_id, model
        self.max_tokens = token_limit(max_tokens)
        self.messages, self.container_id, self.usage = [], None, []

    def ask(self, query):
        if not hasattr(getattr(self.client, "beta", None), "messages"):
            raise RuntimeError("Anthropic Messages/code-execution capability unavailable")
        self.messages.append({"role": "user", "content": query})
        for _ in range(MAX_ROUNDS):
            container = {
                "skills": [{"type": "custom", "skill_id": self.skill_id, "version": "latest"}]
            }
            if self.container_id:
                container["id"] = self.container_id
            try:
                response = self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=list(self.messages),
                    container=container,
                    betas=["code-execution-2025-08-25", SKILLS_VERSION],
                    tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
                )
            except Exception as error:
                raise RuntimeError(
                    f"Anthropic managed capability/request failed ({type(error).__name__})"
                ) from None
            if response.container:
                self.container_id = response.container.id
            blocks = [
                block.model_dump(exclude_none=True) if hasattr(block, "model_dump") else block
                for block in response.content
            ]
            self.messages.append({"role": "assistant", "content": blocks})
            if response.usage:
                self.usage.append(response.usage.model_dump())
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason not in {"end_turn", "stop_sequence"}:
                raise RuntimeError("Anthropic response was refused or incomplete")
            return response
        raise RuntimeError(f"Anthropic continuation stopped after {MAX_ROUNDS} requests")

    @staticmethod
    def text(response):
        return "\n".join(
            block["text"] if isinstance(block, dict) else block.text
            for block in response.content
            if (block.get("type") if isinstance(block, dict) else block.type) == "text"
        )


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
        Conversation(client, skill_id, model or anthropic_settings().model, max_tokens),
        query,
        input_fn,
    )


STYLE_SKILL_TITLE = "style-guide"
STYLE_SKILL_DIR = Path(__file__).parent / "_skills" / STYLE_SKILL_TITLE

CALCULATOR_SKILL_TITLE = "calculator"
CALCULATOR_SKILL_DIR = Path(__file__).parent / "_skills" / CALCULATOR_SKILL_TITLE


def main(argv=None):
    args = arguments(argv)
    settings = anthropic_settings()
    owned = {}
    with anthropic.Anthropic(**settings.client_kwargs()) as client:
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
            f"ERROR: Anthropic managed run stopped ({type(error).__name__}); check configuration, capability, and budget."
        )
        raise SystemExit(1) from None
