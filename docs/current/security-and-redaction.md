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
- Files and directories reached through repository symlinks, junctions, or
  other reparse points are excluded fail closed, including links that would
  traverse to content outside the selected repository root.
- C# solution and project discovery uses the same containment policy. An
  explicitly selected solution or project file is rejected when it is outside
  that policy rather than being opened by MSBuild.
- Known secret files are excluded by default, including `.env` variants,
  credential and secret data files, common private-key and keystore formats,
  Terraform state, and selected local cloud or container credential files.
  Safe environment templates such as `.env.example`, `.env.sample`, and
  `.env.template` remain eligible.
- Repeated `--allow-path <glob>` options restrict ingestion to matching
  repository-relative paths. Repeated `--deny-path <glob>` options add
  exclusions and take precedence over allow patterns.
- Path patterns support `*`, `?`, and `**`, match case-insensitively, and reject
  absolute paths or parent traversal. They are anchored at the repository root:
  use `README.md` for only the root file and `**/README.md` for that basename at
  any depth. Generated/cache exclusions cannot be overridden by an allow
  pattern, and allow patterns cannot opt linked paths back into scope.
- `--include-known-secret-files` explicitly disables only the default known-
  secret-file exclusions. It does not bypass generated/cache exclusions,
  configured deny patterns, value redaction, or repository authorization.
- The normalized filter configuration and path-policy version participate in
  snapshot identity, and watch uses the same effective filter as ingestion.
- Private key blocks are replaced with `<redacted>`.
- Environment-style assignments with names containing `SECRET`, `PASSWORD`, `PASSWD`, `TOKEN`, `API_KEY`, `PRIVATE_KEY`, or `CONNECTION_STRING` are redacted.
- JSON string values with sensitive-looking key names are redacted.
- C# string assignments with sensitive-looking variable names are redacted.
- Connection string password fragments such as `Password=...` or `Pwd=...` are redacted.
- Redacted content receives a new content hash, and graph nodes are remapped to that redacted content hash before store writes, embeddings, and summaries.
- Ingestion emits diagnostic `CMSEC001` when redaction changes one or more content items.

Repository-specific sensitive-file conventions still require reviewed deny
patterns; CodeMesh does not infer every proprietary credential or artifact
name safely.

Example restricted ingestion:

```powershell
dotnet run --project src/CodeMesh.Cli -- ingest `
  --root C:\path\to\repository `
  --allow-path "src/**" `
  --allow-path "tests/**" `
  --deny-path "src/generated/**" `
  --skip-embeddings
```

Shared multi-user storage adds tenant isolation, path privacy, authorization,
retention, and verified-deletion requirements. Those requirements are proposed
in [Repository Identity and Snapshot Retention](../planning/repository-identity-and-snapshot-retention.md);
they are not current shared-service behavior.

### Development feedback sessions

The MCP feedback write surface is disabled unless its process is started with
an exact `development-feedback` profile, repository binding, immutable session
manifest path, and reviewed manifest SHA-256. Startup and every feedback call
recheck the hash, expiry, revocation record, and exact participant binding.
Session activation and revocation use exclusive creation. The manifest allows
at most seven days and applies bounded packet, per-process request, text, and
path limits. The request limit is a runaway-output control, not a cross-process
security quota.

Client packets are created exclusively under the exact bound checkout's
ignored `.codemesh-feedback/` directory. Linked or redirected outboxes,
absolute or traversing paths, secret-looking text, unsupported fields, and
client-supplied session, repository, binding, snapshot, CodeMesh, or
classification identities are rejected. The in-process tool trace stores only
tool names, sequence, success/failure state, and bounded diagnostic codes; it
does not retain arguments or responses.
Accepted snapshot and parser fields are derived from the most recent successful
status or context-package result already handled by that process. Recording a
packet does not initiate another store, provider, or network request.

The `feedback-maintainer` profile reads only outboxes named by the active
manifest. Invalid packets produce bounded diagnostics rather than unsafe raw
content. Its resolution endpoint validates and hashes an in-memory draft; it
cannot write CodeMesh or an approval record. MCP annotations describe these
properties to capable hosts but are not the enforcement boundary. Direct IDE
filesystem access remains governed by host approval policy, repository
instructions, Git controls, and the human decision tied to exact feedback ids
and a resolution-plan hash.

## Local Evaluation And Inspection Boundaries

Evaluation suites are trusted local executable inputs: validation commands run
with the operator's privileges, and the selected Codex executable must be
trusted. Commands use argument arrays without shell interpolation. An explicit
shell executable inside a suite remains an explicit command, so argv handling
does not make an untrusted suite safe to run.

Agent and model suite names and artifact identifiers accept ASCII letters,
digits, underscores, hyphens, and internal dots. The first character must be a
letter, digit, or underscore; trailing dots and Windows device names are
rejected. Identifiers must be unique ignoring case within a suite, including
across the model benchmark's question and change tiers. These restrictions
protect generated artifact paths on both supported path conventions.

Setup patches use forward-slash paths relative to the suite directory. Absolute
paths, parent traversal, Windows drive or stream syntax, missing files, and
symlinks that resolve outside that directory are rejected. The evaluator checks
all suite artifacts before repository preparation or model execution, then
rechecks task destinations when executing them. Generated descendant paths
must resolve inside the selected artifact directory. Raw-trace directories are
created exclusively. These checks do not provide a sandbox against another
process concurrently changing the operator's filesystem.

Explicit CLI input/output paths remain operator-selected. Report finalization
also trusts the selected report's recorded suite path. Internal response and
policy-audit destinations are supplied by the evaluator, never by the model's
answer tool arguments. Raw traces and retained workspaces remain sensitive.

The five local inspection routes escape request and stored text and attributes
and encode repository identifiers in local URLs. Every dynamic link attribute
is HTML-escaped after URL encoding, and the numeric search limit is validated
before store access and escaped when rendered. Adversarial route tests cover
script and element injection, attribute breakout, and JavaScript-like values.
The local UI remains an administrative inspection surface, without a new
shared-service authentication or authorization claim.

Feedback recording rejects symlinked, junction, or redirected outboxes and
creates each packet exclusively. Existing regular files, symlinks, and hardlinks
are preserved. These checks do not claim protection against a hostile process
concurrently replacing directories in the operator's checkout.

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

Local hardening now validates suite names and identifiers, contains setup
patches and generated descendants, tests literal argv execution, and tests all
five UI routes with adversarial values. The remaining explicit path boundaries
have been reviewed individually in the
[local security review](../evaluation/evidence/security-boundary-review-20260905.json).
The original triage above records the hosted findings before this correction.

No alerts were dismissed and no security-clean claim is supported. The hosted
scan covers remote `8e9c0da`, not unpublished local changes. Exact alert numbers,
classification, and recommended order are retained in the
[CodeQL triage record](../evaluation/evidence/codeql-triage-8e9c0da.json).

## Local CodeQL Verification

The [retained local review](../evaluation/evidence/local-codeql-review-b73e19a.json)
uses CodeQL CLI `2.26.4`, Python queries `1.8.9`, and C# queries `1.9.2`, with
pinned `security-extended` suites. Python candidate `b73e19a` has zero findings
under the default threat model and 61 under default plus local inputs (58 path,
3 command). The C# source, unchanged since scanned `e0beba9`, has zero default
findings and 192 with local inputs (189 path, 3 command). All reported C# flows
originate in test-harness temporary or configured sample paths. Every local
result is retained with its location and reviewed boundary; none is dismissed.

The same local-input configuration reproduces 39 Python results on published
`8e9c0da`. Before the HTML correction, local `e0beba9` has 62; afterward the
reflective-XSS finding is absent. The larger current count also includes newer
local CLI, installation, feedback, and path-validation surfaces. Counts alone
do not measure exploitability or establish a security improvement.

Use local scans when unpublished security changes need review or an exact
release candidate lacks current hosted evidence. Scan a clean isolated
checkout without private archives or environment files. Pin the official CLI
and query packs, retain checksums, and use absolute suite paths when packs were
downloaded into a private custom directory. C# extraction must trace the full
solution build after locked restore. The exercised command shapes are:

```powershell
codeql database create <python-db> --language=python --build-mode=none --source-root=<clean-checkout> --threads=2 --ram=2048
codeql database create <csharp-db> --language=csharp --source-root=<clean-checkout> --command="dotnet build CodeMesh.sln --no-restore --no-incremental -p:UseSharedCompilation=false -nodeReuse:false" --threads=2 --ram=2048
codeql database analyze <db> <absolute-pinned-security-extended.qls> --format=sarifv2.1.0 --output=<new-private-default.sarif> --no-sarif-add-file-contents --threads=2 --ram=2048 --rerun
codeql database analyze <db> <absolute-pinned-security-extended.qls> --format=sarifv2.1.0 --output=<new-private-local.sarif> --no-sarif-add-file-contents --threads=2 --ram=2048 --threat-model=local --rerun
```

Keep default and local-input results separate. The first attempt to add the
local threat model reused default-model BQRS results; those two SARIF files are
retained but invalid for local-threat claims. `--rerun` forces evaluation when
changing the model. Check extraction coverage, query identities, invocation
errors, and findings before accepting a result. Private SARIF and databases
may contain source paths and data-flow context; do not upload them implicitly.
Revisit this local procedure when equivalent exact-candidate hosted evidence
is available, and reverify cache behavior after tool changes.

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
