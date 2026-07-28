# AGENTS.md

## Project Context

Before planning larger CodeMesh work, review these repository notes:

- `docs/agent-quickstart.md` is the preferred starting point for AI agents working in this repository.
- `docs/architecture.md` explains the current component boundaries and data flow.
- `docs/testing.md` explains verification commands and when to use the end-to-end smoke script.
- `docs/mcp-setup.md` explains how to run CodeMesh as an MCP service.
- `docs/self-analysis.md` explains how to index and query CodeMesh itself.
- `docs/security-and-redaction.md` records secret-handling expectations for agent-facing context.
- `docs/agent-prompts.md` contains example prompts for agents using CodeMesh through MCP.
- `docs/next-steps.md` tracks the prioritized backlog for making CodeMesh effective as an MCP service for AI agents.
- `docs/sdlc-roadmap.md` tracks longer-term SDLC intelligence goals beyond implementation-code indexing.

Treat `docs/next-steps.md` and `docs/sdlc-roadmap.md` as planning context, not implemented behavior.

## Agent Defaults

- Do not print `.env` contents, credentials, tokens, private keys, certificates, or local secret values.
- For implementation changes, run `dotnet run --project tests/CodeMesh.Tests` from the repo root unless clearly irrelevant.
- For Python Agent Access changes, also run `uv run pytest` from `agent-access`.
- Use `.\scripts\e2e-smoke.ps1` when changes affect live store wiring, Docker services, repository lifecycle, cleanup, or Agent Access integration.
- Documentation-only changes usually do not require tests; check links and formatting manually.

## Environment

This repo is usually worked on from JetBrains Rider on Windows with PowerShell.

Available CLI tools:

- `rg`
- `git`
- `dotnet` with .NET 10 SDK
- `python` 3.14
- `uv`
- `ruff`
- `pytest`
- `jq`
- `gh`
- `docker`
- `docker compose`
- `7z`

Notes:

- If a newly installed command is not visible, refresh PATH from persisted values:

  ```powershell
  $env:Path = "$([Environment]::GetEnvironmentVariable('Path', 'Machine'));$([Environment]::GetEnvironmentVariable('Path', 'User'))"
  ```
