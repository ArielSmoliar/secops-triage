"""Success/failure paths for incident context replay; no provider or network calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from secops_triage.contracts import (IncidentBundle, Rejected, InspectIncident, LookupEntity,
                                    QueryActivity, FindRelatedCases, TOOL_NAMES, canonical)
from secops_triage.fixtures import scenario, mixed_incident, SCENARIOS
from secops_triage.store import Store
from secops_triage.report import markdown


class SecOpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/private/tmp' if Path('/private/tmp').exists() else None)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'store')
        self.token = secrets.token_urlsafe(32)

    def tearDown(self):
        self.tmp.cleanup()

    def ingest(self, bundle=None, token=None, request=None):
        return self.store.ingest(bundle or scenario('sign_in'), token or self.token, request or secrets.token_hex(16))

    def run_case(self, family, case):
        run = self.ingest(scenario(family, case))
        return self.store.investigate(run, self.token)

    def test_thirty_cases_across_three_families(self):
        expected = {'authorized': 'close', 'authorized_alternative': 'close',
                    'malicious': 'escalate', 'malicious_alternative': 'escalate',
                    'unknown': None, 'unknown_alternative': None, 'unavailable': None,
                    'stale': None, 'contradictory': 'escalate', 'injection': 'close'}
        count = 0
        for family in ('sign_in', 'phishing', 'endpoint'):
            for case in SCENARIOS:
                with self.subTest(family=family, case=case):
                    packet = self.run_case(family, case)
                    self.assertEqual(packet['recommendation'], expected[case])
                    self.assertEqual(packet['synthetic'], True)
                    self.assertEqual(packet['alerts'][0]['contradiction'], case == 'contradictory')
                    self.assertEqual(packet['investigation_status'], 'needs_review' if expected[case] is None else 'complete')
                    self.assertTrue(packet['alerts'][0]['observations'])
                    self.assertEqual(self.store.packet(packet['run_id'], self.token), packet)
                    count += 1
        self.assertEqual(count, 30)

    def test_mixed_incident_preserves_source_and_investigates_all_alerts(self):
        b = mixed_incident()
        original = canonical(b)
        run = self.ingest(b)
        packet = self.store.investigate(run, self.token)
        self.assertEqual(packet['incident_id'], b['incident_id'])
        self.assertEqual({x['family'] for x in packet['alerts']}, {'sign_in', 'phishing', 'endpoint'})
        self.assertEqual(packet['recommendation'], 'escalate')
        self.assertEqual({x['tool'] for x in packet['evidence']}, set(TOOL_NAMES))
        self.assertEqual(packet['upstream_status'], 'unchanged; local investigation only')
        self.assertEqual(canonical(b), original)
        self.assertEqual(self.store.status(run, self.token)['reviews'], [])

    def test_missing_source_is_not_a_clean_result(self):
        b = scenario('phishing')
        b['sources'] = [s for s in b['sources'] if s['template'] != 'interactions']
        run = self.ingest(b)
        packet = self.store.investigate(run, self.token)
        self.assertIsNone(packet['recommendation'])
        self.assertIn('interactions', {g['check'] for g in packet['alerts'][0]['gaps']})

    def test_source_failures_and_partial_coverage_block_close(self):
        for outcome in ('unauthorized', 'timeout', 'malformed', 'truncated', 'success'):
            with self.subTest(outcome=outcome):
                b = scenario('endpoint')
                next(s for s in b['sources'] if s['template'] == 'network').update(outcome=outcome, complete=False)
                packet = self.store.investigate(self.ingest(b), self.token)
                self.assertIsNone(packet['recommendation'])
                self.assertTrue(packet['alerts'][0]['gaps'])

    def test_positive_evidence_can_escalate_despite_missing_other_source(self):
        b = scenario('phishing', 'malicious')
        next(s for s in b['sources'] if s['template'] == 'interactions').update(outcome='timeout', complete=False)
        packet = self.store.investigate(self.ingest(b), self.token)
        self.assertEqual(packet['recommendation'], 'escalate')
        self.assertEqual(packet['investigation_status'], 'needs_review')

    def test_malicious_related_network_evidence_prevents_expected_process_close(self):
        b = scenario('endpoint', 'authorized')
        b['events'].append({'id': 'network-indicator', 'tenant_id': b['tenant_id'],
                            'source_id': 'source-intelligence', 'entity_ids': ['device-1'],
                            'occurred_at': '2026-09-07T10:03:00Z', 'kind': 'indicator',
                            'attributes': {'target_id': 'endpoint-connection', 'verdict': 'malicious',
                                           'indicator': 'Known malicious destination'},
                            'raw_text': 'Source finding associated with the observed connection.'})
        p = self.store.investigate(self.ingest(b), self.token)
        self.assertEqual(p['recommendation'], 'escalate')
        self.assertTrue(p['alerts'][0]['contradiction'])

    def test_mfa_success_alone_does_not_close(self):
        packet = self.run_case('sign_in', 'unknown')
        self.assertIsNone(packet['recommendation'])
        self.assertEqual(packet['alerts'][0]['reason'], 'legitimacy_not_established')

    def test_earlier_account_change_is_not_claimed_to_follow_signin(self):
        b = scenario('sign_in', 'malicious_alternative')
        next(e for e in b['events'] if e['kind'] == 'account_change')['occurred_at'] = '2026-09-07T09:30:00Z'
        packet = self.store.investigate(self.ingest(b), self.token)
        self.assertIsNone(packet['recommendation'])

    def test_registry_has_no_disposition_approval_or_mutation_tools(self):
        tools = self.store.agent_tools(self.ingest(), self.token)
        self.assertEqual(set(tools), set(TOOL_NAMES))
        for name in ('approve', 'promote', 'review', 'close_incident', 'escalate_incident', 'shell'):
            self.assertNotIn(name, tools)
        with self.assertRaises(Rejected):
            tools['inspect_incident']({'run_id': 'injected'})

    def test_query_scope_time_and_templates_are_enforced(self):
        run = self.ingest()
        tools = self.store.agent_tools(run, self.token)
        with self.assertRaises(Rejected):
            tools['lookup_entity'](LookupEntity('other-org-user'))
        with self.assertRaises(Rejected):
            tools['find_related_cases'](FindRelatedCases('foreign-alert'))
        for request in (QueryActivity('alert-sign_in', 'messages', '2026-09-07T09:00:00Z', '2026-09-07T10:30:00Z'),
                        QueryActivity('alert-sign_in', 'authentication', '2026-09-06T09:00:00Z', '2026-09-07T10:30:00Z')):
            with self.assertRaises(Rejected):
                tools['query_activity'](request)
        with self.assertRaises(Rejected):
            QueryActivity('alert-sign_in', 'DROP TABLE runs', '2026-09-07T09:00:00Z', '2026-09-07T10:30:00Z')

    def test_cross_organization_records_and_foreign_targets_rejected(self):
        for field in ('events', 'sources'):
            b = scenario('sign_in')
            b[field][0]['tenant_id'] = 'other-org'
            with self.assertRaises(Rejected):
                self.ingest(b)
        b = scenario('sign_in')
        b['events'][1]['attributes']['target_id'] = 'foreign-event'
        with self.assertRaises(Rejected):
            self.ingest(b)

    def test_strict_contracts_reject_unknown_fields_types_and_future_data(self):
        variations = []
        b = scenario('sign_in'); b['expected_verdict'] = 'close'; variations.append(b)
        b = scenario('sign_in'); b['sources'][0]['complete'] = 1; variations.append(b)
        b = scenario('sign_in'); b['events'][0]['attributes']['mfa'] = 'true'; variations.append(b)
        b = scenario('sign_in'); b['events'].append(deepcopy(b['events'][0])); variations.append(b)
        b = scenario('sign_in'); b['end'] = '2026-10-07T10:30:00Z'; variations.append(b)
        b = scenario('sign_in'); b['events'][0]['occurred_at'] = '2026-09-08T10:00:00Z'; variations.append(b)
        b = scenario('sign_in'); b['events'][0]['entity_ids'] = ['../escape']; variations.append(b)
        for i, b in enumerate(variations):
            with self.subTest(i=i), self.assertRaises(Rejected):
                self.ingest(b)

    def test_owner_cannot_access_another_run_with_wrong_capability(self):
        a = self.ingest()
        other = secrets.token_urlsafe(32)
        b = self.ingest(scenario('endpoint', tenant='other-org'), token=other)
        for method in (self.store.status, self.store.packet, self.store.investigate, self.store.agent_tools):
            with self.assertRaises(Rejected):
                method(b, self.token)
        self.assertNotEqual(a, b)
        self.assertEqual(self.store.investigate(b, other)['tenant_id'], 'other-org')

    def test_ingest_is_idempotent_but_changed_request_conflicts(self):
        b = scenario('sign_in')
        run = self.ingest(b, request='request-1')
        self.assertEqual(self.ingest(b, request='request-1'), run)
        b['title'] = 'Changed source incident'
        with self.assertRaises(Rejected):
            self.ingest(b, request='request-1')

    def test_previous_benign_case_does_not_authorize_current_activity(self):
        p = self.run_case('endpoint', 'unknown')
        report = markdown(self.store, p)
        self.assertIn('Previous alert on this asset', report)
        self.assertIsNone(p['recommendation'])

    def test_input_mutation_cannot_change_snapshot(self):
        b = scenario('sign_in')
        run = self.ingest(b)
        b['events'][0]['attributes']['result'] = 'failure'
        with self.store._locked() as db:
            row = self.store._owner(db, run, self.token)
            self.assertEqual(self.store._load(row).events[0].attributes['result'], 'success')

    def test_analyst_review_binds_packet_and_replays_once(self):
        run = self.ingest()
        p = self.store.investigate(run, self.token)
        args = (run, self.token, p['packet_hash'], 'Analyst Morgan', 'close', 'Reviewed source evidence', 'review-1')
        first = self.store.review(*args)
        self.assertEqual(self.store.review(*args), first)
        self.assertEqual(self.store.status(run, self.token)['state'], 'reviewed')
        self.assertEqual(len(self.store.status(run, self.token)['reviews']), 1)
        with self.assertRaises(Rejected):
            self.store.review(run, self.token, 'a' * 64, 'Analyst', 'close', 'Reviewed', 'review-2')
        with self.assertRaises(Rejected):
            self.store.review(run, self.token, p['packet_hash'], 'Analyst', 'escalate', 'Changed', 'review-1')
        self.assertEqual(self.store.status(run, self.token)['upstream_status'], 'unchanged')

    def test_analyst_override_keeps_missing_evidence_visible(self):
        p = self.run_case('phishing', 'unavailable')
        self.store.review(p['run_id'], self.token, p['packet_hash'], 'Analyst', 'escalate', 'Need additional telemetry', 'review-override')
        self.assertEqual(self.store.packet(p['run_id'], self.token)['investigation_status'], 'needs_review')

    def test_new_revision_invalidates_current_review_preserving_history(self):
        b = scenario('sign_in')
        old = self.ingest(b)
        p = self.store.investigate(old, self.token)
        self.store.review(old, self.token, p['packet_hash'], 'Analyst', 'close', 'Verified', 'old-review')
        b['title'] = 'New source incident revision'
        new = self.ingest(b)
        self.assertFalse(self.store.status(old, self.token)['is_latest'])
        self.assertFalse(self.store.status(old, self.token)['reviews'][0]['current'])
        self.assertEqual(self.store.packet(old, self.token), p)
        self.assertEqual(self.store.status(new, self.token)['reviews'], [])
        with self.assertRaises(Rejected):
            self.store.review(old, self.token, p['packet_hash'], 'Analyst', 'close', 'Verified', 'old-review')

    def test_evidence_tamper_blocks_packet_and_review(self):
        p = self.run_case('endpoint', 'authorized')
        path = self.store.blob_path(p['run_id'], p['evidence'][0]['hash'])
        path.chmod(0o600); path.write_text('{}')
        with self.assertRaises(Rejected):
            self.store.packet(p['run_id'], self.token)
        with self.assertRaises(Rejected):
            self.store.review(p['run_id'], self.token, p['packet_hash'], 'Analyst', 'close', 'Verified', 'tampered')

    def test_forged_citations_or_assessments_fail_validation(self):
        p = self.run_case('sign_in', 'unknown')
        with self.store._locked() as db:
            row = self.store._owner(db, p['run_id'], self.token)
            bad = deepcopy(p); bad['tenant_id'] = 'foreign-org'
            with self.assertRaises(Rejected):
                self.store._validate_packet(db, row, bad)
            bad = deepcopy(p); bad['recommendation'] = 'close'
            with self.assertRaises(Rejected):
                self.store._validate_packet(db, row, bad)
            bad = deepcopy(p); bad['alerts'][0]['observations'][0]['event_id'] = 'invented'
            with self.assertRaises(Rejected):
                self.store._validate_packet(db, row, bad)
            bad = deepcopy(p); bad['evidence'][0]['id'] = 'a' * 32
            with self.assertRaises(Rejected):
                self.store._validate_packet(db, row, bad)

    def test_symlink_artifacts_and_storage_roots_rejected(self):
        link = self.root / 'link'; link.symlink_to(self.root / 'store', target_is_directory=True)
        with self.assertRaises(Rejected):
            Store(link)
        p = self.run_case('sign_in', 'authorized')
        path = self.store.blob_path(p['run_id'], p['evidence'][0]['hash'])
        path.unlink(); path.symlink_to(self.root / 'unrelated')
        with self.assertRaises(Rejected):
            self.store.packet(p['run_id'], self.token)

    def test_prompt_injection_is_inert_and_report_escapes_source_markup(self):
        p = self.run_case('endpoint', 'injection')
        report = markdown(self.store, p)
        self.assertEqual(p['recommendation'], 'close')
        self.assertNotIn('<script>', report)
        self.assertNotIn('[click](https://evil.example)', report)
        self.assertIn('Source text (untrusted)', report)
        self.assertEqual(self.store.status(p['run_id'], self.token)['reviews'], [])

    def test_large_query_is_truncated_and_cannot_close(self):
        b = scenario('sign_in')
        auth = next(e for e in b['events'] if e['kind'] == 'authorization')
        for i in range(220):
            e = deepcopy(auth); e['id'] = f'authorization-{i}'; b['events'].append(e)
        p = self.store.investigate(self.ingest(b), self.token)
        self.assertIsNone(p['recommendation'])
        self.assertTrue(any(g['reason'] == 'truncated' for g in p['alerts'][0]['gaps']))

    def test_illegal_transition_and_unknown_schema_rejected(self):
        run = self.ingest()
        with self.store._locked() as db:
            with self.assertRaises(Rejected):
                self.store._transition(db, run, 'reviewed', 'skip collection')
            db.execute('PRAGMA user_version=99'); db.commit()
        with self.assertRaises(Rejected):
            Store(self.root / 'store')

    def test_unexpected_adapter_failure_publishes_no_packet_and_can_retry(self):
        run = self.ingest()
        with patch('secops_triage.replay.execute', side_effect=RuntimeError('adapter failed')):
            with self.assertRaises(RuntimeError):
                self.store.investigate(run, self.token)
        self.assertEqual(self.store.status(run, self.token)['state'], 'failed')
        with self.assertRaises(Rejected):
            self.store.packet(run, self.token)
        self.assertEqual(self.store.investigate(run, self.token)['recommendation'], 'close')

    def test_crash_recovery_never_manufactures_completed_evidence(self):
        run = self.ingest()
        script = '''import json,os,sys
from secops_triage.store import Store
from secops_triage import replay
v=json.load(sys.stdin)
s=Store(v['root'])
original=replay.execute
calls=0
def crash(bundle,request):
 global calls
 calls+=1
 if calls==3: os._exit(73)
 return original(bundle,request)
replay.execute=crash
s.investigate(v['run'],v['token'])
'''
        p = subprocess.run([sys.executable, '-c', script], input=json.dumps({'root': str(self.root / 'store'), 'run': run, 'token': self.token}), text=True, capture_output=True)
        self.assertEqual(p.returncode, 73)
        recovered = Store(self.root / 'store')
        self.assertEqual(recovered.status(run, self.token)['state'], 'needs_review')
        with recovered._locked() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM invocations WHERE state='interrupted'").fetchone()[0], 1)
            preserved = db.execute('SELECT hash FROM evidence').fetchall()
            self.assertEqual(len(preserved), 2)
        packet = recovered.investigate(run, self.token)
        self.assertEqual(packet['recommendation'], 'close')
        self.assertEqual(recovered.status(run, self.token)['reviews'], [])
        for row in preserved:
            recovered._get(run, row[0])

    def test_concurrent_investigation_and_review_are_idempotent(self):
        run = self.ingest()
        with ThreadPoolExecutor(max_workers=2) as pool:
            packets = list(pool.map(lambda _: self.store.investigate(run, self.token), range(2)))
        self.assertEqual(packets[0], packets[1])
        p = packets[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.store.review(run, self.token, p['packet_hash'], 'Analyst', 'close', 'Reviewed', 'same-review'), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.store.status(run, self.token)['reviews']), 1)

    def test_evidence_is_not_shared_between_organizations(self):
        a = self.ingest(scenario('sign_in', tenant='org-a'))
        b = self.ingest(scenario('phishing', tenant='org-b'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            packets = list(pool.map(lambda run: self.store.investigate(run, self.token), (a,b)))
        sets = [{x['hash'] for x in p['evidence']} for p in packets]
        self.assertFalse(sets[0].intersection(sets[1]))
        self.assertNotEqual(packets[0]['tenant_id'], packets[1]['tenant_id'])

    def test_cli_executes_report_and_does_not_print_owner_token(self):
        output = self.root / 'demo'
        p = subprocess.run([sys.executable, '-m', 'secops_triage', 'demo', '--output', str(output)], text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['recommendation'], 'escalate')
        owner = json.loads((output / 'owner.json').read_text())
        self.assertNotIn(owner['token'], p.stdout + p.stderr)
        self.assertEqual((output / 'owner.json').stat().st_mode & 0o777, 0o600)
        self.assertTrue((output / 'investigation.md').is_file())
        self.assertIn('deterministic', (output / 'investigation.md').read_text())


if __name__ == '__main__':
    unittest.main()
