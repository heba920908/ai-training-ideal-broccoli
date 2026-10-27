import asyncio
import json

import pytest
from t10_mcp_advanced.mcp_server.models.request import MCPRequest
from t10_mcp_advanced.mcp_server.ums_mcp_server import UmsMCPServer


def request(method="tools/list", **params):
    return MCPRequest(
        id=7,
        method=method,
        params={
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
            **params,
        },
    )


def test_discovery_and_five_independent_tool_schemas():
    server = UmsMCPServer()
    discovery = server.handle_discover(request("server/discover"))
    assert discovery.id == 7
    assert discovery.result["supportedVersions"] == ["2026-07-28"]
    result = server.handle_tools_list(request()).result
    assert {tool["name"] for tool in result["tools"]} == {
        "get_user_by_id",
        "search_users",
        "add_user",
        "update_user",
        "delete_users",
    }
    assert result["resultType"] == "complete"
    assert result["ttlMs"] > 0
    assert result["cacheScope"] == "public"
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"]
    schemas = {tool["name"]: tool["inputSchema"] for tool in result["tools"]}
    assert schemas["get_user_by_id"]["required"] == ["id"]
    assert "email" in schemas["add_user"]["required"]
    assert schemas["update_user"]["required"] == ["id", "new_info"]


@pytest.mark.parametrize(
    "meta,code",
    [
        ({}, -32602),
        ({"io.modelcontextprotocol/protocolVersion": "2026-07-28"}, -32602),
        (
            {
                "io.modelcontextprotocol/protocolVersion": "old",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
            -32022,
        ),
        ([], -32602),
        (
            {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": [],
            },
            -32602,
        ),
    ],
)
def test_invalid_metadata_is_a_correlated_protocol_error(meta, code):
    response = UmsMCPServer().validate_request_meta(request(_meta=meta))
    assert response.id == 7
    assert response.error.code == code


def test_missing_tool_and_execution_failure_are_different():
    server = UmsMCPServer()
    missing = asyncio.run(
        server.handle_tools_call(request("tools/call", name="missing"))
    )
    assert missing.error.code == -32602
    failure = asyncio.run(
        server.handle_tools_call(request("tools/call", name="add_user", arguments={}))
    )
    assert failure.error is None
    assert failure.result["isError"] is True
    assert failure.result["content"][0]["type"] == "text"


class Directory:
    def __init__(self):
        self.users = {}

    def add_user(self, model):
        self.users[42] = model.model_dump()
        return json.dumps({"id": 42, **self.users[42]})

    def get_user(self, user_id):
        return json.dumps(self.users[user_id])

    def search_users(self, **filters):
        return json.dumps(
            [
                user
                for user in self.users.values()
                if all(user.get(key) == value for key, value in filters.items())
            ]
        )

    def update_user(self, user_id, model):
        self.users[user_id].update(model.model_dump(exclude_unset=True))
        return self.get_user(user_id)

    def delete_user(self, user_id):
        del self.users[user_id]
        return "deleted"


def test_tools_validate_and_mutate_an_owned_fixture():
    server = UmsMCPServer()
    directory = Directory()
    for tool in server.tools.values():
        tool._user_client = directory

    def call(tool_name, **arguments):
        response = asyncio.run(
            server.handle_tools_call(
                request("tools/call", name=tool_name, arguments=arguments)
            )
        )
        assert not response.result["isError"]
        return response.result["content"][0]["text"]

    assert (
        json.loads(
            call(
                "add_user",
                name="Test",
                surname="Fixture",
                email="test@example.invalid",
                about_me="Synthetic",
            )
        )["id"]
        == 42
    )
    assert json.loads(call("get_user_by_id", id=42))["surname"] == "Fixture"
    assert len(json.loads(call("search_users", email="test@example.invalid"))) == 1
    assert (
        json.loads(call("update_user", id=42, new_info={"company": "Updated"}))[
            "company"
        ]
        == "Updated"
    )
    assert call("delete_users", id=42) == "deleted"
    assert not directory.users
