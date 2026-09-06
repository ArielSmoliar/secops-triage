# OpenAI API preparation

The owner selected the direct OpenAI API on 2026-09-06. This selects a provider; it does not authorize paid inference. A grant-gated live transport and spend ledger are now implemented; see `docs/OPENAI-TRANSPORT.md`. No live attempt is authorized by this document. No OpenAI SDK/client is constructed, dependency added, account endpoint queried, or key persisted by this preparation step.

## Proposed first test

Use the pinned `gpt-4.1-mini-2025-04-14` snapshot for one synthetic faulty-candidate investigation, with at most eight model requests and 2,048 output tokens per request. This is a narrow tool-selection task; the documented instruction-following and function-calling support fit it. Model quality and account access remain unverified. The corrected-candidate investigation and repeated reliability evaluations are separate paid-test scopes.

The [official model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini), checked 2026-09-06, documents the snapshot, a 1,047,576-token context window, and standard text rates of $0.40 per million input tokens and $1.60 per million output tokens. No cache discount is assumed.

The proposed ceiling is **$3.50 USD**. The conservative reservation is **$0.422308 per request**, or **$3.378464 for eight requests**. The calculation reserves the entire documented context window plus the configured output allowance, rounding each request upward to integer microdollars. It intentionally overestimates the shared context window and does not mistake the offline byte cap for an exact token count. This is a planning bound at the recorded text rates, not measured usage or a provider account billing limit; the implemented reservation enforcement is documented in `docs/OPENAI-TRANSPORT.md`. Taxes and unrelated account activity are outside the calculation.

## Run the local preflight

```sh
.venv/bin/python -B -m migration_proof.agent.openai_preflight
```

Expected exit status: **2**, because live execution remains blocked. The JSON reports the plan, pricing freshness, key presence, and unresolved gates. Even with a key, it always reports `execution_enabled: false`, `paid_calls_authorized: false`, and `account_access_verified: false`.

The preflight reads only whether `OPENAI_API_KEY` is nonempty. Configure a project-scoped API key through a local secret mechanism when the live transport is ready; do not put it in Git, command arguments, or chat. Key presence does not validate credentials, billing, or model access. No AWS configuration is needed for this local provider route. Deployment choices remain open.

A price check older than seven days, or dated in the future, requires re-verification. Model identity, prices, endpoint choices, and authorization cannot be supplied through the plan. Ambient provider endpoint overrides do not affect this no-network check. The implemented transport independently fixes the OpenAI endpoint and ignores ambient endpoint overrides.

## Remaining paid-test gate

The transport and durable spend ledger are implemented and tested with fake provider responses; see `docs/OPENAI-TRANSPORT.md`. The preflight now reports both components present. It remains a no-network planning command, cannot issue a grant, and always exits 2. Account access and paid-call authorization remain unverified.

After reviewing the implementation and tests, obtain explicit authorization for the concrete $3.50 test and supply a locally configured project key before creating the owner grant and making a request. Recheck prices if the freshness window has expired. No corrected-candidate or repeated reliability tests are included in this initial scope.

Offline sessions continue to reject live providers. The offline `Limits` contract retains its zero-cost compatibility field; live sessions use a separate integer spend ledger and return no zero-dollar billing claim.
