# Existing-incident investigation: local replay

## Scope and experience

The user selected a product demo for a Tier 1 SOC analyst who receives an incident from a SIEM and needs its details and context. The SIEM creates the incident and remains the system of record. The local investigator preserves source/incident identifiers and gathers evidence for all linked suspicious sign-in, reported phishing and endpoint alerts. Competitive superiority is not a demo acceptance requirement.

`python -m secops_triage demo --output data/demo-N` creates a new private local output directory, runs bounded replay queries, saves a packet and renders a Markdown investigation. The demo incident includes three alerts sharing the same synthetic user/device. The output shows entity ownership, chronology, source attributes, positive and conflicting evidence, missing checks, proposed next checks and a draft case note. Source text is escaped and labeled untrusted.

The result is explicitly labeled **deterministic replay playbooks (no live model)**. It is an executed local workflow, not a model evaluation or live SIEM integration. Demo rules do not provide production incident verdicts.

## Package and data contracts

The separate `secops_triage` package uses only Python's standard library on macOS/Linux. Migration modules, databases, grants and test fixtures remain untouched.

`IncidentBundle.from_dict` validates a normalized snapshot containing:

- `tenant_id`, `source`, `incident_id`, `title`, `observed_at`, `start`, `end`, `synthetic`.
- `alerts`: ID, family, title, entity references and trigger-event references.
- `entities`: ID, kind, display name and owner.
- `sources`: ID, organization, query template, outcome, completeness and covered interval.
- `events`: ID, organization, source, entity references, event time, kind, typed attributes and untrusted text.

Consult `secops_triage/contracts.py` for exact fields and the supported attribute schemas. CLI JSON imports reject duplicate fields and files above 2 MB. The bundle rejects unexpected fields, invalid types, duplicate IDs, broken or cross-organization references, invalid/future event times and unsupported event kinds. Queries are restricted to the imported interval (maximum seven days), known alerts, relevant playbook templates and related entities. Replay supports one source per template; this is not a general multi-provider correlation engine.

Typed requests exposed through `store.agent_tools(run_id, token)`:

- `inspect_incident(InspectIncident())`
- `lookup_entity(LookupEntity(entity_id))`
- `query_activity(QueryActivity(alert_id, template, start, end))`
- `find_related_cases(FindRelatedCases(alert_id))`

The host binds run/organization and ownership. No request accepts a replacement organization, arbitrary query, file path, URL or shell command. There are no agent tools for incident creation, review, approval, promotion, closure, escalation submission, containment or spend authorization. The name `agent_tools` defines the boundary for a later model integration; this increment uses the deterministic host runner.

Sources report success, unavailable, unauthorized, timeout, truncated or malformed, plus separate completeness and interval metadata. Successful empty results differ from failed or incomplete collection. Query records are capped at 200 and the payload is trimmed below 60 KB; any truncation blocks using that check to justify closure. Other tool outputs above 64 KB fail collection. A run permits at most 256 invocations including retries. Local replay performs no blocking external I/O; future connectors need independent hard timeouts and source-specific pagination/freshness checks.

## Demo reasoning and incident aggregation

These intentionally narrow rules make the initial demonstration auditable:

- A malicious intelligence observation tied to retrieved activity supports escalation. Successful sign-in followed by an external account change is a second sign-in escalation path.
- A close recommendation requires retrieved triggers, complete full-window essential checks, a source authorization record tied to each trigger, and no recognized suspicious evidence.
- Familiarity, successful MFA or unknown reputation alone do not justify closing.
- Missing checks or absent evidence of legitimacy yield `needs_review` with no forced verdict.
- Sufficient suspicious evidence can support escalation despite other missing checks. The gaps remain visible.
- Recorded authorization and suspicious evidence are displayed as a conflict. Authorization does not override the suspicious evidence.
- Incident recommendation is escalate if any linked alert warrants escalation; close only if all linked alerts support close; otherwise it is undecided. Investigation completeness is independent of recommendation.

Historical cases and entity ownership are gathered as context and appear in the report. Prior case verdicts do not automatically establish legitimacy. The runner does not adapt its plan or interpret arbitrary prose; it follows a fixed set of actual replay queries. All classifications are demo inferences over structured source assertions. The importer's claim of complete telemetry or valid authorization is not independently attested.

## Persistence and authority

A private local directory contains `triage.sqlite3` and immutable, SHA-256-addressed `blobs/<run_id>/<hash>`. SQLite records source incident heads, investigation runs, transitions, invocations, evidence and local analyst reviews. Artifact publication uses a complete fsynced temporary file and atomic hard link. Reads verify hashes; paths reject symlinks. The database uses foreign keys, full synchronous commits and a POSIX process lock.

The host supplies a random capability to `ingest(bundle, token, request_id)`; only its hash is stored in SQLite. A repeated ingest key returns its existing run only for the same owner, snapshot and implementation identity. A new import creates a new investigation revision and makes prior reviews non-current while preserving their records and evidence. This is a trusted-host import boundary, not an authenticated multi-user SIEM ingestion endpoint.

States: created -> collecting -> packet_ready / needs_review / failed -> reviewed where allowed. Failed or interrupted collection may retry before a packet is published. A completed packet is immutable; new evidence requires a new import/revision. Under the exclusive lock, restart marks an interrupted invocation incomplete and requires a rerun. Prior evidence remains; a new packet uses only the new complete collection pass. Repeated investigation returns the same verified packet. Budget exhaustion cannot manufacture a result.

Implementation identity hashes the contract, replay, assessment and store modules. Changed implementation requires a new import before investigation/review. Old evidence remains on disk; this is not a portable historical evaluator that embeds old executable code.

An analyst's decision is an explicit host operation:

```python
store.review(run_id, token, packet['packet_hash'],
             actor='Analyst name', disposition='escalate',
             reason='Reviewed evidence; further investigation required',
             request_id='unique-review-request')
```

The review binds the exact packet, actor, disposition and explanation. It is idempotent, rejects a stale snapshot or changed payload, and is recorded once. An analyst can adjudicate an incomplete case, but the review does not erase missing checks. **This records a local decision only. It does not close or escalate the upstream SIEM incident.**

## Verification and limits

The suite includes 30 authored cases (ten per family), combined incidents, source coverage and output limits, malicious related network evidence, citation/packet forgery, artifact tampering, wrong-owner/cross-organization access, idempotency conflicts, stale reviews, illegal transitions, concurrent execution/review, adapter failure and actual subprocess termination/restart.

Prompt-injection tests demonstrate inert handling by this fixed deterministic runner and escaped report output. They do not establish resistance by a live model. Likewise, successful fixtures demonstrate contract behavior, not real-world precision, missed-threat rates or analyst productivity.

Storage assumes a private trusted single-host filesystem and trusted application code. Hashes detect accidental/tampered artifacts relative to database references; they are not protection against an attacker controlling both the database and filesystem. Source assertions can be wrong or adversarial. No full tenant identity provider, encryption-at-rest policy, retention service, connector, remote case write, browser UI, model integration, AWS resource or paid call was added.

Next increment: review complete and incomplete packets for the three families, then connect the bounded tool interface to a model under a separately scoped execution/data budget and build the incident investigation experience. Preserve the SIEM's incident ownership throughout.
