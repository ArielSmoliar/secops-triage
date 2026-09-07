"""Prepare a zero-cost synthetic analyst exercise; never dispatch a model."""
import argparse
import csv
import json
import os
from pathlib import Path
import secrets

from .contracts import IncidentBundle, canonical, sha
from .fixtures import scenario
from .report import markdown
from .store import Store


def cases():
    """Matched teaching variants, not a held-out efficacy benchmark."""
    result = {}
    for code, base in (('case-01', 'authorized'), ('case-02', 'contradictory'),
                       ('case-03', 'unavailable')):
        bundle = scenario('phishing', base)
        bundle['incident_id'] = 'INC-' + code[-2:]
        bundle['title'] = 'Reported document-sharing email'
        for event in bundle['events']:
            if event['kind'] == 'authorization':
                event['attributes'].update(actor='Security awareness team', reference='SIM-204')
                event['raw_text'] = (
                    'Owner confirmation retrieved at 10:02 UTC: campaign SIM-204 was approved before delivery. '
                    'Scope: support@vendor.example, subject Your requested document, recipient Morgan Lee, '
                    '09:00–10:30 UTC; this exact message and simulation clicks are covered. '
                    'This is a synthetic imported assertion, not independently verified.')
        bundle['events'].append({
            'id': 'phishing-click', 'tenant_id': bundle['tenant_id'],
            'source_id': 'source-interactions', 'entity_ids': ['user-1', 'device-1'],
            'occurred_at': '2026-09-07T10:04:00Z', 'kind': 'click',
            'attributes': {'message_id': 'phishing-trigger', 'action': 'allowed'},
            'raw_text': 'Synthetic click telemetry; allowed describes the recorded action, not user authorization.'})
        IncidentBundle.from_dict(bundle)
        result[code] = bundle
    return result


def prepare(output):
    output = Path(output).absolute()
    Store._safe(output)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    manifest = {'execution': 'deterministic replay; no model calls',
                'synthetic': True, 'analyst_sessions_completed': 0, 'cases': []}
    for code, bundle in cases().items():
        root = output / code
        root.mkdir(mode=0o700)
        manual = root / 'manual'
        manual.mkdir()
        store = Store(root / 'store')
        token = secrets.token_urlsafe(32)
        run = store.ingest(bundle, token, secrets.token_hex(16))
        fd = os.open(root / 'owner.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as file:
            file.write(canonical({'run_id': run, 'token': token}))
            file.flush()
            os.fsync(file.fileno())
        packet = store.investigate(run, token)
        (root / 'snapshot.json').write_bytes(canonical(bundle))
        (root / 'packet.json').write_bytes(canonical(packet))
        (root / 'assisted.md').write_text(markdown(store, packet))
        source_files = []
        for item in packet['evidence']:
            evidence = store._get(run, item['hash'])
            request = item['request']
            label = request.get('template', request.get('entity_id', item['tool']))
            filename = label + '.json'
            # Both conditions receive identical source results and coverage metadata.
            view = {'evidence_id': item['id'], 'evidence_sha256': item['hash'],
                    'tool': item['tool'], 'request': request, 'result': evidence['result']}
            (manual / filename).write_text(json.dumps(view, indent=2) + '\n')
            source_files.append(filename)
        (manual / 'START.md').write_text(
            '# Existing SIEM incident investigation\n\n'
            'Synthetic replay exercise. Review inspect_incident.json first, then the source files.\n'
            'Record close, escalate, or needs_review with evidence IDs, competing explanations, '
            'missing context and a next action. No SIEM action will occur.\n\n' +
            '\n'.join(f'- [{name}]({name})' for name in sorted(source_files)) + '\n')
        manifest['cases'].append({'case': code, 'snapshot_sha256': sha(canonical(bundle)),
                                  'run_id': run, 'packet_hash': packet['packet_hash'],
                                  'reads': len(packet['evidence']),
                                  'recommendation': packet['recommendation'],
                                  'investigation_status': packet['investigation_status'],
                                  'reviews': store.status(run, token)['reviews']})
    with (output / 'observations.csv').open('w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['participant', 'case', 'condition', 'order', 'start_utc', 'end_utc',
                         'elapsed_seconds', 'disposition', 'evidence_ids', 'missing_context',
                         'next_action', 'unsupported_claims', 'material_corrections',
                         'quality_score_0_to_10', 'critical_error', 'notes'])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'START.md').write_text(
        '# Analyst walkthrough kit\n\n'
        'Prepared synthetic cases; no analyst session or live-model evaluation has run.\n'
        'Facilitator: read docs/SECOPS-ANALYST-WALKTHROUGH.md in the repository first.\n'
        'Share only the assigned manual folder, or assisted report plus its linked evidence.\n'
        'Keep manifest, snapshots and other variants hidden until debrief.\n'
        'Record observations in observations.csv; leave unmeasured values blank.\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New private output directory')
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({'output': str(args.output.absolute()), 'cases': len(result['cases']),
                      'execution': result['execution'], 'analyst_sessions_completed': 0}))


if __name__ == '__main__':
    main()
