# Making changes to CodeMesh

Document type: task-oriented developer guide

These walkthroughs explain existing extension points without implementing a new
feature. Start with [Architecture](../current/architecture.md#where-to-change-what)
to locate the subsystem, and use [Testing](../evaluation/testing.md) to select
checks. The producer, persisted representation, read consumer, and interface
contract often live in different projects or languages.

## Change a parser's output

Suppose an evidenced C# call-graph bug needs a corrected invocation edge. Begin
with a minimal fixture modeled on
`TestCSharpParserEmitsInvocationAndMemberAccessRelationships` in
[tests/CodeMesh.Tests/Program.cs](../../tests/CodeMesh.Tests/Program.cs). Keep the
example small enough to show the source expression, expected source/target
symbols, and any edge that must be absent. Use a multi-project fixture like
`TestCSharpParserEmitsCrossProjectInvocationRelationships` if resolution across
compilations is the actual failure.

Trace the producer in
[CSharpParseService.cs](../../src/CodeMesh.Parser.CSharp/CSharpParseService.cs).
`ExtractDeclarationNodes` must register target symbol keys before the later
`ExtractRelationships` pass. For an invocation problem, follow
`AddBodyReferenceRelationships`, `ResolveMethodSymbol`, and
`AddSymbolRelationship`; the last resolves only targets that correspond to
indexed symbols. A missing external framework node is different from a broken
local method lookup.

Before changing ids, decide whether the change affects the logical symbol,
source declaration, or just edge metadata. Review
[CodeMeshFingerprint](../../src/CodeMesh.Domain/Utilities/CodeMeshFingerprint.cs)
and [SnapshotIdentity](../../src/CodeMesh.Ingestion/SnapshotIdentity.cs): stable
metadata and relationships influence source identity, while volatile provenance
does not. Parser binary changes are not automatically fingerprinted. Changing a
schema or profile may therefore require an explicit version decision, with an
ADR for a consequential implemented change.

Then inspect the consumers. The
[Neo4j adapter](../../src/CodeMesh.Storage/Neo4j/Neo4jGraphStore.cs) persists the
edge, Python [graph_store.py](../../agent-access/codemesh_agent_access/graph_store.py)
retrieves it, and [store.py](../../agent-access/codemesh_agent_access/store.py)
prioritizes/groups it. An edge can be present in Neo4j yet absent from a package
because of direction, grouping, total limits, or candidate selection. Add a
consumer assertion only when the change actually alters that observable behavior.

| Contract to preserve | Check location |
| --- | --- |
| Every edge endpoint corresponds to the intended local node identity | C# parser fixture and its symbol/declaration assertions. |
| Same effective source remains deterministic | Snapshot/multi-language tests where identity semantics change. |
| New metadata is stored and interpreted consistently | Storage adapter mapping plus Python normalizer tests. |
| Agent-visible relationship remains source-grounded and bounded | Context relationship tests and MCP fixture evaluator. |

For a parser-only fix, use the affected .NET checks. If graph serialization,
lifecycle, or an Agent Access consumer changes, run both suites. Live wiring or
cleanup changes also select the authorized end-to-end smoke path. Update
[Ingestion internals](../current/ingestion-internals.md),
[Architecture](../current/architecture.md), and any changed canonical contract;
update current status only with the resulting evidence actually obtained.

The same pattern applies to structural parsers, but their evidence differs.
For a Python/Rust boundary, review both
[Python import metadata](../../src/CodeMesh.Parser.Python/PythonParseService.cs)
and [Rust export metadata](../../src/CodeMesh.Parser.Rust/RustParseService.cs),
then `CompositeParserClient.AddPyO3Relationships`. Preserve ambiguity rejection
and one combined generation. Adding a parser client also requires CLI selection,
capability/version, path policy, composition, tests, and documentation; the
interface seam alone is not an authorized parser-expansion task.

## Change context ranking

Suppose a recorded multi-term query returns repeated declarations from one file
and misses a relevant implementation file. First distinguish candidate acquisition
from final order. Inspect `search_context_nodes` in
[graph_store.py](../../agent-access/codemesh_agent_access/graph_store.py), then
`_search_lexical_context`, `_lexical_score`, `_diversify_lexical_nodes`,
`_build_context_hit`, and `_ranked_unique_hits` in
[store.py](../../agent-access/codemesh_agent_access/store.py). A final-sort change
cannot improve recall for a node excluded from the raw candidate pool.

Create a regression example using the stub patterns in
[test_context_ranking.py](../../agent-access/tests/test_context_ranking.py).
Express the observable ranking or file-coverage requirement, rather than
asserting every intermediate numeric constant. Preserve existing tests for
parameter expansion, multi-term coverage, saturated-score tie-breaking, and
distinct-file selection. A score change may also change which declaration and
content hash supply the package's citation; verify that the source remains
coherent, not just that the expected filename appears.

Use the Python tests, Ruff checks, and deterministic MCP fixture evaluator from
[COMMANDS.md](../../COMMANDS.md#python-agent-access). .NET checks are unnecessary
for a purely Python ranking implementation unless a shared contract changes.
When a task requires live retrieval evidence, use a clean exact candidate and
the existing frozen suite under its controlling procedure. Do not modify frozen
targets or thresholds to make a change appear beneficial. Add a separately
identified diagnostic suite if the measured question is new.

If the problem is latency, use the existing package timing sideband to identify
the stage before changing concurrency. Search sources already run concurrently;
candidate and item hydration include sequential work. A passing deterministic
ranking test cannot establish a speedup or normal-agent benefit. Keep performance,
retrieval quality, and paired-agent evidence separate in documentation.

Update [Retrieval internals](../current/retrieval-internals.md) and
[Agent Access Contracts](../current/agent-access-contracts.md) when selection or
diagnostics visibly change. Historical reports stay bound to their original
candidates.

## Extend an existing interface field

Suppose an authorized change adds a diagnostic field to a context response.
Start by identifying whether it belongs in the shared structured package or is
specific to one presentation. For example, the existing MCP-only
`codemesh_next_action` status field is presentation guidance, while snapshot
identity belongs in the common response. Avoid copying a presentation-only
field into every storage record.

Trace this alignment chain:

1. Define the producer and missing/unknown behavior in
   [store.py](../../agent-access/codemesh_agent_access/store.py) or the relevant
   adapter. A dictionary field still needs a documented meaning and type.
2. Update the corresponding Pydantic model in
   [models.py](../../agent-access/codemesh_agent_access/models.py) if the field
   is part of a typed request or response.
3. Review [rest.py](../../agent-access/codemesh_agent_access/rest.py),
   [tools.py](../../agent-access/codemesh_agent_access/tools.py), and both the
   manifest and registered signatures in
   [mcp.py](../../agent-access/codemesh_agent_access/mcp.py). The printable
   manifest and actual tool registration are separate representations that tests
   keep aligned.
4. Review [cli.py](../../agent-access/codemesh_agent_access/cli.py),
   [formatting.py](../../agent-access/codemesh_agent_access/formatting.py), and
   [web.py](../../agent-access/codemesh_agent_access/web.py) for presentation.
   Preserve the text-only MCP agent form and its whole-response character cap.
5. Update
   [AgentAccessContracts.cs](../../src/CodeMesh.Domain/Contracts/AgentAccessContracts.cs)
   and [AgentAccessClient](../../src/CodeMesh.Control/AgentAccess/AgentAccessClient.cs)
   when the .NET surface consumes it. Check explicit JSON names and nullability;
   PascalCase C# names are not the wire schema.

Run both suites for this serialization/interface boundary. Python REST/MCP/CLI
tests assert forwarding and output; `TestAgentAccessContractsMapRestJson` and
`TestAgentAccessClientCallsRestEndpoints` in the
[.NET harness](../../tests/CodeMesh.Tests/Program.cs) protect the other end.
Use the smoke path if the change affects REST integration or live wiring under
the [risk rules](../evaluation/testing.md). Update the canonical
[Agent Access Contracts](../current/agent-access-contracts.md) with the exact
field and failure behavior, then update handbook explanations that depend on it.

## Modify storage or lifecycle behavior

Begin at [StorageContracts.cs](../../src/CodeMesh.Storage/StorageContracts.cs),
then read the .NET adapter, in-memory implementation, Python reader, and any
administrative delete path. An interface such as `IIncrementalContentStore`
promises namespace-aware state/removal; implementing a global delete instead
would break retention even if a one-repository fixture passed.

For publication work, explicitly identify what is inside the project-document
compare-and-swap and what happens before or after it. Exercise conflict and
partial-failure paths in addition to the success path. For retention work,
protect referenced snapshots and shared content, and verify retry behavior
after one store fails. Keep
[ADR 0001](../decisions/0001-local-repository-identity-and-snapshot-publication.md)
and [Identity and persistence](../current/identity-and-persistence.md) aligned
with the implemented boundary. Both language suites and the end-to-end smoke
path are selected for these changes; a lock-protected in-memory pass is not
equivalent to a real-store race test.

## Complete the change

Review the final diff and preserve unrelated edits. Report passed, failed,
skipped, and unavailable checks separately, including integration skips and
unexecuted live/model work. Apply the repository standards checks, use a focused
Conventional Commit, and validate its range as indexed in
[COMMANDS.md](../../COMMANDS.md#repository-standards). A commit does not authorize
publication, a model campaign, or a store mutation outside the selected work.

Update normative behavior in its canonical reference, verified status in
[Project Status](../current/project-status.md), and future execution order only
in [Next Steps](../planning/next-steps.md) when that order has actually changed.
Use the [methodology](../engineering/methodology.md) to distinguish implemented
behavior from inspected evidence and later acceptance states.
