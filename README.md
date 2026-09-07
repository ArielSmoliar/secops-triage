Current Strands integration: [SecOps Strands investigation](docs/SECOPS-STRANDS.md). Run the SDK with zero-cost scripted replay using `python -m secops_triage demo --strands --output data/new-strands-demo`. Live SecOps inference awaits a separately authorized bounded attempt.

# Incident investigation demo

Help a Tier 1 SOC analyst investigate an **existing incident created by a SIEM or another security tool**. Gather identity, email, endpoint and historical context, then prepare an evidence-linked close-or-escalate recommendation. One incident can contain multiple related alerts.

The first working slice is a local replay with three playbooks: suspicious sign-ins, reported phishing and endpoint alerts. It executes real bounded queries against synthetic source records and persists the results. Its assessment is explicitly **deterministic demo logic, not live AI**. The upstream system remains the incident system of record.

## Run the incident demo

Python 3.11+ on macOS/Linux; this slice needs no dependencies or credentials. Choose a new output directory for each CLI run:

```sh
python3 -m secops_triage demo --output data/incident-demo-1
```

Open `data/incident-demo-1/investigation.md` to inspect the entities, event timeline, per-alert findings, missing context, source evidence links and draft case note. `packet.json` contains the structured result. The private `owner.json` is for local host access only; do not share it.

To investigate a normalized local incident snapshot:

```sh
python3 -m secops_triage investigate incident.json --output data/imported-incident-1
```

This imports an existing incident; it does not create an incident in a SIEM. No live connector, paid model, upstream case write or containment action runs. See [contracts, limits and analyst review](docs/SECOPS-REPLAY.md).

## Verify the SecOps slice

```sh
python3 -m unittest discover -s tests -p test_secops_triage.py -v
```

The tests include 30 synthetic cases across all three families, a combined incident, source failures, stale coverage, evidence tampering, run isolation, replay, concurrency and process-crash recovery. These establish demo behavior, not production detection accuracy or measured time savings.

The original migration implementation and its tests remain intact below. It is a preserved technical baseline, not the active product workflow.

## Preserved Migration Proof baseline

Evidence-backed acceptance for software migrations. The deterministic fixture demonstrates a green ordinary test suite alongside a cross-tenant authorization regression.

Phase 2 implements the local deterministic acceptance backend. Phase 3 now adds a real Strands loop with an explicitly scripted offline provider. Historical bounded migration live-test results are documented in `docs/OPENAI-LIVE-RESULT.md`. The SecOps replay does not invoke a model.

## Verify

Python 3.11+ on macOS or Linux; standard library only. Tests need permission to bind ephemeral localhost sockets.

```sh
python3 -m unittest discover -s tests -v
python3 -m migration_proof.probe
```

The probe must report `403 → 200 with synthetic leaked fields → 403`. The expanded suite includes real HTTP checks, generated-regression execution, promotion rollback, concurrent replay, and subprocess crash recovery.

## Offline Strands integration

```sh
uv sync --frozen --extra agent
uv run --frozen --extra agent python -m unittest discover -s tests -v
```

The `agent` extra pins Strands 1.54.0; `uv.lock` records its dependency graph and hashes. Without this extra, the standard-library tests still run and agent tests explicitly skip. Full verification requires the extra and zero skips. See [Phase 3 integration and limits](docs/PHASE3.md) for `run_offline` usage and the remaining live-provider gate.

## Local API

Use a private local filesystem directory (no symlinks) for `Store`. Keep SQLite and its artifact directory together. Never send the returned owner token to an agent.

```python
from migration_proof.core.store import Store
from migration_proof.core.contracts import InspectInput, BaselineInput, CompareInput

store = Store("data/local-acceptance")
run = store.create_run("corrected")
run_id, token = run["run_id"], run["token"]
tools = store.agent_tools(run_id, token)

tools["inspect_candidate"](InspectInput(run_id, "corrected"))
tools["run_baseline_tests"](BaselineInput(run_id, run["digest"]))
tools["compare_tenant_boundary"](
    CompareInput(run_id, run["original_digest"], run["digest"])
)
packet = store.assemble_decision_packet(run_id, token, run["digest"])
assert packet["ready"]
```

Only an explicit human decision should call the separate backend methods `approve(run_id, token, packet_id, actor)` and `promote(run_id, token, approval_id, idempotency_key)`. Promotion changes only that run's local SQLite accepted-release pointer. There are exactly four entries in `tools`; approval, replacement, packet assembly, and promotion are absent.

For a faulty candidate, a failed comparison blocks acceptance. `apply_safe_patch(PatchInput(...))` accepts the parsed new-file diff defined by `SAFE_PATCH` in `core/artifacts.py`. It adds the one audited regression test to an immutable derived snapshot. The test fails on the faulty application. An owner can then call `replace_candidate(..., "corrected", actor)` to carry the generated test forward; all gates must run again before approval.

See [Phase 2 architecture and review](docs/PHASE2.md), [handoff](docs/HANDOFF.md), and [build runbook](docs/runbooks/migration-proof-build-release-demo-runbook.md). Owner review remains required before any model integration.
