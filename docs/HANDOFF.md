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

## Latest completed live investigation (2026-09-07)

The owner authorized the seven-request/$3.00 replacement. It completed successfully at `5cef71a706919896c4c662a1471190989aae0228`: six real model requests, all four scoped tools, one generated regression test executed and failed as expected, blocked packet, zero approvals/promotions. See `docs/OPENAI-LIVE-RESULT.md` and `outputs/openai-live-validation.json`. All usage is recorded; conservative estimate $0.004005. Combined reservations including the prior uncertain attempt are $2.956156. Both grants are closed; no further paid attempt is authorized. The configured key remains in ignored `.env`. Next review the live evidence and define the corrected-candidate/reliability evaluation scope before changing the grant policy or requesting further paid execution. This update supersedes the pending-replacement notes above. No UI, AWS, AgentCore, or submission work yet.

## Corrected evaluation preparation (2026-09-07)

The corrected-candidate grant scope and atomic spend-schema v2 migration are implemented and tested with fake provider responses; see `docs/CORRECTED-EVALUATION.md`. Grants now remain single-use per run/digest and preserve prior spend history, allowing an explicitly owner-corrected digest carrying the generated regression to receive separate authorization. The corrected test reaches readiness with all four fresh gates passing, without approval or promotion. No further paid calls were made and historical live stores were not migrated. Next: obtain authorization for an additional corrected-only attempt of at most four requests/$1.70, using a fresh zero-cost offline-prepared run because backend identity changed. The local key already exists in ignored `.env`; do not display it. This supersedes the earlier request to design the corrected scope. Reliability, UI, AWS, AgentCore, and submission work remain pending.

## SecOps product pivot (2026-09-07)

The owner paused the migration roadmap to focus on frequent daily analyst work and selected: **turn an alert into an evidence-backed close-or-escalate recommendation**, covering suspicious sign-ins, reported phishing, and endpoint alerts. See `memory/secops-triage-design.md` for the design draft, alternative approaches, domain contracts, reuse boundaries, and evaluation plan. Product scope is agreed; local case replay is the recommended implementation approach, pending review. No SecOps implementation or paid execution has occurred.

This supersedes the next-step instruction to request or run the corrected migration evaluation. Preserve historic runs, closed grants, and `.env`; no new paid call is authorized. The migration design and release runbook remain historical references, not the active product roadmap.

Baseline reverified at `7e36c579705a904b5fdf416635db8932031b6c94`: 125 tests passed in 59.051 seconds; probe reproduced original 403, faulty 200 with synthetic leaked fields, corrected 403. Test log: `/private/tmp/secops-pivot-baseline-tests.txt` (temporary local evidence). Initial Git state was clean on main. Changes in this pivot increment are documentation only.

### SecOps workflow research completed (2026-09-07)

At the owner's request, deep research examined official Google Cloud/Workspace, AWS and Microsoft security workflows. Report: `output/pdf/secops-analyst-workflow-research.pdf`; internal source, claim ledger and research/verification notes: `memory/research/secops-20260907/`. The seven-page report cites 22 primary sources and all pages were visually checked. Daily triage is documented; a universal frequency ranking and this product's time savings remain unproven. Native agents already perform substantial evidence-backed investigation. The next office-hours task is to validate where missing context, evidence coverage or review effort remain painful beyond the team's enabled tools. All three alert families remain scoped. No implementation, connector access or paid model calls occurred; design approach review remains open.

## Existing-incident SecOps replay implemented (2026-09-07)

The owner approved implementation and clarified the product boundary: another tool such as a SIEM creates the incident; a Tier 1 analyst investigates its details and context. Competitive superiority is not required for the demo. This update supersedes the pending implementation/review and documentation-only statements above.

The separate standard-library `secops_triage` package now executes four typed, scoped read tools over normalized replay snapshots; gathers ownership, prior cases and activity for linked suspicious sign-in, reported phishing and endpoint alerts; persists runs, invocations, evidence and host-only reviews in SQLite; and renders an evidence-linked Markdown investigation with a draft case note. Immutable SHA-256 artifacts, legal transitions, stale-review invalidation, idempotency, crash recovery and run/tenant scope checks are implemented. Approval, review and upstream incident mutation are never agent tools. Local review leaves the SIEM unchanged.

Read `docs/SECOPS-REPLAY.md` and `memory/secops-triage-design.md`. This is explicitly **deterministic replay playbooks (no live model)**, not an AI efficacy result. A new clean clone with the final source overlay passed all 155 tests in 58.080 seconds, including 30 SecOps test methods and 30 authored scenario subcases. The migration probe reproduced the expected original 403, faulty 200 leak, corrected 403. The combined incident replay completed and recommended escalation; a separate unauthorized-source example retained missing context while recommending escalation. Commands, source hashes and limits are saved in `outputs/secops-replay-validation.json`.

Local review artifacts (ignored, not committed): `data/secops-incident-demo/investigation.md` and `data/secops-missing-context-demo/investigation.md`. Do not expose their owner capabilities. Reproduce with `python -m secops_triage demo --output data/new-demo-directory`.

Next: review the complete and incomplete investigation experience, then scope model-driven investigation and the analyst interface. Source completeness and authorization are trusted import assertions; replay rules are intentionally narrow. Production connectors, identity, retention and real-world efficacy remain unresolved. No new paid call, UI, live connector, AWS resource, AgentCore or submission work occurred. Preserve historical migration stores and closed grants; `.env` remains ignored and no new paid execution is authorized.

## SecOps Strands integration (2026-09-07)

The owner approved the next Strands milestone. Read `docs/SECOPS-STRANDS.md`. The real SDK now drives scoped replay tools in a supervised worker and persists a cited, untrusted agent assessment separately from deterministic evidence checks. Disagreement blocks closure. Host-only SecOps grants and durable reservations reuse the bounded OpenAI transport without inheriting migration spending authority. CLI `--strands` is explicitly zero-cost scripted execution.

No paid SecOps request has run. The prepared proposal is ONE fresh synthetic phishing incident, up to ten OpenAI requests/2,048 output tokens each, nine tools, 120 seconds and $4.25 maximum. Earlier paid migration grants are closed and do not authorize this attempt. Obtain explicit authorization for this concrete ceiling before calling `agent_spend.authorize` or reading the ignored key for dispatch. Preserve historical stores. New engine identity requires fresh replay imports. See `outputs/secops-strands-validation.json` for final verification. AWS/AgentCore, live connectors and UI remain pending.

Final clean-clone verification: 173 tests passed in 60.938 seconds; probe reproduced 403/200/403 and the supervised Strands demo completed. The exact prepared live run is `4ba7fadcc26965807baba68624ac767d` under ignored `data/secops-live-prepared/` with `proposal.json` and a private `owner.json`. No grant issued. The zero-cost report is `data/secops-strands-demo/investigation.md`.
