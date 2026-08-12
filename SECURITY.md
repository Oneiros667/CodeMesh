# Security Policy

CodeMesh indexes repository source and returns selected context to coding
agents. Secret handling, repository boundaries, and provider selection are part
of its security surface.

## Report a vulnerability or exposed secret

Do not open a public issue containing a credential, private source excerpt,
exploit detail, customer identifier, or sensitive path. Use GitHub private
vulnerability reporting if it is enabled for the repository. Otherwise contact
the repository owner through a private channel and include only the minimum
information needed to reproduce the issue.

For a suspected committed secret:

1. Revoke or rotate the credential before treating repository cleanup as
   remediation.
2. Identify affected file paths and commits without copying the secret into
   tickets, chat, or logs.
3. Preserve evidence privately and coordinate any history rewrite with the
   owner. Do not force-push a remediation without explicit approval.

There is not yet a published release or supported-version matrix. Security
reports should identify the commit tested.

## Safe local operation

- Keep `.env`, model caches, database volumes, indexes, evaluation traces, and
  generated source context out of Git.
- Set a unique local Neo4j password before starting Docker Compose. Default host
  port bindings are loopback-only; review them before changing that boundary.
- Use `CODEMESH_MODEL_PROVIDER=none` and leave summary generation disabled for
  the source-local baseline.
- Treat embeddings and generated summaries as copies or derivatives of source
  content. Confirm repository authorization before enabling any network or
  third-party model provider.
- Do not use `--keep-raw-traces` for shareable evaluation evidence. Raw traces
  can contain source, prompts, diffs, and tool responses.

Implemented redaction behavior and its known limitations are documented in
[Security and Redaction](docs/current/security-and-redaction.md).
