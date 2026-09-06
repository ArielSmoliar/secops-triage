"""Credential-free child process. Owner capability arrives only through stdin."""
import asyncio
import json
import logging
import sys


def main():
    logging.disable(logging.CRITICAL)
    from migration_proof.core.store import Store
    from .runtime import execute_session
    request = json.loads(sys.stdin.buffer.read(8193))
    store = Store(request["root"])
    result = asyncio.run(execute_session(store, request["run_id"], request["token"], request["session_id"]))
    print(json.dumps({"session_id": result["id"], "status": result["status"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(1) from None
