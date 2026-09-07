"""Reproducible host-only preparation, single paid execution and sanitized export."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

from .contracts import Rejected, canonical, sha
from .fixtures import scenario
from .store import Store, engine_digest


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())


def prepare(output, case_id=None):
    if case_id is None:
        bundle = scenario('phishing', 'malicious_alternative')
    else:
        from .evaluation_cases import get_case
        bundle = get_case(case_id)
    output = Path(output).absolute()
    Store._safe(output)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    store = Store(output / 'store')
    token = secrets.token_urlsafe(32)
    run = store.ingest(bundle, token, secrets.token_hex(16))
    write_private(output / 'owner.json', {'run_id': run, 'token': token})
    write_private(output / 'incident.json', bundle)
    proposal = {'run_id': run, 'engine_hash': engine_digest(), 'scenario': 'one synthetic reported-phishing incident',
                'case_id': case_id, 'snapshot_sha256': sha(canonical(bundle)),
                'model': 'gpt-4.1-mini-2025-04-14', 'requests_max': 10, 'tool_calls_max': 9,
                'wall_seconds_max': 120, 'budget_microusd': 4250000, 'authorization': 'not issued'}
    write_private(output / 'proposal.json', proposal)
    return proposal


def load_key(path):
    """Parse only a literal assignment; never source or execute credential-file content."""
    from migration_proof.agent.openai_model import validate_key
    if Path(path).stat().st_size > 65536:
        raise Rejected('credential file exceeds limit')
    values = []
    for line in Path(path).read_text().splitlines():
        name, sep, value = line.strip().partition('=')
        if sep and name.strip() in ('OPENAI_API_KEY', 'export OPENAI_API_KEY'):
            value = value.strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            values.append(value)
    if len(values) != 1:
        raise Rejected('one literal OpenAI key assignment required')
    validate_key(values[0])
    return values[0]


def export_result(store, run, token, output, outcome, elapsed):
    from .agent_spend import spending
    from .report import markdown
    result = {'run_id': run, 'outcome': outcome, 'elapsed_seconds': round(elapsed, 3),
              'spend': spending(store, run, token), 'status': store.status(run, token)}
    with store._locked() as db:
        from .agent import SCHEMA
        db.executescript(SCHEMA)
        result['sessions'] = [dict(r) for r in db.execute('SELECT * FROM secops_agent_sessions WHERE run_id=?', (run,))]
        result['events'] = [dict(r) for r in db.execute('SELECT e.stage,e.label FROM secops_agent_events e JOIN secops_agent_sessions s ON s.id=e.session_id WHERE s.run_id=? ORDER BY e.id', (run,))]
        result['tools'] = [dict(r) for r in db.execute('SELECT tool,request,state FROM invocations WHERE run_id=? ORDER BY rowid', (run,))]
        result['grants'] = [dict(r) for r in db.execute('SELECT id,state FROM secops_grants WHERE run_id=?', (run,))]
    try:
        result['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1], text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.SubprocessError:
        result['source_commit'] = None
    if outcome == 'completed':
        packet = store.packet(run, token)
        result.update(packet_hash=packet['packet_hash'], recommendation=packet['recommendation'],
                      investigation_status=packet['investigation_status'], agent_assessment=packet['agent_assessment'])
        (output / 'packet.json').write_bytes(canonical(packet))
        (output / 'investigation.md').write_text(markdown(store, packet))
    (output / 'live-result.json').write_bytes(canonical(result))
    return result


def execute(output, key_file, actor, authorize_usd):
    from .agent_spend import authorize
    from .agent_runner import run_agent
    if authorize_usd != '4.25':
        raise Rejected('explicit authorization must match the fixed $4.25 ceiling')
    output = Path(output).absolute(); Store._safe(output)
    owner = json.loads((output / 'owner.json').read_text())
    proposal = json.loads((output / 'proposal.json').read_text())
    if proposal['engine_hash'] != engine_digest() or proposal['run_id'] != owner['run_id']:
        raise Rejected('prepared implementation changed; create a fresh run')
    store = Store(output / 'store'); run, token = owner['run_id'], owner['token']
    with store._locked() as db:
        row = store._owner(db, run, token)
        store._current(db, row)
        store._load(row)
        if proposal['snapshot_sha256'] != row['snapshot'] or sha(canonical(json.loads((output / 'incident.json').read_text()))) != row['snapshot']:
            raise Rejected('prepared fixture changed; create a fresh run')
        if proposal.get('case_id') is not None:
            from .evaluation_cases import case_digest
            if case_digest(proposal['case_id']) != row['snapshot']:
                raise Rejected('named case changed; create a fresh run')
    key = load_key(key_file)
    grant = authorize(store, run, token, actor)
    started = time.monotonic(); outcome = 'stopped'
    try:
        write_private(output / 'authorization.json', {'grant_id': grant, 'run_id': run, 'actor': actor, 'budget_microusd': 4250000})
        run_agent(store, run, token, grant_id=grant, api_key=key)
        outcome = 'completed'
    except Exception:
        pass  # Durable stage records are exported; raw exception text is not.
    finally:
        key = None
        from .agent_runner import recover
        store = recover(output / 'store')
        with store._locked() as db:
            db.execute("UPDATE secops_grants SET state='closed' WHERE id=? AND run_id=? AND state='issued'", (grant, run))
            db.commit()
    return export_result(store, run, token, output, outcome, time.monotonic()-started)


def main():
    parser = argparse.ArgumentParser(description='Host-only single synthetic investigation attempt. Never an agent tool.')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--output', required=True, type=Path)
    p.add_argument('--case', choices=['case-04'], help='Named draft evaluation case; default is historical single-message fixture')
    p = sub.add_parser('execute'); p.add_argument('--output', required=True, type=Path)
    p.add_argument('--key-file', required=True, type=Path); p.add_argument('--actor', required=True)
    p.add_argument('--authorize-usd', required=True, choices=['4.25'])
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.output, args.case)
        else:
            result = execute(args.output, args.key_file, args.actor, args.authorize_usd)
        print(json.dumps(result))
        return 0 if result.get('outcome', 'completed') == 'completed' else 2
    except Exception:
        parser.exit(2, 'Host operation stopped; inspect the prepared plan and persisted safe diagnostics.\n')


if __name__ == '__main__':
    raise SystemExit(main())
