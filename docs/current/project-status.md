# CodeMesh Project Status

Document type: current status snapshot

Reviewed: 2026-09-01

Implementation reviewed through: configured-evaluator candidate `0bde606`.

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
| Evaluation | Deterministic fixture, live MCP, spontaneous, evaluator-assisted, configured/onboarded paired-agent, and model benchmark harnesses implemented. Configured mode has a provider-free preflight that verifies the exact reviewed normal-profile plan, committed guidance, baseline MCP identities, fresh binding, positive runtime probe, and fail-closed rejection probe before either paired condition runs. | Candidate `0bde606` passed the configured one\|nine preflight and both frozen provider-free retrieval gates. No configured model-backed outcome report exists. Paid/model-backed runs require explicit authorization; fixtures and provider-free gates prove their bounded contracts only. |
| Generated summaries | Complexity-aware prompts and local/online providers implemented. | No summary deployment profile is CodeMesh-qualified. |
| Security | Pre-persistence value redaction and generated/cache path exclusions implemented. | Known secret-file exclusion and configurable allow/deny policy remain open. |
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
`6f5e68c225f88b6162f386e4c3bfb9ae1d974f70d56b04a50c142be7542c004e`
changed only Primary's ignored `.codex/config.toml`. The normal-profile probe
accepted the exact fresh binding and the configured preflight preserved prompt
parity. Its installed ignored `AGENTS.override.md` guidance was retained by
source classification and hash, not raw content. The positive gate returned
both `app/feed_hub/native_replay.py` and
`native/feed_hub_replay/src/lib.rs`; the wrong-checkout gate failed closed with
the live binding, freshness, and provenance issue codes.

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

This is provider-free local diagnostic evidence. It proves a bounded configured
path and feedback/improvement loop, not normal-agent adoption, general product
benefit, release readiness, deployment acceptance, provider authorization, or
production fitness. Secondary, Tertiary, Release, and Hotfix are not activated;
Run-only remains excluded.

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
installation plus probing are reviewable. Clean candidate `0bde606`, exact
Primary commit `fe2f761`, the configured preflight, the eight-gate frozen
one|nine pilot, and the YoutubeDownloader live gate all pass provider-free. The
next evidence gap is adopted normal-host agent tasks that compare this exact
configured path with ordinary exploration without changing task prompts.

The prompt-parity Config.Net campaign recorded zero MCP calls and zero MCP call
attempts. Preserve it as negative spontaneous-discovery evidence; do not change
the frozen task prompt, grading, or targets to manufacture adoption. The next
product-proof campaign should instead evaluate the exact configured/onboarded
integration shipped to normal users, while retaining the same task prompt for
control and treatment.

The evaluated required MCP configuration completed without a harness failure,
and the CodeMesh manifest publishes the intended instructions and tool
contracts. Current Codex documentation says the host reads MCP server
instructions, but its prompt-input diagnostic does not expose the separate base
instructions and tool schemas. The retained campaign therefore cannot attest
the exact selection context presented to the model, and no CodeMesh transport
or contract defect has been confirmed.

The configured/onboarded evaluator now preserves prompt parity, uses the exact
reviewed checkout-local `normal` installation, and retains integration mode,
guidance, baseline MCP, tool-profile, binding, installation-plan, and runtime-
probe identities. It rejects a dirty or stale target, a dirty CodeMesh source
checkout, commit or binding mismatch, changed plan files, unexpected tool
surface, and a failed rejection probe. Historical spontaneous and assisted
modes retain their prior diagnostic behavior.

The clean provider-free gate is complete. The authoritative instance registry
pins Primary `fe2f761`, detached CodeMesh candidate `0bde606`, and the matching
source-view identity; those identities must remain frozen for the next
campaign. The immediate next gate is the model-cost-bearing paired one|nine
campaign through that exact configured installation, which requires separate
explicit model-spend authority. Its passing provider-free preflight proves
configuration and runtime identity only, not normal-agent adoption or product
benefit.

Run the configured Config.Net replication only after a valid one|nine paired
campaign. Expand onboarding to another one|nine checkout only with separate
authority, exact binding, fresh ingestion, and a passing checkout-specific
probe. The earlier `de239b7` stale state and `9f3216c` stale-candidate rejection
remain useful historical diagnostics; they are not the current candidate
state.

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
- Current source redaction does not replace repository authorization or a
  configurable sensitive-file policy.
- Hosted workflow success for remote `8e9c0da` is not evidence for unpublished
  local commits, and an automated scan completing successfully does not resolve
  or justify its open findings.

## Status Maintenance

Update this page when implemented capability, reviewed evidence, or the
immediate product gap changes. Keep detailed procedures in their canonical
guides and keep future execution order in `docs/planning/next-steps.md`.
