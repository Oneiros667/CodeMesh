# Release Preparation

Document type: candidate release policy and reviewable operating procedure

Status: prepared locally; no release candidate, tag, publication, deployment,
or supported released-version line is declared. Owner acceptance of this
procedure and the completed exact-candidate evidence packet is still required.

The [local review packet](../evaluation/review-packet-a158bc0.md) contains draft
notes, verified artifact and dependency identities, and a gate-by-gate ledger
for source `a158bc0`. It leaves unavailable acceptance and owner decisions open.

## Version Identity

[`VERSION`](../../VERSION) contains the canonical numeric source version,
currently `0.1.0`. This preserves the existing Python package version; it does
not retroactively create a release. [`Directory.Build.props`](../../Directory.Build.props)
sets the .NET assembly/package version from that file. The .NET informational
version can include a Git commit suffix. Python package metadata, its checked-in
export, and the lockfile must agree with `VERSION`; the repository check enforces
that agreement. REST OpenAPI reads the Python export.

Use the [version commands](../../COMMANDS.md#application-version) without
opening stores. Record full Git SHA, clean status, build environment, dependency
locks, and artifact checksums alongside the version. A matching version alone
does not establish identical source, dependencies, or accepted behavior.

Version changes update `VERSION`, Python metadata/export, and the regenerated
Python lockfile together. Run the version checker, both application suites, and
package verification. Schema versions for bindings, feedback, snapshots, and
evaluation reports remain independent and need explicit migration review.
`ParserCapability.Version` independently identifies extractor behavior.

## Candidate Public Contract

The initial candidate contract consists of the documented .NET CLI commands,
Python CLI commands, REST request/response models, typed .NET Agent Access
client, normal and diagnostic MCP profiles, installation plans, binding and
feedback formats, and persisted local identity/retention behavior. The exact
shapes and authorization differences are in
[Agent Access Contracts](../current/agent-access-contracts.md),
[Identity and Persistence](../current/identity-and-persistence.md), and
[`COMMANDS.md`](../../COMMANDS.md).

Python implementation modules, graph query plans, ranking weights, HTML layout,
raw traces, private evaluation archives, and undocumented store fields are
internal. Generated summaries and model qualification remain opt-in and
unqualified. No shared-service, cross-tenant, hosted, or production support is
implied. Source citations and freshness checks remain required; rankings and
relationships are navigation evidence.

During `0.x`, an intentional incompatible public change requires a minor version
increment, explicit migration or re-ingestion instructions, and release notes.
Compatible fixes may use patch increments. Before `1.0`, freeze and review the
public contract and establish a supported upgrade path. Published artifacts
are immutable; a correction receives a new version.

## Environment And Support Evidence

There are currently no supported published versions. The source targets .NET
10 and Python 3.12 or newer. The retained [Linux Python verification](../evaluation/evidence/python-runtime-verification-b73e19a.json)
passes all 235 tests and five fixture cases on 3.12.14, 3.13.15, and 3.14.7.
This source-checkout matrix does not establish every future runtime version.
The repository's Windows/PowerShell workflow and Linux Docker profile are
separate acceptance targets. A successful Linux check does not establish
Windows acceptance. Release notes must state exactly which OS/runtime profiles
were exercised and exclude unverified profiles from support claims.

A candidate packet must include SDK/runtime and dependency-lock identities,
store image digests, enabled providers, loopback bindings, and resource needs.
Mutable image tags and loose source dependency constraints do not substitute
for those retained build identities. A source build needs the documented .NET,
Python/uv, PowerShell, Git, and optional Docker toolchain.

## Candidate Verification Gates

1. Select an immutable clean candidate and compare it with the previous released
   version, or explicitly record that no previous release exists. Preserve
   consumed evaluation failures and existing user state.
2. Run all deterministic and standards checks in [`COMMANDS.md`](../../COMMANDS.md),
   including synchronized versions and Conventional Commits. Record passed,
   failed, skipped, and unavailable checks separately.
3. Run the full end-to-end smoke on disposable stores. Exercise clean install,
   CLI version, REST health/OpenAPI, normal MCP binding/freshness, and cleanup.
   Build and inspect local Python and .NET distributable artifacts. Retain their
   checksums and verify the installed package, rather than only editable source.
4. Run current dependency advisories and obtain an exact-candidate CodeQL scan.
   Resolve or explicitly review remaining findings; successful scan execution
   does not establish security cleanliness. The older remote `8e9c0da` scan is
   insufficient for the current candidate.
5. Review persisted-state and configuration differences. If an old format is
   unsupported, require a documented backup and re-ingestion path; do not infer
   backward compatibility from matching schema labels.
6. Retain configured/onboarded outcome evidence appropriate to the release's
   claims. Current mixed and consumed campaigns do not prove repeatable agent
   benefit. Any fresh campaign needs separate model, source, and spend authority.
7. Complete the [release notes](release-notes-template.md), exact artifact and
   environment manifest, known limitations, and owner review. Unavailable gates
   remain open and cannot be converted to acceptance by documentation.

## Upgrade And Recovery Rehearsal

The [local recovery guide](../guides/backup-and-recovery.md) records the
successfully rehearsed stopped-volume procedure and its precise same-version
Linux boundary. It supplies local recovery evidence; upgrade and supported
environment acceptance remain separate.

The separate [development upgrade rehearsal](../evaluation/evidence/local-development-upgrade-ce23f2e.json)
exercises `8e9c0da` to `ce23f2e` and exact whole-set rollback. Its local mechanism
passes, but the frozen sample dependency advisory prevents treating the packet
as complete supported-upgrade acceptance.

Before updating an existing indexed environment, record its exact source and
store identities and stop writers for the selected instance. Back up the
Neo4j, MongoDB, and Qdrant state as one quiesced set, preserve private local
configuration securely, and prove restoration in isolated storage. Do not
combine one store's old backup with newer graph, content, or vector state.

Restore an isolated copy, install the candidate, apply only documented
migrations or re-ingest the authorized repositories, and validate identity,
freshness, representative citations, counts, and deletion. On failure, stop the
candidate and restore the previous software and the complete consistent store
set. The absence of a previous released version means the first-release
upgrade rehearsal must name the actual development baseline being tested.

Backup and rollback commands depend on the selected store versions and
operating environment. This procedure does not authorize mutations of existing
user stores; the concrete environment-specific commands and restoration result
must be attached to the candidate packet before approval.

## Publication And Deployment

After the complete packet is reviewable, obtain explicit owner authorization
naming the version, source SHA, artifact checksums, publication destination,
and permitted action. Tagging, package publication, GitHub release creation,
deployment, and stable promotion are separate recorded actions. A local commit,
prepared runbook, or hosted standards pass authorizes none of them.
