from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from migration_proof.fixtures.tenant_api import Revision, start_fixture


@dataclass(frozen=True)
class ProbeResult:
    revision: Revision
    expected_status: int
    actual_status: int
    leaked_document_fields: list[str]

    @property
    def passed(self) -> bool:
        return self.actual_status == self.expected_status and not self.leaked_document_fields


def tenant_boundary_probe(revision: Revision) -> ProbeResult:
    with start_fixture(revision) as fixture:
        request = Request(
            f"{fixture.base_url}/documents/beta-document",
            headers={"Authorization": "Bearer alpha-token"},
        )
        try:
            with urlopen(request, timeout=2) as response:
                status = response.status
                body = json.loads(response.read())
        except HTTPError as error:
            status = error.code
            body = json.loads(error.read())
            error.close()

    leaked_fields = sorted(set(body).intersection({"id", "tenant", "title"}))
    return ProbeResult(
        revision=revision,
        expected_status=403,
        actual_status=status,
        leaked_document_fields=leaked_fields,
    )


def main() -> int:
    results = [tenant_boundary_probe(revision) for revision in ("original", "faulty", "corrected")]
    print(json.dumps([{**asdict(result), "passed": result.passed} for result in results], indent=2))
    return 0 if results[0].passed and not results[1].passed and results[2].passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
