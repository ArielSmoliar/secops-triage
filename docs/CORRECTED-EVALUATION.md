# Corrected-candidate evaluation — deterministic preparation

Implemented 2026-09-07 after the owner asked to continue from the successful live faulty-candidate investigation. This change adds the corrected-candidate spending scope and verifies it with mocked provider responses. No additional paid calls were made, and existing live-run directories were not opened or migrated during implementation.

## Owner correction and grant scope

`OpenAIPlan` now includes a validated `scenario`: `faulty` (the backward-compatible default) or `corrected`. The stored plan binds that scope to the grant. The existing provider, token limits, reservation calculation, expiry checks, and no-retry behavior remain unchanged.

A faulty grant still requires a fresh faulty run. A corrected grant requires `candidate_replaced`, the corrected seed revision, and the exact carried regression test plus patch history. The existing owner-only `replace_candidate` transition establishes that state. A fresh corrected seed without the generated regression is insufficient. The model cannot select the corrected application or authorize spending.

Each grant remains single-use and bound to one initial digest and one session. Uniqueness is now per `(run_id, initial_digest)`, allowing the same run to receive a separate owner-authorized grant after correction changes its digest. Only one issued or claimed grant may exist per run. An outstanding prior grant must be explicitly revoked before a different-digest grant can be issued. Closed/revoked grants cannot be replayed or reissued for the same digest. A stopped corrected attempt does not grant an automatic retry.

The proposed next test uses `OpenAIPlan(scenario="corrected", model_calls=4, budget_microusd=1_700_000)`: at most four model requests, an **additional $1.70 ceiling**, and a maximum reservation of $1.689232. This is new spending authority beyond the earlier faulty-investigation scope; it has not been authorized by the implementation request.

## Historical records and migration

The spend layer now has its own `inference_schema` version 2; core SQLite `user_version` remains 1. Under the store lock, a legacy database is upgraded in one transaction: rename the two original spend tables, create the new constrained tables, copy every column unchanged, drop the temporary old tables, and validate foreign keys before commit. Individual SQL statements are used because `executescript` would implicitly commit.

All grant IDs, session links, plan JSON, actors, timestamps, statuses, request IDs, token counts, estimates, and reservations are preserved. Old plan JSON without a scenario continues to mean `faulty`; it is not rewritten. Unknown usage remains unknown, and no reservation is refunded. Concurrent constructors serialize, and repeated initialization is idempotent. A migration exception or process exit rolls back both schema and data. Unknown schema versions fail closed.

Migration refuses databases with running legacy orchestration sessions. Finish an active worker or finalize an abandoned session through the existing supervised recovery procedure before upgrading; never migrate around a live worker. The historical paid stores are retained at their original implementation version and were not modified by this work.

Backend identity includes these source changes, so an old live run is not reusable under this new implementation merely because its ledger can migrate. The proposed corrected-only paid test will prepare a **fresh** faulty run through zero-cost offline orchestration, use the existing owner correction transition to carry its regression forward, and then invoke only the corrected investigation through OpenAI. This separates deterministic fixture preparation from the paid behavior being evaluated.

## Verified behavior

The integration test first completes a mocked OpenAI faulty investigation, preserving its grant and request rows. After owner correction, a new corrected grant drives the real Strands SDK and actual isolated fixture workers through inspection, baseline/regression execution, and the boundary probe. Four model turns and three tools collect fresh passing evidence for all four required checks at the corrected digest. The generated test remains present. The result is ready for human approval, with zero approvals or promotions. The prior grant's complete read result remains equal before and after correction.

Failure tests reject the wrong scenario, wrong owner, missing owner correction, missing carried test, duplicate/concurrent grant issuance, old-grant replay, and an outstanding prior grant. A model claiming readiness after inspection and baseline checks alone cannot waive the missing current boundary check; the packet remains not ready and approval is rejected.

Migration tests preserve every historical field and uncertain reservation, check foreign keys and schema versions, inject a failure midway through DDL, terminate a separate process inside the migration transaction, and race concurrent initializers. Existing tests continue to cover credentials, TLS, transport limits, run isolation, stale approval, promotion replay, worker timeouts, and spend recovery.

## Next gate and remaining limits

Review the validation record, then obtain explicit authorization for the additional four-request/$1.70 corrected-only test. Its expected outcome is readiness with the carried regression passing; it must stop before candidate approval or promotion. No request should be sent merely because a key exists or the plan is valid.

A single corrected live success would still not establish reliability. Repeated-model evaluations, richer explanation coverage, public authentication, multi-host execution, UI, AWS resources, AgentCore, and submission work remain outside this change.
