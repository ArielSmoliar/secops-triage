# Independent review of the SecOps demo plan

Date: 2026-09-07. Disposition: **conditional go for a bounded replay demo; not validated for daily SOC use or general investigative judgment**.

## Review provenance

Two fresh-context AI reviewers independently examined the plan and evidence implementation. A third independent agent applied Impeccable's product-register and cognitive-load guidance to the analyst flow after the owner confirmed the product direction. They were not the implementation agent and did not see each other's findings before returning their assessments. These are AI second opinions, not external human SOC validation, a separate-provider benchmark or an analyst study. No paid application-model calls, external messages, credential reads or runtime tests occurred in this review.

Inspected source: main at 570512542edff981536ea760b7cc272a934a02c5, tree 959c74e6a9fe750aae23b4b014e6cc6a9b37ccd6; repository/worktree /Users/arielsmoliar/Developer/migration-proof; remote https://github.com/ArielSmoliar/migration-proof.git. Main matched. Checkout was clean at task start; this review adds only documentation. Remote freshness was not required for inspection. Earlier test and live-execution results were read, not independently rerun.

## Findings and disposition

| Priority | Finding | Evidence | Plan decision |
|---|---|---|---|
| P1 | Daily analyst usefulness is absent from the runbook's critical path | Runbook M2/M3 proceed to paid breadth/UI; walkthrough says no analyst session has occurred | Add M1.5: record a real formative session, case note, source navigation and material corrections before paid breadth and full UI work |
| P1 | Correct packet outcome can hide wrong model judgment | agent.py reconcile retains deterministic escalation on disagreement, with needs_review | Score raw model recommendation, atomic claims, omissions, disagreement and final packet separately |
| P1 | Authorization can close a case without evaluating its actual scope | contracts.py authorization has target_id/actor/reference; investigation.py matches target; drill.py puts scope in prose | Add structured validity, authority and activity scope with revoked/expired/wrong-target/out-of-scope failure cases |
| P1 | Existing citations can accompany unsupported claims | agent.py validation checks identity, fields and length, not semantic support | Add negative claim-support evaluations, including click-to-compromise and unavailable-to-clean inferences |
| P1 | An incomplete handoff cannot be saved through the existing decision API | store.py review accepts only close/escalate; exercise also asks for needs_review | Specify and implement a durable unresolved handoff distinct from a final close/escalate review |
| P2 | Intelligence match cannot be inspected deeply enough | Indicator schema lacks dedicated observable/provider/freshness/rationale; report delegates validation back to analyst | Improve source detail before freezing live evaluation cases; preserve unresolved status when detail is unavailable |
| P2 | Teaching variants largely encode their answers | The three drill cases vary one fixture; scripted agent calls the same assessor | Keep teaching and held-out evaluation separate; independently review new case expectations |
| P2 | The report makes analysts reconcile repeated and distant information | Recommendation, model disagreement, evidence and repeated note sections | Use adjacent competing-evidence groups, visible disagreement and progressive source detail in M3 |
| P2 | Runbook status, harness scope and rehearsal accounting drifted | M1 complete but follow-up restarted it; live prepare hardcodes phishing; M4 adds fresh runs | Archive M1 steps as history; add fixture-selectable preparation and enumerate every campaign/rehearsal slot |

All findings accepted as planning requirements. None is claimed fixed in runtime code by this documentation increment. The current demo rules remain intentionally narrow, and historical evidence stays intact.

## Revised sequence

1. State the proven claim precisely: model-directed bounded collection and cited assessment with deterministic disposition safeguards over synthetic replay evidence.
2. Observe the current phishing walkthrough and record actual analyst friction. One owner session is formative only. Do not infer participation or approval from “keep going.”
3. Strengthen source contracts and cases. Proposed stress case: two similar messages to one user, one covered by campaign authorization and one outside scope; a click tied to the second; stale/domain-level versus fresh/exact-match intelligence; incomplete follow-on identity telemetry. Have a domain reviewer determine the expected outcome after inspecting the evidence, rather than baking a convenient verdict into the plan.
4. Add fixture-selectable bounded preparation and separate model/packet/claim scoring. Verify wrong-target, stale, missing, truncated and adversarial cases offline.
5. Freeze nine cases across the three families, hidden expectations and a fully enumerated live campaign. Request its actual budget only when concrete, then execute and pass M2 before final rehearsals. Do not silently reuse closed grants.
6. Build the smallest analyst workspace that addresses the observed friction, including the unresolved-handoff persistence gap. The flow specification is docs/SECOPS-ANALYST-FLOW-REVIEW.md.
7. Verify final-build UI rehearsals under separately identified campaign slots, then package. No hosting or submission is implied by this review.

## Acceptance evidence still required

- An analyst reaches a supported decision or unresolved handoff without rebuilding the case from scratch; record corrections, missing context and next action.
- Every material model claim has supporting evidence and correct scope. Correct JSON, a valid handle or rule agreement is insufficient.
- Authorization and intelligence are tied to the correct message/activity/time; stale or mismatched evidence cannot produce an unsafe close.
- Failed and incomplete runs remain visible. No paid attempt or model disagreement is omitted from scoring.
- UI saves the exact packet/revision and distinguishes a handoff, a local decision and an upstream system action.
- Human productivity evidence uses separately authored matched cases and counterbalanced assignments. No claim of savings arises from the current teaching kit.

## What this review changes

The project remains worth continuing, but the next work should improve evidence sufficiency and decision usability, not merely add more successful-looking reports. The existing nine-read success and safety tests remain valuable technical evidence. They are not a substitute for analyst usefulness or realistic investigative assessment.

Follow-up independent plan review confirmed that the five plan findings are explicit open gates, with no runtime fix or analyst result falsely claimed. No new blocker was found. Structural runbook validation passed and the drift checker found eight referenced paths with none missing. Runtime tests were not rerun for this documentation-only change.
