"""Supervised Strands process. Credentials use stdin, never argv, environment or output."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from .contracts import Rejected, canonical
from .store import Store


def run_agent(store, run_id, token, *, grant_id=None, api_key=None, wall_seconds=120):
    if type(wall_seconds) is not int or not 1 <= wall_seconds <= 120:
        raise Rejected('invalid hard deadline')
    store.status(run_id, token)
    if bool(grant_id) != bool(api_key):
        raise Rejected('live execution needs both owner grant and key')
    project = Path(__file__).resolve().parents[1]
    env = {'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(project), 'PYTHONIOENCODING': 'utf-8',
           'OTEL_SDK_DISABLED': 'true'}
    data = canonical({'root': str(store.root), 'run_id': run_id, 'token': token,
                      'grant_id': grant_id, 'api_key': api_key})
    process = subprocess.Popen([sys.executable, '-m', 'secops_triage.agent_runner'], cwd=project,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=env, start_new_session=True)
    try:
        output, _ = process.communicate(data, timeout=wall_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        recover(store.root)
        raise Rejected('agent deadline; no retry or refund') from None
    if process.returncode != 0:
        recover(store.root)
        raise Rejected('agent stopped; inspect persisted evidence and spending')
    if output != b'{"completed":true}\n':
        raise Rejected('invalid worker result')
    return store.packet(run_id, token)


def recover(root):
    store = Store(root)
    from .agent_spend import recover as recover_spend
    recover_spend(store)
    with store._locked() as db:
        from .agent import SCHEMA
        db.executescript(SCHEMA)
        db.execute("UPDATE secops_agent_sessions SET state='interrupted' WHERE state='running'")
        db.commit()
    return store


def main():
    try:
        body = sys.stdin.buffer.read(4097)
        if len(body) > 4096:
            raise Rejected('worker request limit')
        value = json.loads(body)
        store = recover(value['root'])
        from .agent import execute_session
        execute_session(store, value['run_id'], value['token'], grant_id=value['grant_id'], api_key=value['api_key'])
        print('{"completed":true}')
        return 0
    except BaseException:
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
