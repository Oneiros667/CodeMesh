# one|nine Adoption and Feedback Priority

Document type: owner-activated implementation plan and pilot gate

Reviewed: 2026-09-01

This document defines the bounded one|nine adoption priority selected in
[Next Steps](next-steps.md). Its initial implementation and provider-free pilot
gate passed from clean candidate `ee1d4d9`; the later configured-evaluator
campaign was finalized at `0bde606`, the bounded status-to-context correction
passed the same provider-free gates at `0378740`, and the one-step entry
correction passed them at `8844c21`. Current behavior and evidence remain
authoritative in
[Project Status](../current/project-status.md); this planning record does not
establish that CodeMesh improves one|nine agent outcomes.

## Decision

The selected CodeMesh product work is a safe, measured one|nine pilot that lets
agents use CodeMesh during real repository tasks and return fast, actionable
feedback to CodeMesh development. The pilot activated:

- unambiguous binding and freshness enforcement for isolated checkouts;
- atomic Python and Rust ingestion;
- a first-class Rust parser module;
- the Python relationships needed to connect application code to PyO3 exports;
- repository-owned MCP onboarding for managed one|nine instances; and
- a sanitized local feedback recorder, validator, and summarizer.

The existing C#/.NET product wedge and evidence remain valid within their stated
boundaries. Owner direction activates only the Python and Rust breadth needed by
this pilot. JavaScript and broader parser or SDLC expansion remain deferred
unless measured one|nine tasks justify them.

## Boundaries

- Checkout correctness and freshness precede rollout. No agent may silently use
  the newest, closest, or otherwise implicit snapshot when a binding is missing,
  ambiguous, or stale.
- Start provider-free, with generated summaries and embeddings disabled. Model-
  backed paired evaluation still requires explicit spend authorization.
- Treat Graphify as an existing one|nine exploration aid and comparative
  baseline. The pilot must demonstrate incremental value rather than assuming
  replacement value.
- Treat routine agent feedback as diagnostic product input. It is not a fixture
  pass, controlled agent comparison, release gate, deployment acceptance, or
  production authorization.
- Do not automatically create external issues, edit CodeMesh, change priorities,
  or transmit repository material from feedback packets.
- Do not retain raw prompts, MCP payloads, source excerpts, secrets, credentials,
  or private environment values in feedback by default.

## Ordered Delivery

### 1. Checkout-safe integration

Complete the outstanding v1 safety work in
[Agent Integration Contract](agent-integration-contract.md):

1. bind MCP startup to an explicit project, checkout, repository root, and
   source view;
2. reject missing, ambiguous, commit-mismatched, or source-view-mismatched
   context packages on the server side;
3. add a provider-free probe that launches the exact configured stdio command,
   checks server instructions and the tool profile, reaches the stores, resolves
   the intended checkout, and proves snapshot freshness; and
4. make installation and repository guidance changes reviewable and opt-in.

A shared local CodeMesh service may serve multiple developer checkouts only
when these bindings keep their snapshots isolated. A single unbound global MCP
alias is not an acceptable one|nine integration.

### 2. Atomic Python and Rust ingestion

Add a language-set ingestion contract, such as `--languages python,rust`, that
publishes one atomic snapshot for a checkout. Snapshot identity, parser-profile
fingerprints, refresh, and watch must preserve the complete selected language
set. A later language-specific ingest must not silently replace a composite
active snapshot with a partial graph.

Add Python imports, calls, tests, and PyO3 boundary relationships sufficient to
connect one|nine application symbols to the native module. Record JavaScript as
an explicit coverage gap when it appears in a task rather than hiding it behind
partial results.

### 3. Rust parser module

Add `src/CodeMesh.Parser.Rust` and expose `rust` through the CLI, ingestion
contracts, parser profiles, tests, and documentation. The initial parser must
emit stable source spans and content hashes for:

- files and modules;
- structs, enums, traits, functions, and methods;
- `impl` blocks and trait implementations;
- `use` imports, calls, and type references;
- Rust test functions and their attributes; and
- PyO3 modules, classes, functions, and exported names.

Repository enumeration must exclude Cargo `target` output or honor applicable
ignore rules. Context packages involving Rust must recommend the repository's
relevant formatting, Clippy, and test commands.

### 4. Durable agent feedback

Provide a versioned local recorder and validator that writes ignored artifacts
under `.codemesh-feedback/` in each participating checkout. Each packet must be
small enough to review and include:

- schema version and diagnostic or controlled-evaluation classification;
- one|nine role, repository root, branch, commit, and dirty state;
- CodeMesh commit, project, checkout, snapshot, language set, and parser profile;
- task family and CodeMesh tools attempted or called, without raw payloads;
- helpful, incorrect, missed, stale, or ambiguous returned paths;
- fallback reason and validation outcome;
- issue category, such as setup, binding, freshness, missing language, missing
  relationship, ranking, budget, or validation;
- a minimal reproduction or expected target set when safe to retain; and
- a proposed smallest correction and reporter confidence.

Add a CodeMesh-side summarizer that reads validated packets from the managed
checkout outboxes, groups recurring failures, preserves exact commit and
snapshot provenance, and produces a prioritized review packet. The CodeMesh
agent or maintainer decides whether a packet warrants implementation,
evaluation, documentation, or no action.

### 5. Instance-owned rollout

Extend the one|nine instance configuration repository to generate and validate
reviewable project-scoped MCP configuration and repository guidance for each
participating checkout. Configuration must forward secret names or use a safe
launcher; it must not copy secret values into tracked files or feedback.

Begin with one pinned, clean checkout. Expand only after the live probe and
feedback path pass for that checkout. Primary, Secondary, Tertiary, Release, and
Hotfix may participate with exact role-specific bindings. Keep Run-only outside
the initial rollout because its operational role and pinned source require a
separate acceptance decision.

Release-checkout retrieval and feedback remain developer-tool evidence. They do
not establish release readiness or authorize deployment.

### 6. Evaluation and improvement loop

Create a provider-free one|nine live suite with real expected files, symbols,
and relationships for:

- Python implementation discovery, impact navigation, and test selection;
- Rust implementation discovery, call/type navigation, and Rust validation;
- Python-to-PyO3-to-Rust navigation;
- clean and dirty source views;
- wrong-checkout, ambiguous-checkout, and stale-snapshot rejection; and
- compact package behavior under the normal MCP tool profile.

Compare the pilot with ordinary repository exploration plus the existing
Graphify integration. Use feedback packets to find candidate improvements, but
retain controlled suites, prompts, gold targets, commits, snapshots, and
outcomes separately. The first explicitly authorized configured/onboarded
campaign used identical control and treatment task prompts and completed safely,
but no treatment retrieved context. Treat that as measured handoff evidence,
not product-benefit evidence.

## Completion Gates

The initial priority is complete only when:

1. the checkout binding and provider-free runtime probe fail closed in negative
   cases and pass against the selected one|nine pilot checkout;
2. a single active snapshot contains the required Python and Rust graph without
   partial-language replacement;
3. Rust fixtures and the selected one|nine crate pass structural, relationship,
   PyO3, test-discovery, determinism, and path-exclusion checks;
4. one|nine agents can record sanitized, valid feedback and CodeMesh can produce
   a provenance-preserving prioritized summary;
5. the provider-free one|nine live suite passes its frozen safety and retrieval
   gates; and
6. canonical current documentation is updated to describe only the behavior and
   evidence actually implemented and verified.

Passing these gates establishes a usable bounded pilot. A broader product-
benefit claim still requires adopted, comparable agent outcomes with
attributable correctness, safety, or efficiency improvement.

## Pilot Gate Result

All six completion gates passed on 2026-08-31 from clean CodeMesh candidate
`ee1d4d9` against Primary commit
`e12d0281b687e58c2baac85f771a684df6fa8552` and the provider-free composite
snapshot recorded in [Project Status](../current/project-status.md). The frozen
instance-owned suite passed four positive retrieval cases for Python, Rust,
test selection, and the PyO3 boundary, plus fail-closed wrong-checkout,
wrong-root, wrong-source-view, and dirty-checkout cases. It validated three
feedback packets and produced a provenance-preserving summary. The pinned
YoutubeDownloader live gate also passed after a discovered partial-symbol
ranking regression was corrected and retested.

This result is clean-candidate provider-free diagnostic evidence. Configured/
onboarded paired agent tasks, not this pilot gate, can test attributable product
benefit. Exact identities, metrics, report hashes, and the retained failed gate
are in the
[Priority 1 evidence record](../evaluation/evidence/onenine-priority1-ee1d4d9.json).

Subsequent configured-evaluator corrections preserved the initial gate as
historical evidence and finalized the frozen campaign at CodeMesh candidate
`0bde606` against Primary commit `fe2f761`. That provider-free preflight, all
eight one|nine retrieval and rejection gates, and the pinned YoutubeDownloader
live gate passed. The exact final identities and claim ceiling are retained in
the [configured one|nine evidence record](../evaluation/evidence/configured-onenine-provider-free-0bde606.json).

The bounded status-to-context correction is frozen at clean candidate
`0378740`. The full deterministic checks, configured preflight, eight one|nine
gates, three retained feedback packets, and pinned YoutubeDownloader live gate
all passed again without invoking a model provider. The exact identities and
claim ceiling are retained in the
[corrected provider-free evidence record](../evaluation/evidence/configured-onenine-provider-free-0378740.json).

The one-step entry correction is frozen at exact clean candidate `8844c21`.
The full deterministic checks, configured preflight, eight one|nine gates,
three retained feedback packets, and pinned YoutubeDownloader live gate all
passed with provider mode `none`. Instance configuration commit `f9f199d`
repinned only Primary; all managed-instance generation checks passed without
activating another checkout. The exact identities and claim ceiling are in the
[one-step provider-free evidence record](../evaluation/evidence/configured-onenine-provider-free-8844c21.json).

The first authorized paired model campaign from those exact identities
completed three correct and safe pairs. Two treatments called repository status,
none called the context-package tool, and the verdict was `insufficient` with no
attributable wins. The handoff correction now has full clean-candidate
provider-free verification. The sanitized historical outcome is retained in the
[configured agent evidence record](../evaluation/evidence/configured-onenine-agent-0bde606.json).

That separately authorized `0378740` campaign also completed three correct and
safe pairs but remained `insufficient`. One treatment called repository status,
none called the context-package tool, and there were no attributable wins. The
status-result action therefore did not produce the required handoff. Preserve
the consumed campaign in the
[corrected configured agent evidence record](../evaluation/evidence/configured-onenine-agent-0378740.json).

The authorized one-step `8844c21` campaign then completed three correct and safe
pairs with context-package adoption in every treatment. It had no attributable
wins or regressions and received a `neutral` verdict; median duration was 1.39%
lower and median tokens were 4.13% higher, both within the configured 10%
threshold. This establishes the selected one|nine handoff, not product benefit.
Preserve the consumed result in the
[one-step configured agent evidence record](../evaluation/evidence/configured-onenine-agent-8844c21.json).
Configured Config.Net preparation now passes provider-free at exact candidate
`b16eee7`. Its separately authorized paired campaign adopted the context-package
tool in all three treatments but `regressed`: all three controls passed, while
two treatments missed required implementation or test citations. Preserve the
consumed negative result in the
[configured Config.Net agent evidence record](../evaluation/evidence/configured-config-net-agent-b16eee7.json).
The provider-free task-shaped package-coverage diagnosis now shows the full
task misses six of seven targets while four focused task-derived queries cover
all seven. The bounded guidance correction is implemented and passes
deterministic Python checks, but commit and clean-candidate provider-free gates
remain before any separately authorized paid retest. No retry or further model
spend is currently authorized.
