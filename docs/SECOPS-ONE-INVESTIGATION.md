# Completing one live phishing investigation

The owner asked to focus on one real investigation end to end and permitted parallel agent review. Scope remains an existing synthetic SIEM phishing incident, real Strands/OpenAI inference, immutable replay evidence and a recommendation for analyst review. No real security connector, new UI, cloud deployment or upstream decision is included.

## Review findings and fixes

Two read-only reviewers evaluated the failure path and the single phishing scenario. An offline real-SDK reproduction changed the first activity query's timestamp from Z to +00:00 and reproduced the prior four-request/three-tool stop. This is a plausible cause, not proof of the original lost fourth response.

The tool schemas now expose exact incident/entity IDs, the allowed templates, exact window values and rejection of additional fields. The prompt distinguishes native intermediate tool calls from final JSON, requires complete collection, explains the provided limits, and asks for material evidence rather than one arbitrary valid citation. Each returned tool result includes remaining-call and completed-check metadata; stored source evidence remains unchanged. Rejections now distinguish unregistered tool, field shape, typed contract and tool budget with safe labels.

A second harness review reproduced a startup failure that left an issued grant and no result export. Host cleanup now recovers interrupted state, closes an unclaimed grant, initializes the result journal and exports a sanitized failure. Tests cover both startup failure and authorization-receipt write failure. No raw credentials or exceptions enter the report.

## Reproducible host workflow

Prepare only (no key read, grant or paid call):

```sh
cd /Users/arielsmoliar/Developer/migration-proof
.venv/bin/python -m secops_triage.live prepare --output data/new-phishing-attempt
```

The new directory contains the fixed synthetic phishing incident, a private owner capability and a public-safe proposal. Existing output directories are rejected. Inspect proposal.json, never print owner.json.

For an owner-authorized single attempt at the fixed $4.25 ceiling, the implemented execute command requires --output, --key-file, --actor and --authorize-usd 4.25. The key-file argument is a local path, never a key value. It parses one literal OPENAI_API_KEY assignment without executing the credential file. The command rejects changed engine identity and issues a fresh single-use grant. It uses the existing supervised runner and exports live-result.json plus investigation.md/packet.json only on success. A failed or completed grant cannot be reused. No default retry exists.

The current owner request to complete the investigation is carried out as one fresh attempt under the previously presented ten-request, nine-tool, 120-second and $4.25 ceiling. The earlier failed run is preserved. Any additional scope or retry requires a new decision.

## Semantic acceptance rubric

- Inspect the existing incident, both related entities, all five phishing checks and prior cases using all four tool types.
- Establish the message at 10:00, inbox delivery at 10:01, an intelligence verdict at 10:03 targeting that message, and an allowed click at 10:04 referencing the same message.
- Escalate based on the linked suspicious message and exposure. Passing mail authentication and an earlier benign case do not clear the current incident.
- Do not claim credential theft, malware execution, confirmed account compromise or a specific malicious URL that the evidence does not contain.
- Distinguish complete empty business-context results from verified authorization or proof of maliciousness.
- Produce a persisted packet with materially supported citations, explicit execution provenance, settled usage and a closed grant. SIEM status remains unchanged. Analyst disposition is a later human action, not performed by this investigation.

The expected recommendation and this rubric are review material, not passed to the live model as an answer key. A success demonstrates this one bounded synthetic investigation, not reliability across the three families or a production SOC efficacy result.

## Second live attempt: collection completed, final validation stopped

At execution commit 66c8abf4f8df5e2e3e7cba1f913a8aaf3e2546ce, run bc4d4acd62ddeb7be26fd40a08cc3ada completed all nine reads through all four tool types. The model chose to query all five phishing sources before the entity lookups and prior cases. Final JSON parsed, but assessment validation failed; no packet was published. All ten requests settled: estimated $0.012979, reserved $4.223080. Grant closed. See outputs/secops-second-live-result.json. No conclusion or unapproved retry is claimed.

The parallel review confirmed another interface defect: incident/ownership results and complete empty business-context queries could not be cited under an event-only finding contract. This is a verified design gap, not proof of the exact lost invalid final field. The fix supplies short session-local citation handles and resolves them into canonical evidence/event references. Empty result and ownership handles resolve to result metadata with event_id null. The renderer labels those query/context citations. Fixed rejection codes now identify invalid vocabulary, finding shape, unknown citation and summary bounds without preserving rejected prose.

All 61 focused SecOps tests pass, including exact handle resolution, result-metadata references, cross-record/unknown evidence rejection, and proof that metadata citations cannot erase missing checks. A separate reviewer found no blocker in the updated citation path. A new fresh attempt requires a new explicit spending decision because the preceding grant used all ten requests and closed.
