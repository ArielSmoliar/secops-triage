# SecOps demo completion runbook

## Metadata

- **Status:** Draft — generated and reviewed; future milestones are not executed or newly authorized by this document.
- **Owner:** Ariel Smoliar, product scope and analyst acceptance.
- **Operator:** Codex for implementation and verification; Ariel for analyst walkthrough and external publication decisions.
- **Last verified:** 2026-09-07.
- **Environment:** Local macOS/Python, synthetic replay evidence, pinned Strands SDK and bounded OpenAI transport. No deployed environment verified.
- **Expected duration:** Planning estimate: 25–40 focused hours over September 8–13, subject to the open analyst-usefulness and source-quality gates. September 14 is a buffer, not a promised completion date.
- **Change/incident ID:** SECOPS-DEMO-COMPLETION; prior failed run 4ba7fadcc26965807baba68624ac767d.

### Verified target identity

Repository and inspected worktree: /Users/arielsmoliar/Developer/migration-proof. Remote: https://github.com/ArielSmoliar/migration-proof.git. Branch: main. Baseline HEAD: 5e73748ac50f626de4953bea0c96edf9b3311b0e. Tree: 23e8ef5404a6c337155642cbe2cae2f150d56fa9. Requested main and baseline commit matched; checkout was clean before documentation creation. The matching worktree is the same path. Origin main was independently checked with git ls-remote on 2026-09-07 during this review and matched HEAD. GitHub reports PRIVATE visibility and no detected license. This is a source stamp, not deployment evidence. Reverify the selected execution commit after any change; never treat this historical stamp as proof that later code is verified.

### Current review stamp

Independent AI plan/evidence reviews and an Impeccable product-flow consultation were requested on 2026-09-07. Inspected main: 570512542edff981536ea760b7cc272a934a02c5; tree: 959c74e6a9fe750aae23b4b014e6cc6a9b37ccd6. Requested main matched in the repository/worktree named above. Checkout was clean at task start; the later inspection contains only this task's new PRODUCT.md. Remote freshness was not required or fetched for this document review. The older stamp remains historical. See outputs/secops-independent-plan-review.md and docs/SECOPS-ANALYST-FLOW-REVIEW.md. These reviews do not constitute independent human SOC validation.

### Milestone dashboard

| Milestone | Deliverable | Exit criterion | Dependency | Planning target |
|---|---|---|---|---|
| M0 — Foundation | Deterministic backend and actual Strands integration | 174 tests passed; scripted replay works; first live failure preserved | Complete at baseline | Done |
| M1 — Complete a live investigation | Complete: see docs/SECOPS-COMPLETED-INVESTIGATION.md | All four tools, valid cited packet, escalation, settled usage and unchanged SIEM verified | Completed after explicitly approved live attempt | Done Sep 7 |
| M1.5 — Observe analyst usefulness | One recorded formative session with a decision and case note | Decisive citations found, competing explanation addressed, missing context and corrections recorded; no critical unsafe inference | M1; open, no session yet | Before paid M2 and full M3 build |
| M2 — Cover the three daily workflows | Nine distinct cases: close, escalate and incomplete for each family | Nine scored live runs; all material citations supported; no unsafe close; expected incomplete cases stay incomplete; hero case passes three consecutive runs | M1.5; source-quality, harness and scoring gates; separately budgeted campaign | Sep 9–10; 6–10 hours |
| M3 — Build the analyst workspace | Existing-incident selector, investigation progress, evidence, gaps, case note and local decision | Analyst completes the workflow without terminal use; evidence links and overrides work; duplicate actions are safe | M1.5 observed friction; M2 cases supply acceptance tests | Sep 10–11; 8–12 hours |
| M4 — Rehearse the complete demo | End-to-end run through the UI with a clear failure path | Three consecutive hero rehearsals; one close and one incomplete walkthrough; no hidden manual data repair | M2 + M3 | Sep 12; 4–6 hours |
| M5 — Package the demo | Reproducible checkout, architecture diagram, setup guide and video | Fresh-checkout run succeeds; video is at most five minutes; every product claim is supported | M4 | Sep 13; 4–6 hours |

M4 is the working-product finish line. M5 makes it reviewable and ready for publication. Submission and optional hosting have separate final approval gates. Targets are estimates, not evidence of progress.

## Objective

Demonstrate a Tier 1 analyst receiving an incident already created by a SIEM, obtaining its context and an evidence-backed close-or-escalate recommendation, and recording a local decision. Strands must perform real model-directed investigation; the analyst should spend their effort reviewing the decision instead of manually collecting and assembling the evidence.

## Scope

**Included**

- Suspicious sign-ins, reported phishing and endpoint alerts, each available as a separate incident in the demo.
- One headline phishing escalation story; endpoint close and sign-in missing-context stories demonstrate breadth and honest uncertainty.
- Synthetic source records clearly labeled as replay; real model inference clearly distinguished from scripted execution and recorded playback.
- A single local analyst workspace, evidence drill-down, draft case note, accept/override with reason, durable local review and restart behavior.
- Reproducible demo package and publication-readiness checks.

**Excluded**

- Real customer data, live SIEM/EDR/email connectors, containment, upstream case writes, arbitrary queries and multi-user production service claims.
- Competitive superiority, a production detection benchmark, a full SOC platform or unsupported time-saving percentages.
- AgentCore and AWS hosting as prerequisites for M1–M5. Optional hosting is evaluated after M4; no resources are provisioned by this runbook review.

**Must remain unchanged**

- SIEM incident ownership and status; historical migration evidence and closed spending grants.
- Agent tools remain read-only and scoped. Approval, promotion, spending authorization and analyst decisions remain host-only.
- Missing telemetry is not benign evidence. Existing citations cannot by themselves establish that a model interpretation is true.
- Failed runs and consumed reservations remain preserved; a retry requires its own authorization and fresh eligible run.

## Preconditions

- Verify the repository and selected commit; stop for an unexpected target or working-tree change. Do not switch branches or discard changes automatically.
- Baseline evidence: `outputs/secops-first-live-result.json` records the stopped live attempt and 174 passing follow-up tests. This review does not rerun those tests.
- Read `docs/SECOPS-FIRST-LIVE-RESULT.md`, `docs/SECOPS-STRANDS.md`, `secops_triage/agent.py`, `secops_triage/agent_spend.py` and `secops_triage/agent_runner.py` before implementing M1.
- Use the pinned optional agent dependencies and a private local output directory. Keep the ignored key and owner capabilities private.
- The earlier ten-request/$4.25 authorization is consumed and closed. No new paid execution is authorized by the request to write these milestones.
- Ariel acts as the domain reviewer for synthetic cases. No independent analyst availability, real source access or production-grade dataset is assumed.
- Readiness facts from the official Devpost tools were retrieved on 2026-09-07: deadline September 14, 2026, 5:00 p.m. PDT / 8:00 p.m. EDT. Aim to finish the package September 13.
- Official requirements: https://agentsforhumans.devpost.com/rules and https://agentsforhumans.devpost.com/ . The guidance says “Install the Strands Agents SDK” and describes AgentCore as “not required.” The submission form calls for a public code URL, MIT or Apache license, README/setup assets, architecture diagram, AWS Builder ID and a demo video of at most five minutes. A hosted live-demo link is optional. Recheck at publication; this review does not establish personal eligibility or submit anything.

## Risk and stop conditions

- **Historical risk:** Two live attempts stopped before the third succeeded. The first exact response failure remains unknown; M1 success establishes one working execution, not a reliability rate for the current build.
- **Risk:** The historical single-run bounds were one alert and ten requests/nine tools; every historical grant is closed. The three-alert scripted example needs 19 tools and 20 turns. Those historical bounds do not authorize a combined paid acceptance scenario. Keep separate incidents for the core demo; any combined live scenario needs a reviewed budget/contract change first.
- **Risk:** There is little headroom for model-selected follow-up calls. If the live test reaches a limit, record a failed/incomplete outcome and review query efficiency or a separately approved bound; never silently increase limits.
- **Risk:** The store uses a POSIX lock and local files and serializes investigations. A serverless or multi-worker deployment cannot be assumed to preserve its guarantees.
- **Stop immediately if:** a response can expand tool authority, evidence crosses incident/tenant scope, a secret appears in output, a stale review becomes current, spending exceeds its grant, or source-system mutation occurs.
- **Stop the affected milestone if:** a required verification is missing, the model invents material evidence, missing checks permit closure, the selected build changes during a run, or expected output cannot be reproduced.
- Repeated failure is not a reason to keep sampling until one good run appears. Record all attempts, separate diagnosis from acceptance, and disclose the sample size.

## Evidence plan

- Record source commit, SDK/model identity, fixture digest, query trace, immutable evidence IDs, outcome, safe failure stages, model/tool counts, usage, timing and reviewer corrections.
- Store sanitized validation records in outputs and concise milestone notes in docs. Put run databases, raw replay artifacts and private ownership files only under ignored data directories.
- Retain all failed and successful runs through demo review. Do not delete evidence as part of retry or rollback. Decide post-event retention separately.
- Never record API keys, owner capabilities, credential files, raw exception text or real customer content. Only approved synthetic data may be sent to the provider.
- For M2, keep expected labels and justifications out of agent-visible inputs. Fix the evaluation set before testing and record any tuning cases separately.
- For UI/rehearsal evidence, distinguish wall time, analyst review time and manual corrections. Do not turn a small internal rehearsal into a claim of measured customer productivity.

## Procedure

### Active prerequisite: analyst usefulness and evaluation readiness

A. **Action (reversible):** Conduct the existing phishing walkthrough and record the participant's actual decision, case note, decisive citations, missing context, corrections and next action. Keep the observations blank until the participant responds; do not treat instructions to continue as domain approval.
   - **Expected result:** Direct evidence of which context the analyst still reconstructs and which parts of the handoff help.
   - **Verify:** The participant can find supporting and conflicting source records and give a bounded next action. Record critical errors even if the overall disposition matches. One owner session is formative, not independent SOC validation or proof of time savings.
   - **If verification fails:** Resolve the observed flow/source gap and repeat a scoped session before paid breadth evaluation or a full UI build.
   - **Approval required:** None for preparation; participation and observations must be real.

B. **Action (reversible):** Improve the source contract and freeze independently reviewed case expectations. Include inspectable intelligence match value/type, provenance, freshness and rationale, and machine-readable authorization validity/scope. Test stale, wrong-target and revoked/out-of-scope authorization cases. Preserve unavailable evidence explicitly.
   - **Expected result:** The case requires inspecting message, time and match relationships rather than copying a supplied malicious label. A two-message phishing case is the proposed stress case; the reviewer must adjudicate its outcome after inspecting all evidence.
   - **Verify:** Wrong-message, expired/revoked authorization and unsupported-compromise checks fail safely; exact matches remain distinguishable. Broader multi-provider ingestion is not required for this increment.
   - **If verification fails:** Keep the case as a disclosed teaching fixture; do not count it as deeper investigative validation.
   - **Approval required:** None for local implementation and offline verification. Original-source details added to synthetic fixtures remain clearly synthetic.

C. **Action (reversible):** Add fixture-selectable preparation and an evaluation record before the M2 campaign. Score raw model recommendation, each material claim, claim-to-citation support, omissions, deterministic outcome, reconciliation disagreement and final packet separately. Keep expected answers outside agent-visible input.
   - **Expected result:** A correct deterministic escalation cannot conceal an incorrect model assessment. A valid citation alone cannot pass an unsupported claim.
   - **Verify:** Negative evaluation examples include invented credential theft from a click, unavailable telemetry described as clean, stale intelligence, unrelated entities, truncation and injected source instructions. Separate offline tests from live-case results.
   - **If verification fails:** Keep paid evaluation pending; repair the evaluator or contract first.
   - **Approval required:** None for offline preparation. No grant is created here.

D. **Action (read-only planning):** Enumerate every paid run by fixture digest, purpose, execution build, bounds and assigned campaign slot. M2 is nine cases plus two additional hero runs; M4's three finished-UI hero runs are separate executions. State whether alternate M4 walkthroughs are fresh inference or saved playback. Do not double-count an M2 run as a finished-UI rehearsal.
   - **Expected result:** One concrete campaign ledger distinguishes acceptance, diagnosis and rehearsal. Historical grants remain closed.
   - **Verify:** Every proposed live execution has explicit unconsumed authority; every failure remains in results. No slot or retry exists outside the approved ledger.
   - **If verification fails:** Revise the proposal before requesting or using a spending grant.
   - **Approval required:** Owner approval of the eventual exact spending proposal, not of this planning document.

The completed M1 procedure below is retained for traceability. Do not restart it merely because it appears earlier in this document.

### Phase 1 — M1: completed historical procedure

1. **Action (read-only):** Reverify the target and inspect the failed run record and the new safe stage logging. The current fourth response cannot be reconstructed from retained evidence.
   - **Expected result:** A documented distinction between observed facts and hypotheses; no claim that the existing failure is fixed.
   - **Verify:** Trace the current final-output and tool-argument validation paths in `secops_triage/agent.py`; confirm the new rejection-journal regression test exists in `tests/test_secops_agent.py`.
   - **If verification fails:** Repair diagnostics offline before any paid dispatch.
   - **Approval required:** None for inspection or scoped local fixes.

2. **Action (reversible):** Implement a reproducible host command or operator harness for preparing a fresh synthetic run, showing its bounded plan, executing an explicitly authorized grant, and exporting a sanitized result. Reuse the existing supervised runner; do not call the internal session seam as a public endpoint. Test malformed dates, templates, extra arguments and final citations without paid calls.
   - **Expected result:** A verified execution procedure that does not depend on temporary scripts from previous tasks.
   - **Verify:** Locked tests pass; command/help paths are checked before being added to the execution record. No nonexistent future CLI command is supplied here.
   - **If verification fails:** Keep the milestone open; do not compensate by loosening the four-tool boundary.
   - **Approval required:** None for the local implementation within the agreed scope.

3. **Action (external paid change):** Prepare a fresh single-phishing run at the verified commit. Present its exact model, ten-request/nine-tool/120-second scope and price-verified ceiling. After owner authorization, issue one grant and execute once. If it stops, inspect the new stage record and reproduce the identified defect offline before proposing another run.
   - **Expected result:** Either a diagnosed stopped attempt or a complete real-model investigation. Only the latter satisfies M1.
   - **Verify:** The saved packet cites returned records; inspect, entity lookup, activity query and related-case lookup all occurred; malicious delivery/interaction evidence supports escalation; usage settled; grant closed; SIEM unchanged.
   - **If verification fails:** Preserve the failed run, close remaining grant authority, and stop paid execution. Do not reuse the failed run after changing engine identity.
   - **Approval required:** New paid-run approval from Ariel. This is required by the consumed single-attempt authorization, not by the mere act of drafting a runbook.

### Phase 2 — M2: validate all three families

4. **Action (reversible):** Author and review nine materially distinct synthetic incidents: close, escalate and missing-context outcomes for each family. Include a misleading benign cue or unrelated event where appropriate; do not merely rename the same records. Fix expected facts and required checks separately from inputs.
   - **Expected result:** Cases require evidence gathering and distinguish observed activity from inferred compromise.
   - **Verify:** Ariel reviews event chronology and entity joins. A delivered message, click, execution and credential compromise are not conflated. Similar entities alone do not establish an attack chain.
   - **If verification fails:** Correct the fixtures and labels before evaluation; retain the revision history.
   - **Approval required:** None for local drafting; domain review completes the fixture acceptance step.

5. **Action (external paid change):** Prepare one bounded evaluation campaign with exact fixture digests, maximum runs/requests, total reserved exposure and stop conditions. Obtain campaign authorization once, then execute only its included fresh-run grants. Score nine cases, plus two additional hero runs so the headline case has three consecutive passes on the frozen build.
   - **Expected result:** Nine of nine expected dispositions/abstentions match; no fabricated material finding, no unsafe close, all material citations support their claims, and no hidden failed run is discarded. Three of three consecutive hero runs pass.
   - **Verify:** Review every finding against its cited source, not only JSON validity. Report per-family results, failure counts, over-escalations, missing-check visibility, latency and actual cost. These are demo acceptance targets, not statistically established production reliability.
   - **If verification fails:** Mark M2 incomplete; fix and rerun only within an explicitly approved remaining scope or a new campaign. Do not treat mass abstention as success.
   - **Approval required:** Ariel approves the concrete campaign budget. No aggregate budget is granted here.

### Phase 3 — M3: build the analyst workspace

6. **Action (reversible):** First implement a durable unresolved-handoff record distinct from final close/escalate review; store.review currently supports only those two final dispositions. Then build one incident investigation screen: existing source incident selector; real collection status; entities and timeline; recommendation and gaps; clickable evidence; draft case note; accept/override with a reason. Use local review semantics already implemented in `secops_triage/store.py`.
   - **Expected result:** One primary action starts investigation; the analyst reviews a prepared packet rather than issuing individual collection prompts. A pending or failed run never appears complete.
   - **Verify:** Browser tests cover one successful run, missing telemetry, model failure, duplicate start, reload/restart, evidence navigation, adjacent model/policy disagreement, unresolved-handoff save/reload, override and stale packet review. An analyst can finish without terminal commands. Label every recorded/scripted mode explicitly.
   - **If verification fails:** Correct the interaction or binding; do not patch display data manually to finish the demo.
   - **Approval required:** No extra permission for local reversible UI work once this milestone is selected for execution; external publication remains separate.

### Phase 4 — M4: rehearse the complete experience

7. **Action (reversible; paid only when covered by an approved campaign):** Rehearse the hero case three consecutive times through the finished UI, then walk through the endpoint-close and sign-in-incomplete cases. Show the existing SIEM incident ID, automatic evidence gathering, a cited finding, an unresolved check where relevant, and the analyst decision.
   - **Expected result:** Three hero passes without manual repair; a clear close path; a clear incomplete path. Local decision persistence never claims to update the SIEM.
   - **Verify:** Check fresh run IDs, stored packets/reviews, bounded costs, time to packet, review/correction time and saved case note. Ariel confirms that the next analyst action is obvious and required context is accessible.
   - **If verification fails:** Return to the specific failing milestone. Preserve an explicitly labeled recorded playback only as a presentation fallback; it does not count as a new live pass.
   - **Approval required:** Reuse only explicit unconsumed campaign scope; recording locally needs no external publication approval.

### Phase 5 — M5: package and review

8. **Action (reversible):** Freeze a candidate commit, write exact setup instructions, prepare an architecture diagram and record a video of at most five minutes. Suggested narrative: 30 seconds for analyst problem, three minutes for the working investigation, one minute for close/incomplete alternatives, 30 seconds for architecture and limits.
   - **Expected result:** Another operator reproduces the demo from a fresh checkout. The video shows working software and accurately identifies Strands, OpenAI and replay data.
   - **Verify:** Fresh-checkout tests and rehearsals pass; links resolve; no secrets appear; all source/assets required to run are present; provenance and any playback are visible. Select and review the intended MIT or Apache license; none is currently detected in GitHub.
   - **If verification fails:** Keep the package private and incomplete until corrected. Do not claim submission readiness from a working local report alone.
   - **Approval required:** None for preparing the local package. Public repository/video publication, license adoption and Devpost submission require their concrete owner decisions after review.

9. **Action (read-only planning; optional external deployment later):** After M4, decide whether a hosted demo or AgentCore is worth the remaining time. If chosen, first resolve durable persistence, identity, one-writer behavior, secrets, hard cost limits, health checks and teardown with exact resource IDs. Validate a staged deployment before publishing its URL.
   - **Expected result:** Optional hosting improves access without jeopardizing M5. No cloud deployment is inferred from passing local tests.
   - **Verify:** A separate deploy procedure names the actual platform, region, storage, budget, rollback and external monitoring before provisioning. No deployment commands are invented in this local runbook.
   - **If verification fails:** Omit hosted access and AgentCore; retain the working local demo, video and reproducible source.
   - **Approval required:** Specific resource/cost and public-access approval; this plan creates none.

### Verified local commands

Run only from the verified repository and after selecting the intended execution commit. These commands validate current code; they do not call the live model or create a paid grant.

```sh
cd /Users/arielsmoliar/Developer/migration-proof
git status --short
git rev-parse HEAD
/Users/arielsmoliar/.local/bin/uv sync --frozen --extra agent --offline
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m migration_proof.probe
demo_parent="$(mktemp -d /private/tmp/secops-demo.XXXXXX)"
.venv/bin/python -m secops_triage demo --strands --output "$demo_parent/replay"
```

Historical M0 baseline: 174 tests. Current test counts must be captured from the selected execution build; probe returns original 403, deliberately faulty 200 with the expected leak, corrected 403. The final command is a real SDK loop with a scripted provider and must be described that way. If locked dependencies are not cached, stop and resolve installation; do not silently change package versions.

## Rollback

- **Trigger:** Any stop condition, failed milestone verification, budget uncertainty, or broken candidate UI.
- **Decision owner:** Ariel owns scope/spending/publication decisions; Codex performs scoped local containment and evidence preservation.
- **Actions:** Stop launching new runs. Let the supervised worker terminate within its bound; do not retry. After worker exit, the existing agent_runner.recover host function can mark interrupted collection and grants safely. Check the saved failed state, request reservations and closed grant before proceeding. Preserve the store and artifacts; recovery is not permission for another paid run.
- **Source/UI recovery:** Keep the last verified commit and its compatible artifacts. Use an isolated checkout for a previous verified presentation build or make a forward corrective commit; do not reset the working repository or open an old store with incompatible code. During a broken UI, use the previously saved Markdown evidence report for review, clearly labeled as a saved run.
- **Corruption:** Do not delete or rewrite a damaged store. Preserve it for inspection and use a new isolated store only after fixing the defect. Never mark evidence complete to recover a demo.
- **Verification:** No process is still spending; no pending request is mistaken for settled usage; no failed run has a new packet or review; original source incident remains unchanged.
- **Limitations:** Paid calls cannot be undone or refunded by rollback. Public release cannot reliably retract copies; this runbook therefore stops before publication without a reviewed release target and owner approval. Optional cloud work requires its own independently executable teardown before resources are created.

## Completion criteria

- M1 has a completed real-model investigation, not only successful connectivity or scripted output.
- M1.5 records an actual formative analyst session and resolves critical handoff failures.
- M2 records raw-model and final-packet outcomes separately and scores material claim support. M2 covers all three alert families and all three outcome classes with reviewed evidence, including three consecutive hero passes.
- M3 lets the analyst investigate, inspect evidence and record a local decision without terminal use.
- M4 passes the finished-UI rehearsals and shows failure/missing-context honestly.
- M5 reproduces from the frozen checkout and supplies a truthful five-minute-or-shorter video and architecture/setup package.
- All paid attempts stay within explicit authority and retain complete accounting or clearly preserved uncertainty; no upstream mutations or secret exposure occur.
- Optional hosting does not block local demo completion. Public submission readiness remains a separate check of repository visibility/license, video access, required fields and deadline.

## Communications

- **Start:** Codex reports the milestone, exact target and authorized scope in this task.
- **Failure:** Report observed stage, affected run, retained evidence and spend status; distinguish hypothesis from verified cause. No automatic external messages.
- **Completion:** Report deliverable links, tests, sample sizes, commit, unresolved limits and next milestone in this task. Ariel reviews product behavior and authorizes concrete external actions when ready.

## Record

- **Started:** Runbook generation and review on 2026-09-07.
- **Completed:** Documentation generation/review followed by M1 completion; M2–M5 remain open.
- **Operator:** Codex, using Generate Runbook 0.3.0.
- **Approvals:** This task requests milestones and review. Prior live attempt was explicitly approved, consumed and closed. No new campaign, publication or deployment approved.
- **Outcome:** Proposed critical path and objective exit gates; structural validation and drift review are recorded separately in the runbook review artifact.
- **Deviations:** No deployment commands are supplied because the platform is unselected. No live execution command is invented; a reproducible operator harness is an M1 deliverable. Source tests are cited from the prior verified result, not claimed rerun for this documentation task.
- **Follow-up:** Complete M1.5 observed usefulness, source-quality and offline scoring/harness gates before a paid M2 campaign. Use the reviewed analyst-flow specification to address observed friction.
- **Next verification:** At each milestone start and whenever source, model, fixture, budget, dependency or release target changes; recheck hackathon requirements before publication.
