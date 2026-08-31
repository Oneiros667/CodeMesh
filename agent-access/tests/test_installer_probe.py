from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from codemesh_agent_access import probe
from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.installer import (
    apply_installation_plan,
    create_installation_plan,
    load_installation_plan,
    verify_plan_applied,
    write_installation_plan,
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
            expected_substrings=["checkout"],
        )
    )

    assert report["passed"] is True
    assert report["rejected"] is True
    assert report["checkout_id"] == "checkout:wrong"


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
        return SimpleNamespace(
            isError=True,
            structuredContent=None,
            content=[SimpleNamespace(text="checkout binding rejected")],
        )
