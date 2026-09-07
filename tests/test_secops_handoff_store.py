from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from secops_triage.contracts import Rejected, TOOL_NAMES
from secops_triage.fixtures import scenario
from secops_triage.store import Store


class HandoffStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'store'
        self.store = Store(self.root)
        self.token = secrets.token_urlsafe(32)
        self.bundle = scenario('phishing', 'unavailable')
        self.run = self.store.ingest(self.bundle, self.token, 'import')
        self.packet = self.store.investigate(self.run, self.token)

    def save(self, **changes):
        args = dict(run_id=self.run, token=self.token, packet_hash=self.packet['packet_hash'],
                    actor='Test analyst', reason='Cannot establish complete context',
                    missing_context='Intelligence source unavailable',
                    next_action='Restore access and inspect the intelligence result', request_id='handoff-1')
        args.update(changes)
        return self.store.save_handoff(**args)

    def test_reload_keeps_unresolved_record_without_final_decision(self):
        saved = self.save()
        self.store = Store(self.root)
        status = self.store.status(self.run, self.token)
        self.assertEqual(status['state'], 'needs_review')
        self.assertEqual(status['reviews'], [])
        self.assertEqual(status['upstream_status'], 'unchanged')
        self.assertEqual(status['handoffs'][0]['id'], saved)
        self.assertEqual(status['handoffs'][0]['packet_hash'], self.packet['packet_hash'])
        self.assertTrue(status['handoffs'][0]['current'])
        self.assertEqual(self.store.packet(self.run, self.token), self.packet)
        self.assertEqual(set(self.store.agent_tools(self.run, self.token)), set(TOOL_NAMES))

    def test_concurrent_replay_and_changed_payload_conflict(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: self.save(), range(2)))
        self.assertEqual(ids[0], ids[1])
        with self.assertRaises(Rejected):
            self.save(next_action='Changed under reused key')
        self.assertEqual(len(self.store.status(self.run, self.token)['handoffs']), 1)

    def test_new_handoff_preserves_prior_history(self):
        first = self.save()
        second = self.save(request_id='handoff-2', next_action='Ask source owner to restore access')
        records = self.store.status(self.run, self.token)['handoffs']
        self.assertEqual([r['id'] for r in records], [first, second])
        self.assertEqual([r['current'] for r in records], [False, True])
        self.assertEqual(self.save(), first)
        self.assertEqual(self.store.status(self.run, self.token)['handoffs'], records)

    def test_new_incident_revision_invalidates_old_handoff(self):
        self.save()
        self.bundle['title'] = 'Updated source incident'
        latest = self.store.ingest(self.bundle, self.token, 'import-2')
        self.assertFalse(self.store.status(self.run, self.token)['handoffs'][0]['current'])
        self.assertEqual(self.store.status(latest, self.token)['handoffs'], [])
        with self.assertRaises(Rejected):
            self.save()

    def test_final_review_retires_handoff_without_erasing_it(self):
        saved = self.save()
        self.store.review(self.run, self.token, self.packet['packet_hash'], 'Test analyst',
                          'escalate', 'Further investigation required', 'review')
        self.assertFalse(self.store.status(self.run, self.token)['handoffs'][0]['current'])
        self.assertEqual(self.save(), saved)
        with self.assertRaises(Rejected):
            self.save(request_id='after-review')

    def test_rejects_wrong_owner_hash_and_precollection(self):
        for changes in ({'token': secrets.token_urlsafe(32)}, {'packet_hash': 'a' * 64}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                self.save(**changes)
        other = self.store.ingest(scenario('endpoint', tenant='another-org'), self.token, 'other-import')
        with self.assertRaises(Rejected):
            self.save(run_id=other)
        self.store.investigate(other, self.token)
        self.save()
        other_packet = self.store.packet(other, self.token)
        with self.assertRaises(Rejected):
            self.save(run_id=other, packet_hash=other_packet['packet_hash'])

    def test_empty_oversized_and_changed_engine_rejected(self):
        for field in ('actor', 'reason', 'missing_context', 'next_action'):
            for value in (' ', 'x' * 2001, None):
                with self.subTest(field=field, value_type=type(value)), self.assertRaises(Rejected):
                    self.save(**{field: value})
        with patch('secops_triage.store.engine_digest', return_value='changed'):
            with self.assertRaises(Rejected):
                self.save()
        self.assertEqual(self.store.status(self.run, self.token)['handoffs'], [])

    def test_tampered_handoff_blocks_read_and_update(self):
        self.save()
        record = self.store.status(self.run, self.token)['handoffs'][0]
        path = self.store.blob_path(self.run, record['content_hash'])
        path.chmod(0o600)
        path.write_text('{}')
        with self.assertRaises(Rejected):
            self.store.status(self.run, self.token)
        with self.assertRaises(Rejected):
            self.save(request_id='handoff-2')

    def test_process_crash_before_commit_preserves_previous_handoff(self):
        first = self.save()
        code = '''import json,os,sys
from secops_triage.store import Store
v=json.load(sys.stdin)
s=Store(v['root'])
original=s._put
def crash(*args):
 original(*args)
 os._exit(73)
s._put=crash
s.save_handoff(v['run'],v['token'],v['packet'],'Test analyst','Pending','Unavailable','Restore source','interrupted')
'''
        result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True,
                                input=json.dumps(dict(root=str(self.root), run=self.run,
                                                      token=self.token, packet=self.packet['packet_hash'])))
        self.assertEqual(result.returncode, 73)
        self.store = Store(self.root)
        records = self.store.status(self.run, self.token)['handoffs']
        self.assertEqual([(r['id'], r['current']) for r in records], [(first, True)])
        self.save(request_id='interrupted', reason='Pending', missing_context='Unavailable', next_action='Restore source')
        self.assertEqual(len(self.store.status(self.run, self.token)['handoffs']), 2)

    def test_insert_failure_rolls_back_retirement_of_prior_handoff(self):
        first = self.save()
        with self.store._locked() as db:
            db.execute("CREATE TRIGGER fail_new_handoff BEFORE INSERT ON handoffs "
                       "WHEN NEW.request_id='fail-insert' BEGIN SELECT RAISE(ABORT, 'injected'); END")
            db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.save(request_id='fail-insert')
        records = Store(self.root).status(self.run, self.token)['handoffs']
        self.assertEqual([(r['id'], r['current']) for r in records], [(first, True)])
        self.assertEqual(self.store.packet(self.run, self.token), self.packet)

    def test_v1_additive_migration_is_atomic_and_preserves_packet(self):
        with self.store._locked() as db:
            db.execute('DROP TABLE handoffs')
            db.execute('PRAGMA user_version=1')
            db.commit()
        with patch('secops_triage.store.HANDOFF_SCHEMA', 'CREATE TABLE handoffs(id TEXT); INVALID SQL;'):
            with self.assertRaises(sqlite3.Error):
                Store(self.root)
        with self.store._locked() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='handoffs'").fetchone())
        self.store = Store(self.root)
        with self.store._locked() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(self.store.packet(self.run, self.token), self.packet)
        self.save()
