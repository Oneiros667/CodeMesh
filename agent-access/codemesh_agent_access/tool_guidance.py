from __future__ import annotations

from typing import Any


_WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "check_freshness",
        "goal": "Check whether indexed context is current before trusting search results.",
        "use_when": [
            "starting work in a repository",
            "the user asks whether CodeMesh is up to date",
            "search results look stale or incomplete",
        ],
        "steps": [
            {
                "tool": "codemesh_list_repositories",
                "why": "Find the repository id or generated alias when it is not already known.",
            },
            {
                "tool": "codemesh_get_repository_status",
                "why": "Inspect latest ingestion run, counts, summary coverage, and git freshness.",
            },
            {
                "tool": "codemesh_list_ingestion_runs",
                "why": "Review recent indexing attempts when status reports failures or unknown freshness.",
            },
        ],
    },
    {
        "id": "find_implementation",
        "goal": "Find source code relevant to a task or behavior.",
        "use_when": [
            "locating implementation",
            "understanding a feature",
            "finding code by natural-language behavior",
        ],
        "steps": [
            {
                "tool": "codemesh_search_context",
                "why": "Search code, generated summaries, and indexed content for relevant nodes.",
            },
            {
                "tool": "codemesh_get_context_package",
                "why": "Package the best hits with snippets, summaries, relationships, and rationale for editing.",
            },
        ],
    },
    {
        "id": "find_symbol",
        "goal": "Find a known type, method, function, file, or symbol-like name.",
        "use_when": [
            "the task mentions a class, method, function, endpoint, or file name",
            "natural-language search is too broad",
            "a precise symbol name is available",
        ],
        "steps": [
            {
                "tool": "codemesh_search_symbols",
                "why": "Search indexed symbol names, ids, signatures, namespaces, and file paths.",
            },
            {
                "tool": "codemesh_get_node",
                "why": "Retrieve the selected symbol with optional content and immediate relationships.",
            },
        ],
    },
    {
        "id": "inspect_relationships",
        "goal": "Understand callers, callees, reads, writes, containment, or type-use relationships.",
        "use_when": [
            "checking blast radius",
            "finding callers or dependencies",
            "understanding how a node is connected",
            "before changing code with unknown callers",
        ],
        "steps": [
            {
                "tool": "codemesh_get_neighbors",
                "why": "Inspect graph relationships around a known node id.",
            },
            {
                "tool": "codemesh_get_context_package",
                "why": "Request grouped relationship context when the next step is code editing.",
            },
        ],
    },
    {
        "id": "prepare_agent_context",
        "goal": "Build context that can be pasted into or consumed by an AI coding agent.",
        "use_when": [
            "implementation work is likely",
            "the agent needs compact evidence",
            "multiple snippets and relationships should be combined",
        ],
        "steps": [
            {
                "tool": "codemesh_get_context_package",
                "why": "Return ranked snippets, summaries, relationship groups, repository metadata, and rationale.",
            },
        ],
    },
    {
        "id": "inspect_operations",
        "goal": "Check Agent Access and indexing operational state.",
        "use_when": [
            "MCP tools fail",
            "stores may be unavailable",
            "ingestion runs need investigation",
        ],
        "steps": [
            {
                "tool": "codemesh_status",
                "why": "Check Agent Access health and configured read endpoints.",
            },
            {
                "tool": "codemesh_list_ingestion_runs",
                "why": "Inspect recent ingestion runs and failures.",
            },
            {
                "tool": "codemesh_get_summary_coverage",
                "why": "Check generated summary coverage for an indexed repository.",
            },
        ],
    },
    {
        "id": "delete_indexed_repository",
        "goal": "Remove one repository from CodeMesh stores.",
        "use_when": [
            "the user explicitly asks to delete indexed repository data",
            "an indexed fixture or stale repository should be cleaned up",
        ],
        "steps": [
            {
                "tool": "codemesh_get_repository_status",
                "why": "Confirm the target repository id or alias before deleting.",
            },
            {
                "tool": "codemesh_delete_repository",
                "why": "Delete graph, content, vectors, summaries, and registry data. Requires confirm=true.",
            },
        ],
    },
]


def get_tool_guidance(task: str | None = None) -> dict[str, Any]:
    task_text = (task or "").strip()
    workflows = _rank_workflows(task_text)
    return {
        "task": task_text or None,
        "recommended_workflows": workflows,
        "available_tools": [
            "codemesh_status",
            "codemesh_search_context",
            "codemesh_get_context_package",
            "codemesh_search_symbols",
            "codemesh_get_node",
            "codemesh_get_neighbors",
            "codemesh_list_repositories",
            "codemesh_get_repository",
            "codemesh_get_repository_status",
            "codemesh_delete_repository",
            "codemesh_get_summary_coverage",
            "codemesh_list_ingestion_runs",
            "codemesh_get_tool_guidance",
        ],
        "default_start": [
            "codemesh_get_tool_guidance",
            "codemesh_list_repositories",
            "codemesh_get_repository_status",
        ],
    }


def _rank_workflows(task: str) -> list[dict[str, Any]]:
    if not task:
        return list(_WORKFLOWS)

    terms = {term for term in _normalize(task).split() if len(term) > 2}
    ranked = []
    for workflow in _WORKFLOWS:
        haystack = _normalize(
            " ".join(
                [
                    workflow["id"],
                    workflow["goal"],
                    " ".join(workflow["use_when"]),
                    " ".join(step["tool"] for step in workflow["steps"]),
                ]
            )
        )
        score = sum(1 for term in terms if term in haystack)
        if score:
            ranked.append((score, workflow))

    if not ranked:
        return list(_WORKFLOWS)

    return [
        workflow
        for _score, workflow in sorted(ranked, key=lambda item: item[0], reverse=True)
    ]


def _normalize(value: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else " " for character in value
    )
