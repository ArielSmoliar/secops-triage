# SecOps Triage

## Register

product

## Users

Tier 1 SOC analysts investigating an existing incident created by a SIEM or another security tool. Their task is to gather context, evaluate competing explanations, verify evidence and prepare a defensible decision or handoff. Suspicious sign-ins, reported phishing and endpoint alerts are the agreed scope. Phishing is the first end-to-end demo.

## Product Purpose

**From SIEM incident to analyst-ready handoff.**

Turn an existing incident into a reviewable, evidence-backed close-or-escalate recommendation. Explicitly retain inconclusive cases and missing context. The analyst owns the final disposition; the local demo never changes the SIEM. Success is less reconstruction and documentation effort with preserved decision quality. Time savings and real-world reliability are not yet measured.

## Brand Personality

Calm, compact, clear. The owner confirmed this workbench direction on 2026-09-07. Use plain language and let evidence establish trust. No invented confidence percentages or claims of autonomous resolution.

## Anti-references

Avoid a chatbot-first workflow that makes the analyst orchestrate each lookup, decorative dashboards that compete with the current case, or report dumps that require reconstructing the investigation. These follow the agreed incident-focused scope and compact workbench direction; no vendor visual reference has been selected.

## Design Principles

- Start with the source incident and the analyst's next decision.
- Put competing evidence together and reveal original source detail on demand.
- Distinguish collection coverage, evidence sufficiency, recommendation and analyst disposition.
- Preserve uncertainty, provenance and revision identity through the handoff.
- Make local actions and their effects explicit; never imply an upstream update.

## Accessibility & Inclusion

The owner confirmed keyboard access and status labels that do not depend on color. Use plain language. Focus management, screen-reader announcements, contrast and responsive layout must be specified and tested when the interface exists. No conformance level or completed accessibility audit is claimed.


## Positioning and proof

Lead with the analyst's decision and handoff: existing incident, relevant evidence, open questions, supported next action. AI summaries, evidence grounding and human oversight are established SecOps capabilities; they are not claimed as unique inventions. Our demo makes a bounded investigation inspectable through exact source/authorization relationships, separate model-versus-policy evaluation and preserved stopped attempts. These are demonstrable design choices, not a measured advantage over enterprise platforms.

The current surface is CLI and Markdown over synthetic replay. Keep live-model history, scripted examples, future UI and external connectors clearly labeled. Prefer task language such as incident context, evidence, open questions and analyst handoff over broad autonomous-SOC promises. Public copy and imagery must not imply a Splunk integration or endorsement. See docs/SECOPS-POSITIONING-REVIEW.md for the source-based comparison.


## Deferred landing page

The owner requested a landing page for the SecOps Triage capability and explicitly deferred it. Backlog scope: the incident-to-analyst-handoff promise, current hero artwork, a concise phishing walkthrough, verified evidence and limitations, and links to the repository and demo materials. Prioritize demo readiness first; do not begin landing-page implementation yet. Keep marketing content separate from the analyst workspace, and preserve the existing publication/hosting gates.


## Demo workflow reference

Use the source-based Splunk/Datadog alignment in docs/SECOPS-WORKFLOW-ALIGNMENT.md: existing incident → context collection → exact evidence → recommendation and open questions → explicit local decision or unresolved handoff. Follow its case-04 facilitator sequence for the hero. Analyst feedback is waived by the owner; the comparison is not human validation.
