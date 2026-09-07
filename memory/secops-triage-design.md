# Design: Evidence-backed alert triage

Date: 2026-09-07
Status: First local replay increment accepted for implementation; implemented, awaiting owner review
Mode: Builder
Working title: SecOps Triage; no repository or package rename selected
Baseline: main at 7e36c579705a904b5fdf416635db8932031b6c94

## Problem and agreed scope

Investigate an existing incident created by a SIEM or another security tool and prepare an evidence-backed close-or-escalate recommendation. The user explicitly selected suspicious sign-ins, reported phishing, and endpoint alerts. All three remain in scope, with separate investigation playbooks and shared evidence and review machinery.

The target user is a frontline SOC analyst repeatedly gathering context, checking related activity, weighing benign and malicious explanations, and writing disposition notes. The owner has relevant experience from Flare AI and SafeAgent; their implementations, customers, data access, and measured workloads have not been inspected or assumed.

Migration work was paused because it did not convincingly meet the user's requirement for frequent daily work. Daily triage is the new problem hypothesis. No measured time savings, specific customer demand, most frequent alert category, or competitive advantage has yet been established.

## Experience to deliver

A Tier 1 analyst selects an existing SIEM incident, which may contain several related alerts, and receives an investigation with inspectable source evidence, contradictory findings, missing checks, and a draft case note. They can accept or override the recommendation and explain why. Their decision remains separate from the agent's recommendation.

The compelling result is reduced searching and documentation while preserving sound judgment. A fluent summary alone does not establish value. An incomplete investigation must be visibly incomplete; mandatory manual review must not be mislabeled as a confirmed malicious incident.

## Premises established in the discussion

- Focus on frequent analyst work rather than occasional migration or detection-rule changes.
- Preserve all three selected alert families while using one common workflow.
- The agent investigates and recommends; the analyst controls disposition and response.
- Missing telemetry does not mean benign activity.
- Measure analyst effort and escalation errors, not just report generation.

Open assumptions: availability of representative alert exports, which source platform to integrate first, real query latency and permissions, analyst review access, and whether existing tools already satisfy this workflow.

## Implementation alternatives

### A. Local evidence replay across all three families — recommended first increment

Effort S relative to the other approaches; integration risk low, product-validation risk medium.

Import explicitly selected, sanitized case bundles into a new local SecOps domain. Bounded tools query the bundle as they would a source adapter. Produce a JSON and Markdown investigation packet and record a local analyst review. Synthetic examples establish correctness; authorized representative exports establish realism later.

Pros: executable end-to-end coverage for all three families; no account or connector dependency; repeatable failure and evidence-leakage tests. Cons: does not prove live collection or time savings; exported context may omit important evidence. Reuses: canonical hashing and artifact-storage patterns, transaction and recovery patterns, bounded orchestration lessons. No wholesale reuse of migration state, registry, or grants.

### B. One platform with live read-only collection

Effort M/L depending on account access; integration and data-handling risk medium/high.

Build one authorized source adapter that supports the selected families where available. Source selection depends on the owner's environment, not a guessed vendor preference. Keep a replay adapter for reproducible evaluation.

Pros: validates real collection and data gaps earlier; nearer to daily use. Cons: access, schemas, pagination, permissions, retention, and provider data handling must be settled; one platform might not cover every selected family. Reuses: A's contracts and replay tests plus existing bounded transport patterns after review.

### C. Multiple live sources and case-system integration — longer-term architecture

Effort XL; integration risk high.

Normalize identity, email, endpoint, and historical case evidence across platforms; add authenticated review and explicitly authorized case-system writes.

Pros: fits fragmented analyst environments; can reduce more tool switching. Cons: entity reconciliation, access control, deployment, connector reliability, and write semantics substantially widen scope. Reuses: A/B domain contracts and source adapters. Requires an actual multi-user authorization design; the existing local owner-token model is insufficient.

Recommendation: A first, designed to admit B without changing recommendation semantics. Move to B only after a concrete source is selected. Do not remain on synthetic examples and claim product validation. The owner clarified that this is a useful product demo, not a requirement to outperform other vendors, and authorized continuing with the incident investigation workflow. Approach A is the first implemented increment; see docs/SECOPS-REPLAY.md.

## Shared investigation contract

Input identifies organization, source, source alert ID, alert family, alert/event times, explicitly bounded investigation window, and input snapshot digest. Organization/run scope is backend-bound, never chosen freely by the model. Preserve distinctions between an alert, source incident, and our investigation run.

Evidence records carry evidence ID, organization/run, source and record ID, event time, collection time, query identity and window, adapter version, collection outcome, completeness/pagination information, normalized body digest, and local artifact reference. Immutable local records retain provenance but hashes do not prove the source is truthful.

Collection outcomes distinguish success, successful empty result, unavailable, unauthorized, timeout, truncated, and malformed. Empty results count as meaningful absence only when source coverage and the requested interval are established. Playbook versions specify required and conditional checks; optional failures need not block a recommendation if irrelevant, but remain visible.

The packet includes:
- Alert summary and affected entities.
- Investigation status: complete or needs_review.
- Recommendation: close, escalate, or null when evidence cannot support either.
- Disposition reason: distinguish benign expected activity, false positive, suspected compromise, and other versioned reasons; a triggered detection can correctly identify benign activity.
- Evidence-linked observations, separate from inferences.
- Evidence supporting the recommendation, contradictory evidence, unresolved checks, and scoped limitations.
- Proposed next checks/actions and a draft case note.
- Input, evidence-set, playbook, and packet digests; creation time and tool/model provenance where applicable.

The backend verifies citations exist in the same run, resolve to intact artifacts, and satisfy declared structural and freshness requirements. It does not claim to verify the truth of every natural-language inference. Analysts and held-out evaluations assess whether cited evidence actually supports the claim.

A close recommendation requires the playbook's essential checks, an evidenced benign explanation, and no unresolved material contradictory findings. Escalation can be recommended on sufficient positive evidence despite missing other telemetry; gaps stay visible. Inconclusive cases return needs_review with recommendation null and specific next checks. Do not force a binary guess or substitute a fabricated confidence percentage.

## Three playbooks

### Suspicious sign-ins

Gather trigger events, account identity, authentication outcomes and methods, device context, bounded sign-in history, network context, and related account activity when available. Verify account and device joins within the organization. Record historical coverage and comparison windows.

Compare expected access explanations against compromise indicators. Familiar IPs, successful MFA, VPN use, and geolocation alone are not sufficient closure criteria. Material uncertainty about authentication/session activity remains explicit.

Example cases: expected travel with corroborating context; unfamiliar successful access with corroborating suspicious activity; ambiguous network change; authentication or history telemetry unavailable. Examples are test hypotheses, not universal production detection rules.

### Reported phishing

Gather reported-message identity, parsed headers and authentication results, sender/domain context, extracted link and attachment metadata, delivery scope, and available interaction telemetry. Distinguish delivery, clicking, execution, and credential compromise; one does not establish the next.

Treat email text, headers, filenames, and links as untrusted data. Do not visit suspicious URLs, download attachments, execute content, or upload material to third parties in the first increment. A URL's presence or successful sender authentication alone does not establish maliciousness or legitimacy.

Example cases: legitimate reported message with corroborating context; malicious message with evidence of user interaction; delivered malicious message without established interaction; absent or truncated interaction records. Document what remains unknown.

### Endpoint alerts

Gather the detection and relevant process ancestry, command lines, file identifiers and available signing information, user/device context, network activity, and related detections within a bounded interval. Preserve process/entity identifiers to avoid joining unrelated executions.

Compare expected administrative/software activity with evidence of suspicious execution. Trusted filenames, signatures, or an administrator account alone do not justify closure. Detection status must not be conflated with verified containment.

Example cases: corroborated administrative activity; suspicious execution with supporting ancestry/network evidence; ambiguous dual-use tool; missing parent process or endpoint telemetry. No shell, isolation, file deletion, or process termination tool.

## Proposed bounded tools

Four read-only operations for the new SecOps registry:
1. inspect_incident: returns existing source incident identity, linked alerts and initial entity references.
2. lookup_entity: returns selected entity context from the run-bound source, with provenance and coverage.
3. query_activity: executes a versioned, allowlisted query template against known entities and bounded time windows; no arbitrary SQL, shell, or network destinations.
4. find_related_cases: returns organization-scoped historical cases and their evidence-backed dispositions. Prior decisions are context, never ground truth by default.

The host supplies run-bound capability context. Unknown entity IDs, cross-organization references, excessive time windows, unsupported templates, and output overflows are rejected or explicitly incomplete. The agent supplies a structured assessment; deterministic host code assembles the packet. No approval, promotion, closure, escalation submission, containment, or spending authorization appears in the registry.

## Persistence, review, and recovery

Use a separate SecOps database and artifact namespace. Preserve existing migration runs and paid-call histories untouched. New records cover cases, investigation runs, tool invocations, evidence, packets, and analyst reviews. A review records actor, exact packet digest, accept/override decision, selected disposition, reason, and time. Local review does not close or escalate the upstream alert.

Proposed run states: created -> collecting -> packet_ready | needs_review | failed; packet_ready or needs_review may receive an analyst review -> reviewed. Incomplete cases can be manually adjudicated with an explicit reason. A review does not turn missing evidence into completed checks.

New alert content, new evidence, or a changed playbook creates a new immutable investigation revision/run. Old reviews remain historical and cannot authorize a decision for the new packet. Never rewrite prior evidence to make a review current.

Record tool start before execution and completion/evidence transactionally. On restart, interrupted collection cannot become successful; mark it incomplete and permit bounded read-only retry with a new invocation record. Packet publication references only committed evidence. Use idempotency keys for duplicate ingest/review submissions and test separate organizations/runs concurrently.

## Reuse decisions grounded in the existing repository

- migration_proof/core/artifacts.py: canonical JSON, SHA-256, run-scoped storage patterns are relevant. It also contains migration patch logic; do not import the module indiscriminately as a generic SecOps abstraction.
- migration_proof/core/store.py: transaction, hash-bound packet, and recovery patterns are useful. Its candidate revisions, four checks, repair, and promotion states are domain-specific and must not become the SecOps state machine.
- migration_proof/agent/runtime.py: study bounded tool guards and loop limits; define a new registry and context contract.
- migration_proof/agent/spend.py: grant and accounting concepts remain useful, but its schema/authorization depends on migration state and candidate digests. Existing grants do not authorize a SecOps session or customer-data egress.
- Preserve the current migration package, tests, and historic data. Avoid a speculative generic framework extraction before the first SecOps workflow works.

## Evaluation and build sequence

1. Define new typed case/evidence/packet contracts and fixture-loader validation. Start with contracts across all three families rather than delivering only one family.
2. Create ten synthetic cases per family (30 total): two supported close cases, two supported escalate cases, two ambiguous cases, and four distinct failure/adversarial cases. Keep expected dispositions, rationale, and required evidence outside all agent-visible inputs. Include unavailable, stale/truncated, contradictory, and injection cases across each family.
3. Implement replay queries, immutable evidence, packet checks, and a local JSON/Markdown report. A scripted assessment may exercise contracts but must be labeled scripted; it does not demonstrate model judgment.
4. Add local analyst review and recovery/isolation tests. Run the preserved migration suite and probe before committing the first implementation unit.
5. Evaluate actual agent judgment only with separately scoped model execution and approved data. Report per-family close precision, missed escalations, abstention/needs_review rate, citation correctness, and coverage. Do not score mass abstention as success. Synthetic labels are authored expectations, not measured field ground truth.
6. Obtain authorized representative historical cases, adjudicate labels with an analyst, and hold out evaluation cases from prompt/playbook tuning. Exclude final case resolution and future events from investigation inputs to prevent answer leakage.
7. Compare manual and assisted work using comparable, counterbalanced cases to reduce learning effects. Measure active review/correction time plus waiting time separately. Proposed pilot target: at least 30% lower median active handling time with no observed increase in missed escalations; small samples cannot establish production safety. Report sample size, per-family counts, disagreement and uncertainty.
8. Select and implement one real read-only connector when source access and data handling are concrete. Recheck product utility before expanding integrations or deployment.

Structural test gates: no cross-run/organization evidence; no unsupported citation accepted; stale or incomplete critical checks never silently enable close; illegal transitions rejected; crash/duplicate operations preserve history; no agent authority over review or external actions; injected source content cannot expand tool authority. Include plausible but unsupported claims, not only malformed output.

## Limits and unresolved risks

No connector, customer-data permission, retention policy, or representative evaluation corpus has been selected. All three families require different evidence; a universal checklist is inadequate. Missing telemetry, ambiguous identities, analyst disagreement, adversarial content, and superficially plausible explanations remain material risks. Over-escalation can also increase workload and must be measured.

The demo should show efficient context gathering and an easy-to-review investigation. Competitive superiority is not an acceptance gate. Claims of real analyst time savings still require measurement.

No paid SecOps calls, UI, AWS resources, AgentCore, external case writes, or submission work are included in this first design increment. Old migration runbook deployment steps are historical and do not authorize SecOps work. This draft does not revalidate hackathon deadlines or requirements.

## Immediate assignment

Build the reviewed local replay increment for all three alert families, then have the owner inspect one complete and one incomplete investigation from each family. Identify the missing evidence or reasoning that would prevent using the packet during a real shift. Choose the first real source from that feedback.

## Implemented incident clarification (2026-09-07)

The upstream SIEM creates and owns the incident. The new local package imports a bounded snapshot, preserves its identity, and investigates all linked alerts. Read-only tool names are inspect_incident, lookup_entity, query_activity and find_related_cases. Assessments currently use labeled deterministic replay rules. The report includes a combined timeline, entity ownership, per-alert context, collection coverage and a draft case note. Local analyst review does not mutate the upstream incident. This increment validates mechanics; a model-driven investigation and operator UI remain subsequent work.
