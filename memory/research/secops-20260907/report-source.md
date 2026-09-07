# The daily work behind alert triage

Research brief for Ariel Smoliar | SecOps product discovery | 7 September 2026

## The problem is credible; the product advantage is unproven

**Alert triage is a documented daily workflow.** Microsoft explicitly schedules incident triage and investigation daily, alongside checks that data connectors and playbooks are working. Its email-security operations guide assigns daily triage, investigation, resolution and classification to the security operations team. This is stronger support for recurring work than the migration use case. It is prescribed operational practice, not a measurement of every analyst's day. [Microsoft: Sentinel operational guide, updated 22 April 2026](https://learn.microsoft.com/en-us/azure/sentinel/ops-guide); [Microsoft: Defender for Office 365 operations guide](https://learn.microsoft.com/en-us/defender-office-365/mdo-sec-ops-guide).

**The most defensible common task is assembling enough context to make a disposition.** Across the reviewed procedures, the analyst starts with an alert, examines its entities and surrounding activity, tests whether the behavior is expected, determines scope, and records a decision. This is a synthesis of the workflows on the following pages, not an observed time-and-motion study.

**Keep suspicious sign-ins, reported phishing and endpoint alerts as three playbooks.** They share a case structure, but require different evidence and interpretation. An email delivery event, a successful authentication and a process detection answer different questions. Do not collapse them into one generic checklist.

**Do not pitch evidence-backed AI investigation as new by itself.** Google TIN, Microsoft's Security Alert Triage Agent and AWS Security Incident Response already cover substantial parts of this promise. The opportunity must be demonstrated against the tools an analyst actually has enabled. [Google: Triage Agent](https://docs.cloud.google.com/chronicle/docs/secops/triage-investigation-agent); [Microsoft: Security Alert Triage Agent](https://learn.microsoft.com/en-us/defender-xdr/security-alert-triage-agent); [AWS: Detect and Analyze](https://docs.aws.amazon.com/security-ir/latest/userguide/detect-and-analyze.html).

## What this research can establish

High confidence: the workflow exists, its steps are concrete, and source availability and organizational context affect decisions. Moderate confidence: automating repeated evidence collection can reduce effort in a suitable environment. Not established: which family is most frequent across SOCs, actual minutes saved by our agent, willingness to adopt, or a defensible market gap.

Scope includes Google Workspace and Google Security Operations; AWS GuardDuty, Detective, Security Hub and Security Incident Response; Microsoft Entra, Defender and Sentinel. These are related security ecosystems, not interchangeable product bundles. No customer environment was accessed.

---PAGE---

# Suspicious sign-ins

## The analyst's job: establish whether access was legitimate

In Entra, the documented investigation compares the event with the user's usual application, device, location, IP and user agent; checks related alerts in other security tools; and may contact the user. Microsoft cautions that email or Teams might themselves be compromised. Depending on the evidence, the analyst confirms compromise, confirms safety or dismisses risk. Full ID Protection access requires Entra ID P2 or Entra Suite. [Microsoft: How to investigate risk, updated 27 May 2026](https://learn.microsoft.com/en-us/entra/id-protection/howto-identity-protection-investigate-risk).

Google's Workspace procedure also asks whether the user recognizes the login and directs further action if legitimacy cannot be established. It documents a benign source of surprising alerts: Mail Fetcher retrieves through Google servers. This illustrates why an unusual location is a question to investigate, rather than a self-contained verdict. [Google: Suspicious login activity, updated 26 August 2026](https://knowledge.workspace.google.com/admin/reports/about-admin-alerts-for-suspicious-login-activity).

AWS's closest analogue is suspicious cloud-credential use. The analyst identifies the principal and API operation, distinguishes long-term from temporary credentials, inspects CloudTrail session-issuer information, reviews effective permissions, and asks the credential user to verify operation, time and source IP. This is cloud access, not a direct substitute for an employee sign-in workflow. [AWS: Remediating potentially compromised credentials](https://docs.aws.amazon.com/guardduty/latest/ug/compromised-creds.html).

## Repeated work and judgment

The repeated work is retrieving history, reconciling user and device identities, finding related activity, and gathering the business explanation. The judgment is whether that explanation accounts for the evidence and whether other activity changes the risk. An owner response is additional evidence; our proposed product should not treat it as an automatic override of contradictory facts.

**Telemetry trap:** Google's user-event documentation notes VPN/proxy addresses, collapsed repeated attempts and special SAML logging behavior. Some nonbrowser activity is excluded except suspicious programmatic sessions. Therefore counts, geography and missing events need source-specific interpretation. [Google: User log events, updated 3 September 2026](https://knowledge.workspace.google.com/admin/reports/user-log-events).

## A concrete case to test

Illustrative reconstruction, not a real customer incident: an unfamiliar-location alert has a familiar device and successful authentication, but the current export lacks subsequent account activity. A useful agent retrieves the available history, explains the location ambiguity, identifies the missing activity source and prepares an exact verification question. It should not conclude "safe because MFA succeeded."

The useful handoff is an evidence-linked answer to: who accessed what, when, from where, whether it fits expected behavior, and which uncertainty still prevents closure. That is our design inference from the procedures above.

---PAGE---

# Reported phishing

## The analyst's job: classify the message and establish impact

Microsoft's daily email triage guidance prioritizes potentially malicious URL clicks ahead of user-reported phishing. This is an urgency ordering, not a frequency ranking. It also requires daily resolution and classification work. The distinction matters: a report that a message looks suspicious is not equivalent to evidence that a recipient interacted with it. [Microsoft: Defender for Office 365 operations guide](https://learn.microsoft.com/en-us/defender-office-365/mdo-sec-ops-guide).

Google documents a concrete search sequence: locate a message by recipient, subject and date; inspect identifiers and delivery records; remove the recipient restriction and repeat the search to find other recipients. Logs may take minutes to arrive. This procedure establishes scope for suspected malicious mail; it is not, by itself, a complete benign-versus-phishing classification method. [Google: Investigate reports of malicious emails, updated 26 August 2026](https://knowledge.workspace.google.com/admin/security/investigate-reports-of-malicious-emails).

Microsoft's delivered-mail workflow distinguishes original delivery location, latest location, filtering overrides and subsequent remediation. A message initially delivered might later have been quarantined. Reconstructing that history prevents a stale delivery fact from being mistaken for current exposure. [Microsoft: Investigate delivered malicious email, updated 3 July 2026](https://learn.microsoft.com/en-us/defender-office-365/threat-explorer-investigate-delivered-malicious-email).

## Where the work gets interrupted

**Content access:** Google separates viewing message headers from viewing sensitive content. An administrator must have access enabled; opening content requires a reason recorded in the audit log. Seeing a report does not imply permission to inspect its body. [Google: View sensitive content, updated 26 August 2026](https://knowledge.workspace.google.com/admin/security/use-the-investigation-tool-to-view-sensitive-content).

**Interaction evidence:** Microsoft's UrlClickEvents comes from Defender for Office 365 and records allowed/blocked clicks and click-through behavior. Without the underlying service, a query may fail or return nothing. Some Drafts/Sent-item events cannot be joined to email tables using the normal message identifier. Empty results therefore cannot establish that nobody clicked. [Microsoft: UrlClickEvents, updated 4 June 2026](https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-urlclickevents-table).

## A concrete case to test

Illustrative reconstruction: three employees report the same suspicious email. The agent groups the reports, identifies other deliveries, separates already-remediated copies from remaining exposure, and checks interaction evidence. If click telemetry is unavailable, the packet states "interaction unknown" and specifies the next check. It does not report "no users affected."

The agent's useful output is a message verdict plus affected scope, interaction evidence, remaining uncertainty and a draft response for analyst review. The AWS sources reviewed did not establish a comparable native employee-reported-mail workflow; this is a research boundary, not a claim that AWS cannot support phishing investigations.

---PAGE---

# Endpoint alerts

## The analyst's job: reconstruct what executed and why

Defender for Endpoint starts from the alert and its affected assets. The analyst expands entities in the alert story, inspects activity before and after the trigger, follows the process tree or timeline, and resolves and classifies the alert after investigation. This is already a structured investigation experience, rather than an empty console requiring an agent to invent every step. [Microsoft: Investigate endpoint alerts, updated 14 January 2026](https://learn.microsoft.com/en-us/defender-endpoint/investigate-alerts).

Google SecOps investigators search an asset by identity and timestamp, then inspect timeline, domains, prevalence and correlated vendor alerts. Crucially, a view opened from an alert can show only that investigation's events. The default time window is two hours, and generic events are excluded from curated asset views; raw-log or UDM searches offer broader coverage. [Google: Investigate assets, updated 3 September 2026](https://docs.cloud.google.com/chronicle/docs/investigation/investigate-asset).

AWS GuardDuty Runtime Monitoring supplies process and lineage context for cloud workloads. Its examples explicitly allow for expected behavior: a cryptocurrency-related finding may reflect authorized blockchain activity and require a carefully scoped suppression. These are EC2/container investigations, not evidence of employee laptop coverage. [AWS: Runtime Monitoring finding types](https://docs.aws.amazon.com/guardduty/latest/ug/findings-runtime-monitoring.html).

## What the analyst must still decide

Our synthesis: a suspicious command or tool must be understood in relation to its parent process, user, workload purpose, subsequent behavior and available history. Repeated evidence retrieval is automatable; business legitimacy and conflicting facts still need judgment. A reputation result should be supporting evidence, not a universal closure rule.

An endpoint alert arriving through AWS Security Hub may originate in a third-party sensor. AWS lists CrowdStrike Falcon as a sending integration. Receiving the finding does not, by itself, establish access to every underlying process or network event. [AWS: Third-party integrations with Security Hub CSPM](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-partner-providers.html).

## A concrete case to test

Illustrative reconstruction: a process alert resembles a known administration task. The first view contains no additional suspicious events, but is restricted to the alert's time window. The agent expands the window and queries relevant raw events before accepting that absence. If process ancestry or task authorization is missing, the analyst sees the gap and the specific lookup needed.

The useful packet connects trigger, execution chain, affected assets, supporting and conflicting context, and response status. A detection, a completed investigation and a successfully contained threat must remain separate concepts in our product.

---PAGE---

# Existing automation is the baseline

## Google already offers adaptive investigation

TIN searches and refines queries, enriches indicators with threat intelligence, analyzes command lines and reconstructs process trees. It exposes a disposition, explanation, investigation timeline and suggested next steps. It operates on SIEM-ingested data rather than SOAR-connector alerts. Its default investigation delay allows arriving events to be correlated. These are documented capabilities, not independently verified accuracy claims. [Google: Triage alerts with the Triage Agent, updated 3 September 2026](https://docs.cloud.google.com/chronicle/docs/secops/triage-investigation-agent).

Access is not a currently open universal free trial. The dedicated terms say the trial ended 31 August 2026 absent written extension; subsequent access depends on subscription and Security Tokens. The overview instead gives 30 August. Both dates are past; use dedicated terms for entitlement discussions and verify the actual account. [Google: Agentic SOC trial, updated 3 September 2026](https://docs.cloud.google.com/chronicle/docs/agentic-soc/trial).

## Microsoft combines triage and existing case context

The Security Alert Triage Agent provides verdicts and supporting reasoning. User-reported phishing is generally available; the broader identity/cloud subset is in preview. This is not evidence of universal support for every endpoint or sign-in alert. [Microsoft: Security Alert Triage Agent](https://learn.microsoft.com/en-us/defender-xdr/security-alert-triage-agent).

Sentinel already offers related incidents, source-query drilldowns, entity context, task lists and an activity record for investigation continuity. Merely retrieving similar cases or adding an audit trail is therefore not established differentiation. [Microsoft: Incident investigation, updated 14 May 2026](https://learn.microsoft.com/en-us/azure/sentinel/incident-investigation).

A current-documentation correction matters: Microsoft says the separate Endpoint AIR experience and manual triggering ended on 1 September 2026, with its capabilities integrated into the antivirus stack. The notice explicitly excludes Office 365 AIR. Older steps remain lower on some pages; the dated notice takes precedence for this research. [Microsoft: Automated investigation results](https://learn.microsoft.com/en-us/defender-xdr/m365d-autoir-results).

## AWS combines automated triage with responders

Security Incident Response evaluates expected behavior using findings, logs, metadata, threat intelligence and customer context. Unresolved legitimacy can require customer confirmation. Its separate AI Investigative Agent gathers evidence and builds timelines for AWS-supported cases; self-managed cases do not include that capability. [AWS: Detect and Analyze](https://docs.aws.amazon.com/security-ir/latest/userguide/detect-and-analyze.html); [AWS: AI Investigative Agent](https://docs.aws.amazon.com/security-ir/latest/userguide/ai-investigative-agent.html).

**Implication:** "We investigate and cite evidence" describes a real need, but also existing products. The comparison must be against enabled native automation, not an artificially manual baseline.

---PAGE---

# What would make analysts better?

## Test improvements to the remaining work

The following are product hypotheses, not established market gaps:

- **Complete missing context:** retrieve the specific history or organizational evidence that the current verdict lacks, rather than repeat its summary.
- **Explain evidence coverage:** show source health, permissions, time windows and incomplete searches so the analyst can interpret an empty result correctly.
- **Make review faster:** connect each consequential conclusion to the relevant observation, expose contradictions, and avoid making the analyst re-run the investigation just to trust the packet.
- **Prepare the exact handoff:** state what needs confirmation, by whom, and why it changes the disposition. Drafting a question is distinct from sending it or authorizing action.

The candidate promise becomes: **complete the investigation an analyst would otherwise have to finish manually, then prepare a defensible disposition.** Keep all three selected families, but validate their evidence requirements separately.

## Do not inherit another agent's productivity headline

Microsoft's vendor-authored phishing study recruited 167 external analysts to process 25-email queues built from 93 employee-reported emails; it excluded 13 low-scoring responses. The experiment inserted synthetic erroneous agent verdicts to test behavior. The reported 6.5x true-positives-per-analyst-minute result uses a protocol that removes agent-benign items from review. The paper attributes most of that gain to removing those items. When analyzing the full queue without that protocol, overall handling time was roughly unchanged statistically, while analysts spent more attention on malicious email. This supports evaluating workflow design, not borrowing a "6.5x faster" promise for our human-review-every-case product. It is a controlled vendor study, not an independent field guarantee. [Microsoft: Randomized Controlled Trial for Phishing Triage Agent, 2025, methods and results](https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/microsoft/bade/documents/products-and-services/en-us/security/randomized-controlled-trial-for-phishing-triage-agent-accessible.pdf).

## How to test the promise

Use the same source evidence and comparable cases for manual/native-tool and assisted work. Keep final resolutions and future events out of agent inputs. Counterbalance case order so familiarity does not become a fake productivity improvement.

Measure active analyst time including verification and correction; total elapsed time including source waits; unnecessary escalations; missed escalation cases; unsafe close recommendations; and unresolved cases. Report results separately for each family. A system that sends everything to review is not a successful triage agent.

A small replay set can validate behavior and identify failures. It cannot establish production safety, real daily frequency or sustained time savings. No numeric benefit is claimed for our project.

---PAGE---

# Office-hours conclusion

## Proceed on the problem; challenge the differentiator

**Keep the SecOps direction.** It fits the user's daily-work criterion much better than the occasional migration workflow. However, public documentation supports the job's existence more strongly than it supports a new standalone product.

**Reported phishing has the strongest explicit workload evidence in this source set.** Microsoft names it in daily operations and publishes a controlled analyst study. This does not establish that it exceeds suspicious sign-ins or endpoint alerts in a particular SOC. Preserve the three-family scope and let actual queue data determine prioritization.

**Make the first review about investigation usefulness.** For each family, assemble one evidence-complete case and one with a realistic gap. Ask whether the packet lets an analyst decide faster than their current console and automation. Measure what they must still look up, what they distrust and what they rewrite. Synthetic cases should be labeled as such; they test mechanics, not demand.

**Stop or narrow if the current stack already does the work.** If the proposed packet mainly restates a native agent's result, integration into that workflow or a narrower missing-evidence task is more plausible than building a parallel SOC console. That is a recommendation from this analysis, not a measured market finding.

## Research boundaries and confidence

Sources were official product documentation, operational guides and one vendor-authored experiment, accessed 7 September 2026. The Google and AWS lanes were researched separately, then consequential capability and limitation claims were checked in the coordinating review. Microsoft workflow and experimental evidence were reviewed directly.

Documentation establishes intended procedures and advertised capabilities. It cannot substitute for observing analysts, disclose every deployment's coverage, or prove that capabilities work reliably in a customer's environment. Google Workspace administrators, frontline SOC analysts and AWS incident responders also represent different roles; their workflows are compared with that distinction intact.

No source in this research establishes a universal frequency ranking across our three families. No customer data, Flare AI implementation or SafeAgent implementation was inspected. No account licensing, connector permissions, deployment or paid model execution was attempted.

The source review stopped after each family's workflow, material telemetry gaps and existing automation had primary support. Remaining gaps require customer observation or execution rather than more general vendor documentation. Conflicting current documentation was preserved or resolved using the more specific dated notice; uncertain rollout and entitlement details should be checked before implementation.

**Next office-hours decision:** which missing part of today's investigation can we demonstrably finish better than the analyst's existing tools? The research supplies concrete candidates. It does not yet supply the answer for a particular team.
