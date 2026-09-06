# Phase 3 — Offline Strands integration

Implemented 2026-09-06, continuing from `bfd7a61178704936d5e2997d1dc3b822310e735b` after the owner asked to continue. This completes the offline orchestration portion of Phase 3. It is not a live-model acceptance test and does not authorize paid inference, UI work, AWS provisioning, or submission.

## What executes

The application now constructs a real Strands `Agent` with exactly the four scoped adapters. An explicit custom `OfflineModel` supplies scripted decisions based on real tool results. Strands performs its normal model/tool event loop; the deterministic store executes fixture checks, creates the allowlisted regression test, records evidence, and determines readiness.

This fixture provider is intentionally labeled `offline-fixture-script-v1` / `scripted_offline` in durable records. It is not an LLM, does not establish model judgment quality, and cannot demonstrate live inference reliability. It verifies that the SDK integration and authority boundaries work before a paid provider is enabled.

The SDK is pinned to `strands-agents==1.54.0` in the optional `agent` extra. `uv.lock` pins transitive dependencies and distribution hashes. The pin was verified against [PyPI's official release](https://pypi.org/project/strands-agents/1.54.0/). Integration was checked against the installed pinned source and the official [custom provider interface](https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/) and [hook lifecycle](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/).

## Install and verify

Use the locked environment on macOS or Linux with Python 3.11+:

```sh
uv sync --frozen --extra agent
uv run --frozen --extra agent python -m unittest discover -s tests -v
uv run --frozen --extra agent python -m migration_proof.probe
```

The standard-library core still runs without the extra. Its tests execute normally and Strands tests are explicitly skipped in that mode. A full integration verification must use the extra and have zero skipped tests. Localhost socket permission is needed for real fixture tests. The observed validation environment is Python 3.14/macOS; other supported interpreters/platforms still need CI coverage.

## Local usage

```python
from migration_proof.core.store import Store
from migration_proof.agent.runner import run_offline

store = Store("data/offline-example")
run = store.create_run("faulty")
attempt = run_offline(store, run["run_id"], run["token"])
assert attempt["status"] == "completed"
assert not attempt["summary"]["ready"]
assert attempt["summary"]["assessment"]["provider_mode"] == "scripted_offline"
```

Keep the returned owner token private. `run_offline` returns no owner capability. The faulty scenario inspects, runs baseline checks, detects the tenant-boundary failure, adds the allowlisted regression test, and executes it. It stops blocked. An owner can then explicitly call `replace_candidate` with the corrected seed and run a new offline attempt. Readiness still stops before approval/promotion.

Do not call the internal `execute_session` test seam as a service endpoint. `run_offline` is the supervised entrypoint and enforces the process deadline and per-run lock.

## Deterministic limits and authority

- At most 12 model turns and 8 requested tools per attempt by default; the core's existing 32-call run budget also applies.
- A 60-second default wall deadline, capped at five minutes. Async cancellation is backed by a supervising subprocess deadline that kills only the process group created for that attempt, including fixture worker descendants.
- Context and model response acceptance caps are 128 KiB and 16 KiB. The offline provider emits a single bounded message per step. These checks are not a streaming memory or live token-billing guarantee.
- Cost is exactly zero. Nonzero budgets and non-offline provider objects are rejected. No default provider is constructed; no AWS credentials are looked up.
- Tools run sequentially. Unknown tools, extra/missing fields, cross-run arguments, stale digests, invalid patches, model errors, malformed final output, and exhausted limits stop the attempt and block the run.
- SDK retries, default output callbacks, automatic tool-directory loading, and model-backed context management are disabled. No tools package or external MCP tools are registered.

The model sees run IDs, candidate digests, the fixed task, and redacted tool results. Owner tokens travel to the child only through stdin, never in argv, the model prompt, returned output, or database plaintext. The worker receives a minimal environment without AWS/provider credentials or telemetry configuration; telemetry export is disabled.

Active orchestration has a per-run lock and a unique running-session record. The core refuses owner mutation and previously issued tool capabilities while another orchestration scope is active. A decision packet cannot be approved in the interval between assembly and attempt finalization. This closes a race that a simple SDK wrapper would leave open.

## Persistence, explanations, and recovery

SQLite adds `agent_sessions` and `agent_events` lazily when the integration is used. The tables are additive to core schema version 1; no historical table is rewritten. Each attempt records its initial/final digest, SDK/provider identity, configured limits, durable model/tool counts, zero cost, timestamps, stop reason, and summary artifact hash. Event labels come from a fixed vocabulary; raw tool arguments, model text, exception strings, and SDK transcripts are not persisted.

The provider's final assessment must use a closed recommendation and reason-code vocabulary. Explanatory sentences are rendered from those codes and labeled untrusted. Free text is rejected rather than relying on incomplete secret regexes. A fabricated recommendation cannot satisfy a missing gate.

The assessment artifact is bound to the exact run and current digest. The deterministic decision packet includes its hash, so approval binds the assessment too. Changed or corrupted assessment content invalidates approval. Core and agent source, project configuration, and the dependency lock are included in backend identity; existing runs from a different implementation require fresh verification.

A parent process holds the per-run orchestration lock, and the worker inherits that lock descriptor so a parent crash cannot immediately create a competing attempt. Normal completion finalizes the journal before releasing the lock. A stopped-session record and run invalidation commit atomically, so a crash cannot leave a stopped attempt with an approvable packet. A supervisor timeout records `deadline` and runs core recovery for interrupted tool intents. An abandoned running attempt discovered after lock acquisition is recorded as interrupted and blocks the run; it is not silently replayed. Existing evidence and summaries are preserved.

Attempt completion and acceptance are different: `completed` means the offline investigation finished, while `summary.ready` reports deterministic readiness. A completed faulty investigation remains blocked. A stopped attempt never implies acceptance, and no attempt creates approval or promotion records.

## Review and evidence

Review covered the SDK's actual call/exception lifecycle, registry construction, adapter coercion boundaries, session ownership, capability invalidation during active attempts, packet/assessment binding, cancellation, and durable stop behavior. Tests discovered that SDK error hooks could overwrite a precise limit reason with a generic model error; the guard now preserves the first failure reason.

The suite exercises the real Strands loop without network/provider access for controller tests, and real separate processes plus localhost HTTP for end-to-end corrected/faulty scenarios. It tests all four tools, generated regression execution, owner correction and re-verification, malicious tool names, malformed/extra/cross-run arguments, unsafe patches, forged readiness, context/response/call/deadline limits, provider failures, zero-cost enforcement, secret canaries, approval exclusion, assessment tampering, same-run exclusion, two-run isolation, and process-exit recovery.

Exact results are recorded in `outputs/phase3-validation.txt`.

## Remaining Phase 3 gate

A live provider is deliberately not configurable yet. Completing live-model Phase 3 requires selection of provider/model/region, access confirmation, provider-specific input/output limits and pricing, explicit paid-call authorization and a budget ceiling, and a bounded integration test. The offline fixture's synthetic token metadata is not billing evidence. General generated-test syntax, unrestricted prose, public authentication, and multi-host execution remain separate design work.

The owner subsequently selected direct OpenAI API on 2026-09-06. See `docs/OPENAI-PREFLIGHT.md` for the implemented no-network configuration/budget preflight and remaining live-transport work. Offline execution and its zero-cost contract are unchanged.

The OpenAI transport and owner-only spend ledger are now implemented and tested without paid calls. `docs/OPENAI-TRANSPORT.md` supersedes the historical live-provider gap above. Live quality, account access, and paid-call authorization remain unverified.
