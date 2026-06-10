from __future__ import annotations

import json
import sys
from typing import Any

from codemesh_agent_access import cli
from codemesh_agent_access.models import ToolResult


def test_package_cli_agent_output_mode(monkeypatch: Any, capsys: Any) -> None:
    async def fake_get_context_package(query: str, **kwargs: Any) -> ToolResult:
        return ToolResult(
            data={
                "query": {"query": query},
                "items": [
                    {
                        "hit": {
                            "node_id": "node:download",
                            "kind": "Method",
                            "file_path": "Downloader.cs",
                            "start_line": 10,
                            "end_line": 12,
                            "score": 0.9,
                        },
                        "node": {
                            "name": "DownloadAsync",
                            "span": {
                                "file_path": "Downloader.cs",
                                "start_line": 10,
                                "end_line": 12,
                            },
                        },
                        "relationship_groups": {},
                        "snippet": "return Task.CompletedTask;",
                        "rationale": {"rank": 1},
                    }
                ],
            }
        )

    monkeypatch.setattr(cli.tools, "get_context_package", fake_get_context_package)
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "package", "download", "--output", "agent"])

    cli.main()

    output = capsys.readouterr().out
    assert output.startswith("CodeMesh context package\n")
    assert "1. Method DownloadAsync" in output
    assert "return Task.CompletedTask;" in output


def test_search_cli_still_outputs_json(monkeypatch: Any, capsys: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_search_context(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(data={"query": query, "hits": []})

    monkeypatch.setattr(cli.tools, "search_context", fake_search_context)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "search",
            "download",
            "--filter",
            "project=Sample",
            "--filter",
            "kind=Method",
        ],
    )

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert captured["query"] == "download"
    assert captured["filters"] == {"project": "Sample", "kind": "Method"}
    assert payload["data"] == {"query": "download", "hits": []}


def test_symbols_cli_outputs_json(monkeypatch: Any, capsys: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_search_symbols(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(data={"query": {"query": query}, "symbols": []})

    monkeypatch.setattr(cli.tools, "search_symbols", fake_search_symbols)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "symbols",
            "DownloadAsync",
            "--repository-id",
            "sample_repo",
            "--kind",
            "Method",
            "--filter",
            "project=Sample",
            "--no-declarations",
        ],
    )

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert captured["query"] == "DownloadAsync"
    assert captured["repository_id"] == "sample_repo"
    assert captured["kinds"] == ["Method"]
    assert captured["filters"] == {"project": "Sample"}
    assert captured["include_declarations"] is False
    assert payload["data"] == {"query": {"query": "DownloadAsync"}, "symbols": []}


def test_package_cli_forwards_filters_and_repository_toggle(monkeypatch: Any, capsys: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_context_package(query: str, **kwargs: Any) -> ToolResult:
        captured["query"] = query
        captured.update(kwargs)
        return ToolResult(data={"query": {"query": query}, "items": []})

    monkeypatch.setattr(cli.tools, "get_context_package", fake_get_context_package)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "package",
            "download",
            "--filter",
            "filePath=Downloader.cs",
            "--no-repository",
        ],
    )

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert captured["query"] == "download"
    assert captured["filters"] == {"filePath": "Downloader.cs"}
    assert captured["include_repository"] is False
    assert payload["data"] == {"query": {"query": "download"}, "items": []}


def test_neighbors_cli_forwards_relationship_kinds(monkeypatch: Any, capsys: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_neighbors(node_id: str, **kwargs: Any) -> ToolResult:
        captured["node_id"] = node_id
        captured.update(kwargs)
        return ToolResult(data={"relationships": []})

    monkeypatch.setattr(cli.tools, "get_neighbors", fake_get_neighbors)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "neighbors",
            "node:download",
            "--relationship-kind",
            "Invokes",
            "--relationship-kind",
            "Reads",
        ],
    )

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert captured["node_id"] == "node:download"
    assert captured["relationship_kinds"] == ["Invokes", "Reads"]
    assert payload["data"] == {"relationships": []}


def test_summaries_cli_outputs_coverage_json(monkeypatch: Any, capsys: Any) -> None:
    captured: dict[str, Any] = {}

    async def fake_get_summary_coverage(repository_id: str) -> ToolResult:
        captured["repository_id"] = repository_id
        return ToolResult(data={"repository_id": repository_id, "completed_count": 4})

    monkeypatch.setattr(cli.tools, "get_summary_coverage", fake_get_summary_coverage)
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "summaries", "sample_repo"])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert captured["repository_id"] == "sample_repo"
    assert payload["data"] == {"repository_id": "sample_repo", "completed_count": 4}


def test_cli_prints_mcp_manifest(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "mcp-manifest"])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["service"] == "codemesh-agent-access"
    assert "codemesh_search_context" in {tool["name"] for tool in payload["tools"]}
    assert payload["contracts"]["codemesh_search_context"]["response"]["diagnostics"] == [
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


def test_cli_filter_requires_key_value_pair(monkeypatch: Any) -> None:
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "search", "download", "--filter", "broken"])

    try:
        cli.main()
    except SystemExit as exc:
        assert str(exc) == "Invalid --filter value 'broken'. Expected KEY=VALUE."
    else:
        raise AssertionError("Expected invalid filter to exit.")
