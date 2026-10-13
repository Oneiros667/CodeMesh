# CodeMesh Project Status

Document type: current status snapshot

Reviewed: 2026-09-08

Implementation status is reviewed against the current inspected worktree.
Current search-scope correction and provider-free retrieval evidence is bound
to candidate `4fb9e81`. Capped-runner and incomplete campaign evidence remains
bound to candidate `0f18071`. Earlier configured/onboarded task-adaptive evidence
remains bound to `fbc1433`; other configured agent evidence remains bound
separately to one-step one|nine candidate `8844c21`, Config.Net candidates
`b16eee7` and `3804028`, and YoutubeDownloader candidate `64d4052`. Earlier paid
campaigns remain bound to candidates `0bde606` and `0378740`.

Retained evidence below remains bound to the exact commits named in each
evidence section; it does not inherit this implementation baseline.

This document records current implementation and retained evidence. It does not
set execution order; use
[`docs/planning/next-steps.md`](../planning/next-steps.md) for that. Passing
tests or evaluation harnesses do not by themselves establish generalized agent
benefit, release readiness, deployment acceptance, or production fitness.

## Implementation Update: 2026-09-10

The owner-activated development-session MCP feedback loop is implemented in the
current local source. An immutable, hash-pinned, expiring, separately revocable
session authorizes exact client and CodeMesh bindings. The
`development-feedback` profile adds bounded local v2 packet recording with
server-derived provenance; the `feedback-maintainer` profile adds allowlisted
list/get intake and deterministic non-authorizing resolution-plan hashes.
Installation-plan v2 pins the session path and hash while retaining v1 normal
plan loading. The existing normal four-tool and diagnostic surfaces remain
separate.

The full 257-test Agent Access suite, including a real-stdio provider-free
integration test, passes locally. The integration records a failed client report, permits
maintainer intake and resolution planning without a CodeMesh edit, records a
passing superseding recheck, derives the original failure as resolved, rejects
calls after revocation, and retains both append-only packets. This proves the
implemented same-machine workflow and safety contracts only. It does not prove
that agents provide useful feedback, that a proposed fix is correct, that a
human approved an edit, or that CodeMesh improves agent outcomes.

## Review Checkpoint: 2026-09-08

The review began on clean local `main` at `b2c053c`, 65 commits ahead of
`origin/main`. Only documentation and retained evidence changed between the
packaged source candidate `a158bc0` and that review baseline; application source,
tests, build files, and dependency locks are unchanged. Historical checks remain
bound to their recorded candidates and were not rerun as current-HEAD tests.

| Reviewed area | Evidence checked in this review | Conclusion |
| --- | --- | --- |
| Recent implementation | Parser design-time output isolation, explicit HTML attribute escaping, exclusive feedback packet creation, and their regression coverage in source/tests | Recent corrections are present; no implementation drift requiring a contract or architecture update was identified. |
| Local distribution and runtime records | SHA-256 recheck of all four package artifacts, eight configured-runtime evidence files, and twelve dependency locks against the retained manifests | All 24 hashes match. Package/runtime execution remains the retained `a158bc0` local evidence, not a new execution or release acceptance. |
| Product progress | Configured campaign records and the review packet's outcome gate | One bounded Config.Net improvement coexists with neutral, regressed, and incomplete campaigns; repeatable configured-agent benefit remains unproven. |
| Public state | Read-only GitHub main, workflow, alert, release, and tag queries on 2026-09-08 | Remote main remains `8e9c0da`; hosted successes cover that older source. There are 39 open CodeQL alerts, zero open Dependabot/secret-scanning alerts, and no releases or tags. |
| Remaining work | Seven-gate [source review packet](../evaluation/review-packet-a158bc0.md) and [execution order](../planning/next-steps.md) | Local preparation is reviewable. Current-source hosted review, supported environment/resource and upgrade acceptance, repeatable product evidence, and owner release/publication decisions remain open. |

This checkpoint refreshes source and evidence inspection only. It does not
activate another model campaign, change a pilot binding, start services, or
supply new application, dependency-advisory, or environment-acceptance results.

Documentation verification passed Markdown lint, version consistency,
publication safety, workflow policy, and whitespace checks. The canonical
Markdown-link check failed on two missing `docs/experimental.md` targets inside
ignored downloaded CodeQL C# and Python query packs under `.codemesh-evals/`;
it reported no project-documentation link failures. Those retained packs were
left unchanged. Application suites and smoke were skipped for this
documentation-only review.

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
| Agent Access | REST, stdio MCP, Python CLI, typed .NET client, repository status, context search/packages, symbols, nodes, neighbors, and deletion implemented. The normal four-tool profile retains exact binding, fail-closed freshness, reviewed installation, provider-free probing, and package guidance. Explicit development-feedback and feedback-maintainer profiles add immutable session authority, server-derived v2 packet recording, allowlisted intake, and non-authorizing resolution hashes. V1 packets and installation plans remain readable. | Repository deletion remains outside every MCP profile. Feedback is local diagnostic input, not trusted truth, approval, outcome memory, or product-benefit evidence. Returned relationships and rankings remain navigation evidence, not runtime proof. |
| Context packaging | Agent-format packages, 12,000-character MCP cap, source spans, rationale, relationships, and .NET, Python, and Rust validation recommendations implemented. | Source verification remains required for consequential conclusions. |
| Local UI | Read-only health, repository, run, freshness, and search views implemented. | It is a local inspection surface, not established product-benefit evidence. |
| Evaluation | Deterministic fixture, live MCP, spontaneous, evaluator-assisted, configured/onboarded paired-agent, and model benchmark harnesses implemented. Agent campaigns require explicit input-plus-output-plus-reasoning reported-token accounting, a runner-declared hard-cap capability, remaining-budget limits on every invocation, boundary stopping, and no automatic retry. Configured mode also verifies the reviewed normal-profile plan, committed guidance, baseline MCP identities, fresh binding, positive runtime probe, and fail-closed rejection probe. | Configured outcomes include neutral one\|nine, regressed and improved Config.Net, and two duration-regressed YoutubeDownloader campaigns. None establishes repeatable benefit. Default `codex` capability preflight refuses because it cannot guarantee the hard cap. Explicit `capped-codex` failed closed in its first authorized campaign when provider credits were unavailable; no pair completed and the campaign is consumed. |
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
configuration, runtime identity, safety, and adoption observed across the
campaigns. They do not establish attributable correctness or efficiency
benefit, repeatability, release readiness, deployment acceptance, provider
authorization, or production fitness. Secondary, Tertiary, Release, and Hotfix
are not activated; Run-only remains excluded.

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

### Configured replication readiness

- Exact clean CodeMesh candidate `b16eee7` adds a configured/onboarded suite
  while preserving the frozen Config.Net prompt, targets, thresholds, and
  source commit.
- The reviewed local normal-profile installation and ignored repository
  guidance bind exact Config.Net commit `ae0af7d`, project `prj_e5d8c8`,
  checkout `chk_6d1d16`, and source view `b4981658`.
- The configured preflight passed with prompt parity, fresh accepted binding,
  the four-tool normal profile, a positive context package, and fail-closed
  rejection. The six-case live gate then passed all 18 calls with recall, MRR,
  and nDCG of 1.0 and zero secret leaks.

This is provider-free configured-integration readiness, not agent adoption or
product-benefit evidence. The exact sanitized record is
[configured Config.Net provider-free evidence](../evaluation/evidence/configured-config-net-provider-free-b16eee7.json).

The separately authorized configured campaign then completed all three pairs
with context-package adoption in every treatment and no safety, MCP transport,
or command-policy failure. All three controls passed, while two treatments
missed required implementation or test citations; the treatment success rate
was therefore one of three and the verdict was `regressed`. On the only pair
where both conditions passed, treatment was 21.31% slower and used 117.18%
more tokens. This is valid negative configured-product evidence, not replicated
benefit. Preserve the consumed result and do not retry it automatically. The
sanitized record is
[configured Config.Net agent evidence](../evaluation/evidence/configured-config-net-agent-b16eee7.json).

### Independent configured replication

Exact clean candidate `64d4052` adds a configured/onboarded version of the
frozen YoutubeDownloader audio-container impact task without changing its
prompt, targets, thresholds, source commit, or model settings. Its 125 Python
tests, Ruff checks, five deterministic fixtures, reviewed normal-profile plan,
configured preflight, positive and wrong-checkout probes, two-case impact live
gate, and unchanged six-case live gate all passed. The impact gate covered all
six required targets with recall and MRR 1.0, nDCG 0.891323, and zero leaks;
the unchanged live gate retained recall 1.0, MRR 0.9, nDCG 0.926186, and zero
leaks. Exact identities and hashes are retained in the
[configured YoutubeDownloader provider-free evidence](../evaluation/evidence/configured-youtube-downloader-provider-free-64d4052.json).

The separately authorized configured campaign completed all three pairs with
100% control and treatment correctness, context-package adoption in every
treatment, and no safety, MCP, or command-policy failure. Treatments attempted
the context package two, two, and three times. With no correctness win or
regression, treatment median duration was 49.79% higher and median tokens were
41.00% higher across all three matched pairs, so the valid verdict is
`regressed`. This replicates configured adoption and correctness on another
C# repository, not repeatable product benefit. Raw query arguments were not
retained, so focused-query guidance is a diagnosis lead rather than an
established cause. The sanitized result is
[configured YoutubeDownloader campaign evidence](../evaluation/evidence/configured-youtube-downloader-agent-64d4052.json).

### Task-adaptive query correction

The provider-free YoutubeDownloader diagnosis preserved its six impact targets,
source commit, repository identity, and retrieval thresholds. One frozen
task-shaped package covered all six targets in one call with primary rank two.
Three proactive focused packages also covered all six, but produced 35,991
agent-formatted characters instead of 12,000 and repeated five of 24 ranked
item occurrences. The diagnostic comparison is retained separately because its
CodeMesh worktree contained the new suite and guidance edits:
[task-adaptive query diagnosis](../evaluation/evidence/youtube-downloader-task-adaptive-query-diagnosis-e2e1bca.json).

Exact clean detached candidate `fbc1433` contains the smallest correction.
Agents now start with one concise task-shaped package, stop when it resolves
every required facet, and issue a focused follow-up only for a specific
unresolved implementation or test facet. The guidance caps each task at three
non-overlapping packages. At that commit, 125 Python tests, Ruff checks, five
deterministic MCP fixtures, the reviewed normal-profile preflight, positive
probe, and wrong-checkout rejection all passed. The adaptive five-case gate
passed all 15 calls with recall 1.0, MRR 0.875, nDCG 0.862253, and zero leaks.
The unchanged impact gate retained recall and MRR 1.0 and nDCG 0.891323; the
unchanged canonical gate retained recall 1.0, MRR 0.9, and nDCG 0.926186.
No model provider was invoked. Exact hashes and identities are in the
[task-adaptive provider-free evidence](../evaluation/evidence/youtube-downloader-task-adaptive-provider-free-fbc1433.json).

The separately authorized `fbc1433` configured campaign then completed all
three pairs with 100% control and treatment correctness, one successful context
package in every treatment, and no safety, MCP, or command-policy failure. It
had no correctness win or regression. Median treatment tokens were 6.63% lower,
but median duration was 10.0192% higher, crossing the frozen 10% threshold by
0.0192 percentage points and producing a `regressed` verdict. The campaign also
reported 2,596,056 aggregate tokens, including 2,219,264 cached-input tokens,
and therefore exceeded its authorized 1.6M reported-token ceiling. The
evaluator at that candidate had no hard aggregate-token stop; this is a control
failure, not a reason to discard or retry the consumed result. Raw traces and
query arguments were not retained. The sanitized record is
[task-adaptive configured campaign evidence](../evaluation/evidence/configured-youtube-downloader-agent-fbc1433.json).

## Current Gap

The next search diagnosis now has request-isolated operation timing in the
source. It separates source-store fetches, candidate selection, context
expansion, declaration and content reads, optional relationships, and final
ranking, while retaining the existing package-stage timing and unchanged
responses. Injected-delay tests cover attribution, result parity, overlapping
requests, and failure cleanup. This instrumentation does not establish a new
agent-benefit result.

Clean instrumentation candidate `2879e7f` passed the unchanged adaptive live
suite in a fresh isolated store with recall 1.0, MRR 0.875, nDCG 0.862253,
and zero leaks. The task-shaped package p50 was 451.070 ms. Adding 50,000
synthetic unrelated graph nodes left retrieval unchanged but increased package
p50 to 1,504.467 ms, including 1,227.914 ms in lexical fetch. The query plan
loaded lexical properties for all 51,685 nodes before repository filtering.
An isolated query experiment moved that filter before property projection,
loaded properties for only the 1,685 target nodes, and preserved the exact
ordered candidate hash. Clean correction candidate `4fb9e81` passed the frozen
adaptive, impact, and canonical live suites with unchanged quality and zero
leaks. Under the same synthetic store load, task-shaped package p50 fell to
391.808 ms (73.96% lower) and lexical fetch p50 to 124.113 ms (89.89% lower).
All adaptive cases retained identical ordered candidates. The
[correction evidence](../evaluation/evidence/search-scope-correction-4fb9e81.json)
records exact candidates, checks, hashes, and claim limits. This controlled mechanism
does not establish the cause of the historical 16.7-second result or an agent
benefit. The [search-scope diagnosis](../evaluation/evidence/search-scope-diagnosis-2879e7f.json)
retains timings, plans, fixture identity, report hashes, and limitations.

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

The provider-free task-shaped context-package coverage diagnosis is now
complete at exact baseline candidate `b16eee7`. The frozen 58-term
task query returned eight test paths and only one of seven required targets.
Four concise task-derived facets covered all seven targets in a separate
five-case/15-call provider-free suite with recall 1.0, MRR 0.660714, nDCG
0.76259, and zero secret leaks. The unchanged canonical live suite also passed
all 18 calls with recall, MRR, and nDCG of 1.0. This isolates a bounded guidance
and query-decomposition gap without proving which query the paid treatments
used. Exact details are retained in the
[focused-query diagnosis](../evaluation/evidence/config-net-focused-query-diagnosis-b16eee7.json).

Exact clean detached candidate `3804028` contains the smallest correction: the
context package remains the single normal-host entry tool, while MCP
instructions, tool and status guidance, and generated onboarding direct
multi-part work to a small set of focused implementation and test queries
instead of one long full-task query. All 125 Python tests, Ruff checks, and five
deterministic MCP fixtures pass at that candidate.

The reviewed configuration-only Config.Net plan, separately managed ignored
guidance, configured preflight, positive probe, and wrong-checkout rejection
all passed with provider mode `none`. The committed focused suite then passed
all five cases and 15 calls with recall 1.0, MRR 0.660714, nDCG 0.76259, and
zero secret leaks; `LazyVar.cs` remains at the accepted rank-eight boundary.
The unchanged canonical suite also passed all six cases and 18 calls with
recall, MRR, and nDCG of 1.0 and zero secret leaks. This establishes an exact
provider-free correction candidate, not normal-agent compliance or product
benefit. Exact identities and report hashes are retained in the
[focused-query provider-free evidence](../evaluation/evidence/config-net-focused-query-provider-free-3804028.json).
The separately authorized exact-candidate campaign then completed all three
pairs and received an `improved` verdict. Every treatment used the context
package, made two or three package attempts, passed the citation grader, and
completed without safety, MCP, or command-policy failure. Controls passed two
of three; the second control missed `ConfigurationBuilder.cs`, producing one
CodeMesh-attributable win and no treatment regressions. Across the two jointly
successful pairs, treatment median duration was 13.69% lower and median tokens
were 3.59% lower. This is positive configured evidence for one task, repository,
model, and three-pair campaign; it does not establish that the wording change
caused the result or that product benefit is repeatable. The sanitized record is
[focused-query configured campaign evidence](../evaluation/evidence/configured-config-net-agent-3804028.json).
Preserve all one|nine and Config.Net campaigns in their original evidence
classes. This retest is consumed; no further model spend is authorized.

Both configured YoutubeDownloader campaigns are consumed. Candidate `64d4052`
preserved full adoption and correctness but regressed duration by 49.79% and
tokens by 41.00%. Candidate `fbc1433` reduced each treatment to one context
package and lowered median tokens by 6.63%, but its 10.0192% duration regression
still failed the frozen threshold. It also exceeded its authorized aggregate
reported-token ceiling because that historical evaluator did not enforce a hard
stop. The current evaluator closes that control gap with explicit
reported-token accounting, a mandatory compatible runner capability,
remaining-budget limits, boundary stopping, and no automatic retry. The
default Codex runner does not claim that capability and is refused before any
model call. The explicit `capped-codex` runner now counts complete request input,
reserves worst-case output-plus-reasoning charge, enforces zero provider
request/stream retries, retains ambiguous reservations, and reconciles its
sanitized ledger against Codex final usage. These records establish configured
adoption and correct/safe completion, not repeatable benefit or efficiency
causality. Neither consumed campaign may be retried.

Provider-free attribution at exact instrumentation candidate `66033ad` measured
the task-shaped package at 16,830.931 ms total p50: search accounted for
16,725.370 ms (99.37%) and item hydration for 102.668 ms (0.61%). Hydration did
not qualify as dominant, so the proposed concurrency optimization was rejected.
Any fresh paid evaluation still requires exact-candidate deterministic,
configured, retrieval, safety, and capped-runner gates plus explicit spend
authority.

Exact clean candidate `0f18071` passed 149 Python tests, Ruff check and format,
all five deterministic MCP fixtures, repository standards, the configured
positive and fail-closed rejection preflight, and the frozen adaptive, impact,
and canonical provider-free suites. A synthetic provider-free run through the
installed Codex executable completed one counted request with zero retries and
exact proxy/final-usage agreement. The one separately authorized
`gpt-5.6-sol` medium-reasoning campaign then stopped after its first control
execution because the provider reported no available credits. No pair
completed. The proxy retained the interrupted call's full 267,528-token
reservation, admitted no later request, and recorded zero request or stream
retries. The campaign is `insufficient`, incomplete, and consumed; it is hard-cap
failure evidence only, not agent adoption, correctness, efficiency, or spend
evidence. The sanitized record is
[capped YoutubeDownloader campaign evidence](../evaluation/evidence/configured-youtube-downloader-agent-0f18071.json).

Expand onboarding to another one|nine checkout only with separate authority,
exact binding, fresh ingestion, and a passing checkout-specific probe. The
earlier `de239b7` stale state and `9f3216c` stale-candidate rejection remain
useful historical diagnostics; they are not the current candidate state.

## Public Repository And Hosted Evidence

At the 2026-09-08 read-only GitHub recheck, the public `main` branch remains at
`8e9c0da`, while the local configured-evaluator candidate and its documentation remain unpublished.
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

The original [CodeQL triage](../evaluation/evidence/codeql-triage-8e9c0da.json)
is preserved. Local security hardening now validates evaluation suite names and
identifiers, contains setup patches and generated artifact paths, and rejects
invalid suites before preparation or model execution. Literal argv and all five
UI routes have adversarial regression coverage. The full Python suite passes
227 tests with two existing dependency warnings. The
[local boundary review](../evaluation/evidence/security-boundary-review-20260905.json)
accounts for all 39 findings, including explicit operator-selected paths and
trusted executable inputs. This is local verification, without an updated
hosted scan or alert dismissal.

The subsequent UI correction explicitly HTML-escapes dynamic link attributes
and the numeric search limit at their render points. All 231 Python tests pass,
including hostile attribute values and invalid or out-of-range limit rejection
before store access; Ruff lint and formatting pass. Two existing dependency
warnings remain. This verification does not dismiss the hosted XSS finding.

The local-input security review then reproduced overwrites of existing packet
destinations, including symlinks and hardlinks. Feedback recording now creates
packet files exclusively and explicitly rejects linked outboxes before the
existing Git ignore check (which already rejected Linux outbox symlinks). The
three overwrite regressions fail before correction and pass afterward; an
additional test checks explicit outbox rejection. The full
Python suite now passes 235 tests with two existing dependency warnings.

The [local CodeQL review](../evaluation/evidence/local-codeql-review-b73e19a.json)
now binds complete extraction and pinned suites to exact local source. Python
`b73e19a` has zero default-threat findings and 61 local-input findings; unchanged
C# source at `e0beba9` has zero default findings and 192 local-input findings.
All 253 local-input results have retained locations and boundary review. The
HTML finding is absent after explicit attribute escaping. Cached first attempts
were rejected for local-threat claims and rerun, with original results retained.
This is local static-analysis evidence, without hosted dismissal or a blanket
security-clean claim.

## Local Release Preparation

The source version is now declared in `VERSION` and consumed by .NET builds.
Python package metadata, lockfile, and version export are checked for agreement;
REST OpenAPI uses that export. Both CLIs expose a provider-free version command.
The retained source value is `0.1.0`, preserving the existing Python value and
creating no published release. The full local verification passes 70 .NET tests
with no skips, 228 Python tests, and five deterministic MCP cases. The .NET
build retains its existing nullable warning and Python retains two dependency
warnings. The retained 2026-09-05 .NET and locked Python dependency advisory
checks report no known vulnerabilities for CodeMesh's own dependency sets; this does not clear
the frozen external sample's separate advisory or the hosted CodeQL findings.

[Release Preparation](../engineering/release-preparation.md) defines a reviewable
candidate contract, compatibility policy, environment evidence, verification,
recovery, and publication gates. Local [package verification](../evaluation/evidence/local-package-verification-96b4ebf.json)
now binds Python wheel/source artifacts, a .NET publish archive, and their
checksums to clean `96b4ebf`. Installed-wheel CLI, REST OpenAPI, normal manifest,
bundled suite/patch loading, and all five fixture cases pass. Full smoke passes
at that candidate. Parser packaging correction `1ef5ca9` adds the required SDK
to its runtime and the version files to the Docker allow-list; its project
probe loads through MSBuild without filesystem fallback, while retaining a
read-only generated-editor-config warning at that historical candidate.
The subsequent C# capability `0.2.3` output-isolation correction now passes two
concurrent read-only container parses without warnings, preserves generated
compiler metadata and cross-project relationships, and cleans temporary output
after completion and observed project failures. Its deterministic verification
passes 71 .NET tests with no skips and 228 Python tests. See the
[output-isolation decision](../decisions/0005-isolate-parser-design-time-outputs.md).
Hosted security review, Windows and
other environment acceptance, a supported upgrade/rollback rehearsal,
appropriate product evidence, and owner release approval remain separate gates.
A [disposable Linux recovery rehearsal](../evaluation/evidence/local-recovery-rehearsal-f314043.json)
now passes at `f314043`: the complete stopped four-volume set restored into new
volumes with identical image IDs and matching graph, MongoDB, vector, registry,
snapshot, and context-item digests. This closes the local same-version recovery
mechanism check; it does not establish a supported upgrade or production recovery.

A [development-baseline upgrade and rollback rehearsal](../evaluation/evidence/local-development-upgrade-ce23f2e.json)
now verifies isolated `8e9c0da` to `ce23f2e` reader compatibility, re-ingestion,
identity preservation, eight source citations, scoped deletion, and exact
whole-set rollback. The initial six-case retrieval gate failed its relationship
check without sample dependency assets. Locked sample restore failed on the
frozen AngleSharp advisory; the assets it produced enabled a subsequent
unchanged six-case/18-call gate to pass, with advisory warnings retained. The
local mechanism passes, while sample dependency and supported-environment
acceptance remain open. All task containers are down and backups are preserved.

The [Linux Python runtime matrix](../evaluation/evidence/python-runtime-verification-b73e19a.json)
now passes all 235 tests and five deterministic fixture cases on Python 3.12.14,
3.13.15, and 3.14.7 at `b73e19a`. Each retains two existing dependency warnings.
This extends local source verification; Windows and released-artifact acceptance
remain separate.

[Refreshed local artifacts](../evaluation/evidence/local-package-verification-a158bc0.json)
now bind the completed parser, UI, and feedback corrections to clean `a158bc0`.
The installed wheel passes version/OpenAPI checks, the four-tool normal manifest,
all 16 packaged suites and patches, and five fixture cases. The .NET publish
contains the design-time targets and reports the exact build SHA. Full smoke and
two concurrent read-only parser-container parses pass; the parser emits no
warnings and leaves no scratch directories. The retained 2026-09-05 dependency
advisory checks report no known vulnerabilities in CodeMesh's 11 .NET projects and 48 Python
packages. All task containers are down. These are local artifacts and checks,
with the separate sample advisory and release/acceptance gates still open.

The [source review packet](../evaluation/review-packet-a158bc0.md) now supplies
draft release notes and a seven-gate evidence ledger.
Artifact bytes and all 12 dependency-lock identities were reverified on
2026-09-08. The packet records the 2026-09-05 requirement for a PR and `verify`
for main; no release or remote tag exists at the 2026-09-08 recheck.
Owner review, publication authority, supported profiles, and representative
resource acceptance remain open.

The [fresh configured runtime probe](../evaluation/evidence/configured-runtime-verification-a158bc0.json)
now verifies normal-profile installation and retrieval, rejection of incorrect
source hashes, unknown checkouts, and dirty source, and acceptance after source
restoration. The installed wheel drove
the unchanged source-backed launch; no model campaign was run.

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
