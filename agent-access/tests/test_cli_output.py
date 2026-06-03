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
    async def fake_search_context(query: str, **kwargs: Any) -> ToolResult:
        return ToolResult(data={"query": query, "hits": []})

    monkeypatch.setattr(cli.tools, "search_context", fake_search_context)
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "search", "download"])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
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
            "--no-declarations",
        ],
    )

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert captured["query"] == "DownloadAsync"
    assert captured["repository_id"] == "sample_repo"
    assert captured["kinds"] == ["Method"]
    assert captured["include_declarations"] is False
    assert payload["data"] == {"query": {"query": "DownloadAsync"}, "symbols": []}
