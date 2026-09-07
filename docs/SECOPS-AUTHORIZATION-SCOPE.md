# Structured authorization scope

The closure policy now evaluates explicit authorization assertions instead of treating a matching target ID as sufficient. This addresses the source-scope finding in the independent plan review. It does not establish that an external approver is authentic.

## Required normalized fields

An authorization event retains target_id, actor and reference, and now requires:

| Field | Meaning |
|---|---|
| status | approved, pending or revoked |
| authority_role | identity_owner, security_awareness, endpoint_owner or unknown |
| authority_verified | Boolean assertion supplied by the trusted importer |
| approved_at | UTC time of approval, no later than the source observation |
| valid_from / valid_until | Inclusive UTC interval for permitted activity |
| authorized_event_ids | Explicit known event IDs covered by this authorization |
| authorized_entity_ids | Explicit known entities covered by this authorization |

Unknown fields, wrong types, empty or duplicate scope lists, unknown references and inverted intervals are rejected at import. Source raw text and actor display names do not expand permission. Roles are a narrow demo-policy mapping, not production RBAC: identity_owner for sign-ins, security_awareness for phishing and endpoint_owner for endpoint activity.

## Decision behavior

Authorization must target a retrieved trigger and have approved status, the expected role and a true imported authority assertion. Approval must precede or coincide with every activity it is used to authorize, including earlier related account changes. The trigger and its retrieved related delivery/click or process/connection activity must all appear in the event list, fall within the permitted interval and have their entities covered. Sign-in account changes associated by shared entities are conservatively included; this is not proof of session causality.

A permitted message therefore does not automatically permit a click; a permitted process does not automatically permit a connection. A second trigger cannot inherit the first trigger's authorization. Observations outside the authorization scope cannot justify closure. Invalid or conflicting assertions for a trigger or its related activity block using a nominally valid companion assertion to close; the importer must resolve source history rather than have the engine cherry-pick it.

Replay retrieves authorization and intelligence assertions through their target relationship to scoped activity, even when the assertion is attributed to an additional entity on that activity. Unrelated entities remain excluded, and source/window/template limits still apply.

Rejected authorization appears as a cited observation with the failing checks. With no other suspicious evidence, the packet remains needs_review with no close/escalate recommendation. Sufficient suspicious evidence can still recommend escalation while the invalid authorization remains visible. Complete required collection and absence of suspicious evidence remain separate closure obligations.

## Compatibility and preserved evidence

This changes the normalized authorization contract and source-engine identity. The old three-field authorization shape is rejected, not silently upgraded with permissive defaults. Use a fresh snapshot/import with explicit source assertions for new investigations. Do not fill missing historical authorization fields by assumption.

Historical live stores and artifacts were not opened, migrated or rewritten for this change. Saved reports remain available. Revalidating old packets with this new contract may fail; use their recorded execution build to reproduce historical behavior. Do not change engine hashes or overwrite evidence to bypass that boundary. The SQLite schema itself remains version 2.

The demo fixtures now supply explicit synthetic authorization scope. The walkthrough's authorized-click case lists that click in the structured scope; prose alone does not suffice. No real approval, campaign validation, paid model response or human analyst disposition is claimed.

## Verification and remaining work

New tests cover revoked/pending status, unverified/wrong-role authority, late approval, early/expired activity windows and missing entities across all three families; wrong targets, excluded clicks/connections, inclusive boundaries, a second message, contradictory authorization records, suspicious evidence despite revoked authorization and malformed source fields. Existing fixture outcome tests continue to exercise successful authorization.

The source authority flag, actor, scope and timestamps are still trusted importer assertions. A real connector must establish authoritative provenance, role/approval semantics, revocation history and freshness. Intelligence match detail, independently scored model claims, an observed analyst walkthrough and the browser UI remain separate open gates. This increment strengthens deterministic scope enforcement; it does not validate production incident decisions.

## Independent review and demonstrated failure path

The independent reviewer reproduced three closure gaps during development: approval timing omitted an earlier related activity; related click/connection revocations were ignored; entity-only query filtering could hide a revocation attributed to an additional activity entity. All three were fixed with regression tests. Final independent review found no remaining closure blockers in the reviewed changes; this is not proof against every possible input.

A fresh synthetic execution at data/secops-authorization-scope-checked/run/investigation.md shows the authorized-message case with its click removed from structured permission. It returns needs_review and no close/escalate recommendation even though source prose says simulation clicks are covered. The SIEM remains unchanged. This is deterministic replay, not a new live-model result.

Final verification: 216 tests passed in 63.740 seconds on the reviewed implementation. Thirteen focused authorization tests cover the new scope and review-discovered gaps. See outputs/secops-authorization-validation.json.
