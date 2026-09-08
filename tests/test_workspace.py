"""Offline workspace boundaries and persisted analyst workflow; no paid calls."""
import http.client
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from secops_triage.workspace import private_write

from secops_triage.contracts import InspectIncident, Rejected
from secops_triage.workspace import Server, Workspace


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='secops-ui-', dir='/private/tmp')
        self.workspace = Workspace(Path(self.temp.name) / 'workspace')

    def tearDown(self):
        self.workspace.close()
        self.temp.cleanup()

    def start(self, case='case-04'):
        run = self.workspace.start(case, secrets.token_hex(16))
        self.workspace.thread.join(20)
        self.assertFalse(self.workspace.thread.is_alive())
        return run

    def test_real_sdk_trace_scoped_and_no_capability_export(self):
        run = self.start()
        view = self.workspace.view(run)
        self.assertEqual(view['dispatch'], 'completed')
        self.assertEqual(view['packet']['recommendation'], 'escalate')
        self.assertEqual(len(view['evidence']), 9)
        self.assertEqual({x['tool'] for x in view['trace']},
                         {'inspect_incident', 'lookup_entity', 'query_activity', 'find_related_cases'})
        self.assertEqual(view['sessions'][0]['mode'], 'Strands SDK with scripted provider (no live model)')
        raw = json.dumps(view)
        self.assertNotIn(self.workspace.data['runs'][0]['token'], raw)
        self.assertNotIn('owner_hash', raw)
        self.assertNotIn('rubric', raw)
        self.assertEqual(self.workspace.path.stat().st_mode & 0o777, 0o600)

    def test_duplicate_start_and_new_revision_invalidate_old_review(self):
        request = secrets.token_hex(16)
        run = self.workspace.start('case-05', request)
        self.workspace.thread.join(20)
        self.assertEqual(self.workspace.start('case-05', request), run)
        self.assertEqual(self.workspace.start('case-05', secrets.token_hex(16)), run)
        view = self.workspace.view(run)
        body = dict(packet_hash=view['packet']['packet_hash'], actor='Automated test, not human acceptance',
                    reason='Test-only scoped close record.', request_id=secrets.token_hex(16), action='close')
        first = self.workspace.decide(run, body)
        self.assertEqual(self.workspace.decide(run, body), first)
        newer = self.workspace.start('case-05', secrets.token_hex(16), run)
        self.workspace.thread.join(20)
        self.assertNotEqual(newer, run)
        self.assertFalse(self.workspace.view(run)['is_latest'])
        self.assertFalse(self.workspace.view(run)['reviews'][0]['current'])
        with self.assertRaises(Rejected):
            self.workspace.decide(run, dict(body, request_id=secrets.token_hex(16)))

    def test_missing_collection_and_handoff_restart(self):
        run = self.start('case-03')
        view = self.workspace.view(run)
        self.assertIsNone(view['packet']['recommendation'])
        self.assertTrue(any(e['result']['outcome'] == 'unavailable' for e in view['evidence']))
        body = dict(packet_hash=view['packet']['packet_hash'], actor='AI test operator', reason='Missing account audit.',
                    missing_context='Account change export unavailable.', next_action='Retrieve authorized export.',
                    request_id=secrets.token_hex(16), action='handoff')
        first = self.workspace.decide(run, body)
        self.assertEqual(self.workspace.decide(run, body), first)
        self.assertNotEqual(self.workspace.view(run)['state'], 'reviewed')
        root = self.workspace.root
        self.workspace.close()
        self.workspace = Workspace(root)
        restored = self.workspace.view(run)
        self.assertEqual(restored['handoffs'][0]['id'], first['id'])
        self.assertTrue(restored['handoffs'][0]['current'])
        self.assertEqual(restored['packet']['packet_hash'], body['packet_hash'])
        self.assertEqual(len(restored['sessions']), 1)
        self.assertIsNone(self.workspace.thread)

    def test_stale_packet_rejected_and_override_explicit(self):
        run = self.start('case-04')
        view = self.workspace.view(run)
        body = dict(packet_hash='0'*64, actor='AI verification', reason='Explicit test override, not real analyst acceptance.',
                    request_id=secrets.token_hex(16), action='close')
        with self.assertRaises(Rejected):
            self.workspace.decide(run, body)
        body['packet_hash'] = view['packet']['packet_hash']
        self.workspace.decide(run, body)
        saved = self.workspace.view(run)
        self.assertEqual(saved['reviews'][0]['disposition'], 'close')
        self.assertEqual(saved['packet']['recommendation'], 'escalate')
        self.assertEqual(saved['siem_status'], 'unchanged')

    def test_progress_reads_do_not_wait_for_worker_flock_and_failure_is_retained(self):
        ready, release = threading.Event(), threading.Event()
        def worker(store, run, token):
            def collect(db, row, bundle, call):
                call('inspect_incident', InspectIncident())
                ready.set()
                release.wait(5)
                raise Rejected('simulated offline worker failure')
            return store._investigate(run, token, collect)
        self.workspace.worker = worker
        run = self.workspace.start('case-04', secrets.token_hex(16))
        try:
            self.assertTrue(ready.wait(5))
            before = time.monotonic()
            view = self.workspace.view(run)
            self.assertLess(time.monotonic() - before, 1)
            self.assertEqual(len(view['trace']), 1)
            self.assertIsNone(view['packet'])
            self.assertEqual(self.workspace.start('case-04', secrets.token_hex(16)), run)
            with self.assertRaises(Rejected):
                self.workspace.start('case-05', secrets.token_hex(16))
        finally:
            release.set()
            self.workspace.thread.join(10)
        view = self.workspace.view(run)
        self.assertEqual(view['dispatch'], 'stopped')
        self.assertEqual(view['state'], 'failed')
        self.assertIsNone(view['packet'])
        self.assertEqual(len(view['evidence']), 1)
        self.assertNotIn('simulated offline worker failure', json.dumps(view))
        self.assertEqual(self.workspace.start('case-04', secrets.token_hex(16)), run)

    def test_crash_after_ingest_retains_capability_without_redispatch(self):
        request = secrets.token_hex(16)
        writes = []
        def fail_mapping(path, value):
            writes.append(True)
            if len(writes) == 2:
                raise OSError('simulated persistence failure after ingest')
            private_write(path, value)
        with patch('secops_triage.workspace.private_write', side_effect=fail_mapping):
            with self.assertRaises(OSError):
                self.workspace.start('case-04', request)
        self.assertIsNone(self.workspace.thread)
        persisted = json.loads(self.workspace.path.read_text())
        self.assertEqual(len(persisted['intents']), 1)
        self.assertEqual(persisted['runs'], [])
        root = self.workspace.root
        self.workspace.close()
        self.workspace = Workspace(root)
        run = self.workspace.catalog()['cases'][3]['latest_run']
        self.assertIsNotNone(run)
        view = self.workspace.view(run)
        self.assertEqual(view['dispatch'], 'interrupted')
        self.assertEqual(view['trace'], [])
        self.assertEqual(self.workspace.start('case-04', request), run)
        self.assertIsNone(self.workspace.thread)

    def test_crash_before_ingest_does_not_import_on_restart(self):
        request = secrets.token_hex(16)
        with patch.object(self.workspace.store, 'ingest', side_effect=OSError('before commit')):
            with self.assertRaises(OSError):
                self.workspace.start('case-04', request)
        root = self.workspace.root
        self.workspace.close()
        self.workspace = Workspace(root)
        self.assertEqual(self.workspace.data['runs'], [])
        self.assertEqual(self.workspace.catalog()['cases'][3]['interrupted_starts'], 1)
        with self.assertRaises(Rejected):
            self.workspace.start('case-04', request)
        self.assertIsNone(self.workspace.thread)

    def test_changed_build_preserves_trace_without_recomputing_historical_policy(self):
        run = self.start()
        original = self.workspace.view(run)
        with patch('secops_triage.workspace.engine_digest', return_value='changed-build'), \
             patch.object(self.workspace.store, '_packet', side_effect=AssertionError('must not revalidate')):
            view = self.workspace.view(run)
        self.assertTrue(view['historical_unverifiable'])
        self.assertFalse(view['engine_current'])
        self.assertIsNone(view['packet'])
        self.assertIsNone(view['policy'])
        self.assertEqual(view['recorded_packet_hash'], original['packet']['packet_hash'])
        self.assertEqual(view['trace'], original['trace'])

    def test_second_operator_and_foreign_run_refused(self):
        with self.assertRaises(Rejected):
            Workspace(self.workspace.root)
        with self.assertRaises(Rejected):
            self.workspace.view('f'*32)
        with self.assertRaises(Rejected):
            self.workspace.start('case-99', secrets.token_hex(16))
        with self.assertRaises(Rejected):
            self.workspace.start('case-04', secrets.token_hex(16), 'f'*32)

    def test_tampered_evidence_refuses_view(self):
        run = self.start()
        view = self.workspace.view(run)
        item = view['evidence'][0]
        path = self.workspace.store.blob_path(run, item['hash'])
        path.chmod(0o600)
        path.write_text('{}')
        with self.assertRaises(Rejected):
            self.workspace.view(run)

    def test_historical_store_cannot_be_implicitly_imported(self):
        root = Path(self.temp.name) / 'history'
        (root / 'store').mkdir(parents=True, mode=0o700)
        root.chmod(0o700)
        with self.assertRaises(Rejected):
            Workspace(root)


class WorkspaceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='secops-http-', dir='/private/tmp')
        cls.workspace = Workspace(Path(cls.temp.name) / 'workspace')
        cls.server = Server(cls.workspace, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.workspace.close()
        cls.temp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        c.request(method, path, body=body, headers=headers or {})
        response = c.getresponse()
        data, status, result_headers = response.read(), response.status, dict(response.getheaders())
        c.close()
        return status, data, result_headers

    def session(self):
        status, _, headers = self.request('/')
        self.assertEqual(status, 200)
        cookie = headers['Set-Cookie'].split(';')[0]
        status, body, _ = self.request('/api/session', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        return {'Cookie':cookie, 'Origin':self.server.origin, 'X-Secops-CSRF':json.loads(body)['csrf'], 'Content-Type':'application/json'}

    def test_root_csp_and_no_arbitrary_files(self):
        status, _, h = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", h['Content-Security-Policy'])
        self.assertIn('HttpOnly', h['Set-Cookie'])
        self.assertIn('SameSite=Strict', h['Set-Cookie'])
        self.assertEqual(self.request('/../workspace.json')[0], 403)
        self.assertEqual(self.request('/api/cases')[0], 403)

    def test_cross_site_and_dns_rebinding_refused(self):
        self.assertEqual(self.request('/', headers={'Host':'attacker.example'})[0], 403)
        self.assertEqual(self.request('/', headers={'Origin':'https://attacker.example'})[0], 403)
        self.assertEqual(self.request('/', headers={'Sec-Fetch-Site':'cross-site'})[0], 403)
        headers = self.session()
        headers['Origin'] = 'https://attacker.example'
        body = json.dumps({'case':'case-04','request_id':secrets.token_hex(16),'previous':None})
        self.assertEqual(self.request('/api/start','POST',body,headers)[0],409)

    def test_csrf_and_unexpected_authority_fields_refused(self):
        headers = self.session()
        del headers['X-Secops-CSRF']
        body = json.dumps({'case':'case-04','request_id':secrets.token_hex(16),'previous':None})
        self.assertEqual(self.request('/api/start','POST',body,headers)[0],409)
        headers = self.session()
        data = json.loads(body)
        data['api_key'] = 'not-a-real-key'
        self.assertEqual(self.request('/api/start','POST',json.dumps(data),headers)[0],409)
        self.assertEqual(self.request('/api/authorize','POST','{}',headers)[0],404)
        self.assertEqual(len(self.workspace.data['runs']),0)

    def test_catalog_omits_rubrics_and_cookie_is_not_owner_capability(self):
        headers = self.session()
        status, body, _ = self.request('/api/cases',headers=headers)
        self.assertEqual(status,200)
        value=json.loads(body)
        self.assertEqual(len(value['cases']),9)
        self.assertFalse(value['paid_calls_enabled'])
        self.assertNotIn('rubric',str(value))
        self.assertNotIn('recommendation',str(value))


if __name__ == '__main__':
    unittest.main()
