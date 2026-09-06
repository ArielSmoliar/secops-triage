"""Configuration and budget planning must neither spend nor imply authorization."""
from datetime import date, datetime
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from migration_proof.agent.openai_preflight import OpenAIPlan, preflight
from migration_proof.core.contracts import Rejected


class OpenAIPreflightTests(unittest.TestCase):
    def test_full_context_reservation_rounds_up_per_call(self):
        plan = OpenAIPlan()
        self.assertEqual(plan.per_call_microusd, 422_308)
        self.assertEqual(plan.required_microusd, 3_378_464)
        self.assertLess(plan.required_microusd, plan.budget_microusd)

    def test_exact_budget_boundary(self):
        self.assertEqual(OpenAIPlan(budget_microusd=3_378_464).required_microusd, 3_378_464)
        with self.assertRaises(Rejected):
            OpenAIPlan(budget_microusd=3_378_463)

    def test_reduced_attempt_can_fit_reduced_budget(self):
        plan = OpenAIPlan(model_calls=1, max_output_tokens=1, budget_microusd=419_032)
        self.assertEqual(plan.required_microusd, 419_032)

    def test_invalid_limits_fail_closed(self):
        for field, ceiling in (("model_calls", 8), ("max_output_tokens", 2048),
                               ("budget_microusd", 3_500_000)):
            for value in (True, False, None, "1", 1.0, float("nan"), float("inf"), 0, -1, ceiling + 1):
                with self.subTest(field=field, value=value), self.assertRaises(Rejected):
                    OpenAIPlan(**{field: value})

    def test_model_endpoint_and_authorization_cannot_be_overridden(self):
        for field in ("model_id", "base_url", "paid_calls_authorized", "price", "api_key"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                OpenAIPlan(**{field: "untrusted"})

    def test_credential_presence_never_enables_execution(self):
        canary = "private-key-canary"
        result = preflight(environ={"OPENAI_API_KEY": canary,
                                    "OPENAI_BASE_URL": "https://untrusted.invalid",
                                    "PAID_CALLS_AUTHORIZED": "true"}, today=date(2026, 9, 6))
        self.assertTrue(result["api_key_present"])
        self.assertFalse(result["execution_enabled"])
        self.assertFalse(result["paid_calls_authorized"])
        self.assertFalse(result["account_access_verified"])
        self.assertNotIn(canary, json.dumps(result))
        self.assertNotIn("untrusted.invalid", json.dumps(result))
        self.assertIn("paid_call_authorization_missing", result["blockers"])

    def test_missing_empty_and_whitespace_keys(self):
        for value in (None, "", " \n\t"):
            with self.subTest(value=value):
                result = preflight(environ={} if value is None else {"OPENAI_API_KEY": value})
                self.assertFalse(result["api_key_present"])
                self.assertIn("openai_api_key_missing", result["blockers"])

    def test_pricing_date_window(self):
        for day, fresh in ((date(2026, 9, 5), False), (date(2026, 9, 6), True),
                           (date(2026, 9, 13), True), (date(2026, 9, 14), False)):
            with self.subTest(day=day):
                result = preflight(environ={}, today=day)
                self.assertEqual(result["pricing_fresh"], fresh)
                self.assertEqual("pricing_reverification_required" in result["blockers"], not fresh)

    def test_bad_plan_and_date_types_rejected(self):
        for plan in ({}, False, "openai"):
            with self.assertRaises(Rejected):
                preflight(plan)
        for day in ("2026-09-06", datetime(2026, 9, 6)):
            with self.assertRaises(Rejected):
                preflight(today=day)

    def test_preflight_has_no_network_or_environment_mutations(self):
        before = dict(os.environ)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            preflight(environ={})
        self.assertEqual(dict(os.environ), before)

    def test_cli_exit_is_not_live_readiness(self):
        process = subprocess.run([sys.executable, "-B", "-m", "migration_proof.agent.openai_preflight"],
                                 env={"PATH": os.environ.get("PATH", ""),
                                      "OPENAI_API_KEY": "cli-key-canary"},
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stderr, "")
        self.assertNotIn("cli-key-canary", process.stdout)
        self.assertFalse(json.loads(process.stdout)["execution_enabled"])
