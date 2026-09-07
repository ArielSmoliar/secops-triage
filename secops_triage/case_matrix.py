"""Eight draft synthetic investigations; host rubrics never enter source snapshots."""
from .contracts import IncidentBundle, TEMPLATES, canonical, sha
from .fixtures import scenario, intelligence_attributes

CASE_IDS = ('case-01', 'case-02', 'case-03', 'case-05', 'case-06',
            'case-07', 'case-08', 'case-09')


def _event(bundle, event_id):
    return next(e for e in bundle['events'] if e['id'] == event_id)


def _add(bundle, event_id, kind, attributes, minute):
    template = next(t for t, kinds in TEMPLATES.items() if kind in kinds)
    bundle['events'].append({'id': event_id, 'tenant_id': bundle['tenant_id'],
                            'source_id': 'source-' + template,
                            'entity_ids': ['user-1', 'device-1'],
                            'occurred_at': f'2026-09-07T10:{minute:02d}:00Z',
                            'kind': kind, 'attributes': attributes,
                            'raw_text': 'Synthetic imported source assertion for local evaluation.'})


def get_case(case_id):
    if case_id not in CASE_IDS:
        raise ValueError('unknown evaluation case')
    family = ('sign_in' if case_id in CASE_IDS[:3] else
              'phishing' if case_id in ('case-05', 'case-06') else 'endpoint')
    b = scenario(family, 'authorized')
    b.update(incident_id='INC-20' + case_id[-2:], title={
        'case-01': 'Unfamiliar sign-in through planned corporate VPN egress',
        'case-02': 'Successful sign-in followed by external mailbox forwarding',
        'case-03': 'Unfamiliar sign-in with unavailable account audit export',
        'case-05': 'Reported awareness simulation with recorded link interaction',
        'case-06': 'Reported document email with incomplete interaction export',
        'case-07': 'Scheduled endpoint inventory and related service connections',
        'case-08': 'Inventory process and a second unapproved executable',
        'case-09': 'Endpoint execution with revoked maintenance approval'}[case_id])
    auth = _event(b, family + '-authorization')['attributes']
    if family == 'sign_in':
        _event(b, 'sign_in-trigger')['attributes']['ip'] = '192.0.2.44'
        auth.update(reference='VPN-CHANGE-2041', actor='Synthetic identity operations owner')
        _event(b, 'sign_in-authorization')['raw_text'] = 'Synthetic change record identifies 192.0.2.44 as planned corporate VPN egress. Only the listed sign-in is authorized.'
        if case_id == 'case-02':
            _add(b, 'mailbox-forwarding', 'account_change',
                 {'change': 'mailbox_forwarding', 'external': True}, 6)
        elif case_id == 'case-03':
            next(s for s in b['sources'] if s['template'] == 'account_activity').update(
                outcome='unavailable', complete=False)
    elif family == 'phishing':
        url = 'https://awareness.example/campaign/september'
        message = _event(b, 'phishing-trigger')['attributes']
        message.update(sender='training@awareness.example', subject='September awareness exercise',
                       observables=[{'type': 'url', 'value': url}])
        _add(b, 'simulation-click', 'click', {'message_id': 'phishing-trigger', 'action': 'allowed'}, 4)
        auth.update(reference='AWARENESS-2045', actor='Synthetic awareness program owner')
        # The approval is asserted before all activity; the source records it after the click.
        _event(b, 'phishing-authorization')['occurred_at'] = '2026-09-07T10:05:00Z'
        auth['authorized_event_ids'].append('simulation-click')
        if case_id == 'case-06':
            message.update(sender='documents@partner.example', subject='Shared document',
                           observables=[{'type': 'url', 'value': 'https://partner.example/shared/42'}])
            b['events'] = [e for e in b['events'] if e['kind'] != 'authorization']
            next(s for s in b['sources'] if s['template'] == 'interactions').update(
                outcome='truncated', complete=False)
            attrs = intelligence_attributes('phishing-trigger', 'unknown')
            attrs.update(observable_value='https://partner.example/shared/42', confidence='unknown',
                         rationale='Synthetic exact URL record has no conclusive verdict.')
            _add(b, 'document-url-assessment', 'indicator', attrs, 7)
    else:
        auth.update(reference='INVENTORY-2047', actor='Synthetic endpoint operations owner')
        if case_id == 'case-07':
            _add(b, 'inventory-upload', 'connection',
                 {'process_id': 'endpoint-trigger', 'destination': 'https://inventory.example/upload'}, 3)
            auth['authorized_event_ids'].append('inventory-upload')
            _event(b, 'endpoint-authorization')['occurred_at'] = '2026-09-07T10:04:00Z'
        elif case_id == 'case-08':
            _add(b, 'second-process', 'process',
                 {'name': 'document-viewer.exe', 'command_line': 'document-viewer.exe --open invoice',
                  'parent': 'explorer.exe', 'observables': [{'type': 'sha256', 'value': 'b' * 64}]}, 5)
            _add(b, 'second-connection', 'connection',
                 {'process_id': 'second-process', 'destination': 'https://files.example/session'}, 6)
            b['alerts'][0]['trigger_ids'].append('second-process')
            attrs = intelligence_attributes('second-process', family='endpoint')
            attrs.update(observable_value='b' * 64, assessed_at='2026-09-07T10:06:00Z',
                         rationale='Synthetic provider labels the second executable exact hash malicious.')
            _add(b, 'second-process-hash', 'indicator', attrs, 7)
        else:
            auth['status'] = 'revoked'
            _event(b, 'endpoint-authorization')['raw_text'] = 'Synthetic maintenance approval was revoked; this record does not establish authorized execution.'
            next(s for s in b['sources'] if s['template'] == 'network').update(
                outcome='unavailable', complete=False)
    IncidentBundle.from_dict(b)
    return b


# Text and source references are deliberately host-only; no expected answer is imported.
_RUBRICS = {
    'case-01': ('close', 'complete', [
        ('vpn_access', 'Successful MFA sign-in uses the VPN egress IP named in the imported change record.', ['sign_in-trigger', 'sign_in-authorization']),
        ('scoped_approval', 'The verified identity-owner assertion covers this exact sign-in, entities and time.', ['sign_in-authorization'])],
        ('source_trust', 'Imported VPN ownership and authorization assertions have not been independently verified.', ['sign_in-authorization']),
        ['mfa_proves_no_compromise', 'prior_case_authorizes_current_signin']),
    'case-02': ('escalate', 'complete', [
        ('access_then_change', 'External mailbox forwarding is recorded after successful access on the same entities.', ['sign_in-trigger', 'mailbox-forwarding']),
        ('limited_scope', 'The VPN change assertion covers the sign-in but excludes the forwarding event.', ['sign_in-authorization', 'mailbox-forwarding'])],
        ('actor_unknown', 'The records do not establish who caused forwarding or whether data left the mailbox.', ['mailbox-forwarding']),
        ['data_was_exfiltrated', 'vpn_approval_authorizes_forwarding', 'attacker_identity_is_known']),
    'case-03': (None, 'needs_review', [
        ('access_seen', 'The sign-in is successful and has a scoped imported authorization.', ['sign_in-trigger', 'sign_in-authorization'])],
        ('account_gap', 'Account audit collection is unavailable, so subsequent account changes are unknown.', []),
        ['no_account_changes_occurred', 'successful_empty_account_query', 'authorization_overrides_missing_source']),
    'case-05': ('close', 'complete', [
        ('simulation_delivery', 'The reported simulation message was delivered to inbox.', ['phishing-trigger', 'phishing-delivery']),
        ('scoped_click', 'The allowed click joins this message and is explicitly within the awareness authorization.', ['simulation-click', 'phishing-trigger', 'phishing-authorization'])],
        ('credential_submission', 'An allowed click does not establish credential submission.', ['simulation-click']),
        ['credentials_were_submitted', 'email_authentication_proves_safe', 'all_future_campaign_messages_authorized']),
    'case-06': (None, 'needs_review', [
        ('delivered_document', 'The document email was delivered and a linked allowed click is present in the partial export.', ['phishing-trigger', 'phishing-delivery', 'simulation-click']),
        ('unknown_verdict', 'The exact URL provider assessment has an unknown verdict.', ['document-url-assessment'])],
        ('interaction_gap', 'The interaction source is truncated; the recorded click does not establish the complete interaction history.', ['simulation-click']),
        ['unknown_reputation_means_benign', 'no_other_interactions', 'credentials_were_stolen']),
    'case-07': ('close', 'complete', [
        ('inventory_activity', 'The inventory process has two explicitly linked service connections.', ['endpoint-trigger', 'endpoint-connection', 'inventory-upload']),
        ('full_scope', 'The endpoint-owner authorization covers the process and both connection event IDs.', ['endpoint-authorization'])],
        ('authorization_trust', 'The imported endpoint-owner assertion has not been independently authenticated.', ['endpoint-authorization']),
        ['powershell_is_always_benign', 'all_device_activity_is_authorized']),
    'case-08': ('escalate', 'complete', [
        ('two_processes', 'The inventory execution and second executable have distinct process IDs and hashes.', ['endpoint-trigger', 'second-process']),
        ('second_network', 'The later session connection belongs to the second process.', ['second-process', 'second-connection']),
        ('exact_second_hash', 'A currently valid provider assertion labels the second process exact hash malicious.', ['second-process', 'second-process-hash']),
        ('approval_limited', 'The inventory authorization excludes the second process and its connection.', ['endpoint-authorization', 'second-process', 'second-connection'])],
        ('impact_unknown', 'The provider assertion and network event do not establish execution impact or exfiltration.', ['second-process-hash', 'second-connection']),
        ['inventory_hash_is_malicious', 'both_processes_authorized', 'data_exfiltration_confirmed']),
    'case-09': (None, 'needs_review', [
        ('process_seen', 'Inventory execution is recorded but the relevant maintenance authorization is revoked.', ['endpoint-trigger', 'endpoint-authorization'])],
        ('network_gap', 'The network export is unavailable; connection activity cannot be assessed from retrieved evidence.', []),
        ['revoked_approval_authorizes_execution', 'no_network_activity', 'malicious_execution_confirmed'])}


def get_expectations(case_id):
    bundle = get_case(case_id)
    recommendation, status, facts, unknown, forbidden = _RUBRICS[case_id]
    events = {e['id']: e for e in bundle['events']}
    def entry(row):
        key, text, ids = row
        templates = sorted({events[i]['source_id'].removeprefix('source-') for i in ids})
        if not ids:
            templates = ['account_activity' if case_id == 'case-03' else 'network']
        return {'id': key, 'text': text, 'event_ids': list(ids), 'templates': templates}
    gap = entry(unknown)
    gap['reason'] = 'Draft synthetic case boundary; source absence or assertions do not establish the omitted conclusion.'
    return {'schema_version': 1, 'case_id': case_id, 'status': 'draft_teaching_case',
            'bundle_sha256': sha(canonical(bundle)), 'recommendation': recommendation,
            'investigation_status': status,
            'outcome_rationale': 'Draft expectation under the current deterministic playbook; requires independent case acceptance and does not establish analyst consensus.',
            'facts': [entry(f) for f in facts], 'unknowns': [gap],
            'forbidden_claims': list(forbidden)}
