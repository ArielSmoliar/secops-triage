import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from secops_triage.store import Store
from secops_triage.contracts import Rejected
from secops_triage.fixtures import scenario, mixed_incident

try:
    import strands
except ImportError:
    strands = None


@unittest.skipUnless(strands, 'optional Strands dependency required')
class SecOpsAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(self.root / 'store')
        self.token = secrets.token_hex(32)
    def tearDown(self):
        self.tmp.cleanup()
    def ingest(self, bundle=None):
        return self.store.ingest(bundle or scenario('phishing', 'malicious'), self.token, secrets.token_hex(8))
    def rows(self, table):
        with self.store._locked() as db:
            return [dict(r) for r in db.execute('SELECT * FROM '+table)]
    def execute(self, run, **kwargs):
        from secops_triage.agent import execute_session
        return execute_session(self.store, run, self.token, **kwargs)

    def test_supervised_sdk_three_families_and_host_review(self):
        from secops_triage.agent_runner import run_agent
        run = self.ingest(mixed_incident())
        packet = run_agent(self.store, run, self.token)
        self.assertEqual(packet['recommendation'], 'escalate')
        self.assertEqual(len(packet['evidence']), 19)
        self.assertEqual(packet['agent_assessment']['recommendation'], 'escalate')
        self.assertIn('scripted', packet['execution'])
        self.assertEqual(self.rows('secops_agent_sessions')[0]['model_calls'], 20)
        self.store.review(run, self.token, packet['packet_hash'], 'analyst', 'escalate', 'reviewed', 'review1')
        self.assertEqual(self.store.status(run, self.token)['upstream_status'], 'unchanged')

    def test_source_gap_and_authorized_paths(self):
        for family in ('sign_in','phishing','endpoint'):
            for name,expected in (('authorized','close'),('unavailable',None),('contradictory','escalate')):
                with self.subTest(family=family,name=name):
                    p=self.execute(self.ingest(scenario(family,name)))
                    self.assertEqual(p['recommendation'],expected)

    def test_unknown_tools_and_extra_scope_arguments_fail_closed(self):
        from secops_triage.agent import fixture_model
        for attack in ({'name':'approve','input':{}},
                       {'name':'inspect_incident','input':{'tenant_id':'foreign'}},
                       {'name':'lookup_entity','input':{'entity_id':'foreign'}},
                       {'name':'query_activity','input':{'alert_id':'alert-phishing','template':'messages','start':'2026-01-01T00:00:00Z','end':'2026-09-07T10:30:00Z'}}):
            run=self.ingest()
            with self.assertRaises(Rejected):
                self.execute(run,model_factory=lambda b:fixture_model(b,attack))
            self.assertEqual(self.store.status(run,self.token)['state'],'failed')
            with self.assertRaises(Rejected): self.store.packet(run,self.token)

    def test_forged_final_citation_and_extra_fields_fail(self):
        from secops_triage.agent import fixture_model
        for final in ({'recommendation':'close','findings':[{'evidence_id':'fake','event_id':'fake','summary':'safe'}]},
                      {'recommendation':'close','findings':[], 'approved':True}):
            with self.assertRaises(Rejected):
                self.execute(self.ingest(),model_factory=lambda b:fixture_model(b,final))

    def test_disagreement_blocks_close(self):
        from secops_triage.agent import fixture_model
        def factory(bundle):
            model=fixture_model(bundle); original=model._next
            def next_response(messages):
                result=original(messages)
                if 'recommendation' in result: result['recommendation']='escalate'
                return result
            model._next=next_response
            return model
        p=self.execute(self.ingest(scenario('endpoint','authorized')),model_factory=factory)
        self.assertIsNone(p['recommendation'])
        self.assertEqual(p['investigation_status'],'needs_review')
        self.assertEqual(self.store.packet(p['run_id'],self.token),p)

    def test_model_cannot_hide_missing_checks(self):
        from secops_triage.agent import fixture_model
        def factory(bundle):
            model=fixture_model(bundle); original=model._next
            def next_response(messages):
                result=original(messages)
                if 'recommendation' in result: result['recommendation']='close'
                return result
            model._next=next_response; return model
        p=self.execute(self.ingest(scenario('endpoint','unavailable')),model_factory=factory)
        self.assertIsNone(p['recommendation'])

    def test_no_network_without_grant_and_real_data_rejected(self):
        with patch('migration_proof.agent.openai_model._post') as post:
            self.execute(self.ingest())
            with self.assertRaises(Rejected):
                self.execute(self.ingest(),grant_id='missing',api_key='fake-key')
            post.assert_not_called()
        b=scenario('endpoint');b['synthetic']=False
        with self.assertRaises(Rejected): self.execute(self.ingest(b))

    def test_grant_single_use_and_unknown_usage_no_retry(self):
        from secops_triage.agent_spend import authorize,spending
        run=self.ingest(); g=authorize(self.store,run,self.token,'test authorization')
        with patch('migration_proof.agent.openai_model._post',side_effect=RuntimeError('secret canary')) as post:
            with self.assertRaises(Rejected): self.execute(run,grant_id=g,api_key='fake-key')
            self.assertEqual(post.call_count,1)
            with self.assertRaises(Rejected): self.execute(run,grant_id=g,api_key='fake-key')
            self.assertEqual(post.call_count,1)
        spend=spending(self.store,run,self.token)
        self.assertEqual(spend['reserved_microusd'],422308)
        self.assertFalse(spend['usage_complete'])
        self.assertEqual(self.rows('secops_grants')[0]['state'],'closed')

    def test_grant_scope_expiry_and_duplicate_authorization(self):
        from secops_triage.agent_spend import authorize
        with self.assertRaises(Rejected): authorize(self.store,self.ingest(mixed_incident()),self.token,'test')
        run=self.ingest(); g=authorize(self.store,run,self.token,'test')
        with self.assertRaises(Rejected): authorize(self.store,run,self.token,'test')
        other=self.ingest()
        with patch('migration_proof.agent.openai_model._post') as post:
            with self.assertRaises(Rejected): self.execute(other,grant_id=g,api_key='fake')
            post.assert_not_called()

    def test_ledger_budget_usage_and_recovery(self):
        from secops_triage.agent_spend import authorize,Ledger,recover,spending
        run=self.ingest();g=authorize(self.store,run,self.token,'test')
        with self.store._locked() as db:
            ledger=Ledger(db,self.store._owner(db,run,self.token),g)
            for i in range(10):
                req,_=ledger.reserve(g)
                ledger.settle(g,req,{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110})
            with self.assertRaises(Rejected): ledger.reserve(g)
            ledger.close()
        self.assertEqual(spending(self.store,run,self.token)['requests'],10)
        run2=self.ingest();g2=authorize(self.store,run2,self.token,'test')
        with self.store._locked() as db:
            ledger=Ledger(db,self.store._owner(db,run2,self.token),g2); req,_=ledger.reserve(g2)
            with self.assertRaises(Rejected):ledger.settle(g2,req,{'prompt_tokens':True})
        recover(self.store)
        self.assertFalse(spending(self.store,run2,self.token)['usage_complete'])

    def test_model_call_limit(self):
        from secops_triage.agent import fixture_model
        with self.assertRaises(Rejected):
            self.execute(self.ingest(),model_factory=lambda b:fixture_model(b,{'name':'inspect_incident','input':{}}))
        self.assertLessEqual(self.rows('secops_agent_sessions')[0]['model_calls'],24)

    def test_existing_packet_not_misrepresented_as_agent_execution(self):
        run=self.ingest();self.store.investigate(run,self.token)
        with self.assertRaises(Rejected):self.execute(run)

    def test_report_model_text_is_escaped_and_separate(self):
        from secops_triage.report import markdown
        p=self.execute(self.ingest())
        report=markdown(self.store,p)
        self.assertIn('Agent assessment (untrusted)',report)
        self.assertIn('deterministic evidence checks',report)

    def test_fake_openai_transport_runs_real_sdk_and_settles_usage(self):
        from secops_triage.agent_spend import authorize,spending
        from migration_proof.agent.openai_preflight import MODEL_ID
        from secops_triage.agent import fixture_model
        from secops_triage.contracts import IncidentBundle
        b=scenario('phishing','malicious'); run=self.ingest(b)
        script=fixture_model(IncidentBundle.from_dict(b));g=authorize(self.store,run,self.token,'test')
        def post(body,key):
            payload=json.loads(body)
            self.assertEqual({t['function']['name'] for t in payload['tools']}, {'inspect_incident','lookup_entity','query_activity','find_related_cases'})
            query=next(t['function']['parameters'] for t in payload['tools'] if t['function']['name']=='query_activity')
            self.assertFalse(query['additionalProperties'])
            self.assertEqual(query['properties']['start']['enum'],[b['start']])
            self.assertEqual(set(query['properties']['template']['enum']), {'messages','delivery','interactions','intelligence','business_context'})
            self.assertNotIn(self.token,body.decode());self.assertNotIn('test-secret-key',body.decode())
            messages=[]
            if payload['messages'][-1]['role']=='tool':
                blocks=json.loads(payload['messages'][-1]['content'])
                messages=[{'content':[{'toolResult':{'content':blocks}}]}]
            result=script._next(messages)
            if 'name' in result:
                message={'role':'assistant','content':None,'tool_calls':[{'id':secrets.token_hex(8),'type':'function','function':{'name':result['name'],'arguments':json.dumps(result['input'])}}]};stop='tool_calls'
            else: message={'role':'assistant','content':json.dumps(result)};stop='stop'
            return {'model':MODEL_ID,'service_tier':'default','choices':[{'message':message,'finish_reason':stop}],
                    'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110}}
        with patch('migration_proof.agent.openai_model._post',side_effect=post):
            p=self.execute(run,grant_id=g,api_key='test-secret-key')
        self.assertEqual(p['recommendation'],'escalate')
        self.assertEqual(spending(self.store,run,self.token)['requests'],10)
        self.assertTrue(spending(self.store,run,self.token)['usage_complete'])

    def test_actual_process_crash_recovers_collection_and_session(self):
        import subprocess,sys
        from secops_triage.agent_runner import recover
        run=self.ingest()
        code = """
import json,sys,os
from secops_triage.store import Store
from secops_triage.agent import execute_session,fixture_model
v=json.load(sys.stdin)
def factory(b):
 m=fixture_model(b); original=m._next
 def next_response(messages):
  if m.index==2: os._exit(73)
  return original(messages)
 m._next=next_response
 return m
execute_session(Store(v['root']),v['run'],v['token'],model_factory=factory)
"""
        p=subprocess.run([sys.executable,'-c',code],input=json.dumps({'root':str(self.store.root),'run':run,'token':self.token}),text=True,capture_output=True)
        self.assertEqual(p.returncode,73)
        recovered=recover(self.store.root)
        self.assertEqual(recovered.status(run,self.token)['state'],'needs_review')
        self.assertEqual(self.rows('secops_agent_sessions')[0]['state'],'interrupted')
        with self.assertRaises(Rejected):recovered.packet(run,self.token)
        packet=self.execute(run)
        self.assertEqual(packet['recommendation'],'escalate')

    def test_hard_deadline_kills_worker_process(self):
        import subprocess
        from secops_triage.agent_runner import run_agent
        original=subprocess.Popen
        seen=[]
        def hung_worker(args,**kwargs):
            # Actual isolated process blocks, to exercise the supervisor kill path.
            process=original([args[0],'-c','import time; time.sleep(30)'],**kwargs)
            seen.append(process);return process
        run=self.ingest()
        with patch('secops_triage.agent_runner.subprocess.Popen',side_effect=hung_worker):
            with self.assertRaisesRegex(Rejected,'deadline'):
                run_agent(self.store,run,self.token,wall_seconds=1)
        self.assertIsNotNone(seen[0].poll())
        self.assertEqual(self.store.status(run,self.token)['state'],'created')

    def test_expired_grant_and_changed_identity_prevent_dispatch(self):
        from secops_triage.agent_spend import authorize
        for mutation in ("expires=0", "identity='changed'"):
            run=self.ingest();grant=authorize(self.store,run,self.token,'test')
            with self.store._locked() as db:
                db.execute('UPDATE secops_grants SET '+mutation+' WHERE id=?',(grant,));db.commit()
            with patch('migration_proof.agent.openai_model._post') as post:
                with self.assertRaises(Rejected):self.execute(run,grant_id=grant,api_key='fake-key')
                post.assert_not_called()

    def test_agent_assessment_tampering_blocks_review(self):
        run=self.ingest();packet=self.execute(run)
        session=self.rows('secops_agent_sessions')[0]
        blob=self.store.blob_path(run,session['result_hash'])
        blob.chmod(0o600);blob.write_text('{}')
        with self.assertRaises(Rejected):self.store.packet(run,self.token)
        with self.assertRaises(Rejected):self.store.review(run,self.token,packet['packet_hash'],'analyst','close','test','tamper')

    def test_failure_stage_journal_excludes_untrusted_values(self):
        from secops_triage.agent import fixture_model
        run=self.ingest()
        with self.assertRaises(Rejected):
            self.execute(run,model_factory=lambda b:fixture_model(b,{'name':'inspect_incident','input':{'secret-canary':'secret-canary'}}))
        events=self.rows('secops_agent_events')
        self.assertTrue(any(e['stage']=='tool_rejected' for e in events))
        self.assertEqual(events[-1]['stage'],'session_stopped')
        self.assertNotIn('secret-canary',json.dumps(events))

    def test_utc_offset_reproduces_four_response_stop_with_specific_stage(self):
        from secops_triage.agent import fixture_model
        def factory(bundle):
            m=fixture_model(bundle); original=m._next
            def response(messages):
                value=original(messages)
                if value.get('name')=='query_activity':
                    value['input']['start']=value['input']['start'].replace('Z','+00:00')
                return value
            m._next=response;return m
        with self.assertRaises(Rejected):self.execute(self.ingest(),model_factory=factory)
        session=self.rows('secops_agent_sessions')[0]
        self.assertEqual((session['model_calls'],session['tool_calls']),(4,3))
        self.assertTrue(any(e['stage']=='tool_rejected' and e['label']=='typed_contract' for e in self.rows('secops_agent_events')))
