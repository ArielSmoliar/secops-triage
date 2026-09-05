import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from migration_proof.fixtures.tenant_api import start_fixture


class BaselineFixtureTests(unittest.TestCase):
    def test_all_revisions_pass_the_ordinary_happy_path(self) -> None:
        for revision in ("original", "faulty", "corrected"):
            with self.subTest(revision=revision), start_fixture(revision) as fixture:
                request = Request(
                    f"{fixture.base_url}/documents/alpha-document",
                    headers={"Authorization": "Bearer alpha-token"},
                )
                with urlopen(request, timeout=2) as response:
                    body = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(body["tenant"], "alpha")

    def test_all_revisions_reject_an_unknown_token(self) -> None:
        for revision in ("original", "faulty", "corrected"):
            with self.subTest(revision=revision), start_fixture(revision) as fixture:
                request = Request(
                    f"{fixture.base_url}/documents/alpha-document",
                    headers={"Authorization": "Bearer invalid-token"},
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=2)
                self.assertEqual(raised.exception.code, 401)
                raised.exception.close()


if __name__ == "__main__":
    unittest.main()
