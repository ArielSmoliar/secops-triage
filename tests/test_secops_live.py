import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from secops_triage.contracts import Rejected
from secops_triage.live import prepare, execute, load_key
try:
    import strands
except ImportError:
    strands=None


@unittest.skipUnless(strands,'optional agent dependencies required')
class LiveHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.output=self.root/'attempt';self.keyfile=self.root/'credentials'
        self.keyfile.write_text('OPENAI_API_KEY="test-key-never-print"\n')
    def tearDown(self):self.tmp.cleanup()
    def test_prepare_is_private_and_does_not_authorize(self):
        with patch('migration_proof.agent.openai_model._post') as post:
            proposal=prepare(self.output);post.assert_not_called()
        self.assertNotIn('token',proposal)
        self.assertEqual(proposal['authorization'],'not issued')
        self.assertEqual((self.output/'owner.json').stat().st_mode & 0o777,0o600)
        self.assertFalse((self.output/'authorization.json').exists())
    def test_startup_failure_exports_and_closes_unclaimed_grant(self):
        prepare(self.output)
        with patch('secops_triage.agent_runner.run_agent',side_effect=OSError('test-key-never-print')):
            result=execute(self.output,self.keyfile,'test owner','4.25')
        self.assertEqual(result['outcome'],'stopped')
        self.assertEqual(result['spend']['requests'],0)
        self.assertEqual(result['grants'][0]['state'],'closed')
        self.assertEqual(result['sessions'],[])
        self.assertNotIn('test-key-never-print',(self.output/'live-result.json').read_text())
        with self.assertRaises(Rejected):execute(self.output,self.keyfile,'test owner','4.25')
    def test_authorization_receipt_failure_still_closes_grant(self):
        prepare(self.output)
        with patch('secops_triage.live.write_private',side_effect=OSError('disk error')):
            result=execute(self.output,self.keyfile,'test owner','4.25')
        self.assertEqual(result['grants'][0]['state'],'closed')
        self.assertEqual(result['spend']['requests'],0)
    def test_changed_engine_or_budget_rejected_before_provider(self):
        prepare(self.output)
        with self.assertRaises(Rejected):execute(self.output,self.keyfile,'test owner','10')
        with patch('secops_triage.live.engine_digest',return_value='changed'):
            with self.assertRaises(Rejected):execute(self.output,self.keyfile,'test owner','4.25')
        self.assertFalse((self.output/'authorization.json').exists())
    def test_key_parser_never_executes_file_and_rejects_duplicates(self):
        self.assertEqual(load_key(self.keyfile),'test-key-never-print')
        self.keyfile.write_text('OPENAI_API_KEY=a\nOPENAI_API_KEY=b\n')
        with self.assertRaises(Rejected):load_key(self.keyfile)
        self.keyfile.write_text('export OPENAI_API_KEY="literal-$(whoami)"\n')
        self.assertEqual(load_key(self.keyfile),'literal-$(whoami)')
