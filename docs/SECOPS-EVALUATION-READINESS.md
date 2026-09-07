# Deeper phishing case and separate assessment scoring

This increment prepares offline evaluation. It does not complete M1.5 or M2, run a paid campaign, or establish analyst usefulness. The case and its rubric remain draft teaching material pending Ariel's domain review.

## Inspect the message relationships

`case-04` has two messages to the same user with identical sender and subject, but distinct message IDs and URLs. The first arrives at 10:00 and is delivered at 10:01. Its source authorization was approved at 09:00 and covers only that message and delivery. The follow-up arrives at 10:05, is delivered at 10:06 and receives an allowed click at 10:07. Similarity does not extend the first message's authorization.

A cached benign domain assessment expired at 10:00. A later source assessment labels the exact follow-up URL malicious and remains within its source-validity interval at the 11:00 snapshot. Source accuracy is still an imported assertion. Neither the click nor the provider's landing-page description establishes credential submission or account compromise. Follow-on identity telemetry is outside this bounded phishing playbook; it was not queried and must not be described as clean or as a failed query.

Independent fresh-context AI review adjudicated the source chronology and supports escalation. The expected `needs_review` investigation status is the implementation's conservative policy for retaining stale/domain-only evidence gaps. The old benign domain assessment is not a competing exact-URL verdict. This qualification is in the rubric; no human analyst consensus is claimed.

Fresh report inspection also exposed an old cross-message conflict label: any authorization and suspicious finding in one alert were described as conflicting. The assessor now requires overlap between suspicious activity and an applicable authorization scope. The two-message case has no such conflict; a same-message regression preserves the genuine conflict path.

Source input comes from `evaluation_cases.get_case('case-04')`; `get_expectations` returns a separate host-only rubric with a fixture digest, required facts, unknowns and prohibited overclaims. Rubric data never enters the snapshot, tool results or model prompt. The readable synthetic IDs and source rationale still make this a teaching case, not a held-out benchmark. Eight additional draft cases are now available in docs/SECOPS-CASE-MATRIX-AND-CAMPAIGN.md; none is claimed human-accepted or live-validated.

## Evaluate model, policy and final packet separately

`secops_triage.evaluation` reads the current, owner-authorized run and verifies its packet and stored evidence. Its evaluation snapshot includes:

- Original model recommendation and findings, unchanged, with their original citations.
- Deterministic policy recomputed from the actual collected evidence before reconciliation.
- Final reconciled packet and model/policy disagreement.
- Fixture, rubric, evidence, packet and evaluator identity bound by SHA-256.

The score separates raw-model outcome agreement, policy agreement, final-packet agreement, per-claim support and omitted required facts/unknowns. Thus a model that recommends close cannot pass merely because policy preserves escalation.

Citation validity is checked by the existing packet validator. Semantic support is **reviewer-mediated**, not inferred from citation existence, keyword matching or rule agreement. The reviewer splits every finding into claim spans covering all non-whitespace text, records supported/unsupported/unverifiable judgments and rationales, and explicitly attests that all material claims were split. Each rubric requirement is marked present with references to supported findings, omitted, or unreviewed. The evaluator checks structural completeness; it cannot verify the reviewer's honesty or detect an incorrectly labeled semantic claim. Prohibited overclaims are reviewer guidance, not a hidden automatic classifier.

Blank reviews remain `pending_review`; unsupported/unverifiable claims, omissions or outcome mismatch fail. A run without model assessment is `not_evaluated`. A complete review can pass this local evaluation, but `campaign_acceptance` remains false: this draft case, scripted outputs and AI judgments do not satisfy live-run, human domain-review or observed-usefulness gates. The offline negative tests use explicitly labeled adversarial outputs; they demonstrate score behavior, not automatic hallucination detection.

Stopped executions have no final packet to score and are rejected by this scorer. Their existing safe live-result/session/spending records remain the evidence of failure. The planning-only campaign ledger in docs/SECOPS-CASE-MATRIX-AND-CAMPAIGN.md enumerates proposed slots. Durable runtime binding and failed-attempt accounting remain to be implemented; completed runs must never be counted as all attempts.

## Reproduce without paid calls

Run from the repository at the intended source revision. Choose new output directories; commands refuse to overwrite existing artifacts.

```sh
.venv/bin/python -m secops_triage.live prepare --case case-04 --output data/case04-proposal
.venv/bin/python -m secops_triage investigate data/case04-proposal/incident.json --strands --output data/case04-scripted
.venv/bin/python -m secops_triage.evaluation prepare --run data/case04-scripted --case case-04 --output data/case04-review-draft
```

The first command imports a named synthetic fixture and records its digest without issuing any grant. The second runs the real SDK with a **scripted provider**, not a live model. The scripted fixture is an orchestration test, not a competent analyst answer; its default finding is insufficient for the full rubric. The third saves source.json, a blank review.json and score.json. No support judgment or analyst participation is invented.

Inspect source.json and the referenced records. Make an edited copy of review.json, attribute the reviewer as human or AI, split material claims, give support rationales and review each requirement. Then score against the current verified run:

```sh
.venv/bin/python -m secops_triage.evaluation score --run data/case04-scripted --case case-04 --review data/case04-review-completed.json --output data/case04-reviewed
```

Each scoring command writes a new private directory containing source, review and result; it never overwrites a previous review. It does not record a final analyst decision, close an incident or alter spending. CLI success means artifacts were produced; read the score's outcome field for evaluation status. Changed source, rubric, evaluator, run or review binding requires a fresh review. Owner capabilities remain internal and are not exported.

Named live preparation now binds proposal digest and incident export to the stored run, and rechecks the named fixture before any key read or grant issuance. Selecting a case grants no paid authority. The old default single-message preparation remains available. Changes to live.py change engine identity; use fresh imports and preserve historical stores/reports. SQLite and the four-tool registry are unchanged.

## Remaining gates

Ariel's actual walkthrough and case adjudication are open. Nine distinct accepted cases, a fixed live campaign ledger, fresh spending authorization, live model claim reviews, and repeated hero success are still required for M2. UI work should address observed friction after M1.5. No claim of real-source enrichment, productivity gain or general SOC accuracy follows from these offline checks.

Verification: 249 full-suite tests passed in 64.524 seconds on unchanged source. The independently reviewed 21 evaluation/case tests cover supported/unsupported/pending results, wrong raw-model recommendations, omissions, tampering, case isolation and conflict scope. The final nine-read scripted demo remains pending semantic review. See outputs/secops-evaluation-validation.json for source hashes, packet identity, the superseded run, probe and runbook checks.
