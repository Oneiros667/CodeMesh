from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from codemesh_agent_access import feedback as feedback_module
from codemesh_agent_access import mcp
from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.feedback import (
    FeedbackPacketV2,
    get_session_feedback,
    list_session_feedback,
    prepare_feedback_resolution,
    record_development_feedback,
    validate_feedback,
)
from codemesh_agent_access.feedback_session import (
    CLIENT_PROFILE,
    MAINTAINER_PROFILE,
    SessionBounds,
    SessionParticipant,
    activate_session,
    create_session_plan,
    create_session_runtime,
)
from codemesh_agent_access.models import ToolResult


NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)


def test_records_v2_with_server_derived_session_and_repository_provenance(
    tmp_path: Path,
) -> None:
    client_runtime, _maintainer_runtime, client, _codemesh = _session(tmp_path)

    packet, output = _record(client_runtime)

    assert packet.schema_version == "codemesh-feedback/v2"
    assert packet.classification == "diagnostic"
    assert packet.session.session_id == client_runtime.payload.session_id
    assert packet.repository.root == str(client)
    assert packet.codemesh.project_id == "project:client"
    assert packet.codemesh.checkout_id == "checkout:client"
    assert packet.codemesh.binding.status == "accepted"
    assert packet.codemesh.languages == ["csharp", "python"]
    assert packet.task.recent_tool_events[0].tool == "codemesh_get_context_package"
    assert validate_feedback(output) == packet


def test_content_feedback_requires_accepted_provenance_but_setup_does_not(
    tmp_path: Path,
) -> None:
    client_runtime, _maintainer_runtime, _client, _codemesh = _session(tmp_path)
    unavailable = {
        "status": "unavailable",
        "diagnostic_code": "binding_rejected",
    }

    with pytest.raises(ValueError, match="requires accepted snapshot"):
        _record(client_runtime, provenance=unavailable)

    packet, _output = _record(
        client_runtime,
        provenance=unavailable,
        issue_category="binding",
    )
    assert packet.codemesh.snapshot_id is None
    assert packet.codemesh.binding.diagnostic_code == "binding_rejected"


def test_v2_validator_reapplies_sanitization_to_handcrafted_packet(
    tmp_path: Path,
) -> None:
    client_runtime, _maintainer_runtime, _client, _codemesh = _session(tmp_path)
    _packet, output = _record(client_runtime)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["result"]["fallback_reason"] = "token=do-not-retain"
    unsigned = {key: value for key, value in payload.items() if key != "feedback_id"}
    payload["feedback_id"] = feedback_module._content_id(unsigned)
    output.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="credential or secret"):
        validate_feedback(output)


def test_maintainer_lists_gets_and_prepares_stable_non_authorizing_plan(
    tmp_path: Path,
) -> None:
    client_runtime, maintainer_runtime, _client, _codemesh = _session(tmp_path)
    failed, _ = _record(client_runtime)
    passed, _ = _record(
        client_runtime,
        validation_outcome="passed",
        supersedes_feedback_ids=[failed.feedback_id],
    )

    listing = list_session_feedback(maintainer_runtime)
    assert listing["total"] == 2
    states = {item["feedback_id"]: item["state"] for item in listing["items"]}
    assert states[failed.feedback_id] == "resolved"
    assert states[passed.feedback_id] == "verified"

    detail = get_session_feedback(maintainer_runtime, failed.feedback_id)
    assert detail["state"] == "resolved"
    assert detail["session_scope"] == "active_session"
    assert detail["packet"]["feedback_id"] == failed.feedback_id

    arguments = {
        "runtime": maintainer_runtime,
        "feedback_ids": [failed.feedback_id],
        "reproduction_state": "reproduced",
        "change_summary": "Preserve the missing relationship during retrieval.",
        "proposed_paths": ["src/retrieval.py"],
        "risks": ["Could alter ranking."],
        "required_tests": ["Run the relationship fixture."],
    }
    first = prepare_feedback_resolution(**arguments)
    second = prepare_feedback_resolution(**arguments)
    assert first == second
    assert first["human_review_required"] is True
    assert first["human_approved"] is False
    assert len(first["plan_hash"]) == 64


def test_only_matching_passing_rechecks_resolve_feedback(tmp_path: Path) -> None:
    client_runtime, maintainer_runtime, _client, _codemesh = _session(tmp_path)
    failed, _ = _record(client_runtime)

    with pytest.raises(ValueError, match="Only a passing recheck"):
        _record(
            client_runtime,
            validation_outcome="failed",
            supersedes_feedback_ids=[failed.feedback_id],
        )

    _record(
        client_runtime,
        issue_category="ranking",
        validation_outcome="passed",
        supersedes_feedback_ids=[failed.feedback_id],
    )
    listing = list_session_feedback(maintainer_runtime)
    states = {item["feedback_id"]: item["state"] for item in listing["items"]}
    assert states[failed.feedback_id] == "open"


def test_maintainer_rejects_outside_ids_and_proposal_paths(tmp_path: Path) -> None:
    client_runtime, maintainer_runtime, _client, _codemesh = _session(tmp_path)
    packet, _ = _record(client_runtime)

    with pytest.raises(ValueError, match="not found"):
        get_session_feedback(maintainer_runtime, "feedback-" + "a" * 20)

    with pytest.raises(ValueError, match="repository-relative"):
        prepare_feedback_resolution(
            maintainer_runtime,
            feedback_ids=[packet.feedback_id],
            reproduction_state="reproduced",
            change_summary="Test unsafe scope.",
            proposed_paths=[str(tmp_path / "outside.py")],
        )


def test_maintainer_reports_linked_packet_as_invalid_without_reading_it(
    tmp_path: Path,
) -> None:
    client_runtime, maintainer_runtime, client, _codemesh = _session(tmp_path)
    _record(client_runtime)
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret":"do not inspect"}', encoding="utf-8")
    (client / ".codemesh-feedback" / "linked.json").symlink_to(outside)

    listing = list_session_feedback(maintainer_runtime)

    assert listing["total"] == 1
    assert listing["invalid_packet_count"] == 1
    assert listing["invalid_packets"][0]["code"] == "invalid_packet"


def test_mcp_feedback_profiles_are_exact_and_record_through_the_client_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_runtime, maintainer_runtime, client, _codemesh = _session(tmp_path)

    async def accepted_status(repository_id: str, **_kwargs) -> ToolResult:
        return ToolResult(
            data={
                "repository_id": repository_id,
                "repository": {"snapshot_id": "snapshot:mcp"},
                "latest_run": {
                    "language": "python",
                    "parser_name": "python-tree-sitter",
                },
                "freshness": {
                    "status": "fresh",
                    "is_stale": False,
                    "binding": {"status": "accepted", "issues": []},
                },
            }
        )

    monkeypatch.setattr(mcp.tools, "get_repository_status", accepted_status)
    client_server = mcp.build_server(
        profile=CLIENT_PROFILE,
        binding=client_runtime.binding,
        feedback_runtime=client_runtime,
    )
    client_tools = {tool.name: tool for tool in asyncio.run(client_server.list_tools())}
    assert set(client_tools) == set(client_runtime.payload.profiles[CLIENT_PROFILE])
    assert client_tools["codemesh_record_feedback"].annotations.readOnlyHint is False
    assert client_tools["codemesh_record_feedback"].annotations.destructiveHint is False
    assert (
        client_tools["codemesh_record_feedback"].inputSchema["additionalProperties"]
        is False
    )
    assert "explicitly enabled" in client_server.instructions

    asyncio.run(client_server.call_tool("codemesh_get_repository_status", {}))

    _content, recorded = asyncio.run(
        client_server.call_tool(
            "codemesh_record_feedback",
            {
                "confidence": "high",
                "task_family": "discovery",
                "issue_category": "ranking",
                "validation_outcome": "failed",
                "missed_paths": ["src/retrieval.py"],
            },
        )
    )
    assert recorded["recorded"] is True
    assert recorded["packet_path"].startswith(".codemesh-feedback/")
    assert Path(client, recorded["packet_path"]).is_file()
    recorded_packet = validate_feedback(Path(client, recorded["packet_path"]))
    assert isinstance(recorded_packet, FeedbackPacketV2)
    assert recorded_packet.task.recent_tool_events[0].tool == (
        "codemesh_get_repository_status"
    )
    with pytest.raises(ToolError, match="classification|repository_root"):
        asyncio.run(
            client_server.call_tool(
                "codemesh_record_feedback",
                {
                    "confidence": "high",
                    "task_family": "discovery",
                    "issue_category": "binding",
                    "validation_outcome": "failed",
                    "classification": "controlled-evaluation",
                    "repository_root": str(client),
                },
            )
        )

    maintainer_server = mcp.build_server(
        profile=MAINTAINER_PROFILE,
        binding=maintainer_runtime.binding,
        feedback_runtime=maintainer_runtime,
    )
    maintainer_tools = {
        tool.name: tool for tool in asyncio.run(maintainer_server.list_tools())
    }
    assert set(maintainer_tools) == set(
        maintainer_runtime.payload.profiles[MAINTAINER_PROFILE]
    )
    assert all(tool.annotations.readOnlyHint for tool in maintainer_tools.values())
    _content, listing = asyncio.run(
        maintainer_server.call_tool("codemesh_list_feedback", {})
    )
    assert listing["total"] == 1


def test_feedback_mcp_profiles_fail_closed_without_session_runtime() -> None:
    binding = RepositoryBinding("project:test", "checkout:test", "/does/not/matter")
    for profile in (CLIENT_PROFILE, MAINTAINER_PROFILE):
        with pytest.raises(ValueError, match="validated session runtime"):
            mcp.build_server(profile=profile, binding=binding)


def test_agent_format_context_package_supplies_feedback_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_runtime, _maintainer_runtime, client, _codemesh = _session(tmp_path)

    async def context_package(query: str, **_kwargs) -> ToolResult:
        return ToolResult(
            data={
                "query": {"query": query},
                "repository": {"snapshot_id": "snapshot:agent"},
                "latest_run": {
                    "language": "python,rust",
                    "parser_name": "composite-v1",
                },
                "items": [],
                "validation_recommendations": [],
                "total_snippet_characters": 0,
                "generated_at": NOW.isoformat(),
            }
        )

    monkeypatch.setattr(mcp.tools, "get_context_package", context_package)
    server = mcp.build_server(
        profile=CLIENT_PROFILE,
        binding=client_runtime.binding,
        feedback_runtime=client_runtime,
    )
    package = asyncio.run(
        server.call_tool(
            "codemesh_get_context_package",
            {"query": "find bridge", "output_format": "agent"},
        )
    )
    assert package.isError is False
    _content, recorded = asyncio.run(
        server.call_tool(
            "codemesh_record_feedback",
            {
                "confidence": "high",
                "task_family": "cross-language-impact",
                "issue_category": "missing-relationship",
                "validation_outcome": "failed",
                "missed_paths": ["src/retrieval.py"],
            },
        )
    )
    packet = validate_feedback(client / recorded["packet_path"])
    assert isinstance(packet, FeedbackPacketV2)
    assert packet.codemesh.snapshot_id == "snapshot:agent"
    assert packet.codemesh.languages == ["python", "rust"]


def test_feedback_session_enforces_request_and_packet_bounds(tmp_path: Path) -> None:
    bounds = SessionBounds(max_requests_per_minute=1, max_packets=1)
    client_runtime, _maintainer_runtime, _client, _codemesh = _session(
        tmp_path,
        bounds=bounds,
    )
    server = mcp.build_server(
        profile=CLIENT_PROFILE,
        binding=client_runtime.binding,
        feedback_runtime=client_runtime,
        monotonic_clock=lambda: 10.0,
    )
    asyncio.run(server.call_tool("codemesh_get_feedback_session", {}))
    with pytest.raises(ToolError, match="request-rate limit"):
        asyncio.run(server.call_tool("codemesh_get_feedback_session", {}))

    unavailable = {"status": "unavailable", "diagnostic_code": "binding_rejected"}
    _record(client_runtime, issue_category="binding", provenance=unavailable)
    with pytest.raises(ValueError, match="packet limit"):
        _record(
            client_runtime,
            issue_category="binding",
            provenance=unavailable,
        )


def _record(
    runtime,
    *,
    provenance=None,
    issue_category="missing-relationship",
    validation_outcome="failed",
    supersedes_feedback_ids=None,
) -> tuple[FeedbackPacketV2, Path]:
    return record_development_feedback(
        runtime=runtime,
        confidence="high",
        task_family="change-impact",
        issue_category=issue_category,
        validation_outcome=validation_outcome,
        provenance=provenance
        or {
            "status": "accepted",
            "snapshot_id": "snapshot:test",
            "languages": ["python", "csharp"],
            "parser_profile": "mixed-v1",
        },
        recent_tool_events=[
            {
                "sequence": 1,
                "tool": "codemesh_get_context_package",
                "outcome": "succeeded",
            }
        ],
        missed_paths=["src/retrieval.py"],
        minimal_reproduction="Request callers for the selected method.",
        proposed_correction="Include the missing caller edge.",
        supersedes_feedback_ids=supersedes_feedback_ids,
    )


def _session(tmp_path: Path, *, bounds: SessionBounds | None = None):
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    plan = create_session_plan(
        manifest_path=tmp_path / "session.json",
        codemesh=_participant(codemesh, "codemesh", "maintainer"),
        clients=[_participant(client, "client", "Primary")],
        expires_at=NOW + timedelta(hours=4),
        bounds=bounds,
        now=NOW,
    )
    activate_session(plan, plan.plan_hash)
    client_runtime = create_session_runtime(
        plan.manifest_path,
        plan.manifest_file_sha256,
        profile=CLIENT_PROFILE,
        binding=RepositoryBinding(
            "project:client",
            "checkout:client",
            str(client),
        ),
        clock=lambda: NOW,
    )
    maintainer_runtime = create_session_runtime(
        plan.manifest_path,
        plan.manifest_file_sha256,
        profile=MAINTAINER_PROFILE,
        binding=RepositoryBinding(
            "project:codemesh",
            "checkout:codemesh",
            str(codemesh),
        ),
        clock=lambda: NOW,
    )
    return client_runtime, maintainer_runtime, client, codemesh


def _participant(root: Path, name: str, role: str) -> SessionParticipant:
    return SessionParticipant(
        project_id=f"project:{name}",
        checkout_id=f"checkout:{name}",
        repository_root=str(root),
        reporter_role=role,
    )


def _repository(path: Path, *, ignored: bool) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "codemesh-tests@example.invalid"],
        cwd=path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "CodeMesh Tests"], cwd=path, check=True
    )
    (path / "src").mkdir()
    (path / "src" / "retrieval.py").write_text("pass\n", encoding="utf-8")
    if ignored:
        (path / ".gitignore").write_text("/.codemesh-feedback/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "test: fixture"], cwd=path, check=True)
    return path.resolve()
