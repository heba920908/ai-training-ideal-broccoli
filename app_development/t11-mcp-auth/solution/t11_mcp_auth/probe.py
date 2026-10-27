# ruff: noqa: BLE001

import argparse
import asyncio
import json
import math
import secrets as random_secrets
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from t11_mcp_auth.config import load_environment, redact, required

PROTOCOL = "2026-07-28"
TOOLS = ("add_user", "search_user", "get_user_by_id", "update_user", "delete_user")
MAX_REFRESH_WAIT = 180.0


def ApiKeyMCPClient(url, key):
    from t11_mcp_auth.agent.mcp_clients.api_key_mcp_client import ApiKeyMCPClient

    return ApiKeyMCPClient(url, key)


def OauthHttpMCPClient(url):
    from t11_mcp_auth.agent.mcp_clients.oauth_mcp_client import OauthHttpMCPClient

    return OauthHttpMCPClient(url)


def parser():
    result = argparse.ArgumentParser(description="Local T11 authenticated MCP probe")
    result.add_argument("--auth", choices=("api-key", "oauth"), required=True)
    result.add_argument("--url")
    result.add_argument("--ums-url", default="http://127.0.0.1:8042")
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--expect-forbidden", action="store_true")
    result.add_argument("--verify-refresh", action="store_true")
    return result


def write_capture(path, value, secrets=()):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(value, secrets=secrets), indent=2) + "\n")


def _local_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "?" in value
        or "#" in value
        or "\\" in value
        or any(character.isspace() for character in value)
    ):
        raise ValueError("A credential-free loopback URL is required")
    _ = parsed.port
    return value.rstrip("/")


def _http_status(error):
    pending, visited = [error], set()
    while pending and len(visited) < 40:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        status = getattr(getattr(current, "response", None), "status_code", None)
        if isinstance(status, int):
            return status
        pending.extend(getattr(current, "exceptions", ()))
        pending.extend(
            item
            for item in (
                getattr(current, "__cause__", None),
                getattr(current, "__context__", None),
            )
            if item is not None
        )
    return None


def _owned(record, email):
    return (
        isinstance(record, dict)
        and type(record.get("id")) is int
        and record["id"] > 0
        and record.get("email") == email
    )


def _created_record(result, email):
    if not isinstance(result, str):
        return result if _owned(result, email) else None
    try:
        record = json.loads(result.removeprefix("User successfully added: "))
    except (ValueError, TypeError):
        return None
    return record if _owned(record, email) else None


async def run_probe(args, *, clock=time.monotonic, wait=asyncio.sleep):
    scenarios = {
        name: {"outcome": "blocked", "reason": "not exercised in this run"}
        for name in (
            "missing_credential",
            "invalid_credential",
            "discovery",
            "role_denied",
            *TOOLS,
            "refresh",
            "cleanup",
        )
    }
    summary = {
        "auth": args.auth,
        "protocol": PROTOCOL,
        "scenarios": scenarios,
        "exit_code": 1,
    }
    events, known_secrets = [], set()
    email = f"t11-probe-{uuid.uuid4().hex}@example.invalid"
    fixture = {"attempted": False, "id": None}
    current = "configuration"
    wrapper = None

    def credentials():
        manager = getattr(wrapper, "token_manager", None)
        for name in ("_access_token", "_refresh_token"):
            value = getattr(manager, name, None)
            if isinstance(value, str) and value:
                known_secrets.add(value)

    def capture(operation, request, response, status=None):
        credentials()
        events.append(
            {
                "operation": operation,
                "request": request,
                "status": status,
                "response": response,
            }
        )

    def passed(name, **details):
        scenarios[name] = {"outcome": "passed", **details}

    async def lookup(http, ums):
        response = await http.get(f"{ums}/v1/users/search", params={"email": email})
        capture(
            "fixture_lookup",
            {"method": "GET", "path": "/v1/users/search", "params": {"email": email}},
            {"body": "omitted; ownership checked locally"},
            response.status_code,
        )
        response.raise_for_status()
        records = response.json()
        if not isinstance(records, list) or any(
            not _owned(item, email) for item in records
        ):
            raise RuntimeError("Fixture ownership could not be verified")
        if len(records) > 1:
            raise RuntimeError("Fixture lookup was not unique")
        return records[0] if records else None

    async def verify_record(http, ums, identifier):
        response = await http.get(f"{ums}/v1/users/{identifier}")
        capture(
            "fixture_read",
            {"method": "GET", "path": f"/v1/users/{identifier}"},
            {"body": "omitted; ownership checked locally"},
            response.status_code,
        )
        response.raise_for_status()
        record = response.json()
        if not _owned(record, email) or record["id"] != identifier:
            raise RuntimeError("Fixture ownership could not be verified")
        return record

    async def call(name, arguments):
        try:
            result = await wrapper.call_tool(name, arguments)
            if isinstance(result, str) and result.startswith("Tool error:"):
                raise RuntimeError("MCP tool reported failure")
        except (Exception, asyncio.CancelledError) as error:
            capture(
                name,
                {"method": "tools/call", "name": name, "arguments": arguments},
                {"outcome": "failed", "detail": "remote body omitted"},
                _http_status(error),
            )
            raise
        capture(
            name,
            {"method": "tools/call", "name": name, "arguments": arguments},
            {"outcome": "returned", "body": "omitted; verified through owned fixture"},
        )
        return result

    async def cleanup(http, ums):
        if not fixture["attempted"]:
            scenarios["cleanup"] = {"outcome": "not_needed"}
            return
        try:
            record = await lookup(http, ums)
            if record is not None:
                identifier = record["id"]
                if fixture["id"] is not None and identifier != fixture["id"]:
                    raise RuntimeError("Fixture identifier changed")
                await verify_record(http, ums, identifier)
                response = await http.delete(f"{ums}/v1/users/{identifier}")
                capture(
                    "fixture_cleanup",
                    {"method": "DELETE", "path": f"/v1/users/{identifier}"},
                    {"body": "omitted"},
                    response.status_code,
                )
                if response.status_code != 204:
                    raise RuntimeError("Fixture deletion failed")
                if await lookup(http, ums) is not None:
                    raise RuntimeError("Fixture remains after deletion")
            passed("cleanup", fixture_absent=True)
        except (Exception, asyncio.CancelledError):
            scenarios["cleanup"] = {
                "outcome": "failed",
                "reason": "owned fixture cleanup could not be verified",
            }

    try:
        load_environment()
        if (args.expect_forbidden or args.verify_refresh) and args.auth != "oauth":
            raise ValueError("OAuth options require OAuth mode")
        if args.expect_forbidden and args.verify_refresh:
            raise ValueError("Forbidden and refresh checks require separate logins")
        url = _local_url(
            args.url
            or f"http://127.0.0.1:{8007 if args.auth == 'api-key' else 8008}/mcp"
        )
        ums = _local_url(args.ums_url)
        summary.update({"url": url, "ums_url": ums})
        key = required("MCP_API_KEY") if args.auth == "api-key" else None
        if key:
            known_secrets.add(key)
        wrong = random_secrets.token_urlsafe(32)
        while wrong == key:
            wrong = random_secrets.token_urlsafe(32)
        known_secrets.add(wrong)
        async with httpx.AsyncClient(
            timeout=60, trust_env=False, follow_redirects=False
        ) as http:
            try:
                for name, auth_headers in (
                    ("missing_credential", {}),
                    (
                        "invalid_credential",
                        {"X-API-Key": wrong}
                        if key
                        else {"Authorization": "Bearer malformed"},
                    ),
                ):
                    current = name
                    headers = {
                        "MCP-Protocol-Version": PROTOCOL,
                        "MCP-Method": "server/discover",
                        "Accept": "application/json, text/event-stream",
                        **auth_headers,
                    }
                    payload = {
                        "jsonrpc": "2.0",
                        "id": uuid.uuid4().hex,
                        "method": "server/discover",
                        "params": {},
                    }
                    response = await http.post(url, headers=headers, json=payload)
                    capture(
                        name,
                        {
                            "method": "POST",
                            "url": url,
                            "headers": headers,
                            "json": payload,
                        },
                        {"body": "omitted"},
                        response.status_code,
                    )
                    scenarios[name] = {
                        "outcome": "passed"
                        if response.status_code == 401
                        else "failed",
                        "status": response.status_code,
                        "expected_status": 401,
                    }

                current = "discovery"
                wrapper = ApiKeyMCPClient(url, key) if key else OauthHttpMCPClient(url)
                try:
                    async with wrapper:
                        credentials()
                        passed(
                            "discovery",
                            status=None,
                            evidence="SDK server/discover returned successfully",
                        )
                        capture(
                            "discovery",
                            {"method": "server/discover", "protocol": PROTOCOL},
                            {
                                "outcome": "returned",
                                "http_status": "not exposed by SDK wrapper",
                            },
                        )
                        if args.expect_forbidden:
                            scenarios["role_denied"] = {
                                "outcome": "failed",
                                "reason": "discovery unexpectedly allowed",
                            }
                            raise RuntimeError("Expected role denial")
                        current = "tools_list"
                        listing = await wrapper.get_tools()
                        names = {item["function"]["name"] for item in listing}
                        capture(
                            "tools_list",
                            {"method": "tools/list"},
                            {"tools": sorted(names & set(TOOLS))},
                        )
                        if names != set(TOOLS):
                            raise RuntimeError("Unexpected T11 tool discovery")
                        passed("tools_list")
                        current = "add_user"
                        fixture["attempted"] = True
                        created = await call(
                            "add_user",
                            {
                                "user_create_model": {
                                    "name": "T11",
                                    "surname": "Probe",
                                    "email": email,
                                    "about_me": "Owned synthetic acceptance fixture",
                                }
                            },
                        )
                        record = _created_record(created, email) or await lookup(
                            http, ums
                        )
                        if record is None:
                            raise RuntimeError("Created fixture not found")
                        fixture["id"] = identifier = record["id"]
                        await verify_record(http, ums, identifier)
                        passed("add_user", user_id=identifier)
                        current = "search_user"
                        found = await call(
                            "search_user", {"search_user_request": {"email": email}}
                        )
                        if email not in str(found):
                            raise RuntimeError(
                                "Search did not return the owned fixture"
                            )
                        passed("search_user")
                        current = "get_user_by_id"
                        found = await call("get_user_by_id", {"user_id": identifier})
                        if email not in str(found):
                            raise RuntimeError("Read did not return the owned fixture")
                        await verify_record(http, ums, identifier)
                        passed("get_user_by_id")
                        current = "update_user"
                        updated = {
                            "name": "T11Updated",
                            "surname": "Probe",
                            "email": email,
                        }
                        await verify_record(http, ums, identifier)
                        await call(
                            "update_user",
                            {"user_id": identifier, "user_update_model": updated},
                        )
                        observed = await verify_record(http, ums, identifier)
                        if any(
                            observed.get(name) != value
                            for name, value in updated.items()
                        ):
                            raise RuntimeError("Update was not observed")
                        passed("update_user")
                        current = "delete_user"
                        await verify_record(http, ums, identifier)
                        await call("delete_user", {"user_id": identifier})
                        if await lookup(http, ums) is not None:
                            raise RuntimeError("Deletion was not observed")
                        passed("delete_user")
                        if args.verify_refresh:
                            current = "refresh"
                            manager = wrapper.token_manager
                            previous = manager._access_token
                            credentials()
                            sdk, transport = wrapper.client, wrapper._http_client
                            started = clock()
                            threshold = getattr(manager, "_expires_at", None)
                            delay = 61.0
                            if isinstance(threshold, (float, int)) and math.isfinite(
                                threshold
                            ):
                                delay = max(delay, threshold + 31.0 - started)
                            if delay > MAX_REFRESH_WAIT:
                                raise RuntimeError("Expiry exceeds bounded probe wait")
                            async with asyncio.timeout(MAX_REFRESH_WAIT + 5):
                                await wait(delay)
                                elapsed = clock() - started
                                if elapsed < delay:
                                    raise RuntimeError(
                                        "Clock did not reach post-expiry boundary"
                                    )
                                await wrapper.get_tools()
                            credentials()
                            observation = {
                                "elapsed_seconds": elapsed,
                                "credential_changed": bool(previous)
                                and previous != manager._access_token,
                                "same_client": sdk is wrapper.client
                                and transport is wrapper._http_client,
                            }
                            capture(
                                "refresh",
                                {"method": "tools/list", "wait_seconds": delay},
                                observation,
                            )
                            if (
                                not observation["credential_changed"]
                                or not observation["same_client"]
                            ):
                                raise RuntimeError(
                                    "Same-client refresh was not observed"
                                )
                            passed("refresh", **observation)
                except (Exception, asyncio.CancelledError) as error:
                    credentials()
                    status = _http_status(error)
                    if (
                        args.expect_forbidden
                        and current == "discovery"
                        and status == 403
                    ):
                        passed(
                            "role_denied",
                            status=403,
                            evidence="browser PKCE client discovery denied",
                        )
                        scenarios["discovery"] = {"outcome": "denied", "status": 403}
                        capture(
                            "role_denied",
                            {"method": "server/discover"},
                            {"outcome": "denied"},
                            403,
                        )
                    else:
                        scenarios[current] = {
                            "outcome": "failed",
                            "status": status,
                            "reason": "probe operation failed; remote details omitted",
                        }
            finally:
                await cleanup(http, ums)
    except (Exception, asyncio.CancelledError) as error:
        scenarios[current] = {
            "outcome": "failed",
            "status": _http_status(error),
            "reason": "probe dependency or configuration failed; details omitted",
        }
    summary["exit_code"] = int(
        any(item["outcome"] == "failed" for item in scenarios.values())
    )
    credentials()
    write_capture(args.output_dir / "events.json", events, secrets=known_secrets)
    write_capture(args.output_dir / "summary.json", summary, secrets=known_secrets)
    return redact(summary, secrets=known_secrets)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        summary = asyncio.run(run_probe(args))
    except (Exception, KeyboardInterrupt):
        print("Probe failed; evidence could not be completed. Remote details omitted.")
        return 1
    print(json.dumps(summary, indent=2))
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
