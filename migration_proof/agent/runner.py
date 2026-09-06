"""Supervised entrypoints with per-run exclusion and hard process-group deadlines."""
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
    return _run(store, run_id, token, limits or Limits())


def run_openai(store, run_id, token, grant_id, *, api_key):
    """Paid entrypoint. Requires a separately authorized, unclaimed owner grant."""
    from .openai_model import validate_key
    from .spend import SpendLedger
    validate_key(api_key)
    plan = SpendLedger(store).plan(run_id, token, grant_id)
    return _run(store, run_id, token, Limits(model_calls=plan.model_calls, wall_seconds=120),
                grant_id=grant_id, api_key=api_key)


def _run(store, run_id, token, limits, *, grant_id=None, api_key=None):
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
        from .contracts import MODEL_ID
        from .openai_preflight import MODEL_ID as OPENAI_MODEL_ID
        session_id = journal.start(run_id, token, limits, model_id=OPENAI_MODEL_ID if grant_id else MODEL_ID)
        request_fields = {"root": str(store.root), "run_id": run_id, "token": token, "session_id": session_id}

        process = None
        try:
            if grant_id:
                from .spend import SpendLedger
                SpendLedger(store).claim(run_id, token, grant_id, session_id)
                request_fields["api_key"] = api_key
            request = canonical(request_fields)
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
        result = journal.read(run_id, token, session_id)
        if grant_id:
            result["spend"] = SpendLedger(store).read(run_id, token, grant_id)
        return result
