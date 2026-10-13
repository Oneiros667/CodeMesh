# CodeMesh developer handbook

Document type: human developer entry point

Source reviewed: `348709de06f971e4ef15fde7f6b7b082799c6777` on `main`.
Review date: 2026-09-05. The working tree was clean before this documentation
change. The chapters describe inspected implementation and representative
tests; their walkthroughs are source traces, not newly executed live runs.
Historical measurements remain bound to the candidates in
[Project Status](../current/project-status.md).

## What CodeMesh does

CodeMesh turns a selected repository into a queryable index of source structure,
relationships, and source text. A developer or coding agent can ask where a
behavior is implemented, follow likely callers and dependencies, and obtain a
compact package of relevant source locations with suggested validation. The
package points the reader back to the checkout to verify a conclusion before
changing code.

The initial product focus is C#/.NET. Its C# parser uses Roslyn compilations to
connect declarations to symbols and resolve local calls and member access.
Python, Rust, Markdown, and deployment parsers cover additional workflows with
more structural analysis. A relationship from one of these parsers is a useful
navigation lead; it is not a runtime execution trace or a complete proof of
change impact. The [parser chapter](../current/ingestion-internals.md) explains
the different evidence each parser produces.

There are two principal halves. **Ingestion** is the .NET write path: select
files, parse them, redact stored content, calculate identity, write the stores,
and publish a snapshot selection. **Agent Access** is the Python read path:
resolve that selection, retrieve and rank candidates, attach source and
relationships, and serve a response. Normal MCP access also checks that the
selected index belongs to the exact clean checkout. The Python service reads
the stores directly; it does not ask the .NET CLI to ingest on demand.

This distinction explains a common debugging mistake: a reachable REST service
does not imply an indexed repository, and a successfully indexed dirty checkout
does not imply that normal MCP access will accept it. See
[IngestionOrchestrator.IngestAsync](../../src/CodeMesh.Ingestion/IngestionOrchestrator.cs),
[CodeMeshReadStore.get_context_package](../../agent-access/codemesh_agent_access/store.py),
and the rejection tests in
[test_store_components.py](../../agent-access/tests/test_store_components.py).

## Vocabulary

| Term | Meaning in this implementation |
| --- | --- |
| Repository root | The selected filesystem directory. Its path is provenance, not the persistent project identity. |
| Project identity | A persistent `prj_` id for the indexed repository, potentially shared deliberately by multiple checkouts. Distinct from a Roslyn/MSBuild project. |
| Parser project | The `CodeNode.Project` grouping, such as a C# project name. This participates in fingerprints and is not a `prj_` id. |
| Checkout | A particular local working tree, identified by a private `chk_` marker. |
| Alias | A human-readable selector retained with project identity. Aliases can collide; ambiguous reads are rejected. |
| Node | A `CodeNode`: a file, declaration, symbol, document section, or other indexed entity. |
| Stable key | A parser-produced logical key. Its stability depends on the parser; a declaration key can include source position. |
| Relationship | A directed edge with a kind and optional label/metadata, such as `Contains`, `Defines`, or `Invokes`. |
| Source span | Repository-relative file and line/column coordinates. Unknown spans use zero; C# logical symbols often need a declaration for concrete source. |
| Content hash | SHA-256 identity of a stored text item, recalculated if redaction changes that item. It may identify a fragment rather than an entire file. |
| Source view | The canonical fingerprint of effective parser output after redaction, including graph structure and content identities. It is not simply the Git commit. |
| Snapshot | A deterministic `snp_` namespace for that project, source view, ingestion scope, parser profile, and graph schema. |
| Slot | A versioned reference selecting a snapshot: checkout-current, clean branch-head, explicit pin, or evidence slot. |
| Generation | One staging/publication attempt. Identical source can produce multiple generations for the same snapshot. |
| Ingestion run | Execution metadata and write statistics. The successful run record is separate from generation failure tracking. |
| Binding | The configured project, checkout, absolute root, and optional source-view hash used by normal MCP. |
| Context hit | A ranked candidate with source location, identity, score components, and optional expansion information. |
| Context package | Hits hydrated with content metadata, budgeted snippets, optional summaries, grouped relationships, and validation suggestions. |
| Enrichment | Optional embeddings or generated summaries. Core source retrieval can operate without a model provider. |

The definitions come from
[graph records](../../src/CodeMesh.Domain/Graph/GraphTypes.cs),
[snapshot contracts](../../src/CodeMesh.Domain/Contracts/SnapshotContracts.cs),
[SnapshotIdentity.Compute](../../src/CodeMesh.Ingestion/SnapshotIdentity.cs), and
[Python response models](../../agent-access/codemesh_agent_access/models.py).
The detailed identity chapter explains where the same field name has different
public and storage meanings.

## Chapter index

| Chapter | Questions it answers |
| --- | --- |
| [Architecture and code navigation](../current/architecture.md) | Which processes run, what depends on what, and where does a change belong? |
| [Identity and persistence](../current/identity-and-persistence.md) | What are the keys, store responsibilities, publication boundaries, and retention rules? |
| [Ingestion internals](../current/ingestion-internals.md) | How do selection, parsers, redaction, incremental writes, refresh, and watch work? |
| [Retrieval internals](../current/retrieval-internals.md) | How do binding, freshness, search, ranking, expansion, and packaging work? |
| [Enrichment and evaluation internals](../current/enrichment-and-evaluation.md) | How are embeddings, summaries, feedback, installation, and evaluation connected? |
| [Three end-to-end walkthroughs](developer-walkthroughs.md) | What calls what during ingestion, context retrieval, and changed-source refresh? |
| [Development and debugging](development-and-debugging.md) | How do I set up, choose entry points, inspect failures, and recover locally? |
| [Making changes](making-changes.md) | Which producer, consumer, tests, and documents must move together? |
| [Testing](../evaluation/testing.md) | Which harness proves which invariant, and what validation does my change require? |

These chapters explain implementation. Keep exact interface fields in
[Agent Access Contracts](../current/agent-access-contracts.md), supported
invocations in [COMMANDS.md](../../COMMANDS.md), and security policy in
[Security and Redaction](../current/security-and-redaction.md). The
[documentation hub](../README.md) defines the complete authority order.

## Reading paths

For onboarding, read this introduction and glossary, then architecture, the
three walkthroughs, and local development. Return to identity, ingestion, or
retrieval for the detailed mechanisms behind the walkthroughs. Read the testing
guide before your first change.

For debugging, start with the symptom table in
[Development and debugging](development-and-debugging.md#diagnose-by-symptom).
Establish the process, checkout, selected snapshot, and provider mode before
following the corresponding ingestion or retrieval trace. An empty response
can result from filtering, unavailable stores, or ranking; the response alone
does not identify which one.

For implementation work, use architecture's
[where to change what](../current/architecture.md#where-to-change-what) table,
then the relevant [change walkthrough](making-changes.md). Read both ends of a
serialized contract. Use the risk map in Testing rather than treating a single
unit test as complete integration evidence.

## Boundaries and known questions

The core behavior is repository-scoped parsing, source-backed retrieval, local
snapshot lifecycle, and checkout-bound MCP access. Model generation is optional.
Shared-store tenancy, full language semantics outside the bounded parsers,
general runtime impact proof, and broader SDLC or agent-memory systems remain
proposals unless source and current contracts establish otherwise.
[Next Steps](../planning/next-steps.md) controls activation of future work.

This handbook does not update product-benefit results. Deterministic fixtures,
live-store integration, configured retrieval, and paired agent evaluation answer
different questions. The [evaluation chapter](../current/enrichment-and-evaluation.md)
and [methodology](../engineering/methodology.md) explain those boundaries.

Source inspection also found limits worth preserving for maintainers:
publication is not a distributed transaction; cleanup has no shared-service
coordinator; freshness does not reparse the checkout; and some parser/snippet
edge cases need focused regression work. The concrete findings and their
verification limits are recorded in
[Inspection findings](development-and-debugging.md#inspection-findings).
They were documented without changing application code or claiming a live
reproduction.
