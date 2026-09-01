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
  attributable to CodeMesh;
- the configured Config.Net campaign achieved context-package adoption in all
  three treatments but regressed correctness in two treatments, so configured
  cross-repository adoption is established while product benefit is not; and
- no summary model is qualified, so the core baseline remains summary-free.

Explicit repository onboarding is now the selected v1 product contract; see
[Agent Integration Contract](../planning/agent-integration-contract.md). The
checkout-local integration and provider-free probes are implemented and passed
their clean-candidate gates. The paired-agent evaluator now represents that
configured integration. The one-step context-package entry contract and its
exact-candidate preflight, frozen one|nine gates, and YoutubeDownloader
provider-free gate pass at candidate `8844c21`. The first configured campaign,
retained at candidate `0bde606`, completed all three pairs correctly and safely
but was insufficient: two treatments called repository status, none retrieved a
context package, and there were no attributable wins. The separately authorized
campaign through corrected candidate `0378740` was also correct and safe but
insufficient: one treatment called status, none retrieved context, and there
were no attributable wins. The one-step `8844c21` campaign then completed all
three pairs correctly and safely with context-package adoption in every
treatment. Its verdict was `neutral`, with no attributable wins or regressions;
median duration was 1.39% lower and median tokens were 4.13% higher. Preserve
all three results and their frozen task, prompt, grading targets, and control
behavior. The separate Config.Net zero-adoption prompt-parity campaign remains
negative spontaneous-discovery evidence and must not be rewritten as a
transport defect or configured-product result.

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

The harness records spontaneous, assisted, and configured modes. Configured
reports retain installed guidance, baseline MCP, profile, binding, plan, and
probe identities. Never relabel earlier assisted evidence as configured product
evidence. If adoption remains zero, retain that negative result rather than
weakening the comparison.

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

uv run python -m codemesh_agent_access eval live `
  --suite youtube-downloader-impact-adaptive-live `
  --output ..\.codemesh-evals\youtube-downloader-impact-adaptive-live\report.json

uv run python -m codemesh_agent_access eval agent `
  --suite youtube-downloader-impact-agent `
  --repository-root ..\references\YoutubeDownloader `
  --model <model-id>
```

Keep these suites separate from the original live and three-task agent suites so
their outcomes do not rewrite the frozen baseline. The adaptive live suite is
provider-free: it compares the frozen task-shaped package with three bounded
focused facets while preserving the same repository commit, six targets, and
retrieval thresholds. It is a retrieval and package-budget gate, not a paired
agent campaign.

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

The `youtube-downloader-impact-configured-agent` suite preserves the same
frozen prompt, targets, thresholds, and source commit while setting
`integration_mode = "configured"`. It uses the reviewed repository-owned
normal installation and guidance, keeps control and treatment prompts equal,
and forbids evaluator-only treatment guidance. Run its configured preflight and
retrieval gates before any separately authorized model campaign.

## Independent Replication And Discoverability

The `config-net-cache-live`, `config-net-cache-assisted-agent`,
`config-net-cache-agent`, and `config-net-cache-configured-agent` suites pin the
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

Exact clean candidate `b16eee7` adds the configured suite while preserving that
prompt, target set, threshold, and source commit. Its reviewed normal-profile
plan and ignored repository guidance passed the configured preflight with
prompt parity, a fresh exact binding, positive context retrieval, and
fail-closed rejection. The full six-case live gate then passed all 18 calls
with recall, MRR, and nDCG of 1.0 and zero secret leaks. No model provider was
invoked. The sanitized record is
[configured Config.Net provider-free evidence](evidence/configured-config-net-provider-free-b16eee7.json).
That gate also retained an earlier broad task-query diagnostic: it returned
tests but missed requested implementation paths, whereas the canonical
decomposed live cases all passed. This did not establish a root cause.

The separately authorized configured campaign completed all three pairs with
context-package adoption in every treatment and no safety, MCP transport, or
command-policy failure. All three controls passed. Treatments passed one of
three: repetition one omitted `ConfigurationBuilder.cs`, and repetition two
omitted `LazyVar.cs`, `ConfigurationBuilder.cs`, `LogicTest.cs`, and
`ConfigurableMethodsTest.cs`. The verdict was `regressed`, with no attributable
wins. On the only jointly successful pair, treatment duration was 21.31% higher
and token use was 117.18% higher. The sanitized record is
[configured Config.Net agent evidence](evidence/configured-config-net-agent-b16eee7.json).
Preserve this consumed negative configured-product artifact and do not retry it
automatically. The next work is provider-free reproduction of full-task
context-package coverage against every required target, correlated with the
retained broad-query miss but without claiming a cause that raw campaign
packages and final messages cannot establish.

That provider-free diagnosis is now retained separately. The exact frozen
58-term task query returned eight test paths and only `LogicTest.cs` from the
seven required targets. Four concise task-derived queries covering cached
writes, setter routing, proxy interception, and cache expiration recovered all
seven targets. The separate `config-net-cache-focused-live` diagnostic passed
five cases and all 15 calls with recall 1.0, MRR 0.660714, nDCG 0.76259, and
zero secret leaks against clean `b16eee7`; the unchanged canonical suite also
passed all 18 calls. Its suite definition was uncommitted, so this validates the
retrieval strategy rather than an exact correction candidate. The sanitized
record is
[focused-query diagnosis](evidence/config-net-focused-query-diagnosis-b16eee7.json).

Exact clean detached candidate `3804028` retains the context package as the
one-step entry tool but replaces one-long-full-task guidance with a small set of
focused implementation and test queries for multi-part work. Its 125 Python
tests, Ruff checks, and five fixture cases pass. The reviewed configuration-only
plan and ignored guidance passed configured preflight, a positive package
probe, and wrong-checkout rejection with provider mode `none`. The committed
focused suite passed five cases and 15 calls with recall 1.0, MRR 0.660714,
nDCG 0.76259, and zero leaks; `LazyVar.cs` remains at rank eight. The unchanged
canonical suite passed six cases and 18 calls with recall, MRR, and nDCG of 1.0
and zero leaks. The sanitized exact-candidate record is
[focused-query provider-free evidence](evidence/config-net-focused-query-provider-free-3804028.json).
This is provider-free correction readiness, not normal-agent compliance or
product-benefit evidence.

The separately authorized exact-candidate campaign retained the frozen task,
grading, repository, model, reasoning effort, seed, repetitions, normal profile,
and prompt parity. It completed all three pairs with an `improved` verdict.
Every treatment adopted the context package, made two or three package attempts,
and passed; controls passed two of three because repetition two missed
`ConfigurationBuilder.cs`. The report therefore records one
CodeMesh-attributable win, zero treatment regressions, and no safety, MCP, or
command-policy failures. Across the two jointly successful pairs, treatment
median duration was 13.69% lower and median tokens were 3.59% lower. The
sanitized record is
[focused-query configured campaign evidence](evidence/configured-config-net-agent-3804028.json).
This is positive configured evidence for one bounded campaign. Raw package
arguments and final messages were not retained, so it neither proves exact
query wording nor establishes causal or repeatable product benefit.

Independent clean candidate `64d4052` added the configured YoutubeDownloader
impact suite while preserving the frozen task and repository identity. Its full
deterministic checks, reviewed configuration-only plan, configured preflight,
positive and wrong-checkout probes, two-case impact live gate, and unchanged
six-case live gate passed with provider mode `none`. The impact gate returned
all six targets with recall and MRR 1.0, nDCG 0.891323, and zero leaks; the
canonical gate retained recall 1.0, MRR 0.9, nDCG 0.926186, and zero leaks. The
sanitized record is
[configured YoutubeDownloader provider-free evidence](evidence/configured-youtube-downloader-provider-free-64d4052.json).

The separately authorized campaign completed every control and treatment
correctly and safely, with context-package adoption in every treatment and no
failed MCP calls. Treatments attempted two, two, and three packages. There were
no correctness wins or regressions, while treatment median duration was 49.79%
higher and median tokens were 41.00% higher across all three matched pairs. The
efficiency threshold therefore produced a valid `regressed` verdict. The
sanitized record is
[configured YoutubeDownloader campaign evidence](evidence/configured-youtube-downloader-agent-64d4052.json).
This replicates configured adoption and correctness on an independent C# task,
not repeatable product benefit. Because raw query arguments were not retained,
the package-attempt count motivates provider-free adaptive-query diagnosis but
does not establish the regression's cause.

That provider-free diagnosis preserves the frozen YoutubeDownloader task, six
targets, source identity, and thresholds. One 29-term task-shaped package
covered all six targets in one call with primary rank two and a 12,000-character
agent package. Three focused implementation/test-facet packages also covered
all six, but used 35,991 formatted characters across three calls and repeated
five of 24 ranked item occurrences. The observed one-call latency was
17,177.121 ms versus 18,669.373 ms summed across the three focused calls. The
one-repetition comparison ran while the new suite and guidance were uncommitted,
so it establishes the retrieval-shape decision rather than exact-candidate
readiness. The sanitized record is the
[task-adaptive query diagnosis](evidence/youtube-downloader-task-adaptive-query-diagnosis-e2e1bca.json).

Exact clean detached candidate `fbc1433` implements the bounded correction:
start with one concise task-shaped package, stop when every required facet is
resolved, and issue a focused follow-up only for a specific unresolved
implementation or test facet, with at most three non-overlapping packages per
task. Its 125 Python tests, Ruff checks, five fixture cases, reviewed
normal-profile preflight, positive probe, and wrong-checkout rejection passed.
The committed adaptive suite passed all 15 calls with recall 1.0, MRR 0.875,
nDCG 0.862253, and zero leaks. The unchanged impact suite passed all six calls
with recall and MRR 1.0 and nDCG 0.891323; the unchanged canonical suite passed
all 18 calls with recall 1.0, MRR 0.9, and nDCG 0.926186. No model provider was
invoked. The sanitized record is
[task-adaptive provider-free evidence](evidence/youtube-downloader-task-adaptive-provider-free-fbc1433.json).
This is exact-candidate correction readiness, not evidence of normal-agent
guidance compliance, efficiency benefit, or causality for the retained
`64d4052` regression. Another campaign requires fresh explicit model-spend
authorization and must not be started automatically.

Candidate `0bde606` passed the configured preflight for the selected explicit-
onboarding contract against exact Primary commit `fe2f761`. Its first paid run
completed three correct and safe pairs, with repository-status adoption in two
treatments, no context-package calls, no attributable wins, and verdict
`insufficient`. The sanitized record is
[configured one|nine agent evidence](evidence/configured-onenine-agent-0bde606.json).
Preserve that frozen identity and result. The corrected run used a new exact
clean candidate while keeping repository guidance, task prompt, grading,
normal-user tool profile, model settings, and control behavior fixed; it did not
create an evaluator-only tool-selection advantage.

Clean detached candidate `0378740` contains the bounded status-to-context
correction and passed the full deterministic checks, configured preflight, all
eight frozen one|nine retrieval and rejection gates, all three retained feedback
packet validations, and the pinned YoutubeDownloader live gate with provider
mode `none`. The sanitized record is
[corrected provider-free evidence](evidence/configured-onenine-provider-free-0378740.json).
This established readiness for the separately authorized model campaign; it did
not establish agent context adoption or product benefit.

The authorized `0378740` campaign completed three correct and safe pairs with
prompt parity and the exact reviewed normal-profile installation. Only one
treatment called repository status, no treatment called the context-package
tool, and there were no attributable wins. Its verdict was `insufficient`.
Overall treatment medians were 6.07% slower and used 4.17% more tokens; those
differences are diagnostic because context retrieval never occurred. The
sanitized record is
[corrected configured campaign evidence](evidence/configured-onenine-agent-0378740.json).
Preserve this consumed artifact and do not retry it automatically.

The subsequent provider-free implementation removes the measured two-step
dependency by making the fail-closed context package the single normal-host
entry action across MCP instructions, tool descriptions, and generated
repository onboarding. Status remains an explicit diagnostic tool. Exact clean
candidate `8844c21` passed the full deterministic checks, configured preflight,
all eight frozen one|nine gates, all three retained feedback packet validations,
and the pinned YoutubeDownloader live gate with provider mode `none`. The
sanitized record is
[one-step provider-free evidence](evidence/configured-onenine-provider-free-8844c21.json).
The authorized campaign from those identities retrieved a context package in
all three treatments and passed every control and treatment safely. It produced
no attributable win or regression, so the verdict was `neutral`; both median
efficiency deltas remained inside the 10% threshold. The sanitized record is
[one-step configured campaign evidence](evidence/configured-onenine-agent-8844c21.json).
This establishes adoption for the selected one|nine task, not product benefit.
The later Config.Net configured campaign also established adoption but
regressed correctness, so adoption now spans two repositories without
establishing repeatable product benefit.

## Configured Agent Preflight And Campaign

A configured suite sets `integration_mode` to `configured`, pins
`repository_commit`, and may list `baseline_mcp_servers`. Named baseline servers
must be present in the reviewed checkout-local `.codex/config.toml`; control and
treatment receive the same selected baseline, while treatment additionally
receives the reviewed CodeMesh normal-profile launch. Embedded environment
values are rejected for baseline servers; use declared `env_vars` names.

From `agent-access`, run the provider-free gate first:

```powershell
uv run python -m codemesh_agent_access eval agent `
  --suite <configured-suite.json> `
  --repository-root <pinned-checkout> `
  --configured-plan <reviewed-plan.json> `
  --configured-guidance-path AGENTS.override.md `
  --configured-probe-query "<frozen retrieval query>" `
  --configured-expected-path <expected-path> `
  --preflight-only `
  --preflight-output <preflight-report.json>
```

The guidance path may be a committed repository file or an explicitly installed
ignored file such as instance-generated `AGENTS.override.md`. The evaluator
copies the same reviewed bytes into both temporary conditions and records the
path, source classification, and SHA-256 hash rather than raw guidance.

The preflight rejects dirty or stale source state, a dirty CodeMesh tool checkout,
commit, checkout, root, or source-view mismatch, changed installation files, a
non-normal tool surface, uncommitted guidance, a failed context probe, or a
failed wrong-checkout rejection probe. The report records stable identities and
hashes, not raw guidance or MCP payloads.

Only after the preflight and repository-specific frozen retrieval gates pass,
and only with explicit model-spend authority, remove `--preflight-only`, add
`--model <model-id>` and `--output-dir <artifact-directory>`, and run the paired
campaign. The task prompt, model, reasoning effort, temporary checkout, and
declared baseline MCP servers stay identical across conditions.

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

Each control and treatment run receives the same task prompt, model, reasoning effort, sandbox, and isolated temporary clone. Both run non-interactively with `--ask-for-approval never`. Historical spontaneous and assisted suites preserve their frozen behavior: control has an empty MCP map and treatment adds the unbound `diagnostic` profile. Configured suites instead give both conditions the same explicitly selected baseline MCP servers and add only the exact reviewed, bound `normal` CodeMesh installation to treatment. Suites without explicit mode preserve compatibility by deriving spontaneous or assisted classification from `treatment_guidance`; configured suites forbid evaluator-only guidance and preserve prompt parity.

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
