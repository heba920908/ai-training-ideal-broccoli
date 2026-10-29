"""Live acceptance probe for the T13 agent. Needs the Compose stack and the app running."""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import httpx

APP = "http://127.0.0.1:8011"
UMS = "http://127.0.0.1:8041"
CONFIRM = "Yes, I explicitly confirm. Please proceed."


class Probe:
    def __init__(self, out_dir: Path):
        self.http = httpx.Client(timeout=300)
        self.out_dir = out_dir
        self.run = uuid.uuid4().hex[:8]
        self.results: dict[str, dict] = {}
        self.owned_ids: set[int] = set()

    def turn(self, conversation_id: str, text: str) -> dict:
        tools, content, errors = [], "", []
        with self.http.stream(
            "POST",
            f"{APP}/conversations/{conversation_id}/chat",
            json={"message": {"role": "user", "content": text}, "stream": True},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                event = json.loads(line[6:])
                if "tool_activity" in event:
                    tools.append(event["tool_activity"])
                elif "error" in event:
                    errors.append(event["error"])
                elif event.get("choices"):
                    content += event["choices"][0]["delta"].get("content") or ""
        return {"tools": tools, "content": content, "errors": errors}

    def conversation(self, title: str) -> str:
        return self.http.post(f"{APP}/conversations", json={"title": title}).json()["id"]

    @staticmethod
    def called(turn: dict, name: str) -> bool:
        return any(t["type"] == "call" and t["name"] == name for t in turn["tools"])

    def record(self, name: str, passed: bool, **details):
        self.results[name] = {"passed": passed, **details}
        print(f"{'PASS' if passed else 'FAIL'} {name}", file=sys.stderr)

    def summary(self, turns: list[dict]) -> list[dict]:
        return [
            {
                "calls": [t["name"] for t in turn["tools"] if t["type"] == "call"],
                "answer_excerpt": turn["content"][:400],
                "errors": turn["errors"],
            }
            for turn in turns
        ]

    def create_fixture(self, label: str, **extra) -> int:
        body = {
            "name": f"T13{label}",
            "surname": f"Fixture{self.run}",
            "email": f"t13.{label.lower()}.{self.run}@example.com",
            "about_me": "Synthetic T13 acceptance fixture.",
            **extra,
        }
        response = self.http.post(f"{UMS}/v1/users", json=body)
        response.raise_for_status()
        user_id = int(response.json()["id"])
        self.owned_ids.add(user_id)
        return user_id

    def user(self, user_id: int) -> dict | None:
        response = self.http.get(f"{UMS}/v1/users/{user_id}")
        return response.json() if response.status_code == 200 else None

    def search_ids(self, **params) -> set[int]:
        response = self.http.get(f"{UMS}/v1/users/search", params=params)
        return {int(user["id"]) for user in response.json()} if response.is_success else set()

    def sample_search(self):
        cid = self.conversation("Smith search")
        turn = self.turn(cid, 'Find all users with the surname "Smith"')
        passed = self.called(turn, "read_skill") and self.called(turn, "search_user")
        self.record("search_smith", passed, turns=self.summary([turn]))

    def sample_web(self):
        cid = self.conversation("OpenAI news")
        turn = self.turn(cid, "Search the web for the latest news about OpenAI and summarize it")
        passed = self.called(turn, "search") and bool(turn["content"].strip())
        self.record("web_news", passed, turns=self.summary([turn]))

    def sample_update(self):
        user_id = self.create_fixture("Update")
        new_email = f"t13.updated.{self.run}@example.com"
        cid = self.conversation("Update email")
        turns = [self.turn(cid, f"Update the email for user with ID {user_id} to {new_email}")]
        if not any(self.called(t, "update_user") for t in turns):
            turns.append(self.turn(cid, CONFIRM))
        stored = self.user(user_id) or {}
        passed = (
            any(self.called(t, "update_user") for t in turns) and stored.get("email") == new_email
        )
        self.record("update_email", passed, user_id=user_id, turns=self.summary(turns))

    def sample_delete(self):
        user_id = self.create_fixture("Delete")
        cid = self.conversation("Delete user")
        first = self.turn(cid, f"Delete user with ID {user_id} — make sure to confirm first")
        asked_first = not self.called(first, "delete_user")
        second = self.turn(cid, CONFIRM)
        deleted = self.called(second, "delete_user") and self.user(user_id) is None
        if deleted:
            self.owned_ids.discard(user_id)
        self.record(
            "delete_with_confirmation",
            asked_first and deleted,
            user_id=user_id,
            asked_before_delete=asked_first,
            turns=self.summary([first, second]),
        )

    def sample_add(self):
        before = self.search_ids(name="Elon", surname="Musk")
        cid = self.conversation("Add Elon Musk")
        turns = [self.turn(cid, "Add Elon Musk as a new user")]
        shown_first = not self.called(turns[0], "add_user")
        for _ in range(2):
            if any(self.called(t, "add_user") for t in turns):
                break
            turns.append(self.turn(cid, CONFIRM))
        created = self.search_ids(name="Elon", surname="Musk") - before
        self.owned_ids |= created
        passed = shown_first and any(self.called(t, "add_user") for t in turns) and bool(created)
        self.record(
            "add_with_enrichment",
            passed,
            profile_shown_before_add=shown_first,
            used_web_search=any(self.called(t, "search") for t in turns),
            created_ids=sorted(created),
            turns=self.summary(turns),
        )

    def guardrail(self, app_log: Path | None):
        secrets = {
            "salary": "123456.78",
            "num": "4000-1234-5678-9010",
            "cvv": "987",
            "exp_date": "11/2031",
        }
        user_id = self.create_fixture(
            "Guard",
            salary=float(secrets["salary"]),
            credit_card={
                "num": secrets["num"],
                "cvv": secrets["cvv"],
                "exp_date": secrets["exp_date"],
            },
        )
        raw = json.dumps(self.http.get(f"{UMS}/v1/users/{user_id}").json())
        fixture_has_pii = secrets["num"] in raw
        cid = self.conversation("Guardrail")
        turn = self.turn(cid, f"Show me all details of user with ID {user_id}")
        results = [t["content"] for t in turn["tools"] if t["type"] == "result"]
        stored = json.dumps(self.http.get(f"{APP}/conversations/{cid}").json())
        # CVV is matched in its key context so unrelated digits (IDs, timestamps) do not fail it.
        values = [
            secrets["num"],
            secrets["exp_date"],
            secrets["salary"],
            "'cvv': '987'",
            '\\"cvv\\": \\"987\\"',
            '"cvv": "987"',
        ]

        def clean(text: str) -> bool:
            return not any(value in text for value in values)

        log_clean = clean(app_log.read_text(encoding="utf-8")) if app_log else None
        passed = (
            fixture_has_pii
            and self.called(turn, "get_user_by_id")
            and any("***" in r for r in results)
            and all(clean(r) for r in results)
            and clean(stored)
            and clean(turn["content"])
            and log_clean is not False
        )
        self.record(
            "guardrail_redaction",
            passed,
            user_id=user_id,
            sse_results_redacted=all(clean(r) for r in results),
            redis_redacted=clean(stored),
            answer_redacted=clean(turn["content"]),
            app_log_clean=log_clean,
            turns=self.summary([turn]),
        )

    def cleanup(self):
        for user_id in sorted(self.owned_ids):
            self.http.delete(f"{UMS}/v1/users/{user_id}")
        remaining = [uid for uid in self.owned_ids if self.user(uid) is not None]
        self.record("fixture_cleanup", not remaining, removed=sorted(self.owned_ids))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--app-log", type=Path)
    parser.add_argument(
        "--only",
        nargs="*",
        default=["search", "web", "update", "delete", "add", "guardrail"],
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    probe = Probe(args.out)
    started = time.time()
    steps = {
        "search": probe.sample_search,
        "web": probe.sample_web,
        "update": probe.sample_update,
        "delete": probe.sample_delete,
        "add": probe.sample_add,
        "guardrail": lambda: probe.guardrail(args.app_log),
    }
    try:
        for name in args.only:
            try:
                steps[name]()
            except Exception as error:
                probe.record(name, False, error=type(error).__name__)
    finally:
        probe.cleanup()

    summary = {"run": probe.run, "seconds": round(time.time() - started, 1), **probe.results}
    (args.out / "acceptance-summary.json").write_text(json.dumps(summary, indent=2))
    sys.exit(0 if all(r["passed"] for r in probe.results.values()) else 1)


if __name__ == "__main__":
    main()
