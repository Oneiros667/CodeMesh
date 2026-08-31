# Agent Quickstart

Document type: repository navigation guide

This is the preferred starting point for coding agents working in CodeMesh.

## Read Order

1. [`AGENTS.md`](../../AGENTS.md) for operating rules and authority boundaries.
2. [Documentation Hub](../README.md) for document ownership and classification.
3. [`COMMANDS.md`](../../COMMANDS.md) for supported repository commands and
   [Software Engineering Methodology](../engineering/methodology.md) for
   evidence and authority boundaries.
4. [Project Status](../current/project-status.md) for current implementation and evidence.
5. [Architecture](../current/architecture.md) and
   [Agent Access Contracts](../current/agent-access-contracts.md) for current behavior.
6. [Next Steps](../planning/next-steps.md) only when selecting future product work.

Use [MCP Setup](mcp-setup.md) and [Self-Analysis](self-analysis.md) when
configuring or dogfooding CodeMesh. Use [Testing](../evaluation/testing.md) to select
verification.

## Product Boundary

CodeMesh is a local-first context and likely change-impact service for coding
agents. Its initial wedge is C#/.NET implementation discovery, impact
navigation, and validation selection. Broader parser, SDLC, summary,
portability, shared-store, UI, and memory work remains secondary unless the
execution order or the user activates it.

## Task Routing

| Task | Start in |
| --- | --- |
| REST, MCP, Python CLI, ranking, formatting, or context packages | `agent-access/codemesh_agent_access` and `docs/current/agent-access-contracts.md` |
| .NET Agent Access client contracts | `src/CodeMesh.Domain/Contracts` and `src/CodeMesh.Control/AgentAccess` |
| Ingestion, cleanup, embeddings, or summaries | `src/CodeMesh.Ingestion` |
| C# semantic graph behavior | `src/CodeMesh.Parser.CSharp` |
| Python, Markdown, or deployment parsing | The matching `src/CodeMesh.Parser.*` project |
| Store reads, writes, or cleanup | `src/CodeMesh.Storage` |
| CLI workflow or repository discovery | `src/CodeMesh.Cli` and `src/CodeMesh.Control` |
| Product direction | `docs/current/project-status.md`, then `docs/planning/next-steps.md` |

## Working Rules

- Inspect the current checkout and preserve unrelated work before editing.
- Treat source and tests as implementation authority.
- Treat proposals as unimplemented until source, contracts, and verification
  establish otherwise.
- Keep generated summaries optional and normal validation provider-free.
- Never print `.env` values, credentials, tokens, keys, certificates, or local
  secrets.
- Report passed, failed, skipped, and unavailable checks separately.
- Use supported invocations from [`COMMANDS.md`](../../COMMANDS.md) and select
  the smallest risk-appropriate verification path in
  [Testing](../evaluation/testing.md).
