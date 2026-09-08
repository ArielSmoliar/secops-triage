# SecOps Triage workspace design

The primary user is a Tier 1 analyst comparing an existing SIEM incident with retrieved evidence at a desktop workstation. The immediate goal is to understand what supports the next action, what remains unknown and what to hand off. Product context is in PRODUCT.md; this design applies to the local scripted workspace, not the deferred landing page.

Use a calm light workspace with warm neutral surfaces, restrained teal actions, system fonts and compact information density. The dark warm ink, muted text, borders, focus blue, warning amber and failure red are defined as OKLCH tokens in `secops_triage/web/style.css`. Color is supplementary: all execution, coverage, review and failure states have text labels. Typography uses a 14px body with larger incident and recommendation headings; monospace is reserved for tool and integrity identity.

The sequence is incident selection, real SDK trace, assessment and evidence, uncertainty, then local decision. Desktop places evidence and handoff beside each other. Distinct phishing messages retain separate identities and authorization scopes. At smaller widths the layout becomes one column, and the incident queue scrolls horizontally. Do not hide failed/incomplete work or imply a current live model from a saved scripted trace.

Interaction conventions: one primary investigation action; an explicit inline confirmation for a new revision; exact evidence drill-down with keyboard focus and Escape return; persistent packet-bound drafts; local unresolved handoff distinct from final close/escalate. No fake progress, invented reasoning, default analyst attribution or automatic retries. Source text is rendered as text. Build changes make historical assessments unavailable for revalidation while retaining evidence.

Impeccable consultation informed hierarchy, restrained color, source comparison, accessible focus and responsive behavior. Automated keyboard/layout checks and AI screenshot inspection are documented in the workspace validation; no human usability or complete assistive-technology audit is claimed.
