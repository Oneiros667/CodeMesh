# CodeMesh Project Status

Document type: current status snapshot

Reviewed: 2026-09-01

Implementation status is reviewed against the current inspected worktree.
Current configured/onboarded evidence is bound to one-step entry candidate
`8844c21`; retained earlier paid campaigns remain bound separately to
candidates `0bde606` and `0378740`.

Retained evidence below remains bound to the exact commits named in each
evidence section; it does not inherit this implementation baseline.

This document records current implementation and retained evidence. It does not
set execution order; use
[`docs/planning/next-steps.md`](../planning/next-steps.md) for that. Passing
tests or evaluation harnesses do not by themselves establish generalized agent
benefit, release readiness, deployment acceptance, or production fitness.

## Product Position

CodeMesh is a local-first context and likely change-impact service for coding
agents. The initial product wedge is C#/.NET implementation discovery, impact
navigation, and validation selection through compact source-backed context.

The current milestone is configured/onboarded evidence that a normal agent host
uses the selected CodeMesh v1 repository integration, then performs at least as
safely and correctly as normal repository exploration with attributable
efficiency or correctness benefit. Spontaneous MCP discovery remains useful
usability evidence, but is no longer the v1 acceptance contract.

## Capability Status

| Area | Current status | Important boundary |
| --- | --- | --- |
| C# parsing | Implemented with Roslyn semantic relationships, declarations, test files, and test cases. | Strongest parser and current product wedge. |
| Python parsing | Files, classes, functions, async and multiline functions, imports, local/imported calls, test cases, and containment implemented. | This is a lightweight structural parser rather than a complete Python semantic model; dynamic imports and type resolution remain limited. |
| Rust parsing | Files, modules, structs, enums, traits, impl blocks, functions, methods, `use` declarations, test cases, call/type relationships, and PyO3 exports implemented in `CodeMesh.Parser.Rust`. | The parser is heuristic and source-structural rather than rustc-semantic; broader macro and conditional-compilation resolution remains open. |
| Markdown parsing | Documents, sections, anchors, source spans, and containment implemented. | Cross-links to code, commands, endpoints, and projects are not modeled. |
| Deployment parsing | Initial Dockerfile and Compose nodes, metadata, containment, and service dependencies implemented. | Helm, Kubernetes, CI/CD, overrides, and code-to-runtime links remain planned. |
| Ingestion | Dry-run, incremental writes, staged deterministic snapshots, atomic multi-language parser composition, compare-and-swap slot publication, reference-aware cleanup, refresh, watch, redaction, optional embeddings, and optional summaries implemented. | One selected language set publishes one snapshot or fails before slot activation; watch remains polling-based. |
| Storage | Snapshot-namespaced Neo4j graph, MongoDB content/registry/runs/summaries, Qdrant vectors, and in-memory test adapters implemented. Neo4j graph publication uses bounded write batches. | Publication is atomic at the registry slot boundary rather than one cross-store transaction; normal service-backed operation requires configured stores. |
| Agent Access | REST, stdio MCP, Python CLI, typed .NET client, repository status, context search/packages, symbols, nodes, neighbors, and deletion implemented. The normal four-tool MCP profile supports exact project/checkout/root/source-view binding, fail-closed freshness, hashed review-before-apply installation, a provider-free live probe, and versioned feedback record/validate/summarize commands. | Repository deletion remains outside both MCP profiles. Returned relationships and rankings are navigation evidence, not runtime proof. Unbound diagnostic and REST surfaces retain their documented administrative behavior. |
| Context packaging | Agent-format packages, 12,000-character MCP cap, source spans, rationale, relationships, and .NET, Python, and Rust validation recommendations implemented. | Source verification remains required for consequential conclusions. |
| Local UI | Read-only health, repository, run, freshness, and search views implemented. | It is a local inspection surface, not established product-benefit evidence. |
| Evaluation | Deterministic fixture, live MCP, spontaneous, evaluator-assisted, configured/onboarded paired-agent, and model benchmark harnesses implemented. Configured mode has a provider-free preflight that verifies the exact reviewed normal-profile plan, committed guidance, baseline MCP identities, fresh binding, positive runtime probe, and fail-closed rejection probe before either paired condition runs. | The authorized `8844c21` campaign achieved context-package adoption in all three treatments and passed all six executions safely. Its verdict was `neutral`, with no attributable wins or regressions. Cross-repository model-backed replication requires separate authorization. |
| Generated summaries | Complexity-aware prompts, local/online providers, and a provider-neutral qualification runner/report compiler are implemented. The runner uses the production prompt/parser, requires calibration and held-out qualification partitions, redacts inputs, records immutable suite/profile/source identity, creates typed blinded review packets, and binds isolated live-retrieval plus resource/cost evidence before applying quality, safety, retrieval, and deployment gates. | No summary deployment profile is CodeMesh-qualified. Provider-backed execution, a complete reviewed corpus, two blinded reviews, isolated indexes, query-level retrieval assessment, deployment measurements, and model/source/spend authority remain separate requirements. |
| Security | Pre-persistence value redaction, immutable generated/cache exclusions, default known-secret-file exclusion, repository-relative allow/deny globs, fail-fast pattern validation, and path-policy-bound snapshot identity implemented. | Explicitly including known secret files requires a separate CLI flag and does not weaken redaction or repository authorization requirements. |
| Repository identity | Stable project/checkout markers, deterministic source snapshots, checkout-current and clean branch-head slots, explicit retained slots, legacy migration, and richer local freshness implemented. | Separate clones attach with explicit `--project-id`; shared-service tenant/authorization/privacy controls remain deferred. |

Detailed current interfaces are in
[Agent Access Contracts](agent-access-contracts.md), and component boundaries
are in [Architecture](architecture.md).

## Activated one|nine Pilot

The bounded pilot is active only for the clean Primary checkout at
`fe2f761583bf78601961ff17934185c4b6a632f9`. It is bound to project
`prj_a570a726917d4d0ca596085aaf07af50`, checkout
`chk_70c50c5494de4837ab0627aca021eab2`, and source view
`fea1951d1eeb93ac265112aef7000dcac1a9832b000ea81b360b0851df56e69b`.
Provider-free ingestion run
`98b439c4b0d484297852dae7723be555e75bf8fcf7c565c96a9b0bad43b66062`
published snapshot
`snp_bf026d3f2e2b5a40f3c9fa112ae36b7e026b0f5a0f0483a23796b0a6adc9243e`
with 45,650 nodes, 95,218 relationships, 12,873 content items, zero
embeddings, and zero summaries. It redacted 324 content items before
persistence.

The reviewed plan at hash
`fcadac37ae4df261e8b746e14f9191e22a7b6399b991925d4d1e12a5947daf34`
changed only Primary's ignored `.codex/config.toml`. The normal-profile probe
accepted the exact fresh binding and the configured preflight preserved prompt
parity. Its installed ignored `AGENTS.override.md` guidance was retained by
source classification and hash, not raw content. The positive gate returned
both `app/feed_hub/native_replay.py` and
`native/feed_hub_replay/src/lib.rs`; the wrong-checkout gate failed closed with
the live binding, freshness, and provenance issue codes.

An execution-readiness recheck on 2026-09-01 found the detached CodeMesh
candidate still clean at `0bde606` and confirmed that the reviewed plan,
installed configuration, installed guidance, and retained preflight still
matched their recorded hashes. Primary had advanced to `011f562` on `main`; its
branch tip was preserved while the checkout was temporarily restored to exact
`fe2f761`. The exact configured preflight passed again without repinning or
re-indexing, and Primary was returned to clean `main` at `011f562` after the
campaign.

Clean detached CodeMesh candidate `0bde606` passed all eight frozen one|nine
provider-free gates, comprising four positive retrieval gates and four
rejection gates, and validated all three retained feedback packets. The same
candidate passed the pinned six-case, 18-call YoutubeDownloader summary-free
live gate with 1.0 tool success and recall, 0.9 MRR, 0.926186 nDCG, and zero
secret leaks. Its final local verification comprised 124 Python tests, Ruff
check and format, and all five deterministic MCP fixtures. After the missing
ASP.NET Core targeting pack and runtime were installed, attended deterministic
.NET verification at documentation commit `9c8aca3` also passed: locked
restore, build, 64 tests, and format verification completed with zero failures.
The build retained one `CS8625` nullable warning, and the YoutubeDownloader
sample test remained skipped because `CODEMESH_SAMPLE_CSHARP_ROOT` was not
configured. No solution, project, or C# source differed from evaluated
candidate `0bde606` at that verification commit.

The attended correction path remains evidence: `4eccd80` missed the Rust
expected path, `a6ebaa5` expected the wrong live rejection diagnostic, and
`854d678` failed the YoutubeDownloader MRR threshold at 0.766667. No model was
invoked in those attempts or the final pass. The sanitized exact-candidate
record is [configured one|nine provider-free evidence](../evaluation/evidence/configured-onenine-provider-free-0bde606.json).

The status-to-context correction is now frozen in clean detached candidate
`0378740`. At that exact commit, locked restore, build, 69 .NET tests, format
verification, 125 Python tests, Ruff check and format, all five deterministic
MCP fixtures, and all repository standards checks passed; one nullable build
warning and the unconfigured YoutubeDownloader sample skip remain. Against the
same exact Primary source identity, the new normal-profile configured preflight,
all eight frozen one|nine gates, all three feedback packets, and the pinned
YoutubeDownloader live gate passed with provider mode `none`. Primary's newer
`main` tip `0297190` was preserved and restored after the gates. The sanitized
record is [corrected candidate provider-free evidence](../evaluation/evidence/configured-onenine-provider-free-0378740.json).

The subsequent one-step entry correction is frozen in clean detached candidate
`8844c21`. MCP instructions, tool descriptions, and generated onboarding now
make the fail-closed context package the first normal-host action while keeping
repository status as an explicit diagnostic and retaining its compatibility
next-action field. At that exact commit, locked restore, build, 69 .NET tests,
format verification, 125 Python tests, Ruff check and format, all five
deterministic MCP fixtures, and all repository standards checks passed. The
final service-backed .NET rerun passed after an earlier Neo4j cold-start
cancellation; the existing nullable warning and unconfigured YoutubeDownloader
sample skip remain.

one|nine instance configuration commit `f9f199d` repinned only Primary to the
new candidate and regenerated all managed instance instructions successfully;
it did not activate another checkout. Against exact Primary source identity
`fe2f761`, the reviewed configured preflight, all eight frozen one|nine gates,
all three feedback packets, and the pinned YoutubeDownloader live gate passed
with provider mode `none`. Primary's newer `main` tip `162fa515` was preserved
and restored after the gates. The sanitized record is
[one-step candidate provider-free evidence](../evaluation/evidence/configured-onenine-provider-free-8844c21.json).

The authorized `gpt-5.6-sol` medium-reasoning configured campaign then completed
three paired repetitions. All six executions were correct and safe, with no
failed MCP calls or command-policy violations. Two of three treatments called
`codemesh_get_repository_status`, but no treatment called
`codemesh_get_context_package`; the third treatment made no CodeMesh call.
The verdict was therefore `insufficient`, with zero treatment wins and zero
CodeMesh-attributable wins. On the two status-adopting pairs, treatment medians
were 2.22% slower and used 6.14% more tokens; overall medians were 30.29% slower
and used 46.61% more tokens. Those differences are diagnostic because no
context retrieval occurred. The sanitized record is
[configured one|nine agent evidence](../evaluation/evidence/configured-onenine-agent-0bde606.json).

The separately authorized rerun through exact corrected candidate `0378740`
also completed all three pairs correctly and safely, with no failed MCP calls,
command-policy violations, or treatment regressions. One treatment called
`codemesh_get_repository_status`; no treatment called
`codemesh_get_context_package`. The verdict remained `insufficient`, with zero
treatment wins and zero CodeMesh-attributable wins. Overall treatment medians
were 6.07% slower and used 4.17% more tokens. The single status-adopting pair
was 44.22% slower and used 21.54% more tokens, but those differences remain
diagnostic because task context was never retrieved. The sanitized record is
[corrected configured campaign evidence](../evaluation/evidence/configured-onenine-agent-0378740.json).

The separately authorized `gpt-5.6-sol` medium-reasoning campaign at exact
candidate `8844c21` completed all three configured pairs. All six executions
were correct and safe, with no failed MCP calls or command-policy violations.
Every treatment called `codemesh_get_context_package` directly, so the one-step
entry correction produced full measured adoption. The verdict was `neutral`:
there were no treatment wins, attributable wins, or matched regressions.
Median treatment duration was 1.39% lower and median tokens were 4.13% higher,
both inside the 10% neutrality band. One treatment used 110 shell commands
while the other two used 19; that outlier remains diagnostic. Primary was
restored to clean `main` at `162fa515` after the consumed campaign. The
sanitized record is
[one-step configured campaign evidence](../evaluation/evidence/configured-onenine-agent-8844c21.json).

Together, the provider-free and model-backed records prove the bounded
configuration, runtime identity, safety, and status adoption observed across
the campaigns. They do not establish context-package adoption, correctness or
efficiency benefit, repeatability, release readiness, deployment acceptance,
provider authorization, or production fitness. Secondary, Tertiary, Release,
and Hotfix are not activated; Run-only remains excluded.

## Retained Product Evidence

### Summary-free retrieval

- The pinned YoutubeDownloader live suite passed all six cases with complete
  expected target and relationship coverage.
- Two corrected three-repeat baseline agent campaigns completed all nine pairs
  with equal 100% task success but zero CodeMesh adoption.
- A separate complex output-container task reached 100% live recall after a
  focused ranking correction, while its spontaneous agent campaign still made
  zero CodeMesh calls.
- Overall timing or token differences from non-adopted treatments are retained
  as diagnostics and are not attributed to CodeMesh.

The sanitized live-gate manifest is
[`docs/evaluation/evidence/summary-free-baseline-e84b189.json`](../evaluation/evidence/summary-free-baseline-e84b189.json).

### Assisted utility

- The first valid onboarding-assisted complex campaign achieved full adoption
  and task success but regressed median elapsed time and tokens.
- After the MCP agent brief was capped at 12,000 characters and onboarding was
  focused on default packages plus targeted verification reads, the same
  three-pair task retained full adoption and correctness. Median elapsed time
  fell 34.7%, median tokens fell 64.5%, and treatments used 2 to 4 shell
  commands versus 14 to 18 for controls.
- The independent Config.Net summary-free live gate passed at clean CodeMesh
  commit `d764270`: all 18 calls succeeded, recall and MRR were 1.0, nDCG was
  0.93483, and no secret leaks were detected.
- The Config.Net assisted campaign produced two CodeMesh-attributable
  correctness wins, full treatment success and adoption, no safety violations,
  and 11.8% lower median elapsed time. Treatment median tokens were 3.0% higher.

These results replicate utility after explicit onboarding. They do not prove
prompt-parity discoverability, spontaneous adoption, or broad generalization.
The Config.Net transcription is
[`docs/evaluation/evidence/config-net-assisted-replication-d764270.json`](../evaluation/evidence/config-net-assisted-replication-d764270.json).

### Prompt-parity discoverability

- The Config.Net summary-free live gate remained comparable and passed at clean
  CodeMesh commit `647d83d`: all 18 calls succeeded, recall and MRR were 1.0,
  nDCG was 0.93483, and no secret leaks were detected.
- The frozen three-pair prompt-parity campaign completed with identical control
  and treatment task prompts, but no treatment run called or attempted a
  CodeMesh MCP tool.
- Control passed two of three runs and treatment passed one of three, with no
  safety violations. The harness verdict was `regressed`, but the zero adoption
  rate means overall timing and token differences are diagnostic and cannot be
  attributed to CodeMesh.

This is negative normal-host discoverability evidence, not a failure of the
assisted CodeMesh workflow or a broad product verdict. The sanitized
transcription is
[`docs/evaluation/evidence/config-net-prompt-parity-647d83d.json`](../evaluation/evidence/config-net-prompt-parity-647d83d.json).

## Current Gap

Explicit repository onboarding is implemented for the bounded one|nine pilot:
the normal profile exposes only context package, repository status, repository
listing, and node lookup; exact binding and freshness are enforced; and
installation plus probing are reviewable. Clean one-step candidate `8844c21`,
exact Primary commit `fe2f761`, the configured preflight, the eight-gate frozen
one|nine pilot, and the YoutubeDownloader live gate all pass provider-free. The
configured normal-host campaigns at historical candidate `0bde606` and
corrected candidate `0378740` were both valid but insufficient. Across them,
three treatments called repository status and none retrieved task context. The
subsequent `8844c21` campaign was valid and neutral: all three treatments
retrieved a context package, all six executions passed safely, and there were
no attributable wins or regressions.

The prompt-parity Config.Net campaign recorded zero MCP calls and zero MCP call
attempts. Preserve it as negative spontaneous-discovery evidence; do not change
the frozen task prompt, grading, or targets to manufacture adoption. The
first two configured one|nine campaigns evaluated the status-first onboarding
path and showed that the status-result action did not produce context adoption.
The third campaign preserved the same task and comparison conditions and showed
that direct context-package entry did produce adoption in every treatment.

The evaluated MCP configuration completed without a harness failure, and the
CodeMesh manifest published the intended instructions and tool contracts. The
measured transition failure was narrower: a fresh accepted status response did
not itself state the next tool action. The current implementation adds an MCP-only
`codemesh_next_action` status field that directs a fresh accepted binding to
continue immediately to an agent-format context package and directs every
other state to fall back. This correction is committed, covered by
deterministic contract tests, and verified through the full provider-free
exact-candidate gates at `0378740`. Its paid campaign still observed one
status-only treatment and no context-package call, so the action field did not
produce the required normal-host handoff.

The current implementation removes that two-step dependency. MCP server
instructions, context-package and status tool descriptions, and generated
repository onboarding now use the fail-closed context package as the single
normal-host entry action. Repository status remains available for explicit
ingestion, count, and freshness diagnostics, and its compatibility next-action
field remains intact. Exact clean candidate `8844c21` passed the full
deterministic suite, configured preflight, eight one|nine pilot gates, feedback
validation, and pinned YoutubeDownloader live gate with no model provider. The
authorized paired campaign then observed context-package adoption in every
treatment and a neutral outcome. This proves the measured handoff for the
selected task; it does not prove attributable product benefit or
cross-repository repeatability.

The configured/onboarded evaluator now preserves prompt parity, uses the exact
reviewed checkout-local `normal` installation, and retains integration mode,
guidance, baseline MCP, tool-profile, binding, installation-plan, and runtime-
probe identities. It rejects a dirty or stale target, a dirty CodeMesh source
checkout, commit or binding mismatch, changed plan files, unexpected tool
surface, and a failed rejection probe. Historical spontaneous and assisted
modes retain their prior diagnostic behavior.

The immediate next work is provider-free preparation of a configured/onboarded
Config.Net replication: select an exact clean source identity, create and review
its normal-profile binding and repository guidance, then pass the configured
preflight and pinned live retrieval gate. Preserve all three one|nine campaigns
as consumed artifacts. A Config.Net paired model campaign requires separate
explicit model-spend authorization after those provider-free gates pass.

Expand onboarding to another one|nine checkout only with separate authority,
exact binding, fresh ingestion, and a passing checkout-specific probe. The
earlier `de239b7` stale state and `9f3216c` stale-candidate rejection remain
useful historical diagnostics; they are not the current candidate state.

## Public Repository And Hosted Evidence

At this review, the public GitHub `main` branch remains at `8e9c0da`, while the
local configured-evaluator candidate and its documentation remain unpublished.
The latest hosted baseline-verification success applies to remote `8e9c0da`;
there is no exact-HEAD hosted workflow evidence for the unpublished local
commits.

The latest hosted CodeQL workflow completed successfully for remote `8e9c0da`,
which proves that the scan ran, not that the repository is security-clean.
GitHub still reports 39 open CodeQL alerts: 3 critical command-line-injection
alerts and 36 high alerts, comprising 35 path-injection findings and one
reflected-XSS finding. Dependabot and secret scanning report zero open alerts.
These hosted findings apply to the published remote state and do not establish
the security state of the unpublished local commits.

The separate read-only triage identifies suite-derived artifact paths as the
first hardening target, keeps explicit local command and path selection within
its documented trust boundary pending hardening, and requires an adversarial UI
test before considering the XSS finding dismissible. No alert was dismissed.
See the [CodeQL triage record](../evaluation/evidence/codeql-triage-8e9c0da.json).

## Current Boundaries

- Generated summaries remain disabled in the core product-proof baseline.
- No summary model is qualified.
- Python, Rust, Markdown, and deployment parsers do not match Roslyn's semantic depth.
- The activated one|nine pilot is pinned to one Primary snapshot and must not be
  silently expanded or repointed when either checkout advances.
- Shared multi-user stores, portable snapshot artifacts, outcome memory,
  Kubernetes/Helm ingestion, and broader SDLC intelligence are not implemented.
- Current source redaction and path filtering do not replace repository
  authorization or review of an explicitly broadened ingestion scope.
- Hosted workflow success for remote `8e9c0da` is not evidence for unpublished
  local commits, and an automated scan completing successfully does not resolve
  or justify its open findings.

## Status Maintenance

Update this page when implemented capability, reviewed evidence, or the
immediate product gap changes. Keep detailed procedures in their canonical
guides and keep future execution order in `docs/planning/next-steps.md`.
