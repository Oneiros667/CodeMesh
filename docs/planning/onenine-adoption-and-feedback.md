# one|nine Adoption and Feedback Priority

Document type: owner-activated implementation plan and pilot gate

Reviewed: 2026-08-31

This document defines the bounded one|nine adoption priority selected in
[Next Steps](next-steps.md). Its initial implementation and provider-free pilot
gate passed locally; a clean-candidate repeat remains required. Current behavior
and evidence remain authoritative in
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
outcomes separately. With explicit model-spend authorization, a later paired
campaign may evaluate the shipped configured/onboarded integration using
identical control and treatment task prompts.

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

All six completion gates passed locally on 2026-08-31 against Primary commit
`11c6d7682890da9979bbc5b1fbec5e2c33b89fff` and the provider-free composite
snapshot recorded in [Project Status](../current/project-status.md). The frozen
instance-owned suite passed four positive retrieval cases for Python, Rust,
test selection, and the PyO3 boundary, plus fail-closed wrong-checkout,
wrong-root, wrong-source-view, and dirty-checkout cases. It validated three
feedback packets and produced a provenance-preserving summary.

This result is local diagnostic evidence from an uncommitted CodeMesh working
tree. The next priority is an exact clean candidate and repeat of the gates,
followed only with explicit model-spend authority by configured/onboarded paired
agent tasks. Those tasks, not this pilot gate, can test attributable product
benefit.
