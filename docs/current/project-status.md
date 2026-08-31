# CodeMesh Project Status

Document type: current status snapshot

Reviewed: 2026-08-31

Implementation reviewed through: clean candidate `ee1d4d9`.

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
| Evaluation | Deterministic fixture, live MCP, spontaneous/evaluator-assisted paired agent, and model benchmark harnesses implemented. | Configured/onboarded paired mode is not implemented. Paid/model-backed runs require explicit authorization; fixtures prove contracts only. |
| Generated summaries | Complexity-aware prompts and local/online providers implemented. | No summary deployment profile is CodeMesh-qualified. |
| Security | Pre-persistence value redaction and generated/cache path exclusions implemented. | Known secret-file exclusion and configurable allow/deny policy remain open. |
| Repository identity | Stable project/checkout markers, deterministic source snapshots, checkout-current and clean branch-head slots, explicit retained slots, legacy migration, and richer local freshness implemented. | Separate clones attach with explicit `--project-id`; shared-service tenant/authorization/privacy controls remain deferred. |

Detailed current interfaces are in
[Agent Access Contracts](agent-access-contracts.md), and component boundaries
are in [Architecture](architecture.md).

## Activated one|nine Pilot

The first bounded pilot is active only for the clean Primary checkout at
`e12d0281b687e58c2baac85f771a684df6fa8552`. It is bound to project
`prj_a570a726917d4d0ca596085aaf07af50`, checkout
`chk_70c50c5494de4837ab0627aca021eab2`, and source view
`ce3c63a66e3e4821bf5431d9997314070d60ec61f9ab8b35aa0cdcafbacace4a`.
The provider-free ingestion published snapshot
`snp_52a2af6a662c8070cea0ccb6db837a68717f45422aa7574fe5db0af2543169e9`
with 45,492 nodes, 94,774 relationships, 12,766 content items, zero
embeddings, and zero summaries.

The reviewed installation plan changed only Primary's ignored
`.codex/config.toml`. The normal-profile stdio probe accepted the exact binding,
reported fresh commit/source provenance, exposed exactly four tools, and
returned real Python and Rust context. A focused test-selection probe initially
missed `tests/test_feed_hub_native_replay_adapter.py`; a feedback packet
recorded the exact commit/snapshot failure, identifier tokenization was
corrected, and a superseding recheck returned the target. The feedback summary
now reports that ranking item as resolved and the onboarding probe as verified.

The clean CodeMesh candidate `ee1d4d9` and installation plan
`6d37def879a062f8a93923514376f14707ddf430582e675aff44aa7b2e4ad40a`
then passed eight provider-free runtime
gates: accepted fresh Python, Rust, test-selection, and PyO3 retrieval, plus
fail-closed wrong-checkout, wrong-root, wrong-source-view, and dirty-checkout
probes. It validated all three retained Primary feedback packets and returned
the checkout to a clean state.

The same clean candidate passed the pinned six-case, 18-call
YoutubeDownloader summary-free live gate with 1.0 recall, 0.9 MRR, 0.926186
nDCG, and zero secret leaks. The first candidate run exposed and retained a
partial-symbol primary-path ranking regression; deterministic canonical source
selection corrected it before the final pass. The sanitized exact-candidate
record is
[one|nine Priority 1 evidence](../evaluation/evidence/onenine-priority1-ee1d4d9.json).

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

Explicit repository onboarding is now implemented for the bounded one|nine
pilot: the normal profile exposes only context package, repository status,
repository listing, and node lookup; exact binding and freshness are enforced;
and installation plus probing are reviewable. The clean committed candidate and
its provider-free gates now pass. The next evidence gap is adopted normal-host
agent tasks that compare the configured path with ordinary exploration without
changing task prompts.

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

The configured/onboarded agent campaign remains model-cost-bearing and requires
explicit authorization, clean committed checkouts, a fresh matching index, and
report metadata that identifies the shipped guidance and tool profile. Unit and
contract tests for instructions do not substitute for normal-host evidence.

The existing paired-agent runner cannot yet produce that evidence. It selects
the historical unbound `diagnostic` profile and classifies runs only as
spontaneous or evaluator-assisted. Before any paid campaign, extend it to use
the reviewed checkout-local `normal` installation unchanged and retain the
integration mode, guidance identity, tool profile, binding, installation-plan
hash, and runtime-probe identity in the report. This provider-free harness work
is the first remaining implementation step; running it against a model remains
a separate spend-authority gate.

## Public Repository And Hosted Evidence

At this review, the public GitHub `main` branch remains at `8e9c0da`, while the
local checkout is four commits ahead at documentation-only HEAD `96335a1`. The
latest hosted baseline-verification success applies to remote `8e9c0da`; there
is no exact-HEAD hosted workflow evidence for the local one|nine pilot commits.

The latest hosted CodeQL workflow completed successfully for remote `8e9c0da`,
which proves that the scan ran, not that the repository is security-clean.
GitHub still reports 39 open CodeQL alerts: 3 critical command-line-injection
alerts and 36 high alerts, comprising 35 path-injection findings and one
reflected-XSS finding. Dependabot and secret scanning report zero open alerts.
These hosted findings apply to the published remote state and do not establish
the security state of the unpublished local commits.

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
- Hosted workflow success for remote `8e9c0da` is not evidence for the four
  unpublished local commits, and an automated scan completing successfully does
  not resolve or justify its open findings.

## Status Maintenance

Update this page when implemented capability, reviewed evidence, or the
immediate product gap changes. Keep detailed procedures in their canonical
guides and keep future execution order in `docs/planning/next-steps.md`.
