from __future__ import annotations

from codemesh_agent_access.formatting import format_context_package_for_agent


def test_format_context_package_for_agent_emits_compact_brief() -> None:
    package = {
        "query": {"query": "download video subtitles"},
        "repository": {
            "repository_id": "repo:test",
            "root_path": "C:/sample",
        },
        "latest_run": {
            "run_id": "run:test",
            "stage": "Completed",
        },
        "items": [
            {
                "hit": {
                    "node_id": "csharp:method:Sample.Downloader.DownloadAsync(System.String)",
                    "kind": "Method",
                    "file_path": "Downloader.cs",
                    "start_line": 10,
                    "end_line": 24,
                    "score": 0.81234,
                },
                "node": {
                    "id": "csharp:method:Sample.Downloader.DownloadAsync(System.String)",
                    "kind": "Method",
                    "name": "DownloadAsync",
                    "span": {
                        "file_path": "Downloader.cs",
                        "start_line": 10,
                        "end_line": 24,
                    },
                },
                "content": {
                    "hash": "method-body",
                },
                "relationship_groups": {
                    "callers": [
                        {
                            "direction": "in",
                            "other": {
                                "kind": "Method",
                                "name": "Main",
                                "file_path": "Program.cs",
                                "start_line": 8,
                                "end_line": 16,
                            },
                        }
                    ],
                    "callees": [
                        {
                            "direction": "out",
                            "other": {
                                "kind": "Method",
                                "name": "Normalize",
                                "file_path": "Downloader.cs",
                                "start_line": 26,
                                "end_line": 28,
                            },
                        }
                    ],
                    "reads": [],
                    "writes": [],
                    "contains": [],
                    "defines": [],
                    "uses_types": [],
                },
                "snippet": "public Task DownloadAsync(string url)\n{\n    return Task.CompletedTask;\n}",
                "rationale": {
                    "rank": 1,
                },
            }
        ],
    }

    text = format_context_package_for_agent(package)

    assert "CodeMesh context package" in text
    assert "Query: download video subtitles" in text
    assert "Repository: repo:test (C:/sample)" in text
    assert "1. Method DownloadAsync" in text
    assert "File: Downloader.cs:10-24" in text
    assert "Score: 0.812; rank 1" in text
    assert "Content hash: method-body" in text
    assert "Callers: Main (Method, in, Program.cs:8-16)" in text
    assert "Callees: Normalize (Method, out, Downloader.cs:26-28)" in text
    assert "public Task DownloadAsync(string url)" in text


def test_format_context_package_for_agent_handles_empty_packages() -> None:
    text = format_context_package_for_agent({"query": {"query": "missing"}, "items": []})

    assert text == "CodeMesh context package\nQuery: missing\nItems: 0"
