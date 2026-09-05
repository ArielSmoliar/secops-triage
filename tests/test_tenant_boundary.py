import unittest

from migration_proof.probe import tenant_boundary_probe


class TenantBoundaryTests(unittest.TestCase):
    def test_original_and_corrected_revisions_preserve_the_boundary(self) -> None:
        self.assertTrue(tenant_boundary_probe("original").passed)
        self.assertTrue(tenant_boundary_probe("corrected").passed)

    def test_faulty_migration_exposes_the_regression(self) -> None:
        result = tenant_boundary_probe("faulty")
        self.assertFalse(result.passed)
        self.assertEqual(result.actual_status, 200)
        self.assertEqual(result.leaked_document_fields, ["id", "tenant", "title"])


if __name__ == "__main__":
    unittest.main()
