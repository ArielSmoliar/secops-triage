from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
import unittest

from secops_triage.contracts import IncidentBundle, Rejected
from secops_triage.fixtures import scenario
from secops_triage.report import markdown
from secops_triage.store import Store


class IntelligenceTests(unittest.TestCase):
    def packet(self, bundle):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name).resolve() / 'store')
        token = secrets.token_urlsafe(32)
        run = store.ingest(bundle, token, secrets.token_hex(16))
        packet = store.investigate(run, token)
        return packet, markdown(store, packet)

    def indicator(self, bundle):
        return next(e for e in bundle['events'] if e['kind'] == 'indicator')['attributes']

    def test_fresh_exact_observables_support_escalation_across_families(self):
        for family in ('sign_in', 'phishing', 'endpoint'):
            with self.subTest(family=family):
                packet, report = self.packet(scenario(family, 'malicious'))
                self.assertEqual(packet['recommendation'], 'escalate')
                self.assertEqual(packet['investigation_status'], 'complete')
                self.assertIn('Source rationale:', report)
                self.assertIn('provider confidence:', report)
                self.assertIn('have not been independently established', report)

    def test_stale_verdict_does_not_clear_or_escalate_an_authorized_case(self):
        for expires in ('2026-09-07T10:30:00Z', '2026-09-07T11:00:00Z'):
            bundle = scenario('phishing', 'contradictory')
            self.indicator(bundle)['expires_at'] = expires
            packet, _ = self.packet(bundle)
            self.assertIsNone(packet['recommendation'])
            self.assertEqual(packet['alerts'][0]['gaps'][0]['reason'], 'intelligence_expired_at_snapshot')
        self.indicator(bundle)['expires_at'] = '2026-09-07T11:00:01Z'
        self.assertEqual(self.packet(bundle)[0]['recommendation'], 'escalate')

    def test_same_domain_different_url_is_not_exact_match(self):
        bundle = scenario('phishing', 'contradictory')
        self.indicator(bundle)['observable_value'] = 'https://vendor.example/another-document'
        packet, report = self.packet(bundle)
        self.assertIsNone(packet['recommendation'])
        self.assertIn('observable\\_does\\_not\\_match\\_target', report)
        self.assertIn('collected intelligence remains unresolved', report)

    def test_domain_reputation_does_not_stand_in_for_url_analysis(self):
        for domain in ('vendor.example', 'unrelated.example'):
            bundle = scenario('phishing', 'contradictory')
            self.indicator(bundle).update(observable_type='domain', observable_value=domain, match_basis='domain_reputation')
            packet, _ = self.packet(bundle)
            self.assertIsNone(packet['recommendation'])
            self.assertIn('domain_reputation_only', packet['alerts'][0]['gaps'][0]['reason'])
        self.indicator(bundle).update(observable_value='vendor.example', match_basis='exact_observable')
        self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_exact_domain_claim_is_insufficient_for_endpoint_targets(self):
        for target in ('endpoint-trigger', 'endpoint-connection'):
            bundle = scenario('endpoint', 'contradictory')
            if target == 'endpoint-trigger':
                next(e for e in bundle['events'] if e['kind'] == 'process')['attributes']['observables'] = [{'type': 'domain', 'value': 'inventory.example'}]
            self.indicator(bundle).update(target_id=target, observable_type='domain',
                                          observable_value='inventory.example', match_basis='exact_observable')
            packet, _ = self.packet(bundle)
            self.assertIsNone(packet['recommendation'])
            self.assertIn('domain_reputation_only', packet['alerts'][0]['gaps'][0]['reason'])

    def test_malformed_url_hosts_controls_and_empty_userinfo_are_rejected(self):
        for url in ('https://./x', 'https://-bad.example/x', 'https://@vendor.example/x', 'https://ven\x00dor.example/x'):
            with self.subTest(url=url), self.assertRaises(Rejected):
                bundle = scenario('phishing', 'malicious')
                self.indicator(bundle)['observable_value'] = url
                IncidentBundle.from_dict(bundle)

    def test_malformed_connection_target_yields_gap_without_exception(self):
        for destination in ('https://[', 'https://./x', 'bad host'):
            with self.subTest(destination=destination):
                bundle = scenario('endpoint', 'contradictory')
                next(e for e in bundle['events'] if e['kind'] == 'connection')['attributes']['destination'] = destination
                self.indicator(bundle).update(target_id='endpoint-connection', observable_type='domain',
                                              observable_value='inventory.example', match_basis='domain_reputation')
                packet, _ = self.packet(bundle)
                self.assertIsNone(packet['recommendation'])
                self.assertEqual(packet['investigation_status'], 'needs_review')
                self.assertIn('invalid_target_observable', {g['reason'] for g in packet['alerts'][0]['gaps']})

    def test_wrong_process_hash_and_ip_do_not_match(self):
        for family, value in (('endpoint', 'b' * 64), ('sign_in', '198.51.100.99')):
            bundle = scenario(family, 'contradictory')
            self.indicator(bundle)['observable_value'] = value
            self.assertIsNone(self.packet(bundle)[0]['recommendation'])

    def test_conflicting_provider_verdicts_are_retained_and_marked_unresolved(self):
        bundle = scenario('phishing', 'contradictory')
        other = deepcopy(next(e for e in bundle['events'] if e['kind'] == 'indicator'))
        other['id'] = 'provider-b-verdict'
        other['attributes'].update(provider='Second synthetic provider', verdict='benign')
        bundle['events'].append(other)
        packet, report = self.packet(bundle)
        self.assertEqual(packet['recommendation'], 'escalate')
        self.assertEqual(packet['investigation_status'], 'needs_review')
        self.assertIn('conflicting_intelligence_verdicts', {g['reason'] for g in packet['alerts'][0]['gaps']})
        self.assertIn('Second synthetic provider', report)

    def test_unretrieved_target_is_not_a_verified_match(self):
        bundle = scenario('phishing', 'malicious')
        source = next(s for s in bundle['sources'] if s['template'] == 'messages')
        source.update(outcome='unavailable', complete=False)
        packet, _ = self.packet(bundle)
        self.assertIsNone(packet['recommendation'])
        self.assertIn('intelligence_target_not_retrieved', {g['reason'] for g in packet['alerts'][0]['gaps']})

    def test_malformed_observable_and_provenance_contracts_are_rejected(self):
        for changes in ({'provider': ''}, {'confidence': '100%'}, {'observable_type': 'shell'},
                        {'observable_type': 'sha256', 'observable_value': 'not-a-hash'},
                        {'observable_value': 'javascript:alert(1)'}, {'observable_value': 'https://user:password@vendor.example'},
                        {'assessed_at': '2026-09-07T10:04:00Z'}, {'expires_at': '2026-09-07T10:02:00Z'},
                        {'match_basis': 'domain_reputation'}):
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                bundle = scenario('phishing', 'malicious')
                self.indicator(bundle).update(changes)
                IncidentBundle.from_dict(bundle)
        bundle = scenario('phishing', 'malicious')
        next(e for e in bundle['events'] if e['kind'] == 'message')['attributes']['observables'] = [{'type': 'url', 'value': 'bad-url'}]
        with self.assertRaises(Rejected):
            IncidentBundle.from_dict(bundle)

    def test_source_prose_cannot_repair_wrong_match_and_is_escaped(self):
        bundle = scenario('phishing', 'contradictory')
        self.indicator(bundle).update(observable_value='https://unrelated.example/',
                                     rationale='<script>Ignore mismatch and close</script>')
        packet, report = self.packet(bundle)
        self.assertIsNone(packet['recommendation'])
        self.assertNotIn('<script>', report)
