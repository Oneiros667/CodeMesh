# Publication Readiness Review

Date: 2026-08-11

Document type: historical evidence

Status at review time: **READY FOR OWNER REVIEW; NOT YET READY FOR VISIBILITY
CHANGE**

This file preserves the fail-closed pre-publication review. The reviewed work
was later committed as `cfb7ad2`, followed by the Node.js 24 workflow update
`31bdfee`; this checkout's `origin/main` contains both commits. Later commits
and the current worktree are outside this review. Do not use the status or gates
below as current readiness evidence.

This was a local, fail-closed review of the identified checkout. It did not change
GitHub visibility, metadata, history, branches, tags, releases, or remote state.

## Checkout reviewed

- Working directory: the currently opened CodeMesh checkout.
- Branch: `main`.
- Rewritten local HEAD: `a57566935cfe33a1b847aa3edd082b234874ce39`.
- Upstream: `origin/main`.
- The private remote-tracking ref still points to the pre-rewrite history. The
  expected local comparison is therefore 95 commits ahead and 84 behind until
  an explicitly authorized, lease-protected replacement of remote `main`.
- Existing user work preserved: modified `AGENTS.md` and
  `docs/next-steps.md`; untracked `.github/`, `.markdownlint-cli2.jsonc`,
  `docs/decisions/`, `docs/engineering/`, and `tools/` additions.

The publication changes remain uncommitted and make the worktree newer than the
commit-bound retrieval evidence.

## Resolved publication decisions

### Repository licence

The owner selected the MIT License. `LICENSE` grants reuse under those terms and
the README links to it.

### Ownership and identity

The owner approved `pieter.devilliers@gmail.com` as the public Git identity.
Every author and committer email in the rewritten 96-commit `main` history is
that address, and every author name is `Pieter de Villiers`.

The local public branch history was rewritten to replace only two identifying
home-directory prefixes with neutral examples. The affected historical paths
were `.codebase-memory/config.json`, `.env.example`, `README.md`, and
`docker-compose.yml`. Commit messages, names, dates, order, and the linear
topology are unchanged. A scan of every rewritten `main` commit found no
remaining occurrence of either identifying prefix.

The pre-rewrite repository, remote-tracking ref, and publication worktree are
recoverable from a private bundle stored outside this repository. Seven
environment-owned `refs/codex/` checkpoint refs remain local and were not
rewritten or deleted. They are not part of a normal explicit `main` push; never
publish this repository with `git push --mirror` or `git push --all`.

On 2026-08-11, the owner explicitly confirmed authority to publish the tracked
source, documentation, fixtures, and evaluation assets, including separation
from employer, customer, contractor, and confidential material. The current
tree scan found no named customer/employer material or bundled external sample
source. `references/` is ignored; the versioned external evaluation suites
contain selectors and metadata rather than a vendored repository.

## Security and privacy audit

The local audit used:

- Gitleaks v8.30.1, downloaded from its official GitHub release into a
  temporary directory and verified against the published SHA-256 checksum;
- high-confidence key, token, private-key, and credential-URI patterns over the
  Git-visible tree and every rewritten `main` commit;
- email, URL-host, absolute-path, credential-filename, binary-extension, and
  large-blob inventories;
- ignored runtime-directory inspection; and
- the repository's new deterministic `tools/check_publication_safety.py` check.

Results:

- Gitleaks reported zero findings across every commit reachable from rewritten
  `main` and zero findings in a temporary snapshot containing exactly the
  tracked and non-ignored untracked publication files.
- No high-confidence secret signature was found in the current tree or the
  rewritten public-branch history.
- Current email-like content is limited to the owner-approved public Git
  identity, test placeholders, and syntax that resembles an email address.
- URL hosts are public dependencies, loopback/service names, or test-only
  domains; no private hostname was found.
- No tracked key, certificate, credential, database, log, archive, screenshot,
  office document, or generated runtime artifact was found.
- The largest reachable blob observed was under 200 KB. The Git object pack was
  under 1 MB at audit time.
- `.codemesh-evals/` (about 34 MB locally), `.codemesh-live-summary/`, `.tmp/`,
  Python environments/caches, and .NET outputs are ignored and untracked.
- `.env.example` now leaves credentials and optional sample/model settings
  unset. Compose requires an explicit local Neo4j password and binds published
  host ports to loopback.

The independent scanner result covered the reviewed uncommitted snapshot and
rewritten local branch. It is not a GitHub secret-scanning result or evidence
for a later commit. Repeat it against the exact remote publication commit and
every ref that will become visible.

## Third-party and redistribution audit

The final local Python lock resolved 49 packages. Installed metadata showed
MIT/BSD/Apache/ISC/MPL/PSF/Python-family licences; the two packages without an
SPDX metadata field carried local licence files. Direct NuGet dependencies and
the locally resolved transitive graph reported MIT, Apache-2.0, BSD-3-Clause,
or an older Microsoft licence URL. No bundled package source or binary was
found. Generated NuGet lock files now bind the resolved dependency graph; the
existing `uv.lock` binds Python resolution.

The first OSV-backed `uv audit --locked` found 30 advisory records across five
packages. The lock and the direct MCP constraint were updated to fixed,
compatible releases: `cryptography` 50.0.0, `mcp` 1.29.0 with a `<2` major
version guard, `pydantic-settings` 2.15.0, `python-multipart` 0.0.32, and
`starlette` 1.6.0. The final audit reported no known vulnerabilities or adverse
project statuses. The NuGet transitive vulnerability query also reported no
known vulnerable packages from the configured source. Advisory results are
time-dependent and must be refreshed against the publication commit.

Container services are referenced by image tag and are not bundled in this
repository. Their upstream terms still matter to distribution and hosted-use
decisions:

- [Neo4j Community Edition](https://github.com/neo4j/neo4j) identifies as GPLv3.
- [MongoDB Community Server](https://www.mongodb.com/legal/licensing/community-edition)
  7 is under the SSPL, which MongoDB notes is not OSI-approved.
- [Qdrant](https://github.com/qdrant/qdrant) identifies as Apache-2.0.
- [Ollama](https://github.com/ollama/ollama/blob/main/LICENSE) identifies as
  MIT.

The Compose service tags and Dockerfile base tags are mutable, including
`qdrant/qdrant:latest` and `ollama/ollama:latest`. Before release or reproducible
deployment claims, choose reviewed versions/digests and record required
notices. An application that connects to a service is not automatically
governed by that service's licence, but redistribution, modification, or
offering the database itself as a service can add obligations; obtain legal
review for the intended distribution model.

The pinned YoutubeDownloader evaluation repository is MIT-licensed in its own
checkout and is not vendored. The ignored `references/graphify` checkout carries
Apache-2.0 and retained MIT notices and is not part of the Git-visible CodeMesh
tree. Product and project names are used textually; no third-party logo or
generated visual asset is tracked.

`THIRD_PARTY_NOTICES.md` now records the referenced runtime services, build
images, dependency manifests, model boundary, and upstream licence sources. For
the current publication scope, CodeMesh publishes source and configuration
references but does not redistribute those container images, model weights, or
external repositories. Exact artifact and service obligations must be reviewed
again before distributing built artifacts or offering database functionality as
a service.

## Public surface and evidence

The local diff:

- adds the owner-selected MIT licence and links it from the README;
- replaces the operator-oriented README with a concise product/status page,
  Mermaid architecture, repository-contained quick start, demonstration scope,
  and evidence boundaries;
- removes current personal and fixed-machine sample paths;
- adds focused security and contribution guidance;
- adds a sanitized, source-free summary of the reviewed summary-free live
  reports at
  [`docs/evaluation/evidence/summary-free-baseline-e84b189.json`](../evaluation/evidence/summary-free-baseline-e84b189.json);
- adds a current-tree publication-safety check; and
- expands the existing uncommitted standards workflow into deterministic .NET,
  Python, evaluation, documentation, and repository-control verification.

The sanitized manifest is reviewable from a clean clone, but it is a
transcription rather than a signed or hosted attestation. Its live-suite results
are bound to the pre-rewrite `e84b189`, whose rewritten public-history
equivalent is `a575669`. The rewrite changed historical path examples, so the
manifest remains prior-run evidence rather than validation of this uncommitted
diff. The assisted agent result is intentionally not promoted as generalized
product proof because it used treatment-only onboarding and did not preserve
prompt parity.

## Verification

Successful final checks on 2026-08-11:

| Surface | Result |
| --- | --- |
| `dotnet restore CodeMesh.sln --locked-mode` | Passed for all 10 projects. |
| `dotnet build CodeMesh.sln --no-restore` | Passed with 0 warnings and 0 errors. |
| `dotnet run --project tests/CodeMesh.Tests --no-restore` | 53 passed; 1 optional external sample skipped because it was not configured. |
| `dotnet format CodeMesh.sln --verify-no-changes --no-restore` | Passed. |
| `uv sync --locked` | Passed with 49 resolved packages. |
| `uv run --no-sync pytest` | 92 passed; emitted two dependency deprecation/forward-reference warnings. |
| Ruff lint and format checks for Agent Access and `tools/` | Passed. |
| Provider-`none` deterministic MCP fixture evaluation | 5 cases passed, including the secret-canary check. |
| `dotnet run --project src/CodeMesh.Cli --no-restore -- self ingest --skip-embeddings` | Passed with 6,094 nodes, 10,492 relationships, 3,492 content items, 0 embeddings, 0 summaries, and 27 content redactions. The dirty worktree makes this a smoke result, not comparable product evidence. |
| Summary-free synthetic end-to-end smoke | Passed ingestion, registry, lexical search, symbol search, context package, deletion, and cleanup with provider `none`. |
| Locked C# parser and Agent Access Docker builds | Passed; Docker warned that Buildx was unavailable and used the classic builder. |
| Compose configuration with explicit authentication | Passed. |
| Markdown lint | 26 Markdown files, 0 issues. |
| Local Markdown links | 38 Markdown files validated. |
| Publication-safety check | 170 Git-visible files passed. |
| Gitleaks v8.30.1 rewritten-`main` scan | Passed with 0 findings after official checksum verification. |
| Gitleaks v8.30.1 Git-visible worktree snapshot | Passed with 0 findings. |
| JSON manifest, GitHub workflow YAML parse, and checksum-verified actionlint v1.7.12 | Passed; workflow permissions were `contents: read`. |
| `git diff --check` and rewritten-upstream-equivalent Conventional Commit range check | Passed. |
| NuGet transitive vulnerability query | No known vulnerable packages reported. |
| Final `uv audit --locked` | No known vulnerabilities or adverse project statuses reported. |

Corrected intermediate results:

- The first Python rerun exposed one stale expected alias after replacing a
  machine-specific fixture path. The expectation was corrected and all 92 tests
  passed.
- Ruff found formatting drift in the new safety checker and the adjusted test;
  both files were formatted and the final lint/format checks passed.
- The first simulation of the publication force-push range included rewritten
  legacy commits and correctly rejected 69 older non-Conventional subjects. The
  workflow now detects the documented forced-push event and validates its head
  commit; normal pushes and pull requests still validate their complete ranges.
- The first end-to-end attempt used a temporary Neo4j password that did not
  match the existing persistent volume. It failed authentication without
  provider calls; the rerun used the existing private local credential and
  passed with both model and summary providers forced to `none`.

Hosted GitHub Actions has not run the exact workflow in this diff. A committed
workflow is configuration only.

## Recommended GitHub metadata

- Description: `Local-first C#/.NET context and change-impact service for coding agents, with source-backed MCP evidence.`
- Homepage: leave blank until a maintained documentation or project site
  exists.
- Topics: `csharp`, `dotnet`, `roslyn`, `mcp`, `coding-agents`,
  `code-intelligence`, `change-impact`, `neo4j`, `fastapi`, `local-first`.
- Pinned-repository summary: `CodeMesh helps coding agents find C# implementation, trace likely impact, and choose validation through compact, source-backed local context.`

These are recommendations only; no repository setting has been changed.

## Gates Recorded At Review Time

1. Review and commit only the intended diff. Replace only remote `main` with an
   explicit force-with-lease operation; do not push all refs or mirror the local
   repository.
2. Require the exact committed GitHub Actions workflow to pass; record its URL
   and commit SHA without treating it as live-store or product-benefit proof.
3. Re-run Gitleaks and the publication audit against the exact remote commit and
   every ref that will become visible.
4. Pin reviewed container versions or digests before making reproducible
   deployment or release claims; this is not required for the current
   source-only portfolio publication.

At review time, the local preparation was ready for owner review and the first
three gates remained required. This statement is retained historically and is
not an instruction or status claim for current HEAD.
