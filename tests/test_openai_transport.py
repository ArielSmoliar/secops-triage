"""No paid calls: fake HTTPS and real SDK/SQLite/fixture integration."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import importlib.util
import json
import ssl
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from migration_proof.agent.contracts import Limits
from migration_proof.agent.journal import Journal
from migration_proof.agent.openai_preflight import OpenAIPlan, MODEL_ID
from migration_proof.agent.spend import SpendLedger
from migration_proof.core.contracts import Rejected
from migration_proof.core.store import Store

HAS_STRANDS = importlib.util.find_spec('strands') is not None
if HAS_STRANDS:
    from migration_proof.agent.openai_model import OpenAIModel, _post, payload, parse_response, validate_key
    from migration_proof.agent.offline_model import OfflineModel
    from migration_proof.agent.runtime import execute_session
    from migration_proof.agent.runner import run_openai


def response(content=None, call=None):
    message = {"role": "assistant", "content": content}
    if call:
        message['tool_calls'] = [{"id": "call_test", "type": "function", "function": {
            "name": call['name'], "arguments": json.dumps(call['input'])}}]
    return {"model": MODEL_ID, "service_tier": "default", "usage": {
        "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        "choices": [{"finish_reason": "tool_calls" if call else "stop", "message": message}]}


class LedgerFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()))
        self.store = Store(Path(self.temp.name) / 'store')
        self.run = self.store.create_run('faulty')
        self.ledger = SpendLedger(self.store)
        self.journal = Journal(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def grant(self, plan=None):
        return self.ledger.authorize(self.run['run_id'], self.run['token'], plan or OpenAIPlan(), 'test-owner')

    def start(self, plan=None):
        grant = self.grant(plan)
        session = self.journal.start(self.run['run_id'], self.run['token'], Limits(model_calls=8), model_id=MODEL_ID)
        self.ledger.claim(self.run['run_id'], self.run['token'], grant, session)
        return grant, session

    def report(self, grant):
        return self.ledger.read(self.run['run_id'], self.run['token'], grant)


class SpendTests(LedgerFixture):
    def test_grant_requires_owner_fresh_faulty_and_once_only(self):
        with self.assertRaises(Rejected):
            self.ledger.authorize(self.run['run_id'], 'wrong', OpenAIPlan(), 'owner')
        good = self.store.create_run('corrected')
        with self.assertRaises(Rejected):
            self.ledger.authorize(good['run_id'], good['token'], OpenAIPlan(), 'owner')
        self.grant()
        with self.assertRaises(Rejected):
            self.grant()

    def test_invalid_authorization_and_stale_pricing(self):
        for actor, ttl in (('', 600), ('owner', True), ('owner', 0), ('owner', 901)):
            with self.assertRaises(Rejected):
                self.ledger.authorize(self.run['run_id'], self.run['token'], OpenAIPlan(), actor, ttl_seconds=ttl)
        with patch('migration_proof.agent.spend.preflight', return_value={'pricing_fresh': False}), self.assertRaises(Rejected):
            self.grant()

    def test_reserve_before_dispatch_usage_and_non_refundable_budget(self):
        grant, session = self.start(OpenAIPlan(model_calls=1))
        request, plan = self.ledger.reserve(session)
        self.assertEqual(self.report(grant)['reserved_microusd'], plan.per_call_microusd)
        self.ledger.settle(session, request, response()['usage'])
        report = self.report(grant)
        self.assertEqual(report['reported_estimate_microusd'], 72)
        self.assertEqual(report['reserved_microusd'], 422308)
        self.assertTrue(report['usage_complete'])
        with self.assertRaises(Rejected):
            self.ledger.reserve(session)
        with self.assertRaises(Rejected):
            self.ledger.settle(session, request, response()['usage'])

    def test_concurrent_reservations_only_one_pending(self):
        grant, session = self.start()
        def reserve():
            try:
                return self.ledger.reserve(session)[0]
            except Rejected:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: reserve(), range(8)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(len(self.report(grant)['requests']), 1)

    def test_unknown_usage_retains_reservation_and_blocks_more_calls(self):
        grant, session = self.start()
        request, _ = self.ledger.reserve(session)
        with self.assertRaises(Rejected):
            self.ledger.settle(session, request, {'prompt_tokens': True, 'completion_tokens': 20, 'total_tokens': 21})
        self.assertFalse(self.report(grant)['usage_complete'])
        self.assertEqual(self.report(grant)['reserved_microusd'], 422308)
        with self.assertRaises(Rejected):
            self.ledger.reserve(session)

    def test_missing_negative_excessive_and_inconsistent_usage(self):
        for usage in (None, {}, {'prompt_tokens': -1, 'completion_tokens': 1, 'total_tokens': 0},
                      {'prompt_tokens': 1, 'completion_tokens': 2049, 'total_tokens': 2050},
                      {'prompt_tokens': 1047577, 'completion_tokens': 1, 'total_tokens': 1047578},
                      {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 1}):
            run = self.store.create_run('faulty')
            grant = self.ledger.authorize(run['run_id'], run['token'], OpenAIPlan(), 'owner')
            session = self.journal.start(run['run_id'], run['token'], Limits(), model_id=MODEL_ID)
            self.ledger.claim(run['run_id'], run['token'], grant, session)
            request, _ = self.ledger.reserve(session)
            with self.subTest(usage=usage), self.assertRaises(Rejected):
                self.ledger.settle(session, request, usage)

    def test_cross_run_claim_read_revoke_and_settlement_rejected(self):
        grant, session = self.start()
        other = self.store.create_run('faulty')
        other_session = self.journal.start(other['run_id'], other['token'], Limits(), model_id=MODEL_ID)
        with self.assertRaises(Rejected):
            self.ledger.claim(other['run_id'], other['token'], grant, other_session)
        with self.assertRaises(Rejected):
            self.ledger.read(other['run_id'], other['token'], grant)
        with self.assertRaises(Rejected):
            self.ledger.revoke(self.run['run_id'], 'wrong', grant)
        request, _ = self.ledger.reserve(session)
        with self.assertRaises(Rejected):
            self.ledger.settle(other_session, request, response()['usage'])
        self.assertEqual(self.report(grant)['requests'][0]['status'], 'pending')

    def test_expiry_revocation_and_claim_replay(self):
        grant, session = self.start()
        with self.assertRaises(Rejected):
            self.ledger.claim(self.run['run_id'], self.run['token'], grant, session)
        with patch('migration_proof.agent.spend.time.time', return_value=10**12), self.assertRaises(Rejected):
            self.ledger.reserve(session)
        self.ledger.revoke(self.run['run_id'], self.run['token'], grant)
        with self.assertRaises(Rejected):
            self.ledger.reserve(session)

    def test_stop_closes_grant_preserves_pending_and_never_promotes(self):
        grant, session = self.start()
        self.ledger.reserve(session)
        self.journal.finish(session, 'deadline')
        report = self.report(grant)
        self.assertEqual(report['status'], 'closed')
        self.assertEqual(report['requests'][0]['status'], 'unknown')
        self.assertEqual(self.store.status(self.run['run_id'], self.run['token'])['state'], 'blocked')
        self.assertIsNone(self.journal.read(self.run['run_id'], self.run['token'], session)['cost_usd'])

    def test_process_exit_pending_request_is_preserved_on_recovery(self):
        grant = self.grant()
        code = '''import json,os,sys
from migration_proof.core.store import Store
from migration_proof.agent.spend import SpendLedger
from migration_proof.agent.journal import Journal
from migration_proof.agent.contracts import Limits
from migration_proof.agent.openai_preflight import MODEL_ID
r=json.loads(sys.stdin.read()); s=Store(r['root']); j=Journal(s); l=SpendLedger(s)
a=j.start(r['run_id'],r['token'],Limits(),model_id=MODEL_ID)
l.claim(r['run_id'],r['token'],r['grant'],a); l.reserve(a); os._exit(77)
'''
        result = subprocess.run([sys.executable, '-B', '-c', code], input=json.dumps({**self.run, 'root': str(self.store.root), 'grant': grant}), text=True, timeout=10)
        self.assertEqual(result.returncode, 77)
        recovered = Journal(Store(self.store.root))
        with self.assertRaises(Rejected):
            recovered.start(self.run['run_id'], self.run['token'], Limits())
        report = self.report(grant)
        self.assertEqual(report['status'], 'closed')
        self.assertEqual(report['requests'][0]['status'], 'unknown')
        self.assertEqual(report['reserved_microusd'], 422308)


    def test_failure_finalization_is_atomic_with_grant_and_run(self):
        grant, session = self.start()
        self.ledger.reserve(session)
        with closing(sqlite3.connect(self.store.root / 'state.sqlite3')) as db, db:
            db.execute("CREATE TRIGGER fail_grant BEFORE UPDATE ON inference_grants BEGIN SELECT RAISE(ABORT,'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.journal.finish(session, 'deadline')
        self.assertEqual(self.journal.row(session)['status'], 'running')
        self.assertEqual(self.report(grant)['status'], 'claimed')
        self.assertEqual(self.report(grant)['requests'][0]['status'], 'pending')
        with closing(sqlite3.connect(self.store.root / 'state.sqlite3')) as db, db:
            db.execute('DROP TRIGGER fail_grant')
        self.journal.finish(session, 'deadline')
        self.assertEqual(self.report(grant)['status'], 'closed')

    def test_price_expiry_after_grant_prevents_reservation(self):
        grant, session = self.start()
        with patch('migration_proof.agent.spend.preflight', return_value={'pricing_fresh':False}), self.assertRaises(Rejected):
            self.ledger.reserve(session)
        self.assertEqual(self.report(grant)['requests'], [])

    def test_grant_rejects_candidate_change_before_claim(self):
        grant = self.grant()
        with self.store._locked() as db:
            self.store._invalidate(db, self.run['run_id'], 'test candidate replacement')
        self.store.replace_candidate(self.run['run_id'], self.run['token'], 'corrected', 'owner')
        session = self.journal.start(self.run['run_id'], self.run['token'], Limits(), model_id=MODEL_ID)
        with self.assertRaises(Rejected):
            self.ledger.claim(self.run['run_id'], self.run['token'], grant, session)
        self.assertEqual(self.report(grant)['requests'], [])


@unittest.skipUnless(HAS_STRANDS, 'install the locked agent extra')
class TransportTests(LedgerFixture):
    def fake_completion(self, body, key):
        request = json.loads(body)
        self.sent.append(request)
        last = request['messages'][-1]
        messages = [] if self.script.last_tool is None else [{'content': [{'toolResult': {'content': json.loads(last['content'])}}]}]
        value = self.script._next(messages)
        if 'name' in value:
            self.script.last_tool = value['name']
            return response(call=value)
        return response(content=json.dumps(value))

    def test_real_strands_loop_fake_openai_real_fixture_four_tools(self):
        grant, session = self.start()
        self.sent = []
        self.script = OfflineModel({'run_id': self.run['run_id'], 'version': 'faulty'})
        model = OpenAIModel(self.ledger, session, 'secret-test-canary')
        with patch('migration_proof.agent.openai_model._post', side_effect=self.fake_completion):
            result = asyncio.run(execute_session(self.store, self.run['run_id'], self.run['token'], session, model))
        self.assertEqual(result['status'], 'completed', result)
        self.assertFalse(result['summary']['ready'])
        self.assertEqual(result['summary']['assessment']['provider_mode'], 'openai_api')
        self.assertEqual({e['label'] for e in result['events'] if e['kind']=='tool'},
                         {'inspect_candidate','run_baseline_tests','compare_tenant_boundary','apply_safe_patch'})
        self.assertEqual(len(self.sent), 7)
        self.assertTrue(self.report(grant)['usage_complete'])
        self.assertEqual(self.report(grant)['reported_estimate_microusd'], 504)
        self.assertNotIn('secret-test-canary', json.dumps(self.sent))
        self.assertNotIn(self.run['token'], json.dumps(self.sent))
        with closing(sqlite3.connect(self.store.root / 'state.sqlite3')) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM approvals').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM promotions').fetchone()[0], 0)
            self.assertNotIn('secret-test-canary', '\n'.join(db.iterdump()))
        for req in self.sent:
            self.assertEqual(req['model'], MODEL_ID)
            self.assertEqual(req['max_completion_tokens'], 2048)
            self.assertFalse(req['parallel_tool_calls'])
            self.assertFalse(req['store'])
            self.assertEqual(req['service_tier'], 'default')

    def test_network_failure_has_one_attempt_and_keeps_reservation(self):
        grant, session = self.start()
        model = OpenAIModel(self.ledger, session, 'secret-canary')
        with patch('migration_proof.agent.openai_model._post', side_effect=RuntimeError('secret-canary')) as post:
            result = asyncio.run(execute_session(self.store, self.run['run_id'], self.run['token'], session, model))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result['status'], 'stopped')
        self.assertNotIn('secret-canary', json.dumps(result))
        self.assertEqual(self.report(grant)['requests'][0]['status'], 'unknown')

    def test_no_grant_means_no_dispatch(self):
        session = self.journal.start(self.run['run_id'], self.run['token'], Limits(), model_id=MODEL_ID)
        model = OpenAIModel(self.ledger, session, 'secret-canary')
        with patch('migration_proof.agent.openai_model._post') as post:
            result = asyncio.run(execute_session(self.store, self.run['run_id'], self.run['token'], session, model))
        post.assert_not_called()
        self.assertEqual(result['status'], 'stopped')

    def test_forbidden_tool_rejected_by_real_guard(self):
        grant, session = self.start()
        model = OpenAIModel(self.ledger, session, 'test-key')
        with patch('migration_proof.agent.openai_model._post', return_value=response(call={'name':'approve','input':{}})):
            result = asyncio.run(execute_session(self.store, self.run['run_id'], self.run['token'], session, model))
        self.assertEqual(result['reason'], 'invalid_tool')
        self.assertEqual(result['status'], 'stopped')

    def test_https_fixed_destination_caps_and_no_redirect_retry(self):
        conn = MagicMock()
        answer = conn.getresponse.return_value
        answer.status = 200
        answer.getheader.return_value = 'identity'
        answer.read.return_value = json.dumps(response(content='{}')).encode()
        with patch('migration_proof.agent.openai_model.http.client.HTTPSConnection', return_value=conn) as factory:
            _post(b'{}', 'test-key')
        self.assertEqual(factory.call_args.args, ('api.openai.com',))
        self.assertEqual(conn.request.call_args.args[:2], ('POST','/v1/chat/completions'))
        answer.read.assert_called_once_with(65537)
        conn.close.assert_called_once()
        for status in (301, 401, 429, 500):
            conn.reset_mock(); answer.status = status
            with patch('migration_proof.agent.openai_model.http.client.HTTPSConnection', return_value=conn), self.assertRaises(Rejected):
                _post(b'{}', 'test-key')
            self.assertEqual(conn.request.call_count, 1)
            answer.read.assert_not_called()
        answer.status = 200; answer.read.return_value = b'x' * 65537
        with patch('migration_proof.agent.openai_model.http.client.HTTPSConnection', return_value=conn), self.assertRaises(Rejected):
            _post(b'{}', 'test-key')

    def test_response_identity_usage_shape_and_incomplete_output(self):
        original = response(content='{}')
        for field, value in (('model','different'), ('service_tier','priority'), ('choices',[])):
            bad = copy.deepcopy(original); bad[field] = value
            with self.assertRaises(Rejected):
                parse_response(bad)
        for reason in ('length','content_filter'):
            bad = copy.deepcopy(original); bad['choices'][0]['finish_reason'] = reason
            with self.assertRaises(Rejected):
                parse_response(bad)

    def test_credentials_and_runner_require_valid_grant(self):
        for key in ('', 'x\nHeader: bad', 'x'*513, None):
            with self.assertRaises(Rejected):
                validate_key(key)
        with patch('subprocess.Popen') as spawn, self.assertRaises(Rejected):
            run_openai(self.store, self.run['run_id'], self.run['token'], 'missing', api_key='test-key')
        spawn.assert_not_called()

    def test_request_rejects_multimodal_extra_tools_and_oversize(self):
        specs = [{'name': name, 'description': 'test', 'inputSchema': {'json': {'type': 'object'}}}
                 for name in ('inspect_candidate','run_baseline_tests','compare_tenant_boundary','apply_safe_patch')]
        for messages, tools in (([{'role':'user','content':[{'image':{}}]}], specs),
                                ([{'role':'user','content':[{'text':'ok'}]}], specs + [specs[0]]),
                                ([{'role':'user','content':[{'text':'x'*262144}]}], specs)):
            with self.assertRaises(Rejected):
                payload(messages, tools, 'fixed', 2048)

    def test_malformed_usage_stops_real_loop_before_any_tool(self):
        grant, session = self.start()
        bad = response(call={'name':'inspect_candidate','input':{'run_id':self.run['run_id'],'version':'faulty'}})
        bad.pop('usage')
        with patch('migration_proof.agent.openai_model._post', return_value=bad):
            result = asyncio.run(execute_session(self.store, self.run['run_id'], self.run['token'], session,
                                                OpenAIModel(self.ledger, session, 'test-key')))
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['tool_calls'], 0)
        self.assertFalse(self.report(grant)['usage_complete'])

    def test_supervised_worker_key_stdin_and_durable_usage(self):
        grant = self.grant()
        fake = response(content=json.dumps({'recommendation':'blocked','reason_codes':['insufficient_evidence']}))
        inspect = response(call={'name':'inspect_candidate','input':{'run_id':self.run['run_id'],'version':'faulty'}})
        code = ('import migration_proof.agent.openai_model as m\n'
                'answers=iter(' + repr([inspect, fake]) + ')\n'
                'm._post=lambda body,key: next(answers)\n'
                'from migration_proof.agent.worker import main\nmain()\n')
        original_popen = subprocess.Popen
        captured = []
        def spawn(args, **kwargs):
            captured.append((args, kwargs))
            return original_popen([sys.executable, '-B', '-c', code], **kwargs)
        with patch('migration_proof.agent.runner.subprocess.Popen', side_effect=spawn):
            result = run_openai(self.store, self.run['run_id'], self.run['token'], grant, api_key='isolated-secret-canary')
        self.assertEqual(result['status'], 'completed', result)
        self.assertFalse(result['summary']['ready'])
        self.assertEqual(result['spend']['reported_estimate_microusd'], 144)
        self.assertEqual(result['spend']['status'], 'closed')
        self.assertNotIn('isolated-secret-canary', repr(captured))
        self.assertNotIn('OPENAI_API_KEY', captured[0][1]['env'])
        self.assertTrue(captured[0][1]['pass_fds'])
        self.assertTrue(captured[0][1]['start_new_session'])

    def test_supervisor_kills_hanging_provider_retains_uncertainty(self):
        from migration_proof.agent.runner import _run
        grant = self.grant()
        code = ('import time\nimport migration_proof.agent.openai_model as m\n'
                'm._post=lambda body,key: time.sleep(60)\n'
                'from migration_proof.agent.worker import main\nmain()\n')
        original_popen = subprocess.Popen
        children = []
        def spawn(args, **kwargs):
            child = original_popen([sys.executable, '-B', '-c', code], **kwargs)
            children.append(child)
            return child
        with patch('migration_proof.agent.runner.subprocess.Popen', side_effect=spawn):
            result = _run(self.store, self.run['run_id'], self.run['token'],
                          Limits(model_calls=8, wall_seconds=3), grant_id=grant, api_key='test-key')
        self.assertEqual(result['reason'], 'deadline', result)
        self.assertIsNotNone(children[0].poll())
        self.assertEqual(result['spend']['requests'][0]['status'], 'unknown')
        self.assertEqual(result['spend']['reserved_microusd'], 422308)

    def test_tls_verifies_host_with_pinned_ca_bundle_when_system_roots_missing(self):
        conn = MagicMock()
        answer = conn.getresponse.return_value
        answer.status = 200
        answer.getheader.return_value = 'identity'
        answer.read.return_value = json.dumps(response(content='{}')).encode()
        with patch.dict('os.environ', {'SSL_CERT_FILE':'/missing-ca-file', 'SSL_CERT_DIR':'/missing-ca-directory'}), \
             patch('migration_proof.agent.openai_model.http.client.HTTPSConnection', return_value=conn) as factory:
            _post(b'{}', 'test-key')
        context = factory.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreater(context.cert_store_stats()['x509_ca'], 0)
