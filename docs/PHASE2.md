# Phase 2 — Deterministic acceptance backend

Implemented on 2026-09-05, starting from clean `main` at `f3f0eeec3bd689b412529f73359412cd9c995c4f`. The initial four tests passed and the probe reproduced the expected original/faulty/corrected results before editing. The first sandboxed attempt could not bind localhost sockets; rerunning with local socket access passed without changing the fixture.

## Component and authority boundaries

- `core/contracts.py`: frozen typed inputs/outputs with runtime argument validation, fixed checks, and four operational contracts.
- `core/artifacts.py`: canonical UTF-8 JSON, SHA-256, immutable publication, run-scoped paths, symlink rejection, and the narrow unified-diff parser.
- `core/store.py`: SQLite authority, state transitions, invocations, evidence, repairs, decision packets, approvals, promotions/receipts, owner capabilities, and recovery.
- `core/worker.py`: fixed isolated Python subprocess. It executes actual fixture health, baseline HTTP tests, and three original/candidate boundary comparisons. Generated regression tests execute in that subprocess.

`Store.agent_tools` returns an immutable registry containing exactly `inspect_candidate`, `run_baseline_tests`, `compare_tenant_boundary`, and `apply_safe_patch`. Each callable is bound to one run. The typed requests contain no command, arbitrary path, approval, promotion, policy override, or replacement capability. Owner tokens are checked before producing the registry and are not retained in tool closures. Approval, promotion, packet assembly, and corrected-candidate selection are separate backend operations.

This is a trusted local Python backend, not a Python sandbox. A future model receives serialized tool schemas and calls through these adapters; it must never receive the Store object, the owner token, or a Python execution tool. Owner actor strings are local attribution, not externally authenticated identities.

## Records and identity

SQLite stores runs and authoritative accepted digests, transitions, candidate lineage, invocations, evidence, repairs, packets, approvals, and promotions. Promotion rows are both durable execution intents and receipts: `pending` becomes `verified` or `rolled_back`. Final receipts are not modified by replay.

Each run has a random ID and independent accepted-release namespace, even if its candidate digest matches another run. Owner tokens are generated randomly and only their SHA-256 hashes are stored. Evidence reads and owner operations verify run ownership. Paths are constructed from validated IDs and content hashes, never caller-supplied paths.

The source-only fixture is rebuilt as a canonical source bundle rather than a Git worktree or binary. The bundle includes immutable fixture and runner sources, original/candidate revision selectors, generated test source, patch hashes, policy, target, runtime configuration, Python version, tool version, backend source digest, Git commit provenance, application version, and source artifact digest. There is no dependency lockfile because the implementation is standard-library only; its manifest field is explicitly null. Generated files, logs, databases, and working-tree caches are outside this explicit source manifest.

Every derived candidate creates a new content-addressed bundle and lineage record; old sources and evidence remain untouched. A corrected candidate changes only the owner-selected immutable seed revision and carries the generated regression forward. Evidence is never carried forward. Changing the backend implementation or Python runtime requires fresh verification/a new run rather than reuse of old approval.

## Evidence and readiness

Evidence has run/digest binding, invocation/tool identity and version, timestamp, structured result, check status, and SHA-256 body hash. Worker summaries retain command identity, duration, test counts/results, and redacted status/leaked-field evidence. Tokens, raw HTTP headers, worker stderr, and exception messages are not persisted. Outputs are marked untrusted. Unrestricted model explanations are rejected in this phase; a proper text-redaction boundary is required before enabling them.

All four fixed policy gates must pass for the current digest. Missing gates, any failed/contradictory current evidence, malformed worker output, partial health, divergent probe results, timeout, and exhausted tool budget fail closed. The controller independently computes the boundary pass predicate from all three trials. A packet assembled before all gates complete is superseded when new evidence is collected; approved packets and their evidence cannot be rewritten through the API.

The worker gets 15 seconds and an output acceptance cap of 64 KiB per stream. A run gets 32 operational calls. The source runner emits only bounded summaries; the output cap is checked on completion, not a streaming sandbox limit. There is no untrusted arbitrary code execution path.

## Safe repair

The parser accepts a single new-file unified diff under `tests/acceptance/test_tenant_boundary.py`, with the exact audited regression-test body. This is intentionally narrower than the design's maximum of two files/four hunks/200 changed lines. It rejects path traversal, absolute paths, application modifications, binary/credential payloads, alternative Python, and changed assertions. It neither invokes a shell nor accepts general agent-authored Python.

A boundary failure is required before this repair is available. The repair fixes missing test coverage; it does not fix authorization. The faulty derived candidate remains blocked when the generated test executes. Only an owner-selected corrected seed can proceed through all gates to readiness. There is no general source checkout/import or arbitrary patch rollback operation in this phase; immutable predecessor snapshots preserve the pre-patch state.

## Approval and promotion

Approval binds actor, nonce, run, exact candidate digest, exact packet hash, target, fixed action `promote_candidate`, and a finite expiry of at most one hour. SQL uniqueness prevents duplicate approval for the same run/digest/action. Expired or invalidated approvals require a fresh candidate/run and evidence; they cannot be renewed silently. The API does not mutate approved evidence. Missing/corrupt content invalidates active approval and blocks the run; original records remain for diagnosis.

Promotion serializes requests, consumes an active matching approval, updates the run-local accepted pointer, and inserts a pending receipt in one SQLite transaction. It then verifies the accepted candidate's hashes, HTTP health, and tenant boundary before finalizing. Failed verification atomically restores the previous pointer and records a rolled-back receipt. A receipt insert failure rolls back the pointer and approval consumption too.

Replays of an already executed approval return its original receipt, including after restart or with a new retry key. Reusing a key for a different approval is rejected. A replay is historical evidence of the execution; current integrity/state must be obtained separately before displaying a live accepted state. This backend has no production deployment side effect.

## Crash recovery and durability

A process-level POSIX `flock` serializes operations and startup recovery across Store instances. SQLite transactions use `BEGIN IMMEDIATE`, foreign keys, and `synchronous=FULL`. The lock spans fixed tool execution, so a recovering process cannot mistake a live worker invocation for an abandoned one. This trades throughput for a simple correctness boundary appropriate to the local deterministic layer.

Artifacts are written and fsynced before atomic hard-link publication, with directory fsync before SQLite references are committed. Published blobs are read-only. A pre-commit crash can leave an unreferenced blob; recovery preserves it and never turns it into evidence. Garbage collection and destructive reset are deliberately absent.

Interrupted tool intents become `interrupted`; no partial result is promoted to evidence. The caller may rerun the scoped tool to produce a new invocation and new evidence. Recovery never invents an approval. Pending promotions reverify the committed pointer and finalize the same receipt or roll back. A promoting run without a recoverable intent is rejected as ambiguous, with the database preserved. Unknown schema versions are rejected rather than silently migrated.

Back up SQLite and artifacts together while the service is stopped. Recovery assumes a private local filesystem with POSIX lock/link/fsync semantics. It does not protect against a malicious local administrator changing both the database and artifacts; hash checks detect content corruption within that trust model, not signed third-party attestation.

## Review and validation

The implementation review checked each public authority boundary, every state-machine edge, hash verification at decision/promotion boundaries, transaction boundaries around approval/pointer/receipt writes, interrupted execution handling, and the exact four-entry tool registry. Review fixes added independent trial validation, stale packet refresh, patch-blob validation, backend identity binding, directory durability, and rejection of ambiguous recovery states.

The test suite covers actual HTTP success/failure and generated-test execution; invalid contracts, stale inputs, missing gates, malformed results, divergent probes, failed health, timeouts, budgets, unsafe patches, illegal transitions, candidate/evidence/packet corruption, approval expiry, owner correction, cross-run ownership/evidence, concurrent promotion replay, artifact publication failure, SQLite transaction failure, restart, and actual subprocess exits during tool execution and after pointer commit.

Validation results are recorded in `outputs/phase2-validation.txt`. Owner review before connecting a model is still required; this implementation review is not a claim that owner approval has occurred.

## Remaining limits and next gate

- The backend is local, POSIX-only, and serializes all runs; no multi-host database or distributed lock protocol exists.
- Public authentication, secure cookies, rate limiting, retention, backup automation, and deployment hardening belong to later phases.
- The patch grammar is deliberately fixed; broadening generated test syntax requires a separate execution-safety design and review.
- General model text redaction, orchestration budgets, provider selection, and cost controls remain unimplemented because there is no model integration.
- No Strands, live model, UI, AWS, AgentCore, or Devpost work is included. Complete owner review of this deterministic layer before authorizing that work.
