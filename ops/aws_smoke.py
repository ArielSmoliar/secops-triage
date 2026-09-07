"""One-shot infrastructure smoke, scripted Strands only. No AWS API calls."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

from secops_triage.contracts import Rejected, canonical
from secops_triage.store import Store


def verify_mount(root, expected_uuid):
    Store._safe(root)
    if not expected_uuid or not os.path.ismount(root):
        raise Rejected('expected persistent mount is absent')
    result = subprocess.run(['findmnt', '--json', '--mountpoint', str(root),
                             '--output', 'TARGET,FSTYPE,UUID,OPTIONS'],
                            check=True, capture_output=True, text=True, timeout=10)
    mounts = json.loads(result.stdout)['filesystems']
    if len(mounts) != 1:
        raise Rejected('ambiguous persistent mount')
    mount = mounts[0]
    if (mount['target'] != str(root) or mount['uuid'] != expected_uuid
            or mount['fstype'] not in ('ext4', 'xfs')
            or 'rw' not in mount['options'].split(',')):
        raise Rejected('wrong persistent filesystem')


def write_once(path, value):
    with path.open('xb') as handle:
        handle.write(canonical(value))
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def smoke(root, slot, *, expected_uuid=None, local_check=False):
    root = Path(root).absolute()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', slot):
        raise Rejected('invalid smoke slot')
    if local_check and expected_uuid:
        raise Rejected('local check cannot attest an AWS mount')
    Store._safe(root)
    if not root.is_dir():
        raise Rejected('operator must prepare the private root first')
    if not local_check:
        verify_mount(root, expected_uuid)
    if root.stat().st_mode & 0o077:
        raise Rejected('persistent root must be private (0700)')
    location = root / slot
    old_umask = os.umask(0o077)
    try:
        location.mkdir(mode=0o700)  # Exclusive reservation; existing slot never reruns.
        parent_fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(parent_fd)  # Persist reservation before any worker can launch.
        finally:
            os.close(parent_fd)
        write_once(location / 'started.json', {
            'schema': 1, 'slot': slot, 'mode': 'local-check' if local_check else 'aws-host-candidate',
            'execution': 'scripted-strands', 'case': 'case-04', 'paid_calls': 0})
        try:
            from secops_triage.evaluation_cases import get_case
            from secops_triage.agent_runner import run_agent
            from secops_triage.report import markdown
            store = Store(location / 'store')
            token = secrets.token_urlsafe(32)
            run_id = store.ingest(get_case('case-04'), token, secrets.token_hex(16))
            write_once(location / 'owner.json', {'run_id': run_id, 'token': token})
            packet = run_agent(store, run_id, token)
            write_once(location / 'packet.json', packet)
            with (location / 'investigation.md').open('x') as handle:
                handle.write(markdown(store, packet))
                handle.flush()
                os.fsync(handle.fileno())
            if (packet['recommendation'], packet['investigation_status'], len(packet['evidence'])) != ('escalate', 'needs_review', 9):
                raise Rejected('unexpected infrastructure smoke outcome')
            event = {'schema': 1, 'slot': slot, 'state': 'completed',
                     'mode': 'local-check' if local_check else 'aws-host-candidate',
                     'execution': 'scripted-strands', 'case': 'case-04',
                     'run_id': run_id, 'packet_hash': packet['packet_hash'],
                     'evidence_reads': 9, 'paid_calls': 0,
                     'semantic_review': 'pending', 'siem_status': 'unchanged'}
            write_once(location / 'result.json', event)
            return event
        except BaseException:
            if not (location / 'result.json').exists():
                write_once(location / 'result.json', {'schema': 1, 'slot': slot,
                           'state': 'stopped', 'execution': 'scripted-strands', 'paid_calls': 0})
            raise
    finally:
        os.umask(old_umask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--slot', required=True)
    parser.add_argument('--expected-uuid')
    parser.add_argument('--local-check', action='store_true', help='Local validation only; no cloud evidence')
    args = parser.parse_args()
    try:
        print(json.dumps(smoke(args.root, args.slot, expected_uuid=args.expected_uuid,
                               local_check=args.local_check), sort_keys=True))
    except Exception:
        parser.exit(2, 'Smoke stopped; preserve slot artifacts. No automatic retry.\n')


if __name__ == '__main__':
    main()
