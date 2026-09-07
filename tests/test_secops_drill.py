import json
from pathlib import Path
import tempfile
import unittest

from secops_triage.drill import prepare
from secops_triage.store import Store


class AnalystDrillTests(unittest.TestCase):
    def test_matched_cases_preserve_conflict_gaps_and_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'kit'
            result = prepare(root)
            self.assertEqual([c['recommendation'] for c in result['cases']], ['close', 'escalate', None])
            self.assertEqual([c['investigation_status'] for c in result['cases']], ['complete', 'complete', 'needs_review'])
            self.assertEqual(result['analyst_sessions_completed'], 0)
            self.assertEqual(len({c['snapshot_sha256'] for c in result['cases']}), 3)
            for case in result['cases']:
                self.assertEqual(case['reads'], 9)
                self.assertEqual(case['reviews'], [])
                packet = json.loads((root / case['case'] / 'packet.json').read_text())
                self.assertEqual(packet['alerts'][0]['contradiction'], case['case'] == 'case-02')
                self.assertEqual(bool(packet['alerts'][0]['gaps']), case['case'] == 'case-03')
                self.assertNotIn('agent_assessment', packet)
                self.assertEqual((root / case['case'] / 'owner.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(len((root / 'observations.csv').read_text().splitlines()), 1)
            with self.assertRaises(FileExistsError):
                prepare(root)

    def test_manual_views_contain_exact_same_results_as_assisted_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'kit'
            result = prepare(root)
            for case in result['cases']:
                folder = root / case['case']
                store = Store(folder / 'store')
                packet = json.loads((folder / 'packet.json').read_text())
                expected = [store._get(case['run_id'], e['hash'])['result'] for e in packet['evidence']]
                views = [json.loads(p.read_text()) for p in (folder / 'manual').glob('*.json')]
                actual = [v['result'] for v in views]
                self.assertCountEqual([(v['evidence_id'], v['evidence_sha256']) for v in views],
                                      [(e['id'], e['hash']) for e in packet['evidence']])
                self.assertCountEqual(expected, actual)
                self.assertNotIn('recommendation', (folder / 'manual' / 'START.md').read_text())
                self.assertIn('deterministic', (folder / 'assisted.md').read_text())
