# Contributing to CodeMesh

CodeMesh is currently focused on source-grounded implementation discovery,
likely change-impact analysis, and validation selection for C#/.NET coding
agents. Proposed work should align with [Next Steps](docs/planning/next-steps.md) unless
the owner explicitly activates a deferred area.

The [Documentation Hub](docs/README.md) identifies current references,
operating guides, status, planning documents, and historical evidence.

## Development setup

Required tools are the .NET 10 SDK, Python 3.12 or newer, `uv`, and Git. Docker
Compose is needed only for live-store and end-to-end work.

```powershell
dotnet restore CodeMesh.sln --locked-mode
Set-Location agent-access
uv sync --locked
```

Copy `.env.example` to `.env` only for local services, set a unique development
password, and never commit the resulting file.

## Change discipline

- Keep changes focused and preserve unrelated work.
- Ground behavior and status claims in source, tests, or reviewed evidence.
- Do not include credentials, private source, customer/employer material,
  generated indexes, databases, model output, or raw evaluation traces.
- Keep online model providers opt-in. Normal development and CI must remain
  summary-free and deterministic.
- Add or update canonical documentation when behavior, commands, contracts, or
  architecture change.
- Use Conventional Commits when a commit is requested.

## Validation

Use the canonical risk-scaled commands and selection rules in
[Testing](docs/evaluation/testing.md). Run .NET commands serially because the solution
shares intermediate outputs. Use the end-to-end smoke path only for changes
that cross live stores, repository lifecycle, cleanup, Docker, or Agent Access
integration boundaries. Do not run provider-backed evaluation without explicit
authorization.

The full engineering policy is in
[Engineering Standards](docs/engineering/standards.md).
