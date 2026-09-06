"""Trusted orchestration limits and a closed, non-authoritative explanation format."""
from dataclasses import dataclass
import math

from migration_proof.core.contracts import Rejected

SDK_VERSION = "1.54.0"
MODEL_ID = "offline-fixture-script-v1"
REASONS = {
    "all_gates_passed": "The collected checks passed; human approval is still required.",
    "tenant_boundary_failed": "The tenant boundary failed acceptance.",
    "regression_test_added": "The allowlisted regression test was added and executed.",
    "human_correction_required": "A human must select a corrected application candidate.",
    "insufficient_evidence": "Required evidence is incomplete.",
}
STOP_REASONS = {"completed", "model_limit", "tool_limit", "deadline", "invalid_tool",
                "invalid_contract", "tool_failed", "invalid_response", "model_failed",
                "interrupted", "worker_failed", "response_limit", "context_limit"}


@dataclass(frozen=True)
class Limits:
    model_calls: int = 12
    tool_calls: int = 8
    wall_seconds: float = 60
    response_bytes: int = 16384
    context_bytes: int = 131072
    max_cost_usd: float = 0

    def __post_init__(self):
        for value, upper in ((self.model_calls, 32), (self.tool_calls, 32),
                             (self.response_bytes, 65536), (self.context_bytes, 262144)):
            if type(value) is not int or not 1 <= value <= upper:
                raise Rejected("invalid finite orchestration limit")
        if (type(self.wall_seconds) not in (int, float) or not math.isfinite(self.wall_seconds)
                or not 0 < self.wall_seconds <= 300):
            raise Rejected("invalid deadline")
        if type(self.max_cost_usd) not in (int, float) or self.max_cost_usd != 0:
            raise Rejected("only zero-cost offline orchestration is enabled")


def explanation(value):
    if (not isinstance(value, dict) or set(value) != {"recommendation", "reason_codes"}
            or value["recommendation"] not in ("ready_for_approval", "blocked")
            or not isinstance(value["reason_codes"], list) or not 1 <= len(value["reason_codes"]) <= 4
            or any(type(code) is not str or code not in REASONS for code in value["reason_codes"])):
        raise Rejected("invalid bounded explanation")
    return {"untrusted": True, "recommendation": value["recommendation"],
            "reason_codes": value["reason_codes"],
            "explanation": " ".join(REASONS[code] for code in value["reason_codes"])}
