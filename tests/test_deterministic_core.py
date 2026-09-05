"""Success, adversarial input, persistence, concurrency, and process-crash tests."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from migration_proof.core.artifacts import Artifacts, PATCH_PATH, SAFE_PATCH, canonical, parse_patch, sha
from migration_proof.core.contracts import (
    BaselineInput, CompareInput, InspectInput, PatchInput, Rejected,
)
from migration_proof.core.store import STATES, Store, transaction


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp" if Path('/private/tmp').exists() else None)
        self.root = Path(self.temp.name) / "store"
        self.store = Store(self.root)
        self.run = self.store.create_run("corrected")
        self.run_id, self.token = self.run["run_id"], self.run["token"]
        self.tools = self.store.agent_tools(self.run_id, self.token)

    def tearDown(self):
        self.temp.cleanup()

    def sql(self, query, args=()):
        with closing(sqlite3.connect(self.root / "state.sqlite3")) as db, db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(query, args)]

    @staticmethod
    def worker(run_id, bundle, mode):
        """Fast fixed-result seam; separate integration tests execute real HTTP."""
        if mode == "inspect":
            return {"passed": True}
        if mode == "baseline":
            return {"passed": bundle["revision"] != "faulty" or PATCH_PATH not in bundle["files"],
                    "test_count": 3 if PATCH_PATH in bundle["files"] else 2, "failures": 0, "errors": 0}
        expected = {"status": 403, "leaked_fields": []}
        actual = expected if bundle["revision"] != "faulty" else {"status": 200, "leaked_fields": ["id", "tenant", "title"]}
        return {"passed": expected == actual, "consistent": True,
                "trials": [{"original": expected, "candidate": actual}] * 3}

    def check(self, store=None, run=None):
        store, run = store or self.store, run or self.run
        tools = store.agent_tools(run["run_id"], run["token"])
        status = store.status(run["run_id"], run["token"])
        version = store._bundle(run["run_id"], status["digest"])["revision"]
        tools["inspect_candidate"](InspectInput(run["run_id"], version))
        baseline = tools["run_baseline_tests"](BaselineInput(run["run_id"], status["digest"]))
        if baseline.exit_status == 0:
            tools["compare_tenant_boundary"](CompareInput(run["run_id"], status["original_digest"], status["digest"]))
        return store.assemble_decision_packet(run["run_id"], run["token"], status["digest"])

    def ready(self):
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            return self.check()

    def approval(self):
        packet = self.ready()
        return self.store.approve(self.run_id, self.token, packet["packet_id"], "test-owner")

    def test_exact_four_scoped_contracts(self):
        self.assertEqual(set(self.tools), {"inspect_candidate", "run_baseline_tests", "compare_tenant_boundary", "apply_safe_patch"})
        with self.assertRaises(TypeError):
            self.tools["approve"] = self.store.approve
        with self.assertRaises(Rejected):
            self.tools["inspect_candidate"]({"run_id": self.run_id, "version": "corrected"})
        for invalid in ("../other", "", "z" * 32):
            with self.assertRaises(Rejected):
                InspectInput(invalid, "corrected")
        with self.assertRaises(Rejected):
            InspectInput(self.run_id, "shell")
        with self.assertRaises(Rejected):
            BaselineInput(self.run_id, "bad")

    def test_wrong_owner_and_cross_run_scope(self):
        other = self.store.create_run()
        with self.assertRaises(Rejected):
            self.store.agent_tools(other["run_id"], self.token)
        with self.assertRaises(Rejected):
            self.store.status(other["run_id"], self.token)
        with self.assertRaises(Rejected):
            self.tools["inspect_candidate"](InspectInput(other["run_id"], "faulty"))
        database = (self.root / "state.sqlite3").read_bytes()
        self.assertNotIn(self.token.encode(), database)

    def test_all_state_edges_enforced(self):
        # Exhaustively check the transition primitive; public methods separately test gate predicates.
        with self.store._locked() as db:
            for initial in STATES:
                for target in STATES:
                    db.execute("UPDATE runs SET state=? WHERE id=?", (initial, self.run_id))
                    if target in STATES[initial]:
                        with transaction(db):
                            self.store._transition(db, self.run_id, target, "test")
                    else:
                        with self.assertRaises(Rejected), transaction(db):
                            self.store._transition(db, self.run_id, target, "test")

    def test_success_approval_promotion_replay(self):
        approval = self.approval()
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            receipt = self.store.promote(self.run_id, self.token, approval, "once")
            replay = self.store.promote(self.run_id, self.token, approval, "different-key")
        self.assertEqual(receipt, replay)
        self.assertEqual(receipt["status"], "verified")
        self.assertEqual(self.store.status(self.run_id, self.token)["accepted_digest"], self.run["digest"])
        self.assertEqual(len(self.sql("SELECT * FROM promotions")), 1)
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "consumed")
        with self.assertRaises(Rejected):
            self.tools["run_baseline_tests"](BaselineInput(self.run_id, self.run["digest"]))

    def test_missing_gates_never_ready_and_packet_refreshes(self):
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            self.tools["inspect_candidate"](InspectInput(self.run_id, "corrected"))
            packet = self.store.assemble_decision_packet(self.run_id, self.token, self.run["digest"])
            self.assertFalse(packet["ready"])
            with self.assertRaises(Rejected):
                self.store.approve(self.run_id, self.token, packet["packet_id"], "owner")
            packet2 = self.check()
        self.assertTrue(packet2["ready"])
        self.assertNotEqual(packet["packet_id"], packet2["packet_id"])

    def test_stale_inputs_leave_state_unchanged(self):
        for name, request in (
            ("inspect_candidate", InspectInput(self.run_id, "faulty")),
            ("run_baseline_tests", BaselineInput(self.run_id, "0" * 64)),
            ("compare_tenant_boundary", CompareInput(self.run_id, "0" * 64, self.run["digest"])),
        ):
            with self.assertRaises(Rejected):
                self.tools[name](request)
        self.assertEqual(self.store.status(self.run_id, self.token)["state"], "created")
        self.assertFalse(self.sql("SELECT * FROM invocations"))

    def test_approval_requires_current_packet_and_actor(self):
        packet = self.ready()
        for packet_id, actor in (("other", "owner"), (packet["packet_id"], "")):
            with self.assertRaises(Rejected):
                self.store.approve(self.run_id, self.token, packet_id, actor)
        for ttl in (0, -1, 3601, float("inf"), float("nan"), True):
            with self.assertRaises(Rejected):
                self.store.approve(self.run_id, self.token, packet["packet_id"], "owner", ttl)

    def test_expired_approval_blocks_and_invalidates(self):
        approval = self.approval()
        self.sql("UPDATE approvals SET expires=0")
        with self.assertRaises(Rejected):
            self.store.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")
        self.assertFalse(self.sql("SELECT * FROM promotions"))

    def corrupt(self, content_hash):
        path = self.store.artifacts.path(self.run_id, content_hash)
        path.chmod(0o600)
        path.write_bytes(b"tampered")

    def test_candidate_change_invalidates_approval(self):
        approval = self.approval()
        self.corrupt(self.run["digest"])
        with self.assertRaises(Rejected):
            self.store.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(self.sql("SELECT state FROM runs")[0]["state"], "blocked")
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")

    def test_evidence_change_invalidates_approval(self):
        approval = self.approval()
        self.corrupt(self.sql("SELECT blob_hash FROM evidence")[0]["blob_hash"])
        with self.assertRaises(Rejected):
            self.store.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")

    def test_packet_change_invalidates_approval(self):
        approval = self.approval()
        self.corrupt(self.sql("SELECT blob_hash FROM packets")[0]["blob_hash"])
        with self.assertRaises(Rejected):
            self.store.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")

    def test_missing_artifact_fails_closed(self):
        self.ready()
        self.store.artifacts.path(self.run_id, self.run["digest"]).unlink()
        with self.assertRaises(Rejected):
            self.store.status(self.run_id, self.token)
        self.assertEqual(self.sql("SELECT state FROM runs")[0]["state"], "blocked")

    def test_patch_parser_rejects_unsafe_or_arbitrary_code(self):
        for candidate in (
            SAFE_PATCH.replace(PATCH_PATH, "../fixture.py"),
            SAFE_PATCH.replace(PATCH_PATH, "/tmp/evil.py"),
            SAFE_PATCH.replace(PATCH_PATH, "tests/acceptance/../evil.py"),
            SAFE_PATCH.replace(PATCH_PATH, "fixture.py"),
            SAFE_PATCH.replace("import unittest", "import os; os.system('id')"),
            SAFE_PATCH.replace("403", "200"),
            SAFE_PATCH + "Binary files differ\n", SAFE_PATCH + SAFE_PATCH,
            SAFE_PATCH.replace("import unittest", "SECRET_TOKEN=abc"),
            SAFE_PATCH.replace("import unittest", "\x00"),
        ):
            with self.subTest(patch=candidate[:70]), self.assertRaises(Rejected):
                parse_patch(candidate)
        self.assertEqual(parse_patch(SAFE_PATCH)[0], PATCH_PATH)

    def test_safe_patch_and_owner_correction_lineage(self):
        run = self.store.create_run("faulty")
        tools = self.store.agent_tools(run["run_id"], run["token"])
        original_blob = self.store.artifacts.get(run["run_id"], run["digest"])
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            packet = self.check(run=run)
            self.assertFalse(packet["ready"])
            repair = tools["apply_safe_patch"](PatchInput(run["run_id"], run["digest"], SAFE_PATCH))
            self.assertNotEqual(repair.candidate_digest, run["digest"])
            self.assertEqual(self.store.artifacts.get(run["run_id"], run["digest"]), original_blob)
            failed_packet = self.check(run=run)
            self.assertFalse(failed_packet["ready"])
            corrected = self.store.replace_candidate(run["run_id"], run["token"], "corrected", "owner")
            self.assertIn(PATCH_PATH, self.store._bundle(run["run_id"], corrected)["files"])
            packet = self.check(run=run)
            self.assertTrue(packet["ready"])
        evidence = self.sql("SELECT digest FROM evidence WHERE run_id=? AND id IN (" + ",".join("?" for _ in packet["evidence_ids"]) + ")", (run["run_id"], *packet["evidence_ids"]))
        self.assertTrue(all(r["digest"] == corrected for r in evidence))

    def test_patch_without_failure_is_rejected(self):
        with self.assertRaises(Rejected):
            self.tools["apply_safe_patch"](PatchInput(self.run_id, self.run["digest"], SAFE_PATCH))
        self.assertFalse(self.sql("SELECT * FROM repairs"))

    def test_tools_cannot_approve_or_replace_faulty_candidate(self):
        run = self.store.create_run("faulty")
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            packet = self.check(run=run)
        with self.assertRaises(Rejected):
            self.store.approve(run["run_id"], run["token"], packet["packet_id"], "owner")
        with self.assertRaises(Rejected):
            self.store.replace_candidate(run["run_id"], self.token, "corrected", "owner")
        self.assertEqual(self.store.status(run["run_id"], run["token"])["state"], "blocked")

    def test_tool_timeout_and_exception_are_redacted(self):
        for error in (subprocess.TimeoutExpired("worker", 15), RuntimeError("secret=do-not-store")):
            run = self.store.create_run("corrected")
            tools = self.store.agent_tools(run["run_id"], run["token"])
            with patch.object(Store, "_execute", side_effect=error), self.assertRaises(Rejected):
                tools["inspect_candidate"](InspectInput(run["run_id"], "corrected"))
            self.assertEqual(self.store.status(run["run_id"], run["token"])["state"], "blocked")
        self.assertNotIn(b"do-not-store", (self.root / "state.sqlite3").read_bytes())
        for blob in (self.root / "artifacts").glob("*/*"):
            if blob.is_file():
                self.assertNotIn(b"do-not-store", blob.read_bytes())

    def test_budget_exhaustion_blocks(self):
        self.sql("UPDATE runs SET calls=32 WHERE id=?", (self.run_id,))
        with self.assertRaises(Rejected):
            self.tools["inspect_candidate"](InspectInput(self.run_id, "corrected"))
        self.assertEqual(self.store.status(self.run_id, self.token)["state"], "blocked")

    def test_failed_promotion_rolls_back_atomically(self):
        approval = self.approval()
        with patch.object(Store, "_execute", return_value={"passed": False}):
            receipt = self.store.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(receipt["status"], "rolled_back")
        self.assertEqual(self.store.status(self.run_id, self.token)["accepted_digest"], self.run["original_digest"])
        self.assertEqual(self.store.status(self.run_id, self.token)["state"], "promotion_failed")
        self.assertEqual(self.store.promote(self.run_id, self.token, approval, "once"), receipt)

    def test_two_runs_and_concurrent_replays_are_isolated(self):
        other = self.store.create_run("corrected")
        first_approval = self.approval()
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            packet = self.check(run=other)
            second_approval = self.store.approve(other["run_id"], other["token"], packet["packet_id"], "second-owner")
            def promote(index):
                run, approval = (self.run, first_approval) if index % 2 == 0 else (other, second_approval)
                return self.store.promote(run["run_id"], run["token"], approval, "same-key")
            with ThreadPoolExecutor(max_workers=4) as executor:
                receipts = list(executor.map(promote, range(12)))
        self.assertEqual(len({r["id"] for r in receipts}), 2)
        self.assertEqual(len(self.sql("SELECT * FROM promotions")), 2)
        self.assertEqual(self.run["digest"], other["digest"])
        self.assertNotEqual(self.store.artifacts.path(self.run_id, self.run["digest"]), self.store.artifacts.path(other["run_id"], other["digest"]))
        with self.assertRaises(Rejected):
            self.store.evidence(self.run_id, self.token, packet["evidence_ids"][0])

    def test_restart_recovers_approved_and_verified_runs(self):
        approval = self.approval()
        restarted = Store(self.root)
        self.assertEqual(restarted.status(self.run_id, self.token)["state"], "approved")
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            receipt = restarted.promote(self.run_id, self.token, approval, "once")
        restarted = Store(self.root)
        self.assertEqual(restarted.promote(self.run_id, self.token, approval, "once"), receipt)

    def test_restart_invalidates_expired_approval(self):
        self.approval()
        self.sql("UPDATE approvals SET expires=0")
        restarted = Store(self.root)
        self.assertEqual(restarted.status(self.run_id, self.token)["state"], "blocked")
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")

    def child(self, source, *arguments):
        result = subprocess.run([sys.executable, "-c", source, str(self.root), *arguments], capture_output=True)
        self.assertEqual(result.returncode, 73, result.stderr.decode())

    def test_process_crash_during_tool_leaves_no_false_evidence(self):
        self.child('''import os,sys
from migration_proof.core.store import Store
from migration_proof.core.contracts import InspectInput
s=Store(sys.argv[1])
s._execute=lambda *a: os._exit(73)
s.agent_tools(sys.argv[2],sys.argv[3])["inspect_candidate"](InspectInput(sys.argv[2],"corrected"))
''', self.run_id, self.token)
        self.assertEqual(self.sql("SELECT status FROM invocations")[0]["status"], "running")
        restarted = Store(self.root)
        self.assertEqual(self.sql("SELECT status FROM invocations")[0]["status"], "interrupted")
        self.assertFalse(self.sql("SELECT * FROM evidence"))
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            self.assertTrue(self.check(store=restarted)["ready"])

    def crash_promotion(self):
        approval = self.approval()
        self.child('''import os,sys
from migration_proof.core.store import Store
s=Store(sys.argv[1])
s._finish_promotion=lambda *a: os._exit(73)
s.promote(sys.argv[2],sys.argv[3],sys.argv[4],"once")
''', self.run_id, self.token, approval)
        self.assertEqual(self.sql("SELECT status FROM promotions")[0]["status"], "pending")
        self.assertEqual(self.sql("SELECT accepted_digest FROM runs")[0]["accepted_digest"], self.run["digest"])
        return approval

    def test_process_crash_after_pointer_commit_recovers_receipt(self):
        approval = self.crash_promotion()
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            restarted = Store(self.root)
        receipt = restarted.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(receipt["status"], "verified")
        self.assertEqual(len(self.sql("SELECT * FROM promotions")), 1)

    def test_process_crash_then_verification_failure_rolls_back(self):
        approval = self.crash_promotion()
        with patch.object(Store, "_execute", side_effect=RuntimeError("offline")):
            restarted = Store(self.root)
        receipt = restarted.promote(self.run_id, self.token, approval, "once")
        self.assertEqual(receipt["status"], "rolled_back")
        self.assertEqual(restarted.status(self.run_id, self.token)["accepted_digest"], self.run["original_digest"])

    def test_artifact_publication_failure_does_not_reference_partial_blob(self):
        with patch("migration_proof.core.artifacts.os.link", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.store.artifacts.put(self.run_id, b"new artifact")
        self.assertFalse(self.store.artifacts.path(self.run_id, sha(b"new artifact")).exists())
        self.assertEqual(self.sql("PRAGMA integrity_check")[0]["integrity_check"], "ok")

    def test_symlink_artifact_and_path_traversal_rejected(self):
        path = self.store.artifacts.path(self.run_id, self.run["digest"])
        original = path.read_bytes()
        path.unlink()
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(original)
        path.symlink_to(outside)
        with self.assertRaises(Rejected):
            self.store.artifacts.get(self.run_id, self.run["digest"])
        with self.assertRaises(Rejected):
            self.store.artifacts.get("../outside", self.run["digest"])
        with self.assertRaises(Rejected):
            Artifacts(path)

    def test_canonical_digest_is_stable_and_binds_target(self):
        self.assertEqual(canonical({"b": 2, "a": 1}), canonical({"a": 1, "b": 2}))
        same = self.store.create_run("corrected")
        other = self.store.create_run("corrected", "another-target")
        self.assertEqual(same["digest"], self.run["digest"])
        self.assertNotEqual(other["digest"], self.run["digest"])

    def test_owner_replacement_invalidates_approval_and_old_evidence(self):
        run = self.store.create_run("original")
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            packet = self.check(run=run)
        approval = self.store.approve(run["run_id"], run["token"], packet["packet_id"], "owner")
        before = self.store.artifacts.get(run["run_id"], run["digest"])
        new_digest = self.store.replace_candidate(run["run_id"], run["token"], "corrected", "owner")
        self.assertNotEqual(new_digest, run["digest"])
        self.assertEqual(self.store.artifacts.get(run["run_id"], run["digest"]), before)
        self.assertEqual(self.sql("SELECT status FROM approvals WHERE id=?", (approval,))[0]["status"], "invalidated")
        with self.assertRaises(Rejected):
            self.store.promote(run["run_id"], run["token"], approval, "stale")
        self.assertFalse(self.sql("SELECT * FROM promotions"))
        with patch.object(Store, "_execute", staticmethod(self.worker)):
            self.assertTrue(self.check(run=run)["ready"])

    def test_divergent_probe_result_cannot_claim_pass(self):
        expected = {"status": 403, "leaked_fields": []}
        divergent = {"passed": True, "trials": [
            {"original": expected, "candidate": expected},
            {"original": expected, "candidate": {"status": 500, "leaked_fields": []}},
            {"original": expected, "candidate": expected}]}
        with patch.object(Store, "_execute", return_value=divergent):
            result = self.tools["compare_tenant_boundary"](CompareInput(self.run_id, self.run["original_digest"], self.run["digest"]))
        self.assertFalse(result.passed)
        self.assertEqual(self.store.status(self.run_id, self.token)["state"], "blocked")

    def test_partial_health_and_malformed_result_block(self):
        for result in ({"passed": False}, {"passed": "true"}):
            run = self.store.create_run("corrected")
            tools = self.store.agent_tools(run["run_id"], run["token"])
            with patch.object(Store, "_execute", return_value=result):
                if result["passed"] is False:
                    self.assertFalse(tools["inspect_candidate"](InspectInput(run["run_id"], "corrected")).healthy)
                else:
                    with self.assertRaises(Rejected):
                        tools["inspect_candidate"](InspectInput(run["run_id"], "corrected"))
            self.assertEqual(self.store.status(run["run_id"], run["token"])["state"], "blocked")

    def test_transaction_failure_cannot_consume_approval_or_move_pointer(self):
        approval = self.approval()
        self.sql("CREATE TRIGGER fail_receipt BEFORE INSERT ON promotions BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.promote(self.run_id, self.token, approval, "once")
        status = self.store.status(self.run_id, self.token)
        self.assertEqual(status["state"], "approved")
        self.assertEqual(status["accepted_digest"], self.run["original_digest"])
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "active")
        self.assertFalse(self.sql("SELECT * FROM promotions"))

    def test_recovery_rejects_ambiguous_promotion(self):
        self.sql("UPDATE runs SET state='promoting' WHERE id=?", (self.run_id,))
        with self.assertRaisesRegex(Rejected, "ambiguous"):
            Store(self.root)
        self.assertEqual(self.sql("SELECT state FROM runs")[0]["state"], "promoting")

    def test_unknown_schema_is_not_silently_migrated(self):
        self.sql("PRAGMA user_version=99")
        with self.assertRaises(Rejected):
            Store(self.root)
        self.assertEqual(self.sql("PRAGMA user_version")[0]["user_version"], 99)

    def test_approved_blob_cannot_be_overwritten_through_storage_api(self):
        self.approval()
        path = self.store.artifacts.path(self.run_id, self.run["digest"])
        before = path.read_bytes()
        self.assertEqual(path.stat().st_mode & 0o222, 0)
        other = self.store.artifacts.put(self.run_id, b"other candidate")
        self.assertNotEqual(other, self.run["digest"])
        self.assertEqual(path.read_bytes(), before)

    def test_backend_change_invalidates_existing_approval(self):
        self.approval()
        with patch.object(Store, "_backend_identity", return_value="0" * 64):
            with self.assertRaises(Rejected):
                self.store.status(self.run_id, self.token)
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")

    def test_runtime_change_invalidates_existing_approval(self):
        self.approval()
        with patch("migration_proof.core.store.sys.version", "different-runtime"):
            with self.assertRaises(Rejected):
                self.store.status(self.run_id, self.token)
        self.assertEqual(self.sql("SELECT status FROM approvals")[0]["status"], "invalidated")

    def test_real_fixture_success_and_failure_with_generated_test(self):
        # Full execution: HTTP health, ordinary suite, six boundary probes, and test patch.
        self.assertTrue(self.check()["ready"])
        run = self.store.create_run("faulty")
        self.assertFalse(self.check(run=run)["ready"])
        tools = self.store.agent_tools(run["run_id"], run["token"])
        repair = tools["apply_safe_patch"](PatchInput(run["run_id"], run["digest"], SAFE_PATCH))
        baseline = tools["run_baseline_tests"](BaselineInput(run["run_id"], repair.candidate_digest))
        self.assertEqual(baseline.test_count, 3)
        self.assertEqual(baseline.exit_status, 1)
        corrected = self.store.replace_candidate(run["run_id"], run["token"], "corrected", "owner")
        packet = self.check(run=run)
        self.assertTrue(packet["ready"])
        approval = self.store.approve(run["run_id"], run["token"], packet["packet_id"], "owner")
        receipt = self.store.promote(run["run_id"], run["token"], approval, "real-http")
        self.assertEqual(receipt["new_digest"], corrected)
        self.assertEqual(receipt["status"], "verified")


if __name__ == "__main__":
    unittest.main()
