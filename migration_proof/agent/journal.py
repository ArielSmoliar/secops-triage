"""Durable orchestration attempts; raw model text and credentials are never stored."""
from dataclasses import asdict
import json
import time
from uuid import uuid4

from migration_proof.core.artifacts import canonical
from migration_proof.core.contracts import Rejected
from migration_proof.core.store import transaction
from .contracts import MODEL_ID, SDK_VERSION, STOP_REASONS, Limits

SCHEMA = '''
CREATE TABLE IF NOT EXISTS agent_sessions(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 initial_digest TEXT NOT NULL, final_digest TEXT,
 model_id TEXT NOT NULL, sdk_version TEXT NOT NULL, limits_json TEXT NOT NULL,
 status TEXT NOT NULL, reason TEXT, model_calls INTEGER NOT NULL DEFAULT 0,
 tool_calls INTEGER NOT NULL DEFAULT 0, cost_usd REAL NOT NULL DEFAULT 0 CHECK(cost_usd=0),
 summary_hash TEXT, started REAL NOT NULL, finished REAL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_agent_per_run ON agent_sessions(run_id)
 WHERE status='running';
CREATE TABLE IF NOT EXISTS agent_events(
 id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES agent_sessions(id),
 kind TEXT NOT NULL, label TEXT NOT NULL, at REAL NOT NULL);
'''


class Journal:
    def __init__(self, store):
        self.store = store
        with store._locked() as db:
            db.executescript(SCHEMA)

    def start(self, run_id, token, limits):
        # The caller must hold the run orchestration flock across this operation.
        with self.store._locked() as db:
            row = self.store._owner(db, run_id, token)
            self.store._integrity(db, row)
            previous = db.execute("SELECT id FROM agent_sessions WHERE run_id=? AND status='running'", (run_id,)).fetchone()
            if previous:
                self._end(db, previous[0], "interrupted", None)
                raise Rejected("interrupted orchestration preserved; start a fresh run")
            if row["state"] not in ("created", "planning", "checking", "candidate_replaced"):
                raise Rejected("run is not available for orchestration")
            session_id = uuid4().hex
            with transaction(db):
                db.execute("INSERT INTO agent_sessions(id,run_id,initial_digest,model_id,sdk_version,limits_json,status,started) VALUES(?,?,?,?,?,?,?,?)",
                           (session_id, run_id, row["digest"], MODEL_ID, SDK_VERSION,
                            canonical(asdict(limits)).decode(), "running", time.time()))
            return session_id

    def row(self, session_id):
        with self.store._locked() as db:
            row = db.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise Rejected("unknown orchestration")
            return dict(row)

    def reserve(self, session_id, kind, label):
        if kind not in ("model", "tool"):
            raise Rejected("unknown event kind")
        with self.store._locked() as db:
            row = db.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
            if row is None or row["status"] != "running":
                raise Rejected("orchestration is not running")
            limits = Limits(**json.loads(row["limits_json"]))
            limit = limits.model_calls if kind == "model" else limits.tool_calls
            column = "model_calls" if kind == "model" else "tool_calls"
            if row[column] >= limit:
                raise Rejected(kind + "_limit")
            with transaction(db):
                db.execute(f"UPDATE agent_sessions SET {column}={column}+1 WHERE id=?", (session_id,))
                db.execute("INSERT INTO agent_events(session_id,kind,label,at) VALUES(?,?,?,?)",
                           (session_id, kind, label, time.time()))

    def _end(self, db, session_id, reason, summary):
        if reason not in STOP_REASONS:
            raise Rejected("unknown stop reason")
        session = db.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
        if session["status"] != "running":
            return
        run = self.store._run(db, session["run_id"])
        content_hash = self.store.artifacts.put(run["id"], canonical(summary)) if summary else None
        with transaction(db):
            db.execute("UPDATE agent_sessions SET status=?,reason=?,final_digest=?,summary_hash=?,finished=? WHERE id=?",
                       ("completed" if reason == "completed" else "stopped", reason, run["digest"], content_hash, time.time(), session_id))
            if reason != "completed":
                self.store._invalidate_in_transaction(db, run["id"], "orchestration stopped: " + reason)

    def finish(self, session_id, reason, summary=None):
        with self.store._locked() as db:
            row = db.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise Rejected("unknown orchestration")
            self._end(db, session_id, reason, summary)

    def read(self, run_id, token, session_id):
        with self.store._locked() as db:
            self.store._owner(db, run_id, token)
            row = db.execute("SELECT * FROM agent_sessions WHERE id=? AND run_id=?", (session_id, run_id)).fetchone()
            if row is None:
                raise Rejected("unknown orchestration for run")
            result = dict(row)
            result["events"] = [dict(r) for r in db.execute("SELECT kind,label,at FROM agent_events WHERE session_id=? ORDER BY id", (session_id,))]
            result["summary"] = json.loads(self.store.artifacts.get(run_id, row["summary_hash"])) if row["summary_hash"] else None
            return result
