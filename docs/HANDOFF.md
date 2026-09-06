# Migration Proof — Session Handoff

Updated: 2026-09-06

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

Phase 2 is committed as `bfd7a61178704936d5e2997d1dc3b822310e735b`. Phase 3 offline Strands integration is now implemented; see `docs/PHASE3.md` and `outputs/phase3-validation.txt`. Its provider is explicitly scripted, not a live LLM.

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

The baseline four tests remain unchanged. Phase 2 adds comprehensive deterministic tests; see `outputs/phase2-validation.txt` for the verified suite result and `docs/PHASE2.md` for architecture, review, and limitations.

## Settled architecture

- Strands Agents SDK owns planning, tool choice, the constrained safe-repair decision, and explanation.
- Deterministic application code owns policy, state transitions, evidence hashing, run isolation, approval, promotion, and receipts.
- The model receives exactly four operational tools:
  - `inspect_candidate`
  - `run_baseline_tests`
  - `compare_tenant_boundary`
  - `apply_safe_patch`
- Approval, promotion, arbitrary shell execution, and unrestricted filesystem/network access must not be exposed as agent tools.
- Persistence now uses SQLite plus immutable run-scoped content-addressed artifacts and SHA-256 hashes.
- Approved evidence becomes immutable; changed content invalidates the approval.
- AWS hosts the public demo. AgentCore is optional stretch scope after the baseline works.
- Claude is not required. Select a Strands-compatible model/provider only after confirming AWS region access, cost, and deployment fit.
- Build the product first; prepare and submit to Devpost later. Final submission requires explicit owner confirmation.

## Current gaps

- Phase 2 deterministic safety and Phase 3 offline integration are implemented and locally reviewed. The owner selected the direct OpenAI API on 2026-09-06. A no-network model/budget preflight is implemented (see `docs/OPENAI-PREFLIGHT.md`); the grant-gated transport and durable spend ledger are now implemented and tested without paid calls (`docs/OPENAI-TRANSPORT.md`). Account access and paid-call authorization remain open.
- Strands 1.54.0 is pinned with a locked optional dependency graph. The real SDK loop runs a zero-cost scripted provider with persistent budgets, a hard process deadline, and exactly four scoped tools. The OpenAI provider requires a separately issued owner spending grant; no paid execution is authorized.
- No operator UI yet.
- No AWS architecture, configuration, or deployment yet.
- AWS region, deployment authentication, retention, and teardown remain open. Local inference uses the selected OpenAI snapshot; its proposed $3.50 test ceiling still needs explicit authorization.

## Next work, in order

1. Review Phase 2 (`docs/PHASE2.md`) and its validation record.
2. Rerun the full deterministic suite and probe from a clean commit.
3. Resolve or explicitly accept the documented local-only constraints.
4. Obtain owner review of the four-tool registry and deterministic safety layer before connecting a model.
5. Continue the selected OpenAI API route in `docs/OPENAI-PREFLIGHT.md`: review `docs/OPENAI-TRANSPORT.md` and its validation evidence, obtain explicit paid-call authorization for the concrete $3.50 test and local key setup, then execute the bounded attempt and record account access and usage. The offline Strands portion is already present.
6. Build the operator UI around failure evidence, constrained repair, re-verification, human approval, and receipt states.
7. Verify AWS access and select the smallest viable staging architecture; add budget alerts, secret handling, observability, rollback, and teardown.
8. Deploy and verify staging, then obtain explicit approval before exposing a public endpoint.
9. Rehearse and record the synthetic demo; prepare submission assets only after the build is stable.

## Stop conditions

Stop and preserve evidence if there is cross-run contamination, mutable approved evidence, an ambiguous recovered state, any path for the model to approve/promote, credential exposure, unsafe public mutation, or unbounded AWS/model spend.

## Recommended next-session prompt

> Continue in `/Users/arielsmoliar/Developer/migration-proof` on `main`. Read this handoff, `docs/PHASE2.md`, `docs/PHASE3.md`, the build runbook, and the approved design. Run `uv sync --frozen --extra agent`, the complete suite, and the probe. The offline Strands integration is implemented and explicitly scripted; do not present it as LLM judgment or live-model evidence. The owner selected OpenAI API; `docs/OPENAI-PREFLIGHT.md` records the model and budget proposal. The grant-gated transport and durable spend ledger are tested with fake responses. Review `docs/OPENAI-TRANSPORT.md`; the next gate is explicit paid-call authorization and local key setup for one bounded $3.50 attempt. Keep approval and promotion out of the tool registry. No UI, AWS resources, AgentCore, or submission work yet.

## Latest live attempt (2026-09-06)

The owner authorized one eight-request/$3.50 attempt and configured `.env`. It stopped at the first provider dispatch before any tool ran; usage is unknown and $0.422308 remains reserved. See `docs/OPENAI-FIRST-ATTEMPT.md` and `outputs/openai-first-attempt.json`. A TLS-only diagnostic found zero system CA roots; the transport now explicitly uses the pinned certifi bundle and TLS verification passes without sending inference. The original run remains blocked and its closed grant is preserved. Do not repeat it automatically. The next gate is explicit authorization for a replacement of at most seven requests/$3.00, keeping cumulative reservations below $3.50. The local key is already configured; never display or commit it. This update supersedes the earlier first-attempt prerequisite notes above.
