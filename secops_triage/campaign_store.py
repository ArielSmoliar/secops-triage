"""Host-only single-store campaign accounting; never an agent tool or spending grant.

All runs for a campaign must live in this Store. Prepare repeated cases lazily.
Host attestations record authority; they do not infer analyst participation.
"""
from contextlib import contextmanager
import fcntl
import hmac
import json
import os
import secrets

from .campaign import build_plan
from .contracts import Rejected, bounded, canonical, sha
from .store import now

SCHEMA = '''
CREATE TABLE IF NOT EXISTS campaigns(
 id TEXT PRIMARY KEY, plan_hash TEXT UNIQUE NOT NULL, plan TEXT NOT NULL,
 owner_hash TEXT NOT NULL, authority TEXT);
CREATE TABLE IF NOT EXISTS campaign_slots(
 campaign_id TEXT NOT NULL REFERENCES campaigns(id), slot_id TEXT NOT NULL,
 run_id TEXT UNIQUE NOT NULL REFERENCES runs(id), grant_id TEXT UNIQUE,
 state TEXT NOT NULL, session_id TEXT UNIQUE, result_hash TEXT,
 PRIMARY KEY(campaign_id,slot_id));
CREATE TABLE IF NOT EXISTS campaign_evaluations(
 id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, slot_id TEXT NOT NULL,
 result_hash TEXT NOT NULL, content_hash TEXT NOT NULL, outcome TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS campaign_events(
 id INTEGER PRIMARY KEY, campaign_id TEXT NOT NULL, slot_id TEXT NOT NULL,
 stage TEXT NOT NULL, at TEXT NOT NULL);
'''
GATES = ('analyst_feedback', 'case_acceptance', 'price_verification',
         'spending_authorization', 'build_verification')


def binding(db, run):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='campaign_slots'").fetchone():
        return None
    return db.execute('SELECT * FROM campaign_slots WHERE run_id=?', (run,)).fetchone()


def claim(db, run, grant, session):
    """Fence paid grant consumption inside the worker's exclusive store lock."""
    slot = binding(db, run)
    if slot is None:
        return
    if slot['state'] != 'dispatching' or slot['grant_id'] != grant or slot['session_id'] is not None or not isinstance(session, str):
        raise Rejected('campaign dispatch missing or already consumed')
    plan = json.loads(db.execute('SELECT plan FROM campaigns WHERE id=?', (slot['campaign_id'],)).fetchone()[0])
    CampaignStore._fresh(plan)
    CampaignStore._prior(db, plan, slot['campaign_id'], slot['slot_id'])
    db.execute('UPDATE campaign_slots SET session_id=? WHERE run_id=?', (session, run))
    db.commit()  # consumption remains even if later provider setup fails


class CampaignStore:
    def __init__(self, store):
        self.store = store
        with store._locked() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _lifecycle(self):
        path = self.store.root / '.campaign-host.lock'
        self.store._safe(path)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _campaign(self, db, campaign, token):
        row = db.execute('SELECT * FROM campaigns WHERE id=?', (campaign,)).fetchone()
        if not row or not isinstance(token, str) or not hmac.compare_digest(row['owner_hash'], sha(token.encode())):
            raise Rejected('campaign owner required')
        plan = json.loads(row['plan'])
        if plan['plan_hash'] != row['plan_hash'] or sha(canonical({k:v for k,v in plan.items() if k != 'plan_hash'})) != row['plan_hash']:
            raise Rejected('campaign plan corrupted')
        return row, plan

    @staticmethod
    def _fresh(plan):
        current = build_plan()
        if current['worktree_dirty'] or not current['source_commit'] or plan != current:
            raise Rejected('campaign needs exact clean execution build and plan')

    @staticmethod
    def _slot(plan, slot):
        values = [s for s in plan['slots'] if s['slot_id'] == slot]
        if len(values) != 1 or values[0]['milestone'] != 'M2' or values[0]['mode'] != 'proposed_live':
            raise Rejected('slot is not bound M2 live scope')
        return values[0]

    @staticmethod
    def _event(db, campaign, slot, stage):
        db.execute('INSERT INTO campaign_events(campaign_id,slot_id,stage,at) VALUES(?,?,?,?)',
                   (campaign, slot, stage, now()))

    def register(self, plan, token):
        self._fresh(plan)
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise Rejected('private campaign owner capability required')
        campaign = secrets.token_hex(16)
        with self.store._locked() as db:
            if db.execute('SELECT 1 FROM campaigns WHERE plan_hash=?', (plan['plan_hash'],)).fetchone():
                raise Rejected('plan already registered; resume existing campaign')
            db.execute('INSERT INTO campaigns VALUES(?,?,?,?,NULL)',
                       (campaign, plan['plan_hash'], canonical(plan).decode(), sha(token.encode())))
            db.commit()
        return campaign

    def record_authority(self, campaign, token, actor, references):
        """Explicit host attestations for this exact M2 plan; issues no run grant.

        Call only after actual gate evidence and new owner spending approval exist.
        References are trusted host assertions, not independently authenticated.
        """
        bounded(actor, 200)
        if type(references) is not dict or set(references) != set(GATES):
            raise Rejected('all campaign gate references required')
        for value in references.values():
            bounded(value)
        with self.store._locked() as db:
            row, plan = self._campaign(db, campaign, token)
            self._fresh(plan)
            if row['authority'] is not None:
                raise Rejected('authority already recorded')
            value = {'actor': actor, 'references': references, 'plan_hash': plan['plan_hash'], 'scope': 'M2', 'at': now()}
            db.execute('UPDATE campaigns SET authority=? WHERE id=?', (canonical(value).decode(), campaign))
            db.commit()

    def reserve(self, campaign, token, slot_id, run, run_token):
        """Durably consume a slot with a fresh run; neither grant nor dispatch."""
        from .agent import SCHEMA as AGENT_SCHEMA
        from .agent_spend import SCHEMA as SPEND_SCHEMA
        with self.store._locked() as db:
            db.executescript(AGENT_SCHEMA + SPEND_SCHEMA)
            _, plan = self._campaign(db, campaign, token)
            self._fresh(plan)
            slot = self._slot(plan, slot_id)
            row = self.store._owner(db, run, run_token)
            self.store._current(db, row)
            self.store._load(row)
            if row['snapshot'] != slot['fixture_sha256'] or row['engine'] != slot['execution_engine_hash']:
                raise Rejected('wrong case or build for slot')
            if row['state'] != 'created' or row['packet_hash'] or any(db.execute(query, (run,)).fetchone() for query in (
                    'SELECT 1 FROM invocations WHERE run_id=?', 'SELECT 1 FROM secops_agent_sessions WHERE run_id=?',
                    'SELECT 1 FROM secops_grants WHERE run_id=?')):
                raise Rejected('slot requires untouched run before authorization')
            if binding(db, run) or db.execute('SELECT 1 FROM campaign_slots WHERE campaign_id=? AND slot_id=?', (campaign, slot_id)).fetchone():
                raise Rejected('slot or run already reserved; no retry')
            self._prior(db, plan, campaign, slot_id, self.store._get)
            db.execute('INSERT INTO campaign_slots VALUES(?,?,?,?,?,?,?)', (campaign, slot_id, run, None, 'reserved', None, None))
            self._event(db, campaign, slot_id, 'reserved')
            db.commit()

    @staticmethod
    def _prior(db, plan, campaign, slot_id, read=None):
        prior = [s['slot_id'] for s in plan['slots'] if s['milestone'] == 'M2']
        for previous in prior[:prior.index(slot_id)]:
            p = db.execute('SELECT state,result_hash FROM campaign_slots WHERE campaign_id=? AND slot_id=?', (campaign, previous)).fetchone()
            if not p or p['state'] not in ('completed', 'incomplete'):
                raise Rejected('prior slot incomplete or stopped; revise campaign')
            reviews = db.execute('SELECT outcome,content_hash FROM campaign_evaluations WHERE campaign_id=? AND slot_id=? AND result_hash=? ORDER BY rowid', (campaign, previous, p['result_hash'])).fetchall()
            previous_run = db.execute('SELECT run_id FROM campaign_slots WHERE campaign_id=? AND slot_id=?', (campaign, previous)).fetchone()[0]
            for saved in reviews:
                if read is not None:
                    record = read(previous_run, saved['content_hash'])
                    if record['result_hash'] != p['result_hash'] or record['score']['outcome'] != saved['outcome']:
                        raise Rejected('evaluation binding corrupted')
            if not reviews or any(r['outcome'] == 'fail' for r in reviews) or reviews[-1]['outcome'] != 'pass':
                raise Rejected('prior slot needs passing bound claim review; failed cases stop campaign')

    def attach_grant(self, campaign, token, slot_id, run_token, grant):
        from .agent_spend import identity, price
        import time
        with self.store._locked() as db:
            authority, plan = self._campaign(db, campaign, token)
            self._fresh(plan)
            if not authority['authority']:
                raise Rejected('campaign gates and explicit authority pending')
            slot = self._bound(db, campaign, slot_id)
            row = self.store._owner(db, slot['run_id'], run_token)
            self.store._current(db, row); self.store._load(row)
            g = db.execute('SELECT * FROM secops_grants WHERE id=?', (grant,)).fetchone()
            if (slot['state'] != 'reserved' or slot['grant_id'] is not None or row['state'] != 'created'
                    or not g or g['run_id'] != row['id'] or g['identity'] != identity(row)
                    or g['state'] != 'issued' or g['expires'] <= time.time()
                    or db.execute('SELECT 1 FROM secops_requests WHERE grant_id=?', (grant,)).fetchone()):
                raise Rejected('grant is not fresh authority for reserved run')
            price()
            db.execute("UPDATE campaign_slots SET grant_id=?,state='authorized' WHERE campaign_id=? AND slot_id=?", (grant, campaign, slot_id))
            self._event(db, campaign, slot_id, 'authorized')
            db.commit()

    @staticmethod
    def _bound(db, campaign, slot_id):
        row = db.execute('SELECT * FROM campaign_slots WHERE campaign_id=? AND slot_id=?', (campaign, slot_id)).fetchone()
        if row is None:
            raise Rejected('slot is not reserved')
        return row

    def execute(self, campaign, token, slot_id, run_token, key_file):
        """One supervised dispatch using an already-issued, bound grant. Never retries."""
        from .agent_runner import run_agent
        from .live import load_key
        with self._lifecycle():
            with self.store._locked() as db:
                _, plan = self._campaign(db, campaign, token)
                self._fresh(plan)
                self._prior(db, plan, campaign, slot_id, self.store._get)
                slot = self._bound(db, campaign, slot_id)
                row = self.store._owner(db, slot['run_id'], run_token)
                self.store._current(db, row); self.store._load(row)
                if slot['state'] != 'authorized' or row['state'] != 'created':
                    raise Rejected('slot cannot dispatch again')
                g = db.execute('SELECT * FROM secops_grants WHERE id=?', (slot['grant_id'],)).fetchone()
                from .agent_spend import identity, price
                import time
                if not g or g['state'] != 'issued' or g['identity'] != identity(row) or g['expires'] <= time.time():
                    raise Rejected('grant changed or expired')
                price()
                if any(db.execute(q, (row['id'],)).fetchone() for q in ('SELECT 1 FROM invocations WHERE run_id=?', 'SELECT 1 FROM secops_agent_sessions WHERE run_id=?')):
                    raise Rejected('run has prior execution evidence')
                db.execute("UPDATE campaign_slots SET state='dispatching' WHERE campaign_id=? AND slot_id=?", (campaign, slot_id))
                self._event(db, campaign, slot_id, 'dispatch_intent')
                db.commit()  # before key access and process creation
            try:
                key = load_key(key_file)
                run_agent(self.store, slot['run_id'], run_token, grant_id=slot['grant_id'], api_key=key)
            except Exception:
                pass  # keep only safe durable diagnostics
            finally:
                key = None
            return self._reconcile(campaign, token, slot_id)

    def recover(self, campaign, token, slot_id):
        """After host loss, fence worker startup and consume slot permanently."""
        with self._lifecycle():
            return self._reconcile(campaign, token, slot_id)

    def _reconcile(self, campaign, token, slot_id):
        # The store lock waits for an active worker. A not-yet-started worker is
        # fenced by the terminal slot state before it can consume the grant.
        with self.store._locked() as db:
            authority, plan = self._campaign(db, campaign, token)
            slot = self._bound(db, campaign, slot_id)
            if slot['result_hash']:
                return self.store._get(slot['run_id'], slot['result_hash'])
            run = slot['run_id']
            row = db.execute('SELECT * FROM runs WHERE id=?', (run,)).fetchone()
            db.execute("UPDATE secops_requests SET state='unknown' WHERE state='pending' AND grant_id IN (SELECT id FROM secops_grants WHERE run_id=?)", (run,))
            db.execute("UPDATE secops_grants SET state='closed' WHERE run_id=?", (run,))
            db.execute("UPDATE secops_agent_sessions SET state='interrupted' WHERE run_id=? AND state='running'", (run,))
            db.execute("UPDATE invocations SET state='interrupted' WHERE run_id=? AND state='running'", (run,))
            if row['state'] == 'collecting':
                self.store._transition(db, run, 'needs_review', 'campaign recovery; no retry')
            packet = None
            # Verification of historical content avoids loading under a new engine.
            if row['packet_hash']:
                packet = self.store._get(run, row['packet_hash'])
            sessions = [dict(r) for r in db.execute('SELECT * FROM secops_agent_sessions WHERE run_id=? ORDER BY rowid', (run,))]
            grants = [dict(r) for r in db.execute('SELECT id,state,identity FROM secops_grants WHERE run_id=? ORDER BY rowid', (run,))]
            requests = [dict(r) for r in db.execute('SELECT r.* FROM secops_requests r JOIN secops_grants g ON g.id=r.grant_id WHERE g.run_id=? ORDER BY r.rowid', (run,))]
            from .agent import LIVE
            completed = (packet is not None and packet.get('run_id') == run and packet.get('snapshot_hash') == row['snapshot']
                         and packet.get('engine_hash') == row['engine'] and packet.get('execution') == LIVE
                         and slot['session_id'] is not None and len(sessions) == 1
                         and sessions[0]['id'] == slot['session_id'] and sessions[0]['state'] == 'assessed'
                         and packet.get('agent_assessment', {}).get('session_id') == slot['session_id']
                         and sessions[0]['mode'] == LIVE
                         and sessions[0]['result_hash'] == sha(canonical(packet.get('agent_assessment')))
                         and slot['grant_id'] is not None and len(grants) == 1 and grants[0]['id'] == slot['grant_id']
                         and bool(requests) and all(r['state'] == 'settled' for r in requests))
            outcome = ('completed' if packet['investigation_status'] == 'complete' else 'incomplete') if completed else 'stopped'
            result = {'campaign_id': campaign, 'plan_hash': plan['plan_hash'], 'slot_id': slot_id,
                      'case_id': self._slot(plan, slot_id)['case_id'], 'run_id': run, 'grant_id': slot['grant_id'],
                      'fixture_sha256': row['snapshot'], 'engine_hash': row['engine'],
                      'rubric_sha256': plan['cases'][self._slot(plan, slot_id)['case_id']]['rubric_sha256'],
                      'source_commit': plan['source_commit'], 'authority_sha256': sha((authority['authority'] or '').encode()),
                      'outcome': outcome, 'previous_state': slot['state'], 'packet_hash': row['packet_hash'],
                      'sessions': sessions, 'grants': grants, 'requests': requests,
                      'events': [dict(r) for r in db.execute('SELECT e.stage,e.label FROM secops_agent_events e JOIN secops_agent_sessions s ON s.id=e.session_id WHERE s.run_id=? ORDER BY e.id', (run,))],
                      'tools': [dict(r) for r in db.execute('SELECT id,tool,request,state FROM invocations WHERE run_id=? ORDER BY rowid', (run,))],
                      'evidence': [dict(r) for r in db.execute('SELECT id,hash FROM evidence WHERE run_id=? ORDER BY rowid', (run,))],
                      'reserved_microusd': sum(r['reserved'] for r in requests),
                      'estimated_microusd': sum(r['estimated'] or 0 for r in requests),
                      'usage_complete': all(r['state'] == 'settled' for r in requests),
                      'semantic_review': 'pending', 'campaign_acceptance': False, 'at': now()}
            digest = self.store._put(run, result)
            db.execute('UPDATE campaign_slots SET state=?,result_hash=? WHERE campaign_id=? AND slot_id=?', (outcome, digest, campaign, slot_id))
            self._event(db, campaign, slot_id, 'reconciled_' + outcome)
            db.commit()
            return result

    def record_evaluation(self, campaign, token, slot_id, run_token, review):
        """Preserve a reviewer-mediated score bound to the immutable attempt result."""
        from .evaluation import snapshot, score
        with self.store._locked() as db:
            _, plan = self._campaign(db, campaign, token)
            slot = dict(self._bound(db, campaign, slot_id))
            if not slot['result_hash'] or slot['state'] not in ('completed', 'incomplete'):
                raise Rejected('no completed model packet to review')
            result = self.store._get(slot['run_id'], slot['result_hash'])
        source = snapshot(self.store, slot['run_id'], run_token, result['case_id'])
        if (source['packet']['packet_hash'] != result['packet_hash']
                or sha(canonical(source['rubric'])) != result['rubric_sha256']):
            raise Rejected('review targets different packet or rubric')
        scored = score(source, review)
        value = {'result_hash': slot['result_hash'], 'source': source, 'review': review, 'score': scored}
        with self.store._locked() as db:
            self._campaign(db, campaign, token)
            digest = self.store._put(slot['run_id'], value)
            db.execute('INSERT INTO campaign_evaluations VALUES(?,?,?,?,?,?)',
                       (secrets.token_hex(16), campaign, slot_id, slot['result_hash'], digest, scored['outcome']))
            self._event(db, campaign, slot_id, 'evaluation_' + scored['outcome'])
            db.commit()
        return scored

    def status(self, campaign, token):
        with self.store._locked() as db:
            row, plan = self._campaign(db, campaign, token)
            return {'campaign_id': campaign, 'plan_hash': plan['plan_hash'], 'authority_recorded': row['authority'] is not None,
                    'evaluations': [dict(r) for r in db.execute('SELECT slot_id,result_hash,content_hash,outcome FROM campaign_evaluations WHERE campaign_id=? ORDER BY rowid', (campaign,))],
                    'slots': [dict(r) for r in db.execute('SELECT * FROM campaign_slots WHERE campaign_id=? ORDER BY rowid', (campaign,))],
                    'events': [dict(r) for r in db.execute('SELECT slot_id,stage,at FROM campaign_events WHERE campaign_id=? ORDER BY id', (campaign,))]}
