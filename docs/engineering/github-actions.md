# GitHub Actions baseline verification

The read-only workflow validates:

- locked .NET restore, build, tests, and formatting;
- locked Python restore, tests, Ruff, and the deterministic in-process MCP
  fixture suite;
- Git whitespace;
- synchronized application-version declarations;
- Markdown with the repository-pinned `markdownlint-cli2` version;
- local Markdown links;
- publication-safety patterns in Git-visible files;
- read-only workflow policy, immutable action pins, and disabled checkout
  credential persistence; and
- Conventional Commit messages in the pushed range, or the pull-request title.

Normal pushes validate the complete pushed range. Pull requests use the
base-to-head range for source checks and validate the pull-request title as the
future squash-commit subject. A forced push validates only its new head commit
because the replaced history may be unavailable to the runner and is not a
meaningful Conventional Commit comparison. Force pushes require separate owner
approval; a publication rewrite must be audited independently before its
one-time remote replacement.

Every action is pinned to a full immutable commit SHA, checkout credentials are
not persisted, and the workflow receives only `contents: read`. It uses no
repository secrets, model providers, Docker services, live stores, raw traces,
or uploaded artifacts.

A committed workflow is configuration, not evidence that GitHub has run it.
Even after a hosted pass, its results cover only the declared deterministic
checks. They do not establish live-store integration, generalized agent
benefit, release readiness, deployment acceptance, or production fitness. Use
the commands in [`docs/evaluation/testing.md`](../evaluation/testing.md) for additional affected
surfaces.

Review action-version and permission changes as supply-chain changes. Do not
add publication or deployment permissions to this verification workflow.
After a workflow change, run the repository-local policy check listed in
[`COMMANDS.md`](../../COMMANDS.md#repository-standards).
