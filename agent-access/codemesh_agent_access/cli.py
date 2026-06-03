from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from .config import Settings
from . import mcp, tools
from .formatting import format_context_package_for_agent


def main() -> None:
    parser = argparse.ArgumentParser(prog="codemesh-agent-access")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("rest", help="Run the REST API.")
    subcommands.add_parser("mcp", help="Run the MCP server over stdio.")
    subcommands.add_parser("status", help="Print Agent Access status JSON.")
    search_parser = subcommands.add_parser("search", help="Search stored CodeMesh context.")
    search_parser.add_argument("query")
    search_parser.add_argument("--repository-id")
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--kind", action="append", default=[])
    search_parser.add_argument("--no-expand-context", action="store_true")
    search_parser.add_argument("--context-depth", type=int, default=4)
    search_parser.add_argument("--include-context-relationships", action="store_true")
    search_parser.add_argument("--context-relationship-limit", type=int, default=8)

    package_parser = subcommands.add_parser("package", help="Build an agent-ready context package.")
    package_parser.add_argument("query")
    package_parser.add_argument("--repository-id")
    package_parser.add_argument("--limit", type=int, default=8)
    package_parser.add_argument("--max-characters", type=int, default=12000)
    package_parser.add_argument("--kind", action="append", default=[])
    package_parser.add_argument("--context-depth", type=int, default=4)
    package_parser.add_argument("--no-content", action="store_true")
    package_parser.add_argument("--no-relationships", action="store_true")
    package_parser.add_argument("--relationship-limit", type=int, default=8)
    package_parser.add_argument("--caller-limit", type=int)
    package_parser.add_argument("--callee-limit", type=int)
    package_parser.add_argument("--read-limit", type=int)
    package_parser.add_argument("--write-limit", type=int)
    package_parser.add_argument("--contains-limit", type=int)
    package_parser.add_argument("--definition-limit", type=int)
    package_parser.add_argument("--uses-type-limit", type=int)
    package_parser.add_argument("--output", choices=["json", "agent"], default="json")

    symbols_parser = subcommands.add_parser("symbols", help="Search indexed CodeMesh symbols.")
    symbols_parser.add_argument("query")
    symbols_parser.add_argument("--repository-id")
    symbols_parser.add_argument("--limit", type=int, default=20)
    symbols_parser.add_argument("--kind", action="append", default=[])
    symbols_parser.add_argument("--no-declarations", action="store_true")

    node_parser = subcommands.add_parser("get-node", help="Fetch a stored CodeMesh node.")
    node_parser.add_argument("node_id")
    node_parser.add_argument("--repository-id")
    node_parser.add_argument("--no-content", action="store_true")
    node_parser.add_argument("--no-neighbors", action="store_true")

    neighbors_parser = subcommands.add_parser("neighbors", help="Fetch relationships around a stored CodeMesh node.")
    neighbors_parser.add_argument("node_id")
    neighbors_parser.add_argument("--repository-id")
    neighbors_parser.add_argument("--depth", type=int, default=1)

    repos_parser = subcommands.add_parser("repos", help="List indexed CodeMesh repositories.")
    repos_parser.add_argument("--limit", type=int, default=50)

    repo_parser = subcommands.add_parser("repo", help="Fetch an indexed CodeMesh repository.")
    repo_parser.add_argument("repository_id")

    runs_parser = subcommands.add_parser("runs", help="List CodeMesh ingestion runs.")
    runs_parser.add_argument("--repository-id")
    runs_parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    settings = Settings.from_env()

    if args.command == "rest":
        uvicorn.run("codemesh_agent_access.rest:app", host=settings.host, port=settings.port)
        return

    if args.command == "mcp":
        mcp.run()
        return

    if args.command == "status":
        result = asyncio.run(tools.status())
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "search":
        result = asyncio.run(
            tools.search_context(
                args.query,
                repository_id=args.repository_id,
                limit=args.limit,
                kinds=args.kind,
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
            )
        )
        if args.output == "agent":
            print(format_context_package_for_agent(result.data))
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
        result = asyncio.run(tools.get_neighbors(args.node_id, repository_id=args.repository_id, depth=args.depth))
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

    if args.command == "runs":
        result = asyncio.run(tools.list_ingestion_runs(repository_id=args.repository_id, limit=args.limit))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    parser.print_help()
