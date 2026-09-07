"""Match normalized evidence only. No network enrichment or threat adjudication."""
import ipaddress
from urllib.parse import urlsplit

from .contracts import instant, observable, Rejected


def activity_observables(target):
    attrs = target['attributes']
    if target['kind'] in ('message', 'process'):
        return {(v['type'], v['value']) for v in attrs['observables']}
    if target['kind'] == 'sign_in':
        return {('ip', attrs['ip'])}
    if target['kind'] == 'connection':
        value = attrs['destination']
        if value.startswith(('http://', 'https://')):
            return {('url', value)}
        try:
            ipaddress.ip_address(value)
            return {('ip', value)}
        except ValueError:
            return {('domain', value.lower())}
    return set()


def match_issues(indicator, target, observed_at):
    a = indicator['attributes']
    issues = []
    if instant(a['expires_at']) <= instant(observed_at):
        issues.append('intelligence_expired_at_snapshot')
    values = activity_observables(target)
    try:
        for kind, value in values:
            observable(kind, value)
    except Rejected:
        return issues + ['invalid_target_observable']
    value = (a['observable_type'], a['observable_value'])
    if a['match_basis'] == 'domain_reputation':
        domains = {v for k, v in values if k == 'domain'}
        domains.update(urlsplit(v).hostname for k, v in values if k == 'url')
        if a['observable_value'] not in domains:
            issues.append('observable_does_not_match_target')
        issues.append('domain_reputation_only')
    elif value not in values:
        issues.append('observable_does_not_match_target')
    elif a['observable_type'] == 'domain':
        issues.append('domain_reputation_only')
    return issues
