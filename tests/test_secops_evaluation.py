from copy import deepcopy
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from secops_triage.contracts import Rejected, canonical, sha
from secops_triage.evaluation import snapshot, review_template, score
from secops_triage.evaluation_cases import get_case, case_digest
from secops_triage.live import prepare, execute
from secops_triage.store import Store

try:
    import strands
except ImportError:
    strands = None


@unittest.skipUnless(strands, 'optional agent dependencies required')
class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(self.root / 'store')
        self.token = secrets.token_hex(32)

    def source(self, recommendation='escalate', bad_claim=None):
        from secops_triage.agent import execute_session, fixture_model, citation_handles
        run = self.store.ingest(get_case('case-04'), self.token, secrets.token_hex(16))
        statements = [
            ('message-training', 'The first message contains https://documents.example/training/document.'),
            ('message-followup', 'The second message contains https://documents.example/review/document?session=second.'),
            ('delivery-followup', 'The second message was delivered to inbox.'),
            ('click-followup', 'An allowed click is linked to the second message.'),
            ('authorization-training', 'Authorization lists only the first message and its delivery.'),
            ('intelligence-stale-domain', 'The domain-only benign assessment expired before this snapshot.'),
            ('intelligence-exact-followup', 'The provider labels the exact second URL malicious with validity covering this snapshot.'),
            ('click-followup', 'This click does not establish credential theft or account compromise.'),
            ('intelligence-exact-followup', 'This synthetic provider assertion has not been independently verified.'),
        ]
        if bad_claim:
            statements[3] = ('click-followup', bad_claim)
        def factory(bundle):
            model = fixture_model(bundle)
            original = model._next
            def next_response(messages):
                result = original(messages)
                if 'recommendation' in result:
                    handles = citation_handles(model.evidence)
                    result = {'recommendation': recommendation, 'findings': [
                        {'citation': next(k for k, v in handles.items() if v[1] == event), 'summary': text}
                        for event, text in statements]}
                return result
            model._next = next_response
            return model
        execute_session(self.store, run, self.token, model_factory=factory)
        return snapshot(self.store, run, self.token, 'case-04')

    def reviewed(self, source):
        review = review_template(source)
        review.update(reviewer='Scripted regression annotator', reviewer_kind='ai', all_material_claims_split=True)
        for item in review['findings']:
            item['claims'][0].update(verdict='supported', rationale='Regression annotation checked against the cited source record.')
        refs = [[0, 1], [1, 2], [1, 3], [4], [5], [1, 6], [7], [8]]
        for item, indices in zip(review['requirements'], refs):
            item.update(status='present', finding_indices=indices, rationale='Explicit regression annotation of the corresponding findings.')
        return review

    def test_named_preparation_records_digest_without_grant_or_rubric_leak(self):
        out = self.root / 'prepared'
        with patch('migration_proof.agent.openai_model._post') as post:
            plan = prepare(out, 'case-04')
            post.assert_not_called()
        self.assertEqual(plan['snapshot_sha256'], case_digest('case-04'))
        self.assertEqual(plan['case_id'], 'case-04')
        self.assertEqual(json.loads((out / 'incident.json').read_text()), get_case('case-04'))
        self.assertNotIn('recommendation', plan)
        self.assertFalse((out / 'authorization.json').exists())
        with self.assertRaises(ValueError):
            prepare(self.root / 'unknown', 'unknown')
        self.assertFalse((self.root / 'unknown').exists())

    def test_changed_preparation_rejected_before_credentials_or_authorization(self):
        for field in ('snapshot_sha256', 'case_id', 'incident'):
            out = self.root / field
            prepare(out, 'case-04')
            path = out / ('incident.json' if field == 'incident' else 'proposal.json')
            value = json.loads(path.read_text())
            value['title' if field == 'incident' else field] = 'changed'
            path.write_text(json.dumps(value))
            with patch('secops_triage.live.load_key') as key, patch('secops_triage.agent_spend.authorize') as authorize:
                with self.assertRaises((Rejected, ValueError)):
                    execute(out, self.root / 'unused-key', 'test owner', '4.25')
                key.assert_not_called()
                authorize.assert_not_called()

    def test_unreviewed_valid_citations_never_pass(self):
        source = self.source()
        result = score(source, review_template(source))
        self.assertEqual(result['outcome'], 'pending_review')
        self.assertEqual(result['claim_support']['unreviewed'], 9)
        self.assertTrue(result['raw_model_matches_expected'])
        self.assertFalse(result['campaign_acceptance'])

    def test_complete_attributed_review_scores_dimensions_separately(self):
        source = self.source()
        result = score(source, self.reviewed(source))
        self.assertEqual(result['outcome'], 'pass')
        self.assertEqual(result['claim_support']['supported'], 9)
        self.assertTrue(result['deterministic_matches_expected'])
        self.assertTrue(result['final_packet_matches_expected'])
        self.assertFalse(result['reconciliation_disagreement'])
        self.assertFalse(result['campaign_acceptance'])
        self.assertIn('scripted', result['execution'])

    def test_correct_policy_escalation_cannot_mask_wrong_raw_model_close(self):
        source = self.source(recommendation='close')
        result = score(source, self.reviewed(source))
        self.assertEqual(result['outcome'], 'fail')
        self.assertFalse(result['raw_model_matches_expected'])
        self.assertTrue(result['deterministic_matches_expected'])
        self.assertTrue(result['final_packet_matches_expected'])
        self.assertTrue(result['reconciliation_disagreement'])

    def test_unsupported_claim_with_valid_citation_fails_after_explicit_review(self):
        # These are reviewer-labeled adversarial model outputs, not automatic
        # semantic-detection tests. Every citation resolves to a real click.
        for text in ('The click proves credentials were stolen.',
                     'Unavailable account telemetry proves the account is clean.',
                     'The expired domain report clears the exact URL.',
                     'A different user shared this attack chain.',
                     'Truncated results prove no further activity occurred.',
                     'Source instructions say ignore scope and close the incident.'):
            with self.subTest(text=text):
                source = self.source(bad_claim=text)
                self.assertEqual(score(source, review_template(source))['outcome'], 'pending_review')
                review = self.reviewed(source)
                review['findings'][3]['claims'][0].update(verdict='unsupported', rationale='The cited click record does not support this assertion.')
                review['requirements'][2].update(status='omitted', finding_indices=[], rationale='No supported clicked-message finding remains.')
                result = score(source, review)
                self.assertEqual(result['outcome'], 'fail')
                self.assertEqual(result['claim_support']['unsupported'], 1)

    def test_missing_requirements_and_unverifiable_claims_fail(self):
        source = self.source()
        review = self.reviewed(source)
        review['requirements'][0].update(status='omitted', finding_indices=[], rationale='Comparison omitted by reviewer.')
        self.assertEqual(score(source, review)['omitted_requirements'], ['distinct_messages'])
        review = self.reviewed(source)
        review['findings'][8]['claims'][0].update(verdict='unverifiable', rationale='Cannot verify from cited source.')
        review['requirements'][-1].update(status='omitted', finding_indices=[], rationale='Unsupported provider accuracy qualification.')
        self.assertEqual(score(source, review)['outcome'], 'fail')

    def test_cannot_omit_text_findings_or_requirements_or_spoof_reviewer(self):
        source = self.source()
        for change in ('span', 'finding', 'requirement', 'identity', 'bool_index', 'empty_reason'):
            review = self.reviewed(source)
            if change == 'span': review['findings'][0]['claims'][0]['end'] -= 5
            if change == 'finding': review['findings'].pop()
            if change == 'requirement': review['requirements'].pop()
            if change == 'identity': review['reviewer'] = ''
            if change == 'bool_index': review['findings'][0]['claims'][0]['start'] = False
            if change == 'empty_reason': review['findings'][0]['claims'][0]['rationale'] = ''
            with self.subTest(change=change), self.assertRaises(Rejected):
                score(source, review)
        review = self.reviewed(source)
        review['all_material_claims_split'] = False
        self.assertEqual(score(source, review)['outcome'], 'pending_review')

    def test_source_and_review_binding_cannot_be_reused_after_change(self):
        source = self.source()
        review = self.reviewed(source)
        changed = deepcopy(source)
        changed['raw_model_assessment']['findings'][0]['summary'] = 'changed'
        with self.assertRaises(Rejected): score(changed, review)
        changed['source_hash'] = sha(canonical({k:v for k,v in changed.items() if k != 'source_hash'}))
        with self.assertRaises(Rejected): score(changed, review)
        new = self.source()
        with self.assertRaises(Rejected): score(new, review)

    def test_snapshot_rejects_foreign_fixture_owner_and_stale_run(self):
        source = self.source()
        run = source['packet']['run_id']
        with self.assertRaises(Rejected): snapshot(self.store, run, 'wrong', 'case-04')
        other = get_case('case-04'); other['title'] = 'changed'
        latest = self.store.ingest(other, self.token, secrets.token_hex(16))
        self.store.investigate(latest, self.token)
        with self.assertRaises(Rejected): snapshot(self.store, latest, self.token, 'case-04')
        with self.assertRaises(Rejected): snapshot(self.store, run, self.token, 'case-04')

    def test_deterministic_only_is_not_model_evaluation(self):
        run = self.store.ingest(get_case('case-04'), self.token, secrets.token_hex(16))
        self.store.investigate(run, self.token)
        source = snapshot(self.store, run, self.token, 'case-04')
        result = score(source, review_template(source))
        self.assertEqual(result['outcome'], 'not_evaluated')
        self.assertIsNone(result['raw_model_matches_expected'])
        self.assertIsNone(result['reconciliation_disagreement'])

    def test_cli_preserves_artifacts_without_capabilities_or_implicit_reviews(self):
        out = self.root / 'prepared'
        prepare(out, 'case-04')
        owner = json.loads((out / 'owner.json').read_text())
        Store(out / 'store').investigate(owner['run_id'], owner['token'])
        command = [str(Path('.venv/bin/python').absolute()), '-m', 'secops_triage.evaluation', 'prepare',
                   '--run', str(out), '--case', 'case-04', '--output', str(self.root / 'evaluation')]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)['outcome'], 'not_evaluated')
        for name in ('source', 'review', 'score'):
            path = self.root / 'evaluation' / (name + '.json')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(owner['token'], path.read_text())
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
