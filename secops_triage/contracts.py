"""Strict input contracts. Source text is data; no executable query language."""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
import json
import re


class Rejected(ValueError):
    pass


FAMILIES = ('sign_in', 'phishing', 'endpoint')
TEMPLATES = {
    'authentication': {'sign_in'},
    'account_activity': {'account_change'},
    'messages': {'message'},
    'delivery': {'delivery'},
    'interactions': {'click'},
    'processes': {'process'},
    'network': {'connection'},
    'intelligence': {'indicator'},
    'business_context': {'authorization'},
    'related_cases': {'case_reference'},
}
REQUIRED = {
    'sign_in': ('authentication', 'account_activity', 'intelligence', 'business_context'),
    'phishing': ('messages', 'delivery', 'interactions', 'intelligence', 'business_context'),
    'endpoint': ('processes', 'network', 'intelligence', 'business_context'),
}
ATTRS = {
    'sign_in': {'result': str, 'ip': str, 'device': str, 'mfa': bool},
    'account_change': {'change': str, 'external': bool},
    'message': {'sender': str, 'subject': str, 'authentication': str},
    'delivery': {'message_id': str, 'location': str},
    'click': {'message_id': str, 'action': str},
    'process': {'name': str, 'command_line': str, 'parent': str},
    'connection': {'process_id': str, 'destination': str},
    'indicator': {'target_id': str, 'verdict': str, 'indicator': str},
    'authorization': {'target_id': str, 'actor': str, 'reference': str,
                      'status': str, 'authority_role': str, 'authority_verified': bool,
                      'approved_at': str, 'valid_from': str, 'valid_until': str,
                      'authorized_event_ids': list, 'authorized_entity_ids': list},
    'case_reference': {'case_id': str, 'disposition': str, 'summary': str},
}
OUTCOMES = ('success', 'unavailable', 'unauthorized', 'timeout', 'truncated', 'malformed')
TOOL_NAMES = ('inspect_incident', 'lookup_entity', 'query_activity', 'find_related_cases')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}', value):
        raise Rejected('invalid identifier')


def bounded(value, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value.encode('utf-8')) > limit:
        raise Rejected('invalid bounded text')


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
        raise Rejected('timestamp must be UTC YYYY-MM-DDTHH:MM:SSZ')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as e:
        raise Rejected('invalid timestamp') from e


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise Rejected('unknown or missing fields')


def strings(value, limit=32):
    if type(value) not in (tuple, list) or not 1 <= len(value) <= limit:
        raise Rejected('invalid reference list')
    for item in value:
        ident(item)
    if len(set(value)) != len(value):
        raise Rejected('duplicate reference')


@dataclass(frozen=True)
class Alert:
    id: str
    family: str
    title: str
    entity_ids: tuple[str, ...]
    trigger_ids: tuple[str, ...]

    def __post_init__(self):
        ident(self.id)
        if self.family not in FAMILIES:
            raise Rejected('unsupported alert family')
        bounded(self.title)
        strings(self.entity_ids)
        strings(self.trigger_ids)


@dataclass(frozen=True)
class Entity:
    id: str
    kind: str
    name: str
    owner: str

    def __post_init__(self):
        ident(self.id)
        if self.kind not in ('user', 'device', 'message', 'workload'):
            raise Rejected('unsupported entity type')
        bounded(self.name)
        bounded(self.owner)


@dataclass(frozen=True)
class Source:
    id: str
    tenant_id: str
    template: str
    outcome: str
    complete: bool
    start: str
    end: str

    def __post_init__(self):
        ident(self.id)
        ident(self.tenant_id)
        if self.template not in TEMPLATES or self.outcome not in OUTCOMES or type(self.complete) is not bool:
            raise Rejected('invalid source coverage')
        if instant(self.start) > instant(self.end):
            raise Rejected('inverted source coverage')


@dataclass(frozen=True)
class Event:
    id: str
    tenant_id: str
    source_id: str
    entity_ids: tuple[str, ...]
    occurred_at: str
    kind: str
    attributes: dict
    raw_text: str

    def __post_init__(self):
        ident(self.id)
        ident(self.tenant_id)
        ident(self.source_id)
        strings(self.entity_ids)
        instant(self.occurred_at)
        if self.kind not in ATTRS:
            raise Rejected('unsupported event kind')
        exact(self.attributes, ATTRS[self.kind])
        for key, typ in ATTRS[self.kind].items():
            if type(self.attributes[key]) is not typ:
                raise Rejected('invalid event attribute type')
            if typ is str:
                bounded(self.attributes[key])
        if self.kind == 'authorization':
            a = self.attributes
            if a['status'] not in ('approved', 'pending', 'revoked'):
                raise Rejected('invalid authorization status')
            if a['authority_role'] not in ('identity_owner', 'security_awareness', 'endpoint_owner', 'unknown'):
                raise Rejected('invalid authorization authority')
            if instant(a['valid_from']) > instant(a['valid_until']):
                raise Rejected('inverted authorization window')
            instant(a['approved_at'])
            strings(a['authorized_event_ids'], 200)
            strings(a['authorized_entity_ids'], 100)
        bounded(self.raw_text, 8000)
        enum = {'sign_in': ('result', ('success', 'failure')),
                'indicator': ('verdict', ('malicious', 'benign', 'unknown')),
                'delivery': ('location', ('inbox', 'quarantine', 'deleted', 'unknown')),
                'click': ('action', ('allowed', 'blocked', 'unknown'))}
        if self.kind in enum:
            field, allowed = enum[self.kind]
            if self.attributes[field] not in allowed:
                raise Rejected('invalid event value')


@dataclass(frozen=True)
class IncidentBundle:
    tenant_id: str
    source: str
    incident_id: str
    title: str
    observed_at: str
    start: str
    end: str
    alerts: tuple[Alert, ...]
    entities: tuple[Entity, ...]
    sources: tuple[Source, ...]
    events: tuple[Event, ...]
    synthetic: bool

    def __post_init__(self):
        for v in (self.tenant_id, self.source, self.incident_id):
            ident(v)
        bounded(self.title)
        start, end, observed = map(instant, (self.start, self.end, self.observed_at))
        if not start <= end <= observed or end - start > timedelta(days=7):
            raise Rejected('invalid investigation window (maximum seven days)')
        if type(self.synthetic) is not bool:
            raise Rejected('synthetic flag must be boolean')
        for items, typ, maximum in ((self.alerts, Alert, 12), (self.entities, Entity, 100),
                                    (self.sources, Source, 16), (self.events, Event, 1000)):
            if type(items) is not tuple or not 1 <= len(items) <= maximum or any(type(x) is not typ for x in items):
                raise Rejected('invalid bundle collection')
            if len({x.id for x in items}) != len(items):
                raise Rejected('duplicate record identifier')
        entities = {x.id for x in self.entities}
        sources = {x.id: x for x in self.sources}
        events = {x.id: x for x in self.events}
        if len({s.template for s in self.sources}) != len(self.sources):
            raise Rejected('one replay source per query template is required')
        if any(s.tenant_id != self.tenant_id for s in self.sources):
            raise Rejected('cross-organization source')
        for e in self.events:
            if e.tenant_id != self.tenant_id or not set(e.entity_ids) <= entities or e.source_id not in sources:
                raise Rejected('cross-scope or unknown event reference')
            s = sources[e.source_id]
            if e.kind not in TEMPLATES[s.template] or not instant(s.start) <= instant(e.occurred_at) <= instant(s.end):
                raise Rejected('event does not match source coverage')
            if instant(e.occurred_at) > observed:
                raise Rejected('future evidence')
            if e.kind == 'authorization':
                a = e.attributes
                if not set(a['authorized_event_ids']) <= events.keys() or not set(a['authorized_entity_ids']) <= entities:
                    raise Rejected('unknown authorization scope reference')
                if instant(a['approved_at']) > instant(e.occurred_at):
                    raise Rejected('authorization approval is later than its source observation')
            field = {'indicator': 'target_id', 'authorization': 'target_id',
                     'delivery': 'message_id', 'click': 'message_id', 'connection': 'process_id'}.get(e.kind)
            if field:
                target = events.get(e.attributes[field])
                if target is None or not set(e.entity_ids).intersection(target.entity_ids):
                    raise Rejected('unrelated event target')
                expected = {'delivery': 'message', 'click': 'message', 'connection': 'process'}.get(e.kind)
                if expected and target.kind != expected:
                    raise Rejected('incorrect target event type')
        for a in self.alerts:
            if not set(a.entity_ids) <= entities or not set(a.trigger_ids) <= events.keys():
                raise Rejected('unknown alert reference')
            kind = {'sign_in': 'sign_in', 'phishing': 'message', 'endpoint': 'process'}[a.family]
            if any(events[t].kind != kind or not set(events[t].entity_ids) <= set(a.entity_ids) for t in a.trigger_ids):
                raise Rejected('invalid trigger scope')

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        exact(value, cls.__dataclass_fields__)
        # Round-trip eliminates caller-owned mutable references before persistence.
        try:
            raw = canonical(value)
            if len(raw) > 2_000_000:
                raise Rejected('bundle is too large')
            v = json.loads(raw)
            for name, typ in (('alerts', Alert), ('entities', Entity), ('sources', Source), ('events', Event)):
                if type(v[name]) is not list:
                    raise Rejected('bundle collection must be a list')
                result = []
                for item in v[name]:
                    exact(item, typ.__dataclass_fields__)
                    for field in ('entity_ids', 'trigger_ids'):
                        if field in item:
                            strings(item[field])
                            item[field] = tuple(item[field])
                    result.append(typ(**item))
                v[name] = tuple(result)
            return cls(**v)
        except (TypeError, KeyError, OverflowError, RecursionError) as e:
            raise Rejected('malformed bundle') from e


@dataclass(frozen=True)
class InspectIncident:
    pass


@dataclass(frozen=True)
class LookupEntity:
    entity_id: str

    def __post_init__(self):
        ident(self.entity_id)


@dataclass(frozen=True)
class QueryActivity:
    alert_id: str
    template: str
    start: str
    end: str

    def __post_init__(self):
        ident(self.alert_id)
        if self.template not in TEMPLATES or self.template == 'related_cases':
            raise Rejected('query template not allowed')
        if instant(self.start) > instant(self.end):
            raise Rejected('inverted query window')


@dataclass(frozen=True)
class FindRelatedCases:
    alert_id: str

    def __post_init__(self):
        ident(self.alert_id)


REQUEST_TYPES = dict(zip(TOOL_NAMES, (InspectIncident, LookupEntity, QueryActivity, FindRelatedCases)))
