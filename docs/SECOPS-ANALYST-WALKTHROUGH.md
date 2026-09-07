# Phishing analyst walkthrough

This is a prepared formative exercise, not a completed analyst study. It strengthens the existing phishing story with a competing explanation: the message may belong to an approved awareness simulation. Three matched synthetic variants exercise close, escalate and missing-context decisions. The newly generated reports use deterministic replay, not new model responses. The separately preserved M1 report remains the evidence of a real-model investigation.

## Generate the kit

From the repository, run:

```sh
.venv/bin/python -m secops_triage.drill --output data/secops-analyst-drill
```

Use a new directory on each run. No API key, model grant, network access or SIEM write is involved. Each case has a manual source folder, assisted report, immutable evidence store, packet and snapshot. A private owner capability is saved with mode 0600; do not share it. The manifest records snapshot and packet hashes. The observations CSV starts empty; generated files are not analyst results. The current local kit is data/secops-analyst-handoff. The earlier reviewed kit remains preserved at data/secops-analyst-drill-reviewed. Evidence links are absolute local paths: conduct this first session on this computer; copying just the report elsewhere will break links.

## Shared instructions and demo policy

Give these instructions to every participant, regardless of condition:

“You are reviewing an existing SIEM incident reporting a document-sharing email. Decide close, escalate, or needs_review. Supply a short case note with evidence references, the strongest competing explanation, missing context and the next action. Your answer does not change the SIEM.”

For this deliberately narrow exercise, close requires authorization tied to the exact message, complete required source coverage and no observed suspicious evidence. A conflicting malicious indicator requires escalation for further investigation. Unavailable intelligence prevents closure; report needs_review when no other evidence independently supports escalation. This is a demo policy, not production incident-response guidance. Source completeness and campaign authorization are trusted synthetic assertions.

Both conditions receive the same bounded source results, including coverage metadata. The manual folder separates incident details, entities, message, delivery, interactions, intelligence, business context and prior cases. The assisted condition gets the assembled report and all of its evidence links. These are normalized source exports, not a recreation of vendor consoles or their real navigation costs.

## Five-minute product walkthrough

1. **0:00–0:40 — Existing incident.** Open case-02/manual/inspect_incident.json. The SIEM has already opened the incident. The analyst needs context, not another alert.
2. **0:40–1:30 — Plausible benign explanation.** Inspect the message and business context: passing authentication, a documented simulation and an earlier benign case. Explain why each cue needs scope checking. The authorization event at 10:02 records retrieved confirmation of prior approval; it is not a pre-event timestamp.
3. **1:30–2:40 — Contradiction.** Open case-02/assisted.md. Follow the authorization and malicious-indicator citations. Both target the same message; the report preserves the conflict. An allowed click does not prove credential entry, compromise or user authorization.
4. **2:40–3:40 — Reviewable handoff.** Read the timeline and coverage. Draft the decision: escalate the unresolved campaign/intelligence conflict; verify campaign scope and indicator accuracy. Do not claim containment or a final analyst decision has occurred.
5. **3:40–4:30 — Change the evidence.** Briefly show case-01 (documented simulation with complete checks) and case-03 (intelligence unavailable). The conclusion changes with evidence, and missing context stays visible.
6. **4:30–5:00 — Provenance.** Identify this walkthrough as deterministic synthetic replay. Refer separately to docs/SECOPS-COMPLETED-INVESTIGATION.md for the real-model run and its measured runtime. Do not attribute its 19.2-second runtime to these new scenarios.

## Observe an analyst session

For a guided product walkthrough, start with the conflict case and ask the analyst to explain what they trust, what they must verify, and what context they still need. Record their actual words and corrections. Stop timing when they submit an evidence-backed decision and case note, not when the report loads.

For a comparison, assign a participant only one condition for a given case. Keep this facilitator document, manifest, snapshots, alternate reports and expected outcomes hidden until debrief. Counterbalance condition and case order across participants; give everyone the same policy and available evidence. Do not compare a person's manual pass with their second assisted pass on the same case as a time-savings measurement: they already know the answer. These three variants also share a structure and are teaching cases; a stronger study needs separately authored matched incidents and independent domain review.

Record participant pseudonym, condition, order, timestamps, elapsed time, disposition, citations, missing context, next action, unsupported claims, material corrections and score in observations.csv. Add source-open count and analyst confidence to notes. Record loading/collection latency separately from analyst review time. Leave unobserved values blank. Never populate results from model or developer guesses.

## Facilitator key and rubric — do not show before decision

| Case | Expected demo disposition | Decisive reasoning |
|---|---|---|
| case-01 | Close | Exact-message simulation attestation; full required coverage; no observed suspicious evidence. Passing authentication and prior benign cases alone are insufficient. |
| case-02 | Escalate | Exact-message authorization conflicts with a same-message malicious indicator. Validate both; do not infer confirmed compromise. |
| case-03 | needs_review | Simulation attestation exists, but intelligence is unavailable. The missing source is not a successful empty result. Restore access or obtain equivalent approved evidence. |

Score each criterion 0 (absent/incorrect), 1 (partial), or 2 (complete): disposition; decisive evidence with correct references; competing explanation; coverage and bounded uncertainty; actionable case note. Maximum 10. Flag a critical error regardless of score for closing case-02/03, treating unavailable intelligence as clean, citing the wrong message, or asserting confirmed compromise.

Report individual observed times and quality scores before aggregates. Any apparent speed improvement accompanied by unsafe closure or unsupported claims fails the product hypothesis. One internal analyst session can reveal usability problems; it cannot establish production reliability, causal productivity gains or competitive superiority.

## Current evidence and next gate

Automated checks verify the three policy outcomes, conflict/gap visibility, nine reads per case, equal manual/assisted source results, private capability files, zero recorded reviews and refusal to overwrite an existing kit. A separate reviewer challenged scenario scope and the measurement design. These are engineering and design checks; no independent analyst session has happened.

The next gate is an observed walkthrough with Ariel or a Tier 1 analyst: can they reach a defensible decision, follow the decisive citations and identify remaining uncertainty without reconstructing the entire investigation? Save the observations before expanding the UI or making productivity claims. M2's broader nine-case live evaluation and repeated hero runs remain incomplete and separately budgeted.

## Handoff presentation update

The current report leads with the scoped recommendation and cites both authorization and suspicious observations. It lists unresolved intelligence questions: the normalized indicator contract has no dedicated indicator-value, provider, confidence or verdict-explanation fields. The receiving analyst is asked to obtain the original intelligence report and validate the exact match, freshness and explanation. No such external lookup has run; this is an explicit follow-up, not newly collected evidence.

Source gaps such as unavailable intelligence link to the query evidence. Open questions also appear in the draft case note. Complete collection is explicitly distinguished from incident resolution or confirmed compromise. Report rendering does not change the packet, recommendation or review records. The current kit remains deterministic synthetic replay; no analyst feedback or disposition was inferred from the owner's instruction to continue.

Verification: 67 SecOps tests passed in 3.726 seconds, including four new handoff tests for conflicting evidence, missing intelligence, authorized activity and escaped source labels. See outputs/secops-handoff-validation.json.
