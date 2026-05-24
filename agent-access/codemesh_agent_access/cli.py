from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from .config import Settings
from . import mcp, tools


def main() -> None:
    parser = argparse.ArgumentParser(prog="codemesh-agent-access")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("rest", help="Run the REST API.")
    subcommands.add_parser("mcp", help="Run the MCP server over stdio.")
    subcommands.add_parser("status", help="Print Agent Access status JSON.")
    search_parser = subcommands.add_parser("search", help="Search stored CodeMesh context.")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--kind", action="append", default=[])

    node_parser = subcommands.add_parser("get-node", help="Fetch a stored CodeMesh node.")
    node_parser.add_argument("node_id")
    node_parser.add_argument("--no-content", action="store_true")
    node_parser.add_argument("--no-neighbors", action="store_true")

    neighbors_parser = subcommands.add_parser("neighbors", help="Fetch relationships around a stored CodeMesh node.")
    neighbors_parser.add_argument("node_id")
    neighbors_parser.add_argument("--depth", type=int, default=1)

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
        result = asyncio.run(tools.search_context(args.query, limit=args.limit, kinds=args.kind))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "get-node":
        result = asyncio.run(
            tools.get_node(
                args.node_id,
                include_content=not args.no_content,
                include_neighbors=not args.no_neighbors,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    if args.command == "neighbors":
        result = asyncio.run(tools.get_neighbors(args.node_id, args.depth))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return

    parser.print_help()
