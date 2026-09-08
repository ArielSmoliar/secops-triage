# Title

SecOps Triage

## One-line Summary

A Strands-powered workspace that gathers security evidence, exposes critical context, and supports a cited investigation and an actionable analyst handoff.

## Devpost Project Story

## Inspiration
Security analysts need to decide what an existing incident warrants: further investigation, a supported close, or a handoff with open questions. The difficult part is connecting messages, identities, activity, intelligence, and business authorization without losing the source behind each conclusion.

SecOps Triage is built for Tier 1 security analysts. Its goal is an evidence-backed next decision, with judgment kept in the analyst's hands.

## What it does
The demo follows two similar emails. The first is an approved security-training exercise. The second has a different link that was clicked and flagged malicious by synthetic intelligence. The first email's approval does not cover that follow-up.

The analyst starts an investigation, watches the Strands tool trace, compares the two messages, opens the exact-link intelligence citation, and saves a handoff containing the reason, missing context, and a concrete next action. Here, that next action is to request an authorized identity audit export and inspect the follow-up link. A recorded click is not treated as proof of stolen credentials.

## How we built it
The Strands Agents SDK calls four scoped investigation tools: `inspect_incident`, `lookup_entity`, `query_activity`, and `find_related_cases`. The demonstrated run makes nine evidence reads. Results, citations, coverage, and packet identity are retained so the analyst can inspect the sources.

Python host controls enforce scope, evidence integrity, durable storage, and decision boundaries. The browser workspace uses JavaScript, HTML, and CSS; SQLite and retained artifacts hold the local record. Provider output, deterministic policy, and the final packet remain separate. Decisions and handoffs are host-side actions, outside the agent's investigation tool set. The source SIEM stays unchanged.

The recorded UI demo runs locally with synthetic evidence and a scripted provider through the real Strands SDK. It demonstrates executable orchestration and the analyst workflow. The recorded handoff is saved by an automated demonstration operator. Separately, a scripted run was verified on private EC2 in Ohio with encrypted EBS, Systems Manager access, and CloudWatch delivery. That EC2 host is now stopped; the browser UI is not deployed there. AgentCore and Bedrock are not part of this implementation.

## Challenges we ran into
We had to preserve distinctions that are easy to blur: approval for one event versus another, an exact URL match versus an older domain assessment, missing telemetry versus a clean result, and collected evidence versus a complete analysis.

Durable execution also mattered. We built around retained failures, duplicate-start protection, immutable evidence, and explicit revisions, so a stopped investigation does not silently become a successful one.

## Accomplishments that we're proud of
- A working local analyst workflow from an existing synthetic incident to a saved evidence-bound handoff.
- A visible four-tool Strands investigation with nine inspectable evidence reads in the hero case.
- Explicit separation of agent retrieval, host policy, and operator decisions.
- A verified application baseline with 310 passing tests, zero skips, and 14 browser checks.
- A two-minute narrated demo that shows the exact evidence behind the next action.

## What we learned
An agent's output becomes more useful when a reviewer can follow its sources and see what remains unknown. We used Codex to develop and debug the implementation, conduct independent AI reviews, verify frozen source, and iterate on the analyst UI and demo. OpenAI-generated narration is labeled in the video. These engineering checks are not a claim of human acceptance or measured time savings.

## What's next for SecOps Triage
Evaluate live-model assessment quality, validate usefulness with analysts, and add authorized live security connectors. The current demo is a local, single-operator prototype using synthetic evidence and scripted execution. Production accuracy and analyst productivity gains have not been measured.

## Try it locally
Use Python 3.11+ and uv on macOS or Linux. From a fresh checkout:
```sh
uv sync --frozen --extra agent
uv run --frozen --extra agent python -m secops_triage.workspace --root data/judge-workspace --port 0
```
Open the printed localhost URL, select case-04, and click **Run scripted investigation**. Inspect the four tools, message comparison, source citations, and saved handoff. Choose a new private workspace directory for a fresh demo. No API key, paid model call, or AWS account is needed for this local walkthrough. Stop with Ctrl-C.

Source and setup: https://github.com/ArielSmoliar/secops-triage

## Problem
Tier 1 analysts need to connect incident evidence and authorization before deciding the next step.

## Solution
Four scoped Strands tools gather context into an inspectable packet and local analyst workflow.

## Why This Matters
A similar message does not inherit another message's training approval. The analyst can examine the exact sources behind further investigation.

## How We Used AI
Real Strands SDK orchestration with a scripted provider in the current demo. OpenAI generated the labeled narration. Historical live results are separately recorded; no current live-model quality claim.

## How We Used Codex
Implementation, debugging, independent AI review, frozen-source verification, browser checks and demo editing, documented in repository handoffs.

## Key Features
Four scoped tools; trace and citations; exact authorization comparison; missing context; local evidence-bound decisions/handoffs.

## Architecture
Diagram: docs/assets/secops-triage-architecture.png. Local UI, Strands/scripted provider, host controls and SQLite/artifacts; separately verified Ohio EC2/EBS/SSM/CloudWatch.

## Testing Instructions
Use the Try it locally instructions in the story above. No credentials or paid model calls.

## Public Demo Link
Not available; local walkthrough is provided.

## Public Repository Link
https://github.com/ArielSmoliar/secops-triage

## Demo Video
Local final-v4: data/demo-video-20260908/final-v4/secops-triage-demo-2min.mp4. Two minutes, OpenAI Cedar voice, no subtitles. Public YouTube/Vimeo URL pending.

## Screenshot Shot List
1. Strands trace and four tools.
2. Two message scopes.
3. Exact-follow-up intelligence.
4. Saved automated local handoff.
Cover: docs/assets/secops-triage-hero-v2.png (conceptual illustration).

## Submission Readiness Notes
Owner requested populating existing Devpost draft; final submission is not authorized. Project 1421584 / submission 1175395. Project content saved through Devpost connector; submitter, country, repository, testing instructions, architecture attachment, cover and four captioned demo images were saved and verified. The entry remains a draft.

## Known Limitations
Scripted findings are minimal and failed the semantic completeness review retained in docs/SECOPS-TECHNICAL-REVIEW-20260908.md. Live-model evaluation and analyst validation remain pending. No measured productivity or production accuracy claim; no live SIEM integration.

## TODO Official Form Fields
- Submitter: Individual (owner supplied).
- Country: United States (owner supplied).
- Track: Professional Agents proposed; explicit approval requested after automatic review blocked this selection.
- Repository: public GitHub URL above. MIT license selected for owner's open-source request.
- Architecture diagram: existing reviewed diagram uploaded to the draft.
- AWS Builder ID: missing.
- Public video URL: missing.
- Live demo/blog: optional, not available.

Devpost readback: the project page is public (`published`), while the hackathon entry remains Draft with no submission timestamp. Public page: https://devpost.com/software/secops-triage. Story content matches after Markdown/plain-text normalization.
