# Completed live phishing investigation

**Milestone M1 is complete.** One existing synthetic SIEM incident was investigated end to end by the real Strands SDK with real OpenAI responses. The model collected evidence and returned a persisted, cited escalation recommendation. This demonstrates the live agent path over replay evidence; it does not claim a live SIEM connector or production reliability.

Execution commit: 69210cf928f8c2cadde604d4a2dc4a8b8d58495e. Run: 5f976e803708c0b16c4550d4477137ee. Session: e3e1dc9d9e2611fab91c302232ebffe2. Result: packet_ready, complete investigation, escalate. The immutable packet hash and full safe trace are recorded in outputs/secops-completed-live-investigation.json.

## What the agent did

The agent inspected the existing incident, queried the five phishing evidence sources, looked up the user and device, and checked prior cases. All nine reads completed through all four scoped tool types. It produced eight cited findings, including three result-metadata citations for empty authorization context and responsible teams.

The evidence shows a reported message, inbox delivery, malicious intelligence targeting that same message and an allowed click. The previous benign case was treated as context rather than clearance. The final recommendation is escalation for further analyst investigation, not a claim of confirmed account compromise or completed remediation.

The run took **19.2 seconds**, using **ten model requests**. All usage settled; conservative estimated token cost **$0.013638**, reserved exposure **$4.223080**, within the explicitly approved **$4.25** ceiling. The grant is closed. Reservation is not an invoice. No automatic retry occurred after this success.

## Verification and parallel review

The execution build passed **186 tests in 62.585 seconds**. These include the real SDK/fake transport paths, short-reference resolution, metadata citations, cross-record rejection, missing-evidence protection, scoped tools, crash recovery and spending limits. See outputs/secops-citation-validation.json.

Separate read-only agents reviewed the failure path, scenario and final evidence. The final semantic review verified all nine evidence hashes/run identities, all four tool types, all five source checks with full-window coverage and the narrow escalation rationale.

The review identified wording caveats, retained alongside the actual result:

- The telemetry says click/action=allowed; it does not establish that the user authorized the action.
- No authorization record was found in the queried source/window, not everywhere.
- The first finding's reporting claim is supported by incident inspection, although its attached citation points only to the message.
- IT operations is the responsible team; “owned” is an awkward description of a user.
- Passing mail authentication is visible in the timeline but omitted from the model's summary.

These do not invalidate the narrow escalation conclusion. They remain useful improvements for the analyst-facing experience. The model's original output and packet were not rewritten to hide them. No analyst approval or disposition was recorded by either reviewer.

## What changed after the failed attempts

Two earlier attempts remain preserved: the first stopped after three reads with an unknown fourth-response issue; the second completed collection but failed final assessment validation. The first interface correction exposed the exact timestamp/template constraints and budget to the model. The second introduced short server-generated citation handles and legitimate citations to empty-query/ownership metadata. Safe validation reason codes and the reproducible host harness now support diagnosis without raw credential-bearing logs.

Across all three SecOps development attempts: 24 real model requests, one completed investigation and two stopped attempts; estimated usage total $0.028240, conservative reservations $10.135392, all grants closed. This is a development history, not a reliability benchmark. Historical migration accounting remains separate and unchanged.

## Review the result

Local report: data/secops-one-investigation-citations/investigation.md. It includes the original model assessment, source timeline, evidence links, coverage, draft case note and separate evidence-review notes. Packet: data/secops-one-investigation-citations/packet.json. Private ownership records remain ignored and must not be displayed or committed.

The analyst can now review the packet and decide how to handle the source incident. This task does not record their decision or mutate the SIEM. M2–M5, UI, other live scenarios, AWS/AgentCore and submission work remain outside this completed increment.
