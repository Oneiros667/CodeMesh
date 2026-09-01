# CodeMesh repository commands

This is the canonical index for supported contributor and coding-agent
commands. Use [Testing](docs/evaluation/testing.md) for risk-based check
selection, end-to-end variants, evaluation gates, and result interpretation.
Use the linked operating guides for ordered product or evaluation procedures.

Run commands from the repository root unless a section says otherwise. Run
.NET commands serially because projects share intermediate output directories.

## Deterministic verification

### .NET

```powershell
dotnet restore CodeMesh.sln --locked-mode
dotnet build CodeMesh.sln --no-restore
dotnet run --project tests/CodeMesh.Tests --no-restore
dotnet format CodeMesh.sln --verify-no-changes --no-restore
```

### Python Agent Access

Run from `agent-access`:

```powershell
uv sync --locked
uv run --no-sync pytest
uv run --no-sync ruff check . ../tools
uv run --no-sync ruff format --check . ../tools
uv run --no-sync python -m codemesh_agent_access eval
```

The last command is the deterministic in-process MCP fixture suite. It uses no
Docker service or model provider. Run both .NET and Python checks after changes
to shared contracts, serialization, lifecycle, integration, or end-to-end
behavior. A focused change may use only its affected surface when the handoff
states why the other suite was not required.

### Repository standards

```powershell
npx --yes markdownlint-cli2@0.23.1 "**/*.md"
python tools/check_markdown_links.py
python tools/check_publication_safety.py
python tools/check_github_workflows.py .github/workflows/baseline-standards.yml
git diff --check
```

Validate a proposed commit range when relevant:

```powershell
python tools/check_conventional_commit.py --range BASE..HEAD
```

The documentation, publication-safety, and workflow-policy checks are local
and read-only. The GitHub workflow definition and a local workflow-policy pass
are not evidence that hosted GitHub Actions passed.

## End-to-end verification

Use the PowerShell smoke path when changes affect live store wiring, Docker
services, repository lifecycle, cleanup, REST endpoints, or Agent Access
integration:

```powershell
.\scripts\e2e-smoke.ps1
```

The script uses disposable fixture state, but it starts local containers and
services. See [Testing](docs/evaluation/testing.md#end-to-end-smoke) for its
selection rules and variants.

## Local product health

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
docker compose ps
Invoke-RestMethod http://127.0.0.1:8088/health
```

These commands inspect the configured local environment. They do not establish
release, deployment, external acceptance, or production fitness.

## Operational and evaluation procedures

Use the controlling guide instead of treating isolated commands as authority:

- [MCP Setup](docs/guides/mcp-setup.md) for local services, ingestion, refresh,
  health, and MCP configuration;
- [Self-Analysis](docs/guides/self-analysis.md) for indexing and querying this
  repository; and
- [MCP Effectiveness Evaluation](docs/evaluation/mcp-effectiveness.md) for live,
  agent, comparison, and model-backed evaluation.

Live services, provider-backed runs, model spend, raw-trace retention, external
accounts, publication, release, deployment, and production mutation require
their own authority and evidence gates. The presence of a command in a guide
does not grant that authority.

### Summary-model qualification

The qualification runner uses the production summary prompt and parser. Start
from the checked-in synthetic suite and profile examples, then replace the
profile placeholders and use a separately reviewed, frozen corpus for real
qualification:

```powershell
dotnet run --project src/CodeMesh.Cli -- summaries qualify run `
  --suite docs/evaluation/assets/summary-qualification-suite.example.json `
  --profile <profile.json> `
  --private-output <private-archive.json> `
  --review-output <blinded-review-packet.json> `
  --summary-provider <ollama|lmstudio|openai> `
  --summary-model <exact-model-id>

dotnet run --project src/CodeMesh.Cli -- summaries qualify bind-retrieval `
  --archive <private-archive.json> `
  --baseline-live <no-summary-live-report.json> `
  --candidate-live <candidate-summary-live-report.json> `
  --assessment <reviewed-retrieval-assessment.json> `
  --ranking-identity <exact-shared-ranking-configuration> `
  --confirm-isolated-indexes `
  --output <retrieval-evidence.json>

dotnet run --project src/CodeMesh.Cli -- summaries qualify compile `
  --suite <frozen-suite.json> `
  --archive <private-archive.json> `
  --review <reviewer-a.json> `
  --review <reviewer-b.json> `
  --retrieval <retrieval-evidence.json> `
  --deployment <resource-or-cost-evidence.json> `
  --output <sanitized-report.json>

dotnet run --project src/CodeMesh.Cli -- summaries qualify compare `
  --candidate <candidate-report.json> `
  --reference <reference-report.json>
```

`run` refuses dirty CodeMesh checkouts and mismatched suite, profile, provider,
or model identities. Online runs additionally require
`--authorize-online-source`; that flag records the operator's explicit action
but does not replace source-governance, account, or spend approval. Output
paths use create-new semantics. Private archives and review packets contain
source or generated text and must remain in restricted evidence storage.
`compile` requires two complete blinded reviews bound to the same non-empty
disagreement-resolution record hash, a reviewed query-level retrieval
assessment bound to comparable live reports, and complete resource or online
cost evidence bound to the deployment profile. Missing or incompatible
evidence produces `invalid-run`, never a qualified result. The example suite is
a smoke fixture, not a sufficient qualification corpus. Example schemas for
review, retrieval-assessment, and deployment evidence are under
`docs/evaluation/assets/`.

## External advisory checks

Before publication or dependency changes, and only when network access is
appropriate, run:

```powershell
dotnet list CodeMesh.sln package --vulnerable --include-transitive
Set-Location agent-access
uv audit --locked
```

These results are time-dependent because they query external advisory data.
