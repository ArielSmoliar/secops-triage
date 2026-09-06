"""SQLite authority, serialized state transitions, and crash-safe artifact references.

The local service owns its storage directory. flock serializes processes, including
recovery, while SQLite transactions bind each authoritative state change to its audit
records. Long-running fixed tools commit their intent before launching a worker.
"""
from contextlib import contextmanager
import fcntl
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType
from uuid import uuid4

from .artifacts import Artifacts, PATCH_PATH, canonical, parse_patch, sha
from .contracts import (
    CHECKS, TOOL_VERSION, BaselineInput, BaselineOutput, CompareInput, CompareOutput,
    InspectInput, InspectOutput, PatchInput, PatchOutput, Rejected, identifier, revision,
)

STATES = {
    "created": {"planning", "blocked"},
    "planning": {"checking", "blocked"},
    "checking": {"blocked", "repairable", "ready_for_approval"},
    "repairable": {"checking", "blocked"},
    "blocked": {"candidate_replaced", "repairable"},
    "candidate_replaced": {"checking", "blocked"},
    "ready_for_approval": {"approved", "blocked"},
    "approved": {"promoting", "blocked"},
    "promoting": {"verified", "promotion_failed"},
    "verified": {"blocked"},
    "promotion_failed": set(),
}
POLICY = {"policy_version": "1", "purpose": "Preserve the tenant boundary",
          "required_checks": list(CHECKS)}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, state TEXT NOT NULL,
 digest TEXT NOT NULL, original_digest TEXT NOT NULL, target TEXT NOT NULL,
 accepted_digest TEXT NOT NULL, packet_id TEXT, created REAL NOT NULL,
 calls INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS transitions(
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 previous TEXT NOT NULL, next TEXT NOT NULL, reason TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS candidates(
 run_id TEXT NOT NULL REFERENCES runs(id), digest TEXT NOT NULL,
 parent TEXT, revision TEXT NOT NULL, actor TEXT NOT NULL, at REAL NOT NULL,
 PRIMARY KEY(run_id,digest));
CREATE TABLE IF NOT EXISTS invocations(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), digest TEXT NOT NULL,
 tool TEXT NOT NULL, status TEXT NOT NULL, started REAL NOT NULL, finished REAL);
CREATE TABLE IF NOT EXISTS evidence(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), digest TEXT NOT NULL,
 invocation_id TEXT NOT NULL REFERENCES invocations(id), check_id TEXT NOT NULL,
 blob_hash TEXT NOT NULL, passed INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS repairs(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 parent TEXT NOT NULL, digest TEXT NOT NULL, patch_hash TEXT NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS packets(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), digest TEXT NOT NULL,
 blob_hash TEXT NOT NULL, ready INTEGER NOT NULL, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS approvals(
 id TEXT PRIMARY KEY, nonce TEXT NOT NULL UNIQUE, run_id TEXT NOT NULL REFERENCES runs(id),
 digest TEXT NOT NULL, packet_id TEXT NOT NULL REFERENCES packets(id), packet_hash TEXT NOT NULL,
 actor TEXT NOT NULL, target TEXT NOT NULL, action TEXT NOT NULL,
 issued REAL NOT NULL, expires REAL NOT NULL, status TEXT NOT NULL,
 UNIQUE(run_id,digest,action));
CREATE TABLE IF NOT EXISTS promotions(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 approval_id TEXT NOT NULL UNIQUE REFERENCES approvals(id), idempotency_key TEXT NOT NULL,
 prior_digest TEXT NOT NULL, new_digest TEXT NOT NULL, status TEXT NOT NULL,
 verification INTEGER, rollback TEXT NOT NULL, started REAL NOT NULL, finished REAL,
 UNIQUE(run_id,idempotency_key), UNIQUE(run_id,new_digest));
'''


@contextmanager
def transaction(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


class Store:
    """Trusted local backend. Tokens are capabilities; never give owner tokens to tools."""
    def __init__(self, root: str | Path):
        self.root = Path(root).absolute()
        Artifacts._safe(self.root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.artifacts = Artifacts(self.root / "artifacts")
        with self._locked() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise Rejected("unsupported database schema")
            db.executescript(SCHEMA)
            db.execute("PRAGMA user_version=1")
            self._recover(db)

    @contextmanager
    def _locked(self):
        for name in ("store.lock", "state.sqlite3", "state.sqlite3-wal", "state.sqlite3-shm"):
            Artifacts._safe(self.root / name)
        with (self.root / "store.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            db = sqlite3.connect(self.root / "state.sqlite3", isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            try:
                yield db
            finally:
                db.close()
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _run(self, db, run_id):
        identifier(run_id)
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise Rejected("unknown run")
        return row

    def _owner(self, db, run_id, token):
        row = self._run(db, run_id)
        if not isinstance(token, str) or not hmac.compare_digest(row["token_hash"], sha(token.encode())):
            raise Rejected("run ownership required")
        return row

    def _transition(self, db, run_id, state, reason):
        previous = self._run(db, run_id)["state"]
        if state not in STATES[previous]:
            raise Rejected(f"illegal state transition: {previous} -> {state}")
        db.execute("UPDATE runs SET state=? WHERE id=?", (state, run_id))
        db.execute("INSERT INTO transitions(run_id,previous,next,reason,at) VALUES(?,?,?,?,?)",
                   (run_id, previous, state, reason, time.time()))

    def _invalidate_in_transaction(self, db, run_id, reason):
        db.execute("UPDATE approvals SET status='invalidated' WHERE run_id=? AND status='active'", (run_id,))
        db.execute("UPDATE runs SET packet_id=NULL WHERE id=?", (run_id,))
        if "blocked" in STATES[self._run(db, run_id)["state"]]:
            self._transition(db, run_id, "blocked", reason)

    def _invalidate(self, db, run_id, reason):
        with transaction(db):
            self._invalidate_in_transaction(db, run_id, reason)

    @staticmethod
    def _backend_identity():
        package = Path(__file__).parents[1]
        sources = sorted([*package.joinpath("core").glob("*.py"), *package.joinpath("agent").glob("*.py")])
        inputs = {}
        for path in [*sources, package.parent / "pyproject.toml", package.parent / "uv.lock"]:
            if path.exists():
                Artifacts._safe(path)
                inputs[path.relative_to(package.parent).as_posix()] = path.read_text()
        return sha(canonical(inputs))

    def _bundle(self, run_id, digest):
        return json.loads(self.artifacts.get(run_id, digest))

    def _integrity(self, db, row):
        """Verify all current references before decisions; invalidate durably on failure."""
        try:
            bundle = self._bundle(row["id"], row["digest"])
            self._bundle(row["id"], row["original_digest"])
            if (bundle["runtime"]["python"] != sys.version or
                    bundle["backend_hash"] != self._backend_identity() or bundle["policy"] != POLICY or bundle["target"] != row["target"] or
                    bundle["artifact_hash"] != sha(canonical(bundle["files"]))):
                raise Rejected("policy or target mismatch")
            for patch_hash in bundle["patches"]:
                parse_patch(self.artifacts.get(row["id"], patch_hash).decode())
            for record in db.execute("SELECT blob_hash FROM evidence WHERE run_id=? AND digest=?",
                                     (row["id"], row["digest"])):
                self.artifacts.get(row["id"], record[0])
            if row["packet_id"]:
                packet = db.execute("SELECT * FROM packets WHERE id=? AND run_id=?",
                                    (row["packet_id"], row["id"])).fetchone()
                if packet is None:
                    raise Rejected("missing packet")
                packet_body = json.loads(self.artifacts.get(row["id"], packet["blob_hash"]))
                if packet_body.get("agent_assessment_hash"):
                    self.artifacts.get(row["id"], packet_body["agent_assessment_hash"])
        except (Rejected, KeyError, ValueError) as error:
            self._invalidate(db, row["id"], "content integrity failure")
            raise Rejected("content integrity failure; approval invalidated") from error
        return bundle

    def create_run(self, candidate="faulty", target="fixture-local"):
        revision(candidate)
        if not isinstance(target, str) or not target or len(target) > 100:
            raise Rejected("invalid target")
        run_id, token = uuid4().hex, secrets.token_urlsafe(32)
        package = Path(__file__).resolve().parents[1]
        for source in (package / "fixtures/tenant_api.py", package / "core/worker.py"):
            Artifacts._safe(source)
        files = {"fixture.py": (package / "fixtures/tenant_api.py").read_text(),
                 "worker.py": (package / "core/worker.py").read_text()}
        git = subprocess.run(["git", "-C", str(package.parent), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=2, check=False)
        provenance = {"git_commit": git.stdout.strip() if git.returncode == 0 else None,
                      "application_version": "0.1.0"}
        # A source-only Python fixture has no dependency lock or build transform.
        # Its rebuilt artifact is the canonical source payload, including safe tests.
        def bundle(version):
            return {"original_revision": "original", "revision": version,
                    "files": files, "policy": POLICY, "target": target,
                    "tool_version": TOOL_VERSION, "backend_hash": self._backend_identity(),
                    "provenance": provenance, "lockfile": sha((package.parent / "uv.lock").read_bytes()) if (package.parent / "uv.lock").exists() else None,
                    "runtime": {"python": sys.version, "mode": "isolated-subprocess"},
                    "artifact_hash": sha(canonical(files)), "patches": []}
        with self._locked() as db:
            original = self.artifacts.put(run_id, canonical(bundle("original")))
            current = self.artifacts.put(run_id, canonical(bundle(candidate)))
            with transaction(db):
                db.execute("INSERT INTO runs(id,token_hash,state,digest,original_digest,target,accepted_digest,created) VALUES(?,?,?,?,?,?,?,?)",
                           (run_id, sha(token.encode()), "created", current, original, target, original, time.time()))
                db.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?)",
                           (run_id, current, None, candidate, "intake", time.time()))
        return {"run_id": run_id, "token": token, "digest": current, "original_digest": original}

    def status(self, run_id, token):
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._integrity(db, row)
            return {k: row[k] for k in ("id", "state", "digest", "original_digest", "target", "accepted_digest", "packet_id")}

    def evidence(self, run_id, token, evidence_id):
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._integrity(db, row)
            record = db.execute("SELECT * FROM evidence WHERE id=? AND run_id=?", (evidence_id, run_id)).fetchone()
            if record is None:
                raise Rejected("unknown evidence in this run")
            return json.loads(self.artifacts.get(run_id, record["blob_hash"]))

    @staticmethod
    def _agent_scope(db, run_id, session_id=None):
        table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_sessions'").fetchone()
        active = db.execute("SELECT id FROM agent_sessions WHERE run_id=? AND status='running'", (run_id,)).fetchone() if table else None
        if (active is not None and active[0] != session_id) or (session_id is not None and active is None):
            raise Rejected("operation conflicts with active orchestration")

    def agent_tools(self, run_id, token, *, session_id=None):
        """Bind a run once; returned callables accept only their exact typed contract."""
        with self._locked() as db:
            self._owner(db, run_id, token)
            self._agent_scope(db, run_id, session_id)
        def bind(name, expected):
            def tool(request):
                if type(request) is not expected or request.run_id != run_id:
                    raise Rejected("tool contract or run scope mismatch")
                # Revalidate even frozen dataclasses potentially constructed by an adapter.
                request.__post_init__()
                return self._tool(name, request, session_id)
            tool.__name__ = name
            return tool
        return MappingProxyType({
            "inspect_candidate": bind("inspect_candidate", InspectInput),
            "run_baseline_tests": bind("run_baseline_tests", BaselineInput),
            "compare_tenant_boundary": bind("compare_tenant_boundary", CompareInput),
            "apply_safe_patch": bind("apply_safe_patch", PatchInput),
        })

    def _execute(self, run_id, bundle, mode):
        """Only fixed snapshot code is executed, with finite time/output bounds."""
        if bundle["runtime"]["python"] != sys.version or bundle["tool_version"] != TOOL_VERSION:
            raise Rejected("runtime changed; create a new run")
        with tempfile.TemporaryDirectory(dir=self.root / "artifacts" / run_id) as temporary:
            directory = Path(temporary)
            for name, body in bundle["files"].items():
                if name not in ("fixture.py", "worker.py", PATCH_PATH):
                    raise Rejected("unknown candidate file")
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            # stdout is a fixed JSON summary; no raw request headers or tracebacks persist.
            completed = subprocess.run(
                [sys.executable, "-I", "-B", str(directory / "worker.py"), mode,
                 bundle["revision"], str(directory)],
                capture_output=True, timeout=15, env={"PATH": os.defpath}, check=False)
            if completed.returncode or len(completed.stdout) > 65536 or len(completed.stderr) > 65536:
                raise Rejected("fixed worker failed or exceeded output limit")
            result = json.loads(completed.stdout)
            if type(result.get("passed")) is not bool:
                raise Rejected("invalid fixed worker result")
            return result

    def _record(self, db, run_id, digest, invocation, check, result):
        evidence_id = uuid4().hex
        body = {"run_id": run_id, "digest": digest, "tool_version": TOOL_VERSION,
                "invocation_id": invocation, "tool_name": db.execute("SELECT tool FROM invocations WHERE id=?", (invocation,)).fetchone()[0],
                "check": check, "at": time.time(),
                "untrusted": True, "result": result}
        content_hash = self.artifacts.put(run_id, canonical(body))
        db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)",
                   (evidence_id, run_id, digest, invocation, check, content_hash, int(result["passed"]), body["at"]))
        return evidence_id, content_hash

    def _tool(self, name, request, session_id=None):
        with self._locked() as db:
            self._agent_scope(db, request.run_id, session_id)
            row = self._run(db, request.run_id)
            bundle = self._integrity(db, row)
            if name == "inspect_candidate":
                if request.version != bundle["revision"]:
                    raise Rejected("stale candidate version")
            elif name == "compare_tenant_boundary":
                if request.original_digest != row["original_digest"] or request.candidate_digest != row["digest"]:
                    raise Rejected("stale comparison digest")
            elif request.digest != row["digest"]:
                raise Rejected("stale candidate digest")
            patch = name == "apply_safe_patch"
            allowed = ("blocked", "repairable") if patch else ("created", "planning", "checking", "candidate_replaced")
            if row["state"] not in allowed:
                raise Rejected("tool is not legal in current state")
            if row["calls"] >= 32:
                self._invalidate(db, row["id"], "tool budget exhausted")
                raise Rejected("tool budget exhausted")
            if patch:
                parse_patch(request.patch)
                if PATCH_PATH in bundle["files"]:
                    raise Rejected("regression test already exists")
                failed = db.execute("SELECT 1 FROM evidence WHERE run_id=? AND digest=? AND check_id='tenant_boundary' AND passed=0",
                                    (row["id"], row["digest"])).fetchone()
                if not failed:
                    raise Rejected("safe repair requires boundary failure evidence")
            invocation = uuid4().hex
            started = time.monotonic()
            with transaction(db):
                if row["state"] == "created":
                    self._transition(db, row["id"], "planning", "first inspection/check")
                if self._run(db, row["id"])["state"] in ("planning", "candidate_replaced"):
                    self._transition(db, row["id"], "checking", "collect current evidence")
                db.execute("UPDATE runs SET calls=calls+1,packet_id=NULL WHERE id=?", (row["id"],))
                db.execute("INSERT INTO invocations VALUES(?,?,?,?,?,?,NULL)",
                           (invocation, row["id"], row["digest"], name, "running", time.time()))
            try:
                if patch:
                    return self._patch(db, row, bundle, request, invocation)
                mode = {"inspect_candidate": "inspect", "run_baseline_tests": "baseline", "compare_tenant_boundary": "boundary"}[name]
                result = self._execute(row["id"], bundle, mode)
                if not isinstance(result, dict) or type(result.get("passed")) is not bool:
                    raise Rejected("invalid worker result")
                if mode == "boundary":
                    expected = {"status": 403, "leaked_fields": []}
                    trials = result.get("trials", [])
                    result["passed"] = (len(trials) == 3 and all(
                        t == {"original": expected, "candidate": expected} for t in trials))
                if mode == "baseline":
                    expected_count = 3 if PATCH_PATH in bundle["files"] else 2
                    result["passed"] = (result["passed"] and result.get("test_count") == expected_count
                                        and result.get("failures") == 0 and result.get("errors") == 0)
                result["duration_seconds"] = time.monotonic() - started
                result["command_id"] = "fixture-" + mode + "-v1"
                result["exit_status"] = 0 if result["passed"] else 1
                with transaction(db):
                    checks = ("manifest_integrity", "fixture_health") if mode == "inspect" else (("baseline_tests",) if mode == "baseline" else ("tenant_boundary",))
                    records = [self._record(db, row["id"], row["digest"], invocation, check,
                                           {"passed": True} if check == "manifest_integrity" else result)
                               for check in checks]
                    if not result["passed"]:
                        self._transition(db, row["id"], "blocked", "required check failed")
                    db.execute("UPDATE invocations SET status='completed',finished=? WHERE id=?", (time.time(), invocation))
                if mode == "inspect":
                    return InspectOutput(row["id"], bundle["revision"], row["original_digest"], row["digest"],
                                         ("GET /health", "GET /documents/{id}"), result["passed"], tuple(r[0] for r in records))
                if mode == "baseline":
                    return BaselineOutput(row["id"], row["digest"], "fixture-baseline-v1", 0 if result["passed"] else 1,
                                          result["test_count"], time.monotonic() - started, records[0][1], records[0][0])
                return CompareOutput(row["id"], row["digest"], result["passed"], tuple(result["trials"]), records[0][1], records[0][0])
            except Exception as error:
                # Never persist exception strings: they can contain credentials or paths.
                with transaction(db):
                    self._record(db, row["id"], row["digest"], invocation, "tool_failure", {"passed": False, "reason": "tool execution failed"})
                    db.execute("UPDATE invocations SET status='failed',finished=? WHERE id=?", (time.time(), invocation))
                self._invalidate(db, row["id"], "tool failed; preserve evidence")
                raise Rejected("tool failed; run blocked") from error

    def _patch(self, db, row, bundle, request, invocation):
        path, content = parse_patch(request.patch)
        bundle["files"][path] = content
        patch_hash = self.artifacts.put(row["id"], request.patch.encode())
        bundle["patches"].append(patch_hash)
        bundle["artifact_hash"] = sha(canonical(bundle["files"]))
        new_digest = self.artifacts.put(row["id"], canonical(bundle))
        repair_id = uuid4().hex
        with transaction(db):
            if row["state"] == "blocked":
                self._transition(db, row["id"], "repairable", "allowlisted test generation")
            self._transition(db, row["id"], "checking", "new derived candidate requires all gates")
            db.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?)", (row["id"], new_digest, row["digest"], bundle["revision"], "safe_patch", time.time()))
            db.execute("INSERT INTO repairs VALUES(?,?,?,?,?,?)", (repair_id, row["id"], row["digest"], new_digest, patch_hash, time.time()))
            db.execute("UPDATE runs SET digest=?,packet_id=NULL WHERE id=?", (new_digest, row["id"]))
            db.execute("UPDATE invocations SET status='completed',finished=? WHERE id=?", (time.time(), invocation))
        return PatchOutput(row["id"], row["digest"], new_digest, repair_id)

    def replace_candidate(self, run_id, token, candidate, actor):
        """Owner-only corrected seed selection; generated regression is carried forward."""
        if candidate != "corrected" or not isinstance(actor, str) or not actor.strip():
            raise Rejected("explicit owner and corrected revision required")
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._agent_scope(db, run_id)
            bundle = self._integrity(db, row)
            if row["state"] not in ("blocked", "ready_for_approval", "approved"):
                raise Rejected("candidate replacement not allowed here")
            bundle["revision"] = candidate
            new_digest = self.artifacts.put(run_id, canonical(bundle))
            if new_digest == row["digest"]:
                raise Rejected("replacement must change candidate")
            with transaction(db):
                db.execute("UPDATE approvals SET status='invalidated' WHERE run_id=? AND status='active'", (run_id,))
                if row["state"] != "blocked":
                    self._transition(db, run_id, "blocked", "owner changes content")
                self._transition(db, run_id, "candidate_replaced", "owner selected corrected application; preserve test")
                db.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?)", (run_id, new_digest, row["digest"], candidate, actor, time.time()))
                db.execute("UPDATE runs SET digest=?,packet_id=NULL WHERE id=?", (new_digest, run_id))
            return new_digest

    def _readiness(self, db, row):
        records = list(db.execute("SELECT * FROM evidence WHERE run_id=? AND digest=? ORDER BY at,id", (row["id"], row["digest"])))
        by_check = {record["check_id"]: record for record in records}
        exceptions = [check for check in CHECKS if check not in by_check or not by_check[check]["passed"]]
        # Any contradictory or failed current evidence fails closed, even after a later pass.
        if any(not r["passed"] for r in records):
            exceptions.append("failed_or_contradictory_evidence")
        return records, exceptions

    def assemble_decision_packet(self, run_id, token, digest, agent_explanation="", *, assessment_hash=None, agent_session_id=None):
        # Explanations are deliberately not persisted in Phase 2: unrestricted text
        # needs a dedicated redaction boundary before model integration.
        if agent_explanation:
            raise Rejected("free-text model explanations are not enabled in Phase 2")
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._agent_scope(db, run_id, agent_session_id)
            self._integrity(db, row)
            if digest != row["digest"]:
                raise Rejected("stale packet digest")
            if assessment_hash is not None:
                assessment = json.loads(self.artifacts.get(run_id, assessment_hash))
                if assessment.get("run_id") != run_id or assessment.get("candidate_digest") != digest:
                    raise Rejected("assessment scope mismatch")
            if row["packet_id"]:
                record = db.execute("SELECT * FROM packets WHERE id=?", (row["packet_id"],)).fetchone()
                prior_packet = json.loads(self.artifacts.get(run_id, record["blob_hash"]))
                if assessment_hash is not None and prior_packet.get("agent_assessment_hash") != assessment_hash:
                    self._invalidate(db, run_id, "agent assessment changed")
                    raise Rejected("packet assessment changed; approval invalidated")
                return prior_packet
            if row["state"] not in ("checking", "blocked"):
                raise Rejected("packet assembly not legal here")
            records, exceptions = self._readiness(db, row)
            ready = not exceptions and row["state"] == "checking"
            packet = {"packet_id": uuid4().hex, "run_id": run_id, "candidate_digest": digest,
                      "agent_assessment_hash": assessment_hash,
                      "policy_version": POLICY["policy_version"], "required_check_ids": list(CHECKS),
                      "evidence_ids": [r["id"] for r in records],
                      "repair_ids": [r[0] for r in db.execute("SELECT id FROM repairs WHERE run_id=? ORDER BY at,id", (run_id,))],
                      "unresolved_exceptions": exceptions, "ready": ready,
                      "recommendation": "approve" if ready else "blocked", "created": time.time()}
            packet_hash = self.artifacts.put(run_id, canonical(packet))
            with transaction(db):
                db.execute("INSERT INTO packets VALUES(?,?,?,?,?,?)", (packet["packet_id"], run_id, digest, packet_hash, int(ready), packet["created"]))
                db.execute("UPDATE runs SET packet_id=? WHERE id=?", (packet["packet_id"], run_id))
                if ready:
                    self._transition(db, run_id, "ready_for_approval", "all deterministic gates pass")
            return packet

    def approve(self, run_id, token, packet_id, actor, ttl_seconds=300):
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise Rejected("approval actor required")
        if type(ttl_seconds) not in (float, int) or not math.isfinite(ttl_seconds) or not 0 < ttl_seconds <= 3600:
            raise Rejected("approval expiry must be within one hour")
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._agent_scope(db, run_id)
            self._integrity(db, row)
            if row["state"] != "ready_for_approval" or row["packet_id"] != packet_id:
                raise Rejected("current ready packet required")
            _, exceptions = self._readiness(db, row)
            if exceptions:
                raise Rejected("readiness changed")
            packet = db.execute("SELECT * FROM packets WHERE id=? AND run_id=?", (packet_id, run_id)).fetchone()
            if not packet["ready"] or packet["digest"] != row["digest"]:
                raise Rejected("packet not ready")
            approval_id, issued = uuid4().hex, time.time()
            with transaction(db):
                db.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                           (approval_id, secrets.token_hex(32), run_id, row["digest"], packet_id, packet["blob_hash"], actor,
                            row["target"], "promote_candidate", issued, issued + ttl_seconds, "active"))
                self._transition(db, run_id, "approved", "owner approved exact packet and scope")
            return approval_id

    def promote(self, run_id, token, approval_id, idempotency_key):
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
            raise Rejected("bounded idempotency key required")
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._agent_scope(db, run_id)
            prior = db.execute("SELECT * FROM promotions WHERE run_id=? AND (approval_id=? OR idempotency_key=?)",
                               (run_id, approval_id, idempotency_key)).fetchone()
            if prior:
                if prior["approval_id"] != approval_id:
                    raise Rejected("idempotency key belongs to another approval")
                if prior["status"] == "pending":
                    self._finish_promotion(db, prior)
                return dict(db.execute("SELECT * FROM promotions WHERE id=?", (prior["id"],)).fetchone())
            self._integrity(db, row)
            approval = db.execute("SELECT * FROM approvals WHERE id=? AND run_id=?", (approval_id, run_id)).fetchone()
            if approval is None:
                raise Rejected("unknown approval for run")
            packet = db.execute("SELECT * FROM packets WHERE id=? AND run_id=?",
                                (approval["packet_id"], run_id)).fetchone()
            valid = (packet is not None and packet["blob_hash"] == approval["packet_hash"] and row["state"] == "approved" and approval["status"] == "active" and
                     approval["digest"] == row["digest"] and approval["packet_id"] == row["packet_id"] and
                     approval["target"] == row["target"] and approval["action"] == "promote_candidate" and
                     approval["issued"] <= time.time() < approval["expires"])
            if not valid:
                if approval["status"] == "active" and approval["digest"] == row["digest"]:
                    self._invalidate(db, run_id, "stale or expired approval")
                raise Rejected("stale or expired approval")
            promotion_id = uuid4().hex
            with transaction(db):
                self._transition(db, run_id, "promoting", "consume owner approval")
                db.execute("UPDATE approvals SET status='consumed' WHERE id=?", (approval_id,))
                db.execute("UPDATE runs SET accepted_digest=? WHERE id=?", (row["digest"], run_id))
                db.execute("INSERT INTO promotions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (promotion_id, run_id, approval_id, idempotency_key, row["accepted_digest"], row["digest"], "pending", None, "not_needed", time.time(), None))
            pending = db.execute("SELECT * FROM promotions WHERE id=?", (promotion_id,)).fetchone()
            self._finish_promotion(db, pending)
            return dict(db.execute("SELECT * FROM promotions WHERE id=?", (promotion_id,)).fetchone())

    def _finish_promotion(self, db, promotion):
        row = self._run(db, promotion["run_id"])
        try:
            bundle = self._bundle(row["id"], promotion["new_digest"])
            self._integrity(db, row)
            verified = (row["state"] == "promoting" and row["accepted_digest"] == promotion["new_digest"] and
                        self._execute(row["id"], bundle, "inspect")["passed"] and
                        self._execute(row["id"], bundle, "boundary")["passed"])
        except Exception:
            verified = False
        with transaction(db):
            if not verified:
                db.execute("UPDATE runs SET accepted_digest=? WHERE id=?", (promotion["prior_digest"], row["id"]))
            self._transition(db, row["id"], "verified" if verified else "promotion_failed", "verify accepted slot" if verified else "rollback accepted slot")
            db.execute("UPDATE promotions SET status=?,verification=?,rollback=?,finished=? WHERE id=?",
                       ("verified" if verified else "rolled_back", int(verified), "not_needed" if verified else "restored_prior_digest", time.time(), promotion["id"]))

    def _recover(self, db):
        # flock guarantees that another live process cannot still own these intents.
        interrupted = list(db.execute("SELECT * FROM invocations WHERE status='running'"))
        for invocation in interrupted:
            with transaction(db):
                db.execute("UPDATE invocations SET status='interrupted',finished=? WHERE id=?", (time.time(), invocation["id"]))
            # No partial evidence is accepted. Checking may resume with fresh calls.
            row = self._run(db, invocation["run_id"])
            self._integrity(db, row)
        for promotion in list(db.execute("SELECT * FROM promotions WHERE status='pending'")):
            self._finish_promotion(db, promotion)
        ambiguous = db.execute("SELECT id FROM runs WHERE state='promoting' AND id NOT IN (SELECT run_id FROM promotions WHERE status='pending')").fetchone()
        if ambiguous:
            raise Rejected("ambiguous promotion state; preserve database for owner review")
        for row in list(db.execute("SELECT * FROM runs WHERE state='approved'")):
            try:
                self._integrity(db, row)
            except Rejected:
                continue
            approval = db.execute("SELECT * FROM approvals WHERE run_id=? AND status='active'", (row["id"],)).fetchone()
            if approval is None or not approval["issued"] <= time.time() < approval["expires"]:
                self._invalidate(db, row["id"], "approval expired on recovery")
