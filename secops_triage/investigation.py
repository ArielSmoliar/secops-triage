"""Auditable demo rules, not live AI or a production security verdict engine."""
from .contracts import REQUIRED, instant

ENGINE_LABEL = 'deterministic replay playbooks (no live model)'


def authorization_activity(trigger, records, family):
    activity = [trigger]
    for r, _ in records:
        target = r['attributes'].get('message_id', r['attributes'].get('process_id'))
        if target == trigger['id'] or (family == 'sign_in' and r['kind'] == 'account_change'
                                      and set(r['entity_ids']).intersection(trigger['entity_ids'])):
            activity.append(r)
    return activity


def authorization_failures(record, trigger, records, family):
    """Evaluate imported authorization assertions; no prose or actor name grants scope."""
    a = record['attributes']
    failures = []
    if a['status'] != 'approved':
        failures.append('not_approved')
    role = {'sign_in': 'identity_owner', 'phishing': 'security_awareness', 'endpoint': 'endpoint_owner'}[family]
    if not a['authority_verified'] or a['authority_role'] != role:
        failures.append('authority_not_established')
    activity = authorization_activity(trigger, records, family)
    if any(instant(a['approved_at']) > instant(r['occurred_at']) for r in activity):
        failures.append('approval_after_activity')
    if any(r['id'] not in a['authorized_event_ids'] for r in activity):
        failures.append('activity_out_of_scope')
    if any(not set(r['entity_ids']) <= set(a['authorized_entity_ids']) for r in activity):
        failures.append('entity_out_of_scope')
    if any(not instant(a['valid_from']) <= instant(r['occurred_at']) <= instant(a['valid_until']) for r in activity):
        failures.append('activity_outside_authorization_window')
    return failures


def assess(bundle, evidence):
    results = []
    for alert in bundle.alerts:
        queries = [e for e in evidence if e['result'].get('alert_id') == alert.id
                   and e['tool'] == 'query_activity']
        gaps = []
        observations = []
        # One latest query per template within this collection; narrower queries
        # never satisfy a full-window playbook obligation.
        selected = {}
        for e in queries:
            selected[e['result']['template']] = e
        for template in REQUIRED[alert.family]:
            e = selected.get(template)
            if e is None:
                gaps.append({'check': template, 'reason': 'not_collected', 'evidence_id': None})
            elif (e['result']['outcome'] != 'success' or not e['result']['complete']
                  or e['result']['start'] != bundle.start or e['result']['end'] != bundle.end):
                gaps.append({'check': template, 'reason': e['result']['outcome'] if e['result']['outcome'] != 'success'
                             else 'incomplete_coverage', 'evidence_id': e['id']})
        records = [(record, e['id']) for e in selected.values() for record in e['result']['records']]
        triggers = {r['id']: (r, eid) for r, eid in records if r['id'] in alert.trigger_ids}
        for trigger_id in alert.trigger_ids:
            if trigger_id not in triggers:
                gaps.append({'check': trigger_id, 'reason': 'trigger_not_retrieved', 'evidence_id': None})
        retrieved_ids = {r['id'] for r, _ in records}
        malicious = [(r, eid) for r, eid in records if r['kind'] == 'indicator'
                     and r['attributes']['verdict'] == 'malicious'
                     and r['attributes']['target_id'] in retrieved_ids]
        # A successful identity access plus external account changes is a separate
        # corroborated escalation path, even with no reputation hit.
        if alert.family == 'sign_in' and any(r['attributes']['result'] == 'success' for r, _ in triggers.values()):
            malicious += [(r, eid) for r, eid in records if r['kind'] == 'account_change'
                          and r['attributes']['external'] and any(
                              t['attributes']['result'] == 'success' and t['occurred_at'] <= r['occurred_at']
                              for t, _ in triggers.values())]
        activity_groups = {tid: {r['id'] for r in authorization_activity(t, records, alert.family)}
                           for tid, (t, _) in triggers.items()}
        activity_ids = set().union(*activity_groups.values()) if activity_groups else set()
        record_by_id = {r['id']: r for r, _ in records}
        authorizations = [(r, eid) for r, eid in records if r['kind'] == 'authorization'
                          and r['attributes']['target_id'] in activity_ids]
        authorization_checks = [(r, eid, authorization_failures(r, record_by_id[r['attributes']['target_id']], records, alert.family))
                                for r, eid in authorizations]
        # Contradictory status/scope assertions for one target cannot be overridden
        # by another nominally valid authorization in the same snapshot.
        invalid_targets = {r['attributes']['target_id'] for r, _, failures in authorization_checks if failures}
        invalid_ids = {tid for tid, ids in activity_groups.items() if ids.intersection(invalid_targets)}
        authorized_ids = {r['attributes']['target_id'] for r, _, failures in authorization_checks if not failures} - invalid_ids
        for r, eid in triggers.values():
            observations.append({'text': f"Retrieved {r['kind']} event {r['id']} at {r['occurred_at']}.",
                                 'evidence_id': eid, 'event_id': r['id'], 'role': 'context'})
        for r, eid, failures in authorization_checks:
            if failures:
                observations.append({'text': 'Authorization cannot establish legitimacy: ' + ', '.join(failures) + '.',
                                     'evidence_id': eid, 'event_id': r['id'], 'role': 'authorization_gap'})
                continue
            observations.append({'text': f"Source records authorization by {r['attributes']['actor']} "
                                 f"under {r['attributes']['reference']}.",
                                 'evidence_id': eid, 'event_id': r['id'], 'role': 'benign_context'})
        for r, eid in malicious:
            observations.append({'text': ('Source intelligence marks retrieved incident activity malicious.' if r['kind'] == 'indicator'
                                         else 'External account change follows successful access.'),
                                 'evidence_id': eid, 'event_id': r['id'], 'role': 'suspicious'})
        contradiction = bool(malicious and authorizations)
        if malicious:
            recommendation, reason = 'escalate', 'suspicious_evidence'
        elif gaps:
            recommendation, reason = None, 'missing_evidence'
        elif authorized_ids >= set(alert.trigger_ids):
            recommendation, reason = 'close', 'documented_expected_activity'
        else:
            recommendation, reason = None, 'legitimacy_not_established'
        next_checks = [f"Retrieve complete {g['check']} evidence for {bundle.start} through {bundle.end}." for g in gaps]
        if recommendation is None and not gaps:
            next_checks.append('Confirm the activity with the responsible owner through an approved channel.')
        if invalid_ids:
            next_checks.append('Resolve invalid or conflicting authorization status, authority and exact activity scope.')
        if contradiction:
            next_checks.append('Resolve the conflict between recorded authorization and suspicious evidence.')
        if recommendation == 'escalate':
            next_checks.append('Have an analyst assess incident scope and the appropriate response.')
        results.append({'alert_id': alert.id, 'family': alert.family, 'title': alert.title,
                        'recommendation': recommendation, 'reason': reason,
                        'investigation_status': 'needs_review' if gaps or recommendation is None else 'complete',
                        'observations': observations, 'gaps': gaps, 'contradiction': contradiction,
                        'next_checks': next_checks})
    recommendation = ('escalate' if any(x['recommendation'] == 'escalate' for x in results)
                      else 'close' if all(x['recommendation'] == 'close' for x in results) else None)
    return {'recommendation': recommendation,
            'investigation_status': 'complete' if all(x['investigation_status'] == 'complete' for x in results) else 'needs_review',
            'alerts': results}
