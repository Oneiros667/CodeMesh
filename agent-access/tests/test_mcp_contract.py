from __future__ import annotations

import asyncio
import json
from typing import Any

from codemesh_agent_access import mcp
from codemesh_agent_access.models import ToolResult


def test_mcp_manifest_matches_registered_tools() -> None:
    server = mcp.build_server()
    registered_tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    manifest = mcp.tool_manifest()

    assert {tool["name"] for tool in manifest["tools"]} == set(registered_tools)

    package_tool = registered_tools["codemesh_get_context_package"]
    package_contract = manifest["contracts"]["codemesh_get_context_package"]
    schema = package_tool.inputSchema
    properties = schema["properties"]

    assert schema["required"] == ["query"]
    assert set(package_contract["arguments"]) == set(properties)
    assert package_contract["response"]["relationship_groups"] == [
        "callers",
        "callees",
        "reads",
        "writes",
        "contains",
        "defines",
        "uses_types",
    ]

    for name, contract in package_contract["arguments"].items():
        if not contract.get("required", False):
            assert properties[name]["default"] == contract["default"]

    for name in [
        "caller_limit",
        "callee_limit",
        "read_limit",
        "write_limit",
        "contains_limit",
        "definition_limit",
        "uses_type_limit",
    ]:
        assert {"type": "integer"} in properties[name]["anyOf"]
        assert {"type": "null"} in properties[name]["anyOf"]


def test_mcp_context_package_forwards_group_limits(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_context_package(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(data={"query": query, "arguments": kwargs})

    monkeypatch.setattr(mcp.tools, "get_context_package", fake_get_context_package)

    server = mcp.build_server()
    _content, structured = asyncio.run(
        server.call_tool(
            "codemesh_get_context_package",
            {
                "query": "EnqueueDownload",
                "repository_id": "repo:test",
                "relationship_limit": 12,
                "caller_limit": 2,
                "callee_limit": 3,
                "read_limit": 0,
                "write_limit": 1,
                "contains_limit": 1,
                "definition_limit": 1,
                "uses_type_limit": 0,
            },
        )
    )

    assert captured["query"] == "EnqueueDownload"
    assert captured["repository_id"] == "repo:test"
    assert captured["relationship_limit"] == 12
    assert captured["caller_limit"] == 2
    assert captured["callee_limit"] == 3
    assert captured["read_limit"] == 0
    assert captured["write_limit"] == 1
    assert captured["contains_limit"] == 1
    assert captured["definition_limit"] == 1
    assert captured["uses_type_limit"] == 0
    assert structured["data"]["arguments"]["read_limit"] == 0


def test_print_tool_manifest_emits_contract_json(capsys: Any) -> None:
    asyncio.run(mcp.print_tool_manifest())

    payload = json.loads(capsys.readouterr().out)

    assert payload == mcp.tool_manifest()
