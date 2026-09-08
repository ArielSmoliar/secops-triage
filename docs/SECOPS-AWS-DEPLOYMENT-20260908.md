# SecOps Triage AWS deployment verification — September 8, 2026

The approved Ohio infrastructure integration succeeded. One private EC2 host ran the real Strands Agents SDK with a **scripted provider and synthetic data**, collected nine reads through all four scoped tools, and produced a cited assessment. One allowlisted event was verified in CloudWatch. All 21 saved evidence/verification files survived a real EC2 stop/start unchanged. The host is now stopped; temporary NAT, Elastic IP and default route are removed.

This is an AWS-hosted scripted infrastructure demo. The analyst UI, live evaluation, human validation and narrated end-to-end video remain unfinished. Bedrock, AgentCore and live AWS security-data connectors are not deployed.

## Authorization and build

The owner replied **approved** to the exact [preflight proposal](SECOPS-AWS-PREFLIGHT-20260908.md) at commit `4761d75d4843630c98b8aba85035f263505e04b6`. Approval included the specified host/network resources, new-empty-disk initialization, one scripted smoke, one reviewed CloudWatch event, stop/start verification, final stop, and temporary egress cleanup within the $5 pre-tax planning allowance. It did not authorize paid model/speech calls, campaign dispatch or deletion of retained evidence.

Both CloudFormation change sets were inspected before execution. The host change set used the actual newly created private subnet. Deployed source was clean commit `b5bf97d3d73dae3668860e4d495a72321a719139`, with exact template, smoke helper and uv.lock hashes in [the validation record](../outputs/secops-aws-deployment-validation.json). Python 3.11.16 came from pinned AL2023 release 2023.12.20260831. uv 0.11.21 installed 47 frozen packages including Strands Agents SDK 1.54.0. No source or dependency lock changed during deployment.

## Observed execution

| Component | Verified behavior |
| --- | --- |
| Strands SDK | Actual orchestration and tool hooks; ten scripted provider responses |
| Model/provider | Scripted fixture, zero paid calls; no live model inference |
| Scoped investigation tools | inspect_incident ×1, lookup_entity ×2, query_activity ×5, find_related_cases ×1 |
| Evidence and assessment | Nine recorded reads, cited source record, 36 report evidence links; escalate / needs_review |
| Host controls | Scoped tools, private local storage, one-shot reservation, exact-mount checks and unchanged SIEM status |
| AWS services used | EC2, encrypted EBS, IAM instance role/profile, SSM sessions, CloudWatch Logs, CloudFormation and temporary VPC egress |

The new 20 GiB disk's guest serial matched its AWS volume ID, independently distinguished from the 12 GiB root. Its lack of signatures/partitions/mounts was checked before formatting. ext4 was mounted at /mnt/secops by UUID with mode 0700; the owner capability file remained 0600. AWS describe calls verified no public IP, zero ingress, HTTPS-only egress, IMDSv2, standard CPU credits, both disks encrypted, and the actual narrow role policies. The host role has no model or Parameter Store read authority. Inspected Session Manager preferences had CloudWatch/S3 session logging disabled; no account settings changed.

`smoke-01` was dispatched once. The original `aws-host-candidate` result was preserved; independent EC2, guest, SSM and CloudWatch observations establish AWS execution. The scripted provider's cited finding is not semantic quality acceptance. Human acceptance remains false/pending.

CloudWatch received only the reviewed result schema. Operator readback found exactly one event with SHA-256 `d856b6576fde203e0c9d04c245cfc0869e44844a6646e83983dc187a8ad972c1`, matching the local result bytes. No raw reports, source evidence, stdout stream or owner capability were sent to CloudWatch/GitHub.

## Persistence and final state

Before stopping, the worker had exited and the source was clean. A private baseline covered 21 files, including the SQLite store, evidence blobs, packet, report, capability file and CloudWatch intent/receipt. Baseline SHA-256: `d8bb0e1c79976d9fb7db3e0ae11c9ac2425e8336696ee7e2a216ac01c0a4f30b`.

After a control-plane-confirmed stop and restart, fstab automatically remounted the original UUID. The original EBS serial, exact file set and every hash matched. Only the original started slot existed; no worker or new investigation appeared. Wrong-UUID and absent-mount guards were also checked without dispatching a smoke.

| UTC, September 8 | Observation |
| --- | --- |
| 11:14:57 | First network execution dispatched; cost/cleanup clock began |
| 11:18:35 | Reviewed host creation dispatched |
| 11:51:17 | Exact CloudWatch readback; first stop requested |
| 11:51:41 | Stopped state verified; approved restart requested |
| 11:53:08 | Persistence comparison passed |
| 11:53:33 | Final stop and temporary egress deletion requested |
| 11:55:14 | Final independent AWS state checks passed |

Final checks verified EC2 stopped, network stack DELETE_COMPLETE, NAT deleted, Elastic IP absent, and no default route. Subnet, route table and association remained present and were recorded as DELETE_SKIPPED. Both encrypted volumes remain attached to the stopped host, and the log group retains its 14-day policy. No host-stack or evidence deletion occurred.

The retained network resources are outside the deleted stack. Their exact identities are saved privately; do not blindly recreate the same subnet CIDR or delete the host stack. Restarting this host without a separately approved egress restoration will not restore SSM connectivity. This is not a continuously running or publicly accessible demo.

## Costs and retention

Cleanup began about 39 minutes after the first network dispatch, before the 90-minute deadline. The entire host creation-to-final-verification interval was under 37 minutes, conservatively below the two-hour compute allowance; the network interval was under one hour, below three billed NAT hours. Observed NAT input totals were 1,238,997 bytes from the source and 169,728,805 bytes from the destination. These metrics can lag and are not a final invoice.

The approved $5 allowance is a planning limit, not an AWS-enforced cap. Retained 32 GiB gp3 storage continues at approximately **$2.56/month**; retained log storage uses the price checked in the proposal ($0.03/GB-month, plus any applicable charges). Stopped EC2 and deleted NAT/EIP no longer accrue their running hourly charges. The retained subnet/table/association have no hourly charge. Billing has not settled or been asserted as a final exact amount.

**Retention owner: Ariel Smoliar. Review date: October 9, 2026.** No automatic evidence deletion, snapshots, new paid calls or scheduled restart were configured. A later retention/restart decision requires its own authority.

## Verification deviations and next work

The first browser terminal display became stale during package installation. A separate SSM session, installed RPMs and dnf records established that installation had completed at 11:24:02; packages were not reinstalled. A read-only baseline verifier initially expected session state `completed`; source inspection showed the successful internal state is `assessed`. The verifier was corrected; no application source, evidence or smoke dispatch changed. Both observations are preserved in the private record and sanitized validation.

The pre-deployment frozen 295-test suite passed in 66.713 seconds, with cfn-lint and independent template review. Runtime source remained unchanged throughout the AWS checks. Documentation-only recording does not claim a new full-suite run. Independent review of this completion record is recorded in the validation JSON before commit.

Next: technical case/claim review and a separately authorized live evaluation, analyst UI exposing actual Strands calls/evidence/citations, rehearsals, license/architecture/packaging and the maximum-five-minute OpenAI-voice video. No new model or speech calls are authorized. Demo first; human validation follows success, pre-demo analyst feedback is waived, and campaign authority checks remain enforced. Landing page remains deferred. Rules were rechecked September 8: September 14 at 8pm Eastern, public video at most five minutes, public MIT/Apache repository, architecture, Builder ID and judge access through October 8. Recheck before owner-approved submission.
