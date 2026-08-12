# AGENTS.md

## Project Context

CodeMesh's initial product wedge is source-grounded implementation discovery,
likely change-impact analysis, and validation selection for agents working in
C#/.NET repositories. The current milestone is reviewed evidence that CodeMesh
improves agent outcomes over normal repository exploration. Do not select broad
parser, SDLC, UI, model-provider, summary, portability, or agent-memory work as
the next task unless `docs/next-steps.md` or explicit user direction activates
it.

Before planning larger CodeMesh work, review these repository notes:

- `docs/agent-quickstart.md` is the preferred starting point for AI agents working in this repository.
- `docs/architecture.md` explains the current component boundaries and data flow.
- `docs/testing.md` explains verification commands and when to use the end-to-end smoke script.
- `docs/mcp-setup.md` explains how to run CodeMesh as an MCP service.
- `docs/self-analysis.md` explains how to index and query CodeMesh itself.
- `docs/security-and-redaction.md` records secret-handling expectations for agent-facing context.
- `docs/agent-prompts.md` contains example prompts for agents using CodeMesh through MCP.
- `docs/next-steps.md` tracks the prioritized backlog for making CodeMesh effective as an MCP service for AI agents.
- `docs/graph-intelligence-design.md` proposes relationship evidence, graph
  analysis, explicit agent outcome memory, parser tiers, and portable snapshots.
- `docs/summary-model-qualification.md` defines the planned qualification
  procedure for local and online ingestion summary models.
- `docs/repository-identity-and-snapshot-retention.md` defines the proposed
  multi-checkout identity, bounded snapshot retention, and shared-store
  requirements.
- `docs/sdlc-roadmap.md` tracks longer-term SDLC intelligence goals beyond implementation-code indexing.
- `docs/engineering/standards.md` defines change discipline, commit conventions,
  risk-scaled verification, documentation expectations, and the definition of
  done.

Treat `docs/next-steps.md`, `docs/graph-intelligence-design.md`,
`docs/summary-model-qualification.md`,
`docs/repository-identity-and-snapshot-retention.md`, and
`docs/sdlc-roadmap.md` as planning context, not implemented behavior.

## Agent Defaults

- Inspect `git status --short --branch` before editing and preserve unrelated
  work. Stage only task-related files or hunks when a commit is requested.
- Prefer the smallest coherent change and existing repository patterns. Keep
  implemented behavior, passing tests, reviewed evidence, release, deployment,
  and production authority distinct.
- Do not print `.env` contents, credentials, tokens, private keys, certificates, or local secret values.
- For implementation changes, run `dotnet run --project tests/CodeMesh.Tests` from the repo root unless clearly irrelevant.
- For Python Agent Access changes, also run `uv run pytest` from `agent-access`.
- For changes crossing .NET/Python contracts, serialization, lifecycle, or
  integration boundaries, run both suites.
- Use `.\scripts\e2e-smoke.ps1` when changes affect live store wiring, Docker services, repository lifecycle, cleanup, or Agent Access integration.
- Documentation-only changes usually do not require application tests. Run
  `npx --yes markdownlint-cli2@0.23.1 "**/*.md"`,
  `python tools/check_markdown_links.py`, and `git diff --check`.
- Use Conventional Commits for requested commits. Validate a proposed range
  with `python tools/check_conventional_commit.py --range BASE..HEAD` when
  relevant; do not install or alter Git hooks implicitly.
- Record consequential implemented architecture decisions under
  `docs/decisions/`; do not use decision records to present planning as current
  behavior.

## Completion And Authority

- Update canonical documentation when behavior, commands, contracts, setup,
  architecture, or verified status changes.
- Report passed, failed, skipped, and unavailable checks separately.
- Review the final diff for accidental or unrelated changes and report the
  final worktree state.
- A completed implementation does not authorize a commit, tag, release,
  publication, deployment, production mutation, external spend, or other live
  side effect unless the user explicitly requests it and the repository's
  relevant gates are satisfied.
- GitHub standards workflow success covers only the checks declared in
  `docs/engineering/github-actions.md`; it is not application, product-benefit,
  release, or deployment evidence.

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
