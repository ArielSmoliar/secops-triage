# SecOps demo workflow alignment

Reviewed 2026-09-07. The owner requested alignment with the researched Splunk and Datadog flows and waived actual analyst feedback. This is a source-based design check, not a recorded analyst session or human case acceptance. Video listings/descriptions and official companion articles were inspected; full video playback/transcripts were not reviewed.

## Reference basis

- [Splunk Attack Analyzer video](https://www.splunk.com/en_us/resources/videos/automated-threat-analysis-from-splunk-attack-analyzer.html): credential-phishing and malware analysis.
- [Splunk phishing workflow, July 2026](https://www.splunk.com/en_us/blog/security/centralize-and-accelerate-phishing-investigations-in-splunk-enterprise-security.html): reported email in the analyst queue, related entity context, and inline message/URL enrichment supporting triage. Our inference is to keep the incident and decisive evidence together.
- [Datadog Bits AI video](https://www.youtube.com/watch?v=qULEpqaatu8) and [official workflow article, updated March 2026](https://www.datadoghq.com/blog/bits-ai-security-analyst/): open a signal's investigation, inspect linked queries and contextual findings, review benign/suspicious recommendations, then choose a response. Our local close/escalate/needs-review labels are not exact equivalents of vendor verdicts.
- [Datadog historical investigation video](https://www.youtube.com/watch?v=jsFu8ug1Udg) and [Cloud SIEM demo](https://www.youtube.com/watch?v=oCS8F7KTE3E), linked from its [product page](https://www.datadoghq.com/product/cloud-siem/): references for investigation context and evidence pivots, not proof that this demo implements the same interface.

## Demo sequence and implementation check

| Step | What to show | Current implementation / limitation |
|---|---|---|
| 1. Open the incident | Source incident, affected entities, snapshot time and execution/data labels | CLI import and Markdown report; no analyst queue UI |
| 2. Gather context | Incident, entity, activity and related-case checks | Four scoped read-only tools; synthetic replay, no live vendor enrichment |
| 3. Inspect evidence | Message identity, event chronology, exact URL, authorization scope and intelligence validity | Cited observations, timeline/source details and collection coverage in report.py |
| 4. Review the recommendation | Why escalate or close; strongest benign explanation; unknowns; model/policy disagreement if present | Report includes these components; long report requires navigation. Adjacent evidence/decision panels remain proposed |
| 5. Prepare the next action | Cited case note and missing context, then an explicit local decision or unresolved handoff | Draft case note and host-only persistence exist; no browser controls, upstream update or containment |

The overall task sequence aligns. Presentation parity is not established: the present surface is CLI/Markdown, and the planned compact workspace remains unbuilt. Show the report's agent-assessment section alongside the headline during narration so policy reconciliation cannot hide a model error.

## Hero case-04: facilitator sequence

Use the named evaluation case-04, not the older drill case IDs. Start with the existing reported-phishing incident and the question: what warrants escalation, and what remains unproven?

1. Identify the two emails by distinct message IDs and exact URLs despite their identical sender and subject.
2. Trace delivery and the allowed click to the follow-up message. Do not attribute that click to the training message.
3. Inspect the authorization: it covers only the first message and its delivery. A prior benign case is context, not approval of the follow-up.
4. Compare intelligence scope and validity: the benign domain assessment expired; the current malicious assessment matches the follow-up URL. These are not competing current exact-URL verdicts.
5. Explain the provisional escalation and separate needs_review status. The latter retains evidence gaps; it does not mean the follow-up is authorized or that compromise has been established.
6. Finish with a cited handoff: investigate potential credential exposure and obtain follow-on identity context through the receiving analyst's authorized workflow. Neither credential submission nor account compromise is proven; unqueried telemetry must not be called clean. This is a proposed next check, not an executed action.

The rubric and expected answer stay outside agent inputs. No final analyst disposition is created by this document. Source-based alignment does not demonstrate usefulness, semantic review quality or production accuracy. Feedback is waived; other saved gates and the prohibition on new paid calls remain in effect.
