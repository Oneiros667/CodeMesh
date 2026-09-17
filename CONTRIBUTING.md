# Contributing to CodeMesh

CodeMesh is currently focused on source-grounded implementation discovery,
likely change-impact analysis, and validation selection for C#/.NET coding
agents. Proposed work should align with [Next Steps](docs/planning/next-steps.md) unless
the owner explicitly activates a deferred area.

The [Documentation Hub](docs/README.md) identifies current references,
operating guides, status, planning documents, and historical evidence.
Supported repository commands are indexed in [`COMMANDS.md`](COMMANDS.md).

Start with the [Developer Handbook](docs/guides/developer-handbook.md) to learn
the architecture, domain vocabulary, and implementation flows. Use
[Development and Debugging](docs/guides/development-and-debugging.md) for local
diagnosis and [Making Changes](docs/guides/making-changes.md) to trace a change
across producers, consumers, contracts, and tests.

## Development setup

Required tools are the .NET 10 SDK, Python 3.12 or newer, `uv`, and Git. Docker
Compose is needed only for live-store and end-to-end work.

Use the locked .NET restore and Python Agent Access environment commands in
[`COMMANDS.md`](COMMANDS.md#deterministic-verification).

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
- Format pull-request titles and requested commits as Conventional Commits.

## Pull requests

- Keep each pull request focused and explain the problem, the chosen approach,
  and any intentionally excluded work.
- Complete the repository pull-request template and report each relevant check
  as passed, failed, skipped, or unavailable.
- Resolve review conversations and update the branch before squash merging.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in repository interactions.

## Validation

Use the supported invocations in [`COMMANDS.md`](COMMANDS.md) and the
risk-scaled selection rules in [Testing](docs/evaluation/testing.md). Run .NET
commands serially because the solution shares intermediate outputs. Use the
end-to-end smoke path only for changes that cross live stores, repository
lifecycle, cleanup, Docker, or Agent Access integration boundaries. Do not run
provider-backed evaluation without explicit authorization.

The full engineering policy is in
[Engineering Standards](docs/engineering/standards.md), with evidence and
authority boundaries in the
[Software Engineering Methodology](docs/engineering/methodology.md).
