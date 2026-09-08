# Ohio AWS preflight — September 8, 2026

Status: account inspection completed; deployment has not been authorized or executed. This proposal adds temporary outbound connectivity to the offline host package. It does not authorize it. Private account/resource identifiers and concrete network parameters are in ignored `data/aws-preflight-20260908/`, not this public report.

## Verified target and gap

Console sign-in and CloudShell STS identify the owner's sandbox IAM user in the intended account; Ohio is selected. Operator has AdministratorAccess, IAMUserChangePassword, no inline/group policies and no user permissions boundary. This is broad existing operator access, not a least-privilege operator credential. No permissions were added. Host role remains narrowly scoped to SSM channels/registration and its operations log streams. Organization-level policies and actual creation permissions are not proven by attached policies.

The only VPC is the default VPC, with three default public subnets, enabled DNS support/hostnames, a main local/Internet Gateway route table and default allow-all network ACL. Zero NAT gateways, endpoints, EC2 instances and EBS volumes were returned. Consequently the original no-public-IP host cannot reach SSM or package services. An Internet Gateway alone does not give a private IPv4 host internet access.

The Amazon public AMI parameter resolves to `ami-01c265752adadcdf8`, Amazon owner `137112412989`, available x86_64 HVM EBS image `al2023-ami-2023.12.20260831.0-kernel-6.18-x86_64`, created August 26. AMI root is 8 GiB gp3, so the proposed encrypted 12 GiB root satisfies its minimum. Account default EBS key is alias/aws/ebs. t3.small is offered in us-east-2a; the standard On-Demand vCPU quota is 5 with zero current instances observed (capacity at launch remains unproven). Both proposed stack names were absent. This immutable ID is proposed; never silently resolve latest again. [Release notes](https://docs.aws.amazon.com/linux/al2023/release-notes/relnotes-2023.12.20260831.html) list Python 3.11.16 and later Python packages. Use the pinned AL2023 repository and install Python 3.11 plus git and the versioned uv 0.11.21 distribution, then `uv sync --frozen --extra agent --python python3.11`. Confirm package availability, uv version and source/lock hashes on the host before smoke. No package installation or SSM runtime readiness has been tested on this AMI. [AWS documents AL2023 SSM preinstallation](https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html), but running/registered state is a post-launch gate.

`SSM-SessionManagerRunShell` preferences document is absent and the account-owned Session document list is empty. The Session Manager Preferences console was also inspected: CloudWatch and S3 session logging disabled, KMS session encryption disabled, 20-minute idle timeout, no maximum-duration override and no shell profiles. These are observed preferences, not a guarantee about every organization policy; verify the actual session uses this configuration. No privacy settings were changed. During this smoke, only public setup commands and sanitized operational results may enter the terminal; never print private ownership files, provider credentials or raw stores. No account-wide session setting will be changed.

## Exact proposed resources

Two separately managed stacks, both in Ohio:

- `secops-triage-egress-20260908`, using `infra/aws/temporary-egress.json`: one private subnet (`172.31.48.0/24`, checked unused inside the existing VPC) in us-east-2a, one new route table, one new subnet association, one default route, one zonal public NAT gateway in the existing us-east-2a public subnet, and one Elastic IP for that NAT. Existing routes/subnets are unchanged. No interface endpoints, new VPC or public host address.
- `secops-triage-smoke-20260908`, using unchanged `infra/aws/private-host.json`: one t3.small (standard credits, IMDSv2), encrypted 12 GiB gp3 root and 20 GiB gp3 evidence disk with default included performance; one no-ingress/HTTPS-egress security group; one instance role/profile; one 14-day operations log group; one data-volume attachment. The new private subnet output supplies the host SubnetId. No boot execution, model permission, Parameter Store permission, provider key, public endpoint or UI.

Initial scope: at most two running EC2 hours, one empty-volume initialization after volume-ID/serial verification, one scripted case-04 smoke, one allowlisted log event, one stop/start persistence check without rerunning the smoke, then final stop. No new model/speech calls or active campaign grants. Capture actual IDs from stack outputs before any mount, stop or teardown. Do not format a device with existing signatures/evidence.

The NAT/EIP are temporary and must be removed after final stop, allowing up to three billed NAT hours including creation/cleanup rounding. The private subnet, route table and association are retained by network-stack deletion because the stopped host still depends on them. They have no hourly charge. After NAT removal, restarting the host will not restore SSM/internet access; any future egress requires a new approved deployment. Do not automatically recreate the stack against its retained subnet.

## Current Ohio costs and proposed bounds

AWS Price List API queried September 8 through authenticated CloudShell; the relevant products returned one exact usage match. Prices are USD before taxes, credits and account-specific discounts. No free tier or promotional credit is assumed.

| Item | Rate | Scope / estimated cost |
|---|---:|---:|
| Linux shared t3.small | $0.0208/hour | 2 running hours: $0.0416 |
| Zonal NAT gateway | $0.045/hour | 3 billed hours: $0.135 |
| NAT processing | $0.045/GB | Planning allowance 2 GB: $0.09 |
| One in-use or idle public IPv4 | $0.005/hour | 3 hours: $0.015 |
| Internet data out | $0.09/GB planning rate | Allow 1 GB: $0.09; verify applicable tier |
| gp3 root, 12 GiB | $0.08/GB-month | $0.96/month while retained/stopped |
| gp3 evidence, 20 GiB | $0.08/GB-month | $1.60/month, including after stack deletion |
| Standard log ingestion | $0.50/GB | One sanitized event, at most 1 MB: $0.0005 |
| Log storage | $0.03/GB-month | 1 MB: $0.00003/month before 14-day expiry |

Price SKUs: t3.small BQPEB7HYTVEZPKJW; gp3 storage M6UGCCQ3CDJQAA37; NAT hours SRB9S9CM9RDPW97X; NAT bytes G4MQY9GDKJ9HD52T; in-use IPv4 8HFJK44D9234XNWA; idle IPv4 KYJDP25537AFDVZN; standard ingestion 5T6Z6V26DSR7SZ49; log storage X7X4WD4A95NDR9U5. EC2/EBS/NAT effective September 1, IPv4 July 1, Logs August 1, 2026. Initial broader NAT/IP product-family filters returned no match; corrected exact usage queries supplied these prices.

Expected first verification operational cost about $0.38 within those transfer allowances, plus prorated disks. Retaining both disks September 8–October 9 is approximately $2.65 on a 30-day-month planning basis: approximately $3.03 total. Proposed AWS allowance: $5 before tax through October 9, subject to owner approval. This is an operational budget, not an AWS-enforced cap. No snapshots, paid detailed monitoring, new KMS key, Budgets configuration, live inference or speech generation included. [VPC pricing](https://aws.amazon.com/vpc/pricing/) confirms Ohio NAT pricing, partial-hour rounding and IPv4 fees.

Monitoring: operator records creation/start/stop times and resource IDs, checks running state and NAT byte counters during the two-hour window, begins shutdown/cleanup by 90 minutes from first NAT/EIP creation (including host-creation failure), and verifies EC2 stopped, NAT deleted and EIP released from the control plane. Basic EC2/NAT metrics and manual inventory are the monitoring method; Cost Explorer was not enabled in the console and is not being silently enabled. Billing is delayed, metrics/alerts do not impose a hard cap, and incidental overrun must be reported, not hidden. No unattended deployment or automatic evidence deletion.

## Retention and teardown

Proposed retention owner: Ariel Smoliar. Review date: October 9, after October 8 judging end. Keep encrypted evidence and local sanitized CloudWatch receipt; 14-day CloudWatch event expiry does not erase the local receipt. Evidence disk has Retain on deletion/replacement. Logs group is retained; old events expire after 14 days. No historical local data/grants are uploaded or changed.

Normal end of first verification: stop exact host and verify stopped; delete the egress stack (default route, NAT and EIP removed; private subnet/route table/association retained); verify the private default route absent, NAT deleted and allocation released. Record retained subnet/association/table, host/root/data disk and log group IDs. Continuing cost: $2.56/month for both disks plus remaining log bytes. Forgetting NAT/EIP would add about $36.50 per 730-hour month before traffic; stopping EC2 alone is insufficient.

Later owner-approved host-stack deletion removes instance/root disk/role/profile/security group/attachment, retains data disk and log group. It reduces disk cost to $1.60/month. After the host ENI is gone, remove the retained network association, route table and subnet by their verified IDs under the same later teardown approval. Deleting evidence/logs requires a separate explicit retention decision; October 9 is a review date, not automatic deletion authority. A restored snapshot is historical inspection only and cannot restore spending grants.

Failure containment: stop EC2 through the control plane even if SSM is broken; preserve failed smoke slot/store; delete the exact approved egress stack on failure/window expiry after recording identities, even if host creation never succeeds. Retain may also orphan the three network resources during a failed initial creation; preserve their IDs and resolve collisions before any newly approved retry. Never rerun smoke to hide failure or widen IAM/SSH/network exposure to recover access.

## Validation and unresolved gates

Startup at d5e3307: pinned offline sync checked 47 packages. The first sandboxed suite failed because loopback HTTP binds were denied; preserved in `/private/tmp/secops-startup-20260908-qz6t3xdb`. Unrestricted rerun passed 295 tests in 67.312s with all saved runtime/test/template/metadata hashes unchanged, and probe reproduced 403/200/403. Evidence: `/private/tmp/secops-startup-unrestricted-qebcy7lr`. New local scripted smoke completed nine reads with zero paid calls; `/private/tmp/secops-startup-smoke-1zgn4q0v`. These are local results, not cloud verification.

Independent AI review found no CloudFormation dependency blocker. Scope/retention/restart/failure-cost clarifications were applied, including explicit retained association output. The network template contains six resources. cfn-lint 1.56.0 passed alongside the unchanged host template; final focused structure and frozen-source checks are recorded in outputs/secops-aws-preflight-validation.json. CloudFormation validated both exact templates from clean GitHub commit b5bf97d3d73dae3668860e4d495a72321a719139. Host declares CAPABILITY_IAM. Network change set review-b5bf97d is CREATE_COMPLETE / AVAILABLE and contains exactly six Add actions, no replacements, with verified private target parameters; its stack is REVIEW_IN_PROGRESS. Only review metadata exists: no change set was executed and no EC2/EBS/NAT/EIP resources were provisioned. Final concrete owner deployment approval remains. The network change set is reviewed but unexecuted; the host change set must be bound to the actual new subnet output after approved network creation, then checked for the exact seven host resources before execution. No placeholder subnet is an execution target. This document is not an execution grant.

Rules rechecked September 8: September 14, 2026 at 8pm Eastern deadline; public MIT/Apache repository with setup/assets, architecture diagram, public YouTube/Vimeo video at most five minutes and AWS Builder ID; judge access through October 8. AgentCore and live URL are optional. [Official rules](https://agentsforhumans.devpost.com/rules). No terms accepted or submission sent.

Implementation/template source: b5bf97d3d73dae3668860e4d495a72321a719139. Network SHA-256: 5ae7f478ce07e0c8d76920d4736e714b0a4d8c1d49a3fdf301146504b7cf9fc5. Host SHA-256: 7b19070e66f0544b9b3ecfa10388316f5fd007d6c1e81c8f941f873e433fe889. Final frozen suite: 295 passed in 66.713 seconds. Later documentation-only commits do not change these template bytes.
