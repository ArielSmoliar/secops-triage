# Durable unresolved handoffs

The trusted host can now save an analyst's unresolved work without selecting close or escalate. This implements the persistence gap found in the independent plan and Impeccable flow reviews. No browser control or analyst study is included.

## Host API

After collecting an immutable packet, the host supplies the existing run capability and the analyst's actual input:

```python
handoff_id = store.save_handoff(
    run_id, token, packet['packet_hash'],
    actor=actor,
    reason=reason,
    missing_context=missing_context,
    next_action=next_action,
    request_id=request_id,
)
handoffs = store.status(run_id, token)['handoffs']
```

Actor, reason, missing context and next action are required bounded text. The returned ID identifies a saved unresolved handoff, not a final decision. No handoff is created automatically from a model recommendation or an instruction to continue development. This API is absent from the four agent tools.

## Persistence and revisions

Each handoff has an immutable SHA-256 artifact with its ID, request ID, run, packet hash, actor, reason, missing context, next action and timestamp. SQLite stores the artifact reference and current/history flag. A new handoff for the same run supersedes the old one without editing its content. Repeating an identical request returns the original ID; changed content under the same key is rejected.

A new source incident revision marks older handoffs historical in the same transaction that updates the incident head. Saving against a superseded revision, mismatched packet or changed engine is rejected. A final close/escalate review marks handoffs non-current atomically with the final decision. Replaying the original handoff request after a final review returns its historical ID but does not reopen it. New handoffs after final review are rejected.

Saving does not change the packet's recommendation, evidence or collection status, and does not transition the run to reviewed. A packet whose checks completed can still have an unresolved analyst handoff. Consumers must display the current handoff separately from collection status. A current handoff means this is the latest unresolved note; it is not evidence of truth or completion.

## Migration and crash behavior

SecOps SQLite schema version 2 adds the handoffs table. Versions 0 and 1 upgrade with the schema and version stamp in one transaction; unknown versions are rejected. Failed migration rolls back. Existing records and artifacts are preserved. Older application versions must not open a v2 store. Historical live stores were not opened or migrated during this increment.

The source-engine identity changes with store.py, so new work requires a fresh import. Do not alter old engine hashes to make a run writable. Existing saved reports and historical artifacts remain preserved.

Artifact publication precedes the SQLite save. A crash before the transaction commits can leave an unreferenced immutable artifact; it cannot replace the previous current handoff or manufacture a successful save. A retry uses the same request identity and completes once. No automatic artifact deletion or retry occurs. Database and artifacts remain a trusted local-host storage design, not an adversarial database protection scheme.

## Verification and limits

Tests cover restart/readback, no final review or upstream mutation, unchanged packet, four-tool registry, concurrent replay, changed payload, history replacement, new incident revision, final review, cross-owner/run keys, missing packet, invalid fields, changed engine, corrupted artifact, actual subprocess termination before commit and atomic migration failure. Test records explicitly use a test analyst and are not user research observations.

The local actor string is an attribution supplied by a trusted host, not authenticated workforce identity. There is no automatic notification, task assignment, reminder, SIEM write or handoff delivery to another person. UI input escaping and the save/reload interaction still require implementation and browser tests. The observation, source-quality and model-evaluation gates remain open.

Validation: the full suite passed 202 tests in 62.751 seconds. The final handoff suite passed 11 tests in 0.277 seconds, including one added after independent review to exercise rollback after retirement but before a replacement insert. See outputs/secops-handoff-store-validation.json. No runtime source changed after the full-suite launch.
