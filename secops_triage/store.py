"""Private single-host replay storage. Agent reads and analyst authority are separate."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile

from .contracts import (IncidentBundle, Rejected, REQUEST_TYPES, InspectIncident, LookupEntity,
                        QueryActivity, FindRelatedCases, REQUIRED, canonical, sha, bounded, ident)
from . import replay, investigation

SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, tenant TEXT NOT NULL, source TEXT NOT NULL,
 incident TEXT NOT NULL, snapshot TEXT NOT NULL, engine TEXT NOT NULL, owner_hash TEXT NOT NULL,
 state TEXT NOT NULL, packet_hash TEXT, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS heads(
 tenant TEXT, source TEXT, incident TEXT, run_id TEXT NOT NULL REFERENCES runs(id),
 PRIMARY KEY(tenant,source,incident));
CREATE TABLE IF NOT EXISTS transitions(
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), previous TEXT, next TEXT,
 reason TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS invocations(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), tool TEXT NOT NULL,
 request TEXT NOT NULL, state TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), invocation TEXT UNIQUE NOT NULL REFERENCES invocations(id),
 hash TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(
 id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, run_id TEXT NOT NULL REFERENCES runs(id),
 packet_hash TEXT NOT NULL, actor TEXT NOT NULL, disposition TEXT NOT NULL, reason TEXT NOT NULL,
 current INTEGER NOT NULL, at TEXT NOT NULL);
'''
LEGAL = {'created': {'collecting'}, 'collecting': {'packet_ready', 'needs_review', 'failed'},
         'needs_review': {'collecting', 'reviewed'}, 'packet_ready': {'reviewed'},
         'failed': {'collecting'}, 'reviewed': set()}


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def engine_digest():
    root = Path(__file__).parent
    local = {name: sha((root / name).read_bytes()) for name in
             ('contracts.py', 'replay.py', 'investigation.py', 'store.py', 'agent.py', 'agent_spend.py', 'agent_runner.py')}
    for name in ('migration_proof/agent/openai_model.py', 'migration_proof/agent/openai_preflight.py', 'uv.lock'):
        local[name] = sha((root.parent / name).read_bytes())
    return sha(canonical(local))



class Store:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self._safe(self.root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._safe(self.root / 'triage.sqlite3')
        with self._locked() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise Rejected('unsupported SecOps database version')
            db.executescript(SCHEMA)
            db.execute('PRAGMA user_version=1')
            db.commit()
            for row in db.execute("SELECT * FROM runs WHERE state='collecting'").fetchall():
                db.execute("UPDATE invocations SET state='interrupted' WHERE run_id=? AND state='running'", (row['id'],))
                self._transition(db, row['id'], 'needs_review', 'recovered interrupted collection; rerun required')
            db.commit()

    @staticmethod
    def _safe(path):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise Rejected('symlinks are not permitted in replay storage')

    @contextmanager
    def _locked(self):
        path = self.root / '.lock'
        self._safe(path)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        db = None
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._safe(self.root / 'triage.sqlite3')
            db = sqlite3.connect(self.root / 'triage.sqlite3')
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            yield db
        finally:
            if db is not None:
                db.close()  # rolls back unfinished transaction
            os.close(fd)

    def blob_path(self, run_id, digest):
        if not isinstance(run_id, str) or len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
            raise Rejected('invalid run ID')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise Rejected('invalid content hash')
        path = self.root / 'blobs' / run_id / digest
        self._safe(path)
        return path

    def _put(self, run_id, value):
        body = canonical(value)
        digest = sha(body)
        path = self.blob_path(run_id, digest)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(body)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temporary, 0o400)
            try:
                os.link(temporary, path)
            except FileExistsError:
                self._get(run_id, digest)
            # Persist the publication and newly-created directories.
            for directory in (path.parent, path.parent.parent, self.root):
                handle = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(handle)
                finally:
                    os.close(handle)
        finally:
            os.unlink(temporary)
        return digest

    def _get(self, run_id, digest):
        path = self.blob_path(run_id, digest)
        try:
            if path.stat().st_size > 8_000_000:
                raise Rejected('oversized artifact')
            body = path.read_bytes()
            if sha(body) != digest:
                raise Rejected('evidence hash mismatch')
            return json.loads(body)
        except (OSError, ValueError) as e:
            raise Rejected('missing or invalid immutable artifact') from e

    @staticmethod
    def _owner(db, run_id, token):
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise Rejected('owner authorization required')
        row = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None or not hmac.compare_digest(row['owner_hash'], sha(token.encode())):
            raise Rejected('owner authorization required')
        return row

    @staticmethod
    def _current(db, row):
        head = db.execute('SELECT run_id FROM heads WHERE tenant=? AND source=? AND incident=?',
                          (row['tenant'], row['source'], row['incident'])).fetchone()
        if not head or head[0] != row['id']:
            raise Rejected('superseded incident snapshot; investigate latest revision')

    @staticmethod
    def _transition(db, run_id, target, reason):
        row = db.execute('SELECT state FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None or target not in LEGAL[row[0]]:
            raise Rejected('illegal investigation transition')
        db.execute('INSERT INTO transitions(run_id,previous,next,reason,at) VALUES(?,?,?,?,?)',
                   (run_id, row[0], target, reason, now()))
        db.execute('UPDATE runs SET state=? WHERE id=?', (target, run_id))

    def ingest(self, value, token, request_id):
        """Trusted host imports an EXISTING source incident; never an agent tool."""
        ident(request_id)
        if not isinstance(token, str) or not 32 <= len(token) <= 256:
            raise Rejected('host must supply an owner capability')
        bundle = IncidentBundle.from_dict(value)
        snapshot = sha(canonical(bundle.to_dict()))
        engine = engine_digest()
        with self._locked() as db:
            old = db.execute('SELECT * FROM runs WHERE request_id=?', (request_id,)).fetchone()
            if old:
                self._owner(db, old['id'], token)
                if old['snapshot'] != snapshot or old['engine'] != engine:
                    raise Rejected('idempotency key reused with different input')
                return old['id']
            run_id = secrets.token_hex(16)
            self._put(run_id, bundle.to_dict())
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (run_id, request_id, bundle.tenant_id, bundle.source, bundle.incident_id,
                        snapshot, engine, sha(token.encode()), 'created', None, now()))
            db.execute('INSERT INTO heads VALUES(?,?,?,?) ON CONFLICT(tenant,source,incident) DO UPDATE SET run_id=excluded.run_id',
                       (bundle.tenant_id, bundle.source, bundle.incident_id, run_id))
            db.execute('UPDATE reviews SET current=0 WHERE run_id IN (SELECT id FROM runs WHERE tenant=? AND source=? AND incident=?)',
                       (bundle.tenant_id, bundle.source, bundle.incident_id))
            db.commit()
            return run_id

    def _load(self, row):
        if row['engine'] != engine_digest():
            raise Rejected('investigation implementation changed; import a new revision')
        return IncidentBundle.from_dict(self._get(row['id'], row['snapshot']))

    def _call(self, db, row, bundle, tool, request):
        if tool not in REQUEST_TYPES or type(request) is not REQUEST_TYPES[tool]:
            raise Rejected('unregistered tool or wrong typed contract')
        if db.execute('SELECT COUNT(*) FROM invocations WHERE run_id=?', (row['id'],)).fetchone()[0] >= 256:
            raise Rejected('investigation tool budget exhausted')
        invocation = secrets.token_hex(16)
        db.execute('INSERT INTO invocations VALUES(?,?,?,?,?,?)',
                   (invocation, row['id'], tool, canonical(asdict(request)).decode(), 'running', now()))
        db.commit()  # durable intent before any adapter work
        try:
            result = replay.execute(bundle, request)
            if len(canonical(result)) > 65536:
                raise Rejected('tool result exceeds output budget')
            record = {'id': secrets.token_hex(16), 'run_id': row['id'], 'tenant_id': row['tenant'],
                      'snapshot_hash': row['snapshot'], 'tool': tool, 'request': asdict(request),
                      'adapter': 'local-replay-v1', 'collected_at': now(), 'result': result}
            digest = self._put(row['id'], record)
            db.execute('INSERT INTO evidence VALUES(?,?,?,?,?)', (record['id'], row['id'], invocation, digest, now()))
            db.execute("UPDATE invocations SET state='completed' WHERE id=?", (invocation,))
            db.commit()
            return dict(record, hash=digest)
        except Exception:
            db.rollback()
            db.execute("UPDATE invocations SET state='failed' WHERE id=?", (invocation,))
            db.commit()
            raise

    def agent_tools(self, run_id, token):
        """Only four run-bound operations. Host capability is closed over, not an argument."""
        with self._locked() as db:
            self._owner(db, run_id, token)
        def bind(name):
            def call(request):
                with self._locked() as db:
                    row = self._owner(db, run_id, token)
                    self._current(db, row)
                    if row['packet_hash'] or row['state'] not in ('created', 'collecting', 'needs_review', 'failed'):
                        raise Rejected('collection is closed')
                    bundle = self._load(row)
                    if row['state'] != 'collecting':
                        self._transition(db, run_id, 'collecting', 'bounded tool collection')
                        db.commit()
                    return self._call(db, row, bundle, name, request)
            return call
        return {name: bind(name) for name in REQUEST_TYPES}

    def investigate(self, run_id, token):
        return self._investigate(run_id, token)

    def _investigate(self, run_id, token, collector=None):
        """Runs real replay queries under a fixed, explicitly deterministic plan."""
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._current(db, row)
            if row['packet_hash']:
                return self._packet(db, row)
            bundle = self._load(row)
            if row['state'] != 'collecting':
                self._transition(db, run_id, 'collecting', 'deterministic replay started')
                db.commit()
            evidence = []
            def call(name, request):
                result = self._call(db, row, bundle, name, request)
                evidence.append(result)
                return result
            try:
                agent_assessment = None
                if collector is not None:
                    agent_assessment = collector(db, row, bundle, call)
                else:
                    call('inspect_incident', InspectIncident())
                    for entity in bundle.entities:
                        call('lookup_entity', LookupEntity(entity.id))
                    for alert in bundle.alerts:
                        for template in REQUIRED[alert.family]:
                            call('query_activity', QueryActivity(alert.id, template, bundle.start, bundle.end))
                        call('find_related_cases', FindRelatedCases(alert.id))
                assessment = investigation.assess(bundle, evidence)
                if agent_assessment is not None:
                    from .agent import reconcile
                    assessment = reconcile(assessment, agent_assessment)
                packet = dict(assessment, run_id=run_id, tenant_id=row['tenant'], source=row['source'],
                              incident_id=row['incident'], title=bundle.title, snapshot_hash=row['snapshot'],
                              engine_hash=row['engine'], execution=investigation.ENGINE_LABEL,
                              synthetic=bundle.synthetic, start=bundle.start, end=bundle.end,
                              observed_at=bundle.observed_at, created_at=now(),
                              evidence=[{'id': e['id'], 'hash': e['hash'], 'tool': e['tool'],
                                         'request': e['request'], 'outcome': e['result']['outcome'],
                                         'complete': e['result']['complete']} for e in evidence],
                              upstream_status='unchanged; local investigation only')
                if agent_assessment is not None:
                    packet["agent_assessment"] = agent_assessment
                    packet["execution"] = agent_assessment["execution"]
                self._validate_packet(db, row, packet)
                packet_hash = self._put(run_id, packet)
                self._transition(db, run_id, 'packet_ready' if packet['investigation_status'] == 'complete' else 'needs_review',
                                 'evidence packet assembled')
                db.execute('UPDATE runs SET packet_hash=? WHERE id=?', (packet_hash, run_id))
                db.commit()
                return dict(packet, packet_hash=packet_hash)
            except Exception:
                db.rollback()
                self._transition(db, run_id, 'failed', 'investigation failed; no decision published')
                db.commit()
                raise

    def _validate_packet(self, db, row, packet):
        for field, column in (('run_id', 'id'), ('tenant_id', 'tenant'), ('source', 'source'),
                              ('incident_id', 'incident'), ('snapshot_hash', 'snapshot'), ('engine_hash', 'engine')):
            if packet.get(field) != row[column]:
                raise Rejected('packet identity mismatch')
        self._get(row['id'], row['snapshot'])
        evidence = {}
        for item in packet['evidence']:
            stored = db.execute('SELECT * FROM evidence WHERE id=? AND run_id=?', (item['id'], row['id'])).fetchone()
            if not stored or stored['hash'] != item['hash']:
                raise Rejected('packet cites foreign or changed evidence')
            e = self._get(row['id'], item['hash'])
            if e['run_id'] != row['id'] or e['tenant_id'] != row['tenant'] or e['snapshot_hash'] != row['snapshot']:
                raise Rejected('evidence scope mismatch')
            evidence[item['id']] = e
        if "agent_assessment" in packet:
            from .agent import validate_assessment
            value = packet["agent_assessment"]
            validate_assessment(value, list(evidence.values()))
            session = db.execute('SELECT * FROM secops_agent_sessions WHERE id=? AND run_id=?',
                                 (value['session_id'], row['id'])).fetchone()
            if (not session or session['state'] != 'assessed' or session['result_hash'] != sha(canonical(value))
                    or session['mode'] != value['execution'] or packet['execution'] != value['execution']):
                raise Rejected('agent assessment session mismatch')
            self._get(row['id'], session['result_hash'])
        for alert in packet['alerts']:
            for observation in alert['observations']:
                e = evidence.get(observation['evidence_id'])
                if not e or observation['event_id'] not in {r['id'] for r in e['result']['records']}:
                    raise Rejected('unsupported observation citation')
            for gap in alert['gaps']:
                if gap['evidence_id'] is not None and gap['evidence_id'] not in evidence:
                    raise Rejected('unsupported gap citation')
        # Recompute demo decisions from stored evidence; no caller can forge close.
        expected = investigation.assess(IncidentBundle.from_dict(self._get(row['id'], row['snapshot'])), list(evidence.values()))
        if 'agent_assessment' in packet:
            from .agent import reconcile
            expected = reconcile(expected, packet['agent_assessment'])
        if any(packet[k] != expected[k] for k in ('recommendation', 'investigation_status', 'alerts')):
            raise Rejected('packet assessment is inconsistent with evidence')

    def _packet(self, db, row):
        if not row['packet_hash']:
            raise Rejected('investigation has no packet')
        packet = self._get(row['id'], row['packet_hash'])
        self._validate_packet(db, row, packet)
        return dict(packet, packet_hash=row['packet_hash'])

    def packet(self, run_id, token):
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            return self._packet(db, row)

    def status(self, run_id, token):
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            reviews = [dict(r) for r in db.execute('SELECT id,packet_hash,actor,disposition,reason,current,at FROM reviews WHERE run_id=?', (run_id,))]
            head = db.execute('SELECT run_id FROM heads WHERE tenant=? AND source=? AND incident=?',
                              (row['tenant'], row['source'], row['incident'])).fetchone()[0]
            return {'run_id': run_id, 'state': row['state'], 'is_latest': head == run_id,
                    'reviews': reviews, 'upstream_status': 'unchanged'}

    def review(self, run_id, token, packet_hash, actor, disposition, reason, request_id):
        """Host-only analyst decision record; never writes to the upstream SIEM."""
        bounded(actor, 200)
        bounded(reason)
        ident(request_id)
        if disposition not in ('close', 'escalate'):
            raise Rejected('unsupported analyst disposition')
        with self._locked() as db:
            row = self._owner(db, run_id, token)
            self._current(db, row)
            self._load(row)
            packet = self._packet(db, row)
            if packet_hash != packet['packet_hash']:
                raise Rejected('review targets a stale packet')
            old = db.execute('SELECT * FROM reviews WHERE request_id=?', (request_id,)).fetchone()
            if old:
                if tuple(old[k] for k in ('run_id', 'packet_hash', 'actor', 'disposition', 'reason')) != (run_id, packet_hash, actor, disposition, reason):
                    raise Rejected('review idempotency conflict')
                return old['id']
            if row['state'] not in ('packet_ready', 'needs_review'):
                raise Rejected('packet already reviewed')
            review_id = secrets.token_hex(16)
            db.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)',
                       (review_id, request_id, run_id, packet_hash, actor, disposition, reason, 1, now()))
            self._transition(db, run_id, 'reviewed', 'analyst decision recorded locally')
            db.commit()
            return review_id
