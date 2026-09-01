# Agent Integration Contract

Document type: selected product contract and implementation plan

Reviewed: 2026-09-01

This document selects the v1 integration contract for CodeMesh in coding-agent
hosts. The MCP server instructions, manual repository guidance in
[MCP Setup](../guides/mcp-setup.md), normal/diagnostic tool profiles, exact
checkout binding, fail-closed package freshness, reviewable installation, and
provider-free probes are implemented and passed their clean-candidate gates at
`ee1d4d9`. Configured/onboarded evaluator support is implemented and its live
stale-candidate rejection is verified through `9f3216c`. Exact-candidate
preflight, the frozen one|nine retrieval and rejection gates, and the pinned
YoutubeDownloader live gate passed again with the status-to-context correction
at exact clean candidate `0378740`. The first configured normal-host campaign
remains frozen at `0bde606`; it completed safely and correctly but was
insufficient because two treatments stopped after status and none retrieved
task context. The separately authorized `0378740` campaign was also safe and
correct but insufficient: one treatment stopped after status and none retrieved
task context. The status-result next-action field therefore did not establish
the required normal-host transition. The current implementation instead makes
the fail-closed context package the single normal-host entry action and retains
status for explicit diagnostics. Exact clean candidate `8844c21` passed the
full deterministic and provider-free gates. Its authorized paired campaign
then retrieved a context package in all three treatments and passed all six
executions safely. The verdict was `neutral`, with no attributable wins or
regressions, so adoption is established for the selected task but product
benefit is not.

The separately authorized Config.Net campaign at exact candidate `b16eee7`
also retrieved a context package in every treatment, but two of three
treatments missed required citations while all controls passed. Its `regressed`
verdict establishes configured adoption on a second repository, not product
benefit. Preserve the consumed campaign without an automatic retry.

The bounded follow-up correction is frozen at exact clean candidate `3804028`.
It keeps the context package as the single entry tool and directs multi-part
work to focused implementation and test queries. The reviewed configured
preflight, positive and fail-closed probes, focused-query live suite, unchanged
canonical live suite, and deterministic Python checks all pass with provider
mode `none`. This establishes correction readiness only; normal-agent guidance
compliance and product benefit still require a separately authorized campaign.

That separately authorized campaign completed at the same exact candidate with
the frozen Config.Net comparison conditions. All three treatments adopted the
context package and passed safely; controls passed two of three, producing one
CodeMesh-attributable win, zero treatment regressions, and an `improved`
verdict. Efficiency medians were also favorable across the two jointly
successful pairs. This is positive evidence for the bounded campaign, not proof
that focused wording caused the change or that benefit repeats elsewhere.

The independent configured YoutubeDownloader impact campaign at clean
candidate `64d4052` then preserved a different frozen C# task and repository.
Every control and treatment passed safely, and every treatment adopted the
context package, but treatment medians were 49.79% slower and used 41.00% more
tokens across all three pairs. Its `regressed` verdict is an efficiency result,
not a correctness regression. Configured adoption and correctness now repeat
across repositories, but product benefit does not. Raw query arguments were not
retained, so task-adaptive query decomposition remains a provider-free
diagnosis requirement rather than an established correction.

## Decision

CodeMesh v1 requires explicit, repository-owned agent onboarding. A configured
repository tells compatible coding agents when and how to use CodeMesh for the
initial C#/.NET wedge: implementation discovery, likely change-impact analysis,
and validation selection.

MCP server instructions and tool descriptions remain useful defense in depth,
but they are not the sole integration mechanism. Spontaneous discovery of an
available MCP server remains a later usability objective, not a v1 product
acceptance gate.

This choice follows the retained CodeMesh evidence:

- summary-free live retrieval has passed on two repositories;
- assisted campaigns have replicated utility after explicit onboarding; and
- spontaneous and prompt-parity campaigns have recorded zero CodeMesh adoption.

A comparative review of Graphify's integration in a separate repository also
showed the value of durable repository guidance, a narrow host allowlist, and
freshness checks. It also showed why configuration inspection is insufficient:
the declared integration can look valid while the configured runtime cannot
start. Those observations motivate the live probe below, but they are design
input rather than CodeMesh effectiveness evidence.

## V1 User Contract

CodeMesh may claim configured product use only when all of these conditions
hold:

1. The repository owner has reviewed and opted into the canonical CodeMesh
   guidance block in the repository's agent instructions.
2. The host uses the CodeMesh normal-user tool profile rather than exposing the
   entire administrative surface by default.
3. Configuration identifies the intended project and checkout without silently
   choosing among ambiguous indexed repositories.
4. A live probe starts the configured MCP process, completes initialization,
   validates the expected profile, reaches the stores, and confirms a fresh
   matching repository snapshot.
5. Agents begin relevant tasks with a context package, verify consequential
   findings against current source, and fall back to normal repository
   exploration when CodeMesh is unavailable, stale, or ambiguous. Agents start
   with one concise task-shaped package and stop retrieving when it covers every
   required facet. A specific unresolved implementation or test facet permits
   one focused follow-up, with at most three non-overlapping packages per task.

The supported claim should remain bounded:

> When CodeMesh is configured for a repository and its standard agent guidance
> is installed, coding agents begin with fresh, source-grounded context packages
> for supported C#/.NET implementation-discovery, likely change-impact, and
> validation-selection tasks.

Measured outcome improvement requires separate retained evaluation evidence.
Configuration alone does not establish adoption, correctness, efficiency, or
product benefit.

## Repository-Owned Onboarding

The canonical manual block lives in [MCP Setup](../guides/mcp-setup.md). The
installer generates a complete hashed plan, and applies only that unchanged
reviewed plan after its hash is supplied explicitly. It may manage the marked
guidance block or run in configuration-only mode when another repository owns
generated guidance. It does not silently replace unrelated instructions.

Repository guidance is the portable contract. Host-specific hooks may display
freshness warnings or reminders, but correctness must not depend on a hook that
another host may ignore.

## Tool Profiles

The implemented default `normal` profile is deliberately small:

- `codemesh_get_context_package`
- `codemesh_get_repository_status`
- `codemesh_list_repositories`
- `codemesh_get_node`

This profile supports the intended package-first workflow, repository
resolution, freshness inspection, and targeted CodeMesh reads. Coding agents
may also verify returned spans with their ordinary source-reading tools.

The implemented `diagnostic` profile adds status, guidance, search, symbol,
neighbor, repository-detail, summary-coverage, and ingestion-run tools. Select
profiles with `mcp --profile normal|diagnostic`; `normal` is the default, unknown
names fail before startup, and the static manifest records its selected profile.
Destructive repository deletion remains outside both profiles and is available
only through the explicit administrative REST and Python CLI surfaces.

## Checkout And Freshness Behavior

The normal MCP integration binds host configuration to an exact project,
checkout, repository root, and optional source-view hash. It fails clearly when
selection is missing, wrong, ambiguous, dirty, or stale rather than using
whichever indexed repository looks most recent.

Freshness is a server-side acceptance condition. Before returning task context,
CodeMesh compares the configured checkout and source state with the active
indexed snapshot and exposes the assessment in the response. Client warnings
cannot convert stale data into accepted evidence.

## Live Runtime Probe

Static configuration validation and manifest printing are insufficient because
they do not prove that the configured process can initialize in the target
environment. The implemented positive probe:

1. launch the exact stdio command and working directory used by the host;
2. complete MCP initialization and inspect the server instructions;
3. verify the selected tool profile and reject unexpected destructive tools;
4. call service and store health through the running server;
5. resolve the configured repository without ambiguity; and
6. confirm current checkout and snapshot freshness.

It exits nonzero with a specific diagnostic when any required condition fails.
The companion rejection probe launches the same normal profile with an unsafe
binding and proves that it fails closed. Both probes force provider mode to
`none` and do not invoke a paid model.

## Evaluation Classification

Future reports must distinguish three integration modes:

- **Spontaneous:** control and treatment task prompts are identical; treatment
  adds CodeMesh MCP only and receives no repository onboarding.
- **Evaluator-assisted:** treatment receives temporary evaluator-only guidance.
  Existing assisted evidence remains in this category.
- **Configured/onboarded:** treatment uses the exact repository guidance, tool
  profile, checkout binding, and setup process shipped to normal users. The task
  prompt remains identical to control.

Configured/onboarded evidence supports the selected v1 contract. It must not be
relabeled as spontaneous discovery, and older evaluator-assisted runs must not
be retroactively relabeled as configured product evidence.

The implemented configured mode records integration mode and exact identities
for installed guidance, baseline MCP servers, selected tool profile, binding,
reviewed plan, and positive and rejection probes. It gives control the declared
baseline servers and treatment the identical baseline plus CodeMesh, without
changing the task prompt. The frozen task, grading targets, model settings,
clean-checkout requirements, and summary-free live gate remain unchanged.

The provider-free preflight must pass against the exact candidate before a
campaign. Across the first two authorized one|nine configured campaigns, three
treatments called repository status but none retrieved a context package or
produced an attributable win. The `8844c21` campaign then retrieved a context
package in every treatment, but its neutral result still produced no
attributable win. The `b16eee7` Config.Net campaign also achieved full adoption
but regressed correctness in two treatments. Any further paired comparison
remains model-cost-bearing and requires new separate authorization. The
separately consumed `3804028` Config.Net campaign later produced one
attributable win and zero regressions, but its single-task result does not make
benefit repeatable. The independent `64d4052` YoutubeDownloader campaign then
preserved full adoption and correctness on a different C# repository, but its
49.79% median duration regression and 41.00% median token regression produced a
`regressed` verdict. That result makes task-adaptive query strategy the next
provider-free diagnosis; it does not authorize an automatic paid retry.

## Completion Gates

Complete the product-evidence sequence in this order:

1. retain the canonical manual onboarding block and its opt-in boundary;
2. maintain the implemented normal-user and diagnostic tool profiles;
3. maintain the implemented exact checkout binding and fail-closed freshness;
4. maintain the implemented provider-free positive and rejection probes;
5. maintain the clean-candidate deterministic contracts, summary-free live
   gate, and frozen one|nine pilot gate verified for the one-step correction at
   `8844c21`;
6. maintain the passing configured/onboarded paired-evaluation preflight so the
   implemented runner continues to prove the reviewed normal-profile
   installation and its exact integration identities against the candidate;
7. maintain the implemented one-step fail-closed context-package entry action
   across MCP instructions, installed onboarding, and tool descriptions, as
   provider-free verified at exact candidate `8844c21`; and
8. retain the consumed `8844c21` configured/onboarded campaign that established
   context-package adoption and a neutral outcome for the selected one|nine
   task; and
9. retain the consumed configured Config.Net campaign at exact candidate
   `b16eee7`, which established full context-package adoption but regressed in
   two treatments; and
10. diagnose the full-task context-package coverage gap provider-free against
    every frozen implementation and test target before any bounded correction
    or separately authorized paid retest; and
11. freeze and clean-candidate verify the implemented focused-query guidance
    correction before requesting separately authorized model spend; and
12. retain the separately consumed `3804028` Config.Net campaign, which passed
    all treatments with one attributable win, zero regressions, and an
    `improved` single-campaign verdict; and
13. retain the independently consumed `64d4052` YoutubeDownloader campaign,
    which preserved full adoption and correctness but regressed median duration
    and token usage on a different frozen C# task.

The bounded one|nine path and configured preflight have passed their clean-
candidate provider-free gates. The two status-first campaigns remain valid but
`insufficient`; the one-step campaign is valid and `neutral` with full adoption,
the `b16eee7` Config.Net campaign is valid and `regressed` with full adoption,
and the separate `3804028` Config.Net campaign is valid and `improved` with one
attributable win. The independent `64d4052` YoutubeDownloader campaign is valid
and `regressed` on efficiency despite full adoption and correctness. The
Config.Net improvement remains positive bounded evidence, but the independent
efficiency regression means no result yet establishes repeatable product
benefit. Do not claim benefit from documentation, static manifests, fixtures,
configured CI, adoption alone, or an MCP process that starts without an
attributable agent-outcome result.
