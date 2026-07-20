# MCP Effectiveness Evaluation

CodeMesh has three evaluation levels:

1. The deterministic fixture suite checks MCP behavior without stores or a model provider.
2. The live suite starts CodeMesh through MCP stdio and measures retrieval quality, freshness, safety, reliability, and latency against indexed data.
3. The agent suite runs paired control/treatment tasks with CodeMesh unavailable or available to the agent.

Normal tests never start live stores or invoke a paid agent.

## Deterministic Fixture Suite

From `agent-access`:

```powershell
uv run python -m codemesh_agent_access eval
uv run python -m codemesh_agent_access eval fixture
```

Both commands run the same five fixture scenarios and preserve the existing JSON report and exit behavior.

## Live MCP Benchmark

Start the stores, ingest a clean CodeMesh checkout, and confirm that repository status is fresh:

```powershell
docker compose up -d neo4j mongodb qdrant csharp-parser
dotnet run --project src/CodeMesh.Cli -- self ingest --skip-embeddings
cd agent-access
uv run python -m codemesh_agent_access eval live
```

The runner launches Agent Access itself over stdio, initializes an MCP client session, discovers tools, and calls the built-in `codemesh-live` suite. The default is one warm-up followed by three measured calls per case.

Useful options:

```powershell
uv run python -m codemesh_agent_access eval live --repository-id code_mesh --repetitions 5
uv run python -m codemesh_agent_access eval live --suite path/to/live-suite.json
uv run python -m codemesh_agent_access eval live --allow-stale
uv run python -m codemesh_agent_access eval live --keep-raw-traces
```

Without `--allow-stale`, the indexed commit must match a clean local checkout. An allowed stale run is marked non-comparable. The built-in suite does not require embeddings; running it again with embeddings or summaries enabled exposes their contribution in search diagnostics while preserving the same gold targets.

The report contains:

- Precision and recall at `k`, reciprocal rank, nDCG, and ranking stability.
- Expected relationship coverage.
- MCP startup time, per-call latency, and aggregate p50/p95 latency.
- Search modes, provider names, hit diagnostics, and tool-call reliability.
- Repository/index commit metadata and redaction-canary leakage count.

It intentionally omits snippets, credentials, environment values, and full MCP responses unless raw traces are requested.

## Agent A/B Benchmark

Agent evaluation requires:

- A clean Git checkout whose `HEAD` is the indexed CodeMesh commit.
- A working `codex` installation and existing authentication.
- An explicit model selection.
- Enough time and model budget for three runs per task and condition by default.

Run from the repository root or pass `--repository-root`:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval agent --model <model-id>
```

Optional controls:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --model <model-id> `
  --reasoning-effort medium `
  --repetitions 3 `
  --seed 42 `
  --output-dir ..\.codemesh-evals\manual-run
```

To evaluate a model served locally by LM Studio or Ollama, select the local
provider explicitly. The same provider and model are used for both conditions:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --model <local-model-id> `
  --local-provider lmstudio
```

Some Codex/local-provider combinations expose MCP tools through Responses API
namespace extensions that the local model server does not support. Use
`--codex-executable <path>` to select a compatible Codex build when validating
that combination. The runner detects older builds that lack
`--ignore-user-config` and gives local-provider runs a temporary isolated
`CODEX_HOME`; it never reads the user's Codex configuration in that mode.

Each control and treatment run receives the same task prompt, model, reasoning effort, sandbox, and isolated temporary clone. The control has an empty MCP server map. The treatment adds CodeMesh as a required stdio MCP server. The treatment prompt does not force MCP use, so the report can measure CodeMesh adoption as well as outcomes.

The treatment configuration allowlists CodeMesh read tools and does not expose repository deletion to the benchmark agent.

Answer tasks use structured responses and are graded against real file citations. Change tasks commit a known fault inside the temporary clone, verify that validation fails, let the agent repair it, and grade validation plus changed-path policy. The source checkout is never modified.

The result is `improved`, `regressed`, `neutral`, or `insufficient`. Correctness wins take priority. When correctness is tied, a 10% time or token improvement counts only when the other efficiency metric does not regress by more than 10%. Any treatment safety violation is a regression.

Default artifacts are written under `.codemesh-evals/` and contain the report, validation summaries, changed paths, and secret-scrubbed diffs. `--keep-raw-traces` additionally retains exact Codex JSONL, final messages, full diffs, and raw MCP output; treat that option as sensitive.

## Custom Suites

Built-in suites are named `codemesh-live` and `codemesh-agent`. A custom JSON path can be passed to `--suite`.

Inspect or validate the versioned formats with:

```powershell
uv run python -m codemesh_agent_access eval schema live
uv run python -m codemesh_agent_access eval schema agent
uv run python -m codemesh_agent_access eval validate path/to/suite.json
```

Retrieval targets use one or more exact selectors: `stable_key`, normalized repository-relative `file_path`, or `node_id`. Validation commands are argument arrays with explicit working directories and timeouts; suites do not execute shell command strings.

## Exit Codes And Automation

- `0`: the fixture/live gates passed, or the completed agent comparison was not a regression.
- `1`: evaluation gates failed or the agent treatment regressed.
- `2`: the suite, environment, freshness preflight, transport, or agent infrastructure was invalid.

Keep fixture tests in normal CI. Run live and agent evaluations only in explicit local or self-hosted jobs with their required stores and credentials.
