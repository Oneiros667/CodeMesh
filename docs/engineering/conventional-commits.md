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

The checker allows merge and revert commits produced by Git workflows. It does
not install a hook. Hook adoption requires a separate reviewed decision and
must preserve existing repository tooling.
