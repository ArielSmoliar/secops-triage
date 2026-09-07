from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
import unittest

from secops_triage.contracts import IncidentBundle, Rejected
from secops_triage.drill import cases
from secops_triage.fixtures import scenario
from secops_triage.report import markdown
from secops_triage.store import Store


class AuthorizationTests(unittest.TestCase):
    def packet(self, bundle):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name).resolve() / 'store')
        token = secrets.token_urlsafe(32)
        run = store.ingest(bundle, token, secrets.token_hex(16))
        result = store.investigate(run, token)
        self.assertEqual(store.status(run, token)['reviews'], [])
        return result, markdown(store, result)

    def auth(self, bundle):
        return next(e for e in bundle['events'] if e['kind'] == 'authorization')['attributes']

    def test_status_authority_and_window_failures_cannot_close_all_families(self):
        for family in ('sign_in', 'phishing', 'endpoint'):
            for change, failure in (({'status': 'revoked'}, 'not_approved'),
                                    ({'status': 'pending'}, 'not_approved'),
                                    ({'authority_verified': False}, 'authority_not_established'),
                                    ({'authority_role': 'unknown'}, 'authority_not_established'),
                                    ({'valid_until': '2026-09-07T09:59:59Z'}, 'activity_outside_authorization_window'),
                                    ({'valid_from': '2026-09-07T10:00:01Z'}, 'activity_outside_authorization_window'),
                                    ({'approved_at': '2026-09-07T10:01:00Z'}, 'approval_after_activity'),
                                    ({'authorized_entity_ids': ['user-1']}, 'entity_out_of_scope')):
                with self.subTest(family=family, change=change):
                    bundle = scenario(family)
                    self.auth(bundle).update(change)
                    packet, report = self.packet(bundle)
                    self.assertIsNone(packet['recommendation'])
                    self.assertEqual(packet['investigation_status'], 'needs_review')
                    self.assertIn(failure.replace('_', '\\_'), report)

    def test_wrong_family_authority_and_wrong_target_do_not_authorize(self):
        bundle = scenario('phishing')
        self.auth(bundle)['authority_role'] = 'endpoint_owner'
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])
        bundle = scenario('phishing')
        self.auth(bundle)['target_id'] = 'phishing-previous-case'
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_unapproved_click_is_not_covered_by_message_authorization_or_prose(self):
        bundle = cases()['case-01']
        self.auth(bundle)['authorized_event_ids'].remove('phishing-click')
        packet, report = self.packet(bundle)
        self.assertIsNone(packet['recommendation'])
        self.assertIn('activity\\_out\\_of\\_scope', report)
        # The source text still asserts clicks are covered, but structured scope wins.
        self.assertIn('simulation clicks are covered', report)

    def test_click_must_fall_inside_window_inclusive_boundaries(self):
        bundle = cases()['case-01']
        self.auth(bundle).update(valid_from='2026-09-07T10:00:00Z', valid_until='2026-09-07T10:04:00Z')
        self.assertEqual(self.packet(bundle)[0]['recommendation'], 'close')
        self.auth(bundle)['valid_until'] = '2026-09-07T10:03:59Z'
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_approval_must_precede_every_activity_including_earlier_account_change(self):
        bundle = scenario('sign_in')
        bundle['events'].append({'id': 'earlier-change', 'tenant_id': bundle['tenant_id'],
                                 'source_id': 'source-account_activity', 'entity_ids': ['user-1'],
                                 'occurred_at': '2026-09-07T09:30:00Z', 'kind': 'account_change',
                                 'attributes': {'change': 'display_name', 'external': False},
                                 'raw_text': 'Synthetic earlier account change.'})
        self.auth(bundle)['authorized_event_ids'].append('earlier-change')
        self.auth(bundle)['approved_at'] = '2026-09-07T09:45:00Z'
        packet, report = self.packet(bundle)
        self.assertIsNone(packet['recommendation'])
        self.assertIn('approval\\_after\\_activity', report)
        self.auth(bundle)['approved_at'] = '2026-09-07T09:30:00Z'
        self.assertEqual(self.packet(bundle)[0]['recommendation'], 'close')

    def test_related_connection_cannot_inherit_process_permission(self):
        bundle = scenario('endpoint')
        self.auth(bundle)['authorized_event_ids'] = ['endpoint-trigger']
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_second_message_does_not_inherit_first_authorization(self):
        bundle = cases()['case-01']
        message = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'message'))
        message['id'] = 'second-message'
        bundle['events'].append(message)
        bundle['alerts'][0]['trigger_ids'].append('second-message')
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_related_revocation_blocks_parent_authorization(self):
        for family, related in (('phishing', 'phishing-click'), ('endpoint', 'endpoint-connection')):
            with self.subTest(family=family):
                bundle = cases()['case-01'] if family == 'phishing' else scenario('endpoint')
                other = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'authorization'))
                other['id'] = 'related-revocation'
                other['attributes'].update(target_id=related, status='revoked', authorized_event_ids=[related])
                bundle['events'].append(other)
                packet, report = self.packet(bundle)
                self.assertIsNone(packet['recommendation'])
                self.assertIn('not\\_approved', report)

    def test_related_revocation_on_additional_activity_entity_is_collected(self):
        bundle = cases()['case-01']
        bundle['entities'].append({'id': 'user-2', 'kind': 'user', 'name': 'Second synthetic user', 'owner': 'IT'})
        click = next(e for e in bundle['events'] if e['kind'] == 'click')
        click['entity_ids'].append('user-2')
        self.auth(bundle)['authorized_entity_ids'].append('user-2')
        other = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'authorization'))
        other.update(id='related-revocation', entity_ids=['user-2'])
        other['attributes'].update(target_id='phishing-click', status='revoked', authorized_event_ids=['phishing-click'])
        bundle['events'].append(other)
        packet, report = self.packet(bundle)
        self.assertIsNone(packet['recommendation'])
        self.assertIn('related-revocation', report)
        self.assertIn('not\\_approved', report)

    def test_unrelated_entity_authorization_does_not_enter_scoped_query(self):
        from secops_triage.replay import execute
        from secops_triage.contracts import QueryActivity
        bundle = cases()['case-01']
        bundle['entities'].append({'id': 'user-2', 'kind': 'user', 'name': 'Other synthetic user', 'owner': 'IT'})
        message = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'message'))
        message.update(id='other-message', entity_ids=['user-2'])
        bundle['events'].append(message)
        other = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'authorization'))
        other.update(id='unrelated-authorization', entity_ids=['user-2'])
        other['attributes'].update(target_id='other-message', authorized_event_ids=['other-message'], authorized_entity_ids=['user-2'])
        bundle['events'].append(other)
        typed = IncidentBundle.from_dict(bundle)
        result = execute(typed, QueryActivity('alert-phishing', 'business_context', bundle['start'], bundle['end']))
        self.assertNotIn('unrelated-authorization', [r['id'] for r in result['records']])

    def test_conflicting_authorizations_cannot_be_cherry_picked(self):
        bundle = scenario('phishing')
        other = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'authorization'))
        other['id'] = 'revoked-confirmation'
        other['attributes']['status'] = 'revoked'
        bundle['events'].append(other)
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_suspicious_evidence_still_escalates_with_revoked_authorization(self):
        bundle = scenario('phishing', 'contradictory')
        self.auth(bundle)['status'] = 'revoked'
        packet, report = self.packet(bundle)
        self.assertEqual(packet['recommendation'], 'escalate')
        self.assertIn('not\\_approved', report)

    def test_strict_scope_contract_rejects_malformed_or_unknown_references(self):
        changes = [{'authority_verified': 1}, {'status': 'trusted'},
                   {'authorized_event_ids': ['missing-event']},
                   {'authorized_entity_ids': ['missing-entity']},
                   {'authorized_event_ids': []}, {'authorized_entity_ids': ['user-1', 'user-1']},
                   {'valid_from': '2026-09-07T10:30:00Z', 'valid_until': '2026-09-07T09:00:00Z'},
                   {'approved_at': '2026-09-07T11:00:00Z'}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(Rejected):
                bundle = scenario('phishing')
                self.auth(bundle).update(change)
                IncidentBundle.from_dict(bundle)
        bundle = scenario('phishing')
        a = self.auth(bundle)
        for key in list(a):
            if key not in ('target_id', 'actor', 'reference'):
                del a[key]
        with self.assertRaises(Rejected):
            IncidentBundle.from_dict(bundle)
