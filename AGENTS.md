# AGENTS.md

## Project Context

CodeMesh's initial product wedge is source-grounded implementation discovery,
likely change-impact analysis, and validation selection for agents working in
C#/.NET repositories. The current milestone is reviewed evidence that CodeMesh
improves agent outcomes over normal repository exploration. Do not select broad
parser, SDLC, UI, model-provider, summary, portability, or agent-memory work as
the next task unless `docs/planning/next-steps.md` or explicit user direction activates
it.

Before planning larger CodeMesh work, review these repository notes:

- `docs/README.md` is the documentation hub and authority map.
- `docs/guides/agent-quickstart.md` routes AI agents through the repository.
- `docs/current/project-status.md` records current implementation and reviewed evidence.
- `docs/planning/next-steps.md` is the execution-order authority for future product work.
- `docs/current/architecture.md`, `docs/current/agent-access-contracts.md`, and source/tests
  define current component and interface behavior.
- `docs/evaluation/testing.md`, `docs/current/security-and-redaction.md`, and
  `docs/engineering/standards.md` define verification, safety, and completion
  discipline.

Treat `docs/planning/next-steps.md`,
`docs/planning/agent-integration-contract.md`,
`docs/planning/graph-intelligence-design.md`,
`docs/planning/method-load-and-retrieval-granularity.md`,
`docs/planning/summary-model-qualification.md`,
`docs/planning/repository-identity-and-snapshot-retention.md`, and
`docs/planning/sdlc-roadmap.md` as planning context, not implemented behavior.

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
- Keep current status in `docs/current/project-status.md`, future execution order in
  `docs/planning/next-steps.md`, and detailed proposals in their dedicated planning
  documents.

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
