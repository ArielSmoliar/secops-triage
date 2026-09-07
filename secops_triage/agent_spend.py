"""Host-only, single-use SecOps grants. Never reuses migration grant authority."""
from datetime import datetime, timezone, date
from types import SimpleNamespace
import json
import secrets
from .contracts import Rejected, canonical, sha
from .store import now

CALLS = 10
OUTPUT_TOKENS = 2048
BUDGET_MICROUSD = 4_250_000
SCHEMA = '''
CREATE TABLE IF NOT EXISTS secops_grants(id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
 identity TEXT NOT NULL, actor TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS secops_requests(id TEXT PRIMARY KEY, grant_id TEXT NOT NULL,
 state TEXT NOT NULL, reserved INTEGER NOT NULL, estimated INTEGER, usage TEXT);
'''


def identity(row):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    paths = ['migration_proof/agent/openai_model.py', 'migration_proof/agent/openai_preflight.py', 'uv.lock']
    return sha(canonical({'snapshot': row['snapshot'], 'engine': row['engine'],
                          'provider': {p: sha((root / p).read_bytes()) for p in paths}}))


def price():
    from migration_proof.agent.openai_preflight import (PRICE_CHECKED_ON, MODEL_CONTEXT_TOKENS,
        INPUT_NANODOLLARS_PER_TOKEN, OUTPUT_NANODOLLARS_PER_TOKEN)
    if not 0 <= (datetime.now(timezone.utc).date() - PRICE_CHECKED_ON).days <= 7:
        raise Rejected('pricing requires revalidation')
    return (MODEL_CONTEXT_TOKENS * INPUT_NANODOLLARS_PER_TOKEN + OUTPUT_TOKENS * OUTPUT_NANODOLLARS_PER_TOKEN + 999) // 1000


def authorize(store, run_id, token, actor):
    """Explicit host authorization for ONE synthetic incident, ten calls/$4.25 maximum."""
    if type(actor) is not str or not 1 <= len(actor) <= 200:
        raise Rejected('authorization actor required')
    if price() * CALLS > BUDGET_MICROUSD:
        raise Rejected('insufficient reservation budget')
    with store._locked() as db:
        row = store._owner(db, run_id, token)
        store._current(db, row)
        bundle = store._load(row)
        if not bundle.synthetic or len(bundle.alerts) != 1 or row['state'] != 'created':
            raise Rejected('paid scope requires one fresh synthetic alert')
        db.executescript(SCHEMA)
        from .campaign_store import binding
        slot = binding(db, run_id)
        if slot:
            campaign = db.execute('SELECT authority FROM campaigns WHERE id=?', (slot['campaign_id'],)).fetchone()
            if slot['state'] != 'reserved' or not campaign['authority']:
                raise Rejected('campaign authority missing or slot consumed')
        if db.execute('SELECT 1 FROM secops_grants WHERE run_id=?', (run_id,)).fetchone():
            raise Rejected('run already received a grant')
        grant = secrets.token_hex(16)
        db.execute('INSERT INTO secops_grants VALUES(?,?,?,?,?,?)',
                   (grant, run_id, identity(row), actor, datetime.now(timezone.utc).timestamp()+600, 'issued'))
        db.commit()
        return grant


class Ledger:
    """Used only while the investigation owns the exclusive store lock."""
    def __init__(self, db, row, grant, session_id=None):
        self.db, self.grant = db, grant
        db.executescript(SCHEMA)
        g = db.execute('SELECT * FROM secops_grants WHERE id=?', (grant,)).fetchone()
        if (not g or g['state'] != 'issued' or g['run_id'] != row['id']
                or g['identity'] != identity(row) or g['expires'] <= datetime.now(timezone.utc).timestamp()):
            raise Rejected('missing, expired, changed or consumed SecOps grant')
        price()
        from .campaign_store import claim
        claim(db, row['id'], grant, session_id)
        db.execute("UPDATE secops_grants SET state='running' WHERE id=?", (grant,))
        db.commit()

    def reserve(self, session_id):
        if session_id != self.grant:
            raise Rejected('grant/session mismatch')
        g = self.db.execute('SELECT * FROM secops_grants WHERE id=?', (self.grant,)).fetchone()
        rows = self.db.execute('SELECT * FROM secops_requests WHERE grant_id=?', (self.grant,)).fetchall()
        amount = price()
        if (g['state'] != 'running' or g['expires'] <= datetime.now(timezone.utc).timestamp()
                or len(rows) >= CALLS or any(r['state'] != 'settled' for r in rows)
                or sum(r['reserved'] for r in rows)+amount > BUDGET_MICROUSD):
            raise Rejected('spending stopped')
        request = secrets.token_hex(16)
        self.db.execute('INSERT INTO secops_requests VALUES(?,?,?,?,?,?)',
                        (request, self.grant, 'pending', amount, None, None))
        self.db.commit()
        return request, SimpleNamespace(max_output_tokens=OUTPUT_TOKENS)

    def settle(self, session_id, request_id, usage):
        from migration_proof.agent.openai_preflight import MODEL_CONTEXT_TOKENS
        if (type(usage) is not dict or any(type(usage.get(k)) is not int or usage[k] < 0
            for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
            or usage['prompt_tokens'] > MODEL_CONTEXT_TOKENS or usage['completion_tokens'] > OUTPUT_TOKENS
            or usage['total_tokens'] != usage['prompt_tokens']+usage['completion_tokens']):
            raise Rejected('invalid usage; retain reservation')
        if session_id != self.grant:
            raise Rejected('grant/session mismatch')
        cost = (usage['prompt_tokens']*400 + usage['completion_tokens']*1600+999)//1000
        changed = self.db.execute("UPDATE secops_requests SET state='settled',estimated=?,usage=? WHERE id=? AND grant_id=? AND state='pending'",
                                  (cost, canonical(usage).decode(), request_id, self.grant)).rowcount
        if changed != 1:
            raise Rejected('request is not pending')
        self.db.commit()

    def uncertain(self, session_id, request_id):
        if session_id != self.grant:
            raise Rejected('grant/session mismatch')
        self.db.execute("UPDATE secops_requests SET state='unknown' WHERE id=? AND grant_id=? AND state='pending'", (request_id, self.grant))
        self.db.commit()

    def close(self):
        self.db.execute("UPDATE secops_requests SET state='unknown' WHERE grant_id=? AND state='pending'", (self.grant,))
        self.db.execute("UPDATE secops_grants SET state='closed' WHERE id=?", (self.grant,))
        self.db.commit()


def recover(store):
    with store._locked() as db:
        db.executescript(SCHEMA)
        db.execute("UPDATE secops_requests SET state='unknown' WHERE state='pending'")
        db.execute("UPDATE secops_grants SET state='closed' WHERE state='running'")
        db.commit()


def spending(store, run_id, token):
    with store._locked() as db:
        store._owner(db, run_id, token)
        db.executescript(SCHEMA)
        rows = db.execute('SELECT r.* FROM secops_requests r JOIN secops_grants g ON g.id=r.grant_id WHERE g.run_id=?', (run_id,)).fetchall()
        return {'requests': len(rows), 'reserved_microusd': sum(r['reserved'] for r in rows),
                'estimated_microusd': sum(r['estimated'] or 0 for r in rows),
                'usage_complete': all(r['state']=='settled' for r in rows)}
