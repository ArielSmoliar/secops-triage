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

## First SecOps live attempt stopped (2026-09-07)

The owner approved the ten-request/$4.25 proposal. The single attempt ran at `7764c50cf98d7b335c78f7e3dde7896a37648364` and stopped after four model requests and three successful read calls (inspect incident, user lookup, device lookup), before any activity query or final assessment. All usage settled; estimated $0.001623, reserved $1.689232. The grant is closed; no retry was made or authorized. Read `docs/SECOPS-FIRST-LIVE-RESULT.md` and `outputs/secops-first-live-result.json`. This supersedes the pending-authorization notes above.

The exact fourth-response validation failure was not persisted by that version. Safe stage/stop-reason journaling is now added and tested; it does not retroactively identify or fix the response failure. No successful SecOps model investigation is claimed. A new diagnostic attempt would need a fresh run (engine changed) and separately authorized scope/budget. Preserve the failed run and its closed grant; do not reuse the earlier prepared run or silently rerun it.

## M1 complete: one real-model investigation (2026-09-07)

The owner focused work on one end-to-end investigation and authorized parallel review and the additional bounded attempt. After explicit tool schemas and short event/metadata citation handles, run 5f976e803708c0b16c4550d4477137ee completed at execution commit 69210cf928f8c2cadde604d4a2dc4a8b8d58495e: 19.2 seconds, all nine reads/all four tools, five complete checks, eight model findings, complete packet, escalation recommendation. Ten requests settled; estimate $0.013638 and reservation $4.223080. Grant closed. All 186 tests passed before execution. Separate semantic review passed the narrow escalation with wording caveats; no analyst disposition was recorded.

Read docs/SECOPS-COMPLETED-INVESTIGATION.md and outputs/secops-completed-live-investigation.json. The report is data/secops-one-investigation-citations/investigation.md; owner.json remains private. Earlier failed runs remain preserved; all SecOps grants are closed. Do not infer reliability or a live SIEM connector from this synthetic replay success. M1 is complete; broader scenarios/UI/hosting are subsequent work, not part of this focused increment. No new paid call is authorized after this completed attempt.

## Analyst walkthrough prepared (2026-09-07)

After the successful M1 run, the owner chose to strengthen the demo and test analyst value. `secops_triage.drill` now generates three matched phishing variants (documented simulation, conflicting intelligence, unavailable intelligence), identical manual/assisted source results, reports and an empty observation sheet. Read docs/SECOPS-ANALYST-WALKTHROUGH.md for the five-minute narrative, demo policy, facilitator key and 10-point rubric. This is deterministic synthetic replay and formative preparation, not new model evaluation or measured time savings. No analyst sessions or local dispositions are fabricated; M2 is still open. No paid calls were made and all prior closed grants remain untouched.

Verification: 188 tests passed in 61.697 seconds. See outputs/secops-analyst-drill-validation.json. Reviewed local kit: data/secops-analyst-drill-reviewed; start the guided demonstration with case-02/assisted.md. Manual source exports include the same evidence IDs as the assisted report, including empty query results. Absolute evidence links require a local walkthrough.

## Decision-first analyst handoff (2026-09-07)

The report now leads with cited decision evidence and unresolved questions, including missing normalized intelligence detail and unavailable-source citations. The draft case note retains those questions. Rendering does not alter packet conclusions or record an analyst decision. A fresh deterministic kit is at data/secops-analyst-handoff; earlier kits and live evidence remain preserved. 67 SecOps tests passed, including four new handoff cases; see outputs/secops-handoff-validation.json. No paid calls, external intelligence enrichment or analyst study occurred.

## Independent plan and Impeccable flow review (2026-09-07)

The owner requested stronger external review and confirmed a calm, compact analyst workbench with plain language, keyboard access and non-color-only status. PRODUCT.md records the confirmed context. Two fresh-context AI reviewers challenged plan/evidence quality; a third independently applied Impeccable product-flow guidance. Read outputs/secops-independent-plan-review.md and docs/SECOPS-ANALYST-FLOW-REVIEW.md. These are independent AI second opinions, not human SOC validation or a browser audit.

Conditional go: the runbook now requires observed analyst usefulness, structured authorization/intelligence quality, fixture-selectable preparation and separate raw-model/claim/final-packet scoring before paid breadth evaluation. M3 must implement a durable unresolved handoff because store.review only records close/escalate. Keep assessment disagreement beside the suggested decision and preserve revisions/drafts. This increment changes plans/context only; these runtime findings are not yet fixed. No analyst observations, model calls, UI implementation, external intelligence lookup or deployment occurred.

## Unresolved handoff persistence implemented (2026-09-07)

Store.save_handoff now saves immutable, packet-bound analyst reason/missing context/next action without a final close/escalate decision. status returns handoff history; new notes, incident revisions and final decisions retire older current notes atomically. The four agent tools remain unchanged. Schema v2 is an additive atomic migration; historical live stores were not opened. Engine identity changed: use a fresh import for new work. Read docs/SECOPS-UNRESOLVED-HANDOFF.md. No actual analyst observation, paid call, UI or SIEM action occurred. Source-quality, observed-usefulness and model-scoring gates remain open.

Verification: 202 full-suite tests passed in 62.751 seconds; final focused handoff suite passed 11 tests, including the additional reviewer-requested rollback case. Independent review found no blockers. See outputs/secops-handoff-store-validation.json.

## Structured authorization scope implemented (2026-09-07)

Authorization now requires typed status, role/imported verification, approval and validity times, and explicit event/entity scope. Closure evaluates these fields for triggers and related activity; prose cannot grant scope. Invalid or conflicting authorization remains cited and cannot justify close. See docs/SECOPS-AUTHORIZATION-SCOPE.md. The importer assertions are not externally authenticated by this demo. Old three-field authorization snapshots are rejected; engine identity changed, so use fresh imports. Historical live stores/reports are preserved and were not opened. Intelligence depth, semantic scoring, observed usefulness and UI remain open; no paid calls or analyst observations occurred.

Final verification: 216 tests passed in 63.740 seconds on the reviewed implementation. Thirteen focused authorization tests cover the new scope and review-discovered gaps. See outputs/secops-authorization-validation.json.

## Intelligence evidence made inspectable (2026-09-07)

Indicators now carry typed observable, provider, match basis, confidence, assessment/expiry times and rationale; message/process events carry source observables. Deterministic matching and source-validity checks distinguish exact evidence from expired, mismatched, domain-only and conflicting findings. The handoff includes source detail and keeps evidence-quality gaps separate from failed collection. See docs/SECOPS-INTELLIGENCE-EVIDENCE.md. New shapes/engine identity require fresh imports; historical live stores remain untouched. Provider truth remains an importer assertion, not external verification. No paid calls, human observations or UI were added.

Final verification: 228 tests passed in 63.859 seconds, including 12 focused intelligence tests. Fresh exact-URL and domain-only phishing replays yielded escalate/complete and no recommendation/needs_review respectively. Three independent AI review findings were fixed and rechecked; no remaining blockers in reviewed scope. Runbook validation passed with eight references and zero missing. See outputs/secops-intelligence-validation.json. Next: adjudicate deeper case expectations and separate model-claim scoring; observed analyst usefulness remains unvalidated.


## Deeper case and separate evaluation ready for review (2026-09-07)

Added draft case-04 with two similar messages, first-only authorization, second-message click, stale/domain-only benign intelligence and a fresh exact second-URL malicious assessment. Host-only rubric is separate from agent input. Independent AI source adjudication supports escalation; needs_review remains a conservative policy expectation, not human consensus or an exact-URL conflict. The fresh report exposed a cross-message authorization conflict label; it now requires overlap with the activity scope actually validated, including a review-discovered unchecked-extra-ID edge-case regression.

Named live preparation records and checks fixture identity before credentials/grants. New host-only evaluation snapshots keep raw model claims, policy outcome, final packet and disagreement separate. Explicit attributed reviewers annotate claim spans/support and omissions; a valid citation does not auto-pass. This checks review completeness, not semantic entailment. Draft/scored scripted cases never count as campaign acceptance. See docs/SECOPS-EVALUATION-READINESS.md and outputs/secops-evaluation-independent-review.md.

Final verification: 249 tests passed in 64.524 seconds with source unchanged during execution; 124 focused SecOps tests passed, including 21 evaluation/case tests independently rerun. Runbook checks passed and the original/faulty/corrected probe returned 403/200/403 as expected. Fresh scripted SDK run 5e131cb4e08bac767883b4df1d5323f4 completed nine reads, escalate/needs_review, no false conflict; blank evaluation remains pending_review. See outputs/secops-evaluation-validation.json. Earlier replay and superseded test failure are retained. No paid calls, grants, actual analyst sessions, UI or historical live-store access occurred.

Next: obtain actual formative analyst observations and owner case adjudication; author/review the remaining distinct cases and prepare the enumerated live campaign. Do not treat keep-going messages as analyst feedback or closed grants as reusable authority.


## Nine-case matrix and planning ledger (2026-09-07)

Added eight distinct draft synthetic cases alongside unchanged case-04: close, escalate and unresolved for sign-in, reported phishing and endpoint. Their host-only rubrics preserve source joins, approval scope and unknowns. The evaluation registry uses case-01–09 separately from the older analyst drill's case-01–03 namespace. Named preparation accepts all nine and reports the correct family without issuing grants.

Planning-only campaign command binds source/fixture/rubric hashes and enumerates 11 M2 live proposals, three separate future-UI M4 hero proposals and two zero-cost saved playbacks. Configured ceilings total $59.50, not new authority or refreshed pricing. All slots are unexecuted; M4 build is explicitly unbound. Durable per-slot run/grant/result accounting still needs implementation before dispatch. See docs/SECOPS-CASE-MATRIX-AND-CAMPAIGN.md and outputs/secops-campaign-plan.json. The latter is a dirty-candidate planning snapshot and must be regenerated at a selected execution commit.

Independent unblinded AI review (rubrics were visible) found an unsupported revocation chronology in case-09's title; corrected. All 28 matrix/campaign/case04 tests passed in that review, with no remaining blockers in scope. Final frozen full suite: 268 tests passed in 64.932 seconds. Nine fresh scripted SDK runs produced the expected draft outcomes with 75 evidence reads; all semantic evaluations remain pending. Runbook validation passed. See outputs/secops-case-matrix-validation.json. No paid calls, grants, human acceptance, analyst sessions or historical live-store access occurred.

An asynchronous request for actual analyst feedback on the current case-04 report was sent; no response has been recorded. Do not treat continuation as feedback. Next: record actual feedback and owner case adjudication when supplied; prepare durable campaign slot accounting independently. Paid breadth, UI, external publication and deployment gates remain open.


## Session saved for transfer (2026-09-07)

Current-state entry point: docs/SESSION-HANDOFF.md. Ready-to-paste resume prompt: docs/NEXT-SESSION-PROMPT.md. Latest implementation is 8a2f435; this later save is documentation-only, with the 268-test frozen baseline retained. Next independent work is durable host-only campaign slot accounting; analyst feedback/case acceptance and all new paid authority remain pending. GitHub main was verified against local main before this save; the save commit is to be pushed and reverified. No runtime source or historical evidence changed.


## Durable host-only campaign accounting (2026-09-07)

Resumed clean main and verified GitHub at handoff 84cb2c6; baseline 268 tests passed in 64.768 seconds. Added CampaignStore in secops_triage/campaign_store.py: exact clean plan/source/fixture/rubric identity, explicit host gate references, unique reserved slot/run/grant associations, durable dispatch intent, worker-consumption fencing, immutable stopped/incomplete/completed results and separate bound evaluation records. Review must pass before continuation; any recorded failure remains a stop, including one recorded after the next reservation. Existing bounded single-run grants and supervisor remain in control; campaign functions are not agent tools.

Crash recovery closes orphan/unused authority, preserves unknown request reservations and never resets or reruns a slot. Host lifecycle and store locks cover concurrent reservation, worker startup and recovery. Recorded results remain readable after source changes without repairing old hashes. This is one designated local Store, not distributed or copied-database coordination. Import repeated hero cases lazily to avoid incident-head supersession. Read docs/SECOPS-CAMPAIGN-ACCOUNTING.md.

Independent AI design/implementation review identified and resolved startup-lock, worker-bypass and evaluation-continuation gaps; final independent focused suite passed 19 tests, no remaining blockers in reviewed scope. Frozen full suite: 287 tests passed in 65.830 seconds, all runtime/test/lockfile hashes unchanged. Probe retained 403/200/403 and the intentional faulty leak. Evidence: outputs/secops-campaign-accounting-validation.json. SDK execution tests use fake OpenAI transport in temporary synthetic stores, not live calls or real analyst judgments.

No paid calls, real campaign authority, analyst feedback, human case acceptance, UI/cloud/publication work or historical live-store access occurred. All historical grants remain closed. Engine changed; use fresh imports. Actual M1.5 feedback and case adjudication remain pending; prepare a concrete frozen-build campaign proposal with refreshed pricing only when those gates are satisfied, and obtain explicit new paid authority before dispatch.


## Product and repository renamed to SecOps Triage (2026-09-07)

The owner selected SecOps Triage as the demo/product name and secops-triage as the repository name. GitHub repository ID 1358193735 is now https://github.com/ArielSmoliar/secops-triage and remains private on main; origin points to the renamed repository. The local checkout stays at /Users/arielsmoliar/Developer/migration-proof so saved evidence links and environment paths remain valid. Historical repository names in older evidence are retained.

Updated README, product heading, root project metadata, CLI description and newly generated report branding. The uv.lock change renames only the root virtual project; dependency versions are unchanged. uv lock --check --offline passed. Full frozen suite: 287 tests passed in 65.619 seconds; CLI help and a fresh deterministic report show SecOps Triage. See outputs/secops-rename-validation.json. No paid calls or historical store/evidence changes occurred. The lockfile change alters execution identity, so new investigations need fresh imports. All analyst, spending, UI/cloud and publication gates remain unchanged.
