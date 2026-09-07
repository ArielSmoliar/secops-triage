import unittest

from secops_triage.case_matrix import CASE_IDS, get_case, get_expectations
from secops_triage.contracts import IncidentBundle, QueryActivity, REQUIRED, canonical, sha, instant
from secops_triage.investigation import assess
from secops_triage.replay import execute


class CaseMatrixTests(unittest.TestCase):
    def assessment(self, value):
        bundle = IncidentBundle.from_dict(value)
        alert = bundle.alerts[0]
        evidence = [{'id': 'evidence-' + template, 'tool': 'query_activity',
                     'result': execute(bundle, QueryActivity(alert.id, template, bundle.start, bundle.end))}
                    for template in REQUIRED[alert.family]]
        return assess(bundle, evidence), evidence

    def event(self, bundle, event_id):
        return next(e for e in bundle['events'] if e['id'] == event_id)

    def test_eight_distinct_draft_cases_replay_expected_outcomes(self):
        self.assertEqual(len(CASE_IDS), 8)
        self.assertEqual(len(set(CASE_IDS)), 8)
        self.assertNotIn('case-04', CASE_IDS)
        expected = [('close', 'complete'), ('escalate', 'complete'), (None, 'needs_review'),
                    ('close', 'complete'), (None, 'needs_review'), ('close', 'complete'),
                    ('escalate', 'complete'), (None, 'needs_review')]
        for cid, outcome in zip(CASE_IDS, expected):
            with self.subTest(case=cid):
                result, _ = self.assessment(get_case(cid))
                rubric = get_expectations(cid)
                self.assertEqual((result['recommendation'], result['investigation_status']), outcome)
                self.assertEqual((rubric['recommendation'], rubric['investigation_status']), outcome)
                self.assertEqual(rubric['status'], 'draft_teaching_case')
        self.assertEqual(len({sha(canonical(get_case(c))) for c in CASE_IDS}), 8)

    def test_distinctness_depends_on_activity_scope_and_coverage_not_titles(self):
        footprints = []
        for cid in CASE_IDS:
            bundle = get_case(cid)
            footprints.append(sha(canonical({
                'activity': [{'kind': e['kind'], 'attributes': e['attributes'],
                              'occurred_at': e['occurred_at']} for e in bundle['events']
                             if e['kind'] not in ('case_reference', 'authorization')],
                'scope': [e['attributes']['authorized_event_ids'] for e in bundle['events']
                          if e['kind'] == 'authorization'],
                'coverage': [(s['template'], s['outcome'], s['complete']) for s in bundle['sources']]})))
        self.assertEqual(len(set(footprints)), 8)

    def test_sources_and_rubrics_are_fresh_and_host_labels_do_not_leak(self):
        for cid in CASE_IDS:
            bundle = get_case(cid)
            rubric = get_expectations(cid)
            self.assertEqual(rubric['bundle_sha256'], sha(canonical(bundle)))
            _, evidence = self.assessment(bundle)
            for value in (bundle, evidence):
                rendered = canonical(value).decode()
                for key in ('forbidden_claims', 'draft_teaching_case', 'outcome_rationale',
                            'bundle_sha256', 'investigation_status'):
                    self.assertNotIn(key, rendered)
            bundle['events'][0]['attributes'].clear()
            rubric['facts'][0]['event_ids'].clear()
            rubric['forbidden_claims'].clear()
            self.assertTrue(get_case(cid)['events'][0]['attributes'])
            self.assertTrue(get_expectations(cid)['facts'][0]['event_ids'])
            self.assertTrue(get_expectations(cid)['forbidden_claims'])
        with self.assertRaises(ValueError):
            get_case('case-04')
        with self.assertRaises(ValueError):
            get_expectations('missing')

    def test_rubric_references_match_records_or_explicit_collection_gap(self):
        for cid in CASE_IDS:
            bundle = get_case(cid)
            events = {e['id']: e for e in bundle['events']}
            sources = {s['template']: s for s in bundle['sources']}
            rubric = get_expectations(cid)
            for claim in rubric['facts'] + rubric['unknowns']:
                with self.subTest(case=cid, claim=claim['id']):
                    if claim['event_ids']:
                        self.assertEqual(set(claim['templates']), {
                            events[e]['source_id'].removeprefix('source-') for e in claim['event_ids']})
                    else:
                        self.assertIn(claim, rubric['unknowns'])
                        self.assertTrue(claim['templates'])
                        self.assertTrue(all(sources[t]['outcome'] != 'success' for t in claim['templates']))
                    self.assertTrue(set(claim['templates']) <= set(REQUIRED[bundle['alerts'][0]['family']]))

    def test_event_joins_and_chronology_are_valid(self):
        for cid in CASE_IDS:
            bundle = get_case(cid)
            events = {e['id']: e for e in bundle['events']}
            for e in events.values():
                self.assertLessEqual(instant(bundle['start']), instant(e['occurred_at']))
                self.assertLessEqual(instant(e['occurred_at']), instant(bundle['end']))
                for field in ('message_id', 'process_id'):
                    if field in e['attributes']:
                        target = events[e['attributes'][field]]
                        self.assertLessEqual(instant(target['occurred_at']), instant(e['occurred_at']))
                if e['kind'] == 'authorization':
                    a = e['attributes']
                    for eid in a['authorized_event_ids']:
                        self.assertLessEqual(instant(a['approved_at']), instant(events[eid]['occurred_at']))
                        self.assertLessEqual(instant(a['valid_from']), instant(events[eid]['occurred_at']))
                        self.assertLessEqual(instant(events[eid]['occurred_at']), instant(a['valid_until']))

    def test_forwarding_escalation_requires_subsequent_external_change(self):
        for change in ('before', 'internal'):
            bundle = get_case('case-02')
            forwarding = self.event(bundle, 'mailbox-forwarding')
            if change == 'before':
                forwarding['occurred_at'] = '2026-09-07T09:59:00Z'
            else:
                forwarding['attributes']['external'] = False
            result, _ = self.assessment(bundle)
            self.assertIsNone(result['recommendation'])
        result, _ = self.assessment(get_case('case-02'))
        self.assertFalse(result['alerts'][0]['contradiction'])

    def test_unavailable_account_source_is_not_successful_empty_evidence(self):
        result, evidence = self.assessment(get_case('case-03'))
        source = next(e['result'] for e in evidence if e['result']['template'] == 'account_activity')
        self.assertEqual(source['outcome'], 'unavailable')
        self.assertFalse(source['complete'])
        self.assertEqual(source['records'], [])
        self.assertIn(('account_activity', 'unavailable'),
                      {(g['check'], g['reason']) for g in result['alerts'][0]['gaps']})

    def test_simulation_click_must_be_within_exact_approval_scope(self):
        bundle = get_case('case-05')
        self.assertEqual(self.event(bundle, 'simulation-click')['attributes']['message_id'], 'phishing-trigger')
        self.event(bundle, 'phishing-authorization')['attributes']['authorized_event_ids'].remove('simulation-click')
        result, _ = self.assessment(bundle)
        self.assertIsNone(result['recommendation'])
        self.assertTrue(any('activity_out_of_scope' in o['text'] for o in result['alerts'][0]['observations']))

    def test_truncated_interactions_and_unknown_url_do_not_establish_close_or_escalate(self):
        result, evidence = self.assessment(get_case('case-06'))
        interactions = next(e['result'] for e in evidence if e['result']['template'] == 'interactions')
        self.assertEqual(interactions['outcome'], 'truncated')
        self.assertFalse(interactions['complete'])
        self.assertEqual([r['id'] for r in interactions['records']], ['simulation-click'])
        self.assertIsNone(result['recommendation'])
        self.assertFalse(any(o['role'] == 'suspicious' for o in result['alerts'][0]['observations']))

    def test_inventory_upload_scope_is_required_for_close(self):
        bundle = get_case('case-07')
        self.assertEqual(self.event(bundle, 'inventory-upload')['attributes']['process_id'], 'endpoint-trigger')
        self.event(bundle, 'endpoint-authorization')['attributes']['authorized_event_ids'].remove('inventory-upload')
        result, _ = self.assessment(bundle)
        self.assertIsNone(result['recommendation'])

    def test_second_process_cannot_borrow_inventory_scope_or_hash(self):
        bundle = get_case('case-08')
        auth = self.event(bundle, 'endpoint-authorization')['attributes']
        self.assertNotIn('second-process', auth['authorized_event_ids'])
        self.assertNotIn('second-connection', auth['authorized_event_ids'])
        self.assertEqual(self.event(bundle, 'second-connection')['attributes']['process_id'], 'second-process')
        result, _ = self.assessment(bundle)
        self.assertFalse(result['alerts'][0]['contradiction'])
        self.assertEqual({o['event_id'] for o in result['alerts'][0]['observations'] if o['role'] == 'suspicious'},
                         {'second-process-hash'})
        self.event(bundle, 'second-process-hash')['attributes']['target_id'] = 'endpoint-trigger'
        result, _ = self.assessment(bundle)
        self.assertIsNone(result['recommendation'])
        self.assertIn('observable_does_not_match_target', {g['reason'] for g in result['alerts'][0]['gaps']})

    def test_revoked_approval_and_missing_network_are_independent_obstacles(self):
        bundle = get_case('case-09')
        result, evidence = self.assessment(bundle)
        network = next(e['result'] for e in evidence if e['result']['template'] == 'network')
        self.assertEqual(network['records'], [])
        self.assertTrue(any('not_approved' in o['text'] for o in result['alerts'][0]['observations']))
        next(s for s in bundle['sources'] if s['template'] == 'network').update(outcome='success', complete=True)
        result, _ = self.assessment(bundle)
        self.assertIsNone(result['recommendation'])
        self.assertEqual(result['alerts'][0]['gaps'], [])
        self.event(bundle, 'endpoint-authorization')['attributes']['status'] = 'approved'
        result, _ = self.assessment(bundle)
        self.assertEqual(result['recommendation'], 'close')
