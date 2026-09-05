"""Content-addressed, run-scoped immutable blobs and the single safe patch grammar."""
import hashlib
import json
import os
from pathlib import Path
import re

from .contracts import Rejected, digest, identifier


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


REGRESSION = '''import unittest
from tenant_api import REVISION, boundary

class TenantBoundaryRegression(unittest.TestCase):
    def test_cross_tenant_document_is_forbidden(self):
        result = boundary(REVISION)
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["leaked_fields"], [])
'''
PATCH_PATH = "tests/acceptance/test_tenant_boundary.py"
SAFE_PATCH = ("--- /dev/null\n+++ b/" + PATCH_PATH + "\n@@ -0,0 +1," +
              str(len(REGRESSION.splitlines())) + " @@\n" +
              "".join("+" + line + "\n" for line in REGRESSION.splitlines()))


def parse_patch(patch: str) -> tuple[str, str]:
    """Parse a new-file unified diff. Only the audited regression AST/text is allowed.

    This intentionally narrower grammar prevents generated Python from becoming an
    arbitrary shell/network/filesystem tool. No general patch interpreter is used.
    """
    lines = patch.splitlines(keepends=True)
    if len(lines) < 4 or lines[:2] != ["--- /dev/null\n", "+++ b/" + PATCH_PATH + "\n"]:
        raise Rejected("only a new allowlisted acceptance test is permitted")
    match = re.fullmatch(r"@@ -0,0 \+1,(\d+) @@\n", lines[2])
    if not match or not all(line.startswith("+") for line in lines[3:]):
        raise Rejected("invalid unified diff hunk")
    content = "".join(line[1:] for line in lines[3:])
    if int(match[1]) != len(lines[3:]) or content != REGRESSION:
        raise Rejected("patch must implement the audited tenant-boundary regression")
    return PATCH_PATH, content


class Artifacts:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self._safe(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(path: Path):
        for part in (path, *path.parents):
            if part.is_symlink():
                raise Rejected("symlinks are forbidden in artifact paths")

    def path(self, run_id: str, content_hash: str) -> Path:
        identifier(run_id)
        digest(content_hash)
        path = self.root / run_id / content_hash
        self._safe(path)
        return path

    def put(self, run_id: str, body: bytes) -> str:
        content_hash = sha(body)
        path = self.path(run_id, content_hash)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_fd = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
        if path.exists():
            self.get(run_id, content_hash)
            return content_hash
        # Atomic link publishes only a complete, fsynced file. Orphans are harmless.
        import tempfile
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(body)
                file.flush()
                os.fsync(file.fileno())
            os.chmod(temporary, 0o400)
            os.link(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.unlink(temporary)
        return content_hash

    def get(self, run_id: str, content_hash: str) -> bytes:
        path = self.path(run_id, content_hash)
        try:
            body = path.read_bytes()
        except OSError as error:
            raise Rejected("missing evidence or candidate artifact") from error
        if sha(body) != content_hash:
            raise Rejected("artifact SHA-256 mismatch")
        return body
