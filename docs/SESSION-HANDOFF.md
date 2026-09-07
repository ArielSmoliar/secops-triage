# SecOps Triage session handoff

Saved 2026-09-07. This is the current-state entry point; docs/HANDOFF.md retains the chronological history. This update includes durable host-only campaign accounting; see docs/SECOPS-CAMPAIGN-ACCOUNTING.md.

## Repository and verification

- Work in `/Users/arielsmoliar/Developer/migration-proof`, branch `main`. The desktop may start in `/Users/arielsmoliar/Documents/ChatGPT/migration-proof`; do not assume that is the active repository. Set the working directory explicitly.
- GitHub: https://github.com/ArielSmoliar/secops-triage.git — now public, explicitly authorized by the owner for judges on 2026-09-07. Campaign accounting resumes from verified local/GitHub handoff `84cb2c68f361b1044e1c1a96f87fb9b09e40aa5c` on main. Reverify current HEAD and origin/main on startup; the accounting implementation is a later commit.
- Latest runtime verification after naming: **287 tests passed in 65.619 seconds**, with runtime/test/metadata hashes unchanged during execution. Evidence: outputs/secops-rename-validation.json. Prior campaign accounting verification passed 287 tests plus independent review of 19 focused tests with no blockers; outputs/secops-campaign-accounting-validation.json remains its historical record.
- Nine fresh synthetic investigations completed through the real Strands SDK with a scripted provider: 75 evidence reads, expected policy outcomes, all semantic evaluations pending. These are not live-model successes. Artifacts: data/secops-nine-cases-reviewed/manifest.json and case-01–09-scripted/investigation.md.
- Runbook validator passed, eight path references checked, none missing. Earlier original/faulty/corrected migration probe returned 403/200/403 with the intended faulty leak detected.
- Ignored data stores, private owner capabilities, .env and temporary logs are local-only, not on GitHub. Sanitized evidence, source, fixtures and docs are committed. Recreate synthetic runs in new private directories on another machine; never commit secrets or owner.json.

## Product and settled direction

Positioning: **From SIEM incident to analyst-ready handoff.** README and the conceptual hero now emphasize incident context, cited evidence, open questions and human review, informed by official Splunk content. See docs/SECOPS-POSITIONING-REVIEW.md. This changes messaging, not runtime or product scope.

The owner selected **SecOps Triage** as the demo/product name and **secops-triage** as the repository name. The existing local checkout stays at `/Users/arielsmoliar/Developer/migration-proof` to preserve environment paths and historical evidence links. Python module names stay `secops_triage` and `migration_proof`. Root package metadata/lockfile were renamed; use fresh imports for the changed engine identity.

The project pivoted from occasional migrations to daily Tier 1 SecOps investigation: an existing SIEM incident becomes an evidence-backed close/escalate recommendation or unresolved handoff. The SIEM creates and owns incidents; this demo never modifies upstream status. Scope is suspicious sign-ins, reported phishing and endpoint alerts. Phishing is the hero scenario.

This is a useful product-demo goal, not a claim to outperform established tools. No measured analyst time savings or production detection accuracy exists. The user has relevant Flare AI/safeagent experience, but no actual analyst session or case acceptance has been recorded.

The user requested independent review and Impeccable consultation. PRODUCT.md and docs/SECOPS-ANALYST-FLOW-REVIEW.md capture the confirmed calm, compact, plain-language workbench with keyboard access and status labels independent of color. No UI or visual accessibility audit exists. AI second opinions are not external human SOC validation; the latest matrix review was unblinded because rubrics were visible.

## Implemented and preserved

- Original Migration Proof deterministic foundation and tests remain intact. Do not restart Phase 2 or undo the SecOps pivot.
- SecOps read-only scoped tools: inspect_incident, lookup_entity, query_activity, find_related_cases. SQLite runs/evidence/reviews, hashed immutable artifacts, run/tenant isolation and recovery are implemented. Current SecOps schema is v2.
- Host-only Store.review records final close/escalate; Store.save_handoff stores unresolved reason/context/next action without inventing a final disposition. Approval, promotion, spending and analyst decisions are never agent tools.
- Typed authorization checks status, authority assertion, event/entity scope and validity. Intelligence carries observable, provider, match basis, confidence, assessment/expiry and rationale. Exact URL/IP/hash matching differs from stale, mismatched or domain-only evidence. Source authenticity and provider truth remain imported assertions.
- Conflict labels require overlap with the activity whose authorization was actually validated. A first message's approval does not conflict with a finding about a different message. Reviewer-discovered unchecked extra IDs are regression-tested.
- evaluation.py keeps raw model findings/recommendation, deterministic policy, final packet and disagreement separate. Citation identity is automatic; semantic support requires explicit attributed reviewer judgments and complete claim/omission annotations. Blank reviews cannot pass. A correct policy result cannot hide a wrong model close. This is not automatic entailment detection.
- evaluation_cases.py + case_matrix.py provide nine distinct draft cases and separate host rubrics. case-04 keeps its original two-message digest. Evaluation case-01–09 are a different namespace from drill.py's older phishing teaching case-01–03.
- live.prepare supports all nine named cases and verifies fixture/proposal identity before credentials or grants. It does not issue authority merely by preparing.
- campaign_store.py adds durable host-only slot/run/grant/result and evaluation accounting in one private Store. It requires exact clean source bindings, explicit host gate references and existing single-run grants; none have been authorized for a real campaign. Engine identity changed; use fresh imports.
- campaign.py is **planning-only**. It enumerates 11 M2 proposals (nine cases plus two extra hero runs), three future M4 UI hero runs, and two saved-playback alternatives. Configured cap totals: M2 $46.75, M4 $12.75, total $59.50. These are not actual spend, refreshed pricing or approved budgets. M4 execution build is explicitly unbound. outputs/secops-campaign-plan.json is a dirty-candidate planning artifact; regenerate for a selected execution build.

## Live history and authority

One historical real-model investigation completed: run `5f976e803708c0b16c4550d4477137ee`, 19.2 seconds, ten model requests, nine evidence reads/all four tools, escalation, estimated $0.013638. Read docs/SECOPS-COMPLETED-INVESTIGATION.md and outputs/secops-completed-live-investigation.json. Two earlier failures are preserved. One success is not a reliability estimate for current code.

**All historical grants are closed. No new paid call or campaign is authorized.** Do not reuse a grant, create speculative retries or interpret “keep going” as analyst feedback/spending authority. The nine latest runs are scripted; no key was read for them. Preserve old reports/stores. Engine changes require fresh imports; do not open historical live stores under incompatible code or repair their hashes.

## Next work, in priority order

1. Record actual formative analyst feedback and owner case adjudication when supplied. An asynchronous question requested a disposition, decisive evidence and missing context for data/secops-nine-cases-reviewed/case-04-scripted/investigation.md; no answer has been received. Do not mark M1.5 done or fabricate participation. Independent preparation can continue meanwhile.
2. **Durable campaign slot accounting is implemented:** read docs/SECOPS-CAMPAIGN-ACCOUNTING.md and secops_triage/campaign_store.py. It binds exact clean plans, runs, grants, immutable results and separate claim reviews in one designated private Store; failures cannot silently retry. The planning CLI remains planning-only. No campaign authority has been recorded outside temporary offline tests. Continue actual feedback/case adjudication and concrete campaign preparation only as their gates are satisfied. Distinguish planning, authorization, reservation, dispatch and result reconciliation.
3. After owner acceptance and actual feedback, freeze cases/build, refresh price/bounds and prepare a concrete campaign authorization proposal. Only explicit new spending authority permits live dispatch. Score every raw model claim and preserve failures. The three hero successes must be consecutive on the frozen build; M4 UI rehearsals are separate.
4. UI follows observed analyst friction and the runbook's M1.5/M2 gates. Repository publication is authorized and complete. No AWS, AgentCore, live connectors, further external publication, license adoption or Devpost submission is authorized by this handoff. Recheck hackathon rules/deadline when relevant; saved dates are not current verification.

## Startup reading and checks

Read this file, docs/HANDOFF.md, docs/runbooks/secops-demo-completion-runbook.md, docs/SECOPS-CASE-MATRIX-AND-CAMPAIGN.md, docs/SECOPS-EVALUATION-READINESS.md and outputs/secops-case-matrix-validation.json completely before editing. For campaign work also read docs/SECOPS-CAMPAIGN-ACCOUNTING.md, campaign_store.py, campaign.py, live.py, agent_spend.py, agent_runner.py, evaluation.py and store.py. Product/flow decisions are in PRODUCT.md and docs/SECOPS-ANALYST-FLOW-REVIEW.md. Historical migration background is docs/runbooks/migration-proof-build-release-demo-runbook.md and outputs/migration-acceptance-steward-design.md.

```sh
cd /Users/arielsmoliar/Developer/migration-proof
git status --short --branch
git rev-parse HEAD origin/main
git ls-remote origin refs/heads/main
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m migration_proof.probe
```

Use the pinned .venv and uv.lock; do not silently update dependencies. Real SDK scripted verification is `python -m secops_triage investigate <synthetic-json> --strands --output <new-private-directory>`. The --strands flag here uses a scripted provider; the host live execute command is different and paid.

## Working conventions and pitfalls

- Continue authorized local work autonomously; independent agents may handle bounded parallel review. Commit and push verified logical units. Keep commentary concise and report actual test evidence.
- The actual Developer repository may be outside a session's writable roots. Use the tool's normal escalation/automatic review for authorized operations when needed; do not modify a different checkout as a workaround.
- Never print .env or owner capabilities. Read only the exact credential needed internally for a newly authorized execution.
- Append HANDOFF.md from a freshly read variable and assert its existing contents remain a prefix. A previous variable-reuse mistake overwrote history and was fixed in commit448a149; inspect staged diffstat, especially handoff deletions.
- Freeze all runtime/test source before the final suite. An earlier mixed-source run had a CLI failure; its frozen rerun passed and the superseded result is retained. Do not edit source while verification is running.
- Current verification proves deterministic behavior and scripted integration, not semantic review quality, live reliability or analyst usefulness. Keep those claims separate.
