"""Auditable demo rules, not live AI or a production security verdict engine."""
from .contracts import REQUIRED

ENGINE_LABEL = 'deterministic replay playbooks (no live model)'


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
        authorizations = [(r, eid) for r, eid in records if r['kind'] == 'authorization'
                          and r['attributes']['target_id'] in triggers]
        authorized_ids = {r['attributes']['target_id'] for r, _ in authorizations}
        for r, eid in triggers.values():
            observations.append({'text': f"Retrieved {r['kind']} event {r['id']} at {r['occurred_at']}.",
                                 'evidence_id': eid, 'event_id': r['id'], 'role': 'context'})
        for r, eid in authorizations:
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
