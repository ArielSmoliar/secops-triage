"""Owner-issued, single-attempt inference grants and non-refundable reservations."""
from dataclasses import asdict
import json
import time
from uuid import uuid4

from migration_proof.core.artifacts import PATCH_PATH, REGRESSION, canonical
from migration_proof.core.contracts import Rejected
from migration_proof.core.store import transaction
from .journal import Journal
from .openai_preflight import (OpenAIPlan, MODEL_ID, MODEL_CONTEXT_TOKENS,
                               INPUT_NANODOLLARS_PER_TOKEN, OUTPUT_NANODOLLARS_PER_TOKEN, preflight)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS inference_grants(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 initial_digest TEXT NOT NULL, model_id TEXT NOT NULL, plan_json TEXT NOT NULL,
 actor TEXT NOT NULL, issued REAL NOT NULL, expires REAL NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('issued','claimed','closed','revoked')),
 session_id TEXT UNIQUE REFERENCES agent_sessions(id), UNIQUE(run_id,initial_digest));
CREATE UNIQUE INDEX IF NOT EXISTS one_outstanding_inference_grant ON inference_grants(run_id)
 WHERE status IN ('issued','claimed');
CREATE TABLE IF NOT EXISTS inference_requests(
 id TEXT PRIMARY KEY, grant_id TEXT NOT NULL REFERENCES inference_grants(id),
 ordinal INTEGER NOT NULL, reserved_microusd INTEGER NOT NULL CHECK(reserved_microusd>0),
 status TEXT NOT NULL CHECK(status IN ('pending','recorded','unknown')),
 input_tokens INTEGER, output_tokens INTEGER, estimated_microusd INTEGER,
 started REAL NOT NULL, finished REAL, UNIQUE(grant_id,ordinal));
'''


SCHEMA_VERSION = 2


def _create_schema(db):
    # executescript commits implicitly; execute each statement to keep migration atomic.
    for statement in SCHEMA.split(";"):
        if statement.strip():
            db.execute(statement)
    db.execute("CREATE TABLE inference_schema(version INTEGER NOT NULL)")
    db.execute("INSERT INTO inference_schema VALUES(?)", (SCHEMA_VERSION,))


def _ensure_schema(db):
    versioned = db.execute("SELECT 1 FROM sqlite_master WHERE name='inference_schema'").fetchone()
    if versioned:
        versions = db.execute("SELECT version FROM inference_schema").fetchall()
        if len(versions) != 1 or versions[0][0] != SCHEMA_VERSION:
            raise Rejected("unsupported inference schema")
        return
    legacy = db.execute("SELECT 1 FROM sqlite_master WHERE name='inference_grants'").fetchone()
    if legacy and db.execute("SELECT 1 FROM agent_sessions WHERE status='running'").fetchone():
        raise Rejected("recover or finish active sessions before inference migration")
    with transaction(db):
        if legacy:
            db.execute("ALTER TABLE inference_requests RENAME TO inference_requests_v1")
            db.execute("ALTER TABLE inference_grants RENAME TO inference_grants_v1")
        _create_schema(db)
        if legacy:
            db.execute("INSERT INTO inference_grants SELECT * FROM inference_grants_v1")
            db.execute("INSERT INTO inference_requests SELECT * FROM inference_requests_v1")
            db.execute("DROP TABLE inference_requests_v1")
            db.execute("DROP TABLE inference_grants_v1")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise Rejected("inference migration failed integrity check")


class SpendLedger:
    def __init__(self, store):
        self.store = store
        Journal(store)
        with store._locked() as db:
            _ensure_schema(db)

    def authorize(self, run_id, token, plan, actor, *, ttl_seconds=600):
        """Backend owner action. Call only after explicit authorization to spend."""
        if (type(plan) is not OpenAIPlan or type(actor) is not str or not actor.strip()
                or len(actor) > 80 or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900):
            raise Rejected("invalid inference authorization")
        if not preflight(plan)["pricing_fresh"]:
            raise Rejected("pricing reverification required")
        with self.store._locked() as db:
            run = self.store._owner(db, run_id, token)
            self.store._integrity(db, run)
            self.store._agent_scope(db, run_id)
            bundle = self.store._bundle(run_id, run["digest"])
            if plan.scenario == "faulty":
                eligible = run["state"] == "created" and bundle["revision"] == "faulty"
            else:
                # Only the existing owner-only corrected transition may enter this path.
                eligible = (run["state"] == "candidate_replaced" and bundle["revision"] == "corrected"
                            and bundle["files"].get(PATCH_PATH) == REGRESSION
                            and bool(bundle["patches"]))
            if not eligible:
                raise Rejected("candidate does not match authorized evaluation scenario")
            if db.execute("SELECT 1 FROM inference_grants WHERE run_id=? AND (initial_digest=? OR status IN ('issued','claimed'))",
                          (run_id, run["digest"])).fetchone():
                raise Rejected("digest already granted or prior grant still outstanding")
            grant_id = uuid4().hex
            now = time.time()
            with transaction(db):
                db.execute("INSERT INTO inference_grants VALUES(?,?,?,?,?,?,?,?,?,NULL)",
                           (grant_id, run_id, run["digest"], MODEL_ID, canonical(asdict(plan)).decode(),
                            actor, now, now + ttl_seconds, "issued"))
            return grant_id

    def plan(self, run_id, token, grant_id):
        with self.store._locked() as db:
            self.store._owner(db, run_id, token)
            grant = db.execute("SELECT * FROM inference_grants WHERE id=? AND run_id=?", (grant_id, run_id)).fetchone()
            if grant is None:
                raise Rejected("unknown grant for run")
            return OpenAIPlan(**json.loads(grant["plan_json"]))

    def claim(self, run_id, token, grant_id, session_id):
        with self.store._locked() as db:
            run = self.store._owner(db, run_id, token)
            self.store._integrity(db, run)
            grant = db.execute("SELECT * FROM inference_grants WHERE id=? AND run_id=?", (grant_id, run_id)).fetchone()
            session = db.execute("SELECT * FROM agent_sessions WHERE id=? AND run_id=?", (session_id, run_id)).fetchone()
            if (grant is None or grant["status"] != "issued" or grant["expires"] <= time.time()
                    or grant["initial_digest"] != run["digest"] or session is None
                    or session["status"] != "running" or session["model_id"] != MODEL_ID
                    or session["initial_digest"] != run["digest"]):
                raise Rejected("inference grant cannot be claimed")
            with transaction(db):
                db.execute("UPDATE inference_grants SET status='claimed',session_id=? WHERE id=?", (session_id, grant_id))

    def reserve(self, session_id):
        with self.store._locked() as db:
            grant = db.execute("SELECT * FROM inference_grants WHERE session_id=?", (session_id,)).fetchone()
            session = db.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
            if (grant is None or grant["status"] != "claimed" or grant["expires"] <= time.time()
                    or session is None or session["status"] != "running" or session["model_id"] != MODEL_ID):
                raise Rejected("inference grant inactive")
            self.store._integrity(db, self.store._run(db, grant["run_id"]))
            plan = OpenAIPlan(**json.loads(grant["plan_json"]))
            if not preflight(plan)["pricing_fresh"]:
                raise Rejected("pricing reverification required")
            totals = db.execute("SELECT COUNT(*),COALESCE(SUM(reserved_microusd),0) FROM inference_requests WHERE grant_id=?", (grant["id"],)).fetchone()
            # Never send another request after an unresolved/failed dispatch.
            uncertain = db.execute("SELECT 1 FROM inference_requests WHERE grant_id=? AND status!='recorded'", (grant["id"],)).fetchone()
            if uncertain or totals[0] >= plan.model_calls or totals[1] + plan.per_call_microusd > plan.budget_microusd:
                raise Rejected("inference budget unavailable")
            request_id = uuid4().hex
            with transaction(db):
                db.execute("INSERT INTO inference_requests(id,grant_id,ordinal,reserved_microusd,status,started) VALUES(?,?,?,?,?,?)",
                           (request_id, grant["id"], totals[0] + 1, plan.per_call_microusd, "pending", time.time()))
            return request_id, plan

    def settle(self, session_id, request_id, usage):
        with self.store._locked() as db:
            row = db.execute("SELECT r.*,g.plan_json FROM inference_requests r JOIN inference_grants g ON r.grant_id=g.id WHERE r.id=? AND g.session_id=?", (request_id, session_id)).fetchone()
            if row is None or row["status"] != "pending":
                raise Rejected("request is not pending for session")
            plan = OpenAIPlan(**json.loads(row["plan_json"]))
            valid = (type(usage) is dict and all(type(usage.get(k)) is int for k in
                     ("prompt_tokens", "completion_tokens", "total_tokens")))
            if valid:
                inputs, outputs = usage["prompt_tokens"], usage["completion_tokens"]
                valid = (0 < inputs <= MODEL_CONTEXT_TOKENS and 0 <= outputs <= plan.max_output_tokens
                         and usage["total_tokens"] == inputs + outputs)
            if not valid:
                with transaction(db):
                    db.execute("UPDATE inference_requests SET status='unknown',finished=? WHERE id=?", (time.time(), request_id))
                raise Rejected("invalid inference usage")
            estimate = (inputs * INPUT_NANODOLLARS_PER_TOKEN + outputs * OUTPUT_NANODOLLARS_PER_TOKEN + 999) // 1000
            with transaction(db):
                db.execute("UPDATE inference_requests SET status='recorded',input_tokens=?,output_tokens=?,estimated_microusd=?,finished=? WHERE id=?",
                           (inputs, outputs, estimate, time.time(), request_id))

    def uncertain(self, session_id, request_id):
        with self.store._locked() as db, transaction(db):
            db.execute("UPDATE inference_requests SET status='unknown',finished=? WHERE id=? AND status='pending' AND grant_id IN (SELECT id FROM inference_grants WHERE session_id=?)",
                       (time.time(), request_id, session_id))

    def revoke(self, run_id, token, grant_id):
        with self.store._locked() as db:
            self.store._owner(db, run_id, token)
            row = db.execute("SELECT * FROM inference_grants WHERE id=? AND run_id=?", (grant_id, run_id)).fetchone()
            if row is None:
                raise Rejected("unknown grant for run")
            with transaction(db):
                db.execute("UPDATE inference_grants SET status='revoked' WHERE id=? AND status IN ('issued','claimed')", (grant_id,))
            # An already dispatched request may still be billed; reservations remain.

    def read(self, run_id, token, grant_id):
        with self.store._locked() as db:
            self.store._owner(db, run_id, token)
            row = db.execute("SELECT * FROM inference_grants WHERE id=? AND run_id=?", (grant_id, run_id)).fetchone()
            if row is None:
                raise Rejected("unknown grant for run")
            result = dict(row)
            result["requests"] = [dict(r) for r in db.execute("SELECT * FROM inference_requests WHERE grant_id=? ORDER BY ordinal", (grant_id,))]
            result["reserved_microusd"] = sum(r["reserved_microusd"] for r in result["requests"])
            result["reported_estimate_microusd"] = sum(r["estimated_microusd"] or 0 for r in result["requests"])
            result["usage_complete"] = all(r["status"] == "recorded" for r in result["requests"])
            return result
