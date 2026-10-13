from __future__ import annotations

import asyncio
from collections import deque
from copy import deepcopy
from functools import wraps
import json
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Literal

from mcp.types import CallToolResult, TextContent, ToolAnnotations

from . import feedback, tools
from .binding import RepositoryBinding, bound_repository_reference
from .feedback_session import (
    CLIENT_PROFILE,
    CLIENT_TOOLS,
    FEEDBACK_PROFILES,
    MAINTAINER_PROFILE,
    MAINTAINER_TOOLS,
    SessionRuntime,
)
from .formatting import format_context_package_for_agent


DEFAULT_TOOL_PROFILE = "normal"

_TOOL_NAMES = [
    "codemesh_status",
    "codemesh_get_tool_guidance",
    "codemesh_search_context",
    "codemesh_get_context_package",
    "codemesh_search_symbols",
    "codemesh_get_node",
    "codemesh_get_neighbors",
    "codemesh_list_repositories",
    "codemesh_get_repository",
    "codemesh_get_repository_status",
    "codemesh_get_summary_coverage",
    "codemesh_list_ingestion_runs",
]

_NORMAL_TOOL_NAMES = [
    "codemesh_get_context_package",
    "codemesh_get_repository_status",
    "codemesh_list_repositories",
    "codemesh_get_node",
]

_TOOL_PROFILES: dict[str, list[str]] = {
    DEFAULT_TOOL_PROFILE: _NORMAL_TOOL_NAMES,
    "diagnostic": list(_TOOL_NAMES),
    CLIENT_PROFILE: list(CLIENT_TOOLS),
    MAINTAINER_PROFILE: list(MAINTAINER_TOOLS),
}

_MAX_MCP_AGENT_CHARACTERS = 12000

_SERVER_INSTRUCTIONS = (
    "Use CodeMesh first for source-grounded implementation discovery, likely "
    "change-impact analysis, and validation selection in indexed repositories. "
    "Start with one codemesh_get_context_package call using a concise task-shaped "
    "query, the repository id or alias, output_format='agent', and default limits. "
    "If that package covers every required facet, stop retrieving. Only when it "
    "leaves a specific implementation or test facet unresolved, issue one focused "
    "follow-up for that facet. Use at most three context packages for a task and "
    "avoid overlapping queries. Use the returned ranked "
    "file spans for targeted, batched checkout reads needed to verify citations "
    "instead of repeating broad repository exploration. The package "
    "checks the exact binding and freshness before search and fails closed when "
    "they are not accepted. If the repository is unknown, call "
    "codemesh_list_repositories. Use codemesh_get_repository_status only for "
    "explicit ingestion, count, or freshness diagnostics."
)

_CLIENT_FEEDBACK_INSTRUCTIONS = (
    " This is an explicitly enabled local development-feedback session. Use "
    "codemesh_get_feedback_session to inspect its bounds. When targeted source "
    "verification finds missing, stale, incorrect, or unhelpful CodeMesh output, "
    "use codemesh_record_feedback with a sanitized observation. Do not submit raw "
    "prompts, MCP payloads, source excerpts, credentials, secrets, or environment "
    "values. Recording feedback does not approve or schedule a CodeMesh change."
)

_MAINTAINER_FEEDBACK_INSTRUCTIONS = (
    " This is an explicitly enabled local feedback-maintainer session. Start with "
    "codemesh_list_feedback, investigate selected packets read-only, and use "
    "codemesh_prepare_feedback_resolution to create a stable proposal hash. Do not "
    "edit CodeMesh until a human approves the exact feedback ids and plan hash."
)

_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_RECORD_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)
_STRICT_ARGUMENT_TOOLS = {
    "codemesh_get_feedback_session",
    "codemesh_record_feedback",
    "codemesh_list_feedback",
    "codemesh_get_feedback",
    "codemesh_prepare_feedback_resolution",
}

_SEARCH_CONTEXT_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 8},
    "kinds": {"type": "string[]|null", "default": None},
    "filters": {"type": "object|null", "default": None},
    "vector": {"type": "number[]|null", "default": None},
    "expand_context": {"type": "boolean", "default": True},
    "context_depth": {"type": "integer", "default": 4},
    "include_context_relationships": {"type": "boolean", "default": False},
    "context_relationship_limit": {"type": "integer", "default": 8},
}

_TOOL_GUIDANCE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "task": {
        "type": "string|null",
        "default": None,
        "description": "Optional natural-language task to rank CodeMesh tool workflows.",
    },
}

_CONTEXT_PACKAGE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 8},
    "max_characters": {"type": "integer", "default": 12000},
    "kinds": {"type": "string[]|null", "default": None},
    "filters": {"type": "object|null", "default": None},
    "vector": {"type": "number[]|null", "default": None},
    "context_depth": {"type": "integer", "default": 4},
    "include_content": {"type": "boolean", "default": True},
    "include_relationships": {"type": "boolean", "default": True},
    "relationship_limit": {"type": "integer", "default": 8},
    "caller_limit": {"type": "integer|null", "default": None},
    "callee_limit": {"type": "integer|null", "default": None},
    "read_limit": {"type": "integer|null", "default": None},
    "write_limit": {"type": "integer|null", "default": None},
    "contains_limit": {"type": "integer|null", "default": None},
    "definition_limit": {"type": "integer|null", "default": None},
    "uses_type_limit": {"type": "integer|null", "default": None},
    "include_repository": {"type": "boolean", "default": True},
    "output_format": {"type": "string", "default": "json", "values": ["json", "agent"]},
}

_SYMBOL_SEARCH_ARGUMENTS: dict[str, dict[str, Any]] = {
    "query": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 20},
    "kinds": {"type": "string[]|null", "default": None},
    "filters": {"type": "object|null", "default": None},
    "include_declarations": {"type": "boolean", "default": True},
}

_NODE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "node_id": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "include_content": {"type": "boolean", "default": True},
    "include_neighbors": {"type": "boolean", "default": True},
}

_NEIGHBOR_ARGUMENTS: dict[str, dict[str, Any]] = {
    "node_id": {"type": "string", "required": True},
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "depth": {"type": "integer", "default": 1},
    "relationship_kinds": {"type": "string[]|null", "default": None},
}

_LIST_REPOSITORIES_ARGUMENTS: dict[str, dict[str, Any]] = {
    "limit": {"type": "integer", "default": 50},
}

_GET_REPOSITORY_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string",
        "required": True,
        "description": "Repository hash id or alias.",
    },
}

_GET_REPOSITORY_STATUS_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias; omit when the server is checkout-bound.",
    },
}

_SUMMARY_COVERAGE_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string",
        "required": True,
        "description": "Repository hash id or alias.",
    },
}

_LIST_RUNS_ARGUMENTS: dict[str, dict[str, Any]] = {
    "repository_id": {
        "type": "string|null",
        "default": None,
        "description": "Repository hash id or alias.",
    },
    "limit": {"type": "integer", "default": 50},
}

_RECORD_FEEDBACK_ARGUMENTS: dict[str, dict[str, Any]] = {
    "confidence": {
        "type": "string",
        "required": True,
        "values": ["low", "medium", "high"],
    },
    "task_family": {"type": "string", "required": True},
    "issue_category": {"type": "string", "required": True},
    "validation_outcome": {"type": "string", "required": True},
    "helpful_paths": {"type": "string[]|null", "default": None},
    "incorrect_paths": {"type": "string[]|null", "default": None},
    "missed_paths": {"type": "string[]|null", "default": None},
    "stale_paths": {"type": "string[]|null", "default": None},
    "ambiguous_paths": {"type": "string[]|null", "default": None},
    "fallback_reason": {"type": "string|null", "default": None},
    "minimal_reproduction": {"type": "string|null", "default": None},
    "expected_targets": {"type": "string[]|null", "default": None},
    "proposed_correction": {"type": "string|null", "default": None},
    "supersedes_feedback_ids": {"type": "string[]|null", "default": None},
}

_LIST_FEEDBACK_ARGUMENTS: dict[str, dict[str, Any]] = {
    "include_legacy": {"type": "boolean", "default": False},
    "state": {"type": "string|null", "default": None},
    "category": {"type": "string|null", "default": None},
    "task_family": {"type": "string|null", "default": None},
    "language": {"type": "string|null", "default": None},
    "reporter_role": {"type": "string|null", "default": None},
    "feedback_id": {"type": "string|null", "default": None},
    "offset": {"type": "integer", "default": 0},
    "limit": {"type": "integer", "default": 50},
}

_GET_FEEDBACK_ARGUMENTS: dict[str, dict[str, Any]] = {
    "feedback_id": {"type": "string", "required": True},
    "include_legacy": {"type": "boolean", "default": False},
}

_PREPARE_RESOLUTION_ARGUMENTS: dict[str, dict[str, Any]] = {
    "feedback_ids": {"type": "string[]", "required": True},
    "reproduction_state": {"type": "string", "required": True},
    "change_summary": {"type": "string", "required": True},
    "proposed_paths": {"type": "string[]", "required": True},
    "risks": {"type": "string[]|null", "default": None},
    "required_tests": {"type": "string[]|null", "default": None},
    "unresolved_questions": {"type": "string[]|null", "default": None},
    "include_legacy": {"type": "boolean", "default": False},
}

_RELATIONSHIP_GROUPS = [
    "callers",
    "callees",
    "reads",
    "writes",
    "contains",
    "defines",
    "uses_types",
]

_TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "codemesh_status": {
        "description": "Return CodeMesh Agent Access health and configured read endpoints.",
        "arguments": {},
    },
    "codemesh_get_tool_guidance": {
        "description": "Start here when deciding how CodeMesh can reduce repository exploration. Maps implementation discovery, change impact, validation selection, freshness, and symbol lookup to read-only workflows.",
        "arguments": _TOOL_GUIDANCE_ARGUMENTS,
        "response": {
            "fields": [
                "task",
                "recommended_workflows",
                "available_tools",
                "default_start",
            ],
        },
    },
    "codemesh_search_context": {
        "description": "Start here for broad source-grounded implementation discovery in an indexed repository. Rank relevant code and docs from natural-language task text before broad shell searches; use codemesh_get_context_package when relationships or validation are needed.",
        "arguments": _SEARCH_CONTEXT_ARGUMENTS,
        "response": {
            "diagnostics": [
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
            ],
        },
    },
    "codemesh_get_context_package": {
        "description": "Start here for implementation discovery, likely change-impact analysis, or validation selection in an indexed repository. Begin with one concise task-shaped query at default limits. If the package covers every required facet, stop retrieving; only issue one focused follow-up when a specific implementation or test facet remains unresolved. Use at most three context packages per task and avoid overlapping queries. Verifies the exact binding and freshness and fails closed before search. Returns ranked snippets, graph relationships, freshness metadata, and repository-scoped validation recommendations. Agent format is capped at 12,000 characters; verify returned file spans with targeted reads instead of duplicating broad repository exploration.",
        "arguments": _CONTEXT_PACKAGE_ARGUMENTS,
        "response": {
            "relationship_groups": list(_RELATIONSHIP_GROUPS),
            "fields": [
                "query",
                "repository",
                "latest_run",
                "items",
                "validation_recommendations",
                "total_snippet_characters",
                "generated_at",
            ],
            "output_formats": ["json", "agent"],
            "agent_content_type": "text",
            "agent_max_characters": _MAX_MCP_AGENT_CHARACTERS,
        },
    },
    "codemesh_search_symbols": {
        "description": "Use when a class, method, function, file, endpoint, or symbol-like name is known.",
        "arguments": _SYMBOL_SEARCH_ARGUMENTS,
    },
    "codemesh_get_node": {
        "description": "Use after search or symbol lookup when the exact node id is known and content or immediate relationships are needed.",
        "arguments": _NODE_ARGUMENTS,
    },
    "codemesh_get_neighbors": {
        "description": "Use for likely change-impact analysis around a known node. Inspect callers, callees, reads, writes, containment, and other indexed relationships.",
        "arguments": _NEIGHBOR_ARGUMENTS,
    },
    "codemesh_list_repositories": {
        "description": "Use first when the repository id or generated alias is unknown.",
        "arguments": _LIST_REPOSITORIES_ARGUMENTS,
    },
    "codemesh_get_repository": {
        "description": "Fetch one indexed CodeMesh repository by id or alias.",
        "arguments": _GET_REPOSITORY_ARGUMENTS,
    },
    "codemesh_get_repository_status": {
        "description": "Use for explicit counts, latest-ingestion, summary-coverage, or local-freshness diagnostics; it is not a required first step before context-package retrieval. If called, follow codemesh_next_action in the result: a fresh accepted binding continues to codemesh_get_context_package; any other state stops CodeMesh use.",
        "arguments": _GET_REPOSITORY_STATUS_ARGUMENTS,
        "response": {
            "fields": [
                "repository_id",
                "repository",
                "latest_run",
                "summary_coverage",
                "counts",
                "freshness",
                "refresh",
                "codemesh_next_action",
                "generated_at",
            ],
        },
    },
    "codemesh_get_summary_coverage": {
        "description": "Fetch generated node summary coverage for one indexed CodeMesh repository.",
        "arguments": _SUMMARY_COVERAGE_ARGUMENTS,
        "response": {
            "fields": [
                "repository_id",
                "total_count",
                "completed_count",
                "failed_count",
                "status_counts",
                "kind_counts",
                "provider_model_counts",
                "provider_model_count_details",
                "recent_failures",
                "generated_at",
            ],
        },
    },
    "codemesh_list_ingestion_runs": {
        "description": "List CodeMesh ingestion runs, optionally scoped to a repository id or alias.",
        "arguments": _LIST_RUNS_ARGUMENTS,
    },
    "codemesh_get_feedback_session": {
        "description": "Inspect the active local development-feedback session, bounds, expiry, and agent safety instructions.",
        "arguments": {},
    },
    "codemesh_record_feedback": {
        "description": "Record one sanitized, append-only local feedback packet with server-derived repository, snapshot, binding, session, and CodeMesh provenance. Human review remains required.",
        "arguments": _RECORD_FEEDBACK_ARGUMENTS,
    },
    "codemesh_list_feedback": {
        "description": "List validated feedback summaries only from client outboxes allowlisted by the active local development session.",
        "arguments": _LIST_FEEDBACK_ARGUMENTS,
    },
    "codemesh_get_feedback": {
        "description": "Get one validated feedback packet by exact id from an active-session allowlisted client outbox.",
        "arguments": _GET_FEEDBACK_ARGUMENTS,
    },
    "codemesh_prepare_feedback_resolution": {
        "description": "Validate and hash a read-only proposed CodeMesh resolution for exact feedback ids; this never records approval or edits source.",
        "arguments": _PREPARE_RESOLUTION_ARGUMENTS,
    },
}


def tool_profile_names() -> tuple[str, ...]:
    return tuple(_TOOL_PROFILES)


def _tool_names_for_profile(profile: str) -> list[str]:
    try:
        return _TOOL_PROFILES[profile]
    except KeyError as exc:
        supported = ", ".join(tool_profile_names())
        raise ValueError(
            f"Unknown MCP tool profile '{profile}'. Expected one of: {supported}."
        ) from exc


def _tool_annotations(name: str) -> ToolAnnotations:
    return (
        _RECORD_ANNOTATIONS
        if name == "codemesh_record_feedback"
        else _READ_ONLY_ANNOTATIONS
    )


def _filter_tool_guidance(
    payload: dict[str, Any], tool_names: set[str]
) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload

    data["available_tools"] = [
        name for name in data.get("available_tools", []) if name in tool_names
    ]
    data["default_start"] = [
        name for name in data.get("default_start", []) if name in tool_names
    ]
    data["recommended_workflows"] = [
        workflow
        for workflow in data.get("recommended_workflows", [])
        if all(step.get("tool") in tool_names for step in workflow.get("steps", []))
    ]
    return payload


def _server_instructions(
    binding: RepositoryBinding | None,
    profile: str = DEFAULT_TOOL_PROFILE,
) -> str:
    instructions = _SERVER_INSTRUCTIONS
    if profile == CLIENT_PROFILE:
        instructions += _CLIENT_FEEDBACK_INSTRUCTIONS
    elif profile == MAINTAINER_PROFILE:
        instructions += _MAINTAINER_FEEDBACK_INSTRUCTIONS
    if binding is None:
        return instructions
    return (
        f"{instructions} This server is bound to project "
        f"'{binding.project_id}', checkout '{binding.checkout_id}', and repository "
        f"root '{binding.repository_root}'. Repository-scoped calls default to this "
        "binding and cannot override it."
    )


def tool_manifest(
    profile: str = DEFAULT_TOOL_PROFILE,
    binding: RepositoryBinding | None = None,
) -> dict[str, Any]:
    """Return the stable MCP tool contract used by tests and fallback output."""
    tool_names = _tool_names_for_profile(profile)
    return {
        "service": "codemesh-agent-access",
        "protocol": "mcp",
        "profile": profile,
        "instructions": _server_instructions(binding, profile),
        "tools": [
            {
                "name": name,
                "description": _TOOL_CONTRACTS[name]["description"],
                "annotations": _tool_annotations(name).model_dump(
                    mode="json", exclude_none=True
                ),
            }
            for name in tool_names
        ],
        "contracts": {name: deepcopy(_TOOL_CONTRACTS[name]) for name in tool_names},
        "binding": binding.as_dict() if binding is not None else None,
    }


def build_server(
    profile: str = DEFAULT_TOOL_PROFILE,
    call_guard: Callable[[str, dict[str, Any]], None] | None = None,
    binding: RepositoryBinding | None = None,
    feedback_runtime: SessionRuntime | None = None,
    monotonic_clock: Callable[[], float] = monotonic,
) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The `mcp` package is required to run the CodeMesh MCP server."
        ) from exc

    tool_names = set(_tool_names_for_profile(profile))
    if profile in FEEDBACK_PROFILES:
        if binding is None or feedback_runtime is None:
            raise ValueError(
                "Development feedback MCP profiles require an explicit binding and "
                "validated session runtime."
            )
        if feedback_runtime.profile != profile or feedback_runtime.binding != binding:
            raise ValueError(
                "Development feedback runtime does not match the MCP profile."
            )
        feedback_runtime.assert_active()
    elif feedback_runtime is not None:
        raise ValueError("Feedback session runtime is not valid for this MCP profile.")
    server = FastMCP(
        "codemesh-agent-access",
        instructions=_server_instructions(binding, profile),
    )

    recent_tool_events: deque[dict[str, Any]] = deque(maxlen=32)
    request_times: deque[float] = deque()
    trace_sequence = 0
    latest_accepted_provenance: dict[str, Any] | None = None

    def register_tool(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(function: Callable[..., Any]) -> Callable[..., Any]:
            if name not in tool_names:
                return function

            @wraps(function)
            async def traced(*args: Any, **kwargs: Any) -> Any:
                nonlocal latest_accepted_provenance, trace_sequence
                try:
                    result = await function(*args, **kwargs)
                except BaseException:
                    if name in _NORMAL_TOOL_NAMES:
                        trace_sequence += 1
                        recent_tool_events.append(
                            {
                                "sequence": trace_sequence,
                                "tool": name,
                                "outcome": "failed",
                                "diagnostic_code": "tool_error",
                            }
                        )
                    raise
                if name in _NORMAL_TOOL_NAMES:
                    trace_sequence += 1
                    failed = bool(getattr(result, "isError", False))
                    if isinstance(result, dict) and result.get("ok") is False:
                        failed = True
                    recent_tool_events.append(
                        {
                            "sequence": trace_sequence,
                            "tool": name,
                            "outcome": "failed" if failed else "succeeded",
                            "diagnostic_code": "tool_error" if failed else None,
                        }
                    )
                    if not failed:
                        derived = _feedback_provenance_from_result(name, result)
                        if derived is not None:
                            latest_accepted_provenance = derived
                return result

            registered = server.tool(
                description=_TOOL_CONTRACTS[name]["description"],
                annotations=_tool_annotations(name),
            )(traced)
            if name in _STRICT_ARGUMENT_TOOLS:
                registered_tool = server._tool_manager.get_tool(name)
                assert registered_tool is not None
                argument_model = registered_tool.fn_metadata.arg_model
                argument_model.model_config["extra"] = "forbid"
                argument_model.model_rebuild(force=True)
                registered_tool.parameters = argument_model.model_json_schema(
                    by_alias=True
                )
            return registered

        return register

    def check(name: str, arguments: dict[str, Any]) -> None:
        if call_guard is not None:
            call_guard(name, arguments)

    def check_feedback_rate() -> None:
        assert feedback_runtime is not None
        bounds = feedback_runtime.assert_active().bounds
        current = monotonic_clock()
        while request_times and current - request_times[0] >= 60:
            request_times.popleft()
        if len(request_times) >= bounds.max_requests_per_minute:
            raise ValueError(
                "Development feedback request-rate limit has been reached."
            )
        request_times.append(current)

    def repository_reference(
        repository_id: str | None,
        *,
        required_when_unbound: bool = False,
    ) -> str | None:
        return bound_repository_reference(
            binding,
            repository_id,
            required_when_unbound=required_when_unbound,
        )

    @register_tool("codemesh_status")
    async def codemesh_status() -> dict[str, Any]:
        """Return CodeMesh Agent Access health and configured read endpoints."""
        check("codemesh_status", {})
        return (await tools.status()).model_dump(mode="json")

    @register_tool("codemesh_get_tool_guidance")
    async def codemesh_get_tool_guidance(task: str | None = None) -> dict[str, Any]:
        """Recommend which CodeMesh MCP tools to use for a natural-language agent task."""
        check("codemesh_get_tool_guidance", {"task": task})
        payload = (await tools.tool_guidance(task=task)).model_dump(mode="json")
        return _filter_tool_guidance(payload, tool_names)

    @register_tool("codemesh_search_context")
    async def codemesh_search_context(
        query: str,
        repository_id: str | None = None,
        limit: int = 8,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        vector: list[float] | None = None,
        expand_context: bool = True,
        context_depth: int = 4,
        include_context_relationships: bool = False,
        context_relationship_limit: int = 8,
    ) -> dict[str, Any]:
        """Search CodeMesh context for code relevant to an agent task."""
        repository_id = repository_reference(repository_id)
        check(
            "codemesh_search_context",
            {"query": query, "repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.search_context(
                query,
                repository_id=repository_id,
                limit=limit,
                kinds=kinds,
                filters=filters,
                vector=vector,
                expand_context=expand_context,
                context_depth=context_depth,
                include_context_relationships=include_context_relationships,
                context_relationship_limit=context_relationship_limit,
            )
        ).model_dump(mode="json")

    @register_tool("codemesh_get_context_package")
    async def codemesh_get_context_package(
        query: str,
        repository_id: str | None = None,
        limit: int = 8,
        max_characters: int = 12000,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        vector: list[float] | None = None,
        context_depth: int = 4,
        include_content: bool = True,
        include_relationships: bool = True,
        relationship_limit: int = 8,
        caller_limit: int | None = None,
        callee_limit: int | None = None,
        read_limit: int | None = None,
        write_limit: int | None = None,
        contains_limit: int | None = None,
        definition_limit: int | None = None,
        uses_type_limit: int | None = None,
        include_repository: bool = True,
        output_format: Literal["json", "agent"] = "json",
    ) -> CallToolResult:
        """Build an agent-ready context package with snippets, relationships, and repository metadata."""
        nonlocal latest_accepted_provenance
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=profile == DEFAULT_TOOL_PROFILE,
        )
        check(
            "codemesh_get_context_package",
            {"query": query, "repository_id": repository_id, "limit": limit},
        )
        result = await tools.get_context_package(
            query,
            repository_id=repository_id,
            limit=limit,
            max_characters=max_characters,
            kinds=kinds,
            filters=filters,
            vector=vector,
            context_depth=context_depth,
            include_content=include_content,
            include_relationships=include_relationships,
            relationship_limit=relationship_limit,
            caller_limit=caller_limit,
            callee_limit=callee_limit,
            read_limit=read_limit,
            write_limit=write_limit,
            contains_limit=contains_limit,
            definition_limit=definition_limit,
            uses_type_limit=uses_type_limit,
            include_repository=include_repository,
            binding=binding,
        )
        if result.ok and isinstance(result.data, dict):
            derived = _feedback_provenance_from_data(
                result.data,
                accepted=True,
            )
            if derived is not None:
                latest_accepted_provenance = derived
        if output_format == "agent":
            text = (
                format_context_package_for_agent(
                    result.data,
                    max_characters=min(max_characters, _MAX_MCP_AGENT_CHARACTERS),
                )
                if result.ok
                else result.error or "CodeMesh context package request failed."
            )
            return CallToolResult(
                content=[TextContent(type="text", text=text)],
                isError=not result.ok,
            )

        payload = result.model_dump(mode="json")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload))],
            structuredContent=payload,
            isError=not result.ok,
        )

    @register_tool("codemesh_search_symbols")
    async def codemesh_search_symbols(
        query: str,
        repository_id: str | None = None,
        limit: int = 20,
        kinds: list[str] | None = None,
        filters: dict[str, str] | None = None,
        include_declarations: bool = True,
    ) -> dict[str, Any]:
        """Search indexed CodeMesh symbols by name, id, display signature, namespace, or file path."""
        repository_id = repository_reference(repository_id)
        check(
            "codemesh_search_symbols",
            {"query": query, "repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.search_symbols(
                query,
                repository_id=repository_id,
                limit=limit,
                kinds=kinds,
                filters=filters,
                include_declarations=include_declarations,
            )
        ).model_dump(mode="json")

    @register_tool("codemesh_get_node")
    async def codemesh_get_node(
        node_id: str,
        repository_id: str | None = None,
        include_content: bool = True,
        include_neighbors: bool = True,
    ) -> dict[str, Any]:
        """Fetch a CodeMesh node with optional content and immediate relationships."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=profile == DEFAULT_TOOL_PROFILE,
        )
        check(
            "codemesh_get_node",
            {"node_id": node_id, "repository_id": repository_id},
        )
        return (
            await tools.get_node(
                node_id,
                repository_id=repository_id,
                include_content=include_content,
                include_neighbors=include_neighbors,
                binding=binding,
            )
        ).model_dump(mode="json")

    @register_tool("codemesh_get_neighbors")
    async def codemesh_get_neighbors(
        node_id: str,
        repository_id: str | None = None,
        depth: int = 1,
        relationship_kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch relationships around a CodeMesh node."""
        repository_id = repository_reference(repository_id)
        check(
            "codemesh_get_neighbors",
            {"node_id": node_id, "repository_id": repository_id, "depth": depth},
        )
        return (
            await tools.get_neighbors(
                node_id,
                repository_id=repository_id,
                depth=depth,
                relationship_kinds=relationship_kinds,
            )
        ).model_dump(mode="json")

    @register_tool("codemesh_list_repositories")
    async def codemesh_list_repositories(limit: int = 50) -> dict[str, Any]:
        """List repositories indexed by CodeMesh."""
        check("codemesh_list_repositories", {"limit": limit})
        return (await tools.list_repositories(limit=limit, binding=binding)).model_dump(
            mode="json"
        )

    @register_tool("codemesh_get_repository")
    async def codemesh_get_repository(repository_id: str) -> dict[str, Any]:
        """Fetch one indexed CodeMesh repository by id."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=True,
        )
        assert repository_id is not None
        check("codemesh_get_repository", {"repository_id": repository_id})
        return (await tools.get_repository(repository_id)).model_dump(mode="json")

    @register_tool("codemesh_get_repository_status")
    async def codemesh_get_repository_status(
        repository_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch repository status, counts, latest run, summary coverage, and freshness diagnostics."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=True,
        )
        assert repository_id is not None
        check("codemesh_get_repository_status", {"repository_id": repository_id})
        payload = (
            await tools.get_repository_status(repository_id, binding=binding)
        ).model_dump(mode="json")
        status = payload.get("data")
        status = status if isinstance(status, dict) else {}
        status["codemesh_next_action"] = _repository_status_next_action(status)
        return payload

    @register_tool("codemesh_get_summary_coverage")
    async def codemesh_get_summary_coverage(repository_id: str) -> dict[str, Any]:
        """Fetch generated node summary coverage for one indexed CodeMesh repository."""
        repository_id = repository_reference(
            repository_id,
            required_when_unbound=True,
        )
        assert repository_id is not None
        check("codemesh_get_summary_coverage", {"repository_id": repository_id})
        return (await tools.get_summary_coverage(repository_id)).model_dump(mode="json")

    @register_tool("codemesh_list_ingestion_runs")
    async def codemesh_list_ingestion_runs(
        repository_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List CodeMesh ingestion runs, optionally scoped to a repository."""
        repository_id = repository_reference(repository_id)
        check(
            "codemesh_list_ingestion_runs",
            {"repository_id": repository_id, "limit": limit},
        )
        return (
            await tools.list_ingestion_runs(repository_id=repository_id, limit=limit)
        ).model_dump(mode="json")

    @register_tool("codemesh_get_feedback_session")
    async def codemesh_get_feedback_session() -> dict[str, Any]:
        """Inspect the active local development-feedback session and its bounds."""
        check("codemesh_get_feedback_session", {})
        check_feedback_rate()
        assert feedback_runtime is not None
        payload = feedback_runtime.assert_active()
        return {
            "schema_version": "codemesh-feedback-session-discovery/v1",
            "session_id": payload.session_id,
            "enabled": True,
            "expires_at": payload.expires_at.isoformat(),
            "local_only": payload.local_only,
            "provider_free": payload.provider_free,
            "profile": profile,
            "allowed_categories": [
                "setup",
                "binding",
                "freshness",
                "missing-language",
                "missing-relationship",
                "ranking",
                "budget",
                "validation",
                "other",
            ],
            "bounds": payload.bounds.model_dump(mode="json"),
            "instructions": (
                "Record only sanitized observations after targeted source verification. "
                "Do not include raw prompts, MCP payloads, source excerpts, secrets, "
                "credentials, or environment values. Human review is required."
            ),
        }

    @register_tool("codemesh_record_feedback")
    async def codemesh_record_feedback(
        confidence: Literal["low", "medium", "high"],
        task_family: str,
        issue_category: Literal[
            "setup",
            "binding",
            "freshness",
            "missing-language",
            "missing-relationship",
            "ranking",
            "budget",
            "validation",
            "other",
        ],
        validation_outcome: Literal["passed", "failed", "not-run", "inconclusive"],
        helpful_paths: list[str] | None = None,
        incorrect_paths: list[str] | None = None,
        missed_paths: list[str] | None = None,
        stale_paths: list[str] | None = None,
        ambiguous_paths: list[str] | None = None,
        fallback_reason: str | None = None,
        minimal_reproduction: str | None = None,
        expected_targets: list[str] | None = None,
        proposed_correction: str | None = None,
        supersedes_feedback_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record one sanitized local feedback packet with server-derived provenance."""
        arguments = {
            "confidence": confidence,
            "task_family": task_family,
            "issue_category": issue_category,
            "validation_outcome": validation_outcome,
        }
        check("codemesh_record_feedback", arguments)
        check_feedback_rate()
        assert feedback_runtime is not None and binding is not None
        if issue_category in {"setup", "binding", "freshness"}:
            provenance = {
                "status": "unavailable",
                "diagnostic_code": f"{issue_category}_reported_before_context_acceptance",
            }
        else:
            provenance = latest_accepted_provenance or {
                "status": "unavailable",
                "diagnostic_code": "no_accepted_context_provenance",
            }
        packet, output = feedback.record_development_feedback(
            runtime=feedback_runtime,
            confidence=confidence,
            task_family=task_family,
            issue_category=issue_category,
            validation_outcome=validation_outcome,
            provenance=provenance,
            recent_tool_events=list(recent_tool_events),
            helpful_paths=helpful_paths,
            incorrect_paths=incorrect_paths,
            missed_paths=missed_paths,
            stale_paths=stale_paths,
            ambiguous_paths=ambiguous_paths,
            fallback_reason=fallback_reason,
            minimal_reproduction=minimal_reproduction,
            expected_targets=expected_targets,
            proposed_correction=proposed_correction,
            supersedes_feedback_ids=supersedes_feedback_ids,
        )
        return {
            "recorded": True,
            "feedback_id": packet.feedback_id,
            "packet_path": output.relative_to(Path(binding.repository_root)).as_posix(),
            "local_only": True,
            "human_review_required": True,
        }

    @register_tool("codemesh_list_feedback")
    async def codemesh_list_feedback(
        include_legacy: bool = False,
        state: Literal["open", "resolved", "verified"] | None = None,
        category: Literal[
            "setup",
            "binding",
            "freshness",
            "missing-language",
            "missing-relationship",
            "ranking",
            "budget",
            "validation",
            "other",
        ]
        | None = None,
        task_family: str | None = None,
        language: str | None = None,
        reporter_role: str | None = None,
        feedback_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List validated feedback from active-session allowlisted outboxes."""
        check("codemesh_list_feedback", {"offset": offset, "limit": limit})
        check_feedback_rate()
        assert feedback_runtime is not None
        return feedback.list_session_feedback(
            feedback_runtime,
            include_legacy=include_legacy,
            state=state,
            category=category,
            task_family=task_family,
            language=language,
            reporter_role=reporter_role,
            feedback_id=feedback_id,
            offset=offset,
            limit=limit,
        )

    @register_tool("codemesh_get_feedback")
    async def codemesh_get_feedback(
        feedback_id: str,
        include_legacy: bool = False,
    ) -> dict[str, Any]:
        """Get one exact validated packet from an allowlisted client outbox."""
        check("codemesh_get_feedback", {"feedback_id": feedback_id})
        check_feedback_rate()
        assert feedback_runtime is not None
        return feedback.get_session_feedback(
            feedback_runtime,
            feedback_id,
            include_legacy=include_legacy,
        )

    @register_tool("codemesh_prepare_feedback_resolution")
    async def codemesh_prepare_feedback_resolution(
        feedback_ids: list[str],
        reproduction_state: Literal["reproduced", "not-reproduced", "blocked"],
        change_summary: str,
        proposed_paths: list[str],
        risks: list[str] | None = None,
        required_tests: list[str] | None = None,
        unresolved_questions: list[str] | None = None,
        include_legacy: bool = False,
    ) -> dict[str, Any]:
        """Validate and hash a non-authorizing proposed feedback resolution."""
        check(
            "codemesh_prepare_feedback_resolution",
            {"feedback_ids": feedback_ids, "reproduction_state": reproduction_state},
        )
        check_feedback_rate()
        assert feedback_runtime is not None
        return feedback.prepare_feedback_resolution(
            feedback_runtime,
            feedback_ids=feedback_ids,
            reproduction_state=reproduction_state,
            change_summary=change_summary,
            proposed_paths=proposed_paths,
            risks=risks,
            required_tests=required_tests,
            unresolved_questions=unresolved_questions,
            include_legacy=include_legacy,
        )

    return server


def _feedback_provenance_from_result(
    tool_name: str,
    result: Any,
) -> dict[str, Any] | None:
    if tool_name not in {
        "codemesh_get_repository_status",
        "codemesh_get_context_package",
    }:
        return None
    if isinstance(result, dict):
        payload = result
    else:
        payload = getattr(result, "structuredContent", None)
    if not isinstance(payload, dict) or payload.get("ok") is False:
        return None
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return None
    return _feedback_provenance_from_data(
        data,
        accepted=(
            tool_name == "codemesh_get_context_package"
            or _status_payload_is_accepted(data)
        ),
    )


def _status_payload_is_accepted(data: dict[str, Any]) -> bool:
    freshness = data.get("freshness")
    freshness = freshness if isinstance(freshness, dict) else {}
    assessment = freshness.get("binding")
    assessment = assessment if isinstance(assessment, dict) else {}
    return (
        freshness.get("status") == "fresh"
        and freshness.get("is_stale") is False
        and assessment.get("status") == "accepted"
    )


def _feedback_provenance_from_data(
    data: dict[str, Any],
    *,
    accepted: bool,
) -> dict[str, Any] | None:
    repository = data.get("repository")
    repository = repository if isinstance(repository, dict) else {}
    latest_run = data.get("latest_run")
    latest_run = latest_run if isinstance(latest_run, dict) else {}
    snapshot_id = repository.get("snapshot_id")
    language = latest_run.get("language")
    languages = (
        sorted(
            {
                item.strip().casefold()
                for item in str(language or "").split(",")
                if item.strip()
            }
        )
        if language
        else []
    )
    parser_profile = latest_run.get("parser_name")
    if not accepted or not snapshot_id or not languages or not parser_profile:
        return None
    return {
        "status": "accepted",
        "snapshot_id": snapshot_id,
        "languages": languages,
        "parser_profile": parser_profile,
    }


def _repository_status_next_action(payload: dict[str, Any]) -> dict[str, Any]:
    freshness = payload.get("freshness")
    freshness = freshness if isinstance(freshness, dict) else {}
    binding = freshness.get("binding")
    binding = binding if isinstance(binding, dict) else {}
    eligible = (
        freshness.get("status") == "fresh" and binding.get("status") == "accepted"
    )
    if eligible:
        return {
            "use_codemesh": True,
            "next_tool": "codemesh_get_context_package",
            "instruction": (
                "Binding is accepted and the index is fresh. Continue now with "
                "one codemesh_get_context_package call using a concise task-shaped "
                "query, output_format='agent', and default limits. Stop retrieving "
                "when it covers every required facet. Only issue a focused "
                "follow-up for a specific unresolved implementation or test facet; "
                "use at most three packages and avoid overlapping queries."
            ),
        }

    return {
        "use_codemesh": False,
        "next_tool": None,
        "instruction": (
            "Do not use CodeMesh context for this task because the exact binding "
            "is not both accepted and fresh. Fall back to direct source inspection."
        ),
    }


def run(
    profile: str = DEFAULT_TOOL_PROFILE,
    binding: RepositoryBinding | None = None,
    feedback_runtime: SessionRuntime | None = None,
) -> None:
    if profile == DEFAULT_TOOL_PROFILE and binding is None:
        raise ValueError(
            "The normal MCP profile requires an explicit project, checkout, and "
            "repository-root binding."
        )
    if profile in FEEDBACK_PROFILES and binding is None:
        raise ValueError(
            "Development feedback MCP profiles require an explicit project, "
            "checkout, and repository-root binding."
        )
    server = build_server(
        profile=profile,
        binding=binding,
        feedback_runtime=feedback_runtime,
    )
    server.run()


async def print_tool_manifest(profile: str = DEFAULT_TOOL_PROFILE) -> None:
    print(json.dumps(tool_manifest(profile=profile), indent=2))


if __name__ == "__main__":
    try:
        run()
    except RuntimeError:
        asyncio.run(print_tool_manifest())
