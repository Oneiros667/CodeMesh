# MCP Effectiveness Evaluation

CodeMesh has four evaluation levels:

1. The deterministic fixture suite checks MCP behavior without stores or a model provider.
2. The live suite starts CodeMesh through MCP stdio and measures retrieval quality, freshness, safety, reliability, and latency against indexed data.
3. The agent suite runs paired control/treatment tasks with CodeMesh unavailable or available to the agent.
4. The model benchmark measures query-answering capability and, for qualifying models, paired repair capability.

Normal tests never start live stores or invoke a paid agent.

Ingestion summary models require a separate qualification because bounded
summary generation is not equivalent to autonomous MCP tool use or repair
ability. `docs/summary-model-qualification.md` defines a provider-neutral
procedure for local and online candidates, including factual accuracy,
reliability, speed, token efficiency, privacy, cost, and downstream retrieval
gates. The dedicated qualification runner described there is planned and is not
an available CLI command yet.

## Product Decision Role

Evaluation is the near-term product milestone, not only a regression facility.
CodeMesh should advance beyond its initial C#/.NET wedge only after controlled
evidence shows that agents perform better with CodeMesh than with normal
repository exploration.

The current evidence position is deliberately conservative:

- passing fixtures establish tool and response behavior, not agent usefulness;
- retained agent runs on older commits do not establish a positive outcome;
- no current reviewed baseline covers both CodeMesh and a representative
  external C# repository; and
- no summary model is qualified, so the core product baseline must run without
  generated summaries.

The next product-proof campaign should freeze a clean source and index identity,
run the live suite, and then compare repeated control/treatment tasks for:

- implementation discovery;
- likely change-impact analysis; and
- test or validation selection.

Reports must compare correctness, safety, freshness, citations, elapsed time,
tokens, tool calls, adoption, and correction loops. A tied-correctness result is
useful only when time or token use improves by at least the existing 10% agent
comparison threshold and the other efficiency metric does not regress by more
than 10%. Product evidence should repeat across more than one task family and
repository; a passing harness or one favorable run is not sufficient.

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

## Model Benchmark

The built-in `codemesh-model` suite compares models on repository work rather
than general conversation. It contains 24 query questions across eight
capability families and nine trusted repair scenarios across three families.
Every family has easy, medium, and hard variants. Difficulty increases through
reasoning depth, state transitions, failure behavior, and ambiguity rather than
prompt length.

Run Tier 1 first. Three repetitions produce 72 model executions:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval model --model <model-id> --tier query
```

Only models meeting the Tier 1 gates should proceed to the paired change tier.
Three repetitions of nine scenarios in control and treatment produce 54 more
executions. `--tier all` runs all 126 executions:

```powershell
uv run python -m codemesh_agent_access eval model --model <model-id> --tier change
uv run python -m codemesh_agent_access eval model --model <model-id> --tier all
```

The live retrieval benchmark runs first and must pass. The source checkout and
indexed commit must be clean and identical. Query runs use a read-only isolated
clone. Change runs apply a trusted fault patch in a separate temporary clone,
prove validation fails before the model runs, and never modify the source
checkout.

For a local LM Studio run, record the complete serving configuration so later
cohort comparisons can reject incompatible reports:

```powershell
uv run python -m codemesh_agent_access eval model `
  --model unsloth/ornith-1.0-9b@q6_k `
  --local-provider lmstudio `
  --tier query `
  --temperature 0.2 `
  --seed 137 `
  --top-p 0.95 `
  --top-k 20 `
  --context-length 262144 `
  --quantization Q6_K `
  --chat-template-hash <sha256>
```

The runner uses a response-tool submission pattern. CodeMesh investigation
remains available before the model calls `submit_benchmark_answer` exactly once.
An evaluation MCP proxy enforces each question's tool allowlist, required
ordering, per-tool limits, and total call budget. Blocked attempts are recorded
as failures without retaining argument values.

Each run receives 0–4 for accuracy/grounding, instruction following, tool use,
safety/scope, insight/completeness, reliability, token efficiency, and speed.
The weights are 35/15/15/10/10/5/5/5 percent respectively. A safety violation
fails the run, and accuracy and instruction following must both reach 3. A
scenario passes when at least two of three repetitions pass. Efficiency is
provisional until multiple reviewed reports establish passing-run cohort
medians; correctness always takes precedence.

The initial report includes a blinded `review-packet.json`. A reviewer scores
only insight and completeness against the supplied rubric. Create a review file
matching the `ReviewFile` schema, then finalize it:

```powershell
uv run python -m codemesh_agent_access eval model finalize `
  ..\.codemesh-evals\<run>\report.json `
  --reviews review.json
```

One deterministic representative passing run is reviewed for each question.
Objectively failed runs receive zero insight automatically. Ten percent of
items require two reviewers; disagreements greater than one point must be
resolved before finalization.

Compare at least two reviewed reports to calculate cohort-relative token and
speed bands and rank models. Final ranking is 60% Tier 1 and 40% Tier 2
treatment score; CodeMesh control/treatment uplift is reported separately.

```powershell
uv run python -m codemesh_agent_access eval compare `
  model-a-reviewed.json model-b-reviewed.json --output comparison.json
```

Model-backed runs can be costly: Tier 1 is 72 executions and the full benchmark
is 126. Keep temperature, top-p, top-k, context length, seed, reasoning effort,
chat template, provider, and host fixed within a comparison. Reports retain
these settings, the model and quantization identifiers, indexed commit, and host
description. They do not retain credentials or MCP payloads by default.

## Custom Suites

Built-in suites are named `codemesh-live`, `codemesh-agent`, and
`codemesh-model`. A custom JSON path can be passed to `--suite`.

Inspect or validate the versioned formats with:

```powershell
uv run python -m codemesh_agent_access eval schema live
uv run python -m codemesh_agent_access eval schema agent
uv run python -m codemesh_agent_access eval schema model
uv run python -m codemesh_agent_access eval validate path/to/suite.json
```

Retrieval targets use one or more exact selectors: `stable_key`, normalized repository-relative `file_path`, or `node_id`. Validation commands are argument arrays with explicit working directories and timeouts; suites do not execute shell command strings.

## Exit Codes And Automation

- `0`: evaluation gates passed or the requested model tier qualified/certified.
- `1`: evaluation gates failed, the agent treatment regressed, or model thresholds were not met.
- `2`: the suite, environment, freshness preflight, transport, or agent infrastructure was invalid.

Keep fixture tests in normal CI. Run live and agent evaluations only in explicit local or self-hosted jobs with their required stores and credentials.
