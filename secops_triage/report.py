"""Readable local report. All source-provided content is escaped as inert text."""
import html


def safe(value):
    value = html.escape(str(value), quote=True).replace('\n', ' ').replace('\r', ' ')
    for c in ('\\', '`', '*', '_', '[', ']', '(', ')', '#', '|', '!'):
        value = value.replace(c, '\\' + c)
    return value


def markdown(store, packet):
    reasons = {'suspicious_evidence': 'Suspicious activity needs further investigation',
               'documented_expected_activity': 'Activity matches a documented authorization',
               'missing_evidence': 'Required evidence is missing or incomplete',
               'legitimacy_not_established': 'Expected business activity has not been established'}
    source = f"{safe(packet['source'])} / {safe(packet['incident_id'])}"
    lines = [f"# Investigation of {source}", '', safe(packet['title']), '',
             f"**Execution:** {safe(packet['execution'])}. **Data:** {'synthetic' if packet['synthetic'] else 'imported local snapshot'}.", '',
             f"**Recommendation:** {packet['recommendation'] or 'needs analyst review'}. "
             f"**Investigation:** {packet['investigation_status']}. **SIEM status:** unchanged.", '',
             f"Evidence window: {packet['start']} to {packet['end']}. Snapshot observed at {packet['observed_at']}.", '',
             'The SIEM created this incident. This report gathers context; it does not open or close an upstream case.', '']
    evidence = {}
    for item in packet['evidence']:
        evidence[item['id']] = store._get(packet['run_id'], item['hash'])
    def citation(id):
        item = next(x for x in packet['evidence'] if x['id'] == id)
        return f"[evidence {id[:8]}](<{store.blob_path(packet['run_id'], item['hash'])}>)"
    lines += ['## Entities and ownership', '']
    for e in evidence.values():
        entity = e['result'].get('entity')
        if entity:
            lines += [f"- {safe(entity['kind'])}: {safe(entity['name'])}; owner: {safe(entity['owner'])}. {citation(e['id'])}"]
    lines += ['', '## Timeline and source details', '']
    records = {}
    for e in evidence.values():
        for r in e['result']['records']:
            records.setdefault(r['id'], (r, e['id']))
    for r, eid in sorted(records.values(), key=lambda pair: (pair[0]['occurred_at'], pair[0]['id'])):
        attrs = '; '.join(f"{safe(k)}: {safe(v)}" for k, v in r['attributes'].items())
        lines += [f"- **{r['occurred_at']} - {safe(r['kind'])}** ({safe(r['id'])}). {attrs}. {citation(eid)}",
                  f"  Source text (untrusted): {safe(r['raw_text'])}"]
    for a in packet['alerts']:
        lines += ['', f"## {safe(a['title'])}", '',
                  f"Recommendation: **{a['recommendation'] or 'needs analyst review'}**; reason: {reasons[a['reason']]}.", '']
        for observation in a['observations']:
            lines.append(f"- {safe(observation['text'])} {citation(observation['evidence_id'])}")
        if a['contradiction']:
            lines += ['', '**Conflict: recorded authorization and suspicious evidence both exist.**']
        for gap in a['gaps']:
            lines.append(f"- Missing check: {safe(gap['check'])} ({safe(gap['reason'])}).")
        for action in a['next_checks']:
            lines.append(f"- Next check: {safe(action)}")
    lines += ['', '## Collection coverage', '']
    for item in packet['evidence']:
        request = item['request']
        label = request.get('template', item['tool'])
        alert = request.get('alert_id', 'incident')
        lines.append(f"- {safe(alert)} / {safe(label)}: {item['outcome']}; complete={item['complete']}. {citation(item['id'])}")
    lines += ['', '## Draft case note', '',
              f"Investigated existing incident {source} using {len(packet['evidence'])} recorded reads. "
              f"Recommendation: {packet['recommendation'] or 'manual review required'}. "
              'The analyst must review the evidence and record the final disposition in the source case workflow.', '']
    for a in packet['alerts']:
        lines.append(f"- {safe(a['title'])}: {reasons[a['reason']]}.")
        for observation in a['observations']:
            if observation['role'] != 'context':
                lines.append(f"  {safe(observation['text'])} {citation(observation['evidence_id'])}")
        for gap in a['gaps']:
            lines.append(f"  Still needed: {safe(gap['check'])} ({safe(gap['reason'])}).")
    lines += ['',
              '## Integrity and authority', '',
              f"Run: `{packet['run_id']}`. Packet SHA-256: `{packet['packet_hash']}`.", '',
              'Hashes establish artifact integrity, not the truth of a security conclusion. '
              'Demo rules are deliberately limited; no live model, connector, or containment action ran.', '']
    return '\n'.join(lines)
