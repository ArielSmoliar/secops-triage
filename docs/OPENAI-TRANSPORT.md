# Bounded OpenAI transport and spend ledger

Implemented 2026-09-06 after the owner selected OpenAI API and asked to continue. All verification uses fake OpenAI responses; no paid calls or real inference grants were created outside temporary tests. Live quality, account access, and billing remain unverified.

## Execution and authority

`runner.run_openai(store, run_id, owner_token, grant_id, api_key=...)` is the supervised backend entrypoint. It requires a separately issued `SpendLedger.authorize` grant. Only a fresh `faulty` candidate is eligible, and a run can receive exactly one grant, even after expiry, revocation, or failure. The grant binds owner action, actor, initial digest, pinned model, typed plan, and expiry (default ten minutes, maximum fifteen). A grant is claimed exactly once by one orchestration session. Candidate changes before claim fail closed. The agent's allowlisted test patch can derive a new digest within that same session.

Grant issuance is a spend-bearing owner authorization and must only be invoked after explicit permission for the concrete paid test. It is never included in an agent tool registry. The four existing tools, human candidate correction, readiness gates, promotion approval, and promotion receipt boundaries remain intact. An inference grant does not approve a candidate.

The runner shares the existing per-run lock, isolated child, process-group supervision, and recovery path. It caps the proposed attempt at eight model requests, eight tool requests, and 120 seconds. The child receives owner token and API key through stdin; neither appears in argv, inherited environment, model context, database, or returned results. Ambient OpenAI/AWS configuration and proxies are not forwarded. There is no credential lookup inside the model. Use a local project-scoped key when the paid test is authorized; never paste it into chat or Git.

## Transport

A custom provider implements the pinned Strands 1.54.0 `Model` interface. Its small HTTPS transport uses Python's standard library, so no new OpenAI SDK or transitive dependency is needed. The existing backend identity includes these sources and the exact runtime version. The locked Strands graph is unchanged.

The provider makes one non-streaming POST to `https://api.openai.com/v1/chat/completions`. The [official Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) defines the function-call message shape, output cap, usage fields, and standard service tier. The request fixes the model to `gpt-4.1-mini-2025-04-14`, text modality, one choice, standard tier, temperature zero, `store=false`, no parallel tool calls, and the plan's output cap (maximum 2,048). There are exactly four local function definitions and no provider-hosted tools. Non-text messages and extra tools are rejected.

No redirects, retries, proxy discovery, custom endpoint, or SDK retry mechanism exists. Socket operations time out after twenty seconds; the supervising process imposes the total deadline. The request body is capped at 256 KiB, the HTTP response body at 64 KiB, and accepted model content at 16 KiB. Server errors and exception text are discarded. TLS uses the explicitly pinned certifi CA bundle with hostname and certificate verification enabled; see `docs/OPENAI-FIRST-ATTEMPT.md` for the missing-system-roots regression.

Responses must identify the exact snapshot and standard tier, supply exactly one choice, and finish with one function call or final text. Truncation, refusal, mixed prose/tool output, malformed data, and unsupported response types stop the attempt. The existing guard rejects unknown names, cross-run input, invalid fields, stale digests, and unsafe patches before tool execution. Final text still must match the closed explanation vocabulary. The live context includes that vocabulary and the exact allowlisted patch; this tests tool selection and constrained repair, not arbitrary test authorship.

## Cost and crash behavior

SQLite adds `inference_grants` and `inference_requests`; existing historical records are retained. Each request gets a unique durable reservation before dispatch. Transactions and the store lock serialize concurrent callers. Another request is forbidden while any prior request is pending or has unknown usage.

The proposed plan remains $3.50 for one attempt. At the documented rates checked 2026-09-06, reserve $0.422308 per request: the entire documented context window at the uncached input price, plus maximum configured output, rounded upward to integer microdollars. Eight reservations total $3.378464. This deliberately exceeds likely fixture usage. Neither successful calls nor failures refund reservation capacity; recorded cheap calls cannot extend the request budget. Prices are rechecked for freshness at grant issuance and every reservation; an age above seven days or a future-dated price record blocks dispatch.

Usage settlement validates integer input, output, and total token counts, their consistency, and model/plan limits. It records a conservative estimate using uncached rates, not an invoice amount. Reported estimates exclude requests with unknown usage; `usage_complete=false` makes that explicit. Reservation totals remain the exposure bound even when usage is missing. The bound assumes the published rates and the provider honoring the requested model, token cap, and standard tier. It excludes taxes, unrelated account activity, and later price changes. Unexpected provider identity/tier stops further requests and preserves uncertainty.

Timeouts, transport errors, cancellations, and malformed usage retain the full reservation. There is no automatic retry or recovery replay. Session finalization closes the grant, marks pending requests unknown, and invalidates stopped-run approval eligibility in the same SQLite transaction. After a process crash, the existing per-run lock must become available before recovery marks the abandoned session stopped. The grant cannot be reclaimed. Owner revocation prevents subsequent dispatches; it cannot undo an already sent request or its possible charge.

The historical `agent_sessions.cost_usd=0` column is retained only for schema compatibility with offline records. Live read results return `cost_usd=null`; live accounting authority is the integer spend ledger returned as `spend` by the runner. Do not interpret the legacy SQL zero or `Limits.max_cost_usd=0` as live billing evidence.

## Verification and next gate

Tests cover the complete seven-request faulty-candidate path through the real Strands SDK and actual localhost fixtures with fake provider responses; all four tools execute, the allowlisted test is added, and the run remains blocked for human correction. Additional tests cover real supervised child execution, key isolation, hard termination of a hung provider, SQLite atomic finalization, process-exit recovery, ownership, cross-run access, concurrent reservations, grant replay, expiry, revocation, stale pricing, candidate changes, malformed usage, request size/modality limits, HTTP failures, redirect refusal, and a model attempting approval.

These tests establish adapter and deterministic control behavior. They do not establish real model reliability or successful access to OpenAI. The next gate is explicit authorization for one attempt capped at $3.50 and a locally configured key. After authorization, create a fresh run and grant, execute once, preserve usage and evidence, and stop on failure. A corrected-candidate paid evaluation requires a separately reviewed scope; this implementation deliberately accepts only fresh faulty candidates.

No UI, AWS provisioning, AgentCore, or submission work is included. The implementation retains the local trusted-backend, POSIX-lock, single-host constraints documented in Phase 2 and Phase 3.

The first explicitly authorized live attempt subsequently stopped before any tool call; usage remains unknown. The certificate diagnosis, fix, and remaining authorization gate are recorded in `docs/OPENAI-FIRST-ATTEMPT.md`.

A separately authorized replacement completed with real OpenAI responses on 2026-09-07. See `docs/OPENAI-LIVE-RESULT.md` for observed behavior, usage, and remaining evaluation limits.

Corrected-candidate grant scope and spend-schema version 2 are now implemented; `docs/CORRECTED-EVALUATION.md` supersedes the original fresh-faulty-only and one-grant-per-run restrictions above. Each grant is still single-use for one run/digest, with explicit owner authority and preserved history. No additional paid evaluation has run yet.
