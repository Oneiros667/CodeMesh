from __future__ import annotations

import asyncio
import json
import sys

import pytest

from codemesh_agent_access import cli, evaluation


def test_mcp_evaluation_suite_passes_fixture_scenarios() -> None:
    report = asyncio.run(evaluation.run_mcp_evaluations())
    payload = report.to_dict()

    assert payload["suite"] == "mcp-fixture"
    assert payload["passed"] is True
    assert {case["name"] for case in payload["cases"]} == {
        "tool guidance recommends freshness checks",
        "context search returns diagnostics and stable hits",
        "context package includes agent-ready metadata",
        "repository status exposes stale refresh guidance",
        "context package does not expose fixture secrets",
    }
    assert all(case["passed"] for case in payload["cases"])


def test_cli_eval_prints_report_and_exits_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "eval"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["suite"] == "mcp-fixture"
    assert payload["passed"] is True


def test_cli_eval_fixture_alias_preserves_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["codemesh-agent-access", "eval", "fixture"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["suite"] == "mcp-fixture"


def test_cli_eval_schema_and_validate_are_non_running_commands(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["codemesh-agent-access", "eval", "schema", "live"]
    )
    cli.main()
    assert json.loads(capsys.readouterr().out)["title"] == "LiveSuite"

    monkeypatch.setattr(
        sys,
        "argv",
        ["codemesh-agent-access", "eval", "validate", "codemesh-agent"],
    )
    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["kind"] == "agent"


def test_cli_eval_invalid_suite_exits_with_infrastructure_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["codemesh-agent-access", "eval", "validate", "missing-suite"],
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2
    assert json.loads(capsys.readouterr().err)["ok"] is False
