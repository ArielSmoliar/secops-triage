"""Bounded reads over a snapshot; no network, shell, or model-authored queries."""
from dataclasses import asdict
from .contracts import (Rejected, InspectIncident, LookupEntity, QueryActivity,
                        FindRelatedCases, REQUIRED, TEMPLATES, instant, canonical)


def execute(bundle, request):
    alerts = {a.id: a for a in bundle.alerts}
    if type(request) is InspectIncident:
        return {'outcome': 'success', 'complete': True, 'records': [],
                'incident': {k: getattr(bundle, k) for k in ('tenant_id', 'source', 'incident_id', 'title')},
                'alerts': [asdict(a) for a in bundle.alerts]}
    if type(request) is LookupEntity:
        entity = next((e for e in bundle.entities if e.id == request.entity_id), None)
        if entity is None:
            raise Rejected('entity is outside this incident')
        return {'outcome': 'success', 'complete': True, 'records': [], 'entity': asdict(entity)}
    if type(request) not in (QueryActivity, FindRelatedCases) or request.alert_id not in alerts:
        raise Rejected('alert is outside this incident')
    alert = alerts[request.alert_id]
    template = request.template if type(request) is QueryActivity else 'related_cases'
    start = request.start if type(request) is QueryActivity else bundle.start
    end = request.end if type(request) is QueryActivity else bundle.end
    if template not in (*REQUIRED[alert.family], 'related_cases'):
        raise Rejected('template is outside the alert playbook')
    if not instant(bundle.start) <= instant(start) <= instant(end) <= instant(bundle.end):
        raise Rejected('query exceeds incident investigation window')
    source = next((s for s in bundle.sources if s.template == template), None)
    base = {'alert_id': alert.id, 'template': template, 'start': start, 'end': end,
            'source_id': source.id if source else None, 'records': []}
    if source is None:
        return dict(base, outcome='unavailable', complete=False, coverage=None, total_matches=0)
    coverage = {'start': source.start, 'end': source.end}
    if source.outcome not in ('success', 'truncated'):
        return dict(base, outcome=source.outcome, complete=False, coverage=coverage, total_matches=0)
    records = [asdict(e) for e in bundle.events if e.source_id == source.id
               and e.kind in TEMPLATES[template] and set(e.entity_ids).intersection(alert.entity_ids)
               and instant(start) <= instant(e.occurred_at) <= instant(end)]
    records.sort(key=lambda e: (e['occurred_at'], e['id']))
    complete = (source.complete and source.outcome == 'success'
                and instant(source.start) <= instant(start) and instant(source.end) >= instant(end))
    result = dict(base, records=records[:200], total_matches=len(records), coverage=coverage,
                  outcome=source.outcome, complete=complete)
    if len(records) > 200:
        result.update(outcome='truncated', complete=False)
    while len(canonical(result)) > 60000 and result['records']:
        result['records'].pop()
        result.update(outcome='truncated', complete=False)
    return result
