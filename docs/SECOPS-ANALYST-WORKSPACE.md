# Local analyst workspace

The workspace turns a selected synthetic SIEM incident into a real **Strands SDK scripted investigation**, showing the four scoped tools, committed evidence, citations, deterministic assessment and remaining uncertainty. It saves a local handoff or explicit close/escalate decision. It does not change the source SIEM or run a paid model.

From the verified checkout with the pinned agent dependencies installed:

```sh
.venv/bin/python -m secops_triage.workspace --root data/my-new-workspace --port 0
```

Open the printed `http://127.0.0.1:<port>` URL. Port 0 selects a free port. Choose case-04 for the two-message phishing scenario and click **Run scripted investigation**. Inspect the actual trace, compare messages, follow evidence links and expand the original provider finding. Record your own name/role and a local case note only when making an actual decision. Case-03 shows missing account telemetry; case-07 shows scoped endpoint closure.

The scripted provider deliberately emits a minimal finding; it is not a competent full analyst assessment. All nine reviewed outputs fail the semantic rubric for omissions. The interface separates provider output, deterministic policy and final packet, and labels completed views **Saved execution · no rerun**. “Executing now” means a current scripted SDK execution, not live-model inference. There is no live-provider/import/grant endpoint in this workspace. See [technical review and authority reconciliation](SECOPS-TECHNICAL-REVIEW-20260908.md).

Use Ctrl-C to stop the local server. Restart with the same root and original port to preserve the browser origin and its tab-local unsaved drafts. Saved runs/decisions live in the private server directory and survive a changed port. The directory must be private (0700); ownership metadata is 0600. Keep the entire directory together. Do not point it at historical stores, share its private capability file, or delete evidence to reset a demo. A second workspace process for the same root is refused. A crash preserves the start intent and restores ownership without redispatch. Starting another revision requires an explicit action and makes previous decisions historical.

A changed investigation engine leaves evidence readable, but its historical assessment is not revalidated under the new policy or made eligible for new decisions. View a compatible saved report/build when the original assessment is needed. The UI never rewrites historical packets to make them pass current validation.

This is a loopback, single-operator local prototype. Host/Origin checks, an HttpOnly SameSite session, CSRF checks, CSP and text-only source rendering protect the browser boundary. The local filesystem operator remains trusted. It is not a remotely hosted multiuser service. Drafts use this browser tab's session storage; saved case notes use the existing Store semantics. No upstream writeback or containment is implemented.

## Verification

`tests/test_workspace.py` exercises real scripted Strands orchestration, scope/capability boundaries, duplicate starts, revision invalidation, durable handoff, explicit override, missing collection, retained failure, concurrent progress reads, crash boundaries and historical-build projection. HTTP tests cover exact Host/Origin/session/CSRF and the absence of authority endpoints.

Optional isolated browser checks require an existing Playwright installation and Chrome; neither is downloaded by the check:

```sh
NODE_PATH=/path/to/node_modules node ops/workspace_browser_check.cjs data/new-browser-verification
```

The script refuses an existing output directory, starts a fresh loopback server and isolated browser, uses real scripted runs for hero/close/incomplete workflows, then stops both. Disagreement, source-text injection, stopped-view and historical-build browser states use explicitly labeled presentation fixtures. They do not become saved execution evidence. Backend tests independently cover retained execution failure. Test actors explicitly identify automation, never human acceptance.

Screenshots cover 1440px, 819px and 375px; keyboard skip/evidence focus, draft/save/reload/restart, stale revision and override paths are exercised. A 720px viewport checks the layout space equivalent to a 1440px viewport at 200% zoom; this is not a full browser-zoom or assistive-technology certification. Results and frozen-source hashes are in `outputs/secops-workspace-validation-20260908.json`.

## AWS and release status

This UI runs on the local computer. The separately verified September 8 AWS deployment ran a scripted SDK smoke on private Ohio EC2 with encrypted EBS, SSM and CloudWatch. EC2 is stopped and temporary paid egress was removed. No UI deployment or new AWS action occurred in this increment. Bedrock, AgentCore and live security ingestion remain unimplemented. See [AWS evidence and retention](SECOPS-AWS-DEPLOYMENT-20260908.md).

Human validation, paid live evaluation, formal rehearsals, public video/OpenAI voice, architecture/license packaging and final submission remain separate work. The UI and Impeccable implementation are now present; historical documentation describing them as pending refers to the earlier checkpoints.

Final September 8 verification: **310 tests passed in 71.577s with zero skips**, all14 browser checks passed and the migration probe detected the intended faulty leak (403/200/403). All71 frozen runtime/test/assets/config files were unchanged. Independent AI source/docs review found no remaining blocker after the recorded fixes. Saved screenshots and raw logs are in private ignored verification directories; the sanitized result record is public.
