"""Offline entrypoint: per-run exclusion and a hard process-group deadline."""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys

from migration_proof.core.artifacts import Artifacts, canonical
from migration_proof.core.contracts import Rejected, identifier
from .contracts import Limits
from .journal import Journal


def run_offline(store, run_id, token, limits=None):
    limits = limits or Limits()
    if type(limits) is not Limits:
        raise Rejected("typed limits required")
    identifier(run_id)
    store.status(run_id, token)
    lock_path = store.root / ("agent-" + run_id + ".lock")
    Artifacts._safe(lock_path)
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Rejected("orchestration already active for this run") from None
        journal = Journal(store)
        session_id = journal.start(run_id, token, limits)
        request = canonical({"root": str(store.root), "run_id": run_id, "token": token, "session_id": session_id})
        process = None
        try:
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "migration_proof.agent.worker"],
                cwd=Path(__file__).resolve().parents[2], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                pass_fds=(lock.fileno(),),
                env={"PATH": os.defpath, "OTEL_SDK_DISABLED": "true"})
            output, errors = process.communicate(request, timeout=limits.wall_seconds)
            if process.returncode or len(output) > 65536 or len(errors) > 65536:
                journal.finish(session_id, "worker_failed")
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            journal.finish(session_id, "deadline")
        except BaseException:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            journal.finish(session_id, "interrupted")
            raise
        finally:
            with store._locked() as db:
                store._recover(db)
            fcntl.flock(lock, fcntl.LOCK_UN)
        if journal.row(session_id)["status"] == "running":
            journal.finish(session_id, "worker_failed")
        return journal.read(run_id, token, session_id)
