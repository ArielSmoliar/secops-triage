# OpenAI API preparation

The owner selected the direct OpenAI API on 2026-09-06. This selects a provider; it does not authorize paid inference. The application still supports only offline execution. No OpenAI SDK/client is constructed, dependency added, account endpoint queried, or key persisted by this preparation step.

## Proposed first test

Use the pinned `gpt-4.1-mini-2025-04-14` snapshot for one synthetic faulty-candidate investigation, with at most eight model requests and 2,048 output tokens per request. This is a narrow tool-selection task; the documented instruction-following and function-calling support fit it. Model quality and account access remain unverified. The corrected-candidate investigation and repeated reliability evaluations are separate paid-test scopes.

The [official model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini), checked 2026-09-06, documents the snapshot, a 1,047,576-token context window, and standard text rates of $0.40 per million input tokens and $1.60 per million output tokens. No cache discount is assumed.

The proposed ceiling is **$3.50 USD**. The conservative reservation is **$0.422308 per request**, or **$3.378464 for eight requests**. The calculation reserves the entire documented context window plus the configured output allowance, rounding each request upward to integer microdollars. It intentionally overestimates the shared context window and does not mistake the offline byte cap for an exact token count. This is a planning bound at the recorded text rates, not measured usage, an account billing limit, or implemented spend enforcement. Taxes and unrelated account activity are outside the calculation.

## Run the local preflight

```sh
.venv/bin/python -B -m migration_proof.agent.openai_preflight
```

Expected exit status: **2**, because live execution remains blocked. The JSON reports the plan, pricing freshness, key presence, and unresolved gates. Even with a key, it always reports `execution_enabled: false`, `paid_calls_authorized: false`, and `account_access_verified: false`.

The preflight reads only whether `OPENAI_API_KEY` is nonempty. Configure a project-scoped API key through a local secret mechanism when the live transport is ready; do not put it in Git, command arguments, or chat. Key presence does not validate credentials, billing, or model access. No AWS configuration is needed for this local provider route. Deployment choices remain open.

A price check older than seven days, or dated in the future, requires re-verification. Model identity, prices, endpoint choices, and authorization cannot be supplied through the plan. Ambient provider endpoint overrides do not affect this no-network check. Runtime enforcement of the intended fixed OpenAI endpoint remains transport work.

## Remaining implementation before a paid test

1. Pin the OpenAI transport dependency and test it with a fake HTTP service/client, including function calls, usage, output limits, malformed responses, and credential redaction.
2. Add owner-only, run-scoped inference grants and a SQLite spend ledger. Reserve before dispatch; preserve uncertain reservations after crashes/timeouts; reject concurrent or replayed attempts beyond the grant. Do not reuse candidate-promotion approval records for spending.
3. Enforce the pinned model, text-only payload, output limit, standard pricing tier, no SDK/HTTP retries, no provider-hosted tools, bounded response consumption, and hard process deadline. Reconcile usage conservatively and stop on missing or contradictory billing metadata.
4. Review the implementation and tests, recheck pricing, and obtain explicit authorization for the concrete $3.50 test before sending any model request. Account/model access is then verified without silently retrying failed inference.
5. Record actual usage, tool sequence, deterministic evidence, and stop reason. Approval and promotion remain outside the four agent tools.

The preflight is deliberately separate from the offline `Limits` contract, which continues to reject every nonzero cost and all live model objects. Existing offline evidence is not live-model evidence.
