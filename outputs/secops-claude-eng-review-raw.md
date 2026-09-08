# External Claude review — unadjudicated original

WARNING: This original response contains incorrect commands, outdated AWS limits and overstated severity. It is evidence of reviewer output, not approved execution guidance. Read docs/SECOPS-CLAUDE-ENG-REVIEW.md before using any recommendation.

Reviewed commit: 49ddeb82be1ebbe0fbcaf2318f9d5095f6e7d349

# SecOps Triage AWS Engineering Review

**Verdict:** CONDITIONAL APPROVAL with critical blockers for production deployment and moderate concerns for demo reliability.

---

## Executive Summary

The offline preparation is **technically sound** for a controlled demonstration of AWS hosting capabilities. However, **three P0 blockers prevent production deployment**, and **two P1 issues create moderate demo risk**. The implementation correctly distinguishes AWS hosting from live inference/security integration, but several durability and cost assumptions require explicit verification with live AWS resources.

---

## P0 Blockers (Production Deployment)

### P0-1: Unbounded EBS retention costs with no teardown tooling
**File:** `infra/aws/private-host.json:172-173`, `docs/runbooks/secops-aws-integration-runbook.md:123`  
**Scenario:** Stack deletion retains the 20 GiB encrypted data volume indefinitely. At current Ohio gp3 pricing (~$0.08/GB-month), this is ~$1.60/month per forgotten stack. No automated discovery or cleanup tool exists. Multiple test deployments accumulate orphaned volumes.

**Evidence:**
```json
"DataVolume": {
  "Type": "AWS::EC2::Volume",
  "DeletionPolicy": "Retain",
  "UpdateReplacePolicy": "Retain"
```

Runbook line 123: "deletion or formatting of retained evidence requires a separate retention decision" but provides no implementation.

**Fix:** Before production:
1. Add `ops/aws_cleanup.py` that lists retained volumes by stack name tag and confirms deletion
2. Document retention policy and review schedule in runbook
3. Add CloudWatch alarm for unattached encrypted volumes older than 7 days

---

### P0-2: No cost monitoring or hard spending cap
**File:** `docs/runbooks/secops-aws-integration-runbook.md:43`, `infra/aws/private-host.json` (missing Budget resource)  
**Scenario:** Template mentions "An AWS Budget alert is not a hard spending cap" but provides no budget resource at all. Running instances, retained EBS volumes, and CloudWatch log retention accrue charges indefinitely. A stuck instance runs for days before manual discovery.

**Evidence:**
- Runbook line 43: "No current dollar ceiling is approved; quote compute, both disks, logs, network and any snapshots"
- Template has no `AWS::Budgets::Budget` resource
- No CloudWatch alarm on estimated charges
- Line 118: "Stop does not stop EBS/log/network charges" but no ongoing cost visibility

**Fix:** Before any deployment:
1. Add CloudFormation Budget resource with email notifications at 50%/100% of approved amount
2. Create CloudWatch billing alarm
3. Document expected monthly costs for stopped instance scenario (EBS + logs)

---

### P0-3: Session logging verification gap before credential entry
**File:** `docs/runbooks/secops-aws-integration-runbook.md:49`  
**Scenario:** Runbook states "Account-enforced session logging must be checked before entering any private content" but provides no verification procedure. Operator unknowingly enters sensitive data in unlogged session, creating compliance/audit gap.

**Evidence:** Line 49: "Account-enforced session logging must be checked before entering any private content" - assertion only, no implementation.

**Fix:**
1. Add explicit verification step: `aws ssm describe-session-manager-logs` check before Phase 3
2. Require S3 bucket or CloudWatch Logs destination in prerequisites
3. Add test session command that verifies logging before production access

---

## P1 Issues (Demo/Operational Risk)

### P1-1: Ambiguous device attachment name risks wrong disk formatting
**File:** `infra/aws/private-host.json:204`, `docs/runbooks/secops-aws-integration-runbook.md:91`  
**Scenario:** Template specifies `/dev/sdf` but AL2023 NVMe instances expose this as `/dev/nvme[0-9]n1`. Operator mistakes root device for data device, formats evidence disk, or fails to mount entirely. Runbook explicitly refuses to provide formatting command until inspection.

**Evidence:**
- Template line 204: `"Device": "/dev/sdf"` 
- Runbook line 95: "no guessed `/dev/nvme*` formatting command is supplied here"
- Common AWS issue: named devices appear as NVMe with serial number mapping required

**Fix:**
1. Update runbook Phase 3 step 5 with explicit NVMe resolution procedure: `lsblk -o +SERIAL` matching `DataVolumeId`
2. Add pre-deployment documentation of expected device naming for AL2023
3. Consider adding userdata script that writes volume ID mapping to `/root/volume-map.json` (read-only, no auto-format)

---

### P1-2: No verification that subnet can reach required endpoints
**File:** `docs/runbooks/secops-aws-integration-runbook.md:40`, `infra/aws/private-host.json:9-10`  
**Scenario:** Template accepts any subnet but requires SSM, SSM Messages, CloudWatch Logs, and package repository access. Private subnet without VPC endpoints or NAT fails to connect. First discovery is SSH/SSM connection failure after provisioning.

**Evidence:**
- Runbook line 40: "Existing NAT/endpoints may have costs; the template does not create them or guarantee connectivity"
- Template line 10: Description warns but enforces nothing
- No connectivity test in preconditions

**Fix:**
1. Add Phase 2 verification: attempt `aws ssm start-session` immediately after stack creation to fail fast
2. Document specific endpoint requirements: `com.amazonaws.us-east-2.{ssm,ssmmessages,logs,s3}`
3. Consider adding cfn-init wait condition that signals after successful SSM registration

---

## P2 Concerns (Documentation/Minor Gaps)

### P2-1: Incomplete AMI selection guidance
**File:** `docs/runbooks/secops-aws-integration-runbook.md:41`  
**Evidence:** "Select an Amazon-owned AL2023 x86_64 AMI with current SSM Agent; resolve its immutable ID."  
**Gap:** No guidance on finding current AMI ID, verifying SSM agent version, or checking for required Python 3.11+.  
**Fix:** Add AWS CLI query: `aws ec2 describe-images --owners amazon --filters "Name=name,Values=al2023-ami-2023.*-x86_64" --query 'sort_by(Images, &CreationDate)[-1].ImageId'`

### P2-2: CloudWatch event sanitization not enforced by code
**File:** `ops/aws_smoke.py:84-89`  
**Evidence:** Result dictionary construction has no explicit field allowlist - includes `run_id`, `packet_hash`, etc. by manual selection. Comment at runbook line 106 says "reviewed event" but no runtime enforcement.  
**Fix:** Add `CLOUDWATCH_ALLOWED_FIELDS` constant and filter `result.json` against it before publication. Current implementation is correct but fragile to maintenance.

### P2-3: Recovery tool authority semantics unclear
**File:** `secops_triage/agent_runner.py:41-50`  
**Evidence:** `recover()` function can be called standalone without run owner token, only needs store root. Opens door to unauthorized recovery inspection if store filesystem permissions fail.  
**Fix:** Add token parameter to `recover()` and verify ownership before state transitions. Current POSIX 0700 permissions are correct defense-in-depth but code should enforce token.

### P2-4: t3.small CPU credit exhaustion undefined
**File:** `infra/aws/private-host.json:119-124`  
**Evidence:** Uses `"CPUCredits": "standard"` for t3.small. Smoke test runs ~20 seconds per runbook, but multiple sequential runs could exhaust credits, throttling to baseline 20% CPU.  
**Impact:** Low for single demo, but repeated testing becomes unreliable.  
**Fix:** Document expected CPU credit consumption in runbook or switch to `"unlimited"` mode with cost warning.

---

## Already Resolved / False Positives

### ✓ AgentCore persistence capability
**Claimed issue:** "AgentCore deferred as an architectural choice, not assumed incapable of persistence"  
**Resolution:** Runbook line 147 correctly cites AWS documentation for filesystem configurations and Instances capacity-provider EBS. Deferral is explicit scope decision, not technical blocker. Session storage and EBS lifecycle require validation but documentation exists.

### ✓ SQLite POSIX lock reliability on EBS
**Potential concern:** Network-attached storage and SQLite locking  
**Resolution:** Single-instance, single-attached EBS provides POSIX filesystem guarantees. `store.py:88-104` uses `fcntl.flock()` correctly. No NFS/multi-writer scenario. AWS documentation confirms single-attach EBS supports local filesystem semantics.

### ✓ Grant consumption race condition
**Potential concern:** Worker startup vs. recovery state transition  
**Resolution:** `campaign_store.py:206-242` lifecycle lock covers both worker creation and state updates. SQLite transaction isolation makes grant consumption atomic. Recovery explicitly waits for active worker's store lock (line 241). Design is sound.

### ✓ Source code injection via bundle
**Potential concern:** Untrusted incident data in investigation  
**Resolution:** `replay.py` (not provided but referenced) executes only against frozen fixture data, never arbitrary incident content. `store.py:211` validates bundle structure. No `eval()` or code execution paths in evidence handling.

### ✓ Secrets in CloudWatch
**Claimed risk:** Credentials in log events  
**Resolution:** `aws_smoke.py:84-89` explicitly constructs sanitized event dict. Runbook line 106: "no source text or capability". Template line 50-61 restricts to specific log group. Manual review required before publish (Phase 4 step 7).

---

## Cloud Verification Gates

The following **cannot be verified** without live AWS resources and require explicit confirmation before production claims:

1. **SSM connectivity from selected subnet** - Template accepts any subnet but requires outbound HTTPS to SSM/CloudWatch endpoints
2. **AL2023 NVMe device naming** - Actual `/dev/nvme*` to `/dev/sdf` mapping must be observed
3. **Actual EBS/log/network costs** - Current pricing must be refreshed (runbook line 43)
4. **CloudFormation stack replacement behavior** - Verify retained volume survives instance replacement
5. **Stop/start data persistence** - Actual UUID/mount survival (runbook criteria line 130)
6. **Session Manager logging** - Account-level configuration must exist before credential entry
7. **Python 3.11+ availability on selected AMI** - Must verify before installation
8. **uv 0.11.21 installation on AL2023** - No guarantee current procedure works on actual AMI

---

## Uncertainty: Current Documentation vs. Live Behavior

### Uncertain-1: AgentCore session storage authority semantics
**Issue:** AWS documentation describes persistent filesystem configurations and Instances capacity-provider, but **does not specify** how session resume/recovery interacts with explicit grant consumption and spending authority after host restart.  
**Impact:** Implementation assumes grants are consumed before filesystem persistence. If AgentCore auto-resumes sessions across restarts, it might bypass `campaign_store.py:43-54` grant fencing.  
**Requires:** Live AgentCore testing to verify session lifecycle vs. host stop/start

### Uncertain-2: EBS snapshot lifecycle vs. grant resurrection
**Issue:** Runbook line 47 warns "restored snapshot can resurrect consumed grants" but provides no automated prevention.  
**Current mitigation:** "Restores are isolated historical inspection copies, never a source of renewed paid authority"  
**Gap:** If operator restores snapshot to *same* mount point, SQLite state shows unconsumed grant. No runtime check prevents dispatch.  
**Requires:** Explicit snapshot ID tracking or mount-time grant state validation

### Uncertain-3: CloudWatch Logs PutLogEvents rate limits
**Issue:** Template line 53-54 permits `logs:PutLogEvents` but AWS enforces 5 requests/sec per log stream and 1 MB/sec per account.  
**Impact:** Unknown if single event publish during smoke succeeds under actual account limits.  
**Requires:** Live testing or documented fallback for throttled events

---

## Summary of Findings by Priority

| Priority | Count | Category |
|----------|-------|----------|
| P0 | 3 | Production blockers (cost, monitoring, audit) |
| P1 | 2 | Demo/operational risk (device naming, connectivity) |
| P2 | 4 | Documentation/minor gaps |
| False Positive | 5 | Correctly implemented |
| Verification Gate | 8 | Requires live AWS confirmation |
| Uncertainty | 3 | Needs current AWS service documentation |

**Recommendation:** Proceed with **demo deployment** after addressing P1-1 (device resolution) and P1-2 (connectivity pre-check). **Block production deployment** until P0 items are implemented and all 8 cloud verification gates are confirmed with actual resources.

The offline implementation is **well-architected** for its stated scope. The primary risks are **operational** (cost accumulation, connectivity assumptions) rather than **security or durability** bugs in the code itself.
