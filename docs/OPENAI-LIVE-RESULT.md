# First completed live OpenAI investigation — 2026-09-07

The owner authorized a replacement attempt with at most seven requests and a $3.00 ceiling. It ran once from clean `main` at `5cef71a706919896c4c662a1471190989aae0228`, using the configured OpenAI key and pinned `gpt-4.1-mini-2025-04-14` snapshot. This result used real model responses, the real Strands SDK, actual localhost fixtures, and the deterministic store. It was not the scripted provider.

## Executed behavior

Run `bd53e4dc525e4f46884ee61039ac7409` completed six model calls and five tool calls:

1. `inspect_candidate`: fixture healthy; initial manifest verified.
2. `run_baseline_tests`: the two original baseline tests passed.
3. `compare_tenant_boundary`: three consistent trials found original HTTP 403 versus faulty candidate HTTP 200, exposing synthetic field names `id`, `tenant`, and `title`.
4. `apply_safe_patch`: added exactly the allowlisted regression test, creating a new candidate digest.
5. `run_baseline_tests`: executed three tests; the new regression failed as expected against the faulty application, with one failure and no errors.

The model then returned a blocked recommendation with the reason code `regression_test_added`. It did not change application logic. The backend produced a **not-ready** packet and retained state `blocked`. There are zero candidate approvals and zero promotions.

This proves that the live model selected all four scoped tools, detected the hidden boundary regression, added and executed the constrained test, and stopped within its authority. It does not prove a successful application repair or readiness for promotion.

After the patch, the model reran the baseline suite and stopped on the regression failure; it did not rerun inspection or the boundary probe for the new digest. The packet correctly lists those missing current-digest checks along with the failed baseline. Earlier evidence was retained for history and did not satisfy current gates. Its short explanation mentions the added test but does not explicitly enumerate every unresolved condition; the deterministic packet supplies that detail.

## Usage and integrity

- All six requests returned valid usage metadata: 8,041 input tokens and 492 output tokens.
- Conservative per-request rounded usage estimate: **$0.004005** at the recorded uncached text rates. This is an estimate, not an invoice amount.
- Replacement reservation total: **$2.533848**. Reservations remain preserved rather than refunded after cheaper actual usage.
- Prior failed attempt's uncertain reservation: **$0.422308**; no retrospective zero-charge assumption was made.
- Combined reserved exposure: **$2.956156**, below the original $3.50 envelope.
- The replacement grant is closed. No seventh request or automatic follow-up was made.
- All five evidence blobs passed SHA-256 verification; the current bundle and packet/assessment references passed integrity checks.

The redacted report, per-request accounting, evidence checks, tool sequence, and packet are committed in `outputs/openai-live-validation.json`. Full local records remain in Git-ignored `data/openai-replacement-authorized-20260907/`, with the owner capability protected separately. The API key is not in published artifacts, model-visible context, or run evidence.

## Remaining work

This is one successful live investigation of the faulty candidate, not a reliability evaluation. The corrected-candidate live path, repeatability, richer explanation coverage, and evaluation across failure cases remain unverified. The present spending grant implementation deliberately accepts only a fresh faulty candidate; a corrected-candidate evaluation requires a reviewed scope change and separate paid-call authorization.

The existing 110-test suite and TLS verification passed for the execution commit before this run. This follow-up changes only documentation and redacted evidence. No UI, AWS resources, AgentCore, candidate promotion, or submission work was performed.

The corrected scope and migration have since been implemented and tested without paid calls; see `docs/CORRECTED-EVALUATION.md`. This live faulty-candidate evidence is unchanged.
