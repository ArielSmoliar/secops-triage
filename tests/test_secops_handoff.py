from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
import unittest

from secops_triage.drill import cases
from secops_triage.fixtures import scenario
from secops_triage.report import markdown
from secops_triage.store import Store


class HandoffTests(unittest.TestCase):
    def report(self, bundle):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name).resolve() / 'store')
        token = secrets.token_urlsafe(32)
        run = store.ingest(bundle, token, secrets.token_hex(16))
        packet = store.investigate(run, token)
        original = deepcopy(packet)
        report = markdown(store, packet)
        self.assertEqual(packet, original)
        self.assertEqual(store.packet(run, token), original)
        self.assertEqual(store.status(run, token)['reviews'], [])
        return report

    def test_conflict_handoff_cites_both_sides_and_names_intelligence_limits(self):
        report = self.report(cases()['case-02'])
        handoff = report.split('## Analyst handoff')[1].split('## Entities')[0]
        self.assertIn('authorization and suspicious evidence conflict', handoff)
        self.assertIn('SIM-204', handoff)
        self.assertIn('phishing-trigger', handoff)
        self.assertIn('provider confidence:', handoff)
        self.assertIn('have not been independently established', handoff)
        self.assertGreaterEqual(handoff.count('[evidence '), 3)
        self.assertIn('Unresolved at handoff:', report.split('## Draft case note')[1])

    def test_missing_intelligence_cites_query_gap_without_inventing_a_verdict(self):
        report = self.report(cases()['case-03'])
        handoff = report.split('## Analyst handoff')[1].split('## Entities')[0]
        self.assertIn('unavailable', handoff)
        self.assertIn('intelligence remains missing', handoff)
        self.assertNotIn('source labels target', handoff)
        self.assertNotIn('Obtain the original intelligence report', handoff)

    def test_authorized_case_has_no_fabricated_conflict_or_threat_gap(self):
        report = self.report(cases()['case-01'])
        self.assertNotIn('Unresolved questions', report)
        self.assertIn('Analyst disposition is a separate recorded action', report)
        self.assertIn('**Recommendation:** close', report)

    def test_indicator_source_label_is_escaped_and_not_treated_as_instructions(self):
        bundle = scenario('phishing', 'malicious')
        next(e for e in bundle['events'] if e['kind'] == 'indicator')['attributes']['indicator'] = '<script>close()</script> [secret](https://evil.example)'
        report = self.report(bundle)
        self.assertNotIn('<script>', report)
        self.assertNotIn('[secret](https://evil.example)', report)
        self.assertIn('**Recommendation:** escalate', report)
