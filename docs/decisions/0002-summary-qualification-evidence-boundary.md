# Decision: Bind summary qualification across production generation and live retrieval

- Status: accepted
- Date: 2026-09-01
- Owners: CodeMesh maintainers

## Context

Generated node summaries become searchable navigation evidence. Qualification
therefore has to test the production prompt, parser, redaction, budget, and
provider path while also measuring downstream retrieval against an isolated
no-summary index. The existing live Agent Access evaluator already owns Recall
at k, precision, MRR, nDCG, reliability, and secret-leak measurements. Replacing
that lane would create two ranking contracts, while moving production summary
generation into Python would create a second prompt/parser implementation.

Qualification artifacts also have different disclosure boundaries. Corpus
source, generated text, and review packets may be sensitive; a publishable
result must not need those fields. Human factual review and provider-backed
execution require authority and evidence that deterministic tests cannot grant.

## Decision

- Implement summary generation and qualification compilation in the .NET
  ingestion/CLI surface so the runner calls the production summary prompt,
  parser, redactor, budget policy, and provider adapters directly.
- Record clean CodeMesh source, frozen suite/corpus, deployment profile, prompt,
  provider generation configuration, and measured repetition identities in a
  private archive.
- Run a warm-up before measured repetitions and stop measured execution when
  warm-up fails.
- Emit a model-blinded review packet separately from the private candidate
  identity. Require two complete blinded reviews and aggregate disagreements
  conservatively.
- Keep isolated-index creation and ranking measurement in the live Agent Access
  evaluation lane. Bind distinct no-summary and candidate live reports to the
  qualification run, shared ranking identity, and corpus identity before
  compilation.
- Emit a sanitized report without source or generated response text. Missing,
  dirty, mismatched, or incomplete evidence produces `invalid-run`; failed
  declared gates produce `not-qualified`.
- Treat online-source authorization, model spend, human review, index isolation,
  and publication as separate operator authorities. A CLI flag or runner pass
  does not grant any of them.

## Consequences

- Qualification reuses production generation behavior and the existing live
  retrieval metric contract instead of maintaining parallel implementations.
- Private archives and review packets require restricted evidence storage and
  are not publication-safe by default.
- The runner does not silently start stores or invoke a model during normal
  verification. A real qualification remains an attended, separately
  authorized workflow.
- The checked-in synthetic suite verifies wiring only. A reviewed, stratified,
  held-out corpus and exact deployment budgets are still required for a real
  qualification claim.
- Cross-language live-report schema changes require both .NET and Python
  verification because the .NET binder consumes the Agent Access report.

## Verification

- The deterministic .NET harness exercises input redaction, warm-up and measured
  repetitions, immutable identity, provider usage aggregation, two-reviewer
  compilation, mandatory retrieval binding, gates, and incompatible comparison
  rejection.
- The Python Agent Access tests and deterministic MCP fixture suite protect the
  live-report contract consumed by the binder.
- Repository standards checks validate the operating documentation and links.
