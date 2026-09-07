from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from secops_triage.campaign import build_plan, write_plan
from secops_triage.contracts import REQUEST_TYPES, Rejected, canonical, sha
from secops_triage.evaluation_cases import CASE_IDS, get_case, get_expectations
from secops_triage.live import prepare
from secops_triage.store import Store


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_nine_cases_cover_all_family_outcome_pairs(self):
        self.assertEqual(len(CASE_IDS), 9)
        pairs = [(get_case(c)['alerts'][0]['family'], get_expectations(c)['recommendation']) for c in CASE_IDS]
        self.assertEqual(set(pairs), {(f, r) for f in ('sign_in', 'phishing', 'endpoint') for r in ('close', 'escalate', None)})
        self.assertEqual(len({sha(canonical(get_case(c))) for c in CASE_IDS}), 9)
        # Preserve the independently reviewed two-message source fixture exactly.
        self.assertEqual(sha(canonical(get_case('case-04'))), '7ba8064ffb58b0cae7d09119ab282231ca82cac714a702b44324ffa9e3074560')

    def test_slots_separate_acceptance_rehearsal_and_saved_playback(self):
        plan = build_plan()
        slots = plan['slots']
        self.assertEqual(len(slots), len({s['slot_id'] for s in slots}))
        m2 = [s for s in slots if s['milestone'] == 'M2']
        self.assertEqual(len(m2), 11)
        self.assertEqual([s['case_id'] for s in m2[-3:]], ['case-04'] * 3)
        self.assertEqual(Counter(s['case_id'] for s in m2), Counter({c: 3 if c == 'case-04' else 1 for c in CASE_IDS}))
        self.assertEqual(plan['totals']['M2'], {'proposed_live_runs':11, 'requests_max':110, 'ceiling_microusd':46750000})
        self.assertEqual(plan['totals']['M4'], {'proposed_live_runs':3, 'requests_max':30, 'ceiling_microusd':12750000})
        for s in slots:
            self.assertEqual(s['state'], 'unexecuted')
            self.assertIsNone(s['run_id'])
            if s['mode'] == 'proposed_saved_playback':
                self.assertEqual(s['ceiling_microusd'], 0)
                self.assertEqual(s['requests_max'], 0)
                self.assertEqual(next(p['case_id'] for p in m2 if p['slot_id'] == s['source_slot']), s['case_id'])
            elif s['milestone'] == 'M4':
                self.assertIsNone(s['execution_engine_hash'])
                self.assertEqual(s['build_binding'], 'pending_finished_ui_build')
        self.assertFalse(plan['ready_to_execute'])
        self.assertFalse(plan['pricing_reverified_by_planner'])
        self.assertEqual(set(REQUEST_TYPES), {'inspect_incident','lookup_entity','query_activity','find_related_cases'})

    def test_plan_binds_source_fixtures_rubrics_and_configuration(self):
        plan = build_plan()
        self.assertEqual(plan['plan_hash'], sha(canonical({k:v for k,v in plan.items() if k != 'plan_hash'})))
        for c, entry in plan['cases'].items():
            self.assertEqual(entry['fixture_sha256'], sha(canonical(get_case(c))))
            self.assertEqual(entry['rubric_sha256'], sha(canonical(get_expectations(c))))
            self.assertLessEqual(entry['minimum_reads'], 9)
            self.assertEqual(entry['owner_acceptance'], 'pending')
        self.assertIn('secops_triage/campaign.py', plan['source_sha256'])
        self.assertIn('secops_triage/evaluation.py', plan['source_sha256'])
        self.assertIn('uv.lock', plan['source_sha256'])
        with patch('secops_triage.campaign.engine_digest', return_value='changed'):
            self.assertNotEqual(build_plan()['plan_hash'], plan['plan_hash'])

    def test_over_budget_or_mismatched_rubric_refuses_plan(self):
        bundle = get_case('case-04')
        bundle['entities'] += [{'id': 'extra-' + str(i), 'kind': 'user', 'name': 'Synthetic additional entity', 'owner': 'IT'} for i in range(3)]
        with patch('secops_triage.campaign.get_case', return_value=bundle):
            with self.assertRaises(Rejected): build_plan()
        rubric = deepcopy(get_expectations('case-04')); rubric['bundle_sha256'] = 'changed'
        with patch('secops_triage.campaign.get_expectations', return_value=rubric):
            with self.assertRaises(Rejected): build_plan()

    def test_all_named_preparations_record_right_family_without_grants(self):
        for c in CASE_IDS:
            output = self.root / c
            result = prepare(output, c)
            self.assertEqual(result['case_id'], c)
            self.assertIn(get_case(c)['alerts'][0]['family'], result['scenario'])
            self.assertEqual(json.loads((output / 'incident.json').read_text()), get_case(c))
            self.assertFalse((output / 'authorization.json').exists())
            with Store(output / 'store')._locked() as db:
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='secops_grants'").fetchone())

    def test_private_plan_refuses_overwrite_and_has_no_execution_path(self):
        output = self.root / 'plan'
        plan = write_plan(output)
        raw = (output / 'campaign-plan.json').read_bytes()
        self.assertEqual(json.loads(raw), plan)
        self.assertEqual((output / 'campaign-plan.json').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError): write_plan(output)
        self.assertEqual((output / 'campaign-plan.json').read_bytes(), raw)
        result = subprocess.run([str(Path('.venv/bin/python').absolute()), '-m', 'secops_triage.campaign', '--output', str(self.root / 'cli')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['ready_to_execute'])
        self.assertEqual(sorted(p.name for p in (self.root / 'cli').iterdir()), ['campaign-plan.json'])

    def test_registered_cases_are_available_in_prepare_cli(self):
        result = subprocess.run([str(Path('.venv/bin/python').absolute()), '-m', 'secops_triage.live', 'prepare', '--case', 'case-09', '--output', str(self.root / 'cli-case')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['case_id'], 'case-09')
