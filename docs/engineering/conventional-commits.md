# Conventional Commit validation

CodeMesh follows Conventional Commits 1.0.0. The included checker validates
ordinary subjects and required breaking-change footers.

Validate a message file:

```bash
python tools/check_conventional_commit.py --message-file .git/COMMIT_EDITMSG
```

Validate a Git range before review or release:

```bash
python tools/check_conventional_commit.py --range origin/main..HEAD
```

Pull requests are squash-merged and their titles become the resulting commit
subjects. Use the same `type(optional-scope): imperative summary` format for a
pull-request title. The hosted pull-request workflow validates the title while
local range validation remains useful for branch review.

The checker allows merge and revert commits produced by Git workflows. It does
not install a hook. Hook adoption requires a separate reviewed decision and
must preserve existing repository tooling.
