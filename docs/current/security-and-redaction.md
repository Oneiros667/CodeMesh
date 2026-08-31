# Security And Redaction

Document type: current security reference

CodeMesh is designed to expose repository context to AI agents. That makes secret handling and sensitive-file behavior part of the product surface, not only an implementation detail.

## Current Agent Rules

- Do not print `.env` contents.
- Do not print credentials, tokens, private keys, certificates, connection strings, or local secrets.
- Report secret-related issues using variable names and redacted values only.
- Treat local configuration as private unless the user explicitly asks for a safe summary.

## Files That Need Care

Common sensitive inputs include:

- `.env` and `.env.*`
- private keys and certificates
- cloud credential files
- local Docker, Kubernetes, and Helm secret values
- connection strings
- API tokens and personal access tokens
- service account material
- database dumps and backups

## Implemented Behavior And Remaining Gaps

The current local-first ingestion path redacts sensitive-looking values before content is persisted, embedded, summarized, or returned through Agent Access.

Current behavior:

- A shared repository path policy excludes generated, cache, virtual-environment, smoke, and temporary directories before supported parsers enumerate files.
- Private key blocks are replaced with `<redacted>`.
- Environment-style assignments with names containing `SECRET`, `PASSWORD`, `PASSWD`, `TOKEN`, `API_KEY`, `PRIVATE_KEY`, or `CONNECTION_STRING` are redacted.
- JSON string values with sensitive-looking key names are redacted.
- C# string assignments with sensitive-looking variable names are redacted.
- Connection string password fragments such as `Password=...` or `Pwd=...` are redacted.
- Redacted content receives a new content hash, and graph nodes are remapped to that redacted content hash before store writes, embeddings, and summaries.
- Ingestion emits diagnostic `CMSEC001` when redaction changes one or more content items.

The following behavior remains planned in [Next Steps](../planning/next-steps.md):

- Configurable allowlists and denylists for ingestion.
- Default exclusion for known secret files in addition to the current generated-directory exclusions.
- Broader tests for additional secret formats and false-positive control.

Shared multi-user storage adds tenant isolation, path privacy, authorization,
retention, and verified-deletion requirements. Those requirements are proposed
in [Repository Identity and Snapshot Retention](../planning/repository-identity-and-snapshot-retention.md);
they are not current shared-service behavior.

## Hosted CodeQL Triage

The latest hosted CodeQL run succeeded for published commit `8e9c0da`, but 39
alerts remain open on that commit. A read-only review groups them as:

- 13 path findings at the trusted evaluation-suite boundary that warrant safe
  identifier validation and setup-patch containment;
- 3 command findings at intentional local argv execution boundaries, with no
  shell interpolation but an explicit suite/executable trust requirement;
- 1 reflective-XSS finding that appears escaped in current call sites but needs
  adversarial route tests before dismissal; and
- 22 explicit operator-selected or internally controlled path findings that
  need contract-by-contract review rather than blanket dismissal.

No alerts were dismissed and no security-clean claim is supported. The hosted
scan covers remote `8e9c0da`, not unpublished local changes. Exact alert numbers,
classification, and recommended order are retained in the
[CodeQL triage record](../evaluation/evidence/codeql-triage-8e9c0da.json).

## Redaction Principles

- Preserve enough structure for useful context.
- Remove or mask the sensitive value.
- Prefer stable placeholders such as `<redacted>` over invented replacement values.
- Avoid storing raw secret values in graph, content, vector, or summary stores.
- Avoid sending secret values to embedding or summary providers.

## Safe Examples

Safe:

```text
CODEMESH_NEO4J_URI is configured.
CODEMESH_NEO4J_AUTH is present but redacted.
```

Unsafe:

```text
CODEMESH_NEO4J_AUTH=actual-user/actual-password
```

## Future Implementation Notes

Secret redaction should run before content persistence, embedding generation, summary generation, and MCP response formatting. Redaction should be deterministic enough to test, but conservative enough to avoid exposing questionable values.
