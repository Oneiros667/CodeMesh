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
    assert set(manifest["contracts"]) == set(registered_tools)

    for tool_name, contract in manifest["contracts"].items():
        schema = registered_tools[tool_name].inputSchema
        properties = schema["properties"]
        required = [name for name, argument in contract["arguments"].items() if argument.get("required", False)]

        assert schema.get("required", []) == required
        assert set(contract["arguments"]) == set(properties)

        for name, argument in contract["arguments"].items():
            if not argument.get("required", False):
                assert properties[name]["default"] == argument["default"]

    package_contract = manifest["contracts"]["codemesh_get_context_package"]
    assert package_contract["response"]["relationship_groups"] == [
        "callers",
        "callees",
        "reads",
        "writes",
        "contains",
        "defines",
        "uses_types",
    ]
    assert package_contract["response"]["output_formats"] == ["json", "agent"]

    package_properties = registered_tools["codemesh_get_context_package"].inputSchema["properties"]
    for name in [
        "caller_limit",
        "callee_limit",
        "read_limit",
        "write_limit",
        "contains_limit",
        "definition_limit",
        "uses_type_limit",
    ]:
        assert {"type": "integer"} in package_properties[name]["anyOf"]
        assert {"type": "null"} in package_properties[name]["anyOf"]

    assert package_properties["output_format"]["enum"] == ["json", "agent"]


def test_mcp_context_package_forwards_group_limits(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_context_package(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(data={"query": {"query": query}, "items": [], "arguments": kwargs})

    monkeypatch.setattr(mcp.tools, "get_context_package", fake_get_context_package)

    server = mcp.build_server()
    _content, structured = asyncio.run(
        server.call_tool(
            "codemesh_get_context_package",
            {
                "query": "EnqueueDownload",
                "repository_id": "repo:test",
                "filters": {"kind": "Method"},
                "vector": [0.1, 0.2],
                "relationship_limit": 12,
                "caller_limit": 2,
                "callee_limit": 3,
                "read_limit": 0,
                "write_limit": 1,
                "contains_limit": 1,
                "definition_limit": 1,
                "uses_type_limit": 0,
                "include_repository": False,
                "output_format": "agent",
            },
        )
    )

    assert captured["query"] == "EnqueueDownload"
    assert captured["repository_id"] == "repo:test"
    assert captured["filters"] == {"kind": "Method"}
    assert captured["vector"] == [0.1, 0.2]
    assert captured["relationship_limit"] == 12
    assert captured["caller_limit"] == 2
    assert captured["callee_limit"] == 3
    assert captured["read_limit"] == 0
    assert captured["write_limit"] == 1
    assert captured["contains_limit"] == 1
    assert captured["definition_limit"] == 1
    assert captured["uses_type_limit"] == 0
    assert captured["include_repository"] is False
    assert structured["data"]["arguments"]["read_limit"] == 0
    assert structured["agent_text"].startswith("CodeMesh context package\n")


def test_mcp_search_and_neighbors_forward_query_controls(monkeypatch: Any) -> None:
    captured_search: dict[str, Any] = {}
    captured_neighbors: dict[str, Any] = {}

    async def fake_search_context(query: str, **kwargs: Any) -> ToolResult:
        captured_search["query"] = query
        captured_search.update(kwargs)
        return ToolResult(data={"query": query, "hits": []})

    async def fake_get_neighbors(node_id: str, **kwargs: Any) -> ToolResult:
        captured_neighbors["node_id"] = node_id
        captured_neighbors.update(kwargs)
        return ToolResult(data={"node": {"id": node_id}, "relationships": []})

    monkeypatch.setattr(mcp.tools, "search_context", fake_search_context)
    monkeypatch.setattr(mcp.tools, "get_neighbors", fake_get_neighbors)

    server = mcp.build_server()
    asyncio.run(
        server.call_tool(
            "codemesh_search_context",
            {
                "query": "DownloadAsync",
                "repository_id": "sample_repo",
                "filters": {"filePath": "Downloader.cs"},
                "vector": [0.1, 0.2],
                "include_context_relationships": True,
            },
        )
    )
    asyncio.run(
        server.call_tool(
            "codemesh_get_neighbors",
            {
                "node_id": "node:download",
                "repository_id": "sample_repo",
                "depth": 2,
                "relationship_kinds": ["CALLS", "READS"],
            },
        )
    )

    assert captured_search["query"] == "DownloadAsync"
    assert captured_search["repository_id"] == "sample_repo"
    assert captured_search["filters"] == {"filePath": "Downloader.cs"}
    assert captured_search["vector"] == [0.1, 0.2]
    assert captured_search["include_context_relationships"] is True
    assert captured_neighbors["node_id"] == "node:download"
    assert captured_neighbors["repository_id"] == "sample_repo"
    assert captured_neighbors["depth"] == 2
    assert captured_neighbors["relationship_kinds"] == ["CALLS", "READS"]


def test_mcp_symbol_search_forwards_query_controls(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_search_symbols(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(data={"query": {"query": query}, "symbols": []})

    monkeypatch.setattr(mcp.tools, "search_symbols", fake_search_symbols)

    server = mcp.build_server()
    _content, structured = asyncio.run(
        server.call_tool(
            "codemesh_search_symbols",
            {
                "query": "DownloadAsync",
                "repository_id": "sample_repo",
                "limit": 3,
                "kinds": ["Method"],
                "filters": {"project": "Sample"},
                "include_declarations": False,
            },
        )
    )

    assert captured["query"] == "DownloadAsync"
    assert captured["repository_id"] == "sample_repo"
    assert captured["limit"] == 3
    assert captured["kinds"] == ["Method"]
    assert captured["filters"] == {"project": "Sample"}
    assert captured["include_declarations"] is False
    assert structured["data"]["symbols"] == []


def test_print_tool_manifest_emits_contract_json(capsys: Any) -> None:
    asyncio.run(mcp.print_tool_manifest())

    payload = json.loads(capsys.readouterr().out)

    assert payload == mcp.tool_manifest()
