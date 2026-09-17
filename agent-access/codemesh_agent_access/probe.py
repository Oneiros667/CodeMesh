from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .feedback_session import CLIENT_PROFILE, FEEDBACK_PROFILES, inspect_session
from .installer import InstallationPlan, verify_plan_applied


class RuntimeProbeError(RuntimeError):
    """Raised when the configured MCP process fails a required live gate."""


async def run_feedback_runtime_probe(
    plan: InstallationPlan,
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    verify_plan_applied(plan)
    if plan.profile not in FEEDBACK_PROFILES or plan.session is None:
        raise RuntimeProbeError(
            "The feedback runtime probe requires a pinned feedback installation plan."
        )
    manifest_path = plan.session["manifest_path"]
    manifest_hash = plan.session["manifest_file_sha256"]
    session_status = inspect_session(manifest_path, manifest_hash)
    if session_status["status"] != "active":
        raise RuntimeProbeError(
            "The reviewed development feedback session is not active."
        )
    launch = plan.launch
    expected_tools = sorted(str(value) for value in launch["expected_tools"])
    _require_launch_value(launch["args"], "--feedback-session", manifest_path)
    _require_launch_value(
        launch["args"],
        "--feedback-session-sha256",
        manifest_hash,
    )
    parameters = StdioServerParameters(
        command=str(launch["command"]),
        args=[str(value) for value in launch["args"]],
        cwd=Path(str(launch["cwd"])),
        env={**os.environ, "CODEMESH_MODEL_PROVIDER": "none"},
    )
    timeout = timedelta(seconds=timeout_seconds)
    started = perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialized = await session.initialize()
                    instructions = initialized.instructions or ""
                    _require_instruction_binding(instructions, plan.binding)
                    if "explicitly enabled local" not in instructions:
                        raise RuntimeProbeError(
                            "Feedback MCP instructions do not advertise the active session."
                        )
                    listed = await session.list_tools()
                    actual_tools = sorted(tool.name for tool in listed.tools)
                    if actual_tools != expected_tools:
                        raise RuntimeProbeError(
                            "Feedback MCP tool surface differs from the reviewed plan."
                        )
                    if plan.profile == CLIENT_PROFILE:
                        payload = _tool_payload(
                            await session.call_tool(
                                "codemesh_get_feedback_session",
                                arguments={},
                                read_timeout_seconds=timeout,
                            )
                        )
                        if (
                            payload.get("enabled") is not True
                            or payload.get("session_id") != session_status["session_id"]
                            or payload.get("local_only") is not True
                        ):
                            raise RuntimeProbeError(
                                "Feedback session discovery differs from the reviewed session."
                            )
                    else:
                        payload = _tool_payload(
                            await session.call_tool(
                                "codemesh_list_feedback",
                                arguments={"limit": 1},
                                read_timeout_seconds=timeout,
                            )
                        )
                        if payload.get("session_id") != session_status["session_id"]:
                            raise RuntimeProbeError(
                                "Maintainer feedback intake differs from the reviewed session."
                            )
    except RuntimeProbeError:
        raise
    except TimeoutError as exc:
        raise RuntimeProbeError(
            f"CodeMesh feedback runtime probe exceeded {timeout_seconds} seconds."
        ) from exc
    except Exception as exc:
        nested = _nested_probe_error(exc)
        if nested is not None:
            raise nested from exc
        raise RuntimeProbeError(
            "Could not start or verify the configured feedback MCP process: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    return {
        "schema_version": "codemesh-feedback-runtime-probe-v1",
        "passed": True,
        "provider_mode": "none",
        "profile": plan.profile,
        "server_name": plan.server_name,
        "session_id": session_status["session_id"],
        "manifest_file_sha256": manifest_hash,
        "project_id": plan.binding.get("project_id"),
        "checkout_id": plan.binding.get("checkout_id"),
        "repository_root": plan.binding.get("repository_root"),
        "tools": expected_tools,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


async def run_runtime_probe(
    plan: InstallationPlan,
    *,
    timeout_seconds: int = 30,
    query: str = "repository implementation entry points",
    expected_paths: list[str] | None = None,
) -> dict[str, Any]:
    verify_plan_applied(plan)
    if plan.profile != "normal":
        raise RuntimeProbeError(
            "The product runtime probe requires the normal profile."
        )
    launch = plan.launch
    binding = plan.binding
    expected_tools = sorted(str(value) for value in launch["expected_tools"])
    parameters = StdioServerParameters(
        command=str(launch["command"]),
        args=[str(value) for value in launch["args"]],
        cwd=Path(str(launch["cwd"])),
        env={**os.environ, "CODEMESH_MODEL_PROVIDER": "none"},
    )
    timeout = timedelta(seconds=timeout_seconds)
    started = perf_counter()

    try:
        async with asyncio.timeout(timeout_seconds):
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialized = await session.initialize()
                    instructions = initialized.instructions or ""
                    _require_instruction_binding(instructions, binding)

                    listed = await session.list_tools()
                    actual_tools = sorted(tool.name for tool in listed.tools)
                    if actual_tools != expected_tools:
                        raise RuntimeProbeError(
                            "Configured MCP tool surface differs from the reviewed plan: "
                            f"expected {expected_tools}, got {actual_tools}."
                        )

                    repositories = _tool_payload(
                        await session.call_tool(
                            "codemesh_list_repositories",
                            arguments={"limit": 10},
                            read_timeout_seconds=timeout,
                        )
                    )
                    _require_bound_repository(repositories, binding)

                    status = _tool_payload(
                        await session.call_tool(
                            "codemesh_get_repository_status",
                            arguments={},
                            read_timeout_seconds=timeout,
                        )
                    )
                    status_data = _data(status)
                    _require_fresh_status(status_data, binding)

                    package = await session.call_tool(
                        "codemesh_get_context_package",
                        arguments={
                            "query": query,
                            "max_characters": 4000,
                            "include_content": False,
                            "include_relationships": True,
                            "output_format": "json",
                        },
                        read_timeout_seconds=timeout,
                    )
                    if package.isError:
                        raise RuntimeProbeError(
                            "The bound context-package call returned an MCP error."
                        )
                    package_data = _data(_tool_payload(package))
                    items = package_data.get("items") or []
                    if not items:
                        raise RuntimeProbeError(
                            "The bound context-package probe returned no context items."
                        )
                    returned_paths = sorted(
                        {
                            path
                            for item in items
                            if isinstance(item, dict)
                            for path in [_context_item_path(item)]
                            if path
                        }
                    )
                    missing_paths = sorted(
                        set(expected_paths or []) - set(returned_paths)
                    )
                    if missing_paths:
                        raise RuntimeProbeError(
                            "The bound context-package probe missed expected path(s): "
                            + ", ".join(missing_paths)
                            + f". Returned: {', '.join(returned_paths)}"
                        )
    except RuntimeProbeError:
        raise
    except TimeoutError as exc:
        raise RuntimeProbeError(
            f"CodeMesh MCP runtime probe exceeded {timeout_seconds} seconds."
        ) from exc
    except Exception as exc:
        nested = _nested_probe_error(exc)
        if nested is not None:
            raise nested from exc
        raise RuntimeProbeError(
            "Could not start or verify the configured CodeMesh MCP process: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    freshness = status_data.get("freshness") or {}
    repository = status_data.get("repository") or {}
    return {
        "schema_version": "codemesh-runtime-probe-v1",
        "passed": True,
        "provider_mode": "none",
        "profile": plan.profile,
        "server_name": plan.server_name,
        "project_id": binding.get("project_id"),
        "checkout_id": binding.get("checkout_id"),
        "repository_root": binding.get("repository_root"),
        "snapshot_id": repository.get("snapshot_id"),
        "source_view_hash": repository.get("source_view_hash"),
        "indexed_commit": freshness.get("indexed_commit"),
        "current_commit": freshness.get("current_commit"),
        "freshness_status": freshness.get("status"),
        "binding_status": (freshness.get("binding") or {}).get("status"),
        "tools": expected_tools,
        "context_query": query,
        "context_item_count": len(items),
        "returned_paths": returned_paths,
        "expected_paths": sorted(expected_paths or []),
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


async def run_runtime_rejection_probe(
    plan: InstallationPlan,
    *,
    timeout_seconds: int = 30,
    project_id: str | None = None,
    checkout_id: str | None = None,
    repository_root: str | None = None,
    source_view_hash: str | None = None,
    expected_substrings: list[str] | None = None,
) -> dict[str, Any]:
    verify_plan_applied(plan)
    if plan.profile != "normal":
        raise RuntimeProbeError(
            "The product rejection probe requires the normal profile."
        )
    overrides = {
        "--project-id": project_id,
        "--checkout-id": checkout_id,
        "--repository-root": repository_root,
        "--source-view-hash": source_view_hash,
    }
    launch = plan.launch
    args = _overridden_args([str(value) for value in launch["args"]], overrides)
    parameters = StdioServerParameters(
        command=str(launch["command"]),
        args=args,
        cwd=Path(str(launch["cwd"])),
        env={**os.environ, "CODEMESH_MODEL_PROVIDER": "none"},
    )
    timeout = timedelta(seconds=timeout_seconds)
    started = perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    actual_tools = sorted(tool.name for tool in listed.tools)
                    expected_tools = sorted(
                        str(value) for value in launch["expected_tools"]
                    )
                    if actual_tools != expected_tools:
                        raise RuntimeProbeError(
                            "Rejection probe tool surface differs from the reviewed plan."
                        )
                    result = await session.call_tool(
                        "codemesh_get_repository_status",
                        arguments={},
                        read_timeout_seconds=timeout,
                    )
                    message = _result_text(result)
                    rejection_issues: list[str] = []
                    rejected = bool(result.isError)
                    if not rejected:
                        payload = _tool_payload(result)
                        if payload.get("ok") is False:
                            rejected = True
                        else:
                            status_data = _data(payload)
                            assessment = (status_data.get("freshness") or {}).get(
                                "binding"
                            ) or {}
                            rejection_issues = [
                                str(value) for value in assessment.get("issues") or []
                            ]
                            effective_binding = {
                                **plan.binding,
                                "project_id": project_id
                                or plan.binding.get("project_id"),
                                "checkout_id": checkout_id
                                or plan.binding.get("checkout_id"),
                                "repository_root": repository_root
                                or plan.binding.get("repository_root"),
                                "source_view_hash": source_view_hash
                                if source_view_hash is not None
                                else plan.binding.get("source_view_hash"),
                            }
                            try:
                                _require_fresh_status(status_data, effective_binding)
                            except RuntimeProbeError as rejection:
                                rejected = True
                                detail = (status_data.get("freshness") or {}).get(
                                    "detail"
                                )
                                message = " ".join(
                                    value
                                    for value in [str(detail or ""), str(rejection)]
                                    if value
                                )
                    if not rejected:
                        raise RuntimeProbeError(
                            "Unsafe binding was accepted by the normal MCP profile."
                        )
                    missing = [
                        value
                        for value in expected_substrings or []
                        if value.casefold() not in message.casefold()
                    ]
                    if missing:
                        raise RuntimeProbeError(
                            "Binding was rejected without expected diagnostic(s): "
                            + ", ".join(missing)
                            + f". Returned: {message}"
                        )
    except RuntimeProbeError:
        raise
    except TimeoutError as exc:
        raise RuntimeProbeError(
            f"CodeMesh MCP rejection probe exceeded {timeout_seconds} seconds."
        ) from exc
    except Exception as exc:
        nested = _nested_probe_error(exc)
        if nested is not None:
            raise nested from exc
        raise RuntimeProbeError(
            "Could not run the configured CodeMesh rejection probe: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    return {
        "schema_version": "codemesh-runtime-rejection-probe-v1",
        "passed": True,
        "rejected": True,
        "provider_mode": "none",
        "profile": plan.profile,
        "project_id": project_id or plan.binding.get("project_id"),
        "checkout_id": checkout_id or plan.binding.get("checkout_id"),
        "repository_root": repository_root or plan.binding.get("repository_root"),
        "source_view_hash": source_view_hash
        if source_view_hash is not None
        else plan.binding.get("source_view_hash"),
        "expected_substrings": sorted(expected_substrings or []),
        "rejection_issues": sorted(rejection_issues),
        "diagnostic": message,
        "duration_ms": round((perf_counter() - started) * 1000, 3),
    }


def _require_instruction_binding(
    instructions: str,
    binding: dict[str, str | None],
) -> None:
    required = [
        binding.get("project_id"),
        binding.get("checkout_id"),
        binding.get("repository_root"),
    ]
    missing = [value for value in required if value and value not in instructions]
    if missing:
        raise RuntimeProbeError(
            "MCP initialization instructions do not identify the reviewed binding."
        )


def _require_bound_repository(
    payload: dict[str, Any],
    binding: dict[str, str | None],
) -> None:
    repositories = _data(payload).get("repositories") or []
    if len(repositories) != 1:
        raise RuntimeProbeError(
            "Bound MCP repository listing must expose exactly one checkout."
        )
    repository = repositories[0]
    if (
        repository.get("project_id") != binding.get("project_id")
        or repository.get("checkout_id") != binding.get("checkout_id")
        or not _same_path(
            repository.get("root_path"),
            binding.get("repository_root"),
        )
    ):
        raise RuntimeProbeError(
            "MCP repository listing does not match the reviewed binding."
        )


def _require_fresh_status(
    status: dict[str, Any],
    binding: dict[str, str | None],
) -> None:
    repository = status.get("repository") or {}
    freshness = status.get("freshness") or {}
    assessment = freshness.get("binding") or {}
    if (
        status.get("repository_id") != binding.get("project_id")
        or repository.get("project_id") != binding.get("project_id")
        or repository.get("checkout_id") != binding.get("checkout_id")
        or freshness.get("status") != "fresh"
        or freshness.get("is_stale") is not False
        or assessment.get("status") != "accepted"
    ):
        issues = assessment.get("issues") or []
        raise RuntimeProbeError(
            "Configured repository binding or freshness was rejected"
            + (f": {', '.join(str(value) for value in issues)}" if issues else ".")
        )


def _tool_payload(result: Any) -> dict[str, Any]:
    if result.isError:
        raise RuntimeProbeError("A required MCP probe tool returned an error.")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for item in result.content:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeProbeError("A required MCP probe tool returned no JSON object.")


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise RuntimeProbeError("A required MCP probe payload has an invalid shape.")
    return data


def _same_path(left: Any, right: Any) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(os.path.realpath(str(left))) == os.path.normcase(
        os.path.realpath(str(right))
    )


def _context_item_path(item: dict[str, Any]) -> str | None:
    hit = item.get("hit") if isinstance(item.get("hit"), dict) else {}
    path = hit.get("file_path")
    if path:
        return str(path).replace("\\", "/")
    node = item.get("node") if isinstance(item.get("node"), dict) else {}
    span = node.get("span") if isinstance(node.get("span"), dict) else {}
    path = span.get("file_path")
    return str(path).replace("\\", "/") if path else None


def _overridden_args(
    arguments: list[str], overrides: dict[str, str | None]
) -> list[str]:
    result = list(arguments)
    for flag, value in overrides.items():
        if value is None:
            continue
        if flag in result:
            index = result.index(flag)
            if index + 1 >= len(result):
                raise RuntimeProbeError(f"Reviewed launch has no value for {flag}.")
            result[index + 1] = value
        else:
            result.extend([flag, value])
    return result


def _require_launch_value(arguments: list[Any], flag: str, expected: str) -> None:
    values = [str(value) for value in arguments]
    if flag not in values:
        raise RuntimeProbeError(f"Reviewed launch has no {flag} value.")
    index = values.index(flag)
    if index + 1 >= len(values) or values[index + 1] != expected:
        raise RuntimeProbeError(f"Reviewed launch {flag} value changed.")


def _result_text(result: Any) -> str:
    parts = []
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        parts.append(json.dumps(structured, sort_keys=True, default=str))
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return " ".join(parts)


def _nested_probe_error(error: BaseException) -> RuntimeProbeError | None:
    if isinstance(error, RuntimeProbeError):
        return error
    if isinstance(error, BaseExceptionGroup):
        for nested in error.exceptions:
            match = _nested_probe_error(nested)
            if match is not None:
                return match
    return None
