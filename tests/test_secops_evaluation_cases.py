import unittest

from secops_triage.contracts import IncidentBundle, QueryActivity, REQUIRED, Rejected, canonical, sha
from secops_triage.evaluation_cases import get_case, case_digest, get_expectations
from secops_triage.investigation import assess
from secops_triage.replay import execute


class EvaluationCaseTests(unittest.TestCase):
    def assessment(self, value):
        bundle = IncidentBundle.from_dict(value)
        alert = bundle.alerts[0]
        evidence = [{'id': 'evidence-' + template, 'tool': 'query_activity',
                     'result': execute(bundle, QueryActivity(alert.id, template, bundle.start, bundle.end))}
                    for template in REQUIRED[alert.family]]
        return assess(bundle, evidence), evidence

    def event(self, bundle, event_id):
        return next(e for e in bundle['events'] if e['id'] == event_id)

    def test_fresh_bundle_and_stable_digest_with_separate_rubric(self):
        bundle = get_case('case-04')
        self.assertEqual(case_digest('case-04'), sha(canonical(bundle)))
        bundle['title'] = 'changed'
        self.assertNotEqual(bundle, get_case('case-04'))
        rubric = get_expectations('case-04')
        self.assertEqual(rubric['bundle_sha256'], case_digest('case-04'))
        self.assertEqual(rubric['status'], 'draft_teaching_case')
        for key in ('facts', 'unknowns', 'forbidden_claims', 'recommendation'):
            self.assertNotIn(key, get_case('case-04'))
        with self.assertRaises(ValueError):
            get_case('missing')

    def test_all_rubric_references_exist_in_expected_templates(self):
        bundle = get_case('case-04')
        events = {e['id']: e for e in bundle['events']}
        for fact in get_expectations('case-04')['facts'] + get_expectations('case-04')['unknowns']:
            self.assertTrue(fact['event_ids'])
            self.assertEqual(set(fact['templates']),
                             {events[eid]['source_id'].removeprefix('source-') for eid in fact['event_ids']})

    def test_similar_messages_keep_delivery_click_and_authorization_joins(self):
        bundle = get_case('case-04')
        first = self.event(bundle, 'message-training')['attributes']
        second = self.event(bundle, 'message-followup')['attributes']
        self.assertEqual(first['sender'], second['sender'])
        self.assertEqual(first['subject'], second['subject'])
        self.assertNotEqual(first['observables'], second['observables'])
        self.assertEqual(self.event(bundle, 'click-followup')['attributes']['message_id'], 'message-followup')
        scope = self.event(bundle, 'authorization-training')['attributes']['authorized_event_ids']
        self.assertEqual(scope, ['message-training', 'delivery-training'])
        result, _ = self.assessment(bundle)
        self.assertEqual((result['recommendation'], result['investigation_status']), ('escalate', 'needs_review'))
        self.assertFalse(result['alerts'][0]['contradiction'])
        observations = result['alerts'][0]['observations']
        self.assertEqual({o['event_id'] for o in observations if o['role'] == 'suspicious'}, {'intelligence-exact-followup'})
        self.assertIn('intelligence_expired_at_snapshot,domain_reputation_only',
                      {g['reason'] for g in result['alerts'][0]['gaps']})

    def test_wrong_message_target_cannot_borrow_the_other_url(self):
        bundle = get_case('case-04')
        self.event(bundle, 'intelligence-exact-followup')['attributes']['target_id'] = 'message-training'
        result, _ = self.assessment(bundle)
        self.assertIsNone(result['recommendation'])
        self.assertIn('observable_does_not_match_target', {g['reason'] for g in result['alerts'][0]['gaps']})

    def test_no_fresh_exact_match_leaves_case_unresolved(self):
        for change in ('removed', 'expired'):
            bundle = get_case('case-04')
            if change == 'removed':
                bundle['events'] = [e for e in bundle['events'] if e['id'] != 'intelligence-exact-followup']
            else:
                self.event(bundle, 'intelligence-exact-followup')['attributes']['expires_at'] = bundle['observed_at']
            result, _ = self.assessment(bundle)
            self.assertIsNone(result['recommendation'])
            self.assertEqual(result['investigation_status'], 'needs_review')

    def test_missing_and_truncated_interactions_do_not_become_clean_evidence(self):
        for outcome in ('unavailable', 'truncated'):
            bundle = get_case('case-04')
            next(s for s in bundle['sources'] if s['template'] == 'interactions').update(outcome=outcome, complete=False)
            result, evidence = self.assessment(bundle)
            self.assertEqual(result['recommendation'], 'escalate')
            self.assertIn(('interactions', outcome), {(g['check'], g['reason']) for g in result['alerts'][0]['gaps']})
            if outcome == 'unavailable':
                self.assertEqual(next(e['result']['records'] for e in evidence if e['result']['template'] == 'interactions'), [])

    def test_wrong_click_target_changes_scope_and_never_implies_credential_theft(self):
        bundle = get_case('case-04')
        self.event(bundle, 'click-followup')['attributes']['message_id'] = 'message-training'
        result, _ = self.assessment(bundle)
        self.assertTrue(any(o['role'] == 'authorization_gap' and 'activity_out_of_scope' in o['text']
                            for o in result['alerts'][0]['observations']))
        self.assertIn('credential_theft', {u['id'] for u in get_expectations('case-04')['unknowns']})
        original = IncidentBundle.from_dict(get_case('case-04'))
        with self.assertRaises(Rejected):
            execute(original, QueryActivity(original.alerts[0].id, 'account_activity', original.start, original.end))

    def test_same_message_authorization_and_intelligence_still_conflict(self):
        bundle = get_case('case-04')
        indicator = self.event(bundle, 'intelligence-exact-followup')['attributes']
        indicator['target_id'] = 'message-training'
        indicator['observable_value'] = self.event(bundle, 'message-training')['attributes']['observables'][0]['value']
        result, _ = self.assessment(bundle)
        self.assertTrue(result['alerts'][0]['contradiction'])
        self.assertEqual(result['recommendation'], 'escalate')

    def test_declared_extra_event_outside_validated_scope_does_not_create_conflict(self):
        bundle = get_case('case-04')
        authorization = self.event(bundle, 'authorization-training')['attributes']
        authorization['authorized_event_ids'].append('message-followup')
        authorization['valid_until'] = '2026-09-07T10:02:00Z'
        result, _ = self.assessment(bundle)
        self.assertFalse(result['alerts'][0]['contradiction'])
        self.assertEqual(result['recommendation'], 'escalate')
