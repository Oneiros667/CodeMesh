# Engineering standards

## Change discipline

- Preserve unrelated user work and keep each change focused and reviewable.
- Prefer reversible, fail-closed behavior for risky operations.
- Separate implementation, automated verification, inspected evidence,
  acceptance, release, deployment, and production authorization.
- Do not make unsupported product-benefit or readiness claims.
- Follow the product priorities and deferred-work boundary in
  [`docs/planning/next-steps.md`](../planning/next-steps.md).

The [Software Engineering Methodology](methodology.md) defines the evidence
states, authority boundaries, guidance placement, and admission test for new
reusable controls. Do not add a hook, skill, agent role, plugin, workflow, or
overlapping repository tool without evidence that it changes a material
CodeMesh decision.

## Commits

Use [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

```text
type(optional-scope): imperative summary
```

Common types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`,
`ci`, and `chore`. Use `!` and a `BREAKING CHANGE:` footer together for an
incompatible public-contract change. Commit only task-related files or hunks.

The repository includes the non-mutating checker listed in
[`COMMANDS.md`](../../COMMANDS.md#repository-standards). It does not install
Git hooks or alter Git configuration. See
[Conventional Commit validation](conventional-commits.md).

## Verification

Use the supported invocations in the repository-level
[`COMMANDS.md`](../../COMMANDS.md) and the risk-scaled selection rules in
[`docs/evaluation/testing.md`](../evaluation/testing.md).

- Run both .NET and Python suites after shared-contract, integration,
  serialization, lifecycle, or end-to-end changes.
- Run the relevant focused suite for changes confined to one implementation
  surface, and state why the other suite was not required.
- Use isolated fixtures and mocked external boundaries where practical.
- Do not exercise live services, paid APIs, external accounts, or private data
  without explicit authorization and appropriate gates.
- Report passed, failed, skipped, and unavailable checks separately.

## Documentation and decisions

- Update documentation with behavior, commands, contracts, setup,
  architecture, or verified status changes.
- Distinguish proposed, implemented, automatically verified, inspected, locally
  accepted, externally accepted, released, deployed, and production-authorized
  states.
- Keep normative guidance in one canonical location and link to it elsewhere.
- Use the [Documentation Hub](../README.md) to preserve the boundary between
  current references, status, execution order, proposals, and historical
  evidence.
- Record consequential implemented architecture choices using
  [`docs/decisions/0000-decision-record-template.md`](../decisions/0000-decision-record-template.md).
- Keep dates, versions, links, measurements, and test claims truthful.

## Releases and versioning

CodeMesh has no published release or supported released-version line.
`VERSION` is the canonical source version; .NET consumes it during build,
Python declarations are checked for agreement, and REST uses the Python export.
Configuration and evidence schemas have independent versions.

[Release Preparation](release-preparation.md) defines the candidate API scope,
compatibility rules, verification and migration gates, and a reviewable release
runbook. The runbook still needs owner acceptance and completed release evidence
before use. Apply [Semantic Versioning 2.0.0](https://semver.org/) to published
versions. Released tags and artifacts must be immutable.

Use the [Release Notes Template](release-notes-template.md) to keep preparation,
tagging, publication, deployment, and stable promotion visibly separate. The
template and a completed implementation do not authorize any of those actions.

## Definition of done

A change is done when:

1. The requested work is complete and scoped.
2. Tests are added or updated where behavior changed.
3. Relevant checks pass, or failures and unavailable checks are reported.
4. Documentation matches implemented and verified behavior.
5. The final diff contains no accidental or unrelated edits.
6. If a commit was requested, it is focused and uses a Conventional Commit.
7. The handoff reports verification, worktree state, and remaining limitations.

Implementation completion never authorizes a tag, release, publication,
deployment, production mutation, external spend, or other live side effect.
