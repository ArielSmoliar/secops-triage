# Technical case and raw-claim review, September 8

All nine synthetic cases received an unblinded AI technical review and independent AI source review. No blocking fixture relationship, time, scope or expectation defect was found. This completes the technical review selected by the owner today; it does not constitute human case acceptance or complete live evaluation M2.

Nine new local investigations used the real Strands SDK with the scripted provider, collecting 75 evidence reads. No paid model/speech calls or AWS actions occurred. Original pending reviews remain unchanged. Separate completed AI annotations and scores retain the source hash and reviewer attribution. The public [review record](../outputs/secops-technical-review-20260908.json) contains case/fixture/rubric/source bindings, raw findings, annotations, outcome dimensions and source limitations. Private source snapshots and stores remain in `data/technical-case-review-20260908`; owner capabilities are not exported.

| Case | Technical disposition | Main scope limitation | Semantic result |
|---|---|---|---|
| 01, sign-in close | Scoped VPN approval covers access | MFA and imported approval do not prove no compromise | Fail: 3 omissions |
| 02, sign-in escalation | Later mailbox forwarding is outside VPN approval | Sequence does not establish the actor or exfiltration | Fail: 3 omissions |
| 03, incomplete sign-in | Account audit unavailable | Missing audit is not a clean audit | Fail: 2 omissions |
| 04, phishing escalation | Separate second-message delivery/click and current exact URL intelligence | First-message approval does not transfer; stale domain assessment is not a contradictory exact verdict; click does not prove credential submission | Fail: 8 omissions |
| 05, phishing close | Approval covers the explicitly joined simulation events | Message authentication does not independently prove safety | Fail: 3 omissions |
| 06, incomplete phishing | Document delivery, truncated interaction results and unknown exact verdict | An event named simulation-click does not supply authorization | Fail: 3 omissions |
| 07, endpoint close | Inventory process and network/upload are explicitly covered | Approval does not cover all host activity or all PowerShell | Fail: 3 omissions |
| 08, endpoint escalation | Distinct second process/hash/network outside inventory approval | Do not transfer a hash verdict or infer impact/exfiltration | Fail: 5 omissions |
| 09, incomplete endpoint | Process seen, revoked approval and unavailable network | Revocation time is unknown; unavailable connections are not retrieved evidence | Fail: 2 omissions |

All nine raw findings contain only “Scripted fixture observed this source record.” Each cites a returned trigger. That supports the generic observation, but none expresses a required case fact or uncertainty. All **32 required items are omitted**, producing **nine failed semantic evaluations**. Model recommendation, deterministic policy and final outcome agreement are recorded separately. Correct policy output cannot fill in missing provider analysis. The failures are retained as the result of completed review, not relabeled as successful analysis.

This is reviewer-mediated scoring. Two AI reviewers saw the rubrics; it is neither a blind benchmark nor automatic semantic entailment. `reviewer_kind` is `ai` and `campaign_acceptance` is false throughout. Source authenticity, intelligence-provider truth, human usefulness and live-model reliability remain unestablished.

## Demo-first gate reconciliation

The owner's September 7 decision and September 8 scope selection permit technical review and the scripted analyst UI before human validation. Actual analyst feedback is waived as a prerequisite for this local demo; human validation follows a successful demo. M1.5 remains unperformed, rather than passed by waiver. The UI's automated actors and AI reviews are not human acceptance records.

The runtime campaign gate is unchanged: `CampaignStore.record_authority` still requires the five references `analyst_feedback`, `case_acceptance`, `price_verification`, `spending_authorization` and `build_verification`. No placeholder, waiver string or AI judgment has been recorded as human feedback/case acceptance. All historical grants remain closed. Before a paid campaign, either obtain genuine required evidence or separately and explicitly resolve the authority policy with the owner; a scheduling waiver alone does not bypass the enforced contract. Fresh clean-build/fixture/price bindings, bounded owner spending approval, per-run grants and review-gated continuation are still required. No paid campaign is authorized by this review.

The original M2/M4 plan remains historical planning evidence. M4 needs a newly selected finished-UI build and an asset-inclusive verification manifest. These local browser checks are not the three live hero rehearsals. No historical run or failed attempt was repaired, overwritten, silently retried or counted as human validation.

## Remaining release work

Separately authorized live evaluation and claim review; finished-demo rehearsals; human validation after demo success; packaging, owner-approved MIT/Apache license, architecture and public video; then owner-approved Devpost submission. The landing page remains deferred. OpenAI narration is the selected direction, maximum five minutes, with no speech generation authorized or performed.

Official [Devpost rules](https://agentsforhumans.devpost.com/rules) rechecked September 8: deadline September 14, 2026, 5pm Pacific / 8pm Eastern; public MIT/Apache repository with setup/source/assets, architecture diagram, description, AWS Builder ID and public YouTube/Vimeo video of at most five minutes are required. AgentCore and live demo URL are optional. Judge access must last through October 8. Final submission remains an owner decision.
