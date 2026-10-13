from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import sys
from pathlib import Path

import uvicorn

from .binding import binding_from_values
from .config import Settings
from . import __version__, evaluation, feedback, feedback_session, mcp, tools
from .formatting import format_context_package_for_agent
from .installer import (
    apply_installation_plan,
    create_installation_plan,
    load_installation_plan,
    write_installation_plan,
)
from .probe import (
    RuntimeProbeError,
    run_feedback_runtime_probe,
    run_runtime_probe,
    run_runtime_rejection_probe,
)


def _add_binding_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-id",
        help="Stable CodeMesh project id (or CODEMESH_PROJECT_ID).",
    )
    parser.add_argument(
        "--checkout-id",
        help="Stable CodeMesh checkout id (or CODEMESH_CHECKOUT_ID).",
    )
    parser.add_argument(
        "--repository-root",
        help="Absolute bound checkout root (or CODEMESH_REPOSITORY_ROOT).",
    )
    parser.add_argument(
        "--source-view-hash",
        help="Optional exact indexed source-view hash (or CODEMESH_SOURCE_VIEW_HASH).",
    )


def _add_feedback_session_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--feedback-session",
        help="Absolute active development-feedback session manifest path.",
    )
    parser.add_argument(
        "--feedback-session-sha256",
        help="Expected SHA-256 of the exact active session manifest file.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="codemesh-agent-access")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("rest", help="Run the REST API.")
    mcp_parser = subcommands.add_parser("mcp", help="Run the MCP server over stdio.")
    mcp_parser.add_argument(
        "--profile",
        choices=mcp.tool_profile_names(),
        default=mcp.DEFAULT_TOOL_PROFILE,
        help="Select the MCP tool surface (default: normal).",
    )
    _add_binding_arguments(mcp_parser)
    _add_feedback_session_arguments(mcp_parser)
    manifest_parser = subcommands.add_parser(
        "mcp-manifest", help="Print the MCP tool contract manifest JSON."
    )
    manifest_parser.add_argument(
        "--profile",
        choices=mcp.tool_profile_names(),
        default=mcp.DEFAULT_TOOL_PROFILE,
        help="Select the MCP tool surface (default: normal).",
    )
    _add_binding_arguments(manifest_parser)
    _add_feedback_session_arguments(manifest_parser)
    install_parser = subcommands.add_parser(
        "install",
        help="Plan or apply a reviewable checkout-bound MCP installation.",
    )
    install_actions = install_parser.add_subparsers(
        dest="install_action",
        required=True,
    )
    install_plan_parser = install_actions.add_parser(
        "plan",
        help="Print a reviewable installation plan without modifying the target.",
    )
    install_plan_parser.add_argument("--target-root", required=True)
    install_plan_parser.add_argument("--codemesh-root", required=True)
    install_plan_parser.add_argument("--project-id", required=True)
    install_plan_parser.add_argument("--checkout-id", required=True)
    install_plan_parser.add_argument("--source-view-hash")
    install_plan_parser.add_argument("--server-name", default="codemesh")
    install_plan_parser.add_argument(
        "--profile",
        choices=mcp.tool_profile_names(),
        default=mcp.DEFAULT_TOOL_PROFILE,
    )
    _add_feedback_session_arguments(install_plan_parser)
    install_plan_parser.add_argument(
        "--configuration-only",
        action="store_true",
        help="Plan only MCP configuration when repository guidance is managed elsewhere.",
    )
    install_plan_parser.add_argument("--output")
    install_apply_parser = install_actions.add_parser(
        "apply",
        help="Apply an unchanged reviewed plan with its explicit hash.",
    )
    install_apply_parser.add_argument("plan")
    install_apply_parser.add_argument("--approve-plan-hash", required=True)
    probe_parser = subcommands.add_parser(
        "mcp-probe",
        help="Launch and verify the exact MCP command in an applied installation plan.",
    )
    probe_parser.add_argument("--plan", required=True)
    probe_parser.add_argument("--timeout-seconds", type=int, default=30)
    probe_parser.add_argument(
        "--query", default="repository implementation entry points"
    )
    probe_parser.add_argument("--expected-path", action="append", default=[])
    rejection_probe_parser = subcommands.add_parser(
        "mcp-rejection-probe",
        help="Prove that an unsafe normal-profile binding fails closed.",
    )
    rejection_probe_parser.add_argument("--plan", required=True)
    rejection_probe_parser.add_argument("--timeout-seconds", type=int, default=30)
    rejection_probe_parser.add_argument("--project-id")
    rejection_probe_parser.add_argument("--checkout-id")
    rejection_probe_parser.add_argument("--repository-root")
    rejection_probe_parser.add_argument("--source-view-hash")
    rejection_probe_parser.add_argument(
        "--expected-substring", action="append", default=[]
    )
    feedback_parser = subcommands.add_parser(
        "feedback",
        help="Record, validate, or summarize sanitized CodeMesh feedback.",
    )
    feedback_actions = feedback_parser.add_subparsers(
        dest="feedback_action",
        required=True,
    )
    feedback_session_parser = feedback_actions.add_parser(
        "session",
        help="Plan, activate, inspect, or revoke a development feedback session.",
    )
    feedback_session_actions = feedback_session_parser.add_subparsers(
        dest="feedback_session_action",
        required=True,
    )
    feedback_session_plan = feedback_session_actions.add_parser(
        "plan",
        help="Create a reviewable immutable-session activation plan.",
    )
    feedback_session_plan.add_argument("--manifest-path", required=True)
    feedback_session_plan.add_argument("--codemesh-root", required=True)
    feedback_session_plan.add_argument("--codemesh-project-id", required=True)
    feedback_session_plan.add_argument("--codemesh-checkout-id", required=True)
    feedback_session_plan.add_argument(
        "--client-json",
        action="append",
        required=True,
        help=(
            "JSON object with project_id, checkout_id, repository_root, and "
            "reporter_role; repeat for each client."
        ),
    )
    feedback_session_plan.add_argument("--expires-at", required=True)
    feedback_session_plan.add_argument("--max-packets", type=int, default=100)
    feedback_session_plan.add_argument(
        "--max-requests-per-minute", type=int, default=20
    )
    feedback_session_plan.add_argument("--max-text-characters", type=int, default=500)
    feedback_session_plan.add_argument("--max-paths", type=int, default=32)
    feedback_session_plan.add_argument("--output")
    feedback_session_activate = feedback_session_actions.add_parser(
        "activate",
        help="Create the exact reviewed session manifest exclusively.",
    )
    feedback_session_activate.add_argument("plan")
    feedback_session_activate.add_argument("--approve-plan-hash", required=True)
    feedback_session_inspect = feedback_session_actions.add_parser(
        "inspect",
        help="Inspect a session without exposing client roots.",
    )
    feedback_session_inspect.add_argument("--manifest", required=True)
    feedback_session_inspect.add_argument("--manifest-sha256", required=True)
    feedback_session_revoke = feedback_session_actions.add_parser(
        "revoke",
        help="Close a session by creating an immutable revocation record.",
    )
    feedback_session_revoke.add_argument("--manifest", required=True)
    feedback_session_revoke.add_argument("--manifest-sha256", required=True)
    feedback_session_revoke.add_argument("--reason", required=True)
    feedback_record_parser = feedback_actions.add_parser(
        "record",
        help="Write one versioned packet to an ignored checkout outbox.",
    )
    feedback_record_parser.add_argument("--repository-root", required=True)
    feedback_record_parser.add_argument("--codemesh-root")
    feedback_record_parser.add_argument("--role", required=True)
    feedback_record_parser.add_argument(
        "--classification",
        choices=["diagnostic", "controlled-evaluation"],
        required=True,
    )
    feedback_record_parser.add_argument(
        "--confidence", choices=["low", "medium", "high"], required=True
    )
    feedback_record_parser.add_argument("--project-id", required=True)
    feedback_record_parser.add_argument("--checkout-id", required=True)
    feedback_record_parser.add_argument("--snapshot-id", required=True)
    feedback_record_parser.add_argument(
        "--language", action="append", required=True, dest="languages"
    )
    feedback_record_parser.add_argument("--parser-profile", required=True)
    feedback_record_parser.add_argument("--task-family", required=True)
    feedback_record_parser.add_argument(
        "--issue-category",
        choices=[
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
        required=True,
    )
    feedback_record_parser.add_argument(
        "--validation-outcome",
        choices=["passed", "failed", "not-run", "inconclusive"],
        required=True,
    )
    feedback_record_parser.add_argument("--tool-attempted", action="append", default=[])
    feedback_record_parser.add_argument("--tool-called", action="append", default=[])
    feedback_record_parser.add_argument("--helpful-path", action="append", default=[])
    feedback_record_parser.add_argument("--incorrect-path", action="append", default=[])
    feedback_record_parser.add_argument("--missed-path", action="append", default=[])
    feedback_record_parser.add_argument("--stale-path", action="append", default=[])
    feedback_record_parser.add_argument("--ambiguous-path", action="append", default=[])
    feedback_record_parser.add_argument("--fallback-reason")
    feedback_record_parser.add_argument("--minimal-reproduction")
    feedback_record_parser.add_argument(
        "--expected-target", action="append", default=[]
    )
    feedback_record_parser.add_argument("--proposed-correction")
    feedback_record_parser.add_argument(
        "--supersedes-feedback-id", action="append", default=[]
    )
    feedback_validate_parser = feedback_actions.add_parser(
        "validate", help="Validate packet schema, content id, and provenance shape."
    )
    feedback_validate_parser.add_argument("packets", nargs="+")
    feedback_summarize_parser = feedback_actions.add_parser(
        "summarize",
        help="Build a prioritized review packet from managed checkout outboxes.",
    )
    feedback_summarize_parser.add_argument("roots", nargs="+")
    feedback_summarize_parser.add_argument("--output")
    eval_parser = subcommands.add_parser(
        "eval", help="Run deterministic, live, or agent effectiveness evaluations."
    )
    eval_modes = eval_parser.add_subparsers(dest="eval_mode")
    eval_modes.add_parser("fixture", help="Run deterministic fixture scenarios.")

    live_eval_parser = eval_modes.add_parser(
        "live", help="Run a live MCP stdio retrieval benchmark."
    )
    live_eval_parser.add_argument("--suite", default="codemesh-live")
    live_eval_parser.add_argument("--repository-id")
    live_eval_parser.add_argument("--repetitions", type=int, default=3)
    live_eval_parser.add_argument("--warmup", type=int, default=1)
    live_eval_parser.add_argument("--allow-stale", action="store_true")
    live_eval_parser.add_argument("--keep-raw-traces", action="store_true")
    live_eval_parser.add_argument(
        "--capture-context-package-timings",
        action="store_true",
        help="Capture sanitized sideband context-package stage timings.",
    )
    live_eval_parser.add_argument("--output")

    agent_eval_parser = eval_modes.add_parser(
        "agent", help="Run paired agent tasks with and without CodeMesh."
    )
    agent_eval_parser.add_argument("--suite", default="codemesh-agent")
    agent_eval_parser.add_argument("--model")
    agent_eval_parser.add_argument("--local-provider", choices=["lmstudio", "ollama"])
    agent_eval_parser.add_argument("--codex-executable", default="codex")
    agent_eval_parser.add_argument(
        "--runner",
        choices=["codex", "capped-codex"],
        default="codex",
        help="Agent runner; capped-codex enforces complete-invocation accounting.",
    )
    agent_eval_parser.add_argument("--reasoning-effort", default="medium")
    agent_eval_parser.add_argument("--repetitions", type=int, default=3)
    agent_eval_parser.add_argument(
        "--max-reported-tokens",
        type=int,
        help=(
            "Required hard campaign cap using input + output + reasoning tokens; "
            "cached input is already included in input tokens."
        ),
    )
    agent_eval_parser.add_argument("--seed", type=int, default=42)
    agent_eval_parser.add_argument("--repository-root")
    agent_eval_parser.add_argument("--repository-id")
    agent_eval_parser.add_argument("--output-dir")
    agent_eval_parser.add_argument("--keep-raw-traces", action="store_true")
    agent_eval_parser.add_argument("--keep-workspaces", action="store_true")
    agent_eval_parser.add_argument(
        "--configured-plan",
        help="Reviewed and applied installation plan for a configured suite.",
    )
    agent_eval_parser.add_argument(
        "--configured-guidance-path",
        action="append",
        default=[],
        help="Committed repository guidance file to identify (default: AGENTS.md).",
    )
    agent_eval_parser.add_argument(
        "--configured-probe-query",
        default="repository implementation entry points",
    )
    agent_eval_parser.add_argument(
        "--configured-expected-path",
        action="append",
        default=[],
    )
    agent_eval_parser.add_argument(
        "--configured-probe-timeout-seconds",
        type=int,
        default=30,
    )
    agent_eval_parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Verify configured identity and positive/rejection probes without a model.",
    )
    agent_eval_parser.add_argument("--preflight-output")

    model_eval_parser = eval_modes.add_parser(
        "model", help="Benchmark a model on CodeMesh query and change scenarios."
    )
    model_actions = model_eval_parser.add_subparsers(dest="model_action")
    finalize_model_parser = model_actions.add_parser(
        "finalize", help="Apply blinded insight reviews to a model report."
    )
    finalize_model_parser.add_argument("report")
    finalize_model_parser.add_argument("--reviews", required=True)
    finalize_model_parser.add_argument("--output")
    model_eval_parser.add_argument("--suite", default="codemesh-model")
    model_eval_parser.add_argument("--model")
    model_eval_parser.add_argument(
        "--tier", choices=["query", "change", "all"], default="query"
    )
    model_eval_parser.add_argument("--local-provider", choices=["lmstudio", "ollama"])
    model_eval_parser.add_argument("--codex-executable", default="codex")
    model_eval_parser.add_argument("--reasoning-effort", default="medium")
    model_eval_parser.add_argument("--repetitions", type=int, default=3)
    model_eval_parser.add_argument("--seed", type=int, default=137)
    model_eval_parser.add_argument("--repository-root")
    model_eval_parser.add_argument("--repository-id")
    model_eval_parser.add_argument("--output-dir")
    model_eval_parser.add_argument("--temperature", type=float)
    model_eval_parser.add_argument("--top-p", type=float)
    model_eval_parser.add_argument("--top-k", type=int)
    model_eval_parser.add_argument("--context-length", type=int)
    model_eval_parser.add_argument("--chat-template-hash")
    model_eval_parser.add_argument("--quantization")
    model_eval_parser.add_argument("--hardware")
    model_eval_parser.add_argument("--provider")
    model_eval_parser.add_argument("--keep-raw-traces", action="store_true")
    model_eval_parser.add_argument("--keep-workspaces", action="store_true")

    compare_eval_parser = eval_modes.add_parser(
        "compare", help="Compare two or more reviewed model reports."
    )
    compare_eval_parser.add_argument("reports", nargs="+")
    compare_eval_parser.add_argument("--output")

    validate_eval_parser = eval_modes.add_parser(
        "validate", help="Validate an evaluation suite JSON file."
    )
    validate_eval_parser.add_argument("suite")
    schema_eval_parser = eval_modes.add_parser(
        "schema", help="Print an evaluation suite JSON Schema."
    )
    schema_eval_parser.add_argument("kind", choices=["live", "agent", "model"])
    subcommands.add_parser("status", help="Print Agent Access status JSON.")
    guidance_parser = subcommands.add_parser(
        "tool-guidance", help="Recommend CodeMesh tools for a task."
    )
    guidance_parser.add_argument(
        "task", nargs="?", help="Optional natural-language task to rank guidance."
    )
    search_parser = subcommands.add_parser(
        "search", help="Search stored CodeMesh context."
    )
    search_parser.add_argument("query")
    search_parser.add_argument("--repository-id")
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--kind", action="append", default=[])
    search_parser.add_argument(
        "--filter", action="append", default=[], metavar="KEY=VALUE"
    )
    search_parser.add_argument("--no-expand-context", action="store_true")
    search_parser.add_argument("--context-depth", type=int, default=4)
    search_parser.add_argument("--include-context-relationships", action="store_true")
    search_parser.add_argument("--context-relationship-limit", type=int, default=8)

    package_parser = subcommands.add_parser(
        "package", help="Build an agent-ready context package."
    )
    package_parser.add_argument("query")
    package_parser.add_argument("--repository-id")
    package_parser.add_argument("--limit", type=int, default=8)
    package_parser.add_argument("--max-characters", type=int, default=12000)
    package_parser.add_argument("--kind", action="append", default=[])
    package_parser.add_argument(
        "--filter", action="append", default=[], metavar="KEY=VALUE"
    )
    package_parser.add_argument("--context-depth", type=int, default=4)
    package_parser.add_argument("--no-content", action="store_true")
    package_parser.add_argument("--no-relationships", action="store_true")
    package_parser.add_argument("--no-repository", action="store_true")
    package_parser.add_argument("--relationship-limit", type=int, default=8)
    package_parser.add_argument("--caller-limit", type=int)
    package_parser.add_argument("--callee-limit", type=int)
    package_parser.add_argument("--read-limit", type=int)
    package_parser.add_argument("--write-limit", type=int)
    package_parser.add_argument("--contains-limit", type=int)
    package_parser.add_argument("--definition-limit", type=int)
    package_parser.add_argument("--uses-type-limit", type=int)
    package_parser.add_argument("--output", choices=["json", "agent"], default="json")

    symbols_parser = subcommands.add_parser(
        "symbols", help="Search indexed CodeMesh symbols."
    )
    symbols_parser.add_argument("query")
    symbols_parser.add_argument("--repository-id")
    symbols_parser.add_argument("--limit", type=int, default=20)
    symbols_parser.add_argument("--kind", action="append", default=[])
    symbols_parser.add_argument(
        "--filter", action="append", default=[], metavar="KEY=VALUE"
    )
    symbols_parser.add_argument("--no-declarations", action="store_true")

    node_parser = subcommands.add_parser(
        "get-node", help="Fetch a stored CodeMesh node."
    )
    node_parser.add_argument("node_id")
    node_parser.add_argument("--repository-id")
    node_parser.add_argument("--no-content", action="store_true")
    node_parser.add_argument("--no-neighbors", action="store_true")

    neighbors_parser = subcommands.add_parser(
        "neighbors", help="Fetch relationships around a stored CodeMesh node."
    )
    neighbors_parser.add_argument("node_id")
    neighbors_parser.add_argument("--repository-id")
    neighbors_parser.add_argument("--depth", type=int, default=1)
    neighbors_parser.add_argument("--relationship-kind", action="append", default=[])

    repos_parser = subcommands.add_parser(
        "repos", help="List indexed CodeMesh repositories."
    )
    repos_parser.add_argument("--limit", type=int, default=50)

    repo_parser = subcommands.add_parser(
        "repo", help="Fetch an indexed CodeMesh repository."
    )
    repo_parser.add_argument("repository_id")

    repo_status_parser = subcommands.add_parser(
        "repo-status", help="Fetch repository status and freshness diagnostics."
    )
    repo_status_parser.add_argument("repository_id")

    delete_repo_parser = subcommands.add_parser(
        "delete-repo", help="Delete an indexed CodeMesh repository from all stores."
    )
    delete_repo_parser.add_argument("repository_id")

    summaries_parser = subcommands.add_parser(
        "summaries", help="Fetch generated node summary coverage."
    )
    summaries_parser.add_argument("repository_id")

    runs_parser = subcommands.add_parser("runs", help="List CodeMesh ingestion runs.")
    runs_parser.add_argument("--repository-id")
    runs_parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    settings = Settings.from_env()

    if args.command == "rest":
        uvicorn.run(
            "codemesh_agent_access.rest:app", host=settings.host, port=settings.port
        )
        return

    if args.command == "mcp":
        try:
            binding = binding_from_values(
                args.project_id,
                args.checkout_id,
                args.repository_root,
                args.source_view_hash,
            )
            runtime = _feedback_runtime_from_args(args, binding)
            if runtime is None:
                mcp.run(profile=args.profile, binding=binding)
            else:
                mcp.run(
                    profile=args.profile,
                    binding=binding,
                    feedback_runtime=runtime,
                )
        except ValueError as exc:
            parser.error(str(exc))
        return

    if args.command == "mcp-manifest":
        try:
            binding = binding_from_values(
                args.project_id,
                args.checkout_id,
                args.repository_root,
                args.source_view_hash,
            )
            _feedback_runtime_from_args(args, binding)
        except ValueError as exc:
            parser.error(str(exc))
        print(
            json.dumps(
                mcp.tool_manifest(profile=args.profile, binding=binding),
                indent=2,
            )
        )
        return

    if args.command == "install":
        try:
            if args.install_action == "plan":
                binding = binding_from_values(
                    args.project_id,
                    args.checkout_id,
                    args.target_root,
                    args.source_view_hash,
                )
                assert binding is not None
                plan = create_installation_plan(
                    args.target_root,
                    args.codemesh_root,
                    binding,
                    server_name=args.server_name,
                    profile=args.profile,
                    include_onboarding=not args.configuration_only,
                    feedback_session_path=args.feedback_session,
                    feedback_session_sha256=args.feedback_session_sha256,
                )
                if args.output:
                    write_installation_plan(plan, args.output)
                print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
                return

            plan = load_installation_plan(args.plan)
            changed = apply_installation_plan(plan, args.approve_plan_hash)
            print(
                json.dumps(
                    {
                        "applied": True,
                        "plan_hash": plan.plan_hash,
                        "changed_files": changed,
                    },
                    indent=2,
                )
            )
        except (OSError, ValueError) as exc:
            print(json.dumps({"applied": False, "error": str(exc)}), file=sys.stderr)
            raise SystemExit(1) from exc
        return

    if args.command == "mcp-probe":
        try:
            plan = load_installation_plan(args.plan)
            if plan.profile in feedback_session.FEEDBACK_PROFILES:
                report = asyncio.run(
                    run_feedback_runtime_probe(
                        plan,
                        timeout_seconds=args.timeout_seconds,
                    )
                )
            else:
                report = asyncio.run(
                    run_runtime_probe(
                        plan,
                        timeout_seconds=args.timeout_seconds,
                        query=args.query,
                        expected_paths=args.expected_path,
                    )
                )
            print(json.dumps(report, indent=2, sort_keys=True))
        except (OSError, ValueError, RuntimeProbeError) as exc:
            print(json.dumps({"passed": False, "error": str(exc)}), file=sys.stderr)
            raise SystemExit(1) from exc
        return

    if args.command == "mcp-rejection-probe":
        try:
            plan = load_installation_plan(args.plan)
            report = asyncio.run(
                run_runtime_rejection_probe(
                    plan,
                    timeout_seconds=args.timeout_seconds,
                    project_id=args.project_id,
                    checkout_id=args.checkout_id,
                    repository_root=args.repository_root,
                    source_view_hash=args.source_view_hash,
                    expected_substrings=args.expected_substring,
                )
            )
            print(json.dumps(report, indent=2, sort_keys=True))
        except (OSError, ValueError, RuntimeProbeError) as exc:
            print(json.dumps({"passed": False, "error": str(exc)}), file=sys.stderr)
            raise SystemExit(1) from exc
        return

    if args.command == "feedback":
        try:
            if args.feedback_action == "session":
                if args.feedback_session_action == "plan":
                    clients = [
                        feedback_session.SessionParticipant.model_validate_json(value)
                        for value in args.client_json
                    ]
                    plan = feedback_session.create_session_plan(
                        manifest_path=args.manifest_path,
                        codemesh=feedback_session.SessionParticipant(
                            project_id=args.codemesh_project_id,
                            checkout_id=args.codemesh_checkout_id,
                            repository_root=args.codemesh_root,
                            reporter_role="maintainer",
                        ),
                        clients=clients,
                        expires_at=_parse_datetime(args.expires_at),
                        bounds=feedback_session.SessionBounds(
                            max_packets=args.max_packets,
                            max_requests_per_minute=args.max_requests_per_minute,
                            max_text_characters=args.max_text_characters,
                            max_paths=args.max_paths,
                        ),
                    )
                    if args.output:
                        feedback_session.write_session_plan(plan, args.output)
                    print(
                        json.dumps(
                            plan.model_dump(mode="json"), indent=2, sort_keys=True
                        )
                    )
                    return

                if args.feedback_session_action == "activate":
                    plan = feedback_session.load_session_plan(args.plan)
                    output = feedback_session.activate_session(
                        plan,
                        args.approve_plan_hash,
                    )
                    print(
                        json.dumps(
                            {
                                "activated": True,
                                "session_id": plan.manifest.payload.session_id,
                                "manifest_path": str(output),
                                "manifest_file_sha256": plan.manifest_file_sha256,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                    )
                    return

                if args.feedback_session_action == "inspect":
                    print(
                        json.dumps(
                            feedback_session.inspect_session(
                                args.manifest,
                                args.manifest_sha256,
                            ),
                            indent=2,
                            sort_keys=True,
                        )
                    )
                    return

                output = feedback_session.revoke_session(
                    args.manifest,
                    args.manifest_sha256,
                    reason=args.reason,
                )
                print(
                    json.dumps(
                        {"revoked": True, "revocation_path": str(output)},
                        indent=2,
                        sort_keys=True,
                    )
                )
                return

            if args.feedback_action == "record":
                packet, output = feedback.record_feedback(
                    repository_root=args.repository_root,
                    codemesh_root=args.codemesh_root,
                    role=args.role,
                    classification=args.classification,
                    confidence=args.confidence,
                    project_id=args.project_id,
                    checkout_id=args.checkout_id,
                    snapshot_id=args.snapshot_id,
                    languages=args.languages,
                    parser_profile=args.parser_profile,
                    task_family=args.task_family,
                    issue_category=args.issue_category,
                    validation_outcome=args.validation_outcome,
                    tools_attempted=args.tool_attempted,
                    tools_called=args.tool_called,
                    helpful_paths=args.helpful_path,
                    incorrect_paths=args.incorrect_path,
                    missed_paths=args.missed_path,
                    stale_paths=args.stale_path,
                    ambiguous_paths=args.ambiguous_path,
                    fallback_reason=args.fallback_reason,
                    minimal_reproduction=args.minimal_reproduction,
                    expected_targets=args.expected_target,
                    proposed_correction=args.proposed_correction,
                    supersedes_feedback_ids=args.supersedes_feedback_id,
                )
                print(
                    json.dumps(
                        {
                            "recorded": True,
                            "feedback_id": packet.feedback_id,
                            "path": str(output),
                        },
                        indent=2,
                    )
                )
                return

            if args.feedback_action == "validate":
                packets = [
                    feedback.validate_feedback(path).model_dump(mode="json")
                    for path in args.packets
                ]
                print(
                    json.dumps(
                        {
                            "valid": True,
                            "packet_count": len(packets),
                            "feedback_ids": [
                                packet["feedback_id"] for packet in packets
                            ],
                        },
                        indent=2,
                    )
                )
                return

            report = feedback.summarize_feedback(args.roots)
            payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(payload, encoding="utf-8")
            print(payload, end="")
        except (OSError, ValueError) as exc:
            print(
                json.dumps({"valid": False, "error": str(exc)}, indent=2),
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        return

    if args.command == "eval":
        try:
            if args.eval_mode in {None, "fixture"}:
                report = asyncio.run(evaluation.run_mcp_evaluations())
                print(json.dumps(report.to_dict(), indent=2))
                raise SystemExit(0 if report.passed else 1)

            if args.eval_mode == "schema":
                print(json.dumps(evaluation.suite_json_schema(args.kind), indent=2))
                return

            if args.eval_mode == "validate":
                suite, suite_path = evaluation.load_suite(args.suite)
                print(
                    json.dumps(
                        {
                            "valid": True,
                            "kind": suite.kind,
                            "name": suite.name,
                            "schema_version": suite.schema_version,
                            "path": str(suite_path),
                        },
                        indent=2,
                    )
                )
                return

            if args.eval_mode == "live":
                suite, _suite_path = evaluation.load_suite(args.suite, "live")
                report = asyncio.run(
                    evaluation.run_live_evaluation(
                        suite,
                        repository_id=args.repository_id,
                        repetitions=args.repetitions,
                        warmup=args.warmup,
                        allow_stale=args.allow_stale,
                        keep_raw_traces=args.keep_raw_traces,
                        capture_context_package_timings=(
                            args.capture_context_package_timings
                        ),
                    )
                )
                payload = json.dumps(report.model_dump(mode="json"), indent=2)
                if args.output:
                    output_path = Path(args.output)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(payload + "\n", encoding="utf-8")
                print(payload)
                raise SystemExit(0 if report.passed else 1)

            if args.eval_mode == "agent":
                suite, suite_path = evaluation.load_suite(args.suite, "agent")
                if args.max_reported_tokens is None:
                    raise ValueError(
                        "eval agent requires --max-reported-tokens so campaign "
                        "budgeting can fail closed."
                    )
                configured_plan = (
                    load_installation_plan(args.configured_plan)
                    if args.configured_plan
                    else None
                )
                configured_options = {
                    "configured_plan": configured_plan,
                    "configured_guidance_paths": args.configured_guidance_path or None,
                    "configured_probe_query": args.configured_probe_query,
                    "configured_expected_paths": args.configured_expected_path,
                    "configured_probe_timeout_seconds": (
                        args.configured_probe_timeout_seconds
                    ),
                }
                selected_runner = (
                    evaluation.CappedCodexRunner(args.codex_executable)
                    if args.runner == "capped-codex"
                    else evaluation.CodexRunner(args.codex_executable)
                )
                if args.preflight_only:
                    report = asyncio.run(
                        evaluation.run_agent_preflight(
                            suite,
                            max_reported_tokens=args.max_reported_tokens,
                            runner=selected_runner,
                            repository_root=args.repository_root,
                            repository_id=args.repository_id,
                            **configured_options,
                        )
                    )
                    payload = json.dumps(report, indent=2)
                    if args.preflight_output:
                        output_path = Path(args.preflight_output)
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_text(payload + "\n", encoding="utf-8")
                    print(payload)
                    return
                if not args.model:
                    raise ValueError(
                        "eval agent requires --model <id> unless --preflight-only is used."
                    )
                report = asyncio.run(
                    evaluation.run_agent_evaluation(
                        suite,
                        suite_path,
                        model=args.model,
                        local_provider=args.local_provider,
                        codex_executable=args.codex_executable,
                        reasoning_effort=args.reasoning_effort,
                        max_reported_tokens=args.max_reported_tokens,
                        repetitions=args.repetitions,
                        seed=args.seed,
                        repository_root=args.repository_root,
                        repository_id=args.repository_id,
                        output_dir=args.output_dir,
                        keep_raw_traces=args.keep_raw_traces,
                        keep_workspaces=args.keep_workspaces,
                        runner=selected_runner,
                        **configured_options,
                    )
                )
                print(json.dumps(report.model_dump(mode="json"), indent=2))
                raise SystemExit(0 if report.passed else 1)

            if args.eval_mode == "model":
                if args.model_action == "finalize":
                    report = evaluation.finalize_model_report(
                        args.report,
                        args.reviews,
                        output_path=args.output,
                    )
                    print(json.dumps(report.model_dump(mode="json"), indent=2))
                    raise SystemExit(0 if report.status == "reviewed" else 2)
                if not args.model:
                    raise ValueError("eval model requires --model <id>.")
                suite, suite_path = evaluation.load_suite(args.suite, "model-benchmark")
                report = asyncio.run(
                    evaluation.run_model_benchmark(
                        suite,
                        suite_path,
                        model=args.model,
                        tier=args.tier,
                        local_provider=args.local_provider,
                        codex_executable=args.codex_executable,
                        reasoning_effort=args.reasoning_effort,
                        repetitions=args.repetitions,
                        seed=args.seed,
                        repository_root=args.repository_root,
                        repository_id=args.repository_id,
                        output_dir=args.output_dir,
                        keep_raw_traces=args.keep_raw_traces,
                        keep_workspaces=args.keep_workspaces,
                        temperature=args.temperature,
                        top_p=args.top_p,
                        top_k=args.top_k,
                        context_length=args.context_length,
                        chat_template_hash=args.chat_template_hash,
                        quantization=args.quantization,
                        hardware=args.hardware,
                        provider=args.provider,
                    )
                )
                print(json.dumps(report.model_dump(mode="json"), indent=2))
                passed = (
                    report.qualified
                    if args.tier == "query"
                    else report.certified
                    if args.tier == "change"
                    else report.qualified and report.certified
                )
                raise SystemExit(0 if passed else 1)

            if args.eval_mode == "compare":
                report = evaluation.compare_model_reports(args.reports)
                payload = json.dumps(report.model_dump(mode="json"), indent=2)
                if args.output:
                    Path(args.output).write_text(payload, encoding="utf-8")
                print(payload)
                raise SystemExit(0 if report.comparable else 2)
        except (ValueError, OSError, evaluation.EvaluationInfrastructureError) as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            raise SystemExit(2) from exc

    if args.command == "status":
        result = asyncio.run(tools.status())
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "tool-guidance":
        result = asyncio.run(tools.tool_guidance(task=args.task))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "search":
        result = asyncio.run(
            tools.search_context(
                args.query,
                repository_id=args.repository_id,
                limit=args.limit,
                kinds=args.kind,
                filters=_parse_filters(args.filter),
                expand_context=not args.no_expand_context,
                context_depth=args.context_depth,
                include_context_relationships=args.include_context_relationships,
                context_relationship_limit=args.context_relationship_limit,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "package":
        result = asyncio.run(
            tools.get_context_package(
                args.query,
                repository_id=args.repository_id,
                limit=args.limit,
                max_characters=args.max_characters,
                kinds=args.kind,
                filters=_parse_filters(args.filter),
                context_depth=args.context_depth,
                include_content=not args.no_content,
                include_relationships=not args.no_relationships,
                relationship_limit=args.relationship_limit,
                caller_limit=args.caller_limit,
                callee_limit=args.callee_limit,
                read_limit=args.read_limit,
                write_limit=args.write_limit,
                contains_limit=args.contains_limit,
                definition_limit=args.definition_limit,
                uses_type_limit=args.uses_type_limit,
                include_repository=not args.no_repository,
            )
        )
        if args.output == "agent":
            print(
                format_context_package_for_agent(
                    result.data, max_characters=args.max_characters
                )
            )
            return
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "symbols":
        result = asyncio.run(
            tools.search_symbols(
                args.query,
                repository_id=args.repository_id,
                limit=args.limit,
                kinds=args.kind,
                filters=_parse_filters(args.filter),
                include_declarations=not args.no_declarations,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "get-node":
        result = asyncio.run(
            tools.get_node(
                args.node_id,
                repository_id=args.repository_id,
                include_content=not args.no_content,
                include_neighbors=not args.no_neighbors,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "neighbors":
        result = asyncio.run(
            tools.get_neighbors(
                args.node_id,
                repository_id=args.repository_id,
                depth=args.depth,
                relationship_kinds=args.relationship_kind,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "repos":
        result = asyncio.run(tools.list_repositories(limit=args.limit))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "repo":
        result = asyncio.run(tools.get_repository(args.repository_id))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "repo-status":
        result = asyncio.run(tools.get_repository_status(args.repository_id))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "delete-repo":
        result = asyncio.run(tools.delete_repository(args.repository_id))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "summaries":
        result = asyncio.run(tools.get_summary_coverage(args.repository_id))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "runs":
        result = asyncio.run(
            tools.list_ingestion_runs(
                repository_id=args.repository_id, limit=args.limit
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    parser.print_help()


def _parse_filters(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key:
            raise SystemExit(f"Invalid --filter value '{value}'. Expected KEY=VALUE.")

        filters[key] = item

    return filters


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError("Session timestamp must include a timezone.")
    return parsed


def _feedback_runtime_from_args(
    args: argparse.Namespace,
    binding,
):
    manifest = getattr(args, "feedback_session", None)
    expected_hash = getattr(args, "feedback_session_sha256", None)
    profile = args.profile
    if profile in feedback_session.FEEDBACK_PROFILES:
        if binding is None or not manifest or not expected_hash:
            raise ValueError(
                "Feedback MCP profiles require --feedback-session, "
                "--feedback-session-sha256, and a complete repository binding."
            )
        return feedback_session.create_session_runtime(
            manifest,
            expected_hash,
            profile=profile,
            binding=binding,
        )
    if manifest or expected_hash:
        raise ValueError("Feedback session options require a feedback MCP profile.")
    return None
