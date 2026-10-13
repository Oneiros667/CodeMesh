from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from codemesh_agent_access import probe
from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.installer import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V1,
    apply_installation_plan,
    codex_mcp_overrides,
    create_installation_plan,
    load_installation_plan,
    verify_plan_applied,
    write_installation_plan,
)
from codemesh_agent_access.feedback_session import (
    CLIENT_PROFILE,
    SessionParticipant,
    activate_session,
    create_session_plan,
)


def test_installation_requires_reviewed_hash_and_preserves_unmanaged_content(
    tmp_path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:test", "checkout:test", str(target))

    plan = create_installation_plan(target, codemesh_root, binding)

    assert not (target / ".codex" / "config.toml").exists()
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == (
        "# Existing instructions\n"
    )
    assert all(item.diff for item in plan.files)
    assert "CODEMESH_NEO4J_PASSWORD" in plan.files[0].content
    assert 'CODEMESH_MODEL_PROVIDER = "none"' in plan.files[0].content
    assert "# Existing instructions" in plan.files[1].content

    with pytest.raises(ValueError, match="Approved plan hash"):
        apply_installation_plan(plan, "wrong")

    changed = apply_installation_plan(plan, plan.plan_hash)

    assert changed == [".codex/config.toml", "AGENTS.md"]
    verify_plan_applied(plan)
    assert "# Existing instructions" in (target / "AGENTS.md").read_text(
        encoding="utf-8"
    )
    assert "codemesh:onboarding:start" in (target / "AGENTS.md").read_text(
        encoding="utf-8"
    )
    onboarding = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "1. Start with one `codemesh_get_context_package` call" in onboarding
    assert "covers every required facet" in onboarding
    assert "at most three" in onboarding
    assert "avoid overlapping queries" in onboarding
    assert "fails closed when they are not accepted" in onboarding
    assert "only for explicit diagnostics" in onboarding
    assert onboarding.index("codemesh_get_context_package") < onboarding.index(
        "codemesh_get_repository_status"
    )

    overrides = codex_mcp_overrides(plan, approve_tools=True)
    assert f'mcp_servers.codemesh.command="{plan.launch["command"]}"' in overrides
    assert any('"--profile", "normal"' in value for value in overrides)
    assert any("env_vars=" in value for value in overrides)
    assert any('CODEMESH_MODEL_PROVIDER = "none"' in value for value in overrides)
    assert 'mcp_servers.codemesh.default_tools_approval_mode="approve"' in overrides
    assert not any("codemesh_delete_repository" in value for value in overrides)

    tampered = replace(
        plan,
        launch={**plan.launch, "args": [*plan.launch["args"], "--unexpected"]},
    )
    with pytest.raises(ValueError, match="hash does not match"):
        codex_mcp_overrides(tampered, approve_tools=True)


def test_installation_plan_round_trip_and_concurrent_change_rejection(tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Initial\n", encoding="utf-8")
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:test", "checkout:test", str(target))
    plan = create_installation_plan(target, codemesh_root, binding)
    plan_path = tmp_path / "reviewed-plan.json"
    write_installation_plan(plan, plan_path)

    loaded = load_installation_plan(plan_path)
    assert loaded == plan

    (target / "AGENTS.md").write_text("# Changed after review\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after review"):
        apply_installation_plan(loaded, loaded.plan_hash)


def test_configuration_only_plan_leaves_repository_guidance_to_instance_manager(
    tmp_path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Managed elsewhere\n", encoding="utf-8")
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:test", "checkout:test", str(target))

    plan = create_installation_plan(
        target,
        codemesh_root,
        binding,
        include_onboarding=False,
    )

    assert [item.path for item in plan.files] == [".codex/config.toml"]
    changed = apply_installation_plan(plan, plan.plan_hash)
    assert changed == [".codex/config.toml"]
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == (
        "# Managed elsewhere\n"
    )


def test_feedback_installation_pins_exact_session_and_onboards_client(
    tmp_path: Path,
) -> None:
    target = _git_repository(tmp_path / "target", ignored=True)
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:client", "checkout:client", str(target))
    session_plan = create_session_plan(
        manifest_path=tmp_path / "session.json",
        codemesh=SessionParticipant(
            project_id="project:codemesh",
            checkout_id="checkout:codemesh",
            repository_root=str(codemesh_root),
            reporter_role="maintainer",
        ),
        clients=[
            SessionParticipant(
                project_id=binding.project_id,
                checkout_id=binding.checkout_id,
                repository_root=binding.repository_root,
                reporter_role="Primary",
            )
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    activate_session(session_plan, session_plan.plan_hash)

    plan = create_installation_plan(
        target,
        codemesh_root,
        binding,
        profile=CLIENT_PROFILE,
        feedback_session_path=session_plan.manifest_path,
        feedback_session_sha256=session_plan.manifest_file_sha256,
    )

    assert plan.schema_version == SCHEMA_VERSION
    assert plan.session == {
        "manifest_path": session_plan.manifest_path,
        "manifest_file_sha256": session_plan.manifest_file_sha256,
    }
    assert "--feedback-session" in plan.launch["args"]
    assert "codemesh_record_feedback" in plan.launch["expected_tools"]
    onboarding = next(item.content for item in plan.files if item.path == "AGENTS.md")
    assert "codemesh_get_feedback_session" in onboarding
    assert "Human review remains required" in onboarding
    apply_installation_plan(plan, plan.plan_hash)
    verify_plan_applied(plan)


def test_v1_normal_installation_plan_remains_loadable(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:test", "checkout:test", str(target))
    plan = create_installation_plan(target, codemesh_root, binding)
    payload = plan.to_dict()
    payload["schema_version"] = SCHEMA_VERSION_V1
    payload.pop("session")
    payload.pop("plan_hash")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["plan_hash"] = hashlib.sha256(encoded).hexdigest()
    path = tmp_path / "v1-plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_installation_plan(path)

    assert loaded.schema_version == SCHEMA_VERSION_V1
    assert loaded.session is None
    assert loaded.profile == "normal"


def test_feedback_runtime_probe_checks_session_identity_without_writing(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    target = _git_repository(tmp_path / "target", ignored=True)
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:client", "checkout:client", str(target))
    session_plan = create_session_plan(
        manifest_path=tmp_path / "session.json",
        codemesh=SessionParticipant(
            project_id="project:codemesh",
            checkout_id="checkout:codemesh",
            repository_root=str(codemesh_root),
            reporter_role="maintainer",
        ),
        clients=[
            SessionParticipant(
                project_id=binding.project_id,
                checkout_id=binding.checkout_id,
                repository_root=binding.repository_root,
                reporter_role="Primary",
            )
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    activate_session(session_plan, session_plan.plan_hash)
    plan = create_installation_plan(
        target,
        codemesh_root,
        binding,
        profile=CLIENT_PROFILE,
        feedback_session_path=session_plan.manifest_path,
        feedback_session_sha256=session_plan.manifest_file_sha256,
    )
    apply_installation_plan(plan, plan.plan_hash)
    session = FakeFeedbackProbeSession(plan, session_plan.manifest.payload.session_id)

    @asynccontextmanager
    async def fake_stdio_client(parameters: Any):
        assert parameters.args == plan.launch["args"]
        assert parameters.env["CODEMESH_MODEL_PROVIDER"] == "none"
        yield object(), object()

    monkeypatch.setattr(probe, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(probe, "ClientSession", lambda *_args: session)

    report = asyncio.run(probe.run_feedback_runtime_probe(plan))

    assert report["passed"] is True
    assert report["profile"] == CLIENT_PROFILE
    assert report["session_id"] == session_plan.manifest.payload.session_id
    assert session.calls == ["codemesh_get_feedback_session"]


def test_runtime_probe_checks_exact_bound_normal_server(
    monkeypatch: Any, tmp_path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Initial\n", encoding="utf-8")
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:test", "checkout:test", str(target))
    plan = create_installation_plan(target, codemesh_root, binding)
    apply_installation_plan(plan, plan.plan_hash)

    session = FakeProbeSession(plan)

    @asynccontextmanager
    async def fake_stdio_client(parameters: Any):
        assert parameters.command == plan.launch["command"]
        assert parameters.args == plan.launch["args"]
        assert str(parameters.cwd) == plan.launch["cwd"]
        assert parameters.env["CODEMESH_MODEL_PROVIDER"] == "none"
        yield object(), object()

    monkeypatch.setattr(probe, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(probe, "ClientSession", lambda *_args: session)

    report = asyncio.run(
        probe.run_runtime_probe(plan, expected_paths=["src/example.py"])
    )

    assert report["passed"] is True
    assert report["profile"] == "normal"
    assert report["project_id"] == "project:test"
    assert report["checkout_id"] == "checkout:test"
    assert report["snapshot_id"] == "snapshot:test"
    assert report["context_item_count"] == 1
    assert report["returned_paths"] == ["src/example.py"]
    assert report["expected_paths"] == ["src/example.py"]
    assert session.calls == [
        "codemesh_list_repositories",
        "codemesh_get_repository_status",
        "codemesh_get_context_package",
    ]


def test_rejection_probe_requires_unsafe_binding_to_fail_closed(
    monkeypatch: Any, tmp_path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Initial\n", encoding="utf-8")
    codemesh_root = Path(__file__).resolve().parents[2]
    binding = RepositoryBinding("project:test", "checkout:test", str(target))
    plan = create_installation_plan(target, codemesh_root, binding)
    apply_installation_plan(plan, plan.plan_hash)
    session = FakeRejectedSession(plan)

    @asynccontextmanager
    async def fake_stdio_client(parameters: Any):
        checkout_index = parameters.args.index("--checkout-id") + 1
        assert parameters.args[checkout_index] == "checkout:wrong"
        assert parameters.env["CODEMESH_MODEL_PROVIDER"] == "none"
        yield object(), object()

    monkeypatch.setattr(probe, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(probe, "ClientSession", lambda *_args: session)

    report = asyncio.run(
        probe.run_runtime_rejection_probe(
            plan,
            checkout_id="checkout:wrong",
            expected_substrings=["bound_repository_missing"],
        )
    )

    assert report["passed"] is True
    assert report["rejected"] is True
    assert report["checkout_id"] == "checkout:wrong"
    assert report["rejection_issues"] == [
        "bound_repository_missing",
        "snapshot_not_fresh",
        "snapshot_provenance_unknown",
    ]


class FakeProbeSession:
    def __init__(self, plan: Any) -> None:
        self.plan = plan
        self.calls: list[str] = []

    async def __aenter__(self) -> "FakeProbeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def initialize(self) -> Any:
        binding = self.plan.binding
        return SimpleNamespace(
            instructions=(
                f"bound {binding['project_id']} {binding['checkout_id']} "
                f"{binding['repository_root']}"
            )
        )

    async def list_tools(self) -> Any:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name=name)
                for name in self.plan.launch["expected_tools"]
            ]
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        read_timeout_seconds: Any,
    ) -> Any:
        self.calls.append(name)
        binding = self.plan.binding
        repository = {
            "repository_id": binding["project_id"],
            "project_id": binding["project_id"],
            "checkout_id": binding["checkout_id"],
            "snapshot_id": "snapshot:test",
            "source_view_hash": "view:test",
            "root_path": binding["repository_root"],
        }
        if name == "codemesh_list_repositories":
            data = {"repositories": [repository]}
        elif name == "codemesh_get_repository_status":
            data = {
                "repository_id": binding["project_id"],
                "repository": repository,
                "freshness": {
                    "status": "fresh",
                    "is_stale": False,
                    "indexed_commit": "abc123",
                    "current_commit": "abc123",
                    "binding": {"status": "accepted", "issues": []},
                },
            }
        else:
            data = {
                "query": {"query": arguments["query"]},
                "items": [
                    {
                        "hit": {"file_path": "src/example.py"},
                        "relationship_groups": {},
                    }
                ],
            }
        payload = {"ok": True, "data": data, "error": None}
        return SimpleNamespace(
            isError=False,
            structuredContent=payload,
            content=[SimpleNamespace(text=json.dumps(payload))],
        )


class FakeRejectedSession:
    def __init__(self, plan: Any) -> None:
        self.plan = plan

    async def __aenter__(self) -> "FakeRejectedSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def initialize(self) -> Any:
        return SimpleNamespace(instructions="bound rejection fixture")

    async def list_tools(self) -> Any:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name=name)
                for name in self.plan.launch["expected_tools"]
            ]
        )

    async def call_tool(self, *_args: Any, **_kwargs: Any) -> Any:
        payload = {
            "ok": True,
            "data": {
                "repository_id": self.plan.binding["project_id"],
                "repository": None,
                "freshness": {
                    "status": "missing",
                    "is_stale": True,
                    "provenance_status": "unknown",
                    "detail": "Repository was not found in the CodeMesh registry.",
                    "binding": {
                        "status": "rejected",
                        "issues": [
                            "bound_repository_missing",
                            "snapshot_not_fresh",
                            "snapshot_provenance_unknown",
                        ],
                    },
                },
            },
            "error": None,
        }
        return SimpleNamespace(
            isError=False,
            structuredContent=payload,
            content=[SimpleNamespace(text=json.dumps(payload))],
        )


class FakeFeedbackProbeSession:
    def __init__(self, plan: Any, session_id: str) -> None:
        self.plan = plan
        self.session_id = session_id
        self.calls: list[str] = []

    async def __aenter__(self) -> "FakeFeedbackProbeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def initialize(self) -> Any:
        binding = self.plan.binding
        return SimpleNamespace(
            instructions=(
                "explicitly enabled local feedback session bound to "
                f"{binding['project_id']} {binding['checkout_id']} "
                f"{binding['repository_root']}"
            )
        )

    async def list_tools(self) -> Any:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name=name)
                for name in self.plan.launch["expected_tools"]
            ]
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        read_timeout_seconds: Any,
    ) -> Any:
        self.calls.append(name)
        assert arguments == {}
        payload = {
            "session_id": self.session_id,
            "enabled": True,
            "local_only": True,
        }
        return SimpleNamespace(
            isError=False,
            structuredContent=payload,
            content=[SimpleNamespace(text=json.dumps(payload))],
        )


def _git_repository(path: Path, *, ignored: bool) -> Path:
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
    (path / "README.md").write_text("# Fixture\n", encoding="utf-8")
    if ignored:
        (path / ".gitignore").write_text("/.codemesh-feedback/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "test: fixture"], cwd=path, check=True)
    return path.resolve()
