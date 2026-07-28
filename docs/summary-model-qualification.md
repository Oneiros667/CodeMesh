# Summary Model Qualification Procedure

## Status

This document defines a design and operating procedure. The dedicated
qualification command and report schema described here are not implemented yet.
Existing ingestion and live-evaluation commands can be used to run parts of the
procedure manually.

CodeMesh does implement versioned, complexity-tiered summary prompts and
completion ceilings. The qualification automation and certification report
remain planned.

## Purpose

CodeMesh can use a chat model during ingestion to generate a short summary,
tags, and a confidence value for each eligible code node. Those generated
fields become searchable evidence, so a fluent but inaccurate summary can
degrade retrieval as easily as a good summary can improve it.

This procedure determines whether a local or online model is suitable for
offline summary generation. It evaluates the model as a bounded summarizer, not
as an autonomous coding agent or MCP client.

The procedure answers two related questions:

1. **Model quality:** Does the model reliably produce accurate, grounded, useful
   summaries under the CodeMesh summary contract?
2. **Deployment suitability:** Does a specific provider, model build, prompt,
   serving configuration, and host meet the required privacy, speed, token, and
   downstream-retrieval budgets?

A model can pass the first question but fail the second on a particular host or
online service. Qualification therefore applies to the recorded deployment
profile, not just to a marketing model name.

## Relationship To Existing Evaluations

The evaluation lanes have different responsibilities:

- Deterministic fixtures verify tool and response contracts without invoking a
  model.
- The live MCP suite verifies retrieval, freshness, safety, reliability, and
  latency against indexed data.
- The agent A/B suite measures whether a coding agent performs better with
  CodeMesh available.
- The model benchmark measures an agent model's repository investigation and
  repair capability.
- This procedure evaluates the model used to generate summaries during
  ingestion.

Results from the agent or model benchmark must not be used as evidence that the
same model is a qualified summarizer. Tool use, autonomous reasoning, and code
repair are materially different tasks from producing a short structured
summary from supplied source.

## Qualification Outcomes

Every completed evaluation produces one of these outcomes:

- **Qualified:** all mandatory quality, safety, retrieval, and deployment
  profile gates pass.
- **Conditionally qualified:** mandatory quality and safety gates pass, but use
  is restricted to documented repositories, languages, node kinds, input
  sizes, or operating limits.
- **Not qualified:** one or more mandatory gates fail.
- **Invalid run:** the corpus, configuration, provider, source snapshot, report,
  or measurement environment was incomplete or changed during the run.

The result must include its intended use:

- `local-offline`
- `private-network`
- `online-approved-data`

An online model cannot receive `local-offline` qualification, even if it passes
all quality and performance gates.

## Fixed Qualification Identity

Record the following before generating any summaries:

- CodeMesh commit and clean-worktree state.
- Evaluation-suite name, version, and corpus hash.
- Repository commits and node-content hashes.
- Summary prompt version and prompt hash.
- Provider type and endpoint class: local, private network, or online.
- Exact provider and model identifiers.
- Model revision or artifact hash when available.
- Quantization and numeric precision.
- Chat template and its hash.
- Context length and maximum summary input characters.
- Temperature, top-p, top-k, seed, stop sequences, and maximum output tokens.
- Retry, timeout, concurrency, and batching settings.
- Host operating system, CPU, memory, accelerator, accelerator memory, and
  serving runtime versions.
- For online services, API version, service region, retention policy, and
  pricing snapshot.

Changing any identity field creates a new deployment profile and requires a new
qualification run. Reports from profiles with different identity fields may be
compared, but their samples must not be pooled as repetitions of one profile.

## Evaluation Corpus

Use a versioned, immutable corpus manifest. Each item identifies the repository,
commit, node id, content hash, language, node kind, source span, input size, and
review labels.

The corpus should be stratified across:

- Files and test files.
- Classes, interfaces, structs, enums, and delegates.
- Methods, constructors, properties, events, and test cases.
- Supported programming and deployment languages.
- Small, medium, near-limit, and deliberately truncated inputs.
- Simple declarations, stateful behavior, error paths, side effects, and
  cross-component orchestration.
- Clearly named and misleadingly or ambiguously named symbols.
- Security-sensitive logic with synthetic values rather than real secrets.

Do not select only nodes for which a candidate model already performs well.
Preserve a held-out qualification partition that is not used while adjusting
the prompt or serving settings.

For online candidates, the corpus must contain only source approved for
transmission to that provider. Local qualification may use a broader corpus,
but results from different corpora are not directly comparable.

## Reference Labels

Each reviewed corpus item should contain:

- Required atomic facts.
- Optional useful facts.
- Explicitly forbidden or contradictory claims.
- Expected responsibility or purpose.
- Important inputs, outputs, side effects, and failure behavior when present.
- Required and acceptable tags.
- A human reference summary used as guidance, not as a string-match target.
- A criticality classification for factual errors.

Reference labels should describe meaning instead of enforcing one preferred
writing style. At least two reviewers should independently label a calibration
sample and resolve material disagreements before the corpus is frozen.

## Procedure

### Phase 0: Preflight And Data Governance

1. Verify that CodeMesh and every corpus repository are at the recorded clean
   commits.
2. Confirm the prompt, model, provider, serving settings, and host identity.
3. Run CodeMesh redaction before any model request.
4. Scan prepared inputs for secret canaries and prohibited file classes.
5. For an online provider, verify data classification, transport, retention,
   region, and account authorization before transmitting source.
6. Confirm sufficient disk, memory, model budget, and provider quota.

Any source-governance failure invalidates the run. Quality or cost cannot
override this gate.

### Phase 1: Contract And Reliability

Run every corpus item through the normal CodeMesh summary prompt and parser.
Record:

- Attempted, completed, failed, and retried requests.
- Valid JSON rate.
- Presence and validity of `summary`, `tags`, and `confidence`.
- Empty, malformed, truncated, or schema-invalid responses.
- Provider errors, timeouts, and rate-limit events.
- Output length and tag-count violations.
- Identical-input stability across repetitions.

Do not silently repair malformed model output before scoring it. A separately
measured retry policy may be evaluated, but both first-attempt and eventual
success rates must remain visible.

### Phase 2: Accuracy And Grounding

Score generated summaries against the frozen labels and source:

- **Atomic factual precision:** supported generated claims divided by all
  generated factual claims.
- **Required-fact recall:** required facts present divided by required facts.
- **Critical hallucinations:** unsupported claims that could materially
  misdirect repository understanding or a code change.
- **Contradiction rate:** summaries that conflict with an explicit reference
  fact.
- **Purpose accuracy:** whether the primary responsibility is correctly stated.
- **Behavior coverage:** important inputs, outputs, state changes, side effects,
  and failures captured when relevant.
- **Tag precision, recall, and F1.**
- **Confidence calibration:** whether high, medium, and low confidence correlate
  with observed correctness.
- **Information density:** supported useful facts relative to output tokens.

Objective fact scoring should be automated where labels allow it. Reviewers
should score purpose, completeness, and ambiguous claims from blinded packets
that do not expose the candidate model name.

### Phase 3: Speed And Token Efficiency

Measure cold and warm behavior separately. Use at least one warm-up pass and
three measured repetitions unless the profile explicitly requires more.

Record:

- End-to-end ingestion duration.
- Per-node latency p50, p95, and maximum.
- Time to first token when the provider exposes it.
- Nodes summarized per minute.
- Successful nodes per wall-clock hour.
- Input, output, cached-input, and total tokens.
- Tokens per attempted and successfully summarized node.
- Supported facts and required facts recovered per 1,000 output tokens.
- Retry-adjusted tokens and duration.
- Peak host memory and accelerator memory for local profiles.
- Provider-reported cost and the pricing snapshot for online profiles.

Token counts should come from provider usage fields when available. If counts
are estimated locally, identify the tokenizer and mark them as estimated.
Provider-reported and estimated counts must not be mixed in one aggregate.

Speed and token measurements must include failed attempts and retries. Reporting
only successful calls would reward unstable models.

### Phase 4: Downstream Retrieval Value

Create isolated indexes for:

1. No generated summaries.
2. The candidate model.
3. A qualified reference model when available.

Keep repositories, commits, parsers, embeddings, ranking settings, and queries
identical. Do not allow one candidate's generated summaries to leak into
another candidate's index.

Run the same live retrieval suite against every index and compare:

- Recall at k.
- Precision at k.
- Mean reciprocal rank.
- nDCG.
- Ranking stability.
- Correct summary-hit contribution.
- False-positive summary hits.
- Queries improved, unchanged, and degraded from the no-summary baseline.
- Context-package relevance and token density.
- Redaction-canary leakage.

Inspect all material regressions. Generated text that introduces a confident
but incorrect search hit is an accuracy defect even when aggregate retrieval
metrics remain acceptable.

### Phase 5: Optional Agent Outcome Check

For high-impact deployment profiles, run a controlled agent comparison with the
same consumer model and tasks against:

- The no-summary index.
- The candidate-summary index.
- The reference-summary index.

Only the ingestion summary model may vary. This phase measures whether retrieval
differences produce meaningful answer or repair differences; it does not replace
the earlier deterministic accuracy gates.

## Qualification Gates

Define the performance budget before running candidates. The following are
recommended initial mandatory gates and should be calibrated using reviewed
baseline reports:

### Universal Quality And Safety Gates

- At least 99.5% first-attempt schema-valid responses.
- At least 99.9% eventual completion after the declared bounded retry policy.
- Zero secret-canary leakage.
- Zero critical hallucinations in the qualification partition.
- At least 95% atomic factual precision.
- At least 80% required-fact recall overall, with no corpus stratum below 70%.
- No material retrieval regression from the no-summary baseline: Recall@k,
  MRR, and nDCG may not decrease by more than one absolute percentage point.
- No unresolved safety or source-governance failure.

These thresholds are initial policy, not evidence that a model is safe for every
repository. Tighten them for security-critical or highly regulated source.

### Deployment Profile Gates

Each intended deployment defines:

- Maximum total ingestion time for the target repository size.
- Maximum p95 per-node latency.
- Minimum sustained nodes per minute.
- Maximum total tokens and tokens per successful node.
- Maximum retry-adjusted token overhead.
- Maximum local memory and accelerator-memory usage, or maximum online cost.
- Maximum provider error and rate-limit rate.

A candidate passes only when the upper confidence bound or worst measured
repetition, as selected by policy before the run, meets every budget. Do not
qualify from the best run.

### Comparative Decision

When several candidates pass:

1. Prefer higher factual accuracy and fewer retrieval regressions.
2. Then prefer greater downstream retrieval improvement.
3. When quality is practically tied, prefer the deployment profile with better
   speed, token efficiency, privacy, and operating cost.

Do not trade a critical hallucination or data-governance failure for lower
latency or cost.

## Report And Evidence

The qualification report should contain:

- Immutable qualification identity and corpus manifest hash.
- Outcome and intended-use classification.
- Aggregate metrics plus results by language, node kind, input-size band, and
  criticality.
- First-attempt and retry-adjusted reliability.
- Accuracy, speed, token, resource, and cost measurements.
- No-summary, candidate, and reference retrieval comparisons.
- Failed-item identifiers and sanitized failure categories.
- Reviewer decisions and disagreement resolution.
- Explicit limitations and conditional qualification boundaries.

Keep raw source, prompts, responses, and provider payloads out of the default
report. Store them only in an access-controlled evidence directory when
explicitly requested. Reports must never contain credentials or unredacted
secret values.

## Proposed Automation

A future implementation should add a versioned suite and commands similar to:

```powershell
cd agent-access
uv run python -m codemesh_agent_access eval summaries `
  --suite codemesh-summary-model `
  --provider lmstudio `
  --model <model-id> `
  --profile local-offline

uv run python -m codemesh_agent_access eval summaries compare `
  candidate-a.json candidate-b.json reference.json
```

The runner should:

- Prepare redacted inputs through the production summary prompt.
- Isolate each candidate's summary store or database namespace.
- Capture provider usage without retaining credentials.
- Generate blinded review packets.
- Run the live retrieval suite against each isolated index.
- Enforce predeclared gates and emit machine-readable and human-readable
  reports.
- Reject comparisons with incompatible corpus, prompt, repository, or ranking
  identities.

Until that automation exists, manual results are research evidence only and
must not be presented as a CodeMesh-qualified deployment profile.
