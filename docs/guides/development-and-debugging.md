# Development and debugging

Document type: human developer operating guide

Use the [handbook](developer-handbook.md) for the reading path and
[COMMANDS.md](../../COMMANDS.md) for canonical invocations. This guide explains
what to inspect and why. Examples use PowerShell from the CodeMesh root unless
explicitly stated. They are supported command examples checked against source;
they are not a record that local services or application suites were run during
the handbook review.

## Prepare a development checkout

CodeMesh's projects target .NET 10, and Agent Access declares Python 3.12 or
newer in [pyproject.toml](../../agent-access/pyproject.toml). The repository's
usual IDE/shell combination is Rider on Windows with PowerShell; the baseline
workflow also defines Linux verification. Install the SDK, Python, `uv`, Git,
and Node/npm for Markdown linting. Docker Compose is needed for live-store work,
not for the in-process Python fixture evaluator. Exact dependency versions come
from the committed NuGet lock files and `agent-access/uv.lock`.

Establish identity before editing:

```powershell
git rev-parse --show-toplevel
git status --short --branch
git rev-parse HEAD
```

Read [CONTRIBUTING.md](../../CONTRIBUTING.md), the local `AGENTS.md`, and the
[risk-based test guide](../evaluation/testing.md). Run .NET commands one at a
time so concurrent builds do not contend for the same intermediate files:

```powershell
dotnet restore CodeMesh.sln --locked-mode
dotnet build CodeMesh.sln --no-restore
```

Then initialize Python from `agent-access`:

```powershell
Set-Location agent-access
uv sync --locked
```

`uv sync --locked` includes the development dependency group containing pytest
and Ruff. The .NET tests are a console application invoked with `dotnet run`,
not a discovered xUnit/NUnit suite invoked with `dotnet test`. Use the commands
in [COMMANDS.md](../../COMMANDS.md#deterministic-verification) without substituting
a command that exercises no tests.

The shell-neutral `git`, `dotnet`, `uv`, `python`, and `npx` argument forms also
appear in the checked-in [Linux workflow](../../.github/workflows/baseline-standards.yml).
PowerShell backtick continuations, `$env:` assignments, `Invoke-RestMethod`, and
the smoke script are PowerShell-specific. A workflow definition is evidence of
the intended alternate environment, not proof of an exact-candidate Linux or
Windows run. Use the selected shell explicitly in any validation report.

## Choose the smallest runtime

For documentation or pure Python formatting/ranking work, start with repository
standards and the affected deterministic tests. For parser logic, use the .NET
harness and its synthetic temporary projects. The full .NET harness can probe
configured local stores and execute disposable round-trips if reachable; read
the integration setup before treating it as entirely offline.

For a running product, follow [MCP Setup](mcp-setup.md#start-services) in order:
configure local environment, start stores, ingest the target, then run the
chosen read surface. The CLI's local C# parser does not require the C# HTTP
worker. Normal MCP is a local stdio process with direct store connections;
it does not require a separate REST process. REST is needed for the UI, .NET
client, and REST-based smoke operations.

[docker-compose.yml](../../docker-compose.yml) binds published ports to loopback.
The C# parser container sees `/workspace`; its path must be meaningful inside
that process. Agent Access's container has no equivalent arbitrary host-checkout
mount, so Git freshness may be unavailable for host paths. Prefer the documented
local stdio setup when exact host checkout access is required.

## Configuration that actually controls execution

| Launch | Configuration source | Practical consequence |
| --- | --- | --- |
| .NET CLI | CLI option, then environment, then factory default; `.env` loader fills absent variables from the initial root. | An existing process variable wins over `.env`; changing the file may appear ineffective. |
| Python REST/MCP/CLI | `Settings.from_env` and binding arguments/environment. | No implicit `.env` loading; the parent process must supply the intended environment. |
| Compose | Compose interpolation and service-specific environment mappings. | Container hostnames/ports differ from host-side endpoints. |
| `codemesh.yaml` | Workspace discovery marker and inventory. | Its example keys do not configure runtime factories. |

Implementation sources are
[EnvironmentFileLoader](../../src/CodeMesh.Control/Configuration/EnvironmentFileLoader.cs),
[CLI factories](../../src/CodeMesh.Cli/Program.cs), and
[Settings.from_env](../../agent-access/codemesh_agent_access/config.py).
`dependencies.get_settings/get_store` cache configuration in a Python process;
restart the affected process when intentionally changing its configuration.
Restarting the REST container does not restart an already-running local MCP
server in an IDE host.

Use placeholders such as `C:\path\to\checkout`, `prj_EXACT`, and
`<random-local-password>` in documentation. Inspect variable **names** and the
configured endpoint/collection identity without dumping `.env`, credentials,
or a whole process environment. Keep the actual values in local configuration.

The initial .NET environment load recognizes `--root`, before command-specific
normalization. `--repository-root` is accepted later by ingestion but does not
change that initial load. An explicit `--root` is the clearest launch when
target and current directories differ.

## Useful debugging entry points

In Rider, open `CodeMesh.sln`. For CLI behavior, set a run configuration for
`CodeMesh.Cli`, working directory at the repository root, and the intended
arguments. Start at `RunIngestAsync`; step into `IngestionOrchestrator.IngestAsync`
to separate parsing from persistence. Use a disposable fixture and the supported
dry-run path before debugging writes. For C# shape problems, break in
`LoadProjectContextsAsync`, `ExtractDeclarationNodes`, or `ExtractRelationships`.

For the Python facade, use a Python debugger in the `agent-access` environment.
Break at `get_context_package`, `get_repository_status`, `_search_lexical_context`,
`_build_context_hit`, or `_hydrate_context_package_item` in
[store.py](../../agent-access/codemesh_agent_access/store.py). A ranking test's
stub store is a useful starting point because it isolates scoring/assembly from
live adapter state. For surface mapping, start in `rest.py` or the registered
function inside `mcp.build_server` before entering the facade.

Do not write diagnostic stdout into an MCP stdio server: stdout carries the
protocol. Use debugger state or the existing sanitized timing sideband for
package attribution. Ordinary CLI output includes diagnostics and write/skip
statistics; `--json` uses the serialized ingestion result. The stdout/stderr
paths are visible in [Program.cs](../../src/CodeMesh.Cli/Program.cs) and
[mcp.py](../../agent-access/codemesh_agent_access/mcp.py).

## Health, logs, and evidence capture

From the CodeMesh root in PowerShell, the
[local health commands](../../COMMANDS.md#local-product-health) inspect a
configured environment:

```powershell
dotnet run --project src/CodeMesh.Cli -- doctor
dotnet run --project src/CodeMesh.Cli -- status
docker compose ps
Invoke-RestMethod http://127.0.0.1:8088/health
```

`CodeMeshStatusService` reports workspace/component configuration and endpoint
health. `doctor` adds advice and has different exit behavior from `status`;
inspect the structured component states rather than inferring readiness from
an exit code alone. Python health checks graph, content, summaries, vectors,
and query provider, reporting degraded if a component is not healthy/configured.
Neither health call proves freshness or retrieval quality.

For container errors, use the bounded diagnostic command indexed in
[COMMANDS.md](../../COMMANDS.md#local-product-health):

```powershell
docker compose logs --tail 100 agent-access csharp-parser
```

Review diagnostic text before sharing it: exceptions can contain local paths,
provider response details, or configuration context. Preserve the command,
process/candidate, selected project/checkout/snapshot, first failure, and
sanitized diagnostic codes. Run history is useful but incomplete as an error
log, because early parser failures occur before a persisted failed run exists.

## Diagnose by symptom

| Symptom | Likely causes and first inspection | Supported recovery |
| --- | --- | --- |
| Normal MCP refuses startup | Missing/incomplete binding or unknown profile. Inspect `binding_from_values`, `mcp.run`, and the reviewed launch. | Use the exact installation/binding procedure in [MCP Setup](mcp-setup.md#repository-agent-onboarding). |
| `snapshot_not_fresh` | Commit mismatch, dirty current/indexed view, or unverifiable source provenance. Inspect bound repository status and local Git state. | Finish/record the intended source change, refresh the exact clean checkout and scope, then rerun the reviewed probe. |
| `repository_root_mismatch` or `checkout_mismatch` | Moved checkout, copied marker, wrong host process, or wrong installation target. Inspect registered checkout and launch root. | Correct/review the binding for the intended checkout; do not switch to an unbound profile as a product acceptance substitute. |
| `source_view_hash_mismatch` | Plan pins the previous source view after refresh. | Review a new plan for the new identity and probe it; refresh does not edit installation. |
| Repository missing or ambiguous | No successful publication, wrong Mongo database/collection, colliding alias, or ambiguous slot key. | Check exact project/checkout selectors and configured stores; use the intended explicit identity. |
| Freshness unknown in REST container | Host root/Git inaccessible inside that container. | Inspect through the documented local process with checkout access; preserve the container's unknown result. |
| `CMSHARP010` and missing semantic edges | MSBuild project/solution could not load; filesystem fallback used. | Restore the target using its own supported procedure, verify selected manifest, and inspect workspace diagnostics before reingestion. |
| A file never appears | Wrong language, Compile items, generated/secret/deny filters, linked path, or structural parser limitation. | Compare parser selection and policy to the actual file; use parser dry-run and a focused fixture. |
| Search returns no hits | Wrong namespace or exact filters, metadata query miss, bounded candidate pool, adapter degradation. | Inspect health, resolved query/diagnostics, then a known symbol/path through diagnostic tools. |
| Hit has a zero or unexpected span | Logical C# symbol needs its declaration; declaration missing or selected content differs. | Inspect `Defines`, hit expansion, and the declaration/content hash. |
| Snippet or relationship missing | Output/group limits, omitted content, absent record, or parser resolution limit. | Inspect structured package controls and source span; increase only the relevant diagnostic limit when useful. |
| Completed ingest but failed summaries | Per-node provider errors are persisted without failing source ingestion. | Inspect summary coverage and provider metadata; any provider rerun follows its own authorization and qualification procedure. |
| Refresh fails but old results remain | New generation failed before slot publication. | Preserve the failure, repair the relevant dependency, then intentionally refresh; do not erase the previous index to hide the failure. |
| Watch misses a change or exits | Timestamp/size detector, Git-only change, or an uncaught ingest exception. | Explicit refresh with the same scope; inspect the original exception before restarting watch. |
| Vector count/width error | Write/query model mismatch or incompatible existing collection. | Compare exact model, dimensions, and collection; use the documented embedding verification, preserving unrelated collections. |

The relevant source is linked in
[Ingestion internals](../current/ingestion-internals.md),
[Retrieval internals](../current/retrieval-internals.md), and
[Identity and persistence](../current/identity-and-persistence.md). The table
describes diagnostic paths, not permission to mutate any arbitrary configured
store or to repeat a consumed evaluation campaign.

## Inspection findings

The following are concrete source-review findings recorded for future focused
work. No application fix, live reproduction, or new regression test was made
as part of this documentation task. Existing linked tests cover neighboring
behavior; they are not claimed as tests of each uncovered edge case.

| Finding | Source and consequence | Focused verification needed |
| --- | --- | --- |
| Fragment line slicing can use the wrong coordinate space | [`_snippet_for_hit`](../../agent-access/codemesh_agent_access/store.py) slices whenever the hit's file-absolute line numbers fit within the loaded text's line count. A declaration fragment starting after line 1 can be long enough to satisfy that test, causing it to be sliced as if it were a whole file. | A fragment fixture with non-1 source start and enough lines to enter the slice branch; assert exact emitted source. |
| Markdown headings in fences and repeated titles are not distinguished | [`FindHeadings`/`AnchorFor`](../../src/CodeMesh.Parser.Markdown/MarkdownParseService.cs) use line regexes and unsuffixed anchors. Fenced headings can become sections and repeated anchors can produce duplicate ids. | Fenced-code and repeated-heading parser fixtures, including composite duplicate handling. |
| Refresh path discovery differs from ingest | [`CodeMeshRefreshWorkflow`](../../src/CodeMesh.Control/Configuration/CodeMeshRefreshWorkflow.cs) checks `.git` as a directory, while linked worktrees commonly use a `.git` file; explicit solution paths use caller-relative `Path.GetFullPath`. Ingest uses a different resolver. | Nested-start linked-worktree fixture without another root marker, and a manifest relative only to the selected root. Use explicit root/absolute manifest meanwhile. |
| Publication metadata and cleanup are outside the slot CAS | [`PublishSnapshotAsync`](../../src/CodeMesh.Storage/Mongo/MongoRegistryStore.cs) updates metadata before replacing project slots; [`CollectAsync`](../../src/CodeMesh.Ingestion/SnapshotGarbageCollector.cs) deletes data before its final registry reference check. | Fault injection around revision conflicts and a pin concurrent with collection. The local contract does not supply a shared-store coordinator. |
| Source capture is not a filesystem transaction | [`IngestAsync`](../../src/CodeMesh.Ingestion/IngestionOrchestrator.cs) captures Git before parsing; [`_repository_freshness`](../../agent-access/codemesh_agent_access/store.py) checks Git/recorded provenance without recomputing parser output. | Source edits during parse/read and ignored-but-eligible source changes. Keep source stable during evidence ingestion. |

Treat these as maintenance leads and stated limits, not an activated backlog.
[Next Steps](../planning/next-steps.md) retains execution-order authority.
Documented design rationale is in
[ADR 0001](../decisions/0001-local-repository-identity-and-snapshot-publication.md),
[ADR 0002](../decisions/0002-summary-qualification-evidence-boundary.md), and
[ADR 0003](../decisions/0003-hard-capped-codex-evaluation-runner.md). The observations
above are source analysis; they do not invent a historical reason for a defect.
