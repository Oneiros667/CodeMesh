# Graph Intelligence And Agent Memory Design

Status: proposal

Activation gate: implement this proposal only where current controlled agent
evaluation identifies relationship trust, path discovery, or impact analysis as
a material failure or overhead source. The product-proof baseline and one
representative external C# repository take priority over broad delivery of this
design.

This document records design improvements identified by comparing CodeMesh with
[Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), using the
local Graphify `0.9.27` checkout at commit `62b1d43`. The upstream link
identifies the comparison source; the pinned local commit identifies the source
actually reviewed. This document is planning context, not implemented behavior.
Current CodeMesh behavior remains documented in `docs/architecture.md` and
`docs/agent-access-contracts.md`.

## Purpose

CodeMesh already provides capabilities that should remain central:

- source-grounded context packages with snippets and source spans;
- hybrid lexical, vector, and generated-summary retrieval;
- repository registry, ingestion history, and Git freshness diagnostics;
- incremental graph, content, embedding, and summary persistence;
- pre-persistence secret redaction;
- structured REST, MCP, CLI, web, and .NET interfaces; and
- deterministic, live, agent, and model evaluation levels.

The comparison exposed several complementary gaps:

- relationship records do not communicate how strongly an edge is supported;
- Agent Access does not expose shortest paths, reverse impact, communities, or
  architectural hubs;
- CodeMesh has no explicit record of useful answers, dead ends, or corrections;
- parser depth is high for C# but baseline language breadth is limited;
- the normal deployment profile is heavier than a single-repository local tool;
- graph reports and portable visual exports are limited; and
- pull-request and change-impact intelligence remains roadmap work.

The design below adds those capabilities without weakening source grounding,
freshness evidence, safety controls, or structured contracts.

## Design Principles

### Structural truth and experiential evidence remain separate

Parser and ingestion output describes the repository. Agent outcomes describe
experience using that repository context. Outcome records must never silently
rewrite parser-produced nodes or relationships.

### Source evidence outranks derived structure

Graph traversal can discover candidate paths and impacts, but returned results
must carry source spans, relationship evidence, and freshness state. An inferred
path is navigation evidence, not proof that runtime behavior follows that path.

### High-fidelity parsers and broad baseline parsers can coexist

Roslyn remains the authoritative C# parser. A future tree-sitter-style parser
tier may provide breadth for additional languages, but it must declare lower
semantic fidelity and must not overwrite higher-fidelity records.

### Local-first does not mean state-free

An embedded or portable profile should reduce operational setup while preserving
stable identifiers, repository boundaries, freshness metadata, redaction, and
the ability to migrate to the service-backed stores.

### Agent-facing writes are explicit

Outcome memory, curation, and repository mutation must be opt-in. MCP write
tools require deliberate confirmation and should be disabled by default in
read-only and evaluation profiles.

## Proposed Capability Model

### 1. Relationship Evidence And Confidence

Extend relationship records with evidence that explains why an edge exists.
The design should distinguish these dimensions:

- `provenance`: parser, resolver, imported artifact, model, runtime trace, or
  human curation;
- `confidence`: explicit, inferred, or ambiguous;
- `confidence_score`: optional normalized score for ranked derived evidence;
- `evidence_span`: the source location of the call, import, reference, or other
  relationship site;
- `extractor`: parser or resolver name and version; and
- `observed_at`: ingestion or trace timestamp when time is relevant.

Rules:

- Parser-emitted semantic edges may be `explicit` when the compiler or parser
  binds both endpoints.
- Heuristic name resolution must be `inferred`, even when its score is high.
- Model-generated relationships must never be labeled `explicit`.
- Runtime traces may corroborate a static edge but should remain separate
  evidence rather than overwriting static provenance.
- Context packages should display the evidence site and confidence without
  requiring callers to decode metadata JSON.

This supports safer path finding, impact analysis, and mixed parser tiers.

### 2. Deterministic Graph Analysis

Add a read-only graph-analysis layer over repository-scoped CodeMesh records.
Initial operations should be deterministic:

- shortest path between two nodes;
- reverse affected-node traversal from a changed node;
- direct and bounded transitive callers or dependants;
- central nodes by a documented centrality measure;
- repository graph statistics; and
- community detection with stable remapping between nearby ingestion runs.

Candidate Agent Access tools:

- `codemesh_find_path`
- `codemesh_get_impact`
- `codemesh_get_graph_overview`
- `codemesh_get_community`

Required controls:

- repository id is mandatory when node ids are not globally unambiguous;
- depth, relationship kinds, confidence threshold, and output budget are
  bounded;
- high-degree hubs cannot silently flood traversal output;
- truncation is explicit and reports omitted counts;
- every returned relationship includes direction, kind, evidence location, and
  confidence; and
- responses include repository freshness and indexed commit metadata.

Path finding should preserve direction by default. An undirected mode may be
offered for discovery, but the response must label it as such.

### 3. Explicit Agent Outcome Memory

Introduce an optional experiential layer that records whether retrieved context
helped complete a task.

Supported outcomes should include:

- `useful`
- `dead_end`
- `corrected`
- `unverified`

An outcome record should contain:

- repository id and indexed commit;
- task or question summary;
- cited node and relationship ids;
- outcome and optional correction;
- validation evidence, when available;
- actor and timestamp;
- retention classification; and
- a content fingerprint used for staleness checks.

Derived recommendations may classify nodes or packages as:

- preferred after corroborated useful outcomes;
- tentative after one useful outcome;
- contested after conflicting signals; or
- stale when cited content has changed.

Safety and trust rules:

- no automatic conversation capture;
- no credentials, raw environment values, or unredacted source in outcome
  records;
- one outcome cannot establish a trusted recommendation;
- corrections and recent failures outweigh older positive evidence according to
  a documented policy;
- deleted or materially changed nodes cannot remain preferred without review;
- structural search results remain available even when outcome memory is
  disabled; and
- evaluation runs use isolated outcome stores or disable writes entirely.

The first implementation should expose outcome memory through CLI or REST before
adding MCP writes. A later MCP tool should require `confirm = true` and return a
preview of the record being stored.

### 4. Tiered Parser Breadth

Define parser tiers instead of treating all extracted relationships as equally
authoritative.

#### Tier A: compiler or platform semantic parser

Examples include Roslyn for C#. It may emit bound symbols, declarations, calls,
reads, writes, inheritance, and type usage with high-confidence evidence.

#### Tier B: deterministic syntax parser and resolver

A tree-sitter-style worker can add baseline coverage for more languages. It may
emit files, declarations, imports, containment, and conservatively resolved
calls. Derived cross-file edges must carry resolver provenance and confidence.

#### Tier C: semantic document or model enrichment

Optional model-backed extraction can connect design documents, concepts, and
code. These edges are derived context and must not replace parser-produced
structure.

Merge precedence should be explicit:

1. retain all non-duplicate evidence records;
2. prefer higher-fidelity node attributes for canonical navigation;
3. preserve lower-tier evidence when it adds a distinct source or relationship;
4. never upgrade confidence merely because two heuristic extractors agree; and
5. record parser versions so a re-ingestion can explain changed topology.

Python import and call relationships are the best first test of this model.

### 5. Portable Repository Snapshot

Design an optional portable snapshot for small, local, or read-only use cases.
It should package enough information to serve bounded Agent Access queries
without requiring the full Neo4j, MongoDB, and Qdrant profile.

Minimum snapshot contents:

- repository identity and indexed Git state;
- nodes and relationships with evidence;
- redacted source snippets or content references;
- optional summaries;
- schema and producer versions; and
- integrity hashes.

The snapshot is not automatically a new canonical store. An ADR should compare:

- a single SQLite artifact;
- a compact archive containing graph and content indexes; and
- an embedded storage profile behind existing store contracts.

Vector search may be omitted or provided through an optional sidecar. Portable
mode must report unavailable capabilities rather than silently degrading search.

### 6. Reports, Communities, And Exports

Add human-readable outputs derived from the same stored graph:

- repository overview with node and relationship counts;
- central nodes and high-degree hubs;
- detected communities and cross-community connections;
- confidence and provenance audit;
- Markdown architecture report;
- interactive local graph view; and
- portable GraphML or JSON export.

Generated reports must include the indexed commit and generation timestamp.
They should link back to source spans and state when output is truncated.

Reports are derived artifacts. They do not replace `docs/architecture.md`, ADRs,
or source code as authority.

### 7. Change And Pull-Request Impact

Build change impact in two stages.

#### Local change impact

Map a Git diff to changed nodes, then run bounded reverse traversal over
selected relationship kinds. Return:

- directly changed nodes;
- affected callers, dependants, tests, deployment artifacts, and docs;
- confidence and evidence for every propagation step;
- relevant validation commands; and
- uncertainty where a changed file has incomplete parser coverage.

#### Pull-request intelligence

After local impact is reliable, ingest or query pull-request metadata:

- changed files and symbols;
- base branch and indexed base commit;
- CI and review state;
- ownership metadata;
- overlapping graph areas between open changes; and
- validation and merge-risk indicators.

Pull-request state is time-sensitive external data. It must not be inferred from
an old graph snapshot, and write or merge operations remain outside the initial
read-only design.

## Architecture Boundaries

The proposed capabilities fit existing CodeMesh boundaries:

- parsers emit nodes, relationships, evidence, and diagnostics;
- ingestion normalizes provenance, applies redaction, and persists records;
- storage adapters expose repository-scoped graph analysis primitives;
- Agent Access composes graph results with content, summaries, freshness, and
  validation recommendations;
- Control and CLI manage refresh, export, outcome recording, and verification;
  and
- evaluation measures retrieval and task outcomes without changing the source
  checkout or production stores.

Community detection, centrality, and reflection should be separate services or
pure modules over storage contracts. They should not be embedded in parser
workers.

## Delivery Sequence

### Phase 1: trustworthy graph edges

1. Add relationship provenance, confidence, and evidence spans.
2. Backfill deterministic values for current C# and deployment relationships.
3. Include evidence in neighbors and context packages.
4. Add contract, persistence, and redaction tests.

### Phase 2: path and impact queries

1. Add repository-scoped shortest path and reverse impact primitives.
2. Expose bounded read-only Agent Access tools.
3. Connect impact results to current validation recommendations.
4. Add live evaluation cases for direction, truncation, and stale indexes.

### Phase 3: architecture overview

1. Add graph statistics, centrality, and deterministic community detection.
2. Generate a Markdown overview and local UI views.
3. Establish stability measurements across incremental refreshes.

### Phase 4: parser breadth

1. Define the parser-tier contract.
2. Deepen Python imports and calls as the reference Tier B implementation.
3. Evaluate another representative language before generalizing the worker.

### Phase 5: experiential memory

1. Add outcome records and deterministic reflection in an isolated store.
2. Surface read-only recommendations with staleness and provenance.
3. Add explicit CLI or REST recording.
4. Consider confirmed MCP writes only after safety and retention review.

### Phase 6: portability and SDLC expansion

1. Decide portable snapshot storage through an ADR.
2. Add report and export formats.
3. Extend local change impact to pull requests, ownership, and CI metadata.

## Evaluation Gates

Each phase needs evidence beyond unit tests.

- Relationship confidence: fixtures prove confidence never upgrades across
  heuristic or model-only evidence.
- Paths: golden cases verify endpoints, direction, edge kinds, evidence spans,
  and deterministic tie-breaking.
- Impact: seeded changes verify expected affected nodes and bounded false
  positives.
- Communities: nearby incremental ingestions measure membership and identifier
  stability.
- Parser breadth: representative repositories measure symbol, import, and call
  recall against reviewed targets.
- Outcome memory: tests cover corroboration, corrections, time decay, deleted
  nodes, changed content, redaction, and disabled-write profiles.
- Portable mode: contract tests compare supported query results with the
  service-backed profile.
- Agent usefulness: control and treatment runs measure correctness first, then
  tokens and elapsed time, while preserving freshness and safety gates.

Published comparisons must name the repository commit, indexed commit, parser
versions, enabled stores, model providers, query budgets, and whether results
come from fixtures, live stores, or model-backed agent runs.

## Non-Goals

This proposal does not authorize:

- replacing Roslyn with a lower-fidelity parser;
- treating graph paths as runtime proof;
- silently recording conversations or agent activity;
- enabling agent-facing writes by default;
- weakening secret redaction for portable output;
- making optional model providers mandatory;
- replacing the current structured context package with graph-only text; or
- claiming Graphify benchmark results as CodeMesh performance evidence.

## Decision Summary

CodeMesh should remain source-grounded and service-capable. Controlled product
evaluation should select the next investment. When weak or opaque relationships
are the measured constraint, relationship evidence followed by deterministic
path and impact queries is the preferred sequence. Communities, broader
parsers, outcome memory, and pull-request intelligence remain deferred until
the initial C#/.NET workflow demonstrates repeatable agent benefit.
