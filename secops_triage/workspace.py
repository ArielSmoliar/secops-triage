"""Single-operator loopback workspace. Scripted dispatch only; no paid authority API."""
import argparse
from contextlib import closing
import fcntl
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile
import threading
from urllib.parse import urlsplit

from .agent_runner import run_agent
from .contracts import IncidentBundle, Rejected, canonical, exact, ident
from .evaluation_cases import CASE_IDS, get_case
from .investigation import assess
from .store import Store, now, engine_digest

WEB = Path(__file__).with_name('web')
ID = re.compile(r'[a-f0-9]{32}')


def private_write(path, value):
    Store._safe(path)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(canonical(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Workspace:
    """Owns only its new designated store. Capabilities never cross the HTTP boundary."""
    def __init__(self, root, *, worker=run_agent):
        self.root = Path(root).absolute()
        Store._safe(self.root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_mode & 0o077:
            raise Rejected('workspace directory must be private (0700)')
        self.lock_fd = os.open(self.root / '.workspace-lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock_fd)
            raise Rejected('workspace already open') from None
        self.guard = threading.RLock()
        self.worker = worker
        self.thread = None
        self.path = self.root / 'workspace.json'
        Store._safe(self.path)
        if self.path.exists():
            if self.path.stat().st_mode & 0o077:
                self.close()
                raise Rejected('workspace ownership file must be private')
            self.data = json.loads(self.path.read_text())
            if self.data.get('schema') != 1:
                self.close()
                raise Rejected('unsupported workspace version')
        else:
            if (self.root / 'store').exists():
                self.close()
                raise Rejected('use a new workspace; historical stores are not imported')
            self.data = {'schema': 1, 'runs': [], 'intents': []}
            private_write(self.path, self.data)
        # Store recovery waits for any previous worker lock. It never dispatches.
        self.store = Store(self.root / 'store')
        self.data.setdefault('intents', [])
        self._reconcile_intents()
        for entry in self.data['runs']:
            if entry['dispatch'] in ('reserved', 'running'):
                entry['dispatch'] = 'interrupted'
        private_write(self.path, self.data)

    def _reconcile_intents(self):
        """Recover ownership only; an interrupted start is never dispatched here."""
        known = {e['request_id'] for e in self.data['runs']}
        with self.store._locked() as db:
            for intent in self.data['intents']:
                if intent['request_id'] in known:
                    continue
                row = db.execute('SELECT * FROM runs WHERE request_id=?',
                                 (intent['request_id'],)).fetchone()
                if row:
                    self.store._owner(db, row['id'], intent['token'])
                    if row['snapshot'] != intent['snapshot_hash']:
                        raise Rejected('interrupted start snapshot mismatch')
                    self.data['runs'].append({k: intent[k] for k in
                        ('case', 'token', 'request_id', 'previous', 'created')} |
                        {'run_id': row['id'], 'dispatch': 'interrupted'})
                intent['state'] = 'interrupted'

    def close(self):
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=125)
        if getattr(self, 'lock_fd', None) is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    def entry(self, run_id):
        if not isinstance(run_id, str) or not ID.fullmatch(run_id):
            raise Rejected('unknown workspace run')
        for entry in self.data['runs']:
            if entry['run_id'] == run_id:
                return dict(entry)
        raise Rejected('unknown workspace run')

    def catalog(self):
        with self.guard:
            cases = []
            for case in CASE_IDS:
                b = get_case(case)
                runs = [e['run_id'] for e in self.data['runs'] if e['case'] == case]
                cases.append({'id': case, 'title': b['title'], 'family': b['alerts'][0]['family'],
                              'incident_id': b['incident_id'], 'source': b['source'],
                              'runs': runs, 'latest_run': runs[-1] if runs else None,
                              'interrupted_starts': sum(1 for i in self.data['intents']
                                  if i['case'] == case and i['state'] == 'interrupted')})
            return {'cases': cases, 'active': bool(self.thread and self.thread.is_alive()),
                    'execution': 'scripted', 'paid_calls_enabled': False}

    def start(self, case, request_id, previous=None):
        ident(request_id)
        if case not in CASE_IDS:
            raise Rejected('unknown synthetic incident')
        with self.guard:
            for entry in self.data['runs']:
                if entry['request_id'] == request_id:
                    if entry['case'] != case or entry.get('previous') != previous:
                        raise Rejected('start idempotency conflict')
                    return entry['run_id']
            if any(i['request_id'] == request_id for i in self.data['intents']):
                raise Rejected('interrupted start retained; use a new explicit start request')
            entries = [e for e in self.data['runs'] if e['case'] == case]
            if entries and previous is None:
                return entries[-1]['run_id']  # Duplicate clicks never reserve another run.
            if previous is not None and (not entries or previous != entries[-1]['run_id']):
                raise Rejected('new revision must target the latest run')
            if self.thread and self.thread.is_alive():
                raise Rejected('another investigation is in progress')
            token = secrets.token_urlsafe(32)
            bundle = IncidentBundle.from_dict(get_case(case)).to_dict()
            intent = {'case': case, 'token': token, 'request_id': request_id,
                      'previous': previous, 'created': now(), 'state': 'reserved',
                      'snapshot_hash': hashlib.sha256(canonical(bundle)).hexdigest()}
            self.data['intents'].append(intent)
            try:
                private_write(self.path, self.data)  # Capability durable BEFORE ingest changes head.
            except BaseException:
                self.data['intents'].remove(intent)
                raise
            try:
                run_id = self.store.ingest(bundle, token, request_id)
                entry = {k: intent[k] for k in ('case', 'token', 'request_id', 'previous', 'created')}
                entry.update(run_id=run_id, dispatch='reserved')
                self.data['runs'].append(entry)
                intent['state'] = 'mapped'
                private_write(self.path, self.data)
            except BaseException:
                self._reconcile_intents()
                for item in self.data['runs']:
                    if item['request_id'] == request_id:
                        item['dispatch'] = 'interrupted'
                intent['state'] = 'interrupted'
                # Disk retains the pre-ingest intent even if persistence is unavailable.
                raise
            self.thread = threading.Thread(target=self._execute, args=(run_id,), daemon=True)
            self.thread.start()
            return run_id

    def _execute(self, run_id):
        with self.guard:
            entry = next(e for e in self.data['runs'] if e['run_id'] == run_id)
            entry['dispatch'] = 'running'
            private_write(self.path, self.data)
            token = entry['token']
        try:
            self.worker(self.store, run_id, token)  # No grant, key, provider override or user prompt.
            outcome = 'completed'
        except BaseException:
            outcome = 'stopped'  # Raw exceptions and subprocess output never enter the browser.
        with self.guard:
            entry['dispatch'] = outcome
            private_write(self.path, self.data)

    def view(self, run_id):
        with self.guard:
            entry = self.entry(run_id)
        # A read-only SQLite snapshot sees committed tool progress without acquiring
        # the worker's long-lived flock. Never construct another Store while polling.
        dbpath = self.store.root / 'triage.sqlite3'
        Store._safe(dbpath)
        with closing(sqlite3.connect(f'file:{dbpath}?mode=ro', uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            row = self.store._owner(db, run_id, entry['token'])
            head = db.execute('SELECT run_id FROM heads WHERE tenant=? AND source=? AND incident=?',
                              (row['tenant'], row['source'], row['incident'])).fetchone()[0]
            snapshot = self.store._get(run_id, row['snapshot'])
            records = []
            trace = []
            for item in db.execute('SELECT i.id,i.tool,i.request,i.state,i.at,e.id AS evidence_id,e.hash '
                                   'FROM invocations i LEFT JOIN evidence e ON e.invocation=i.id '
                                   'WHERE i.run_id=? ORDER BY i.rowid', (run_id,)):
                event = {k: item[k] for k in ('id', 'tool', 'state', 'at', 'evidence_id', 'hash')}
                event['request'] = json.loads(item['request'])
                if item['hash']:
                    evidence = self.store._get(run_id, item['hash'])
                    if evidence['run_id'] != run_id or evidence['id'] != item['evidence_id']:
                        raise Rejected('evidence scope mismatch')
                    records.append(dict(evidence, hash=item['hash']))
                    event.update(outcome=evidence['result']['outcome'], complete=evidence['result']['complete'],
                                 record_count=len(evidence['result']['records']))
                trace.append(event)
            stages, sessions = [], []
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='secops_agent_sessions'").fetchone():
                sessions = [dict(x) for x in db.execute('SELECT id,mode,state,model_calls,tool_calls FROM secops_agent_sessions WHERE run_id=?', (run_id,))]
                stages = [dict(x) for x in db.execute('SELECT e.stage,e.label FROM secops_agent_events e JOIN secops_agent_sessions s ON s.id=e.session_id WHERE s.run_id=? ORDER BY e.rowid', (run_id,))]
            engine_current = row['engine'] == engine_digest()
            packet = self.store._packet(db, row) if row['packet_hash'] and engine_current else None
            policy = assess(IncidentBundle.from_dict(snapshot), records) if packet else None
            reviews = [dict(x) for x in db.execute('SELECT id,packet_hash,actor,disposition,reason,current,at FROM reviews WHERE run_id=? ORDER BY rowid', (run_id,))]
            handoffs = self.store._handoffs(db, row)
            return {'run_id': run_id, 'case': entry['case'], 'created': entry['created'],
                    'dispatch': entry['dispatch'], 'state': row['state'], 'is_latest': head == run_id,
                    'latest_run': head, 'engine_current': engine_current,
                    'historical_unverifiable': bool(row['packet_hash'] and not engine_current),
                    'recorded_packet_hash': row['packet_hash'],
                    'source': {k: snapshot[k] for k in ('title', 'incident_id', 'source', 'observed_at', 'start', 'end', 'entities')},
                    'snapshot_hash': row['snapshot'], 'trace': trace, 'stages': stages, 'sessions': sessions,
                    'evidence': records, 'packet': packet, 'policy': policy, 'reviews': reviews, 'handoffs': handoffs,
                    'execution': 'scripted', 'data': 'synthetic local snapshot', 'siem_status': 'unchanged'}

    def decide(self, run_id, body):
        with self.guard:
            entry = self.entry(run_id)
            if self.thread and self.thread.is_alive():
                raise Rejected('wait for collection to finish')
        common = ('packet_hash', 'actor', 'reason', 'request_id', 'action')
        if body.get('action') == 'handoff':
            exact(body, common + ('missing_context', 'next_action'))
            saved = self.store.save_handoff(run_id, entry['token'], body['packet_hash'], body['actor'],
                                           body['reason'], body['missing_context'], body['next_action'], body['request_id'])
        else:
            exact(body, common)
            saved = self.store.review(run_id, entry['token'], body['packet_hash'], body['actor'],
                                      body['action'], body['reason'], body['request_id'])
        return {'id': saved, 'siem_status': 'unchanged'}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, workspace, port=8765):
        self.workspace = workspace
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log request bodies, local notes, capabilities or URLs.

    def reply(self, code, data, content_type='application/json', cookie=False):
        raw = canonical(data) if content_type == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        if cookie:
            self.send_header('Set-Cookie', f'secops_workspace={self.server.session}; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self, session=True, mutation=False):
        if self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            raise Rejected('invalid workspace host')
        origin = self.headers.get('Origin')
        if origin is not None and origin != self.server.origin:
            raise Rejected('cross-origin request refused')
        if self.headers.get('Sec-Fetch-Site') not in (None, 'none', 'same-origin'):
            raise Rejected('cross-site request refused')
        if session:
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
            except Exception:
                raise Rejected('workspace session required') from None
            value = cookie.get('secops_workspace')
            if not value or not hmac.compare_digest(value.value, self.server.session):
                raise Rejected('workspace session required; reload the page')
        if mutation and (origin != self.server.origin or not hmac.compare_digest(self.headers.get('X-Secops-CSRF', ''), self.server.csrf)):
            raise Rejected('same-origin workspace action required')

    def do_GET(self):
        try:
            path = urlsplit(self.path)
            if path.query or path.fragment:
                raise Rejected('unexpected URL parameters')
            static = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            self.authorized(session=path.path not in static)
            if path.path in static:
                name, mime = static[path.path]
                return self.reply(200, (WEB / name).read_bytes(), mime, cookie=path.path == '/')
            if path.path == '/api/session':
                return self.reply(200, {'csrf': self.server.csrf})
            if path.path == '/api/cases':
                return self.reply(200, self.server.workspace.catalog())
            match = re.fullmatch(r'/api/runs/([a-f0-9]{32})', path.path)
            if match:
                return self.reply(200, self.server.workspace.view(match[1]))
            return self.reply(404, {'error': 'Not found'})
        except Rejected as exc:
            self.reply(403, {'error': str(exc)})
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            self.reply(409, {'error': 'Saved evidence is unavailable or inconsistent. Preserve the workspace for inspection.'})

    def do_POST(self):
        try:
            self.authorized(mutation=True)
            if self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                raise Rejected('bounded JSON request required')
            length = int(self.headers.get('Content-Length', '0'))
            if not 1 <= length <= 20000:
                raise Rejected('request size limit')
            from .__main__ import unique_object
            body = json.loads(self.rfile.read(length), object_pairs_hook=unique_object)
            if self.path == '/api/start':
                exact(body, ('case', 'request_id', 'previous'))
                return self.reply(200, {'run_id': self.server.workspace.start(body['case'], body['request_id'], body['previous'])})
            match = re.fullmatch(r'/api/runs/([a-f0-9]{32})/decision', self.path)
            if match:
                return self.reply(200, self.server.workspace.decide(match[1], body))
            self.reply(404, {'error': 'Not found'})
        except Rejected as exc:
            self.reply(409, {'error': str(exc)})
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
            self.reply(409, {'error': 'Action not saved. Check the fields and current revision; your draft is preserved.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='New private workspace, or this workspace on restart')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    workspace = None
    server = None
    try:
        workspace = Workspace(args.root)
        server = Server(workspace, args.port)
        print(f'SecOps Triage: {server.origin} (local scripted workspace; no paid calls)', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (Rejected, OSError, ValueError):
        parser.exit(2, 'Workspace stopped. Verify private directory, port and saved evidence; nothing was retried.\n')
    finally:
        if server:
            server.server_close()
        if workspace:
            workspace.close()


if __name__ == '__main__':
    main()
