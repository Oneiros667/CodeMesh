from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from codemesh_agent_access import mcp
from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.models import ToolResult


def test_mcp_manifest_matches_registered_tools() -> None:
    server = mcp.build_server(profile="diagnostic")
    registered_tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    manifest = mcp.tool_manifest(profile="diagnostic")

    assert manifest["profile"] == "diagnostic"
    assert server.instructions == manifest["instructions"]
    assert "codemesh_get_context_package" in manifest["instructions"]
    assert "concise implementation concepts" in manifest["instructions"]
    assert "focused context-package queries" in manifest["instructions"]
    assert "instead of one long full-task query" in manifest["instructions"]
    assert "targeted, batched checkout reads" in manifest["instructions"]
    assert "fails closed" in manifest["instructions"]
    assert "only for explicit" in manifest["instructions"]
    assert {tool["name"] for tool in manifest["tools"]} == set(registered_tools)
    assert set(manifest["contracts"]) == set(registered_tools)

    for tool_name, contract in manifest["contracts"].items():
        manifest_tool = next(
            tool for tool in manifest["tools"] if tool["name"] == tool_name
        )
        assert manifest_tool["description"] == contract["description"]
        assert registered_tools[tool_name].description == contract["description"]

        schema = registered_tools[tool_name].inputSchema
        properties = schema["properties"]
        required = [
            name
            for name, argument in contract["arguments"].items()
            if argument.get("required", False)
        ]

        assert schema.get("required", []) == required
        assert set(contract["arguments"]) == set(properties)

        for name, argument in contract["arguments"].items():
            if not argument.get("required", False):
                assert properties[name]["default"] == argument["default"]

    search_contract = manifest["contracts"]["codemesh_search_context"]
    assert search_contract["response"]["diagnostics"] == [
        "mode",
        "embedding_attempted",
        "embedding_source",
        "model_provider",
        "vector_available",
        "vector_hit_count",
        "lexical_hit_count",
        "summary_hit_count",
        "vector_candidate_count",
        "lexical_candidate_count",
        "summary_candidate_count",
        "lexical_fallback",
        "hit_count",
    ]

    package_contract = manifest["contracts"]["codemesh_get_context_package"]
    assert "fails closed before search" in package_contract["description"]
    assert package_contract["response"]["fields"] == [
        "query",
        "repository",
        "latest_run",
        "items",
        "validation_recommendations",
        "total_snippet_characters",
        "generated_at",
    ]
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
    assert package_contract["response"]["agent_content_type"] == "text"
    assert package_contract["response"]["agent_max_characters"] == 12000

    package_properties = registered_tools["codemesh_get_context_package"].inputSchema[
        "properties"
    ]
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

    assert "codemesh_delete_repository" not in manifest["contracts"]

    status_contract = manifest["contracts"]["codemesh_get_repository_status"]
    assert "not a required first step" in status_contract["description"]
    assert status_contract["response"]["fields"] == [
        "repository_id",
        "repository",
        "latest_run",
        "summary_coverage",
        "counts",
        "freshness",
        "refresh",
        "codemesh_next_action",
        "generated_at",
    ]

    guidance_contract = manifest["contracts"]["codemesh_get_tool_guidance"]
    assert guidance_contract["response"]["fields"] == [
        "task",
        "recommended_workflows",
        "available_tools",
        "default_start",
    ]


def test_mcp_normal_profile_is_the_default_product_surface() -> None:
    expected_tools = {
        "codemesh_get_context_package",
        "codemesh_get_repository_status",
        "codemesh_list_repositories",
        "codemesh_get_node",
    }

    server = mcp.build_server()
    registered_tools = {tool.name for tool in asyncio.run(server.list_tools())}
    manifest = mcp.tool_manifest()

    assert mcp.DEFAULT_TOOL_PROFILE == "normal"
    assert manifest["profile"] == "normal"
    assert registered_tools == expected_tools
    assert {tool["name"] for tool in manifest["tools"]} == expected_tools
    assert set(manifest["contracts"]) == expected_tools


def test_mcp_diagnostic_profile_excludes_repository_deletion() -> None:
    manifest = mcp.tool_manifest(profile="diagnostic")
    tool_names = {tool["name"] for tool in manifest["tools"]}

    assert "codemesh_search_context" in tool_names
    assert "codemesh_get_tool_guidance" in tool_names
    assert "codemesh_delete_repository" not in tool_names


def test_mcp_unknown_profile_fails_fast() -> None:
    with pytest.raises(ValueError, match="Unknown MCP tool profile 'admin'"):
        mcp.build_server(profile="admin")

    with pytest.raises(ValueError, match="Expected one of: normal, diagnostic"):
        mcp.tool_manifest(profile="admin")


def test_normal_mcp_runtime_requires_checkout_binding() -> None:
    with pytest.raises(ValueError, match="normal MCP profile requires"):
        mcp.run(profile="normal")


def test_bound_mcp_injects_identity_and_rejects_override(
    monkeypatch: Any,
    tmp_path,
) -> None:
    captured: dict[str, Any] = {}
    binding = RepositoryBinding(
        "project:test",
        "checkout:test",
        str(tmp_path),
        "view:test",
    )

    async def fake_get_context_package(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(
            data={
                "query": {"query": query, "repository_id": kwargs["repository_id"]},
                "items": [],
                "validation_recommendations": [],
                "total_snippet_characters": 0,
                "generated_at": "2026-08-31T00:00:00Z",
            }
        )

    monkeypatch.setattr(mcp.tools, "get_context_package", fake_get_context_package)
    server = mcp.build_server(binding=binding)

    result = asyncio.run(
        server.call_tool(
            "codemesh_get_context_package",
            {"query": "find native replay", "output_format": "json"},
        )
    )
    with pytest.raises(ToolError, match="does not match the configured project"):
        asyncio.run(
            server.call_tool(
                "codemesh_get_context_package",
                {
                    "query": "find native replay",
                    "repository_id": "project:other",
                    "output_format": "json",
                },
            )
        )

    assert result.isError is False
    assert captured["repository_id"] == "project:test"
    assert captured["binding"] is binding
    assert server.instructions == mcp.tool_manifest(binding=binding)["instructions"]
    assert "checkout:test" in server.instructions


def test_mcp_context_package_forwards_group_limits(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_context_package(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(
            data={
                "query": {"query": query},
                "items": [
                    {
                        "hit": {
                            "node_id": "node:oversized",
                            "stable_key": "method:Oversized",
                            "kind": "Method",
                            "file_path": "src/Oversized.cs",
                            "start_line": 1,
                            "end_line": 2,
                            "score": 1.0,
                        },
                        "node": {"name": "Oversized"},
                        "snippet": "x" * 50_000,
                    }
                ],
                "arguments": kwargs,
                "oversized_internal_data": "x" * 200_000,
                "total_snippet_characters": 0,
                "generated_at": "2026-08-07T00:00:00Z",
            }
        )

    monkeypatch.setattr(mcp.tools, "get_context_package", fake_get_context_package)

    server = mcp.build_server()
    result = asyncio.run(
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
                "max_characters": 20_000,
            },
        )
    )
    content = result.content
    structured = result.structuredContent

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
    assert structured is None
    assert len(content) == 1
    assert content[0].text.startswith("CodeMesh context package\n")
    assert "oversized_internal_data" not in content[0].text
    assert len(content[0].text) <= 12_000
    assert "[truncated to 12000 characters]" in content[0].text


def test_mcp_tool_guidance_ranks_task_workflows() -> None:
    server = mcp.build_server(profile="diagnostic")
    _content, structured = asyncio.run(
        server.call_tool(
            "codemesh_get_tool_guidance",
            {"task": "check whether the repository index is stale before editing"},
        )
    )

    data = structured["data"]
    assert data["task"] == "check whether the repository index is stale before editing"
    assert data["recommended_workflows"][0]["id"] == "check_freshness"
    assert (
        data["recommended_workflows"][0]["steps"][0]["tool"]
        == "codemesh_list_repositories"
    )
    assert "codemesh_get_tool_guidance" in data["available_tools"]
    assert "codemesh_delete_repository" not in data["available_tools"]
    assert all(
        workflow["id"] != "delete_indexed_repository"
        for workflow in data["recommended_workflows"]
    )


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

    server = mcp.build_server(profile="diagnostic")
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

    server = mcp.build_server(profile="diagnostic")
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


def test_mcp_summary_coverage_forwards_repository_id(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_summary_coverage(repository_id: str) -> ToolResult:
        captured["repository_id"] = repository_id
        return ToolResult(data={"repository_id": repository_id, "completed_count": 3})

    monkeypatch.setattr(mcp.tools, "get_summary_coverage", fake_get_summary_coverage)

    server = mcp.build_server(profile="diagnostic")
    _content, structured = asyncio.run(
        server.call_tool(
            "codemesh_get_summary_coverage",
            {"repository_id": "sample_repo"},
        )
    )

    assert captured["repository_id"] == "sample_repo"
    assert structured["data"]["completed_count"] == 3


def test_mcp_repository_status_forwards_repository_id(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_repository_status(
        repository_id: str, **kwargs: Any
    ) -> ToolResult:
        captured["repository_id"] = repository_id
        return ToolResult(
            data={"repository_id": repository_id, "freshness": {"status": "unknown"}}
        )

    monkeypatch.setattr(mcp.tools, "get_repository_status", fake_get_repository_status)

    server = mcp.build_server()
    _content, structured = asyncio.run(
        server.call_tool(
            "codemesh_get_repository_status",
            {"repository_id": "sample_repo"},
        )
    )

    assert captured["repository_id"] == "sample_repo"
    assert structured["data"]["freshness"]["status"] == "unknown"
    assert structured["data"]["codemesh_next_action"] == {
        "use_codemesh": False,
        "next_tool": None,
        "instruction": (
            "Do not use CodeMesh context for this task because the exact binding "
            "is not both accepted and fresh. Fall back to direct source inspection."
        ),
    }


def test_bound_mcp_repository_status_directs_fresh_context_retrieval(
    monkeypatch: Any,
    tmp_path,
) -> None:
    binding = RepositoryBinding(
        "project:test",
        "checkout:test",
        str(tmp_path),
        "view:test",
    )

    async def fake_get_repository_status(
        repository_id: str, **kwargs: Any
    ) -> ToolResult:
        assert repository_id == "project:test"
        assert kwargs["binding"] is binding
        return ToolResult(
            data={
                "repository_id": repository_id,
                "freshness": {
                    "status": "fresh",
                    "binding": {"status": "accepted", "issues": []},
                },
            }
        )

    monkeypatch.setattr(mcp.tools, "get_repository_status", fake_get_repository_status)

    server = mcp.build_server(binding=binding)
    _content, structured = asyncio.run(
        server.call_tool("codemesh_get_repository_status", {})
    )

    assert structured["data"]["codemesh_next_action"]["use_codemesh"] is True
    assert (
        structured["data"]["codemesh_next_action"]["next_tool"]
        == "codemesh_get_context_package"
    )
    assert "Continue now" in structured["data"]["codemesh_next_action"]["instruction"]
    assert (
        "focused implementation and test queries"
        in structured["data"]["codemesh_next_action"]["instruction"]
    )


def test_mcp_profiles_do_not_expose_repository_deletion() -> None:
    for profile in mcp.tool_profile_names():
        server = mcp.build_server(profile=profile)
        registered_tools = {tool.name for tool in asyncio.run(server.list_tools())}

        assert "codemesh_delete_repository" not in registered_tools


def test_print_tool_manifest_emits_contract_json(capsys: Any) -> None:
    asyncio.run(mcp.print_tool_manifest(profile="diagnostic"))

    payload = json.loads(capsys.readouterr().out)

    assert payload == mcp.tool_manifest(profile="diagnostic")
