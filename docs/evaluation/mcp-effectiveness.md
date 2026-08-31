# MCP Effectiveness Evaluation

Document type: current evaluation guide

CodeMesh has four evaluation levels:

1. The deterministic fixture suite checks MCP behavior without stores or a model provider.
2. The live suite starts CodeMesh through MCP stdio and measures retrieval quality, freshness, safety, reliability, and latency against indexed data.
3. The agent suite runs paired control/treatment tasks with CodeMesh unavailable or available to the agent.
4. The model benchmark measures query-answering capability and, for qualifying models, paired repair capability.

Normal tests never start live stores or invoke a paid agent.

Ingestion summary models require a separate qualification because bounded
summary generation is not equivalent to autonomous MCP tool use or repair
ability. [Summary Model Qualification](../planning/summary-model-qualification.md) defines
a provider-neutral procedure for local and online candidates, including factual
accuracy, reliability, speed, token efficiency, privacy, cost, and downstream
retrieval gates. The dedicated qualification runner described there is planned
and is not an available CLI command yet.

## Product Decision Role

Evaluation is the near-term product milestone, not only a regression facility.
CodeMesh should advance beyond its initial C#/.NET wedge only after controlled
evidence shows that agents perform better with CodeMesh than with normal
repository exploration.

The evidence position is summarized in [Project Status](../current/project-status.md):

- fixtures establish tool and response behavior, not usefulness;
- summary-free self and external live baselines pass their retained gates;
- spontaneous YoutubeDownloader campaigns completed without CodeMesh adoption,
  so their overall efficiency variance is not attributable to CodeMesh;
- two assisted campaigns show utility after explicit onboarding, including an
  independent Config.Net replication, but do not prove prompt-parity discovery;
- the independent prompt-parity Config.Net campaign completed three pairs but
  recorded zero CodeMesh calls or call attempts, so it is negative
  discoverability evidence and its overall efficiency variance is not
  attributable to CodeMesh; and
- no summary model is qualified, so the core baseline remains summary-free.

Explicit repository onboarding is now the selected v1 product contract; see
[Agent Integration Contract](../planning/agent-integration-contract.md). The
checkout-local integration and provider-free probes are implemented and passed
their clean-candidate gates. The current product-proof work is to extend the
paired-agent evaluator to represent that configured integration, then evaluate
the exact guidance, tool profile, checkout binding, and setup process shipped to
normal users. Preserve the same independent task, prompt, grading targets, and
control behavior. The retained zero-adoption campaign remains negative
spontaneous-discovery evidence and must not be rewritten as a transport defect
or configured-product result.

Reports must compare correctness, safety, freshness, citations, elapsed time,
tokens, tool calls, adoption, and correction loops. A tied-correctness result is
useful only when time or token use improves by at least the existing 10% agent
comparison threshold and the other efficiency metric does not regress by more
than 10%. Product evidence should repeat across more than one task family and
repository; a passing harness or one favorable run is not sufficient.

Classify agent evidence by the integration the treatment actually receives:

- **Spontaneous:** the treatment prompt is identical to control, CodeMesh MCP is
  the only added product surface, and no repository onboarding is installed.
- **Evaluator-assisted:** treatment receives evaluator-only guidance. These
  suites must declare the guidance and cannot substitute for product evidence.
- **Configured/onboarded:** the task prompt remains identical to control, while
  treatment receives the exact repository guidance, tool profile, checkout
  binding, and setup process shipped to normal users.

The current harness records spontaneous and assisted modes. Extend its report
schema before claiming configured/onboarded evidence so the installed guidance
and profile identities are retained. Never relabel earlier assisted evidence as
configured product evidence. If adoption remains zero, retain that negative
result rather than weakening the comparison.

## Representative External C# Baseline

The built-in `youtube-downloader-live` and `youtube-downloader-agent` suites pin
the public YoutubeDownloader repository at commit
`05e63cddb6d2a96fc2d21b097129a0765824f251`. The runner rejects a fresh but
different commit unless `--allow-stale` is explicitly used for a non-comparable
diagnostic run.

Prepare the checkout from the CodeMesh repository root:

```powershell
git clone https://github.com/Tyrrrz/YoutubeDownloader.git `
  references/YoutubeDownloader
git -C references/YoutubeDownloader checkout --detach `
  05e63cddb6d2a96fc2d21b097129a0765824f251
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root references/YoutubeDownloader `
  --solution references/YoutubeDownloader/YoutubeDownloader.slnx `
  --skip-embeddings
```

Explicit `--solution` and `--project` paths may be absolute, relative to the
repository root, or relative to the directory that launches the CLI. A missing
explicit file fails ingestion instead of silently falling back to filesystem
parsing.

Run and retain the summary-free live report:

```powershell
cd agent-access
$env:CODEMESH_MODEL_PROVIDER = 'none'
uv run python -m codemesh_agent_access eval live `
  --suite youtube-downloader-live `
  --output ..\.codemesh-evals\youtube-downloader-live\report.json
```

The external live suite checks implementation discovery, query resolution,
cross-project download impact, repository-scoped validation guidance, and exact
source/index freshness. After it passes, run the paired agent comparison:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --suite youtube-downloader-agent `
  --repository-root ..\references\YoutubeDownloader `
  --model <model-id>
```

The three task families are implementation discovery, likely change impact,
and validation selection. The validation task deliberately requires the
repository workflow and solution file and forbids inventing a test project.

The separate `youtube-downloader-impact-live` and
`youtube-downloader-impact-agent` suites preserve the first
complexity-calibration task selected after two zero-adoption baseline campaigns.
They ask retrieval and agents to distinguish required edits from already-generic
flow when adding an audio-only output container across the core and application
projects:

```powershell
uv run python -m codemesh_agent_access eval live `
  --suite youtube-downloader-impact-live `
  --output ..\.codemesh-evals\youtube-downloader-impact-live\report.json

uv run python -m codemesh_agent_access eval agent `
  --suite youtube-downloader-impact-agent `
  --repository-root ..\references\YoutubeDownloader `
  --model <model-id>
```

Keep these suites separate from the original live and three-task agent suites so
their outcomes do not rewrite the frozen baseline.

If the spontaneous complex campaign has zero adoption, the separate
`youtube-downloader-impact-assisted-agent` suite adds transparent treatment-only
onboarding. It instructs the treatment to start with the context package and
then verify only the returned spans needed for citations through targeted,
batched reads. The report records `adoption_mode = "assisted"` and
`prompt_parity = false`; this measures utility after onboarding and cannot
substitute for spontaneous-discovery evidence:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --suite youtube-downloader-impact-assisted-agent `
  --repository-root ..\references\YoutubeDownloader `
  --model <model-id>
```

## Independent Replication And Discoverability

The `config-net-cache-live` and `config-net-cache-assisted-agent` suites pin the
MIT-licensed Config.Net repository at commit
`ae0af7d4b3781c66233bbb677b6e11df1f5b416b`. This is a separate repository,
author, architecture, and task family from YoutubeDownloader. The task traces
the impact of making writes immediately visible through a cached configuration
proxy while preserving store precedence and no-cache behavior.

Prepare and ingest the checkout from the CodeMesh repository root:

```powershell
git clone https://github.com/aloneguid/config.git references/Config.Net
git -C references/Config.Net checkout --detach `
  ae0af7d4b3781c66233bbb677b6e11df1f5b416b
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root references/Config.Net `
  --solution references/Config.Net/src/Config.Net.sln `
  --skip-embeddings
```

Run the summary-free retrieval gate before the paid agent comparison:

```powershell
cd agent-access
$env:CODEMESH_MODEL_PROVIDER = 'none'
uv run python -m codemesh_agent_access eval live `
  --suite config-net-cache-live `
  --output ..\.codemesh-evals\config-net-cache-live\report.json

uv run python -m codemesh_agent_access eval agent `
  --suite config-net-cache-assisted-agent `
  --repository-root ..\references\Config.Net `
  --model <model-id>
```

The assisted suite records `prompt_parity = false`; it can replicate utility
after onboarding but cannot establish spontaneous discovery. Do not run the
agent comparison without explicit authorization for model spend and a clean,
committed, freshly indexed CodeMesh tool checkout.

The first comparable campaign at CodeMesh commit `d764270` passed its live gate
and produced an `improved` assisted verdict across three completed pairs. All
three treatments passed versus one control, CodeMesh was adopted in every
treatment, two wins were attributable to CodeMesh, no safety violations
occurred, and treatment median elapsed time was 11.8% lower. Treatment median
tokens were 3.0% higher. The sanitized transcription is retained in
[`docs/evaluation/evidence/config-net-assisted-replication-d764270.json`](evidence/config-net-assisted-replication-d764270.json).

For the next discoverability gate, `config-net-cache-agent` freezes the same
task and targets but omits `treatment_guidance`. Its task prompt is identical in
control and treatment; the treatment sees only the normal CodeMesh MCP server,
including its canonical initialization instructions and tool contracts:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --suite config-net-cache-agent `
  --repository-root ..\references\Config.Net `
  --model <model-id>
```

This campaign is model-cost-bearing. Run it only with explicit authorization
from a clean, committed, freshly indexed CodeMesh checkout. Unit tests that
confirm instructions are published do not prove that a normal host presents or
acts on them.

The first comparable prompt-parity campaign at clean CodeMesh commit `647d83d`
completed all three pairs but recorded no CodeMesh calls or call attempts.
Control passed two runs and treatment passed one, with no safety violations.
The harness verdict was `regressed`; because adoption was zero, the overall
39.5% duration and 5.9% token regressions are diagnostic and are not attributed
to CodeMesh. Preserve this as negative discoverability evidence. The sanitized
transcription is
[`docs/evaluation/evidence/config-net-prompt-parity-647d83d.json`](evidence/config-net-prompt-parity-647d83d.json).

Before another paid run, implement and verify the selected explicit-onboarding
contract. The treatment must use the same repository guidance and normal-user
tool profile shipped outside the evaluator; do not create an evaluator-only
tool-selection advantage. Record the result as configured/onboarded, not
spontaneous or evaluator-assisted, and retain the prompt-parity failure
separately.

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
dotnet restore CodeMesh.sln --locked-mode
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

Without `--allow-stale`, the indexed commit must match a clean local checkout
and the CodeMesh MCP tool-source checkout must also be clean with a resolvable
commit identity. External-repository reports record both identities. An allowed
stale or uncommitted run is marked non-comparable. The built-in suite does not
require embeddings; running it again with embeddings or summaries enabled
exposes their contribution in search diagnostics while preserving the same gold
targets.

The report contains:

- Precision and recall at `k`, reciprocal rank, nDCG, and ranking stability.
- Expected relationship coverage.
- MCP startup time, per-call latency, and aggregate p50/p95 latency.
- Search modes, provider names, hit diagnostics, and tool-call reliability.
- Repository/index commit metadata and redaction-canary leakage count.

It intentionally omits snippets, credentials, environment values, and full MCP responses unless raw traces are requested.

## Agent A/B Benchmark

Agent evaluation requires:

- A clean benchmark checkout whose `HEAD` is the indexed repository commit.
- A clean CodeMesh tool-source checkout; external-repository reports record its
  commit and branch separately from the benchmark repository identity.
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

Each control and treatment run receives the same task prompt, model, reasoning effort, sandbox, and isolated temporary clone. Both run non-interactively with `--ask-for-approval never`. The control has an empty MCP server map. The treatment adds CodeMesh as a required stdio MCP server, explicitly selects the non-destructive `diagnostic` profile to preserve the frozen historical tool surface, and approves its allowlisted tools so non-interactive calls execute instead of being canceled at the client approval boundary. Under the current report schema, suites without `treatment_guidance` preserve prompt parity and measure spontaneous adoption. Suites with guidance are reported as assisted, preserve the guidance in report metadata, and isolate best-case utility from discoverability. Configured/onboarded mode must be implemented before the runner can represent the selected v1 contract; that future mode must use and record the shipped `normal` profile rather than inheriting the evaluator's diagnostic surface.

The treatment configuration allowlists CodeMesh read tools and does not expose repository deletion to the benchmark agent.

Answer tasks use structured responses and are graded against real file citations. Change tasks commit a known fault inside the temporary clone, verify that validation fails, let the agent repair it, and grade validation plus changed-path policy. The source checkout is never modified.

The result is `improved`, `regressed`, `neutral`, or `insufficient`. Correctness
wins take priority. CodeMesh can receive credit only for matched pairs whose
treatment actually called a CodeMesh tool. The report retains overall medians
for transparency, but correctness and efficiency attribution use adopted pairs;
at least the suite's minimum pair count must adopt CodeMesh. When correctness is
tied, a 10% time or token improvement counts only when the other efficiency
metric does not regress by more than 10%. Any treatment safety violation is a
regression.

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
