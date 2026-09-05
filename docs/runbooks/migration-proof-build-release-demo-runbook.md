# Migration Proof — Build, Release, and Demo Runbook

## Metadata

| Field | Value |
|---|---|
| Status | Reviewed draft; executable through Phase 1 only |
| Owner | Ariel Smoliar |
| Operators | Ariel Smoliar; Codex for implementation support |
| Repository | `/Users/arielsmoliar/Developer/migration-proof` |
| Reviewed baseline | Git commit `878c13f9f17487cac2df0533a2ee3c6940a29a83` |
| Track | Professional Agents |
| Target | Agents for Humans hackathon |
| Last reviewed | 2026-09-05 |
| Estimated build window | 7–10 focused days, subject to AWS access and deployment choices |

## Objective

Build and publicly demonstrate **Migration Proof**, an evidence-backed acceptance agent for software migrations. The demo must show that ordinary tests can pass while a tenant-boundary regression is detected, safely repaired, re-verified, approved by a human, and recorded in an auditable decision packet.

The agent uses the Strands Agents SDK for planning, tool selection, safe-repair decisions, and explanations. Deterministic application code—not the model—owns policy enforcement, evidence hashing, approval, promotion, and receipt generation.

## Scope

### In scope

- A deterministic three-revision fixture: `original`, `faulty`, and `corrected`.
- A Strands agent with only these operational tools:
  - `inspect_candidate`
  - `run_baseline_tests`
  - `compare_tenant_boundary`
  - `apply_safe_patch`
- Durable run, evidence, approval, and promotion records in SQLite plus an evidence directory.
- An operator UI that exposes state, evidence, stop conditions, and the approval boundary.
- A public AWS-hosted demo.
- A repeatable demo script and submission-ready evidence.
- AgentCore only as a stretch enhancement after the baseline deployment is stable.

### Out of scope

- Autonomous production deployment.
- Giving the model approval or promotion capabilities.
- Arbitrary code execution or unrestricted shell access through agent tools.
- General-purpose migration support beyond the controlled tenant-boundary scenario.
- AgentCore as a prerequisite for the first working release.

## Verified facts

- The repository is a clean Git repository on branch `main` at the reviewed baseline commit above.
- No Git remote is configured at review time.
- The standard-library fixture and probe exist.
- `python3 -m unittest discover -s tests -v` passes four tests.
- `python3 -m migration_proof.probe` produces the intended sequence:
  - `original`: expected 403, actual 403, pass
  - `faulty`: expected 403, actual 200 with `id`, `tenant`, and `title` exposed, fail
  - `corrected`: expected 403, actual 403, pass
- The current repository does not yet contain the Strands orchestration, SQLite record store, evidence directory, operator UI, or AWS deployment configuration.

## Assumptions to resolve

- The AWS account, target region, budget guardrails, and credentials are available to the owner.
- The chosen model is enabled in the target region and usable through the selected Strands model provider.
- The public deployment service, hostname, authentication posture, and teardown policy are not yet selected.
- The hackathon submission deadline and current submission requirements must be rechecked before release because they are external and time-sensitive.
- The final deployment commands cannot be specified safely until infrastructure configuration exists and has been tested in a non-production environment.

## Safety classification

| Class | Examples in this runbook | Control |
|---|---|---|
| Read-only | Inspect source, run tests, run probe, view evidence | May run without approval |
| Reversible | Create code, local database, deployment staging resources | Require verification and a recorded checkpoint |
| Consequential | Public deployment, spend-bearing AWS resources, promotion | Human approval required immediately before action |
| Destructive | Resource teardown, deleting evidence or databases | Explicit owner approval and a verified backup/retention decision |

## Preconditions

- Work from the repository path recorded in Metadata.
- Confirm `git status --short` is empty before each release phase.
- Record the current commit SHA before collecting evidence.
- Use a dedicated non-production AWS environment and least-privilege credentials.
- Establish a hard budget alert before creating persistent AWS resources.
- Never place AWS credentials, model credentials, tenant tokens, or sensitive evidence in Git.
- Keep approval and promotion endpoints outside the Strands tool registry.
- Assign a unique run ID and run-scoped working directory to every evaluation.

## Risk and stop conditions

Stop immediately and preserve evidence if any of the following occurs:

- Ordinary baseline tests fail unexpectedly.
- The `original` or `corrected` revision returns anything other than 403 for cross-tenant access.
- The faulty revision cannot be distinguished from the safe revisions.
- A model can invoke approval, promotion, arbitrary shell execution, or unrestricted filesystem/network access.
- Evidence hashes do not reproduce, records cross run boundaries, or concurrent runs share mutable state.
- A restart produces an ambiguous state that could be mistaken for approval or promotion.
- Deployment would expose credentials, tenant data, an unauthenticated mutating endpoint, or unbounded model/AWS spend.
- The public demo cannot be rolled back or disabled promptly.

Escalate these conditions to the owner. Do not “work around” a failed safety invariant to preserve the demo flow.

## Evidence plan

For each run, retain:

- Git commit SHA and application version.
- Run ID, timestamps, state transitions, and tool invocations.
- Baseline test result and tenant-boundary comparison result.
- Candidate and repaired artifact hashes.
- Patch or structured repair description.
- Model/provider identifiers and the agent's explanation.
- Approval actor, timestamp, decision, and content hash.
- Promotion receipt or explicit “not promoted” result.
- Screenshot or recording of the end-to-end operator flow.

Evidence is immutable after approval. A content change invalidates the prior approval and requires a new decision packet.

Preservation invariant: the evidence, logs, hashes, approval record, and promotion receipt needed to explain a run **must remain unchanged** during rollback, recovery, redeployment, and teardown. Preserve those records before changing operational state.

## Procedure

### 1. Re-establish the known-good fixture

**Classification:** Read-only

**Action**

1. Confirm the repository path and current commit.
2. Confirm the worktree is clean.
3. Run:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 -m migration_proof.probe
   ```

**Expected result**

- Four tests pass.
- The probe reports `403 → 200 with leaked fields → 403` for original, faulty, and corrected revisions.

**Verify**

- Save command output with the commit SHA in the run evidence.
- Confirm the faulty response exposes only synthetic fixture data.

**Failure handling**

- Stop. Do not build orchestration on an unstable fixture.
- Diagnose the fixture or test regression and repeat this phase from a clean commit.

**Approval**

- None required.

### 2. Implement deterministic domain and record layers

**Classification:** Reversible

**Action**

1. Define typed inputs and outputs for the four agent tools.
2. Implement run-scoped artifact handling and SHA-256 hashing.
3. Implement SQLite records for runs, transitions, evidence, approvals, and promotions.
4. Implement the state machine and restart behavior described in the approved design.
5. Ensure decision-packet assembly, approval, and promotion live outside the agent tool registry.

**Expected result**

- Every transition is deterministic, validated, and attributable to one run.
- Replaying or restarting cannot manufacture an approval or promotion.

**Verify**

- Add and pass tests for legal/illegal transitions, hash mismatch, run isolation, crash recovery, and approval invalidation.
- Inspect the registered tool list and confirm it contains exactly the four scoped tools.

**Failure handling**

- Stop on any cross-run contamination, mutable approved evidence, or illegal transition.
- Preserve the database and logs for diagnosis; do not reuse the affected run ID.

**Approval**

- Owner review required before connecting a model.

### 3. Add Strands orchestration

**Classification:** Reversible

**Action**

1. Add the Strands Agents SDK using a pinned, documented dependency version.
2. Configure a model supported by the chosen deployment environment.
3. Give the agent only the four scoped tools.
4. Prompt the agent to inspect, test, compare, decide whether the known repair is safe, apply it when appropriate, re-run evidence, and explain the outcome.
5. Enforce iteration, tool-call, timeout, and spend limits in deterministic code.

**Expected result**

- The agent detects the faulty migration, applies only the allowlisted repair, and explains why the post-repair evidence is acceptable.
- Unsupported or ambiguous cases stop for human review.

**Verify**

- Run deterministic unit tests without a live model.
- Run a bounded live-model integration test in the non-production environment.
- Confirm attempts to call unregistered tools or alter approval state fail closed.

**Failure handling**

- Stop after the configured limit or on malformed tool arguments.
- Mark the run `needs_review`; retain the transcript and evidence.
- Do not silently substitute a broader tool or grant new permissions.

**Approval**

- Owner approval required before enabling live model calls that incur cost.

### 4. Build the operator experience

**Classification:** Reversible

**Action**

1. Show candidate identity, current state, baseline result, boundary comparison, repair, re-verification, and evidence hashes.
2. Present the decision packet before the human approval control.
3. Keep approval and promotion as explicit backend actions with clear actor attribution.
4. Make stopped, failed, stale, and recovered states visually distinct from accepted states.

**Expected result**

- A reviewer can understand the failure and repair without reading raw logs.
- No screen implies that the model approved or deployed the change.

**Verify**

- Exercise the happy path, failed repair, stale approval, page reload, and duplicate-submit scenarios.
- Capture screenshots at the detected-failure, repaired-evidence, and approval-receipt states.

**Failure handling**

- Disable approval/promotion controls if evidence is missing, stale, or inconsistent.
- Stop release for misleading state presentation or inaccessible critical controls.

**Approval**

- Owner accepts the final demo flow before deployment.

### 5. Select and provision the AWS baseline

**Classification:** Consequential

**Action**

1. Choose the smallest public AWS architecture that supports the application, persistent evidence, and bounded model access.
2. Record region, service choices, estimated spend, authentication posture, logging, retention, and teardown steps.
3. Confirm the selected Strands model provider and model access in that region.
4. Create a staging deployment before any public endpoint.

**Expected result**

- Staging is reachable by the operator, isolated from unrelated workloads, observable, and cost-bounded.

**Verify**

- Run health checks and the full synthetic scenario in staging.
- Confirm secrets are sourced from an AWS secret/configuration service and absent from logs and artifacts.
- Confirm budget alerts and a tested disable/rollback path.

**Failure handling**

- Stop on missing access, uncertain cost, unsafe authentication, failed health checks, or unavailable rollback.
- Do not add AgentCore merely to compensate for an unstable baseline.

**Approval**

- Explicit owner approval immediately before provisioning spend-bearing persistent resources.

### 6. Release the public demo

**Classification:** Consequential

**Action**

1. Pin the release commit and record the deployment artifact hash.
2. Re-run all automated tests on that commit.
3. Deploy the tested artifact using the deployment procedure established and verified in Phase 5.
4. Run one end-to-end synthetic acceptance flow against the public endpoint.

**Expected result**

- The public system produces a complete decision packet and requires human approval before promotion.

**Verify**

- Confirm public health, TLS, expected access controls, logs, metrics, and evidence persistence.
- Confirm the displayed commit/artifact hashes match the deployed release.
- Confirm a rejected or abandoned run cannot promote.

**Failure handling**

- Disable the public endpoint or roll back to the last verified artifact.
- Preserve failed deployment logs and evidence.

**Approval**

- Explicit owner approval immediately before public release.
- Separate explicit human approval is required for each demonstrated promotion.

### 7. Rehearse and record the demo

**Classification:** Read-only, except for explicitly approved synthetic promotion

**Action**

1. Rehearse a concise story: ordinary tests pass; hidden boundary test fails; agent applies the constrained repair; deterministic verification passes; human approves; receipt is recorded.
2. Use only synthetic fixture data.
3. Record a fallback video and capture submission screenshots.

**Expected result**

- The story is understandable end to end and demonstrates real work, model judgment, deterministic safety, and AWS operation.

**Verify**

- A fresh reviewer can identify the problem, agent contribution, human boundary, and evidence of success.
- The fallback recording contains no secrets, personal data, browser notifications, or unrelated tabs.

**Failure handling**

- Do not record around an unstable live flow. Fix or use the last verified build.
- Redact and re-record any exposed secret or personal information.

**Approval**

- Owner approves the final recording and screenshots for submission use.

### 8. Prepare submission materials

**Classification:** Reversible until Devpost submission

**Action**

1. Recheck current official rules, deadline, required fields, and judging criteria.
2. Prepare the project description, architecture, testing notes, repository link, public demo link, screenshots, and video.
3. State accurately where Strands and AWS are used; do not claim AgentCore unless it is running and evidenced.
4. Perform the hackathon readiness review before submission.

**Expected result**

- Every claim is supported by the release commit, public demo, or retained evidence.

**Verify**

- Check all links in a signed-out browser session.
- Compare the submission copy to the deployed architecture and final demo.

**Failure handling**

- Hold submission for missing required fields, broken links, unsupported claims, or rule conflicts.

**Approval**

- Explicit owner confirmation is required before final Devpost submission.

## Rollback

- Application rollback: redeploy the last verified immutable artifact; never patch the public instance in place.
- Public-access rollback: disable or restrict the endpoint while retaining logs and evidence.
- Run recovery: resume only from a persisted legal state; otherwise mark the run `needs_review` and start a new run ID.
- Approval recovery: any artifact or decision-packet hash change invalidates approval and requires a fresh approval.
- Data recovery: back up the SQLite database and evidence directory before migrations; restore both as one consistency unit.
- AWS teardown: execute only from a reviewed resource inventory, retain required evidence first, and obtain explicit owner approval for deletion.

## Completion criteria

The build is ready for submission only when all are true:

- The baseline and tenant-boundary tests pass from a clean release commit.
- Strands drives the bounded investigation/repair flow using exactly four scoped tools.
- Deterministic code controls state, hashing, approval, promotion, and receipts.
- Run isolation, crash recovery, stale approval, and failure paths are tested.
- A public AWS deployment passes the full synthetic acceptance flow.
- Budget alerts, observability, rollback, and teardown are documented and verified.
- The demo recording and screenshots contain no sensitive information.
- Submission claims match the deployed implementation.
- The owner has explicitly approved public release and, later, Devpost submission.

## Communications

- During build: record decisions and unresolved risks in the repository.
- At a stop condition: notify the owner with run ID, commit SHA, failed invariant, evidence location, and safest next action.
- Before public release: provide the artifact hash, AWS region/services, estimated spend, test results, rollback method, and known limitations.
- After release: provide the public URL, release commit, health status, and teardown owner.

## Record

| Field | Value |
|---|---|
| Run ID | |
| Commit SHA | |
| Artifact hash | |
| Environment / region | |
| Model / provider | |
| Started / completed | |
| Baseline result | |
| Boundary comparison | |
| Repair result | |
| Evidence location | |
| Approval actor / time / hash | |
| Promotion receipt | |
| Exceptions / follow-up | |

## Current review disposition

**Proceed, with gates.** The core fixture is small, deterministic, and demonstrably supports the product story. The next safest action is Phase 2: implement the deterministic record/state layer and test its safety properties before adding Strands or provisioning AWS resources.
