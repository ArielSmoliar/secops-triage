import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ops.aws_smoke import smoke, verify_mount
from secops_triage.contracts import Rejected


class AwsSmokeTests(unittest.TestCase):
    def test_no_mount_cannot_create_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(Rejected):
                smoke(root, 'smoke-01', expected_uuid='expected')
            self.assertEqual(list(root.iterdir()), [])

    def test_wrong_uuid_filesystem_and_readonly_rejected(self):
        root = Path('/mnt/secops')
        base = {'target': str(root), 'fstype': 'ext4', 'uuid': 'expected', 'options': 'rw,relatime'}
        with patch('ops.aws_smoke.os.path.ismount', return_value=True):
            for changed in ({'uuid': 'wrong'}, {'fstype': 'nfs4'}, {'options': 'ro'}, {'target': '/'}):
                result = type('Result', (), {'stdout': json.dumps({'filesystems': [base | changed]})})()
                with patch('ops.aws_smoke.subprocess.run', return_value=result):
                    with self.assertRaises(Rejected):
                        verify_mount(root, 'expected')

    def test_expected_local_filesystem_accepted(self):
        result = type('Result', (), {'stdout': json.dumps({'filesystems': [
            {'target': '/mnt/secops', 'fstype': 'ext4', 'uuid': 'expected', 'options': 'rw,relatime'}]})})()
        with patch('ops.aws_smoke.os.path.ismount', return_value=True), patch('ops.aws_smoke.subprocess.run', return_value=result):
            verify_mount(Path('/mnt/secops'), 'expected')

    def test_existing_slot_never_dispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'smoke-01').mkdir()
            with patch('secops_triage.agent_runner.run_agent') as runner:
                with self.assertRaises(FileExistsError):
                    smoke(root, 'smoke-01', local_check=True)
                runner.assert_not_called()

    def test_failure_is_preserved_and_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with patch('secops_triage.agent_runner.run_agent', side_effect=RuntimeError('PRIVATE-CANARY')) as runner:
                with self.assertRaises(RuntimeError):
                    smoke(root, 'smoke-01', local_check=True)
                result = (root / 'smoke-01/result.json').read_bytes()
                self.assertNotIn(b'PRIVATE-CANARY', result)
                self.assertEqual(json.loads(result)['state'], 'stopped')
                with self.assertRaises(FileExistsError):
                    smoke(root, 'smoke-01', local_check=True)
                self.assertEqual(runner.call_count, 1)
                self.assertEqual((root / 'smoke-01/result.json').read_bytes(), result)
                self.assertEqual((root / 'smoke-01/owner.json').stat().st_mode & 0o777, 0o600)

    def test_symlink_or_public_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'alias').symlink_to(root, target_is_directory=True)
            with self.assertRaises(Rejected):
                smoke(root / 'alias', 'smoke-01', local_check=True)
            root.chmod(0o755)
            with self.assertRaises(Rejected):
                smoke(root, 'smoke-01', local_check=True)
            root.chmod(0o700)

    def test_reservation_sync_failure_prevents_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with patch('ops.aws_smoke.os.fsync', side_effect=OSError('disk failure')), patch('secops_triage.agent_runner.run_agent') as runner:
                with self.assertRaises(OSError):
                    smoke(root, 'smoke-01', local_check=True)
                runner.assert_not_called()
                self.assertTrue((root / 'smoke-01').is_dir())

    def test_template_authority_and_retention(self):
        template = json.loads((Path(__file__).resolve().parents[1] / 'infra/aws/private-host.json').read_text())
        resources = template['Resources']
        self.assertEqual(resources['DataVolume']['DeletionPolicy'], 'Retain')
        self.assertEqual(resources['DataVolume']['UpdateReplacePolicy'], 'Retain')
        self.assertTrue(resources['DataVolume']['Properties']['Encrypted'])
        self.assertFalse(resources['DataVolume']['Properties']['MultiAttachEnabled'])
        host = resources['Host']['Properties']
        self.assertEqual(host['MetadataOptions']['HttpTokens'], 'required')
        self.assertFalse(host['NetworkInterfaces'][0]['AssociatePublicIpAddress'])
        self.assertEqual(resources['SecurityGroup']['Properties']['SecurityGroupIngress'], [])
        self.assertNotIn('UserData', host)
        self.assertEqual(host['CreditSpecification']['CPUCredits'], 'standard')
        role = resources['Role']['Properties']
        self.assertNotIn('ManagedPolicyArns', role)
        serialized = json.dumps(role).lower()
        for forbidden in ('bedrock:', 'secretsmanager:', 'securityhub:', 'guardduty:', 's3:*', 'iam:passrole', 'ssm:getparameter', 'kms:decrypt'):
            self.assertNotIn(forbidden, serialized)
        actions = role['Policies'][0]['PolicyDocument']['Statement'][0]['Action']
        self.assertEqual(set(actions), {'logs:CreateLogStream', 'logs:PutLogEvents'})


if __name__ == '__main__':
    unittest.main()
