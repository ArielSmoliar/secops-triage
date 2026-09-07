"""Draft synthetic teaching cases. Rubrics are host-only, never bundle fields."""
from .contracts import IncidentBundle, TEMPLATES, canonical, sha
from .fixtures import scenario, intelligence_attributes

CASE_IDS = ('case-04',)


def get_case(case_id):
    """Return a fresh source snapshot; no expected answers are agent-visible."""
    if case_id not in CASE_IDS:
        raise ValueError('unknown evaluation case')
    bundle = scenario('phishing', 'unknown')
    bundle.update(incident_id='INC-2044', title='Reported document email and similar follow-up')
    bundle['events'] = []
    bundle['alerts'][0].update(id='alert-two-messages', title='User reported similar document emails',
                               trigger_ids=['message-training', 'message-followup'])

    def add(event_id, kind, attributes, minute, text):
        template = next(t for t, kinds in TEMPLATES.items() if kind in kinds)
        bundle['events'].append({'id': event_id, 'tenant_id': bundle['tenant_id'],
                                 'source_id': 'source-' + template,
                                 'entity_ids': ['user-1', 'device-1'],
                                 'occurred_at': f'2026-09-07T10:{minute:02d}:00Z',
                                 'kind': kind, 'attributes': attributes, 'raw_text': text})

    training_url = 'https://documents.example/training/document'
    followup_url = 'https://documents.example/review/document?session=second'
    for suffix, url, minute in (('training', training_url, 0), ('followup', followup_url, 5)):
        add('message-' + suffix, 'message',
            {'sender': 'support@documents.example', 'subject': 'Your requested document',
             'authentication': 'pass', 'observables': [{'type': 'url', 'value': url}]},
            minute, 'Synthetic mail export; sender and subject are identical across the two messages.')
        add('delivery-' + suffix, 'delivery',
            {'message_id': 'message-' + suffix, 'location': 'inbox'}, minute + 1,
            'Synthetic delivery export joined by message ID.')
    add('click-followup', 'click', {'message_id': 'message-followup', 'action': 'allowed'}, 7,
        'Synthetic gateway interaction: click allowed. No credential submission or account telemetry is recorded here.')
    add('authorization-training', 'authorization',
        {'target_id': 'message-training', 'actor': 'Synthetic awareness program owner',
         'reference': 'TRAIN-2044', 'status': 'approved', 'authority_role': 'security_awareness',
         'authority_verified': True, 'approved_at': '2026-09-07T09:00:00Z',
         'valid_from': bundle['start'], 'valid_until': bundle['end'],
         'authorized_event_ids': ['message-training', 'delivery-training'],
         'authorized_entity_ids': ['user-1', 'device-1']}, 2,
        'Synthetic authorization export limited to the listed message and delivery IDs.')
    stale = intelligence_attributes('message-followup')
    stale.update(verdict='benign', observable_type='domain', observable_value='documents.example',
                 match_basis='domain_reputation', assessed_at='2026-09-07T09:30:00Z',
                 expires_at='2026-09-07T10:00:00Z', provider='Synthetic domain reputation cache',
                 rationale='Historical domain-level benign assessment; does not assess either exact URL.')
    add('intelligence-stale-domain', 'indicator', stale, 8, 'Synthetic cached provider assessment.')
    exact = intelligence_attributes('message-followup')
    exact.update(observable_value=followup_url, assessed_at='2026-09-07T10:08:00Z',
                 provider='Synthetic URL analysis provider',
                 rationale='Synthetic exact-URL analysis labels a credential-collection landing page malicious; no user submission is established.')
    add('intelligence-exact-followup', 'indicator', exact, 9,
        'Synthetic provider assertion, not independently verified provider accuracy.')
    add('prior-training-case', 'case_reference',
        {'case_id': 'PRIOR-TRAIN-2043', 'disposition': 'closed-benign',
         'summary': 'Earlier awareness campaign was authorized; this does not authorize later messages.'},
        1, 'Synthetic prior-case context.')
    IncidentBundle.from_dict(bundle)
    return bundle


def case_digest(case_id):
    return sha(canonical(get_case(case_id)))


def get_expectations(case_id):
    """Inspectable draft rubric, kept out of get_case and all tool results."""
    digest = case_digest(case_id)
    def fact(key, text, event_ids, templates):
        return {'id': key, 'text': text, 'event_ids': event_ids, 'templates': templates}
    return {'schema_version': 1, 'case_id': case_id, 'status': 'draft_teaching_case',
            'bundle_sha256': digest, 'recommendation': 'escalate',
            'investigation_status': 'needs_review',
            'outcome_rationale': 'Fresh exact-URL source evidence supports escalation of the follow-up message. The implementation conservatively retains the expired, domain-only benign assessment as a gap, producing needs_review. This is a policy expectation, not an independently conflicting exact-URL verdict or human analyst consensus.',
            'facts': [
                fact('distinct_messages', 'Two messages share sender and subject but have different IDs and exact URLs.',
                     ['message-training', 'message-followup'], ['messages']),
                fact('delivered_followup', 'The second message was delivered to inbox.',
                     ['message-followup', 'delivery-followup'], ['messages', 'delivery']),
                fact('clicked_followup', 'An allowed click is linked to the second message, not the training message.',
                     ['message-followup', 'click-followup'], ['messages', 'interactions']),
                fact('authorization_limited', 'The imported authorization covers only the first message and its delivery.',
                     ['authorization-training', 'message-training', 'delivery-training'], ['business_context', 'messages', 'delivery']),
                fact('stale_domain', 'The benign domain assessment is expired at snapshot time and is not an exact URL assessment.',
                     ['intelligence-stale-domain'], ['intelligence']),
                fact('exact_followup', 'A provider labels the second message exact URL malicious with validity covering the snapshot.',
                     ['message-followup', 'intelligence-exact-followup'], ['messages', 'intelligence'])],
            'unknowns': [{'id': 'credential_theft', 'text': 'Credential submission and account compromise remain unknown.',
                          'event_ids': ['click-followup', 'intelligence-exact-followup'],
                          'templates': ['interactions', 'intelligence'],
                          'reason': 'A click and provider landing-page assertion do not establish submission; no corresponding telemetry exists in this phishing playbook.'},
                         {'id': 'provider_accuracy', 'text': 'Provider accuracy has not been independently established.',
                          'event_ids': ['intelligence-exact-followup', 'intelligence-stale-domain'],
                          'templates': ['intelligence'],
                          'reason': 'All provider records are synthetic imported assertions.'}],
            'forbidden_claims': ['credentials_were_stolen', 'account_was_compromised',
                                 'training_message_was_clicked', 'both_messages_were_authorized',
                                 'domain_reputation_clears_exact_url', 'unqueried_account_telemetry_is_clean']}
