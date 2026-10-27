import asyncio
import importlib
import importlib.util
import json
from secrets import token_urlsafe
from types import SimpleNamespace

import httpx
import pytest


def probe_module():
    assert importlib.util.find_spec("t11_mcp_auth.probe") is not None, (
        "task 6.1 probe implementation is missing"
    )
    return importlib.import_module("t11_mcp_auth.probe")


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    probe = probe_module()
    secret = token_urlsafe()
    records = {7: {"id": 7, "email": "unrelated@example.invalid"}}
    calls, deleted, requests = [], [], []
    control = SimpleNamespace(
        failure=None,
        malformed_create=False,
        denied=False,
        negative_status=401,
        cleanup_failure=False,
        lookup_mismatch=False,
        clock=0.0,
        entries=0,
        empty_read=False,
        cancel=False,
        unchanged_refresh=False,
    )
    monkeypatch.setattr(probe, "load_environment", lambda: None)
    monkeypatch.setattr(probe, "required", lambda name: secret)

    def handle(request):
        requests.append(request)
        if request.url.path == "/mcp":
            return httpx.Response(control.negative_status, text=f"password={secret}")
        if request.url.path == "/v1/users/search":
            email = request.url.params["email"]
            found = [record for record in records.values() if record["email"] == email]
            if control.lookup_mismatch:
                found = [records[7]]
            return httpx.Response(200, json=found)
        identifier = int(request.url.path.rsplit("/", 1)[1])
        if request.method == "DELETE":
            if control.cleanup_failure:
                return httpx.Response(500, text=secret)
            deleted.append(identifier)
            records.pop(identifier, None)
            return httpx.Response(204)
        return httpx.Response(
            200 if identifier in records else 404, json=records.get(identifier, {})
        )

    original_http = httpx.AsyncClient
    monkeypatch.setattr(
        probe.httpx,
        "AsyncClient",
        lambda **kwargs: original_http(**kwargs, transport=httpx.MockTransport(handle)),
    )

    class Client:
        def __init__(self, *args):
            self.client = object()
            self._http_client = object()
            self.token_manager = SimpleNamespace(
                _access_token=secret,
                _refresh_token=token_urlsafe(),
                _expires_at=30.0,
            )

        async def __aenter__(self):
            control.entries += 1
            if control.denied:
                response = httpx.Response(
                    403, request=httpx.Request("POST", "http://localhost/mcp")
                )
                raise httpx.HTTPStatusError(
                    secret, request=response.request, response=response
                )
            return self

        async def __aexit__(self, *args):
            return None

        async def get_tools(self):
            if control.clock >= 61 and not control.unchanged_refresh:
                self.token_manager._access_token = token_urlsafe()
            return [{"function": {"name": name}} for name in probe.TOOLS]

        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            if name == "add_user":
                record = {"id": 42, **arguments["user_create_model"]}
                records[42] = record
                if control.failure == "add_user":
                    raise RuntimeError(f"callback?code={secret}")
                return (
                    "unparseable"
                    if control.malformed_create
                    else ("User successfully added: " + json.dumps(record))
                )
            if name == control.failure:
                if control.cancel:
                    raise asyncio.CancelledError()
                raise RuntimeError(f"remote error body {secret}")
            if name == "delete_user":
                if control.cleanup_failure:
                    raise RuntimeError(secret)
                deleted.append(arguments["user_id"])
                records.pop(arguments["user_id"])
                return "User successfully deleted"
            if name == "update_user":
                from commons.user_service.user_info import UserUpdate

                update = UserUpdate.model_validate(arguments["user_update_model"])
                records[arguments["user_id"]].update(
                    update.model_dump(exclude_unset=True)
                )
                return "User successfully updated: " + json.dumps(records[42])
            if control.empty_read:
                return "(empty result)"
            return "```\n  email: " + records[42]["email"] + "\n```"

    monkeypatch.setattr(probe, "ApiKeyMCPClient", Client)
    monkeypatch.setattr(probe, "OauthHttpMCPClient", Client)
    args = probe.parser().parse_args(
        ["--auth", "api-key", "--output-dir", str(tmp_path)]
    )
    return SimpleNamespace(
        probe=probe,
        args=args,
        control=control,
        records=records,
        calls=calls,
        deleted=deleted,
        requests=requests,
        secret=secret,
        output=tmp_path,
    )


def test_safe_capture_recursively_redacts_known_and_sensitive_values(tmp_path):
    probe = probe_module()
    secret = token_urlsafe()
    probe.write_capture(
        tmp_path / "capture.json",
        {
            "nested": [
                {
                    "Authorization": f"Bearer {secret}",
                    "code_verifier": secret,
                    "password": secret,
                    "callback": f"http://localhost/?code={secret}",
                }
            ],
            "message": f"prefix {secret}",
        },
        secrets=(secret,),
    )
    saved = (tmp_path / "capture.json").read_text()
    assert secret not in saved
    assert "<redacted>" in saved


def test_success_executes_five_exact_tools_and_only_deletes_own_fixture(runtime):
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 0
    assert summary["scenarios"]["cleanup"]["outcome"] == "passed"
    assert {name for name, _ in runtime.calls} == set(runtime.probe.TOOLS)
    assert runtime.deleted == [42]
    assert list(runtime.records) == [7]
    arguments = dict(runtime.calls)
    assert set(arguments["search_user"]) == {"search_user_request"}
    assert set(arguments["add_user"]) == {"user_create_model"}
    assert set(arguments["update_user"]) == {"user_id", "user_update_model"}
    assert (
        arguments["update_user"]["user_update_model"]["name"]
        != arguments["add_user"]["user_create_model"]["name"]
    )
    assert set(arguments["delete_user"]) == {"user_id"}
    text = "".join(path.read_text() for path in runtime.output.glob("*.json*"))
    assert runtime.secret not in text
    assert "unrelated@example.invalid" not in text
    assert "remote error body" not in text


@pytest.mark.parametrize(
    "failure",
    ["add_user", "search_user", "get_user_by_id", "update_user", "delete_user"],
)
def test_finally_cleans_owned_fixture_on_every_tool_failure(runtime, failure):
    runtime.control.failure = failure
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["cleanup"]["outcome"] == "passed"
    assert runtime.deleted == [42]
    assert list(runtime.records) == [7]
    assert runtime.secret not in json.dumps(summary)


def test_malformed_add_result_falls_back_to_filtered_ums_search(runtime):
    runtime.control.malformed_create = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 0
    assert runtime.deleted == [42]
    assert any(request.url.path == "/v1/users/search" for request in runtime.requests)


def test_lookup_never_deletes_unrelated_or_unverified_record(runtime):
    runtime.control.malformed_create = True
    runtime.control.lookup_mismatch = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["cleanup"]["outcome"] == "failed"
    assert runtime.deleted == []
    assert 7 in runtime.records


def test_cleanup_failure_is_visible_and_nonzero(runtime):
    runtime.control.cleanup_failure = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["cleanup"]["outcome"] == "failed"


def test_failed_behavior_verification_still_cleans_fixture(runtime):
    runtime.control.empty_read = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["search_user"]["outcome"] == "failed"
    assert summary["scenarios"]["cleanup"]["outcome"] == "passed"
    assert runtime.deleted == [42]


def test_cancelled_tool_still_cleans_only_owned_fixture(runtime):
    runtime.control.failure = "search_user"
    runtime.control.cancel = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["cleanup"]["outcome"] == "passed"
    assert runtime.deleted == [42]
    assert list(runtime.records) == [7]


def test_unexpected_negative_status_cannot_be_reported_as_pass(runtime):
    runtime.control.negative_status = 200
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["missing_credential"]["outcome"] == "failed"


@pytest.mark.parametrize(
    "mode,port,header",
    [
        ("api-key", 8007, "x-api-key"),
        ("oauth", 8008, "authorization"),
    ],
)
def test_negative_requests_use_expected_endpoint_and_stateless_protocol(
    runtime, mode, port, header
):
    runtime.args.auth = mode
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 0
    missing, invalid = runtime.requests[:2]
    assert missing.url.port == invalid.url.port == port
    assert header not in missing.headers
    assert header in invalid.headers
    assert missing.headers["MCP-Protocol-Version"] == "2026-07-28"
    assert missing.headers["MCP-Method"] == "server/discover"
    assert "MCP-Session-Id" not in missing.headers
    assert json.loads(missing.content)["method"] == "server/discover"
    assert summary["scenarios"]["refresh"]["outcome"] == "blocked"


def test_expected_forbidden_accepts_discovery_403_without_crud(runtime):
    runtime.args.auth = "oauth"
    runtime.args.expect_forbidden = True
    runtime.control.denied = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 0
    assert summary["scenarios"]["role_denied"]["status"] == 403
    assert runtime.calls == []
    assert runtime.deleted == []


def test_expected_forbidden_fails_if_login_is_actually_allowed(runtime):
    runtime.args.auth = "oauth"
    runtime.args.expect_forbidden = True
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["role_denied"]["outcome"] == "failed"
    assert runtime.calls == []


def test_refresh_waits_past_expiry_on_same_client_without_real_sleep(runtime):
    runtime.args.auth = "oauth"
    runtime.args.verify_refresh = True
    waits = []

    async def wait(seconds):
        waits.append(seconds)
        runtime.control.clock += seconds

    summary = asyncio.run(
        runtime.probe.run_probe(
            runtime.args,
            clock=lambda: runtime.control.clock,
            wait=wait,
        )
    )
    assert summary["exit_code"] == 0
    observed = summary["scenarios"]["refresh"]
    assert observed["outcome"] == "passed"
    assert observed["credential_changed"] is True
    assert observed["same_client"] is True
    assert sum(waits) >= 61
    assert runtime.control.entries == 1


def test_unchanged_token_is_not_refresh_evidence(runtime):
    runtime.args.auth = "oauth"
    runtime.args.verify_refresh = True
    runtime.control.unchanged_refresh = True

    async def wait(seconds):
        runtime.control.clock += seconds

    summary = asyncio.run(
        runtime.probe.run_probe(
            runtime.args,
            clock=lambda: runtime.control.clock,
            wait=wait,
        )
    )
    assert summary["exit_code"] == 1
    assert summary["scenarios"]["refresh"]["outcome"] == "failed"
    assert runtime.control.entries == 1
    assert runtime.deleted == [42]


@pytest.mark.parametrize(
    "url",
    [
        "http://remote.invalid/mcp",
        "http://user:password@127.0.0.1/mcp",
        "http://127.0.0.1/mcp?code=private",
        "http://127.0.0.1/mcp#private",
    ],
)
def test_invalid_urls_fail_before_network_without_echoing_input(runtime, url):
    runtime.args.url = url
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert runtime.requests == []
    assert url not in json.dumps(summary)


@pytest.mark.parametrize(
    "mode,forbidden,refresh",
    [
        ("api-key", True, False),
        ("api-key", False, True),
        ("oauth", True, True),
    ],
)
def test_incompatible_options_fail_without_network(runtime, mode, forbidden, refresh):
    runtime.args.auth = mode
    runtime.args.expect_forbidden = forbidden
    runtime.args.verify_refresh = refresh
    summary = asyncio.run(runtime.probe.run_probe(runtime.args))
    assert summary["exit_code"] == 1
    assert runtime.requests == []


def test_main_returns_nonzero_and_never_prints_exception_secrets(
    monkeypatch, tmp_path, capsys
):
    probe = probe_module()
    secret = token_urlsafe()

    async def fail(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(probe, "run_probe", fail)
    assert probe.main(["--auth", "api-key", "--output-dir", str(tmp_path)]) == 1
    assert secret not in capsys.readouterr().out
