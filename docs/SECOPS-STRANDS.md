# Strands investigation over SecOps replay evidence

The owner approved connecting Strands after the deterministic SecOps increment. The real pinned Strands 1.54.0 loop now selects and invokes the four existing scoped read tools. A source incident already exists; neither agent nor this demo creates, closes, escalates or contains an upstream incident.

## What is verified

Run a zero-cost example:

```sh
uv sync --frozen --extra agent
.venv/bin/python -m secops_triage demo --strands --output data/new-strands-demo
```

This runs the real SDK in a supervised subprocess with an explicitly scripted provider, not a live model. The three-alert fixture makes 19 tool calls and 20 provider turns. Tests also exercise the actual OpenAI transport/provider interface with fake HTTP responses: one phishing incident uses ten requests, including its final assessment. These are integration results, not evidence of model judgment quality.

`agent_runner.run_agent(store, run_id, token)` is the public host entrypoint. `agent.execute_session` is an internal worker/test seam. The runner does not accept a custom model or arbitrary worker command. Model construction is explicit; there is no ambient default provider or credential lookup. Optional dependencies and the transport remain pinned. The transport now accepts a host-supplied tool-name allowlist, with migration's original four-tool registry retained as its default.

## Responsibility and output

Strands receives incident-window metadata and allowed checks, then must retrieve actual evidence. Its final JSON contains a recommendation and up to twelve findings, each referencing a returned evidence ID and an event in that evidence. Unknown tool names, extra scope arguments, out-of-window queries and unsupported citations stop execution.

The immutable packet contains both the untrusted agent assessment and the deterministic evidence assessment. Citation existence does not prove the interpretation is correct. A model recommendation cannot erase gaps or overwrite the deterministic verdict. Disagreement marks the incident as needing review and prevents deterministic closure; sufficient deterministic escalation evidence remains visible. Analyst review binds the packet including the model assessment. Approval, promotion, review and spending grants remain host-only operations.

The report labels scripted versus live execution, escapes model/source prose, and shows any disagreement. This is an investigation explanation based on evidence, not a private chain-of-thought transcript. The current narrow deterministic rules remain a limitation: a legitimate model insight outside those rules requires analyst review.

## Persistence and bounds

The existing SQLite store lock covers the entire investigation and packet publication. Other callers cannot alter evidence or review an unfinished packet. This intentionally serializes all runs sharing one store and is suitable only for the local demo. Tool adapters execute asynchronously on the owning event-loop thread so SQLite operations stay on that thread.

`secops_agent_sessions` records provider mode, model/tool counts, status and the assessment hash. The state `assessed` means the model assessment was recorded; the run's packet/state separately determines publication. The packet validates the same-run session, mode, artifact hash and every citation. Engine identity includes the new agent modules, OpenAI provider/preflight and dependency lock; old runs require a fresh import after these source changes.

The SDK executes tools sequentially with no retries, default output callback, automatic tool-directory loading or model-backed context manager. Offline execution caps 24 model calls; live execution caps ten. The context acceptance cap is 128 KB and model response cap 16 KB. There is a 110-second async deadline plus a 120-second subprocess deadline. The worker receives a minimal environment with telemetry disabled; the owner capability and optional API key enter over stdin, not argv, model context or inherited environment. The supervisor suppresses worker error text and kills its own process group on timeout.

Restart recovers incomplete collection, marks abandoned agent sessions interrupted, closes running grants and retains unknown request reservations. No paid request is retried automatically. Existing evidence survives; a retry uses a fresh collection pass. A completed deterministic packet cannot be relabeled as a Strands investigation.

## Prepared first live attempt — authorization pending

Scope: one fresh synthetic reported-phishing incident, using `gpt-4.1-mini-2025-04-14` via the existing OpenAI HTTPS transport. Maximum ten requests, 2,048 output tokens per request, nine tool calls and 120 seconds. No real security data, security connectors, AWS resources, or upstream mutations.

A separate host-only SecOps grant binds the run, snapshot, engine, provider sources, dependency lock and authorizing actor. It expires after ten minutes and can be claimed once. Grants cannot be reused between runs or issued twice to the same run. Historical migration grants and spending remain untouched.

Proposed ceiling: **$4.25**. At the [published GPT-4.1 mini rates](https://developers.openai.com/api/docs/models/gpt-4.1-mini), checked again 2026-09-07, each dispatch reserves $0.422308 based on the full 1,047,576-token context plus configured output. Ten calls reserve $4.223080, without refunding capacity after cheap responses. The inherited pricing record expires after seven days; stale pricing blocks dispatch. Recorded token estimates are not invoices. Provider failures or invalid usage keep their full reservation and block further calls. The ceiling assumes published standard-tier prices and excludes unrelated account activity and taxes.

`agent_spend.authorize` is an explicit spending action; invoke it only after the owner approves this concrete attempt. No grant for this live attempt has been issued and no paid SecOps request has been sent. A fake-response test and scripted SDK run do not satisfy the pending live-model milestone.

Next: obtain the new spending authorization, execute once, inspect actual tool selection and cited findings, record usage, and stop. One live success would still not establish reliability across unfamiliar incidents or prompt injection. AWS and AgentCore remain separate unverified deployment work.

## Subsequent live result

The owner authorized the proposal and it ran once. It stopped after four model requests and three successful reads, without an investigation packet. The grant is closed and no retry is authorized. See `SECOPS-FIRST-LIVE-RESULT.md`; it supersedes the pending-authorization status above. Follow-up `secops_agent_events` logging now records fixed lifecycle stages and safe stop labels to diagnose future failures.
