from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from codemesh_agent_access.evaluation import agent, benchmark
from codemesh_agent_access.evaluation.codex import (
    REPORTED_TOKEN_ACCOUNTING_ID,
    AgentRunnerCapabilities,
)
from codemesh_agent_access.evaluation.models import (
    AgentSuite,
    ModelBenchmarkSuite,
    load_suite,
)
from codemesh_agent_access.evaluation.paths import (
    managed_artifact_path,
    resolve_setup_patch,
)


@pytest.mark.parametrize(
    "identifier",
    [
        "",
        ".",
        "..",
        "../escape",
        "/absolute",
        "a/b",
        "a\\b",
        "C:drive",
        "item:stream",
        "trailing.",
        "NUL",
        "con.txt",
        "LPT1",
        "line\nbreak",
    ],
)
@pytest.mark.parametrize("kind", ["task", "question", "change"])
def test_artifact_identifiers_reject_cross_platform_path_syntax(identifier, kind):
    agent_suite, _ = load_suite("codemesh-agent", "agent")
    model_suite, _ = load_suite("codemesh-model", "model-benchmark")
    item = {
        "task": agent_suite.tasks[0],
        "question": model_suite.questions[0],
        "change": model_suite.change_scenarios[0],
    }[kind]
    payload = item.model_dump()
    payload["id"] = identifier
    with pytest.raises(ValidationError):
        type(item).model_validate(payload)


def test_suites_reject_case_insensitive_artifact_collisions():
    suite, _ = load_suite("codemesh-agent", "agent")
    payload = suite.model_dump()
    duplicate = dict(payload["tasks"][0], id=payload["tasks"][0]["id"].upper())
    payload["tasks"].append(duplicate)
    with pytest.raises(ValidationError, match="unique ignoring case"):
        AgentSuite.model_validate(payload)

    model_suite, _ = load_suite("codemesh-model", "model-benchmark")
    payload = model_suite.model_dump()
    payload["change_scenarios"][0]["id"] = payload["questions"][0]["id"]
    with pytest.raises(ValidationError, match="unique ignoring case"):
        ModelBenchmarkSuite.model_validate(payload)


@pytest.mark.parametrize(
    "relative",
    [
        "../outside.patch",
        "/tmp/outside.patch",
        "C:/outside.patch",
        "patches\\outside.patch",
        "patches/../outside.patch",
        "a:stream",
    ],
)
def test_patch_names_reject_escape_syntax_before_file_access(tmp_path, relative):
    with pytest.raises(ValueError, match="suite-relative"):
        resolve_setup_patch(tmp_path / "suite.json", relative)


def test_patch_resolution_accepts_contained_files_and_rejects_link_escape(tmp_path):
    suite = tmp_path / "suite"
    (suite / "patches").mkdir(parents=True)
    patch = suite / "patches" / "fault with spaces.patch"
    patch.write_text("fixture patch", encoding="utf-8")
    assert (
        resolve_setup_patch(suite / "suite.json", "patches/fault with spaces.patch")
        == patch
    )

    outside = tmp_path / "outside.patch"
    outside.write_text("must not be applied", encoding="utf-8")
    _symlink(suite / "escape.patch", outside)
    with pytest.raises(ValueError, match="within its suite"):
        resolve_setup_patch(suite / "suite.json", "escape.patch")
    with pytest.raises(ValueError, match="accessible"):
        resolve_setup_patch(suite / "suite.json", "missing.patch")


@pytest.mark.parametrize("directory", ["workspaces", ".runtime", "answer-1-treatment"])
def test_generated_artifacts_reject_existing_symlink_escape(tmp_path, directory):
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    _symlink(root / directory, outside)
    with pytest.raises(ValueError, match="escapes"):
        managed_artifact_path(root, directory, "result.json")
    assert list(outside.iterdir()) == []


def test_operator_selected_artifact_root_may_resolve_to_a_directory(tmp_path):
    root = tmp_path / "selected-root"
    root.mkdir()
    alias = tmp_path / "alias"
    _symlink(alias, root)
    assert (
        managed_artifact_path(alias, "answer", "result.json")
        == root / "answer" / "result.json"
    )


def test_agent_rejects_mutated_identifier_before_preflight_or_runner(
    monkeypatch, tmp_path
):
    suite, path = load_suite("youtube-downloader-agent", "agent")
    suite.tasks[0].id = "../escape"
    monkeypatch.setattr(agent, "_prepare_agent_context", _unexpected_effect)
    runner = _unused_capped_runner()
    with pytest.raises(ValueError, match="safe path segments"):
        asyncio.run(
            agent.run_agent_evaluation(
                suite, path, model="unused", max_reported_tokens=100, runner=runner
            )
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mode", ["agent", "model"])
def test_all_setup_patches_are_checked_before_any_repository_or_model_work(
    monkeypatch, tmp_path, mode
):
    model_suite, original_path = load_suite("codemesh-model", "model-benchmark")
    copied = tmp_path / "suites"
    shutil.copytree(original_path.parent, copied)
    outside = tmp_path / "outside.patch"
    outside.write_text("must not be read or applied", encoding="utf-8")
    _symlink(copied / "escape.patch", outside)
    monkeypatch.setattr(agent, "_prepare_agent_context", _unexpected_effect)
    monkeypatch.setattr(benchmark, "_git_root", _unexpected_effect)

    if mode == "agent":
        suite, _ = load_suite("codemesh-agent", "agent")
        suite.tasks[-1].setup_patch = "escape.patch"
        pending = agent.run_agent_evaluation(
            suite,
            copied / "codemesh-agent.json",
            model="unused",
            max_reported_tokens=100,
            runner=_unused_capped_runner(),
        )
    else:
        model_suite.change_scenarios[-1].setup_patch = "escape.patch"
        pending = benchmark.run_model_benchmark(
            model_suite,
            copied / original_path.name,
            model="unused",
            runner=_unused_capped_runner(),
        )
    with pytest.raises(ValueError, match="within its suite"):
        asyncio.run(pending)


def test_suite_loader_rejects_patch_links_before_returning_a_runnable_suite(tmp_path):
    suite, _ = load_suite("codemesh-agent", "agent")
    outside = tmp_path / "outside.patch"
    outside.write_text("not an accepted patch", encoding="utf-8")
    directory = tmp_path / "suite"
    directory.mkdir()
    _symlink(directory / "escape.patch", outside)
    payload = suite.model_dump()
    payload["tasks"] = [payload["tasks"][0]]
    payload["tasks"][0]["setup_patch"] = "escape.patch"
    path = directory / "suite.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="within its suite"):
        load_suite(path, "agent")


def test_validation_argv_preserves_shell_metacharacters_as_literal_arguments(tmp_path):
    marker = tmp_path / "must-not-exist"
    argument = f"literal; touch {marker}; $(touch {marker})"
    result = agent._run_command(
        [
            sys.executable,
            "-c",
            "import json, sys; print(json.dumps(sys.argv[1:]))",
            argument,
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == [argument]
    assert not marker.exists()


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as exc:
        pytest.skip(f"This platform cannot create the required symlink fixture: {exc}")


def _unexpected_effect(*args, **kwargs):
    raise AssertionError(
        "Unsafe suite reached repository preparation or model execution"
    )


def _unused_capped_runner():
    return SimpleNamespace(
        capabilities=AgentRunnerCapabilities(
            hard_reported_token_cap=True,
            reported_token_accounting=REPORTED_TOKEN_ACCOUNTING_ID,
            runner_id="unused-fixture",
        ),
        run=_unexpected_effect,
    )


@pytest.mark.parametrize("kind", ["agent", "model-benchmark"])
@pytest.mark.parametrize("name", ["../escape", "/absolute", "a\\b", "CON"])
def test_suite_name_cannot_escape_default_artifact_root(kind, name):
    built_in = "codemesh-agent" if kind == "agent" else "codemesh-model"
    suite, _ = load_suite(built_in, kind)
    payload = suite.model_dump()
    payload["name"] = name
    with pytest.raises(ValidationError):
        type(suite).model_validate(payload)


def test_mutated_suite_name_rejected_before_preflight(monkeypatch):
    suite, path = load_suite("youtube-downloader-agent", "agent")
    suite.name = "../escape"
    monkeypatch.setattr(agent, "_prepare_agent_context", _unexpected_effect)
    with pytest.raises(ValueError, match="safe path segments"):
        asyncio.run(
            agent.run_agent_evaluation(
                suite,
                path,
                model="unused",
                max_reported_tokens=100,
                runner=_unused_capped_runner(),
            )
        )


def test_codex_launch_preserves_selected_executable_and_literal_arguments(
    monkeypatch, tmp_path
):
    from codemesh_agent_access.evaluation import codex

    captured = []
    executable = str(tmp_path / "selected codex;literal")
    payload = '$(touch never-created); & echo "literal"'

    class Process:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def spawn(*argv, **kwargs):
        captured.append((argv, kwargs))
        return Process()

    monkeypatch.setattr(codex.asyncio, "create_subprocess_exec", spawn)
    runner = codex.CodexRunner(executable, supports_ignore_user_config=True)
    request = codex.AgentRunRequest(
        prompt=payload,
        cwd=tmp_path,
        condition="control",
        model=payload,
        reasoning_effort="medium",
        sandbox="read-only",
        timeout_seconds=5,
        mcp_cwd=tmp_path,
    )
    asyncio.run(runner.run(request))
    argv, options = captured[0]
    assert argv[0] == executable
    assert argv[-1] == payload
    assert argv[argv.index("--model") + 1] == payload
    assert options["cwd"] == tmp_path
    assert "shell" not in options
    assert len(captured) == 1
