# Decision: Enforce agent campaign tokens through a loopback Responses proxy

- Status: accepted
- Date: 2026-09-01
- Owners: CodeMesh maintainers

## Context

Paired agent campaigns need a hard reported-token ceiling across every model
request and any internal retry activity. Codex JSONL reports cumulative usage
only after a turn completes, while the Responses `max_output_tokens` parameter
limits generated visible and reasoning tokens but not submitted input. A
post-run usage audit can detect an overrun but cannot prevent one.

Codex supports custom Responses providers and independent request and SSE retry
limits. The Responses API also exposes an input-token endpoint that can count a
submitted request before generation. These interfaces allow enforcement without
changing prompts, task ordering, MCP configuration, or grading.

The controlling external interfaces are the
[Responses create method](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
[input-token count method](https://developers.openai.com/api/reference/typescript/resources/responses/subresources/input_tokens),
and [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Decision

- Keep `--runner codex` as the default, truthful fail-closed runner for agent
  campaigns.
- Add explicit `--runner capped-codex`, which starts an ephemeral proxy bound to
  a random loopback port for each agent execution.
- Give Codex a random per-execution proxy bearer token. Keep the upstream OpenAI
  credential inside the proxy process path and exclude it from logs and reports.
- Bind the selected model to its exact bundled entry from the selected Codex
  executable through an ephemeral `model_catalog_json`, preserving its shell and
  MCP tool contract without forwarding remote model discovery.
- Before each `/responses` request, call `/responses/input_tokens` with every
  supported input-bearing field, reserve counted input plus the admitted
  worst-case reported charge for the generated-token envelope, and clamp
  `max_output_tokens` to the smaller of the remaining allowance and the
  selected model's documented 128,000-token output maximum. Because Codex
  reports `output_tokens` inclusive of reasoning while the committed accounting
  adds `reasoning_output_tokens`, reserve twice the admitted generated envelope.
- Configure the custom Codex provider with request and SSE retries set to zero.
  Reject duplicate or declared retry activity as defense in depth.
- Support only foreground Responses calls with local function/custom tools.
  Reject background operation, automatic compaction, prompt templates or
  unreviewed request parameters outside the input-counting contract, other
  provider endpoints, and provider-hosted cost-bearing tools.
- Settle a reservation only from a completed response with valid usage that
  agrees with the prior input count. Retain the complete reservation after an
  interrupted, missing-usage, or otherwise unknown response.
- Require cumulative proxy usage to match Codex final usage before accepting
  completion. Emit only a sanitized hard-cap ledger in evaluation reports.

## Consequences

- A complete invocation cannot admit requests whose worst-case reported-token
  charge exceeds its assigned allowance, including multiple internal model
  turns.
- Interrupted or ambiguous calls can conservatively consume unused allowance
  and make a campaign incomplete. The evaluator does not top up or retry them.
- The capped runner requires the OpenAI Responses and input-token endpoints and
  does not support local model providers.
- Input-token counting adds one non-generating API request before each model
  request. Its latency is runner overhead and must not be attributed to CodeMesh
  retrieval.
- The runner enforces token accounting only. It does not grant model-spend,
  release, deployment, publication, or external-system authority.

## Verification

- Deterministic tests cover exact-boundary admission, multiple requests,
  generated-token clamping, accounting disagreement, missing usage, interrupted
  streams with retained reservations, backend failure, retry rejection, zero
  configured retries, unsupported cost activity, and secret non-disclosure.
- Configured provider-free preflight verifies runner capability before model
  access while preserving the existing positive and wrong-checkout probes.
- A model-backed campaign is accepted only when every execution ledger is
  complete and agrees with Codex final cumulative usage.
