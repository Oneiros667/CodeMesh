from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from codemesh_agent_access import cli
from codemesh_agent_access.feedback import (
    PACKET_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
    record_feedback,
    summarize_feedback,
    validate_feedback,
)


def test_records_and_validates_sanitized_commit_bound_packet(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repo", ignored=True)

    packet, output = _record(repository)

    assert output.parent == repository / ".codemesh-feedback"
    assert packet.schema_version == PACKET_SCHEMA_VERSION
    assert packet.repository.root == str(repository)
    assert packet.repository.branch == "main"
    assert packet.repository.dirty is False
    assert packet.codemesh.languages == ["python", "rust"]
    assert packet.codemesh.dirty is False
    assert packet.result.missed_paths == ["rust/src/lib.rs"]
    assert validate_feedback(output) == packet


def test_recorder_requires_ignored_outbox(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repo", ignored=False)

    with pytest.raises(ValueError, match="is not ignored"):
        _record(repository)


def test_recorder_rejects_secrets_and_non_relative_paths(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repo", ignored=True)

    with pytest.raises(ValueError, match="credential or secret"):
        _record(repository, fallback_reason="token=do-not-store")

    with pytest.raises(ValueError, match="repository-relative paths"):
        _record(repository, missed_paths=[str(repository / "src/app.py")])


def test_validator_rejects_tampered_packet(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repo", ignored=True)
    _packet, output = _record(repository)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["issue"]["category"] = "ranking"
    output.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Feedback id mismatch"):
        validate_feedback(output)


def test_summarizer_groups_and_preserves_exact_provenance(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repo", ignored=True)
    first, _ = _record(repository, snapshot_id="snapshot:first")
    second, _ = _record(repository, snapshot_id="snapshot:second")

    summary = summarize_feedback([repository])

    assert summary["schema_version"] == SUMMARY_SCHEMA_VERSION
    assert summary["packet_count"] == 2
    priority = summary["priorities"][0]
    assert priority["issue_category"] == "missing-relationship"
    assert priority["occurrences"] == 2
    assert priority["priority"] == "high"
    assert priority["status"] == "open"
    assert {item["feedback_id"] for item in priority["provenance"]} == {
        first.feedback_id,
        second.feedback_id,
    }
    assert {item["snapshot_id"] for item in priority["provenance"]} == {
        "snapshot:first",
        "snapshot:second",
    }


def test_successful_recheck_resolves_superseded_failure(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repo", ignored=True)
    failed, _ = _record(repository, snapshot_id="snapshot:failed")
    _passed, _ = _record(
        repository,
        snapshot_id="snapshot:recheck",
        validation_outcome="passed",
        supersedes_feedback_ids=[failed.feedback_id],
    )

    priority = summarize_feedback([repository])["priorities"][0]

    assert priority["status"] == "resolved"
    assert priority["priority"] == "low"
    assert priority["priority_score"] == 0
    assert priority["superseded_feedback_ids"] == [failed.feedback_id]
    assert priority["unresolved_failure_ids"] == []


def test_feedback_cli_records_then_summarizes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = _repository(tmp_path / "repo", ignored=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "codemesh-agent-access",
            "feedback",
            "record",
            "--repository-root",
            str(repository),
            "--codemesh-root",
            str(repository),
            "--role",
            "Primary",
            "--classification",
            "diagnostic",
            "--confidence",
            "medium",
            "--project-id",
            "project:onenine",
            "--checkout-id",
            "checkout:primary",
            "--snapshot-id",
            "snapshot:test",
            "--language",
            "python",
            "--language",
            "rust",
            "--parser-profile",
            "python-rust-v1",
            "--task-family",
            "test-selection",
            "--issue-category",
            "ranking",
            "--validation-outcome",
            "inconclusive",
            "--missed-path",
            "tests/test_bridge.py",
        ],
    )

    cli.main()

    recorded = json.loads(capsys.readouterr().out)
    assert recorded["recorded"] is True
    monkeypatch.setattr(
        sys,
        "argv",
        ["codemesh-agent-access", "feedback", "summarize", str(repository)],
    )
    cli.main()
    summary = json.loads(capsys.readouterr().out)
    assert summary["packet_count"] == 1
    assert summary["priorities"][0]["task_family"] == "test-selection"


def _record(
    repository: Path,
    *,
    snapshot_id: str = "snapshot:test",
    fallback_reason: str | None = "Used rg after the expected edge was absent.",
    missed_paths: list[str] | None = None,
    validation_outcome: str = "failed",
    supersedes_feedback_ids: list[str] | None = None,
):
    return record_feedback(
        repository_root=repository,
        codemesh_root=repository,
        role="Primary",
        classification="diagnostic",
        confidence="high",
        project_id="project:onenine",
        checkout_id="checkout:primary",
        snapshot_id=snapshot_id,
        languages=["rust", "python", "python"],
        parser_profile="python-rust-v1",
        task_family="cross-language-impact",
        issue_category="missing-relationship",
        validation_outcome=validation_outcome,
        tools_attempted=["codemesh_get_context_package"],
        tools_called=["codemesh_get_context_package"],
        missed_paths=missed_paths or ["rust/src/lib.rs"],
        fallback_reason=fallback_reason,
        minimal_reproduction="Find the Python call into the exported Rust function.",
        expected_targets=["python/bridge.py", "rust/src/lib.rs"],
        proposed_correction="Resolve aliased PyO3 exports across language results.",
        supersedes_feedback_ids=supersedes_feedback_ids,
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
    (path / "src" / "app.py").write_text("print('test')\n", encoding="utf-8")
    if ignored:
        (path / ".gitignore").write_text("/.codemesh-feedback/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "test: fixture"], cwd=path, check=True)
    return path.resolve()
