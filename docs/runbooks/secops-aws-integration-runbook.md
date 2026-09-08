# SecOps Triage: Ohio AWS integration

## September 8 preflight amendment — proposed, not deployed

Read [the concrete Ohio preflight proposal](../SECOPS-AWS-PREFLIGHT-20260908.md). Signed-in read-only verification found no NAT/endpoints in the existing VPC. The original host-only package cannot reach SSM with that network. A separately reviewed `infra/aws/temporary-egress.json` now proposes six additional resources: a private subnet, route table, association, default route, NAT gateway and Elastic IP.

This amendment proposes expanding the older network exclusion below; it grants no creation authority.

The final proposal controls account-specific scope, current prices, two-hour compute/three-billed-hour NAT bounds from first network creation, and failure teardown. Network-stack deletion retains subnet/table/association for the stopped host, removes its default route/NAT/EIP, and leaves the host without outbound connectivity. Capture every retained ID before deletion, independently verify route removal/NAT deletion/EIP release, and never blindly recreate the same CIDR. Retained evidence deletion and future network restoration need their own owner decisions. No cloud resources have been deployed.

## Metadata

- **Status:** Draft — offline package implemented; deployment not executed or authorized.
- **Owner:** Ariel Smoliar.
- **Operator:** Codex with Ariel's AWS identity and concrete resource approval.
- **Last verified:** 2026-09-07, local checks only.
- **Environment:** Proposed private EC2 host in Ohio (`us-east-2`); repository `/Users/arielsmoliar/Developer/migration-proof`, main.
- **Expected duration:** First deployment estimate 1–2 hours after access/network selection; initial compute window proposed at two hours. Not a cost cap or approval.
- **Change/incident ID:** SECOPS-AWS-INTEGRATION.

## Objective

Run the existing scripted Strands phishing investigation on AWS, preserve evidence through host stop/start, and verify a sanitized operational event in CloudWatch. This establishes AWS hosting and operations integration; it does not establish Bedrock inference, live AWS security-data ingestion or AgentCore deployment.

The owner selected AWS integration as the active goal and Ohio as the region. This supersedes older instructions to defer all AWS preparation until after the UI. All historical paid model grants remain closed. Analyst feedback is waived; human case acceptance remains pending.

## Scope

**Included**

- `infra/aws/private-host.json`: one t3.small instance with standard CPU credits, 12 GiB encrypted root disk, separate 20 GiB encrypted gp3 data volume, private networking, an IAM role/profile, security group and 14-day operations log group.
- Data volume and log group retained on stack deletion/replacement. Single host, single attached local ext4/XFS data filesystem. SSM-only administration with minimal channel permissions; no Parameter Store reads.
- `ops/aws_smoke.py`: one-shot scripted case-04 smoke, exact filesystem UUID check, private storage, durable slot reservation and sanitized result. No AWS SDK calls or model credentials.

**Excluded**

- Public IP, inbound ports, public endpoint, UI, new NAT/endpoints/VPC, automatic installation or boot dispatch, live model grants, Bedrock, AgentCore, security-data connectors and source-system writes.
- Automated backup restore or campaign dispatch from snapshots.

**Must remain unchanged**

- Historical local stores, grants, secrets and evidence; no upload of `.env`, `owner.json`, raw reports or private data to GitHub/CloudWatch.
- Host-only authority and single designated campaign store. The infrastructure smoke has its own fresh private store; it is not a live campaign slot or semantic acceptance result.

## Preconditions

- AWS CLI exists locally, but profile listing is empty and STS reports no credentials. No AWS account, AMI, VPC, subnet or resource identity is verified. Authentication method is requested from the owner; never request access keys in chat.
- Verify signed-in account and Ohio region, subnet/VPC relationship, route/DNS access to SSM, SSM Messages, CloudWatch and approved package sources. Existing NAT/endpoints may have costs; the template does not create them or guarantee connectivity.
- Select an Amazon-owned AL2023 x86_64 AMI with current SSM Agent; resolve its immutable ID. Verify Python 3.11+ and pinned uv 0.11.21 installation procedure against that AMI before installation. Do not substitute a moving AMI/dependency without recording it.
- Prepare exact clean full Git commit and template SHA-256, account-specific parameters, current Ohio prices, an initial two-hour compute window, storage/log retention cost, stop/teardown identities and owner approval before provisioning. The template alone is not a deploy-ready change set.
- Retained 20 GiB EBS and retained logs continue to incur charges after instance/stack deletion. An AWS Budget alert is not a hard spending cap. No current dollar ceiling is approved; quote compute, both disks, logs, network and any snapshots before requesting approval.

## Risk and stop conditions

- **Risk:** Lost mounts can silently redirect a store to the root disk. Smoke requires the exact mounted UUID, local filesystem type, writable mount and mode 0700; it refuses fallback.
- **Risk:** A restored snapshot can resurrect consumed grants. Restores are isolated historical inspection copies, never a source of renewed paid authority.
- **Risk:** General-purpose SSM shell access is host administration. Only the approved operator receives access; it is not an agent tool. Account-enforced session logging must be checked before entering any private content.
- **Stop immediately if:** target/UUID differs, source changes, secret exposure, unexpected permissions, missing accounting, false completed result, unapproved resource replacement or unexplained cost occurs. Do not repeatedly execute a smoke to get a success.

## Evidence plan

- Record exact build, template digest, AMI identity, region, approved resource scope, smoke mode/run/packet IDs, retained disk identity, stop/start persistence, CloudWatch delivery and final stopped/deleted resource status.
- Store private resource/account details locally under ignored data; commit only sanitized verification summaries under outputs.
- CloudWatch receives only reviewed `result.json` fields: schema, slot, state, execution, mode, case, run/packet identifiers, read count, paid-call count and review/SIEM status. No stdout aggregation, tracing SDK, source text, owner capabilities or raw exceptions.
- Missing result after abrupt termination means interrupted/unknown smoke, never success. Preserve started record/store; do not reissue the same slot or label a new slot as recovery.

## Procedure

### Phase 1 — Prepare and verify locally

1. **Action (read-only/local verification):** Inspect the template and run focused tests from the repository with pinned `.venv`.
   - **Expected result:** Infrastructure lint and mount/retry/retention tests pass.
   - **Verify:** `.venv/bin/python -m unittest discover -s tests -p test_aws_smoke.py -v`; lint with the recorded isolated cfn-lint version. Full suite is required on frozen source before shipping.
   - **If verification fails:** Repair locally; no AWS creation.
   - **Approval required:** None; current authorized preparation.

2. **Action (local reversible):** Run `.venv/bin/python -m ops.aws_smoke --root /private/tmp/CHOSEN-PRIVATE-ROOT --slot smoke-01 --local-check` only after creating a fresh real 0700 directory and replacing the example root.
   - **Expected result:** Nine reads, escalate/needs_review, result mode local-check. No cloud claim follows.
   - **Verify:** Result exists, private owner file is 0600, no credentials are output. Reusing the slot must refuse execution. Keep failure artifacts.
   - **If verification fails:** Diagnose the preserved attempt; do not silently retry.
   - **Approval required:** None; scripted provider only.

### Phase 2 — Resolve and approve the actual cloud target

3. **Action (read-only):** After sign-in, verify account via STS, select Ohio network/AMI, inspect session logging and deployment permissions, and use CloudFormation validation/change-set inspection to review exact resources.
   - **Expected result:** A concrete parameter file and price-checked resource proposal with no unexpected replacements or network creation. No automatic execution of change sets.
   - **Verify:** Region us-east-2, AMI architecture/owner, subnet VPC/AZ, SSM outbound path, IAM restricted to channels and the named log group; template has no ingress/model/data-read permission.
   - **If verification fails:** Resolve the specific prerequisite. Do not create NAT/endpoints, broaden IAM or expose SSH as an improvised fix.
   - **Approval required:** Fresh approval for exact provisioning and costs, after this proposal is complete. Saved closed inference grants authorize nothing here.

### Phase 3 — Provision, mount and run once

4. **Action (external change):** Execute only the approved stack creation. Record HostId, DataVolumeId and OperationsLogGroup outputs. Open an authorized SSM session.
   - **Expected result:** One reachable private host, no inbound listener exposed, encrypted single-attached data volume in the same AZ.
   - **Verify:** EC2/SSM describe results and stack outputs agree; root/data volume IDs and encryption confirmed. Check actual security group and IAM policy, not only template text.
   - **If verification fails:** Stop the host, preserve stack events and disk identities; no repeated provisioning.
   - **Approval required:** Concrete phase-2 resource approval.

5. **Action (external change; disk formatting is destructive):** Resolve the attached data device by exact EBS volume identity, distinguish it from the root disk, inspect for existing signatures, and prepare an ext4/XFS mount at `/mnt/secops` with a dedicated operator-owned 0700 directory. Persist the verified filesystem UUID in mount configuration. Install the pinned source/dependencies in a clean checkout.
   - **Expected result:** Complete store resides on the data disk; clean full commit and frozen uv.lock; no historical stores or provider credentials copied.
   - **Verify:** Device serial matches approved DataVolumeId; `findmnt` reports `/mnt/secops`, expected UUID, ext4/XFS and rw; source commit and lockfile digest match. No bootstrap/boot service executes an investigation.
   - **If verification fails:** Stop before writing any store. Never format a device with evidence; preserve it and reassess.
   - **Approval required:** Resource scope must explicitly include initialization of that new empty volume. Exact commands are produced only after the actual device and AMI are inspected; no guessed `/dev/nvme*` formatting command is supplied here.

6. **Action (external scripted execution):** From the verified checkout, run `.venv/bin/python -m ops.aws_smoke --root /mnt/secops --slot smoke-01 --expected-uuid VERIFIED-UUID`, substituting the independently checked UUID. This is manual, one-shot execution; no startup hook or retry policy.
   - **Expected result:** Immutable started/result files and local evidence; nine reads, escalate/needs_review, scripted-strands execution. The aws-host-candidate label requires independent EC2 evidence to establish cloud execution.
   - **Verify:** Read the sanitized result; inspect cited packet privately. A correct policy outcome is not a semantic model review. No paid calls or source writes.
   - **If verification fails:** Preserve the slot. Abrupt termination may leave only started.json; no rerun of that slot. Existing recovery tools may inspect/reconcile the private store after process exit without dispatch.
   - **Approval required:** Included only in the concrete scripted deployment scope; no paid model authority.

### Phase 4 — Verify observability and persistence, then stop

7. **Action (external change):** Publish one allowlisted operational event from result.json to the exact stack log group using a manually reviewed CloudWatch Logs request. Do not configure broad directory/stdout collection.
   - **Expected result:** Exactly the reviewed event is visible, with no source text or capability.
   - **Verify:** Retrieve it with the operator identity and compare its allowed fields to local result. The host role can write only that log group's streams.
   - **If verification fails:** Preserve the local result and report delivery failure; do not broaden logging or rerun investigation.
   - **Approval required:** Included in approved resource/log scope.

8. **Action (external reversible):** With no worker running, record private artifact hashes, stop then start the exact host, remount the original data volume and verify the same UUID/files/hashes. Do not invoke smoke again. Finally stop the host within the approved compute window.
   - **Expected result:** Evidence survives unchanged and no automatic execution occurs. Final instance state is stopped.
   - **Verify:** EC2 instance status, original volume attachment, mount identity and file hashes; no additional started slot/result appears. Confirm continued EBS/log charges and their retention owner/date.
   - **If verification fails:** Preserve all volumes, stop dispatch, report persistence failure without repairing historical hashes.
   - **Approval required:** Included in the concrete deployment/restart/stop scope.

## Rollback

- **Trigger:** Any verification failure, expired compute window or unexpected billing.
- **Decision owner:** Ariel owns resource retention and spending; Codex contains execution.
- **Actions:** Stop new work and stop the recorded EC2 instance through the AWS control plane, independent of SSM/app health. Verify stopped state. Keep the exact data volume and evidence. Do not restore snapshots as active campaigns.
- **Verification:** No running instance/worker, data volume retained/encrypted, original slot bytes unchanged, no new grant issued.
- **Limitations:** Stop does not stop EBS/log/network charges. Stack deletion removes the host/root disk but intentionally retains data/logs. Before deletion, unmount safely if possible and verify retained data-volume identity; deletion or formatting of retained evidence requires a separate retention decision. No automated teardown is supplied before real resource IDs exist.

## Completion criteria

- [ ] Exact Ohio account/resources/build verified and authorized.
- [ ] Scripted Strands case-04 executes once on the private AWS host.
- [ ] Allowlisted CloudWatch event is retrieved and verified.
- [ ] Original evidence survives stop/start, mount failures refuse execution, no automatic retry occurs.
- [ ] Host stopped and continuing storage/log costs explicitly tracked.
- [ ] Claims say AWS-hosted scripted demo; Bedrock, AgentCore and live security ingestion remain unimplemented.

## Communications

- **Start:** State exact approved target, scope, build and compute window in this task.
- **Failure:** Report stage and retained evidence without private output; no external messages.
- **Completion:** Report actual cloud evidence separately from local checks, resource stopped state and remaining costs.

## Record

- **Started:** 2026-09-07.
- **Completed:** Offline preparation only; cloud execution pending access and concrete authorization.
- **Operator:** Codex.
- **Approvals:** AWS integration goal and Ohio region selected; no provisioning or inference approval yet.
- **Outcome:** CloudFormation package and scripted smoke helper prepared. Local AWS CLI has no credentials.
- **Deviations:** AgentCore deferred as an architectural choice, not assumed incapable of persistence. AWS now documents persistent session storage and Instances capacity-provider EBS; its lifecycle/authority semantics need separate validation.
- **Follow-up:** Resolve authentication, actual network/AMI and price/resource proposal; then seek final provisioning approval.
- **Next verification:** After any source/template/target change and before cloud execution.

## Sources and architecture rationale

The single-host choice preserves existing SQLite, POSIX locks and local process supervision. [AWS EBS retention](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-volume.html) and [SSM networking](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html) establish the relevant resource constraints. Minimal role permissions follow [AWS's custom Session Manager role](https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-create-iam-instance-profile.html). [AgentCore filesystem documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-filesystem-configurations.html) describes persistent options; persistence alone does not verify this application's cross-run authority or recovery behavior.

## External Claude review clarifications — 2026-09-07

Read docs/SECOPS-CLAUDE-ENG-REVIEW.md for the adjudicated findings; do not execute suggestions from the raw review. These clarify the existing gates and do not authorize deployment.

- Before initialization, use read-only `lsblk -o +SERIAL` on the actual Linux host to match the data disk's serial to the approved EBS volume ID, accounting for the displayed volume-ID format. Confirm root-disk identity independently; use the AMI's ebsnvme-id tool if available. Never assume /dev/sdf is a stable guest path or infer role from an nvme index. Record verified volume ID and filesystem UUID. See https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html .
- After account access, inspect Session Manager preferences with the operator's `aws ssm get-document --region us-east-2 --name SSM-SessionManagerRunShell --document-format JSON`; inspect a custom document instead if that is the selected session configuration. A missing default document does not prove no logging. Check actual session document, destinations, encryption, permissions and applicable account policy. Keep private settings out of public artifacts. Do not change account-wide logging settings or enter credentials during this check. See https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-create-preferences-cli.html .
- Before provisioning, verify selected subnet routes, VPC DNS, NACLs and HTTPS egress. Where private endpoints are used, verify ssm, ssmmessages and logs endpoint private DNS and endpoint security-group access from this host group. Verify approved package-source reachability separately; an S3 endpoint alone does not establish PyPI/GitHub access. After provisioning, successful SSM session establishment and one reviewed CloudWatch event are live checks, not substitutes for preflight. No guessed endpoint/NAT deployment.
- The concrete approval proposal must include monitoring method, named retention owner, retained resource IDs when created, review date and continuing storage/log/network estimates. Monitoring does not impose a hard cap. Keep standard CPU credits; verify actual performance rather than enabling unlimited credit charges. No automatic evidence deletion.
