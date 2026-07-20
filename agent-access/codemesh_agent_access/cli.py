from __future__ import annotations

import argparse
import asyncio
import json
import sys

import uvicorn

from .config import Settings
from . import evaluation, mcp, tools
from .formatting import format_context_package_for_agent


def main() -> None:
    parser = argparse.ArgumentParser(prog="codemesh-agent-access")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("rest", help="Run the REST API.")
    subcommands.add_parser("mcp", help="Run the MCP server over stdio.")
    subcommands.add_parser(
        "mcp-manifest", help="Print the MCP tool contract manifest JSON."
    )
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

    agent_eval_parser = eval_modes.add_parser(
        "agent", help="Run paired agent tasks with and without CodeMesh."
    )
    agent_eval_parser.add_argument("--suite", default="codemesh-agent")
    agent_eval_parser.add_argument("--model", required=True)
    agent_eval_parser.add_argument("--local-provider", choices=["lmstudio", "ollama"])
    agent_eval_parser.add_argument("--reasoning-effort", default="medium")
    agent_eval_parser.add_argument("--repetitions", type=int, default=3)
    agent_eval_parser.add_argument("--seed", type=int, default=42)
    agent_eval_parser.add_argument("--repository-root")
    agent_eval_parser.add_argument("--repository-id")
    agent_eval_parser.add_argument("--output-dir")
    agent_eval_parser.add_argument("--keep-raw-traces", action="store_true")
    agent_eval_parser.add_argument("--keep-workspaces", action="store_true")

    validate_eval_parser = eval_modes.add_parser(
        "validate", help="Validate an evaluation suite JSON file."
    )
    validate_eval_parser.add_argument("suite")
    schema_eval_parser = eval_modes.add_parser(
        "schema", help="Print an evaluation suite JSON Schema."
    )
    schema_eval_parser.add_argument("kind", choices=["live", "agent"])
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
        mcp.run()
        return

    if args.command == "mcp-manifest":
        print(json.dumps(mcp.tool_manifest(), indent=2))
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
                    )
                )
                print(json.dumps(report.model_dump(mode="json"), indent=2))
                raise SystemExit(0 if report.passed else 1)

            if args.eval_mode == "agent":
                suite, suite_path = evaluation.load_suite(args.suite, "agent")
                report = asyncio.run(
                    evaluation.run_agent_evaluation(
                        suite,
                        suite_path,
                        model=args.model,
                        local_provider=args.local_provider,
                        reasoning_effort=args.reasoning_effort,
                        repetitions=args.repetitions,
                        seed=args.seed,
                        repository_root=args.repository_root,
                        repository_id=args.repository_id,
                        output_dir=args.output_dir,
                        keep_raw_traces=args.keep_raw_traces,
                        keep_workspaces=args.keep_workspaces,
                    )
                )
                print(json.dumps(report.model_dump(mode="json"), indent=2))
                raise SystemExit(0 if report.passed else 1)
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
