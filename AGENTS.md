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
- `COMMANDS.md` is the canonical repository command index, while
  `docs/evaluation/testing.md` defines risk-based check selection.
- `docs/current/project-status.md` records current implementation and reviewed evidence.
- `docs/planning/next-steps.md` is the execution-order authority for future product work.
- `docs/current/architecture.md`, `docs/current/agent-access-contracts.md`, and source/tests
  define current component and interface behavior.
- `docs/evaluation/testing.md`, `docs/current/security-and-redaction.md`, and
  `docs/engineering/standards.md` define verification, safety, and completion
  discipline.
- `docs/engineering/methodology.md` defines evidence, authority, and
  reusable-control admission boundaries.

Treat `docs/planning/next-steps.md`,
`docs/planning/agent-integration-contract.md`,
`docs/planning/graph-intelligence-design.md`,
`docs/planning/method-load-and-retrieval-granularity.md`,
`docs/planning/summary-model-qualification.md`,
`docs/planning/repository-identity-and-snapshot-retention.md`, and
`docs/planning/sdlc-roadmap.md` as planning context, not implemented behavior.

## Agent Defaults

- Inspect `git status --short --branch` before editing and preserve unrelated
  work. Stage only task-related files or hunks for each commit.
- Prefer the smallest coherent change and existing repository patterns. Keep
  implemented behavior, passing tests, reviewed evidence, release, deployment,
  and production authority distinct.
- Do not print `.env` contents, credentials, tokens, private keys, certificates, or local secret values.
- Use the supported invocations in `COMMANDS.md` and the risk map in
  `docs/evaluation/testing.md`; do not improvise weaker substitutes for an
  unavailable required check.
- For changes crossing .NET/Python contracts, serialization, lifecycle, or
  integration boundaries, run both suites.
- Use the end-to-end smoke path when changes affect live store wiring, Docker
  services, repository lifecycle, cleanup, or Agent Access integration.
- Documentation-only changes usually do not require application tests; run the
  repository standards checks listed in `COMMANDS.md`.
- Use Conventional Commits. Validate a proposed range
  with the checker listed in `COMMANDS.md` when relevant; do not install or
  alter Git hooks implicitly.
- Record consequential implemented architecture decisions under
  `docs/decisions/`; do not use decision records to present planning as current
  behavior.
- Keep current status in `docs/current/project-status.md`, future execution order in
  `docs/planning/next-steps.md`, and detailed proposals in their dedicated planning
  documents.

## Development Feedback Sessions

- Development-feedback MCP profiles are available only through the explicit,
  reviewed session procedure in `docs/guides/mcp-setup.md`. Do not create or
  activate a session unless the user asks for that operational action.
- When acting as the CodeMesh maintainer in an active session, start with
  `codemesh_list_feedback`, retrieve the selected exact id with
  `codemesh_get_feedback`, and reproduce the report read-only.
- Use `codemesh_prepare_feedback_resolution` to validate and hash the smallest
  proposed change. Do not edit source until a human explicitly approves the
  exact feedback ids and returned plan hash. An agent-supplied confirmation is
  not human approval.
- After approval, preserve normal completion discipline. A passing client
  recheck must append a new packet that names the original failure in
  `supersedes_feedback_ids`; do not edit or delete either packet.

## Completion And Authority

- Once a unit of work has been completed, commit the relevant files. Work is
  complete when:
  - Implementation is complete.
  - Tests have been updated, and changes verified through testing.
  - Documentation has been updated.
- Update canonical documentation when behavior, commands, contracts, setup,
  architecture, or verified status changes.
- Use the narrowest truthful evidence state defined in
  `docs/engineering/methodology.md`; one state never implies a later state.
- Report passed, failed, skipped, and unavailable checks separately.
- Review the final diff for accidental or unrelated changes and report the
  final worktree state.
- A completed unit of work and its commit do not authorize a tag, release,
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
