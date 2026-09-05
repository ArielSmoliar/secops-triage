from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Literal
from urllib.parse import urlparse

Revision = Literal["original", "faulty", "corrected"]

TOKENS = {"alpha-token": "alpha", "beta-token": "beta"}
DOCUMENTS = {
    "alpha-document": {"id": "alpha-document", "tenant": "alpha", "title": "Alpha roadmap"},
    "beta-document": {"id": "beta-document", "tenant": "beta", "title": "Beta acquisition"},
}


def authorize(revision: Revision, requester_tenant: str, document_tenant: str) -> bool:
    """Return the revision's authorization decision.

    The faulty migration accidentally treats any authenticated tenant as authorized.
    """
    if revision == "faulty":
        return bool(requester_tenant)
    return requester_tenant == document_tenant


def handler_for(revision: Revision) -> type[BaseHTTPRequestHandler]:
    class TenantHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            path = urlparse(self.path).path
            if path == "/health":
                self._json(200, {"status": "ok", "revision": revision})
                return

            if not path.startswith("/documents/"):
                self._json(404, {"error": "not_found"})
                return

            document = DOCUMENTS.get(path.removeprefix("/documents/"))
            if document is None:
                self._json(404, {"error": "not_found"})
                return

            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            requester_tenant = TOKENS.get(token)
            if requester_tenant is None:
                self._json(401, {"error": "unauthorized"})
                return

            if not authorize(revision, requester_tenant, document["tenant"]):
                self._json(403, {"error": "forbidden"})
                return

            self._json(200, document)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: int, body: dict[str, str]) -> None:
            payload = json.dumps(body, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return TenantHandler


@dataclass
class RunningFixture:
    revision: Revision
    server: ThreadingHTTPServer
    thread: Thread

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def __enter__(self) -> "RunningFixture":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def start_fixture(revision: Revision) -> RunningFixture:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(revision))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return RunningFixture(revision=revision, server=server, thread=thread)

