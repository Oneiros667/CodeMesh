from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.feedback_session import (
    CLIENT_PROFILE,
    MAINTAINER_PROFILE,
    SessionParticipant,
    activate_session,
    create_session_plan,
    revoke_session,
)
from codemesh_agent_access.installer import create_installation_plan


def test_provider_free_stdio_failure_to_recheck_flow(tmp_path: Path) -> None:
    asyncio.run(_exercise_provider_free_stdio_flow(tmp_path))


async def _exercise_provider_free_stdio_flow(tmp_path: Path) -> None:
    codemesh_root = Path(__file__).resolve().parents[2]
    client = _repository(tmp_path / "client")
    client_binding = RepositoryBinding(
        "project:client",
        "checkout:client",
        str(client),
    )
    maintainer_binding = RepositoryBinding(
        "project:codemesh",
        "checkout:codemesh",
        str(codemesh_root),
    )
    session_plan = create_session_plan(
        manifest_path=tmp_path / "session.json",
        codemesh=SessionParticipant(
            project_id=maintainer_binding.project_id,
            checkout_id=maintainer_binding.checkout_id,
            repository_root=maintainer_binding.repository_root,
            reporter_role="maintainer",
        ),
        clients=[
            SessionParticipant(
                project_id=client_binding.project_id,
                checkout_id=client_binding.checkout_id,
                repository_root=client_binding.repository_root,
                reporter_role="integration-client",
            )
        ],
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    activate_session(session_plan, session_plan.plan_hash)
    client_plan = create_installation_plan(
        client,
        codemesh_root,
        client_binding,
        profile=CLIENT_PROFILE,
        include_onboarding=False,
        feedback_session_path=session_plan.manifest_path,
        feedback_session_sha256=session_plan.manifest_file_sha256,
    )
    maintainer_plan = create_installation_plan(
        codemesh_root,
        codemesh_root,
        maintainer_binding,
        profile=MAINTAINER_PROFILE,
        include_onboarding=False,
        feedback_session_path=session_plan.manifest_path,
        feedback_session_sha256=session_plan.manifest_file_sha256,
    )
    before = _git_status(codemesh_root)

    async with _session(client_plan) as client_session:
        discovery = _payload(
            await client_session.call_tool("codemesh_get_feedback_session", {})
        )
        assert discovery["session_id"] == session_plan.manifest.payload.session_id
        failed = _payload(
            await client_session.call_tool(
                "codemesh_record_feedback",
                {
                    "confidence": "high",
                    "task_family": "agent-access-setup",
                    "issue_category": "binding",
                    "validation_outcome": "failed",
                    "fallback_reason": "The configured binding was rejected.",
                },
            )
        )
        assert failed["human_review_required"] is True

    async with _session(maintainer_plan) as maintainer_session:
        listing = _payload(
            await maintainer_session.call_tool("codemesh_list_feedback", {})
        )
        assert listing["total"] == 1
        detail = _payload(
            await maintainer_session.call_tool(
                "codemesh_get_feedback",
                {"feedback_id": failed["feedback_id"]},
            )
        )
        assert detail["packet"]["feedback_id"] == failed["feedback_id"]
        resolution = _payload(
            await maintainer_session.call_tool(
                "codemesh_prepare_feedback_resolution",
                {
                    "feedback_ids": [failed["feedback_id"]],
                    "reproduction_state": "reproduced",
                    "change_summary": "Clarify rejected binding diagnostics.",
                    "proposed_paths": ["agent-access/codemesh_agent_access/binding.py"],
                    "required_tests": ["Run the Agent Access suite."],
                },
            )
        )
        assert resolution["human_approved"] is False
        assert len(resolution["plan_hash"]) == 64

    async with _session(client_plan) as client_session:
        passed = _payload(
            await client_session.call_tool(
                "codemesh_record_feedback",
                {
                    "confidence": "high",
                    "task_family": "agent-access-setup",
                    "issue_category": "binding",
                    "validation_outcome": "passed",
                    "supersedes_feedback_ids": [failed["feedback_id"]],
                },
            )
        )
        assert passed["feedback_id"] != failed["feedback_id"]

        async with _session(maintainer_plan) as maintainer_session:
            listing = _payload(
                await maintainer_session.call_tool("codemesh_list_feedback", {})
            )
            states = {item["feedback_id"]: item["state"] for item in listing["items"]}
            assert states[failed["feedback_id"]] == "resolved"

        revoke_session(
            session_plan.manifest_path,
            session_plan.manifest_file_sha256,
            reason="Integration rehearsal complete.",
        )
        rejected = await client_session.call_tool("codemesh_get_feedback_session", {})
        assert rejected.isError is True

    assert _git_status(codemesh_root) == before
    assert len(list((client / ".codemesh-feedback").glob("feedback-*.json"))) == 2


@asynccontextmanager
async def _session(plan: Any):
    launch = plan.launch
    parameters = StdioServerParameters(
        command=str(launch["command"]),
        args=[str(value) for value in launch["args"]],
        cwd=Path(str(launch["cwd"])),
        env={**os.environ, "CODEMESH_MODEL_PROVIDER": "none"},
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


def _payload(result: Any) -> dict[str, Any]:
    assert result.isError is False
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
    raise AssertionError("MCP tool returned no JSON payload.")


def _git_status(root: Path) -> bytes:
    return subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def _repository(path: Path) -> Path:
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
    (path / ".gitignore").write_text("/.codemesh-feedback/\n", encoding="utf-8")
    (path / "README.md").write_text("# Client fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "test: fixture"], cwd=path, check=True)
    return path.resolve()
