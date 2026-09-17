# Software engineering methodology

## Purpose

This methodology records CodeMesh decisions and evidence boundaries that a
capable coding agent cannot infer reliably from general software-engineering
knowledge. It assumes the agent already knows how to inspect repositories,
design and edit code, debug failures, write tests, review diffs, and document
ordinary changes.

Do not add guidance merely to restate those built-in capabilities. Add a
reusable control only when it changes a material decision because it encodes:

- a project-specific engineering choice;
- a non-obvious safety, authority, privacy, or external-side-effect boundary;
- a fragile procedure whose order or stopping condition is essential;
- a contract with an external system or tool; or
- a repeated, evidenced failure that narrower repository guidance cannot fix.

Generic language or framework advice, routine coding and testing practices,
speculative edge cases, and universal planner/coder/reviewer role chains do not
belong in durable CodeMesh guidance.

## Evidence and claims

Use the narrowest truthful state when describing work:

1. **Proposed**: designed or planned but not implemented.
2. **Implemented**: present in the inspected source or artifact.
3. **Automatically verified**: supported by named passing automated checks.
4. **Inspected**: supported by a bounded manual review of identified evidence.
5. **Locally accepted**: exercised successfully in the declared local setting.
6. **Externally accepted**: accepted by the named host, attended process, or
   external environment.
7. **Released**: published as an immutable identified version or artifact.
8. **Deployed**: installed in the identified target environment.
9. **Production-authorized**: separately approved for production or live use.

One state never implies a later state. Record the exact commit, artifact,
environment, command, result, and limitation needed to support consequential
claims. A workflow definition, configured tool, fixture, or historical result
is not evidence that the current candidate passed.

CodeMesh product-benefit claims also require the evidence classifications and
comparability rules in
[MCP Effectiveness Evaluation](../evaluation/mcp-effectiveness.md). A fixture,
assisted run, stale index, dirty checkout, non-adopted treatment, or historical
report supports only its explicitly bounded claim.

## Authority boundaries

Treat authority as scoped to the requested action:

- analysis, explanation, diagnosis, and review are read-only unless the request
  also authorizes a change;
- implementation authorizes scoped repository-local edits and proportionate
  local verification, not unrelated cleanup or external mutation;
- a requested commit authorizes focused local staging and commit creation, not
  history rewriting or publication; and
- push, tag, release, publication, deployment, migration, external spend,
  production-data mutation, and live side effects each require their own
  authority and controlling procedure.

Use dry-run, read-only, isolated, or disposable inputs before a higher-risk
operation when the repository provides that path. Stop at the first unresolved
authority or evidence gate rather than silently lowering the standard.

## Where guidance belongs

Place each control at the narrowest durable layer:

- **Principle**: a stable project decision in this methodology or the shared
  engineering standards.
- **Skill**: a focused, reusable procedure with a discriminating trigger,
  explicit outcome, and non-obvious guidance.
- **Workflow or runbook**: an ordered project goal with prerequisites,
  checkpoints, stopping conditions, and authority gates.
- **Agent role**: an optional context, permission, or responsibility boundary
  for genuinely independent delegated work.
- **Command index**: supported invocations in [`COMMANDS.md`](../../COMMANDS.md);
  presence never grants authority to run a high-risk command.
- **Project `AGENTS.md` and canonical documentation**: repository facts,
  architecture, domain invariants, read order, safety rules, and release gates.

Keep normative detail in one canonical location and link to it elsewhere.

## Reusable-control admission

Before adding or expanding a principle, skill, agent, hook, plugin, or optional
tool, record answers to these questions:

1. What material decision will the control change?
2. What repository evidence, repeated failure, or external contract requires
   it?
3. Why is existing agent capability or narrower project guidance insufficient?
4. What is the narrow trigger and observable success criterion?
5. What overlap, context cost, permissions, and failure modes does it add?
6. When should it be revised, disabled, or removed?

If the answers do not demonstrate incremental value, do not add the control.
Prefer instructions over scripts unless deterministic execution is necessary,
and prefer a project-local rule over a cross-project rule when the evidence is
project-specific.

This test is why CodeMesh does not automatically adopt overlapping code-graph
tools, generic agent roles, hooks, model providers, or release automation from
an external baseline. Each needs independent value and the appropriate
authority before activation.

## Applying the methodology

Classify the request before selecting checks or changing state. Read-only
analysis, diagnosis, implementation, acceptance, release, and live operations
have different authority and evidence requirements. Use
[`COMMANDS.md`](../../COMMANDS.md), [Testing](../evaluation/testing.md), and the
task's canonical workflow for the actual checks; this document defines shared
decision boundaries rather than duplicating procedures.
