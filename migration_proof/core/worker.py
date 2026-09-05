"""Fixed, isolated subprocess runner for a hashed fixture snapshot. No agent code."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(fixture, path, token=None):
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    req = Request(fixture.base_url + path, headers=headers)
    try:
        with urlopen(req, timeout=2) as response:
            return response.status, json.loads(response.read(8192))
    except HTTPError as error:
        with error:
            return error.code, json.loads(error.read(8192))


def execute(mode, revision, directory):
    spec = importlib.util.spec_from_file_location("tenant_api", directory / "fixture.py")
    fixture_module = importlib.util.module_from_spec(spec)
    sys.modules["tenant_api"] = fixture_module
    spec.loader.exec_module(fixture_module)

    def boundary(version):
        with fixture_module.start_fixture(version) as fixture:
            status, body = request(fixture, "/documents/beta-document", "alpha-token")
        return {"status": status,
                "leaked_fields": sorted(set(body) & {"id", "tenant", "title"})}

    if mode == "inspect":
        with fixture_module.start_fixture(revision) as fixture:
            status, body = request(fixture, "/health")
        return {"passed": status == 200 and body == {"status": "ok", "revision": revision}}
    if mode == "boundary":
        trials = [{"original": boundary("original"), "candidate": boundary(revision)}
                  for _ in range(3)]
        expected = {"status": 403, "leaked_fields": []}
        return {"passed": all(t["original"] == expected and t["candidate"] == expected
                               for t in trials), "trials": trials,
                "consistent": all(t == trials[0] for t in trials)}
    if mode != "baseline":
        raise ValueError("unknown fixed command")

    class Baseline(unittest.TestCase):
        def test_own_document(self):
            with fixture_module.start_fixture(revision) as fixture:
                status, body = request(fixture, "/documents/alpha-document", "alpha-token")
            self.assertEqual(status, 200)
            self.assertEqual(body["tenant"], "alpha")

        def test_unknown_token(self):
            with fixture_module.start_fixture(revision) as fixture:
                status, _ = request(fixture, "/documents/alpha-document", "invalid-token")
            self.assertEqual(status, 401)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Baseline)
    regression = directory / "tests/acceptance/test_tenant_boundary.py"
    if regression.exists():
        fixture_module.REVISION = revision
        fixture_module.boundary = boundary
        spec = importlib.util.spec_from_file_location("regression", regression)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    return {"passed": result.wasSuccessful(), "test_count": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors)}


if __name__ == "__main__":
    print(json.dumps(execute(sys.argv[1], sys.argv[2], Path(sys.argv[3])), sort_keys=True))
