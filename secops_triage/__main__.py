"""Run: python -m secops_triage demo --output data/secops-demo"""
import argparse
import json
import os
from pathlib import Path
import secrets

from .contracts import Rejected, canonical
from .fixtures import mixed_incident
from .report import markdown
from .store import Store


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected('duplicate JSON field')
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description='Investigate an existing SIEM incident using local replay data.')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('demo', 'investigate'):
        p = sub.add_parser(command)
        p.add_argument('--output', required=True, type=Path, help='New private output directory')
        if command == 'investigate':
            p.add_argument('incident', type=Path, help='Normalized incident JSON snapshot, maximum 2 MB')
    args = parser.parse_args()
    try:
        if args.command == 'demo':
            value = mixed_incident()
        else:
            with args.incident.open('rb') as f:
                raw = f.read(2_000_001)
            if len(raw) > 2_000_000:
                raise Rejected('incident export exceeds 2 MB')
            value = json.loads(raw, object_pairs_hook=unique_object)
        Store._safe(args.output.absolute())
        args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
        store = Store(args.output / 'store')
        token = secrets.token_urlsafe(32)
        run_id = store.ingest(value, token, secrets.token_hex(16))
        # Retain capability before collection so a crash does not lose host ownership.
        fd = os.open(args.output / 'owner.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(canonical({'run_id': run_id, 'token': token}))
            f.flush()
            os.fsync(f.fileno())
        packet = store.investigate(run_id, token)
        (args.output / 'packet.json').write_bytes(canonical(packet))
        (args.output / 'investigation.md').write_text(markdown(store, packet))
        print(json.dumps({'report': str((args.output / 'investigation.md').absolute()),
                          'run_id': run_id, 'recommendation': packet['recommendation'],
                          'investigation_status': packet['investigation_status'],
                          'execution': packet['execution'], 'siem_status': 'unchanged'}))
    except (Rejected, ValueError, OSError) as error:
        parser.exit(2, f'Investigation stopped: {error}\n')


if __name__ == '__main__':
    main()
