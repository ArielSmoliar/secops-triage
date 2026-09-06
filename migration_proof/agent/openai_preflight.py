"""No-network planning for the first paid test; never an execution authorization."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import os
from typing import Mapping

from migration_proof.core.contracts import Rejected

MODEL_ID = "gpt-4.1-mini-2025-04-14"
MODEL_CONTEXT_TOKENS = 1_047_576
PRICE_CHECKED_ON = date(2026, 9, 6)
PRICE_SOURCE = "https://developers.openai.com/api/docs/models/gpt-4.1-mini"
# Standard text pricing, without cache discounts: $0.40/$1.60 per million tokens.
INPUT_NANODOLLARS_PER_TOKEN = 400
OUTPUT_NANODOLLARS_PER_TOKEN = 1600


@dataclass(frozen=True)
class OpenAIPlan:
    """One synthetic faulty-candidate attempt. Money is integer USD millionths."""

    model_calls: int = 8
    max_output_tokens: int = 2048
    budget_microusd: int = 3_500_000

    def __post_init__(self):
        for value, ceiling in ((self.model_calls, 8), (self.max_output_tokens, 2048),
                               (self.budget_microusd, 3_500_000)):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise Rejected("invalid bounded OpenAI test plan")
        if self.required_microusd > self.budget_microusd:
            raise Rejected("budget cannot cover the planned maximum requests")

    @property
    def per_call_microusd(self) -> int:
        # Reserve the entire documented model context, not a byte/token heuristic.
        # Adding output separately deliberately overestimates a shared context window.
        nanos = (MODEL_CONTEXT_TOKENS * INPUT_NANODOLLARS_PER_TOKEN
                 + self.max_output_tokens * OUTPUT_NANODOLLARS_PER_TOKEN)
        return (nanos + 999) // 1000

    @property
    def required_microusd(self) -> int:
        return self.model_calls * self.per_call_microusd


def preflight(plan: OpenAIPlan | None = None, *,
              environ: Mapping[str, str] | None = None, today: date | None = None) -> dict:
    """Inspect key presence only. No SDK/client, sockets, store writes, or key output."""
    if plan is None:
        plan = OpenAIPlan()
    if type(plan) is not OpenAIPlan:
        raise Rejected("expected an OpenAI test plan")
    if today is None:
        today = datetime.now(timezone.utc).date()
    if type(today) is not date:
        raise Rejected("expected a calendar date")
    env = os.environ if environ is None else environ
    key = env.get("OPENAI_API_KEY")
    key_present = isinstance(key, str) and bool(key.strip())
    price_fresh = 0 <= (today - PRICE_CHECKED_ON).days <= 7
    blockers = ["paid_call_authorization_missing", "account_model_access_unverified"]
    if not key_present:
        blockers.append("openai_api_key_missing")
    if not price_fresh:
        blockers.append("pricing_reverification_required")
    return {
        "provider": "openai_api", "model_id": MODEL_ID,
        "transport_implemented": True, "spend_ledger_implemented": True,
        "scenario": "one_faulty_candidate_attempt", "model_calls": plan.model_calls,
        "max_output_tokens": plan.max_output_tokens,
        "budget_microusd": plan.budget_microusd,
        "per_call_reservation_microusd": plan.per_call_microusd,
        "total_reservation_microusd": plan.required_microusd,
        "reservation_basis": "full_model_context_plus_output_no_cache_discount",
        "price_checked_on": PRICE_CHECKED_ON.isoformat(), "price_source": PRICE_SOURCE,
        "pricing_fresh": price_fresh, "api_key_present": key_present,
        "account_access_verified": False, "paid_calls_authorized": False,
        "execution_enabled": False, "blockers": blockers,
    }


def main() -> int:
    print(json.dumps(preflight(), sort_keys=True, indent=2))
    # A presence check must never be mistaken for live readiness by a shell caller.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
