from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

from codemesh_agent_access import cli
from codemesh_agent_access.binding import RepositoryBinding
from codemesh_agent_access.feedback_session import (
    CLIENT_PROFILE,
    MAINTAINER_PROFILE,
    SessionParticipant,
    activate_session,
    create_session_plan,
    create_session_runtime,
    inspect_session,
    load_active_session,
    load_session_plan,
    revoke_session,
    write_session_plan,
)


NOW = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)


def test_session_plan_requires_reviewed_hash_and_authorizes_exact_bindings(
    tmp_path: Path,
) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    manifest_path = tmp_path / "sessions" / "active.json"
    manifest_path.parent.mkdir()

    plan = create_session_plan(
        manifest_path=manifest_path,
        codemesh=_participant(codemesh, "codemesh", "maintainer"),
        clients=[_participant(client, "client", "Primary")],
        expires_at=NOW + timedelta(hours=4),
        now=NOW,
    )

    assert not manifest_path.exists()
    with pytest.raises(ValueError, match="Approved plan hash"):
        activate_session(plan, "0" * 64)

    assert activate_session(plan, plan.plan_hash) == manifest_path
    with pytest.raises(FileExistsError):
        activate_session(plan, plan.plan_hash)
    with pytest.raises(ValueError, match="manifest hash"):
        inspect_session(manifest_path, "0" * 64, now=NOW)
    status = inspect_session(manifest_path, plan.manifest_file_sha256, now=NOW)
    assert status["status"] == "active"
    assert status["client_count"] == 1

    client_binding = RepositoryBinding(
        "project:client",
        "checkout:client",
        str(client),
    )
    client_manifest = load_active_session(
        manifest_path,
        plan.manifest_file_sha256,
        profile=CLIENT_PROFILE,
        binding=client_binding,
        now=NOW,
    )
    assert client_manifest.payload.session_id.startswith("session-")

    maintainer_binding = RepositoryBinding(
        "project:codemesh",
        "checkout:codemesh",
        str(codemesh),
    )
    runtime = create_session_runtime(
        manifest_path,
        plan.manifest_file_sha256,
        profile=MAINTAINER_PROFILE,
        binding=maintainer_binding,
        clock=lambda: NOW,
    )
    assert runtime.assert_active().codemesh.repository_root == str(codemesh)


def test_session_plan_round_trip_and_tamper_rejection(tmp_path: Path) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    manifest_path = tmp_path / "active.json"
    plan_path = tmp_path / "plan.json"
    plan = create_session_plan(
        manifest_path=manifest_path,
        codemesh=_participant(codemesh, "codemesh", "maintainer"),
        clients=[_participant(client, "client", "Primary")],
        expires_at=NOW + timedelta(hours=1),
        now=NOW,
    )

    write_session_plan(plan, plan_path)
    assert load_session_plan(plan_path) == plan

    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["manifest"]["payload"]["expires_at"] = (
        NOW + timedelta(hours=2)
    ).isoformat()
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="plan hash|payload hash"):
        load_session_plan(plan_path)


def test_session_rejects_linked_authority_files(tmp_path: Path) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    plan = create_session_plan(
        manifest_path=tmp_path / "active.json",
        codemesh=_participant(codemesh, "codemesh", "maintainer"),
        clients=[_participant(client, "client", "Primary")],
        expires_at=NOW + timedelta(hours=1),
        now=NOW,
    )
    manifest = activate_session(plan, plan.plan_hash)
    manifest_link = tmp_path / "manifest-hardlink.json"
    manifest_link.hardlink_to(manifest)
    with pytest.raises(ValueError, match="unlinked local regular file"):
        inspect_session(manifest, plan.manifest_file_sha256, now=NOW)
    manifest_link.unlink()

    revocation = revoke_session(
        manifest,
        plan.manifest_file_sha256,
        reason="Owner closed the test session.",
        now=NOW,
    )
    revocation_link = tmp_path / "revocation-hardlink.json"
    revocation_link.hardlink_to(revocation)
    with pytest.raises(ValueError, match="unlinked local regular file"):
        inspect_session(manifest, plan.manifest_file_sha256, now=NOW)
    revocation_link.unlink()
    revocation.unlink()
    revocation.symlink_to(tmp_path / "missing-revocation.json")
    with pytest.raises(ValueError, match="unlinked local regular file"):
        inspect_session(manifest, plan.manifest_file_sha256, now=NOW)


def test_session_rejects_wrong_binding_expiry_and_revocation(tmp_path: Path) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    plan = create_session_plan(
        manifest_path=tmp_path / "active.json",
        codemesh=_participant(codemesh, "codemesh", "maintainer"),
        clients=[_participant(client, "client", "Primary")],
        expires_at=NOW + timedelta(hours=1),
        now=NOW,
    )
    activate_session(plan, plan.plan_hash)
    binding = RepositoryBinding("project:client", "checkout:wrong", str(client))

    with pytest.raises(ValueError, match="does not authorize"):
        load_active_session(
            plan.manifest_path,
            plan.manifest_file_sha256,
            profile=CLIENT_PROFILE,
            binding=binding,
            now=NOW,
        )

    correct = RepositoryBinding("project:client", "checkout:client", str(client))
    with pytest.raises(ValueError, match="expired"):
        load_active_session(
            plan.manifest_path,
            plan.manifest_file_sha256,
            profile=CLIENT_PROFILE,
            binding=correct,
            now=NOW + timedelta(hours=1),
        )

    revoke_session(
        plan.manifest_path,
        plan.manifest_file_sha256,
        reason="Owner closed the development session.",
        now=NOW + timedelta(minutes=5),
    )
    with pytest.raises(FileExistsError):
        revoke_session(
            plan.manifest_path,
            plan.manifest_file_sha256,
            reason="Duplicate close must not overwrite.",
            now=NOW + timedelta(minutes=6),
        )
    assert (
        inspect_session(plan.manifest_path, plan.manifest_file_sha256, now=NOW)[
            "status"
        ]
        == "revoked"
    )
    with pytest.raises(ValueError, match="revoked"):
        load_active_session(
            plan.manifest_path,
            plan.manifest_file_sha256,
            profile=CLIENT_PROFILE,
            binding=correct,
            now=NOW,
        )


def test_session_requires_ignored_unlinked_client_outbox(tmp_path: Path) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=False)

    with pytest.raises(ValueError, match="is not ignored"):
        create_session_plan(
            manifest_path=tmp_path / "active.json",
            codemesh=_participant(codemesh, "codemesh", "maintainer"),
            clients=[_participant(client, "client", "Primary")],
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )

    (client / ".gitignore").write_text(
        "/.codemesh-feedback/\n",
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (client / ".codemesh-feedback").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outbox must be a local directory"):
        create_session_plan(
            manifest_path=tmp_path / "active.json",
            codemesh=_participant(codemesh, "codemesh", "maintainer"),
            clients=[_participant(client, "client", "Primary")],
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )


def test_session_rejects_duplicate_clients_and_long_duration(tmp_path: Path) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    participant = _participant(client, "client", "Primary")

    with pytest.raises(ValueError, match="must be unique"):
        create_session_plan(
            manifest_path=tmp_path / "active.json",
            codemesh=_participant(codemesh, "codemesh", "maintainer"),
            clients=[participant, participant],
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )

    with pytest.raises(ValueError, match="seven days"):
        create_session_plan(
            manifest_path=tmp_path / "active.json",
            codemesh=_participant(codemesh, "codemesh", "maintainer"),
            clients=[participant],
            expires_at=NOW + timedelta(days=8),
            now=NOW,
        )


def test_session_cli_plans_activates_inspects_and_revokes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    codemesh = _repository(tmp_path / "codemesh", ignored=False)
    client = _repository(tmp_path / "client", ignored=True)
    manifest = tmp_path / "active.json"
    plan_path = tmp_path / "plan.json"
    client_json = json.dumps(
        _participant(client, "client", "Primary").model_dump(mode="json")
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "feedback",
            "session",
            "plan",
            "--manifest-path",
            str(manifest),
            "--codemesh-root",
            str(codemesh),
            "--codemesh-project-id",
            "project:codemesh",
            "--codemesh-checkout-id",
            "checkout:codemesh",
            "--client-json",
            client_json,
            "--expires-at",
            (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "--output",
            str(plan_path),
        ],
    )
    cli.main()
    planned = json.loads(capsys.readouterr().out)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "feedback",
            "session",
            "activate",
            str(plan_path),
            "--approve-plan-hash",
            planned["plan_hash"],
        ],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["activated"] is True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "feedback",
            "session",
            "inspect",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            planned["manifest_file_sha256"],
        ],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["status"] == "active"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "feedback",
            "session",
            "revoke",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            planned["manifest_file_sha256"],
            "--reason",
            "Owner closed the test session.",
        ],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["revoked"] is True


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
    (path / "README.md").write_text("# Fixture\n", encoding="utf-8")
    if ignored:
        (path / ".gitignore").write_text("/.codemesh-feedback/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "test: fixture"], cwd=path, check=True)
    return path.resolve()
