# Development-Session MCP Feedback Loop

Document type: completed owner-activated implementation plan

Reviewed: 2026-09-10

Status: implemented and provider-free verified in the current local checkout;
not attended, published, released, deployed, or product-benefit validated.

## Decision

CodeMesh extends its existing local `.codemesh-feedback/` packet workflow
into an explicit development-session MCP loop. Client agents will be able to
record bounded feedback through MCP, and a separate agent working in the
CodeMesh checkout will be able to review that feedback and prepare a proposed
resolution. A human must approve the proposed CodeMesh change before the
maintainer agent edits source.

This completed priority is tracked in [Next Steps](next-steps.md). It extends
the local recorder, validator, and summarizer. The existing `normal` and
`diagnostic` MCP profiles remain unchanged; the new profiles are separate and
fail closed without an exact active session.

The first version is local and same-machine. It reads participating checkout
outboxes directly and does not introduce remote feedback transport, shared
multi-user storage, automatic issue creation, or autonomous CodeMesh changes.

## Goals

1. Make the feedback workflow discoverable and directly usable by client
   agents during an explicitly enabled development session.
2. Preserve trustworthy repository, checkout, snapshot, parser, CodeMesh, and
   validation provenance without asking the client agent to supply identities
   that the server can determine.
3. Let a CodeMesh maintainer agent in VS Code list, inspect, reproduce, and
   prepare a resolution for feedback from session-authorized client checkouts.
4. Require explicit human approval before feedback leads to a CodeMesh source
   or documentation change.
5. Close the loop with an append-only passing recheck that supersedes the exact
   earlier failure.

## Non-Goals And Evidence Boundary

- Feedback does not automatically edit CodeMesh, change ranking, trigger
  ingestion, alter priorities, create external issues, or transmit repository
  material.
- Session activation authorizes only bounded local feedback artifacts. It does
  not authorize a CodeMesh edit, commit, push, pull request, release,
  deployment, provider spend, or external mutation.
- Feedback remains diagnostic product input. A packet, fix, or passing recheck
  is not controlled agent-benefit evidence unless a separately authorized
  evaluation establishes that claim.
- This feature is not the proposed agent outcome-memory system. It does not
  train retrieval, prefer nodes, or retain conversations.
- MCP does not enforce write approval for an IDE agent that already has direct
  filesystem access. The host approval policy, repository instructions, Git
  controls, and explicit human decision remain authoritative for source edits.

## Roles And Trust Boundaries

| Role | Allowed behavior | Prohibited implication |
| --- | --- | --- |
| Human owner or maintainer | Review and activate a bounded session; select feedback for investigation; approve an exact proposed change. | Session activation does not pre-approve every resulting CodeMesh change. |
| Client agent | Use CodeMesh and submit sanitized observations through the development-feedback MCP profile. | Client feedback is not trusted ground truth or implementation authority. |
| Client CodeMesh MCP server | Derive provenance, validate and write an append-only packet inside the bound checkout. | It cannot write outside the feedback outbox or modify CodeMesh source. |
| CodeMesh maintainer MCP server | Read and summarize feedback only from session-allowlisted checkout outboxes; prepare a resolution proposal. | It cannot edit source or assert human approval. |
| CodeMesh maintainer agent in VS Code | Reproduce a report, inspect source and tests, propose a bounded change, and implement only after approval. | A feedback packet alone does not authorize an edit. |

## Explicit Development Session

Feedback tools must not be enabled by a loose environment boolean. The
implementation must use a reviewable, hashed session manifest with schema
`codemesh-development-feedback-session/v1` containing:

- a unique session id, creation time, and expiry;
- the exact CodeMesh checkout root;
- each participating client root, project id, checkout id, and reporter role;
- the allowed client and maintainer MCP profiles and tools;
- local-only transport and provider-free declarations;
- packet, text, path, and request-rate bounds; and
- the SHA-256 of the canonical manifest payload, excluding the hash field
  itself.

The installer must include the manifest path and expected hash in its reviewed
launch plan. MCP startup and every feedback call must fail closed when the
manifest is missing, altered, expired, revoked, or does not authorize the exact
bound checkout. Closing a session must prevent new packets without deleting
prior evidence. Because the reviewed manifest is immutable, early closure must
create a separately validated revocation record rather than rewriting it.

The session lifecycle is exposed under
`codemesh-agent-access feedback session` with `plan`, `activate`, `inspect`,
and `revoke` actions. `plan` produces a reviewable
`codemesh-development-feedback-session-plan/v1` artifact containing the exact
proposed manifest bytes and hashes. `activate` requires the expected plan hash
and creates the immutable session manifest exclusively. `revoke` requires the
expected session hash and creates a separate revocation record exclusively.
Activation must retain the existing reviewed-plan and changed-target
protections. The session preflight must also require the target checkout's
`/.codemesh-feedback/` path to be ignored and local rather than silently
editing tracked ignore rules.

## MCP Profiles

The implemented `normal` profile must remain the default read-only product
surface.

The new profiles are:

- `development-feedback`: the normal client tools plus bounded feedback
  discovery and recording. It exists only for a valid explicit session.
- `feedback-maintainer`: read-only feedback intake and resolution planning for
  the CodeMesh checkout. It scans only roots named by the session manifest.

The installer and runtime probe must validate the exact selected profile and
tool allowlist. A normal installation must not gain write tools merely because
the CodeMesh package supports them.

## Client MCP Tools

### `codemesh_get_feedback_session`

Return the session id, expiry, enabled state, local-only status, allowed
categories, packet limits, and concise instructions describing when feedback
is appropriate. Do not return credentials, environment values, or roots that
the bound client does not need.

### `codemesh_record_feedback`

Accept only the agent's bounded observation:

- task family, issue category, confidence, and validation outcome;
- helpful, incorrect, missed, stale, or ambiguous repository-relative paths;
- an optional bounded fallback reason, minimal reproduction, expected target
  set, and proposed correction; and
- optional exact feedback ids superseded by a passing recheck.

The server, not the client agent, must populate:

- session id and recording time;
- repository root, branch, commit, and dirty state;
- bound project and checkout ids;
- selected snapshot, language set, parser profile, and binding assessment; and
- CodeMesh commit, dirty state, and working-tree-state hash.

The tool must allow setup, binding, and freshness failures to be reported even
when context retrieval was rejected. Claims about returned ranking or content
must retain an accepted snapshot and relevant tool-use provenance. The
development-session classification is `diagnostic`; only the controlled
evaluator may create `controlled-evaluation` records.

Adding the session and MCP-origin fields requires a strict
`codemesh-feedback/v2` packet while preserving validation and summarization of
existing v1 packets. Recording remains append-only and content-addressed.

A successful response returns only the feedback id, repository-relative packet
path, local-only state, and `human_review_required = true`. It must not imply
that CodeMesh accepted the report as correct or scheduled a change.

## Maintainer MCP Tools

### `codemesh_list_feedback`

Return bounded summaries of validated feedback from session-allowlisted roots,
with filters for open/resolved state, category, task family, language, client
role, and feedback id. Preserve invalid-packet diagnostics without returning
unsafe raw file content.

### `codemesh_get_feedback`

Return one validated packet and its derived supersession state by exact
feedback id. Reject ambiguous ids and packets whose claimed root does not match
their allowlisted outbox.

### `codemesh_prepare_feedback_resolution`

Produce a read-only proposed resolution containing the selected feedback ids,
exact provenance, reproducibility state, smallest proposed change, risks,
required source and test investigation, validation plan, and a stable plan
hash. It must not modify CodeMesh, write an approval decision, or describe the
plan as human-approved.

An optional MCP resource such as
`codemesh://development-feedback/open` may support host notifications or
subscriptions. Resource-notification support varies between hosts, so listing
feedback through a tool remains the required portable path.

## Agent Discovery And Onboarding

During an active session, the client profile must advertise feedback through:

1. MCP initialization instructions;
2. feedback tool names, descriptions, and schemas;
3. the generated repository-owned `AGENTS.md` onboarding block; and
4. a concise feedback recommendation when a context package is rejected,
   incomplete, truncated, or contradicted by later source verification.

The instruction must name `codemesh_record_feedback`, state that packets remain
local, and prohibit raw prompts, MCP payloads, source excerpts, secrets,
credentials, and environment values. CodeMesh must not solicit a rating after
every successful call. Passing feedback is primarily a recheck that supersedes
an exact earlier failure.

The CodeMesh repository instructions must tell the maintainer agent to start a
development-feedback task with `codemesh_list_feedback`, investigate read-only,
and wait for explicit human approval tied to the feedback id and proposed plan
before editing.

## Human-In-The-Loop Improvement Flow

1. A human reviews and activates a bounded session for exact client checkouts.
2. A client agent uses CodeMesh and source-verifies consequential results.
3. When verification identifies a missing, stale, incorrect, or unhelpful
   result, the agent records a sanitized packet through MCP.
4. A human asks the CodeMesh maintainer agent to review new feedback, or the
   host presents a non-authorizing notification.
5. The maintainer agent lists and retrieves the exact packet, checks its
   provenance, reproduces it when possible, and prepares a bounded resolution.
6. The human approves, rejects, or defers that exact proposal. An agent-supplied
   `confirm = true` is not evidence of human approval.
7. After approval, the maintainer agent changes only the approved CodeMesh
   scope, updates tests and documentation, runs the required checks, and reports
   the resulting commit and evidence state.
8. The updated CodeMesh candidate is deliberately reconfigured and probed in
   the client checkout. No feedback tool silently restarts MCP or rewrites the
   client's binding.
9. A client agent performs the same validation and records a passing recheck
   with `supersedes_feedback_ids` naming the original failure.
10. The summary derives the original report as resolved; neither packet is
    mutated or deleted.

## Safety Invariants

- Feedback writes stay inside the exact bound checkout's ignored
  `.codemesh-feedback/` directory.
- Linked, redirected, traversing, or non-local outboxes are rejected. Packet
  creation is exclusive and never overwrites an existing regular file,
  symlink, junction, or hardlink target.
- Text and path limits, secret-pattern rejection, repository-relative path
  validation, content ids, and strict schemas remain mandatory.
- Client-supplied repository, binding, snapshot, CodeMesh, session, and
  classification identities are rejected rather than trusted.
- Maintainer reads are restricted to exact session-allowlisted roots; the
  implementation must not search arbitrary parent directories or the whole
  filesystem for outboxes.
- No feedback endpoint invokes a model provider, ingestion, refresh, watch,
  repository deletion, garbage collection, external issue tracker, network
  transport, or source edit.
- Raw prompts, MCP request or response payloads, source excerpts, credentials,
  secret values, and environment values are not retained.
- Session closure and expiry stop new writes but preserve already recorded
  evidence and supersession relationships.

## Selected Implementation Shape

### Runtime composition

`build_server()` will receive a validated session runtime explicitly. The
implementation must not use process-global activation state or infer a session
from an environment boolean. The runtime owns the immutable manifest, its
expected hash, revocation and expiry checks, the exact active binding, and a
small injected clock so expiry behavior is deterministic in tests.
Request-rate bounds are enforced per stdio server process with an injected
monotonic clock. They are misuse and runaway-output controls, not a claim of a
cross-process security quota.

The profile registry must be made explicit before adding tools. In particular,
new feedback tools must not enter the existing `diagnostic` profile merely
because that profile currently includes most registered tools. The profiles
are composed as follows:

| Profile | Binding | Tool surface |
| --- | --- | --- |
| `normal` | One client checkout | The existing four read tools, unchanged. |
| `diagnostic` | Optional | The existing diagnostic tools, unchanged. |
| `development-feedback` | One allowlisted client checkout | The four normal tools plus session discovery and packet recording. |
| `feedback-maintainer` | The allowlisted CodeMesh checkout | The four normal tools plus feedback list, get, and resolution-plan tools. |

The maintainer composition lets the VS Code agent inspect CodeMesh through the
normal source-grounded surface while reviewing feedback. Neither new profile
contains repository deletion or other operator controls.

### Session and installation contracts

Create `codemesh_agent_access/feedback_session.py` for strict session-plan,
manifest, participant, bounds, and revocation models. It owns canonical JSON
hashing, exclusive creation, allowlist resolution, expiry and revocation
validation, and ignored-local-outbox preflight. Paths are resolved before
comparison; containment is never established by string-prefix matching.
The manifest is an envelope containing a payload and the SHA-256 of the
canonical payload. The activation plan separately pins the exact serialized
manifest-file hash, avoiding a self-referential whole-file hash.

The installer contract advances to `codemesh-installation-plan-v2`. Its loader
must continue to validate and apply existing v1 normal plans. V2 adds an
optional session block containing the manifest path and expected SHA-256. The
block is required for either feedback profile and rejected for `normal` and
`diagnostic`. Generated launch arguments pin both values:

```text
--feedback-session <absolute-manifest-path>
--feedback-session-sha256 <expected-hash>
```

This keeps the reviewed session identity visible in the same installation plan
that pins the CodeMesh root, profile, binding, launch command, and expected tool
surface. No command silently updates an already installed target when its
reviewed files have drifted.

### Feedback packet compatibility

Keep the existing `FeedbackPacket` v1 model and CLI behavior unchanged. Add a
strict v2 model and a version-discriminated loader used by validation,
summarization, and maintainer intake. V2 adds:

- the server-derived session id, MCP profile, binding assessment, and recording
  time;
- server-derived repository, checkout, snapshot, parser, and CodeMesh
  provenance;
- a bounded recent-tool trace containing tool name, success or bounded failure
  code, and sequence only; and
- an explicit provenance-availability state for reports made before context
  could be accepted.

The MCP server keeps the recent-tool trace in memory for that one stdio server
process. It never records arguments, responses, prompts, source excerpts, or
environment values. The trace supports investigation but is not proof that a
particular result caused the observation.

Setup, binding, and freshness categories may use a bounded unavailable
provenance state. Ranking, missing-language, missing-relationship, budget, and
validation claims require an accepted snapshot plus the applicable parser and
tool provenance. The development endpoint fixes classification to
`diagnostic`; it rejects any client-supplied identity or classification field.

### Maintainer resolution plan

`codemesh_prepare_feedback_resolution` is a deterministic validator and hasher,
not an autonomous fix generator. The maintainer agent supplies a bounded draft
after source inspection: exact feedback ids, reproduction state, proposed
CodeMesh-relative paths, change summary, risks, and checks. The endpoint
validates those fields against the session and packets, orders them
canonically, and returns an in-memory plan plus stable hash. It does not write
the plan, record approval, or edit a file. Human approval must name the exact
feedback ids and returned plan hash before the IDE agent begins implementation.

### MCP metadata

Use MCP tool annotations as defense-in-depth metadata:

- session discovery and all maintainer tools are read-only;
- feedback recording is write-capable, non-destructive, non-idempotent, and
  local-only; and
- no feedback tool has an open-world or network side effect.

The server remains responsible for enforcing these properties; annotations are
not an authorization boundary.

## Source Change Map

| Path | Planned responsibility |
| --- | --- |
| `agent-access/codemesh_agent_access/feedback_session.py` | New session plan, manifest, revocation, validation, bounds, and runtime authorization. |
| `agent-access/codemesh_agent_access/feedback.py` | Preserve v1; add strict v2 creation, validation, summaries, allowlisted intake, and deterministic resolution-plan hashing. |
| `agent-access/codemesh_agent_access/mcp.py` | Explicit profile composition, session injection, five new tools, annotations, instructions, and bounded recent-tool trace. |
| `agent-access/codemesh_agent_access/installer.py` | Backward-compatible installation-plan v2 session pinning and feedback onboarding. |
| `agent-access/codemesh_agent_access/probe.py` | Separate feedback-profile probes and altered, expired, revoked, and wrong-root rejection checks. |
| `agent-access/codemesh_agent_access/cli.py` | Session lifecycle commands and feedback-session options for MCP, manifest, install, and probe commands. |
| `agent-access/tests/test_feedback_session.py` | Session schemas, hashing, exclusive activation/revocation, bounds, expiry, path, and outbox safety. |
| `agent-access/tests/test_feedback.py` | V1 compatibility, v2 provenance rules, summarization, supersession, allowlisted intake, and resolution plans. |
| `agent-access/tests/test_mcp_contract.py` | Exact profile surfaces, annotations, instructions, runtime authorization, and provenance rejection. |
| `agent-access/tests/test_installer_probe.py` | V1 compatibility, v2 plans, onboarding, launch pinning, probes, and rejection cases. |
| `agent-access/tests/test_cli_output.py` | Stable JSON and exit behavior for the session lifecycle and new profile arguments. |
| `agent-access/tests/test_development_feedback_integration.py` | Disposable-checkout provider-free failure, intake, planning, revocation, and passing-recheck flow. |
| Current documentation named below | Publish only behavior that its work package has implemented and verified. |

## Implementation Work Packages

Each package is independently reviewable and must include its tests and the
documentation for behavior introduced by that package. Later packages depend
on the accepted contracts of earlier packages.

### WP1: Session authority and immutable lifecycle

Dependencies: none.

Implement the new session module and the `feedback session` lifecycle CLI. A
plan consumes an explicit participant configuration, resolves
and validates every checkout, proves each outbox is ignored and local, applies
hard upper bounds, and emits proposed immutable manifest bytes plus hashes.
Activation and revocation use exclusive creation and exact expected hashes.
Inspection returns only sanitized state and reasons such as `active`,
`expired`, `revoked`, `hash_mismatch`, or `wrong_checkout`.

Required tests cover schema strictness, canonical hashes, malformed or duplicate
participants, missing and non-Git roots, symlink and containment attacks,
tracked outboxes, existing destinations, expiry boundaries, revocation races,
and wrong CodeMesh or client bindings. No MCP profile is exposed in this
package.

Exit: a human can create, review, activate, inspect, and revoke a bounded local
session artifact, and all failure modes close without modifying a checkout.

### WP2: Client feedback profile and v2 packets

Dependencies: WP1.

Add the explicit `development-feedback` profile, session discovery, packet
recording, bounded in-process tool trace, and v2 packet support. Refactor the
profile registry so exact `normal` and `diagnostic` tool lists are asserted
independently. Resolve repository and CodeMesh provenance inside the server.
Use bounded diagnostic codes when status is unavailable; never persist raw
exceptions. Preserve the existing direct `feedback record` v1 path for
operator and controlled-evaluation use.

Required tests assert the exact profile tool sets and annotations, absence of
feedback tools from old profiles, missing or invalid session rejection,
client-field overposting rejection, category-specific provenance rules,
sanitization and exclusive creation, v1 validation, mixed v1/v2 summaries, and
append-only passing rechecks.

Exit: an allowlisted client agent can discover and write one valid local v2
packet through MCP, while an ordinary normal client sees precisely the prior
read-only contract.

### WP3: Maintainer intake and approval-ready plans

Dependencies: WP1 and WP2 packet contracts.

Add the `feedback-maintainer` profile and deterministic list, get, and prepare
tools. Intake enumerates only the exact outbox of each client participant in
the manifest, validates every packet before projecting safe output, and reports
bounded invalid-packet diagnostics. Exact-id lookup rejects zero matches,
duplicates, claimed-root mismatch, and packets outside the active session.
By default, list and get expose only v2 packets matching the active session.
An explicit `include_legacy = true` may surface valid v1 packets from an
allowlisted outbox as `legacy_unscoped`; that label must survive into any
resolution plan and prevents treating the packet as session-authenticated.

Resolution preparation accepts only validated session feedback and
CodeMesh-relative proposal paths. It returns reproduction status, unresolved
questions, risks, required tests, evidence limits, and the stable plan hash.
The response always states `human_review_required = true` and
`human_approved = false`.

Required tests cover every filter, stable ordering and pagination, malformed
and adversarial files, id ambiguity, root escape attempts, mixed packet
versions, supersession state, stable plan hashes, invalid proposal paths, and
proof that no source or feedback file changes during list, get, or prepare.

Exit: the CodeMesh VS Code agent can turn allowlisted feedback into an exact,
reviewable, non-authorizing proposal without filesystem mutation.

### WP4: Installer, onboarding, and runtime probes

Dependencies: WP2 and WP3 tool manifests.

Add installation-plan v2, pin the session path and hash into feedback-profile
launches, and render profile-specific MCP instructions and `AGENTS.md`
onboarding. Normal onboarding stays byte-for-byte stable unless a deliberate
separate documentation correction is required. Add separate feedback-profile
runtime probes rather than weakening the existing normal probe.

The client probe verifies the exact profile, tool surface, binding, session
hash, expiry, local-only declaration, instructions, and discovery response
without writing a real packet. The maintainer probe verifies the CodeMesh
binding and participant allowlist without reading outside it. Rejection probes
exercise altered, expired, revoked, wrong-root, wrong-profile, and unexpected
tool-surface cases. Configured-agent evaluation continues to require the exact
`normal` profile.

Required tests cover v1 installation-plan loading, v2 plan/apply drift
protection, missing and extraneous session blocks, generated launch arguments,
onboarding content, exact manifests, both positive probes, and every rejection
case.

Exit: a reviewed installation can activate either feedback role reproducibly,
while old normal installations and configured-agent evaluations retain their
existing contract.

### WP5: Provider-free end-to-end rehearsal and documentation promotion

Dependencies: WP1 through WP4.

Create disposable Git checkouts for CodeMesh and one client repository. Run
the exact installed stdio commands with provider mode disabled. Exercise a
client failure packet, maintainer list/get/prepare, explicit confirmation that
no unapproved CodeMesh edit occurred, session revocation rejection, deliberate
reactivation with the updated candidate, and a passing recheck that supersedes
the original packet. Retain only sanitized deterministic test artifacts.

Update `docs/current/agent-access-contracts.md`,
`docs/current/architecture.md`, `docs/current/security-and-redaction.md`,
`docs/guides/mcp-setup.md`, `docs/guides/agent-quickstart.md`, `COMMANDS.md`,
and `docs/current/project-status.md` to the narrowest verified state. Update
repository agent instructions only with implemented commands and approval
language. Keep product-benefit claims in the evaluation track; this rehearsal
does not satisfy them.

Exit: the complete local workflow is provider-free verified, canonical docs
match the shipped contracts, and the feature can move out of planned status
without claiming attended utility or CodeMesh outcome improvement.

## Commit And Review Sequence

Use one Conventional Commit per accepted work package:

1. `feat: add development feedback session authority`
2. `feat: add client feedback MCP profile`
3. `feat: add feedback maintainer MCP profile`
4. `feat: integrate feedback profiles with installation probes`
5. `docs: verify development feedback workflow`

WP5 test code may accompany the fourth commit when it is needed to verify the
integrated implementation; the fifth commit is the final evidence and
documentation promotion. Do not stack all packages into one review. Each
commit must preserve passing earlier contracts, and no package authorizes push,
release, publication, deployment, or use in an external client checkout.

## Verification Plan

Run the supported commands from `COMMANDS.md`, reporting passed, failed,
skipped, and unavailable checks separately. At minimum:

1. run focused tests for the package being implemented;
2. run the complete Agent Access Python suite, Ruff check, and Ruff format
   check;
3. run the deterministic MCP fixture evaluation to protect the exact normal
   configured-agent surface;
4. run the repository standards and documentation checks for every changed
   commit;
5. run the .NET suite before integrated acceptance because the change affects
   repository identity, binding, serialization, and lifecycle contracts, even
   though the implementation is Python-owned; and
6. run the disposable provider-free end-to-end rehearsal for WP5.

No authenticated provider, remote transport, issue tracker, external model,
or non-disposable client checkout is required for these gates. Any later
attended VS Code exercise is separately authorized evidence and must identify
the exact commits, session manifest hash, installation-plan hash, client
binding, and result.

## Acceptance Gates

The feature is complete only when:

1. the default normal manifest and provider-free normal runtime behavior remain
   unchanged;
2. feedback tools are absent without a valid explicit session and fail closed
   for altered, expired, revoked, or wrong-root manifests;
3. client agents cannot override server-derived provenance or classification;
4. setup, binding, and freshness failures remain reportable without treating
   rejected context as accepted evidence;
5. v1 packets remain valid and v2 session packets pass strict schema, content-id,
   sanitization, containment, and exclusive-creation tests;
6. maintainer tools cannot read a checkout outside the session allowlist;
7. no endpoint can edit CodeMesh, start ingestion, call a provider, transmit
   feedback, create an external issue, or assert human approval;
8. installer planning and runtime probes verify the exact profile, session
   manifest hash, binding, instructions, and tool surface;
9. the provider-free end-to-end failure-to-recheck rehearsal passes and retains
   both append-only packets; and
10. canonical documentation distinguishes planned, implemented, provider-free
    verified, human-approved, and product-benefit evidence states.

Passing deterministic tests proves only the tool and safety contracts. Passing
the local end-to-end rehearsal proves the bounded same-machine workflow. It does
not prove that agents submit useful feedback, that a proposed fix is correct,
or that CodeMesh improves agent outcomes.
