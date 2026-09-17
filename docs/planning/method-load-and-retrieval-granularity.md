# Method Load And Retrieval Granularity

Status: proposal

Activation gate: do not implement this proposal merely because method size or
model context limits are measurable. Activate it only after the current
normal-host product contract is resolved and controlled evaluation identifies
method-level maintainability or representation load as a material source of
retrieval error, agent overhead, or unsafe conclusions, unless explicit owner
direction reprioritizes it.

This document defines a future evidence-gated capability. It does not describe
implemented analysis, a supported refactoring rule, or a qualified model
profile. Current behavior remains defined by
[Architecture](../current/architecture.md),
[Agent Access Contracts](../current/agent-access-contracts.md), and source and
tests. [Next Steps](next-steps.md) remains the execution-order authority.

## Purpose

CodeMesh should investigate whether the semantic load that makes a method hard
for a human to maintain also makes it a poor retrieval, embedding, summary, or
agent-context unit.

Raw line or character count is only a proxy. The underlying concern is the
method's **semantic working-set size**: the number of concepts, branches, state
transitions, dependencies, side effects, and source facts that must be held
together to understand or represent the method correctly.

The proposed capability should answer three separate questions:

1. **Human maintainability:** is the source method a review or decomposition
   candidate because of its cognitive, control-flow, state, or conceptual load?
2. **Machine representation:** can a configured embedding or summary profile
   represent the complete method without truncation or excessive semantic
   compression?
3. **Agent consumption:** can the relevant source be packaged with its callers,
   dependencies, tests, and validation evidence within the available task
   context budget?

These findings may correlate, but CodeMesh must not treat them as equivalent.
A maintainable source method may need smaller retrieval units for a constrained
embedding model. A compact but highly nested method may fit every model budget
while remaining difficult for a human to change safely.

## Product Boundary And Non-Goals

The first implementation, if activated, should remain within the initial
C#/.NET product wedge and use source-grounded, deterministic analysis wherever
possible.

This proposal does not authorize CodeMesh to:

- rewrite or automatically refactor source code;
- claim that a line-count threshold proves poor maintainability;
- make model-generated judgments the sole basis for a quality finding;
- require embeddings or summaries for the provider-free product baseline;
- rank developers, teams, or repositories by a single quality score;
- transmit proprietary source to an online provider; or
- generalize C# thresholds to Python or other languages without calibration.

Any future source-change suggestion must remain advisory and include its
deterministic evidence. Representation decomposition may create derived index
units without recommending that the source method itself be changed.

## Current Baseline And Gap

CodeMesh already contains related mechanisms, but not this capability:

- C# parsing emits logical symbol nodes, source declaration nodes, source spans,
  and semantic relationships. Roslyn provides a suitable base for future
  control-flow and data-flow measurements.
- Python parsing emits files, classes, functions, async functions, containment,
  imports, calls, test relationships, and bounded PyO3 links for the activated
  pilot. These heuristic relationships do not provide a comparable semantic
  control-flow model or calibrated method-load findings.
- Summary generation assigns complexity tiers using node kind, source lines,
  characters, truncation, and optional complexity metadata. Those tiers select
  generation budgets; they are not maintainability classifications.
- Current local embedding providers cap source by characters, and current
  summary prompts also apply a character cap. These are operating limits, not
  learned quality thresholds.
- Context packages apply a shared source-character budget and the MCP agent
  representation has its own output cap. Package truncation is explicit, but
  CodeMesh does not currently calculate model-specific token pressure for each
  item.

The summary budget policy recognizes metadata names such as
`cyclomaticComplexity`, `complexity`, and `branchCount`, but the current C# and
Python parsers do not populate a complete, comparable method-load profile.
There is no current CodeMesh evidence establishing a threshold at which method
load causes human-maintenance, retrieval, summary, or agent-task regression.

## Terminology

| Term | Meaning |
| --- | --- |
| Method | A function, method, constructor, test case, accessor, or comparable callable source unit. |
| Logical statement | A parser-defined executable or declarative statement, independent of physical formatting. |
| Semantic phase | A cohesive region such as validation, transformation, persistence, dispatch, cleanup, or error handling. |
| Authoritative node | The parser-emitted node and source span that represents the actual source construct. |
| Representation unit | Source and contextual metadata supplied to an embedding, summary, retrieval, or agent surface. |
| Tokenizer profile | A versioned tokenizer identity and rendering policy used to calculate token counts. |
| Input pressure | Rendered input tokens divided by the usable input budget for one representation unit. |
| Dilution | Loss of retrieval specificity when one representation combines several independently relevant meanings. |
| Decomposition candidate | An advisory finding requiring review, not proof that source refactoring is correct. |

## Proposed Method Load Profile

CodeMesh should attach a versioned, parser-produced method-load profile to each
eligible authoritative node. Missing or unsupported measurements must remain
`unknown`; they must not be recorded as zero.

### Identity And Provenance

Every profile should record:

- repository, snapshot, node, content hash, language, and node kind;
- parser, parser version, profile schema version, and extraction mode;
- source span and generated/test/vendor classifications; and
- diagnostics for partial parsing or unavailable measurements.

Profiles from different parser or metric versions are not directly comparable
unless the report explicitly normalizes them.

### Physical And Lexical Size

Candidate measurements:

- physical source lines;
- non-blank, non-comment source lines;
- logical statement count;
- character and UTF-8 byte counts;
- identifier and operator counts;
- comment and docstring proportions; and
- exact source-token counts for registered tokenizer profiles.

Logical statements should be the primary cross-language size measurement.
Physical lines remain useful for review ergonomics but are affected by braces,
attributes, decorators, multiline expressions, formatting, and comments.

### Control-Flow Load

Candidate measurements:

- cyclomatic complexity;
- cognitive complexity under a documented CodeMesh profile;
- maximum nesting depth;
- branch, loop, exception-handler, return, and jump counts;
- compound-condition and pattern-match complexity; and
- direct or indirect recursion where the parser can establish it.

The calculation must publish its language-specific rules. CodeMesh must not
label two values comparable merely because both use the name `complexity`.

### State And Dependency Load

Candidate measurements:

- parameters and local variables;
- distinct read and mutation targets;
- live-variable pressure when supported;
- incoming and outgoing call relationships;
- distinct referenced types and namespaces or modules;
- exception and cleanup responsibilities; and
- side-effect domains such as filesystem, network, database, process, UI, and
  shared-state interaction.

Graph degree alone is not a quality metric. A coordinator can legitimately have
high fan-out while remaining linear and cohesive.

### Conceptual Load And Cohesion

Candidate deterministic signals include:

- AST and control-flow regions;
- comments or labels that identify internal phases;
- consecutive blocks with materially different referenced types or callees;
- distinct mutation and side-effect domains;
- vocabulary discontinuities between statement regions; and
- whether separate regions change for different source-backed reasons.

Optional local semantic models may propose phase boundaries or cohesion scores,
but their outputs must be labeled derived, model-bound evidence. They cannot
override parser facts or independently establish a refactoring finding.

## Token Accounting

CodeMesh must not use a universal conversion from source lines or characters to
tokens. Token count varies with the exact tokenizer, programming language,
identifier style, punctuation, whitespace, Unicode, special tokens, and the
contextual prefix or prompt wrapped around the source.

For an available tokenizer, CodeMesh should calculate:

```text
tokens = tokenize(tokenizer_identity, complete_rendered_payload)
```

Separate counts are required for:

1. the raw method body;
2. the contextual embedding input;
3. the complete summary prompt;
4. one rendered context-package item; and
5. the complete agent-facing tool response.

A token measurement must be bound to the provider, model, tokenizer and
revision, rendering profile, and any prompt or prefix version. A changed
identity creates a new measurement rather than silently replacing the old one.

When the exact tokenizer is unavailable, CodeMesh may report a conservative
estimate derived from a frozen corpus:

```text
estimated_tokens = characters * p95(tokens_per_character | language, profile)
```

The response must label the result `estimated`, identify the calibration
corpus, and never use the estimate to claim that a provider accepted the input.

### Usable Model Budgets

The advertised model context window is a capacity ceiling, not an ideal node
size. For an agent or summarizer, the usable retrieval budget is approximately:

```text
usable_retrieval_tokens =
    total_context_tokens
    - fixed_instructions_and_tool_schema
    - conversation_and_task_tokens
    - reserved_output_tokens
    - safety_margin
```

An adaptive context package should budget across the expected relevant items
and prefer high-ranked, semantically complete evidence. It should not grant one
large method the entire available context merely because it fits.

For embeddings, CodeMesh should distinguish:

- the **capacity threshold**, where the rendered payload is rejected or
  truncated; and
- the **quality threshold**, where one vector loses retrieval specificity
  before the hard capacity limit is reached.

The quality threshold must be measured for each complete embedding profile.

## Initial Review Scale

The following bands are hypotheses for corpus stratification and initial rule
evaluation. They are not accepted product thresholds.

| Signal | Comfortable seed band | Review seed band | High-risk seed band |
| --- | ---: | ---: | ---: |
| Logical statements | `<= 20` | `21-40` | `> 40` |
| Cyclomatic complexity | `<= 5` | `6-10` | `> 10` |
| Cognitive complexity | `<= 10` | `11-15` | `> 15` |
| Maximum nesting depth | `<= 2` | `3` | `> 3` |
| Reviewed semantic phases | `1` | `2` | `>= 3` |
| Model-input pressure | `<= 0.5` | `> 0.5` and `<= 1.0` | rejected or truncated |

The eventual thresholds should be language-, node-kind-, and profile-specific.
CodeMesh should retain the raw measurements and reasons even if a user-facing
surface presents a simpler severity.

An initial decision policy may be evaluated as follows:

- line or statement count alone never recommends source decomposition;
- one high-risk signal or two review-level signals produces a review finding;
- two independent high-risk human-load signals produce a decomposition
  candidate;
- rejected or truncated model input produces a representation finding even
  when the source method is maintainable; and
- suppressions require an explicit reason and must not erase the measurements.

This policy must be replaced or calibrated from retained evidence before it is
enabled by default.

## Language-Specific Calibration

### C# And .NET

The initial implementation should use Roslyn syntax, semantic, control-flow,
and data-flow APIs where available. It should account for:

- braces and attributes that inflate physical lines;
- local functions, lambdas, async/iterator state machines, and exception flow;
- pattern matching, switch expressions, and compound boolean conditions;
- LINQ pipelines that can compress several transformations into one statement;
- partial types and multiple declarations; and
- generated code and source generators.

Logical symbol identity and declaration source must remain distinct. A finding
must cite the declaration span that produced its measurements.

### Python

Python requires an AST-based profile rather than regex or indentation-only
definition discovery. It should account for:

- comprehensions and generator expressions with nested clauses;
- decorators, context managers, exception flow, and async constructs;
- dynamic dispatch and monkey-patching limits;
- multiple statements on one physical line;
- docstrings and type annotations; and
- closures and non-local state.

Python and C# may share measurement names only where their calculation and
meaning are documented as comparable. Physical-line thresholds should be
calibrated independently.

### Separate Strata

Generated code, tests, mappings, builders, flat dispatch tables, parser tables,
and declarative configuration often have different acceptable size profiles.
They should be reported separately rather than weakening production-code gates
for every method.

## Representation Decomposition

When a method is a poor representation unit, CodeMesh should preserve its
authoritative method node and may derive bounded child units. Candidate
boundaries include:

- validation and guard regions;
- major control-flow branches;
- loops or transformations;
- external-operation phases;
- error handling and compensation; and
- cleanup or finalization.

Derived units must:

- align to source spans and avoid splitting syntax tokens;
- retain the parent method id, signature, containing type, file, and language;
- carry a versioned segmentation profile and content fingerprint;
- identify overlap explicitly;
- remain replaceable derived records rather than source truth; and
- allow retrieval to return the parent, one child, or a compact hierarchy.

Small child units need contextual prefixes so their embeddings do not lose the
meaning supplied by the containing method or type. CodeMesh should compare
whole-method, independent-child, and context-enriched-child representations
rather than presuming that smaller always means better.

Source decomposition and representation decomposition are separate outcomes:

- `maintainability_review`
- `source_decomposition_candidate`
- `representation_pressure`
- `representation_decomposition_required`
- `combined_load`

## Proposed Read Surfaces

If activated, the smallest useful read-only surface should expose:

- raw method-load measurements and provenance;
- human-maintainability and representation findings separately;
- exact or estimated token counts by profile;
- truncation and omitted-region diagnostics;
- cited source spans and relevant graph relationships; and
- threshold-profile identity and calibration status.

Candidate interfaces may include an offline report command, a repository status
summary, and targeted Agent Access lookup for a known node. Do not add a broad
MCP tool or default context-package payload until evaluation shows that agents
use the information and that its token overhead is justified.

Any future automated extraction suggestion must be a separate, explicitly
activated design with compiler- or test-backed behavior-preservation gates.

## Evaluation Design

### Fixed Corpus

Use immutable C# and, after parser activation, Python corpus manifests. Each
item should record repository and commit, node and content hash, language,
node kind, source span, profile measurements, generated/test classification,
and reviewed labels.

Stratify the corpus across:

- small, medium, large, and extreme methods;
- low and high control-flow complexity;
- linear orchestration and dense expression-oriented code;
- stateful, error-handling, concurrency, and resource-lifecycle behavior;
- misleadingly short but conceptually dense methods; and
- long but intentionally flat or declarative methods.

Do not tune and qualify on the same repositories.

### Human Outcomes

Candidate evidence includes:

- independent reviewer decomposition labels and reasons;
- comprehension-task correctness and elapsed time;
- change-task correctness and introduced defects;
- review comments and review duration where collection is authorized;
- historical change coupling and corrective churn; and
- agreement and disagreement by language and method kind.

Repository history is observational evidence, not causal proof. Method age,
ownership, churn, domain, and repository conventions can confound the result.
Paired behavior-preserving before/after refactors provide stronger evidence
than unmatched cross-project comparisons.

### Retrieval And Representation Outcomes

Compare authoritative whole methods with candidate derived representations.
Queries should target facts near the beginning, middle, and end as well as
cross-cutting method behavior.

Measure:

- capacity failures and truncation fraction;
- Recall@k, MRR, and nDCG;
- citation-span accuracy and required-fact coverage;
- whole-method versus best-child similarity, called the dilution gap;
- missing parent-context and false-positive rates; and
- ingestion time, vector count, storage, and query latency.

The provider-free lexical and graph baseline must remain available. Embedding
comparisons must bind the exact tokenizer and model identity.

### Summary Outcomes

If summaries are included, use the separate
[Summary Model Qualification](summary-model-qualification.md) requirements.
Measure atomic factual precision and recall by method-load band, especially for
truncated inputs and facts late in the method. No summary result can qualify the
source-decomposition heuristic by itself.

### Agent Outcomes

Run matched tasks using whole-method and hierarchical representations only
after deterministic retrieval gates pass. Measure:

- task correctness and safety;
- CodeMesh adoption;
- required-fact and citation completeness;
- elapsed time, input and output tokens, and tool calls;
- correction loops and broad fallback exploration; and
- false confidence caused by incomplete source.

Model-backed agent campaigns are cost-bearing unless proven otherwise and
require explicit authorization. Correctness and safety take precedence over
token or time savings.

## Threshold Derivation And Acceptance

Thresholds should be derived from observed inflection points rather than chosen
only because they are round numbers. Candidate analysis includes interpretable
logistic, ordinal, or monotonic models with language, method kind, and
interaction effects, plus bootstrap confidence intervals.

A threshold profile may be accepted only when:

- its corpus, calculation, and identity are immutable and reproducible;
- independent reviewers reach acceptable agreement on the target finding;
- held-out repositories reproduce the claimed discrimination;
- false-positive and false-negative budgets are declared and met;
- representation findings predict measured truncation or retrieval loss;
- source-maintainability findings are not driven by size alone;
- generated, test, and declarative exceptions are explicit;
- the provider-free baseline does not regress; and
- documentation states the languages, node kinds, and profiles for which the
  threshold is valid.

Until those gates pass, findings must be labeled experimental and disabled by
default.

## Proposed Delivery Sequence

If activated by [Next Steps](next-steps.md) or explicit owner direction:

1. Freeze the metric definitions and method-load profile schema.
2. Implement deterministic C# measurement and an offline report without
   changing ingestion ranking or Agent Access defaults.
3. Build and review the C# corpus; calibrate human-load seed bands.
4. Add tokenizer-bound measurement and representation-pressure reporting.
5. Compare whole-method and structure-aware representation profiles through
   deterministic and live retrieval evaluation.
6. Add a targeted read surface only if it improves diagnosis or agent outcomes.
7. Run explicitly authorized matched agent evaluation.
8. Consider default advisory findings only after held-out replication.
9. Design Python parity separately after an AST-capable Python parser is
   activated.

Each phase should remain independently reviewable and must not silently enable
online models, repository writes, source mutation, or cost-bearing evaluation.

## Research Basis

These references motivate evaluation but do not establish CodeMesh thresholds:

- [An Empirical Study on Maintainable Method Size in Java](https://arxiv.org/abs/2205.01842)
  reports a maintenance-oriented result around 24 lines for its Java corpus.
- [Microsoft cyclomatic-complexity guidance](https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1502)
  documents configurable .NET analysis and its limitations.
- [Cognitive Complexity](https://www.sonarsource.com/blog/cognitive-complexity-because-testability-understandability/)
  motivates flow- and nesting-aware measurement.
- [Dense X Retrieval](https://aclanthology.org/2024.emnlp-main.845/)
  shows that retrieval-unit granularity can affect retrieval and downstream
  results under fixed budgets.
- [Late Chunking](https://arxiv.org/abs/2409.04701) describes the tension
  between shorter retrieval units and lost surrounding context.
- [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) shows that a
  model's formal context capacity does not guarantee uniform use of relevant
  information throughout a long input.
- [Hugging Face tokenizer documentation](https://huggingface.co/docs/tokenizers/main/api/tokenizer)
  illustrates why token counts are bound to a tokenizer pipeline rather than a
  universal character conversion.

External research is prior evidence only. CodeMesh still requires frozen,
language-specific, repository-level retrieval and agent evaluation before
making a product claim.
