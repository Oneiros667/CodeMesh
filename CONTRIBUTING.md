# Contributing to CodeMesh

CodeMesh is currently focused on source-grounded implementation discovery,
likely change-impact analysis, and validation selection for C#/.NET coding
agents. Proposed work should align with [Next Steps](docs/next-steps.md) unless
the owner explicitly activates a deferred area.

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

Run .NET commands serially because the solution shares intermediate outputs:

```powershell
dotnet restore CodeMesh.sln --locked-mode
dotnet build CodeMesh.sln --no-restore
dotnet run --project tests/CodeMesh.Tests --no-restore
dotnet format CodeMesh.sln --verify-no-changes --no-restore
```

For Agent Access changes:

```powershell
Set-Location agent-access
uv sync --locked
uv run --no-sync pytest
uv run --no-sync ruff check . ../tools
uv run --no-sync ruff format --check . ../tools
uv run --no-sync python -m codemesh_agent_access eval
```

For documentation and repository controls:

```powershell
npx --yes markdownlint-cli2@0.23.1 "**/*.md"
python tools/check_markdown_links.py
python tools/check_publication_safety.py
git diff --check
```

Use the end-to-end smoke path only for changes that cross live store,
repository lifecycle, cleanup, Docker, or Agent Access integration boundaries.
Do not run provider-backed evaluation without explicit authorization.

The full engineering policy is in
[Engineering Standards](docs/engineering/standards.md).
