# Migration Proof — Session Handoff

Updated: 2026-09-05

## Project

Migration Proof is an Agents for Humans hackathon entry in the **Professional Agents** track. Its product promise is **“Evidence-backed acceptance for software migrations.”** The demo proves that ordinary tests can remain green while a targeted tenant-boundary invariant catches a migration regression, guides a constrained repair, verifies the result, and leaves the final approval with a human.

## Repository

- Local: `/Users/arielsmoliar/Developer/migration-proof`
- GitHub: `https://github.com/ArielSmoliar/migration-proof`
- Visibility: private
- Branch: `main`
- Baseline commit before this handoff: `878c13f9f17487cac2df0533a2ee3c6940a29a83`
- Remote: `origin` tracks `ArielSmoliar/migration-proof`

Do not return to `/Users/arielsmoliar/Documents/Codex/2026-09-02/lo` for implementation. That File Provider-backed directory became inaccessible from the shell. The project was copied safely to the local Developer directory; the old source was not deleted.

## Current implementation

- Python standard-library fixture with `original`, `faulty`, and `corrected` revisions.
- The cross-tenant invariant expects an alpha token requesting a beta document to receive HTTP 403.
- The faulty revision returns 200 and exposes synthetic `id`, `tenant`, and `title` fields.
- Baseline and boundary tests exist and pass.
- Probe output demonstrates `403 → 200 leak → 403`.
- Approved product/architecture design: `outputs/migration-acceptance-steward-design.md`.
- Validated execution runbook: `docs/runbooks/migration-proof-build-release-demo-runbook.md`.

Verified locally:

```bash
python3 -m unittest discover -s tests -v
python3 -m migration_proof.probe
```

The test suite currently contains four passing tests.

## Settled architecture

- Strands Agents SDK owns planning, tool choice, the constrained safe-repair decision, and explanation.
- Deterministic application code owns policy, state transitions, evidence hashing, run isolation, approval, promotion, and receipts.
- The model receives exactly four operational tools:
  - `inspect_candidate`
  - `run_baseline_tests`
  - `compare_tenant_boundary`
  - `apply_safe_patch`
- Approval, promotion, arbitrary shell execution, and unrestricted filesystem/network access must not be exposed as agent tools.
- Persistence will use SQLite plus run-scoped evidence directories and SHA-256 hashes.
- Approved evidence becomes immutable; changed content invalidates the approval.
- AWS hosts the public demo. AgentCore is optional stretch scope after the baseline works.
- Claude is not required. Select a Strands-compatible model/provider only after confirming AWS region access, cost, and deployment fit.
- Build the product first; prepare and submit to Devpost later. Final submission requires explicit owner confirmation.

## Current gaps

- No deterministic state/evidence record layer yet.
- No Strands dependency or agent orchestration yet.
- No SQLite persistence or run-scoped evidence storage yet.
- No operator UI yet.
- No AWS architecture, configuration, or deployment yet.
- AWS region, model/provider, authentication posture, budget ceiling, retention, and teardown policy remain open.

## Next work, in order

1. Implement typed inputs and outputs for the four operational tools.
2. Implement the deterministic state machine, SQLite records, run isolation, artifact storage, and SHA-256 evidence hashing.
3. Add thorough tests for legal and illegal transitions, hash mismatches, stale approval, concurrent-run isolation, restart recovery, and failed repairs.
4. Review the registered tool list and deterministic safety layer before connecting a model.
5. Add a pinned Strands Agents SDK dependency and bounded orchestration with tool-call, iteration, timeout, and cost limits.
6. Build the operator UI around failure evidence, constrained repair, re-verification, human approval, and receipt states.
7. Verify AWS access and select the smallest viable staging architecture; add budget alerts, secret handling, observability, rollback, and teardown.
8. Deploy and verify staging, then obtain explicit approval before exposing a public endpoint.
9. Rehearse and record the synthetic demo; prepare submission assets only after the build is stable.

## Stop conditions

Stop and preserve evidence if there is cross-run contamination, mutable approved evidence, an ambiguous recovered state, any path for the model to approve/promote, credential exposure, unsafe public mutation, or unbounded AWS/model spend.

## Recommended next-session prompt

> Restore the Migration Proof context and continue work in `/Users/arielsmoliar/Developer/migration-proof` on branch `main`. Read `docs/HANDOFF.md`, `docs/runbooks/migration-proof-build-release-demo-runbook.md`, and `outputs/migration-acceptance-steward-design.md` completely before editing. Verify the clean Git state and rerun the existing four tests and probe. Then implement Phase 2 only: typed deterministic contracts for the four scoped agent tools, the SQLite run/state/evidence/approval/promotion record layer, run-scoped artifact storage, SHA-256 hashing, legal transition enforcement, approval invalidation, and crash recovery. Add comprehensive tests for success and failure paths. Do not add Strands, a live model, UI, AWS resources, AgentCore, or Devpost submission work until the deterministic layer is complete, tested, and reviewed. Preserve the rule that approval and promotion are never agent tools. Commit and push the completed, verified Phase 2 as a logical unit, and report test evidence plus any unresolved risks.
