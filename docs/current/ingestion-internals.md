# Ingestion internals

Document type: current implementation reference

Ingestion transforms selected source into one index generation. Its main
collaborators are `IParserClient`, graph/content/vector store contracts,
optional summary contracts, and an optional snapshot-aware registry.
[Architecture](architecture.md) locates the projects;
[Identity and persistence](identity-and-persistence.md) owns the identity and
publication details. This chapter explains the work between those boundaries.

## Request construction and repository selection

[CLI `RunIngestAsync`](../../src/CodeMesh.Cli/Program.cs) resolves `--root` or
`--repository-root`, canonicalizes languages, resolves explicit solution/project
paths, validates the path filter, then constructs adapters and an
[`IngestionRequest`](../../src/CodeMesh.Domain/Contracts/IngestionContracts.cs).
`CodeMeshIngestPathResolver.ResolveFile` tries an existing repository-relative
path first and then an existing caller-relative path. Prefer absolute
manifest paths when the calling directory differs from the target checkout.
Missing explicit files fail before parsing.

`CreateParserClient` selects local C#, Python, Rust, Markdown, or deployment
clients. `--parser-url` or `CODEMESH_CSHARP_PARSER_URL` selects
[`HttpParserClient`](../../src/CodeMesh.Ingestion/HttpParserClient.cs), whose
`ParseAsync` posts the same domain request to `/parse`, checks HTTP success,
and deserializes `ParseResult`. The CLI gives that HTTP client a ten-minute
timeout. It rejects HTTP parser configuration with multiple languages because
the implemented composite uses local clients for one combined generation.

The request defaults to C#. Embeddings and summaries require explicit inclusion
flags; selecting an endpoint or model alone does not enable their write paths.
The [enrichment chapter](enrichment-and-evaluation.md) explains force/skip
behavior. Tests for selection and argument normalization are
`TestIngestPathResolverAcceptsRelativeFiles`,
`TestIngestPathResolverRejectsMissingFiles`, and the refresh/watch workflow
tests in [Program.cs](../../tests/CodeMesh.Tests/Program.cs).

## Shared path filtering

[`RepositoryPathPolicy`](../../src/CodeMesh.Domain/Utilities/RepositoryPathPolicy.cs)
is applied before supported parser enumeration. It excludes generated/cache
directories and linked path components, then applies known-secret-file and
configured allow/deny rules. Allow patterns restrict eligible repository-relative
paths; deny patterns win. Pattern normalization and the policy version become
part of the snapshot scope, so changing the filter can change identity even
when the surviving source looks similar.

The C# parser applies containment to solution/project manifests as well as source
documents. Its `ManifestPathFilter` allows manifest discovery without requiring
every manifest to match a source allow pattern, while preserving the other
policy protections. It rejects an explicitly selected manifest outside the
policy rather than handing it to MSBuild. The full supported glob and secret
policy remains in [Security and Redaction](security-and-redaction.md).

Test the shared rule and the actual caller. For example,
`TestRepositoryPathPolicyRejectsLinkedPaths` covers the reusable policy, while
`TestCSharpParserAppliesRepositoryPathFilters` verifies parser integration.
`TestWatchWorkflowDetectsFileChanges` covers the watcher using that policy.
All are in the [.NET harness](../../tests/CodeMesh.Tests/Program.cs).

## Orchestrator call order

[`IngestionOrchestrator.IngestAsync`](../../src/CodeMesh.Ingestion/IngestionOrchestrator.cs)
performs these phases in order:

1. Canonicalize language and validate the effective path filter. Capture local
   Git provenance. For persistent snapshot-aware operation, resolve project and
   checkout markers and register the checkout.
2. Construct `ParseRequest` and await the selected parser. Any diagnostic whose
   severity is `error`, case-insensitively, aborts before generation staging and
   publication. Warnings remain in the result.
3. Redact content, remap node content hashes, deduplicate content, and compute
   deterministic snapshot identity. Stamp storage namespace and provenance onto
   nodes and relationships afterward.
4. Read existing state in that namespace from incremental stores. Compare node
   content/fingerprints, relationship fingerprints, and content hashes to select
   writes and calculate skipped counts.
5. Capture slot expectations, build `SnapshotPublication`, and stage its
   generation. Write graph first, then content, optional embeddings, and
   optional summaries.
6. Remove obsolete records within the selected namespace using retained id/hash
   sets. Publish the slots after these operations succeed.
7. Construct a completed `IngestionResult`, write compatibility repository and
   successful run records, then register any legacy namespace for later cleanup.

This order is visible in the
[ingestion walkthrough](../guides/developer-walkthroughs.md#walkthrough-1-ingest-and-publish-a-small-repository).
It is important that relationships reach storage after their endpoint nodes,
redaction precedes provider calls, and slots move after the data writes.

## Incremental behavior and failure boundaries

Incremental here means avoiding unnecessary **writes** after parsing, not
incrementally parsing only changed syntax trees. `IsUnchangedNode` compares
content hash and `CodeMeshFingerprint.ForNode`; relationships use their own
fingerprints. Runtime timestamps and run/checkout metadata are excluded from
those fingerprints. An unchanged record may therefore retain an earlier
per-record ingestion-run stamp; use registry observations and slots to determine
current checkout selection.

The normal snapshot-aware path compares records in the newly calculated
snapshot namespace. A changed source view usually creates a new namespace, so
its first ingest writes that snapshot's graph. Reingesting identical source can
skip those writes. Globally content-addressed Mongo text is shared through
references, but graph identity is still snapshot-scoped. The alternate path
without `ISnapshotRegistryStore` uses a mutable repository namespace and is
useful in tests; its refresh cleanup is not historical snapshot retention.

`IIncremental*` stores delete records outside the current sets. Older
`IRefreshable*` interfaces delete stale run stamps instead. Summary cleanup also
runs when summary generation is disabled, retaining only summaries matching
current candidate node/content identities. Skipping embeddings does not run the
embedding-generation/cleanup block. See `TestIncrementalIngestionSkipsUnchangedRecords`,
`TestRepositoryRefreshRemovesStaleRecords`, and
`TestIncrementalIngestionSkipsUnchangedSummaries` in the
[.NET harness](../../tests/CodeMesh.Tests/Program.cs).

Dry-run still parses, redacts, and calculates source identity; it does not
resolve persistent identity markers, stage generations, write stores, or call
model providers through the orchestrator. The CLI constructs configured adapter
objects even for dry-run. Dry-run counts and ids are not proof of a published
snapshot. `TestDryRunSkipsStores` asserts the store boundary.

There is no whole-ingestion retry loop. A parser exception escapes before
staging. Once staged writes begin, a failure triggers best-effort generation
failure recording and rethrows. Cleanup of the failed namespace is separate.
Provider summary failures have a different boundary: individual non-cancellation
generation errors become failed summary records and counters, allowing the
source snapshot to complete. Embedding failures normally escape and fail the
generation. See [optional capability failures](enrichment-and-evaluation.md#disabled-and-failed-capabilities).

Cancellation is passed through parser, storage, and provider interfaces. Parsers
check it at file/declaration boundaries; generation failure recording deliberately
uses a non-cancelled token. CLI calls do not install a linked Ctrl+C cancellation
pipeline for all this work. Watch's delay also has no cancellation token, so do
not promise graceful transactional cleanup on process termination.

## Parser-specific mechanisms

### C#: semantic symbols plus source declarations

[`CSharpParseService.ParseAsync`](../../src/CodeMesh.Parser.CSharp/CSharpParseService.cs)
first loads project contexts. `LoadProjectContextsAsync` tries an explicit
project, an explicit solution, a discovered top-level solution, and a unique
discovered project. If none loads, it emits `CMSHARP010` and falls back to
filesystem C# parsing with a constructed compilation. `TryLoadProjectAsync`
and `TryLoadSolutionAsync` record load/workspace diagnostics; a fallback warning
must not be mistaken for full MSBuild semantics.

MSBuild loading respects project compile items and referenced compilations.
`CreateProjectParseContextsAsync` obtains syntax and compilation contexts;
`CreateWorkspace` registers MSBuild once under a lock. This makes restoring the
target's dependencies relevant to relationship fidelity. The fallback can index
source when project loading is unavailable, but cannot recreate all the target's
build configuration, references, or conditional compilation choices.

Parsing then makes three passes across the project contexts: emit files, emit
declarations and register symbol lookup keys, and extract relationships. Waiting
until all declarations are registered is what permits a call in one loaded
project to resolve to a local symbol in another. `ExtractDeclarationNodes`
emits one logical node per symbol and a separate source declaration per syntax
location; `ExtractRelationships` emits containment and declaration-to-symbol
`Defines` links before semantic edges.

`AddBodyReferenceRelationships` uses Roslyn symbol information for invocation and
constructor expressions and field/property/event access. Assignment context
distinguishes writes from reads, with compound access needing both. Type,
return, parameter, inheritance, implementation, and override relationships are
added when their target resolves to an indexed symbol. External or unresolved
targets are not evidence that no dependency exists. Calls through runtime
reflection or dynamic dispatch are not a complete runtime graph.

Test attributes such as `Fact`, `Theory`, and `TestMethod` identify test cases;
the parser also recognizes CodeMesh's `Test...` methods in test files. This
classification affects retrieval ranking and summary candidate selection.
Representative tests in [Program.cs](../../tests/CodeMesh.Tests/Program.cs) are:

- `TestCSharpParserHonorsProjectCompileItems` for project-aware source selection.
- `TestCSharpParserEmitsInvocationAndMemberAccessRelationships` for call/read/write
  edges, and `TestCSharpParserEmitsCrossProjectInvocationRelationships` for pass
  ordering across projects.
- `TestCSharpParserSeparatesPartialDeclarations` for logical/source separation.
- `TestCSharpParserEmitsTestFilesAndCases` for test recognition.

### Python: indentation, definitions, imports, and bounded calls

[`PythonParseService`](../../src/CodeMesh.Parser.Python/PythonParseService.cs)
is implemented in C#, without executing Python or using Python's AST runtime.
`ParseFile` emits whole-file content, gathers imports, then walks definition
headers while maintaining an indentation stack. `MatchDefinition` can combine
multiline headers using delimiter/header termination logic. `ExtractBlock`
selects a definition's content; classes become `Class`, functions become
`Method`, and test functions become `TestCase`. Async state, decorators, module,
qualified name, and parent are metadata.

`ParseImports` retains module, imported-name, and alias metadata on declaration
nodes, including repeated guarded imports. `AddSemanticRelationships` then
matches calls against uniquely named definitions or imported aliases within the
file. A call through an imported alias can point to its import declaration
rather than a resolved foreign implementation. Despite the helper's name, this
is structural matching, not a Python type checker, complete cross-module
resolver, or dynamic-import analysis. Ambiguous names are left unresolved.

Read `TestPythonParserEmitsClassesFunctionsAndContainment` and
`TestPythonParserEmitsImportsCallsAndTestCases` in the
[.NET harness](../../tests/CodeMesh.Tests/Program.cs). `TestPythonParserParsesAgentAccessProject`
uses this repository as an additional parser-shape check, not proof that every
Python construct is supported.

### Rust: declaration scopes and PyO3 metadata

[`RustParseService.CollectDeclarations`](../../src/CodeMesh.Parser.Rust/RustParseService.cs)
recognizes `mod`, `struct`, `enum`, `trait`, `impl`, `fn`, and `use` shapes using
regular expressions and accumulated attributes. `FindDeclarationEnd` and brace
tracking delimit blocks; enclosing declarations determine containment. `NodeKind`
maps Rust constructs onto the shared graph vocabulary, with Rust-specific
details retained as metadata rather than adding an enum for every syntax form.

`AddSemanticRelationships` resolves unambiguous names within the collected file:
impl-to-trait `Implements`, impl/use references, calls to uniquely named
functions, and signature type uses. PyO3 attributes record exported names and
module/class/function roles for the composite parser. This does not run rustc,
expand macros, evaluate every `cfg` branch, or resolve a Cargo dependency graph.
`CMRS002` indicates a nonempty file with no recognized declarations.

`TestRustParserEmitsDeclarationsRelationshipsTestsAndPyO3Exports` in the
[.NET harness](../../tests/CodeMesh.Tests/Program.cs) provides a representative
embedded Rust fixture, including tests and native export metadata.

### Markdown: heading structure

[`MarkdownParseService.ParseFile`](../../src/CodeMesh.Parser.Markdown/MarkdownParseService.cs)
creates a `Document` with whole-file content and `Section` nodes for recognized
hash-prefixed headings. It maintains a heading-level stack for containment, but
a section's own text ends at the next heading of any level. Descendant sections
remain separate graph nodes rather than being concatenated into the parent's
snippet. Metadata stores heading level, anchor, and document kind.

`FindHeadings` is a line regex, not a complete Markdown parser. It does not track
fenced code blocks, and anchor generation does not add duplicate-heading
suffixes. Repeated titles can therefore collide in section identity. Links to
code, commands, or other documents are not modeled. These inspection findings
are recorded in the [debugging guide](../guides/development-and-debugging.md#inspection-findings).
`TestMarkdownParserEmitsDocumentsSectionsAndContainment` covers the supported
document/heading path.

### Deployment: Dockerfile and Compose structure

[`DeploymentParseService`](../../src/CodeMesh.Parser.Deployment/DeploymentParseService.cs)
selects recognized Dockerfile and Compose filenames. `ParseDockerfile` creates
a file plus stage nodes from `FROM` boundaries, preserving base image, alias,
and selected runtime instruction metadata. `ParseComposeFile` finds service
blocks, emits one service node per name, and extracts build/image, ports,
environment keys, volumes, and dependencies. `depends_on` becomes a
`References` relationship labelled `depends_on` between services in that file.

The implementation is based on lines, indentation, and regular expressions,
not full Compose evaluation. It does not merge override files, resolve all YAML
features or substitutions, or prove a running deployment. It does not parse
Helm, Kubernetes, or CI/CD workflows merely because those files use YAML.
`TestDeploymentParserEmitsDockerfileAndComposeNodes` and
`TestDeploymentParserParsesRepositoryRuntimeArtifacts` in the
[.NET harness](../../tests/CodeMesh.Tests/Program.cs) show the expected shapes.

The structural parsers catch file IO/access failures as warning diagnostics and
continue with other files. A completed run can therefore have partial file
coverage. Inspect diagnostics as well as counts.

## Multi-language composition

[`CompositeParserClient.ParseLanguages`](../../src/CodeMesh.Ingestion/CompositeParserClient.cs)
normalizes aliases, removes duplicates, and ordinal-sorts languages.
`ParseAsync` checks that the request selects exactly the configured language set,
then awaits all selected clients with `Task.WhenAll`. It combines nodes,
diagnostics, and content; content hashes are deduplicated. Duplicate node ids
fail; duplicate relationships can coalesce only when endpoint, kind, and label
agree. Any combined error diagnostic causes the orchestrator to abort before
publication. One language cannot publish independently inside this call.

`AddPyO3Relationships` uses Rust `pythonExportName` metadata and Python static
import/call metadata. It adds references and invocations only when an export
name has exactly one candidate. The edges carry `boundary=pyo3` and source/target
languages. Name matching is a bounded cross-language lead, not proof of Python
module loading or a verified native ABI.

`TestCompositeParserLinksPythonCallsToRustPyO3Exports` covers the boundary;
`TestMultiLanguageIngestionPublishesOneDeterministicSnapshot` covers canonical
language order and failure without publication. Both are in
[Program.cs](../../tests/CodeMesh.Tests/Program.cs). Use one combined ingest for
the desired language set: separate ingests select separate snapshots rather
than appending another language to checkout-current.

## Refresh and watch

[`CodeMeshRefreshWorkflow`](../../src/CodeMesh.Control/Configuration/CodeMeshRefreshWorkflow.cs)
finds a repository root, resolves the selected solution, and builds `ingest`
arguments. It preserves explicit language/filter/provider options; it does not
load a prior run's settings from MongoDB. Repeat the intended `--languages` and
path filters when starting a new refresh/watch command.

[`CodeMeshWatchWorkflow`](../../src/CodeMesh.Control/Configuration/CodeMeshWatchWorkflow.cs)
enumerates eligible files and maps relative paths to `length:last-write-ticks`.
`HasChanges` compares the file count, paths, and those values. The CLI ingests
once immediately, then polls (default two seconds, minimum one) before each
subsequent full ingest. It processes one ingestion at a time. `--run-once` and
`--max-runs` bound the loop.

This is polling, not a filesystem event subscription or content-hash watcher.
Preserving a file's length and timestamp can evade detection, and Git-only
metadata changes need an explicit refresh because `.git` is excluded. A thrown
ingestion exception leaves the watch command through its outer error handler;
there is no automatic retry/backoff loop. See the
[changed-source walkthrough](../guides/developer-walkthroughs.md#walkthrough-3-refresh-changed-source-and-handle-stale-access)
for the implications for snapshot selection and bound access.
