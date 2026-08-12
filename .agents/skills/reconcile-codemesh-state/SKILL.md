---
name: reconcile-codemesh-state
description: Reconcile CodeMesh project status, execution order, evidence, and remaining work against the current Git checkout, source, tests, canonical documentation, and retained artifacts. Use for CodeMesh progress reviews, up-to-date audits, documentation-state reconciliation, roadmap or priority reviews, and requests to identify the next authorized work. Do not use for ordinary implementation discovery, a single bug diagnosis, or executing an already-selected change.
---

# Reconcile CodeMesh State

Produce a current, evidence-bounded view of CodeMesh before updating status
documentation or selecting future work. Treat historical records as leads and
verify consequential conclusions against the current checkout.

## Prerequisites

1. Run `pwd` and `git status --short --branch` in the requested checkout.
2. Record pre-existing modifications and preserve them.
3. Confirm whether the request is read-only or authorizes documentation edits.
4. Do not commit, publish, spend provider budget, run live evaluation, or mutate
   external services without explicit owner authorization.

## Follow The Authority Order

Read only the sources needed for the claim under review, in this order:

1. Read source and tests for implemented behavior.
2. Read `docs/current/agent-access-contracts.md` and
   `docs/current/architecture.md` for current supported surfaces.
3. Read the applicable operating guide, especially
   `docs/evaluation/testing.md`, `docs/evaluation/mcp-effectiveness.md`, or
   `docs/current/security-and-redaction.md`.
4. Read `docs/current/project-status.md` for the reviewed status and evidence
   position.
5. Read `docs/planning/next-steps.md` for future execution order.
6. Use proposals and dated reviews only as planning or historical evidence.

Start from `docs/README.md` when document ownership is unclear. Do not let a
proposal, commit title, old report, or memory override current source and tests.

## Build A Claim Ledger

For every material claim, record:

- the claim and its owning source;
- the current file, symbol, test, command, or artifact that supports it;
- the Git commit, branch, checkout cleanliness, and index identity when
  freshness or evaluation comparability matters;
- the evidence class and maximum defensible conclusion;
- contradictions, missing evidence, and the document that needs correction.

Use these evidence classes without collapsing them:

- planned or proposed;
- implemented but not verified in this review;
- deterministic fixture or unit/contract test passed;
- local integration or live-store check passed;
- comparable live retrieval evidence;
- assisted agent evidence with treatment guidance;
- prompt-parity agent evidence;
- hosted workflow evidence for its declared checks;
- release acceptance;
- deployment or production evidence.

Never infer a higher class from a lower one. In particular, fixtures do not
prove agent usefulness, local workflow configuration does not prove hosted CI,
historical artifacts do not prove current HEAD, and release or production
authority must be explicit.

## Reconcile Current State

1. Compare the working tree and recent relevant history with the source and
   tests that own the behavior.
2. Check whether current contracts and architecture match that behavior.
3. Check whether `docs/current/project-status.md` states the capability and
   reviewed evidence accurately.
4. Check whether `docs/planning/next-steps.md` preserves the current product
   boundary and orders only remaining work.
5. Check retained evidence metadata before reusing measurements. Require the
   relevant tool and target commits, clean-checkout state, fresh index, suite
   mode, provider mode, prompt parity, adoption, and outcome to be explicit.
6. Preserve negative, blocked, skipped, stale, dirty-checkout, and
   non-comparable results. Do not recast them as passes or product failures.
7. Resolve discrepancies by current authority, not by timestamp alone.

When the request asks for the next task, select only the first unblocked item
in `docs/planning/next-steps.md` after reconciling it with current Git state,
implementation, retained evidence, and authorization. Do not activate deferred
summary, parser, SDLC, UI, portability, shared-store, or memory work merely
because a proposal exists.

## Handle Failure And Uncertainty

- Mark missing or unreadable evidence as unavailable.
- Mark stale-index or dirty-checkout evaluation as diagnostic and
  non-comparable unless the canonical evaluator says otherwise.
- Mark provider quota, authentication, and transport failures as blocked or
  unknown, not unsupported.
- Mark conflicting current sources explicitly and identify the highest
  authority that must be resolved.
- Stop before cost-bearing, live, destructive, publication, or external
  operations when authority is absent.
- Avoid exposing raw traces, secrets, credentials, private source, or large
  transcript excerpts.

## Validate The Reconciliation

Before reporting or editing documentation:

1. Recheck each consequential claim against its cited current source.
2. Confirm that proposed status wording does not exceed its evidence class.
3. Confirm that proposed priority wording follows
   `docs/planning/next-steps.md`.
4. If documentation was edited, run the documentation checks in
   `docs/evaluation/testing.md` and inspect the complete diff.
5. Report application suites as skipped when documentation-only work did not
   justify them.

## Report

Lead with the reconciled current position. Include:

- confirmed current capabilities;
- evidence and its claim ceiling;
- contradictions corrected or still open;
- the next authorized item, or the gate blocking it;
- passed, failed, skipped, and unavailable checks separately;
- changed paths, if edits were authorized;
- final worktree state, separating pre-existing work from task changes;
- remaining uncertainty.

Do not claim that documentation alignment, a skill, a custom agent, configured
CI, or a passing fixture establishes CodeMesh product benefit.
