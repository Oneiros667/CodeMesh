# CodeMesh Source Review: a158bc0

Document type: local review packet and draft release notes

Prepared: 2026-09-05

This packet reviews source version `0.1.0` at immutable source commit
`a158bc0308d9fdb8f373ec0d9d6f03233b984f9f`. It is ready for review of the local
work. Release acceptance is incomplete: no release version, tag, publication,
deployment target, or supported profile has been approved. Current implementation
and execution order remain owned by [Project Status](../current/project-status.md)
and [Next Steps](../planning/next-steps.md).

## Candidate And Artifact Identity

The previous published development commit is
`8e9c0da7b497fe51126e3ef66509a8587cfe8d83`. No GitHub release or remote tag exists
at the 2026-09-05 read-only check. This is the first local distribution review,
not an upgrade from a supported released version.

The [package record](evidence/local-package-verification-a158bc0.json) binds the
artifacts below. Their bytes and SHA-256 values were reverified for this packet.
The [review manifest](evidence/review-manifest-a158bc0.json) records all 11 .NET
lock files, the Python lockfile, the inspected local toolchain, and hashes of
retained application-test logs. Raw archives, installation environments, and
logs remain under ignored `.codemesh-evals/` directories in the main checkout.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `python/codemesh_agent_access-0.1.0-py3-none-any.whl` | 157,731 | `b07d638a88c761fc546bcd4ad46bb28a508a3590251350b5edb6be174c9fce0f` |
| `python/codemesh_agent_access-0.1.0.tar.gz` | 231,686 | `c1341687fe62ce06ddcbcf1b25100d489593663b91d51b7c9e4ca862cf96b072` |
| `codemesh-dotnet-0.1.0-linux-build.tar.gz` | 12,583,162 | `6ce9ff6daf7674cfad4184be4b131b574e12210a43deadf386020fb7ff0dc8b3` |
| `dotnet-file-manifest.json` | 22,251 | `cfdee26f4341750b36e2a701f0bf33f09a7e9f3131dfbebbaf8bcead9b4b81d1` |

The .NET informational version is
`0.1.0+a158bc0308d9fdb8f373ec0d9d6f03233b984f9f`; Python package and REST OpenAPI
versions are `0.1.0`. Matching version strings alone do not identify identical
artifacts.

## Verification Gate Ledger

The numbered gates are owned by [Release Preparation](../engineering/release-preparation.md#candidate-verification-gates).

| Gate | Evidence inspected | Current conclusion and remaining action |
| --- | --- | --- |
| 1. Immutable candidate and prior baseline | Clean package build at `a158bc0`; artifact checksums reverified; published development baseline `8e9c0da`; no released version or tag. | Local source/artifact identity verified. Owner selection of a release remains pending. |
| 2. Deterministic and standards checks | 71 .NET tests with zero skips at `f314043`; 235 Python tests on 3.12.14, 3.13.15, and 3.14.7 at `b73e19a`; relevant source, tests, locks, and build files unchanged through `a158bc0`; current documentation and publication checks. | Local checks verified for those source surfaces. Hosted `verify` still needs the proposed PR. |
| 3. Install, package, smoke, and cleanup | Installed wheel outside source: version/OpenAPI, normal four-tool manifest, 16 bundled suites and patch loading, five fixture cases. .NET publish includes design-time targets. Full smoke, separate concurrent read-only parser probe, and fresh normal-profile installation/retrieval/rejection probes pass at `a158bc0`. | Local Linux mechanism verified. Supported-profile, Windows, and representative resource/capacity acceptance remain open. |
| 4. Security | Current dependency checks: no known vulnerabilities in 11 CodeMesh .NET projects or 48 Python packages. Exact source-bound CodeQL default and local-threat results and 253 individual boundary reviews retained. | Local analysis reviewed; no alert dismissed. Hosted Python still has 39 findings on `8e9c0da`. Obtain current hosted analysis and review findings before release acceptance. |
| 5. Persistence and recovery | Same-version restore at `f314043`; isolated `8e9c0da` to `ce23f2e` reader/re-ingestion/deletion rehearsal and complete original-software/data rollback. | Local mechanism verified. Supported upgrade acceptance remains incomplete; frozen sample dependency restore failed on its advisory. |
| 6. Product outcome evidence | Configured campaigns include improved, neutral, regressed, and incomplete outcomes, retained separately in canonical status. | Repeatable configured-agent benefit is unproven. A fresh campaign needs new source/model/reasoning/repetitions/seed/ceiling authority and passing provider-free prerequisites. |
| 7. Notes, manifest, and owner review | This packet, draft notes below, artifact hashes, dependency identities, and known limitations. | Local review deliverable prepared. Owner review, release/support choices, resource evidence, and publication authorization remain pending. |

The [local CodeQL record](evidence/local-codeql-review-b73e19a.json) preserves
invalid cached first attempts and their uncached replacements. Default-threat
results have zero findings; the broader local-input model retains 61 Python and
192 C# results with reviewed boundaries. A zero default result does not clear
those retained results or establish absence of vulnerabilities.

The [development upgrade record](evidence/local-development-upgrade-ce23f2e.json)
preserves its first failed relationship gate and the failed frozen sample
restore. After dependency assets were emitted, the unchanged six-case/18-call
retrieval gate passed with parser advisory warnings. That later pass does not
make the dependency restore pass. No consumed paid campaign was retried.

The [fresh configured runtime record](evidence/configured-runtime-verification-a158bc0.json)
verifies the installed wheel's plan/apply/probe commands and the shipped
source-backed MCP launch from a clean `a158bc0` checkout. It returns the expected
source path, rejects source-view mismatch, unknown checkout, and dirty source,
then passes again after exact source restoration. Configuration and onboarding
were applied only to an isolated clone and kept ignored. This is provider-free
runtime evidence, not a configured-agent campaign or product-benefit result.

The hosted CodeQL configuration covers Actions, C#, and Python with its default
query suite and remote-plus-local threat model. Local retained analysis covers
C# and Python with pinned security-extended suites; it is not an Actions security
scan or an identical hosted query configuration. The current hosted pass remains
a separate requirement.

## Environment And Resource Boundary

The observed host is Linux x86_64 with .NET SDK `10.0.111`, Python `3.14.7`, and
uv `0.12.9`. The isolated Python compatibility checks additionally exercised
3.12.14 and 3.13.15. The Agent Access Docker build uses pinned uv `0.12.3`.
The package record retains selected Neo4j, MongoDB, Qdrant, and Agent Access
image IDs, plus the separately observed read-only parser image ID. These are
local Docker image identities, not published registry manifest digests.

The exercised baseline disables model providers, embeddings, and generated
summaries. Compose exposes services on loopback: Agent Access 8088, C# parser
8091, Neo4j 7474/7687, MongoDB 27017, and Qdrant 6333/6334. Configuration remains
private; this packet contains no credentials or private configuration values.

Compose configures Neo4j with an initial 512 MiB and maximum 1 GiB heap. That
setting is not a complete host resource requirement. Representative dataset,
concurrency, memory, disk, and latency acceptance criteria have not been
selected and measured for a supported deployment. Linux checks do not establish
Windows acceptance. All task containers are stopped; private artifacts and
recovery volumes remain preserved.

## Draft Release Notes

- Source version reviewed: `0.1.0`; release version not selected.
- Status: local artifacts and notes prepared; not tagged, published, deployed,
  or promoted to stable.
- Release date: not released.
- Tag: not created.
- Reviewed source commit: `a158bc0308d9fdb8f373ec0d9d6f03233b984f9f`.
- Previous stable release: none.

### Release highlights

- Exact checkout binding, reviewable installation, freshness rejection, and a
  one-step source-grounded context package for normal MCP clients.
- Bounded Python/Rust ingestion and a provenance-bound feedback path for the
  activated one|nine Primary pilot; one selected language set publishes
  atomically at the snapshot slot boundary.
- Configured-agent evaluation with explicit hard aggregate-token enforcement,
  retained interrupted reservations, and no automatic provider retries.
- Implemented summary-model qualification tooling; no qualified summary
  deployment profile or default-summary retrieval claim.

### Fixes

- Repository filtering precedes Neo4j lexical candidate scoring. The retained
  controlled synthetic-load result improves local retrieval latency; agent
  benefit remains separately unproven.
- Read-only parser-container design-time outputs use private temporary
  directories, preserving compiler metadata and project relationships.
- Evaluation identifiers and generated paths are validated, dynamic HTML
  attributes are escaped, and feedback recording preserves existing packet
  destinations, including links.

### Breaking changes and compatibility review

The following behavior requires review when moving from older development
source; no released-version compatibility promise exists yet:

- Normal MCP operation requires the documented exact checkout binding. Use a
  reviewed installation plan and fresh probe; diagnostic operation retains its
  separate administrative contract.
- Agent evaluation requires `--max-reported-tokens` and a compatible hard-cap
  runner. The default uncapped Codex runner rejects that preflight.
- Known secret files are excluded by default. Unsafe evaluation identifiers,
  escaping setup patches, linked feedback outboxes, and existing packet
  destinations are rejected.
- Path-policy and parser-output changes can produce new snapshot identities.
  Re-ingest and verify the selected checkout; do not substitute old binding
  or campaign evidence for the new source state.

### Upgrade

No supported upgrade is approved by this packet. The rehearsed local sequence
is detailed in [Backup and Recovery](../guides/backup-and-recovery.md):

1. Identify the exact instance, software, stores, configuration, and indexed
   repositories; stop writers.
2. Preserve the complete consistent four-volume set and private configuration.
3. Restore into new isolated volumes and prove original-software digest equality.
4. Exercise the selected new software and re-ingest authorized repositories;
   verify identity, freshness, citations, retrieval, and scoped deletion.
5. On failure, stop the candidate and restore the complete original software
   and store set. Require original data and retrieval digest equality.

### Migrations

The tested development baseline needed no separate offline schema-migration
command. Re-ingestion published new snapshots while preserving project and
checkout identity. This observation is confined to the retained baseline and
same store image identities; other persisted formats need their own review.
Legacy behavior is documented in [Identity and Persistence](../current/identity-and-persistence.md).

### Required data or configuration

Configured local stores and private authentication remain required. Normal MCP
clients need their exact reviewed binding. The verified core profile uses no
model provider or generated summaries. Artifact and dependency checksums are
listed above; published artifact URLs and a supported deployment destination
remain unselected.

### Verification

Use the exact invocations in [COMMANDS](../../COMMANDS.md), including its
[local package procedure](../../COMMANDS.md#local-package-verification). The
installed checks exercised these commands from outside the source checkout:

```powershell
dotnet <verified-dotnet-directory>/CodeMesh.Cli.dll --version
<installed-environment>/bin/codemesh-agent-access --version
<installed-environment>/bin/codemesh-agent-access mcp-manifest --profile normal
<installed-environment>/bin/codemesh-agent-access eval
```

Expected source version: `0.1.0`, with the exact .NET commit suffix above.
The paths identify the private verified artifacts; these are Linux checks.
For a source checkout, run the canonical full smoke on a separately identified
disposable Compose project. Commands do not authorize changing an existing
user deployment.

### Known limitations

- Repeatable configured-agent product benefit remains unproven.
- Hosted current-source checks, Windows/support acceptance, representative
  resource criteria, and owner release review remain incomplete.
- Frozen YoutubeDownloader source retains the AngleSharp advisory
  `GHSA-pgww-w46g-26qg`; no dependency or warning gate was suppressed.
- Local-input CodeQL results remain reviewed and retained, without dismissal.
- Existing .NET nullable and Python dependency warnings are retained in the
  source verification records.
- C# project loading executes MSBuild design-time logic. Private outputs do not
  sandbox arbitrary project targets; custom-target acceptance remains separate.
- Shared-service isolation, broader deployment/parser coverage, outcome memory,
  portable snapshots, and other deferred roadmap scope remain unactivated.

## Proposed External Review Step

Publish the reviewed `workstream/completion` branch and open a draft pull request
against `main` only after explicit owner authorization. The observed branch
rules require a PR, the `verify` status check, resolved review threads, and
squash merging. This proposal requests no merge, tag, package publication,
deployment, provider invocation, or one|nine instance expansion.
