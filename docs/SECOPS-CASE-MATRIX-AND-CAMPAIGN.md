# Nine draft cases and campaign planning

The evaluation registry now contains nine synthetic cases. Every case has a separate host-only rubric with source references and explicit unknowns. These are draft teaching/evaluation fixtures, not a held-out benchmark or human-accepted SOC dataset. The older analyst drill has its own case-01–03 identifiers; those phishing teaching variants are not this evaluation registry.

| Evaluation case | Family | Distinguishing source evidence | Draft policy outcome |
|---|---|---|---|
| case-01 | Sign-in | Planned VPN egress and exact scoped identity-owner approval; complete account audit | close / complete |
| case-02 | Sign-in | Successful access followed by external forwarding excluded from VPN approval | escalate / complete |
| case-03 | Sign-in | Scoped access approval, but account audit export unavailable | unresolved / needs_review |
| case-04 | Phishing | Similar messages with different URLs; first-only approval, second-message click and fresh exact malicious URL; stale domain assessment | escalate / needs_review |
| case-05 | Phishing | Delivered awareness simulation and explicitly authorized click | close / complete |
| case-06 | Phishing | Delivered document, partial click export and unknown exact URL verdict; no approval | unresolved / needs_review |
| case-07 | Endpoint | Scheduled inventory process and two connections within explicit approval scope | close / complete |
| case-08 | Endpoint | Approved inventory beside a distinct second executable with an exact malicious hash and linked network event | escalate / complete |
| case-09 | Endpoint | Execution with revoked approval and unavailable network export | unresolved / needs_review |

Complete describes the bounded collection/policy checks, not incident resolution or proof of compromise. A source assertion may justify the demo policy while remaining independently unverified. Missing metadata references have no invented event IDs. A click is not credential theft; forwarding does not prove exfiltration; a malicious hash assertion does not establish impact. Case-09 has no revocation timestamp, so it does not claim revocation preceded execution. Case-04 retains exactly its previously reviewed snapshot digest.

Independent AI review examined source joins, chronology, scope, expected outcomes and planning bounds. The reviewer saw the colocated rubric during inspection, so this was an unblinded second opinion. It is not human SOC validation. One unsupported temporal claim in case-09's title was corrected. Final targeted review found no remaining blockers; owner adjudication remains open.

## Offline preparation

Named preparation accepts every case ID above. It records the correct family and snapshot hash, preserves the four-tool registry and issues no grant. The existing default single-message preparation remains available.

```sh
.venv/bin/python -m secops_triage.live prepare --case case-08 --output data/case08-proposal
.venv/bin/python -m secops_triage investigate data/case08-proposal/incident.json --strands --output data/case08-scripted
.venv/bin/python -m secops_triage.evaluation prepare --run data/case08-scripted --case case-08 --output data/case08-review
.venv/bin/python -m secops_triage.campaign --output data/campaign-draft
```

Use new private output directories. Scripted SDK runs test collection and policy integration; their deliberately minimal findings do not satisfy the case rubrics. Blank reviews remain pending. Review support and omissions using the workflow in docs/SECOPS-EVALUATION-READINESS.md. No command above dispatches a live model or records analyst participation.

## Proposed slots, not spending authority

The planning artifact binds each case to fixture and rubric hashes and records the current engine, source file hashes, repository commit and dirty-worktree flag. The plan has its own SHA-256. It rejects cases needing more than the existing nine-tool budget. Current sign-in/endpoint cases need eight reads; phishing cases need nine.

| Stage | Proposed fresh live attempts | Request ceiling | Configured maximum ceiling |
|---|---:|---:|---:|
| M2: nine cases plus two additional hero runs | 11 | 110 | $46.75 |
| M4: three finished-UI hero rehearsals | 3 | 30 | $12.75 |
| M4: saved endpoint-close and sign-in-incomplete playback | 0 | 0 | $0 |
| Total proposed fresh inference | 14 | 140 | $59.50 |

These totals multiply the configured $4.25 per-run cap. They are not actual costs, new grants, independently refreshed pricing or an approved budget. All live slots state not_issued/unexecuted and have no run ID. M2's three hero attempts are adjacent. There are no diagnosis/retry slots. Any failed attempt must remain visible; stop and revise scope instead of adding an implicit retry.

M4 is intentionally unbound to an execution engine because the UI does not exist yet. Its slots require a new verified finished-UI build before execution. Alternate M4 walkthroughs explicitly refer to saved M2 runs and cannot count as fresh inference. M2 executions cannot be relabeled finished-UI rehearsals.

The planner does not dispatch, authorize, mark results complete or enforce a campaign at runtime. This is a planning ledger only. Before a campaign, implement per-slot run/grant/result binding and durable accounting for every stopped and completed attempt, with no slot reuse or silent retry. The current individual grant system still governs individual executions; creating a plan does not extend it into aggregate campaign authority.

Actual analyst observations, owner acceptance of each rubric, refreshed prices/bounds, verified execution source and explicit spending authorization remain required. A plan prepared from a dirty candidate is a review artifact; regenerate and verify it at the selected execution commit. Future UI or fixture changes require new bindings. No historical live store was opened or grant reused in this increment.

Verification: 268 tests passed in 64.932 seconds with source unchanged. Nine fresh scripted SDK runs matched draft policy outcomes using 75 recorded evidence reads; all claim reviews remain pending. The independent reviewer reran 28 matrix/campaign/case04 tests. Runbook validation passed with eight references and none missing. Source and packet identities are in outputs/secops-case-matrix-validation.json.
