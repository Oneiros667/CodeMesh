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
                    "stable_key": "Sample.Downloader.DownloadAsync",
                    "kind": "Method",
                    "file_path": "Downloader.cs",
                    "start_line": 10,
                    "end_line": 24,
                    "score": 0.81234,
                    "repository_id": "repo:test",
                    "content_hash": "method-body",
                    "score_components": {
                        "vector_score": 0.7,
                        "kind_weight": 0.1,
                    },
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
                "summary": {
                    "summary": "Downloads subtitles for a video URL.",
                    "provider": "test",
                    "model": "summary-counting",
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
                    "expanded": True,
                    "score_components": {
                        "vector_score": 0.7,
                        "kind_weight": 0.1,
                    },
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
    assert "Stable key: Sample.Downloader.DownloadAsync" in text
    assert "Repository ID: repo:test" in text
    assert "Score: 0.812; rank 1" in text
    assert "Content hash: method-body" in text
    assert "Rationale: expanded=true; score_components[kind_weight=0.100, vector_score=0.700]" in text
    assert "Summary: Downloads subtitles for a video URL." in text
    assert "Callers: Main (Method, in, Program.cs:8-16)" in text
    assert "Callees: Normalize (Method, out, Downloader.cs:26-28)" in text
    assert "public Task DownloadAsync(string url)" in text
    assert text.index("Snippet:") < text.index("Relationships:")


def test_format_context_package_for_agent_handles_empty_packages() -> None:
    text = format_context_package_for_agent({"query": {"query": "missing"}, "items": []})

    assert text == "CodeMesh context package\nQuery: missing\nItems: 0"


def test_format_context_package_for_agent_applies_character_budget() -> None:
    package = {
        "query": {"query": "download"},
        "items": [
            {
                "hit": {
                    "node_id": "node:download",
                    "stable_key": "node:download",
                    "kind": "Method",
                    "file_path": "Downloader.cs",
                    "start_line": 10,
                    "end_line": 20,
                    "score": 0.9,
                    "repository_id": "repo:test",
                    "content_hash": "content:download",
                },
                "snippet": "x" * 400,
                "rationale": {"rank": 1},
            }
        ],
    }

    text = format_context_package_for_agent(package, max_characters=360)

    assert len(text) <= 360
    assert text.endswith("[truncated to 360 characters]")
    assert "Repository ID: repo:test" in text
    assert "Content hash: content:download" in text
