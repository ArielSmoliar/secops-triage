# Inspectable intelligence evidence

Intelligence records now carry a concrete observable, provider, match basis, source confidence, assessment/expiry times and rationale. The deterministic layer compares that observable with the claimed activity and checks validity at the snapshot time. This is verification of imported evidence relationships, not external threat-intelligence enrichment or proof of compromise.

## Normalized contract

Indicators retain target_id, verdict and the descriptive indicator label, and require observable_type, observable_value, provider, match_basis, confidence, assessed_at, expires_at and rationale. Supported observable types are url, domain, ip and sha256. Match basis is exact_observable or domain_reputation. Confidence is source metadata (high, medium, low or unknown), not a calibrated product score and not a substitute for matching evidence.

Messages and processes now include a bounded observables list with explicit type/value entries. Sign-in IPs and connection destinations use their existing structured fields. Exact matching does not infer a URL from the sender, subject, command line or prose. Empty observable lists are permitted, but cannot establish a match. Duplicate/malformed observables, invalid SHA-256/IP values, malformed URL hosts, control characters and userinfo are rejected. Nothing is fetched, resolved, executed or uploaded.

Assessment time cannot follow the source observation; expiry must follow assessment. A finding is expired when expires_at is at or before the snapshot's observed_at. This honors the imported provider-validity interval, not an independently established age policy. Provider authenticity, TTL appropriateness and rationale accuracy remain importer/reviewer responsibilities.

## Decision behavior

- A current exact URL/IP/hash match to the claimed retrieved target can support escalation when the source verdict is malicious. This means the imported source labels that observable malicious; it does not establish a real attack or compromise.
- Same domain with a different URL is not an exact URL match. URL comparison is intentionally literal, including path/query/fragment; no equivalence or redirect is guessed. Conservative formatting mismatches can require review.
- Domain-only findings stay unresolved for every activity type, even if labeled exact_observable. They do not silently become exact URL or file evidence.
- Expired, mismatched, domain-only or unretrieved-target findings create cited evidence-quality gaps. An authorization cannot turn these into a clean result.
- Current benign and malicious verdicts for the same target/type/value remain separately attributed and create a conflict. A valid malicious finding can still support escalation, while investigation status remains needs_review.
- Successful collection is distinct from sufficient evidence. The report calls these “collected intelligence remains unresolved” and carries the issue into the case note.

The replay adapter still has one source per query template. It can preserve provider fields on records from one normalized intelligence export; this is not a new multi-provider connector. Relationship-based retrieval includes assertions attributed to additional entities of scoped activity without collecting unrelated entities.

## Analyst presentation

The handoff shows observable, target, provider, match basis, provider confidence, assessment/expiry times and source rationale beside the citation. It explicitly states that source accuracy and compromise have not been independently established. Invalid findings remain in the timeline and evidence-quality gaps rather than disappearing. Source text is escaped; raw prose cannot repair a wrong structured match.

## Compatibility

These stricter message/process/indicator shapes change input and engine identity. Legacy snapshots lacking the required fields are rejected, not silently filled with invented observables or provenance. intelligence.py participates in the engine digest. Use a fresh import for new work. Historical live stores were not opened or rewritten; saved reports remain preserved. Reproduce old packets using their recorded execution build, not by altering their hashes. SQLite remains schema version 2.

## Review and limits

Independent review reproduced a domain-only bypass through endpoint targets and malformed-host URL acceptance. A follow-up review found malformed connection URLs could raise during matching; these now yield an explicit invalid-target gap. All three findings were fixed with regression tests. Final fresh-context AI review found no remaining blockers in this scope; this was not an external human SOC assessment. Tests cover all three families, expiry boundary, wrong URL/hash/IP, missing target, domain-only scope, conflicting provider verdicts, source prose injection and malformed contracts.

This increment adds deterministic evidence checks and richer synthetic source records. It does not perform a real intelligence lookup, validate provider truth, score model entailment, record analyst participation, add a browser UI or authorize spending. The observed-usefulness and separate model-evaluation gates remain open.

Verification: 228 full-suite tests passed in 63.859 seconds, including 12 focused intelligence tests. Two fresh synthetic phishing CLI runs verified exact-URL escalation and unresolved domain-only evidence. Source hashes, packet hashes and review findings are recorded in outputs/secops-intelligence-validation.json.
