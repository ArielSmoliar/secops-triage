"""Offline campaign safety tests. Grants exist only in temporary synthetic stores."""
from copy import deepcopy
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from secops_triage.campaign import build_plan
from secops_triage.campaign_store import CampaignStore, GATES
from secops_triage.contracts import Rejected, canonical, sha, IncidentBundle, InspectIncident
from secops_triage.evaluation_cases import get_case
from secops_triage.store import Store
from secops_triage.agent_spend import authorize, Ledger


class CampaignStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name).resolve() / 'store')
        self.ledger = CampaignStore(self.store)
        self.token = secrets.token_hex(32)
        self.plan = build_plan()
        # Dedicated current-build seam simulates a clean frozen commit while
        # developing. All fixture/engine/source hashes remain real.
        self.plan['worktree_dirty'] = False
        self.plan['plan_hash'] = sha(canonical({k:v for k,v in self.plan.items() if k != 'plan_hash'}))
        self.current = patch('secops_triage.campaign_store.build_plan', side_effect=lambda: deepcopy(self.plan))
        self.current.start(); self.addCleanup(self.current.stop)
        self.campaign = self.ledger.register(self.plan, self.token)
        self.run = self.ingest()
        self.ledger.reserve(self.campaign, self.token, 'm2-01', self.run, self.token)
        self.keyfile = Path(self.tmp.name) / 'key'
        self.keyfile.write_text('OPENAI_API_KEY=test-secret-canary\n')

    def ingest(self, case='case-01'):
        return self.store.ingest(get_case(case), self.token, secrets.token_hex(16))

    def authority(self):
        self.ledger.record_authority(self.campaign, self.token, 'offline test only',
                                     {key:'synthetic test assertion' for key in GATES})

    def grant(self):
        self.authority()
        grant = authorize(self.store, self.run, self.token, 'offline test only')
        self.ledger.attach_grant(self.campaign, self.token, 'm2-01', self.token, grant)
        return grant

    def execute(self):
        return self.ledger.execute(self.campaign, self.token, 'm2-01', self.token, self.keyfile)

    def recover(self):
        return self.ledger.recover(self.campaign, self.token, 'm2-01')

    def test_pending_gates_prevent_grant_and_key_read(self):
        with self.assertRaises(Rejected): authorize(self.store, self.run, self.token, 'test')
        with patch('secops_triage.live.load_key') as key:
            with self.assertRaises(Rejected): self.execute()
            key.assert_not_called()
        with self.assertRaises(Rejected): self.ledger.record_authority(self.campaign, self.token, 'test', {})

    def test_duplicate_plan_slot_run_and_wrong_owner_rejected(self):
        with self.assertRaises(Rejected): self.ledger.register(self.plan, self.token)
        for slot in ('m2-01','m2-02'):
            with self.assertRaises(Rejected): self.ledger.reserve(self.campaign, self.token, slot, self.run, self.token)
        with self.assertRaises(Rejected): self.ledger.status(self.campaign, 'wrong-owner')
        with self.assertRaises(Rejected): self.ledger.recover(self.campaign, 'wrong-owner', 'm2-01')

    def test_wrong_case_unbound_m4_and_out_of_order_rejected(self):
        wrong = self.ingest('case-04')
        for slot in ('m2-02','m4-hero-1','m4-playback-case-07'):
            with self.assertRaises(Rejected): self.ledger.reserve(self.campaign, self.token, slot, wrong, self.token)
        right = self.ingest('case-02')
        with self.assertRaises(Rejected): self.ledger.reserve(self.campaign, self.token, 'm2-02', right, self.token)

    def test_full_plan_source_rubric_bounds_and_dirty_changes_fail_before_key(self):
        self.grant()
        variants = []
        for field, value in [('source_commit','changed'), ('worktree_dirty',True), ('engine_hash','changed'), ('model','changed')]:
            p=deepcopy(self.plan); p[field]=value; variants.append(p)
        p=deepcopy(self.plan); p['cases']['case-01']['rubric_sha256']='changed'; variants.append(p)
        p=deepcopy(self.plan); p['slots'][0]['requests_max']=100; variants.append(p)
        p=deepcopy(self.plan); p['source_sha256']['secops_triage/evaluation.py']='changed'; variants.append(p)
        for p in variants:
            with patch('secops_triage.campaign_store.build_plan', return_value=p), patch('secops_triage.live.load_key') as key:
                with self.assertRaises(Rejected): self.execute()
                key.assert_not_called()

    def test_superseded_run_stops_dispatch(self):
        self.grant(); self.ingest()
        with patch('secops_triage.live.load_key') as key:
            with self.assertRaises(Rejected): self.execute()
            key.assert_not_called()
        self.assertEqual(self.recover()['outcome'], 'stopped')

    def test_foreign_closed_expired_or_consumed_grant_rejected(self):
        self.authority()
        foreign_run=self.ingest('case-02'); foreign=authorize(self.store,foreign_run,self.token,'test')
        with self.assertRaises(Rejected): self.ledger.attach_grant(self.campaign,self.token,'m2-01',self.token,foreign)
        grant=authorize(self.store,self.run,self.token,'test')
        for update in ("state='closed'", "state='issued',expires=0"):
            with self.store._locked() as db:
                db.execute('UPDATE secops_grants SET '+update+' WHERE id=?',(grant,));db.commit()
            with self.assertRaises(Rejected): self.ledger.attach_grant(self.campaign,self.token,'m2-01',self.token,grant)

    def test_startup_failure_and_duplicate_dispatch_keep_one_result(self):
        self.grant()
        with patch('secops_triage.agent_runner.run_agent',side_effect=OSError('test-secret-canary')) as run:
            result=self.execute()
            with self.assertRaises(Rejected): self.execute()
            self.assertEqual(run.call_count,1)
        self.assertEqual(result['outcome'],'stopped')
        self.assertEqual(result['grants'][0]['state'],'closed')
        self.assertNotIn('test-secret-canary',json.dumps(result))
        self.assertNotIn(self.token,json.dumps(result))
        self.assertEqual(self.recover(),result)
        with self.assertRaises(Rejected): self.store.investigate(self.run,self.token)
        with self.assertRaises(Rejected): self.store.agent_tools(self.run,self.token)['inspect_incident'](InspectIncident())

    def test_reserved_and_orphan_authority_crashes_consume_without_retry(self):
        self.authority(); grant=authorize(self.store,self.run,self.token,'test')
        result=self.recover()  # crash after grant issue, before attaching it
        self.assertIsNone(result['grant_id'])
        self.assertEqual(result['grants'][0]['id'],grant)
        self.assertEqual(result['grants'][0]['state'],'closed')
        with self.assertRaises(Rejected): authorize(self.store,self.run,self.token,'test')
        with self.assertRaises(Rejected): self.ledger.attach_grant(self.campaign,self.token,'m2-01',self.token,grant)

    def test_worker_cannot_consume_before_dispatch(self):
        grant=self.grant()
        with self.store._locked() as db:
            with self.assertRaises(Rejected): Ledger(db,self.store._owner(db,self.run,self.token),grant,'a'*32)
        from secops_triage.agent import execute_session
        with patch('migration_proof.agent.openai_model._post') as post:
            with self.assertRaises(Rejected): execute_session(self.store,self.run,self.token,grant_id=grant,api_key='test')
            post.assert_not_called()

    def test_real_process_crash_preserves_unknown_spend_and_fences_late_worker(self):
        grant=self.grant()
        code='''
import json,os,sys
from secops_triage.store import Store
from secops_triage.agent_spend import Ledger
v=json.load(sys.stdin); s=Store(v['root'])
from unittest.mock import patch
patch('secops_triage.campaign_store.build_plan',return_value=v['plan']).start()
with s._locked() as db:
 db.execute("UPDATE campaign_slots SET state='dispatching' WHERE run_id=?",(v['run'],));db.commit()
 l=Ledger(db,s._owner(db,v['run'],v['token']),v['grant'],'a'*32)
 l.reserve(v['grant'])
 os._exit(73)
'''
        p=subprocess.run([sys.executable,'-c',code],input=json.dumps({'root':str(self.store.root),'run':self.run,'token':self.token,'grant':grant,'plan':self.plan}),text=True,capture_output=True)
        self.assertEqual(p.returncode,73,p.stderr)
        result=self.recover()
        self.assertEqual(result['requests'][0]['state'],'unknown')
        self.assertGreater(result['reserved_microusd'],0)
        self.assertFalse(result['usage_complete'])
        with self.store._locked() as db:
            with self.assertRaises(Rejected): Ledger(db,self.store._owner(db,self.run,self.token),grant,'b'*32)
        with patch('secops_triage.store.engine_digest',return_value='new-engine'):
            self.assertEqual(CampaignStore(Store(self.store.root)).recover(self.campaign,self.token,'m2-01'),result)

    def test_result_publication_failure_rolls_back_and_can_reconcile(self):
        self.grant()
        with patch.object(self.store,'_put',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.recover()
        self.assertIsNone(self.ledger.status(self.campaign,self.token)['slots'][0]['result_hash'])
        self.assertEqual(self.recover()['outcome'],'stopped')

    def test_result_tampering_detected(self):
        result=self.recover()
        slot=self.ledger.status(self.campaign,self.token)['slots'][0]
        path=self.store.blob_path(self.run,slot['result_hash']);path.chmod(0o600);path.write_text('{}')
        with self.assertRaises(Rejected):self.recover()

    def test_real_sdk_fake_transport_success_is_accounted_once(self):
        self.grant()
        result=self.fake_execution('case-01')
        self.assertEqual(result['outcome'],'completed')
        self.assertEqual(len(result['evidence']),8)
        self.assertTrue(result['usage_complete'])
        self.assertFalse(result['campaign_acceptance'])
        self.assertEqual(result['semantic_review'],'pending')
        next_run=self.ingest('case-02')
        with self.assertRaises(Rejected): self.ledger.reserve(self.campaign,self.token,'m2-02',next_run,self.token)
        from secops_triage.evaluation import snapshot, review_template
        source=snapshot(self.store,self.run,self.token,'case-01')
        result=self.ledger.record_evaluation(self.campaign,self.token,'m2-01',self.token,review_template(source))
        self.assertEqual(result['outcome'],'pending_review')
        with self.assertRaises(Rejected): self.ledger.reserve(self.campaign,self.token,'m2-02',next_run,self.token)
        review=review_template(source)
        review.update(reviewer='synthetic test assertions, not semantic validation',reviewer_kind='ai',all_material_claims_split=True)
        for finding in review['findings']:
            for claim in finding['claims']:claim.update(verdict='supported',rationale='test assertion')
        for item in review['requirements']:item.update(status='present',finding_indices=[0],rationale='test assertion')
        scored=self.ledger.record_evaluation(self.campaign,self.token,'m2-01',self.token,review)
        self.assertEqual(scored['outcome'],'pass')
        self.ledger.reserve(self.campaign,self.token,'m2-02',next_run,self.token)
        next_grant=authorize(self.store,next_run,self.token,'test')
        self.ledger.attach_grant(self.campaign,self.token,'m2-02',self.token,next_grant)
        # A subsequently recorded unsupported claim must stop continuation even
        # if a later review says pass; failed evidence cannot be hidden.
        failed=deepcopy(review);failed['findings'][0]['claims'][0]['verdict']='unsupported'
        for item in failed['requirements']:item.update(status='omitted',finding_indices=[])
        self.assertEqual(self.ledger.record_evaluation(self.campaign,self.token,'m2-01',self.token,failed)['outcome'],'fail')
        self.ledger.record_evaluation(self.campaign,self.token,'m2-01',self.token,review)
        with patch('secops_triage.live.load_key') as key:
            with self.assertRaises(Rejected): self.ledger.execute(self.campaign,self.token,'m2-02',self.token,self.keyfile)
            key.assert_not_called()
        with self.store._locked() as db:
            db.execute("UPDATE campaign_slots SET state='dispatching' WHERE run_id=?",(next_run,));db.commit()
            with self.assertRaises(Rejected): Ledger(db,self.store._owner(db,next_run,self.token),next_grant,'b'*32)
        with self.assertRaises(Rejected): self.ledger.reserve(self.campaign,self.token,'m2-02',next_run,self.token)


    def test_scripted_worker_rejected_during_dispatch_and_cannot_retry(self):
        self.grant()
        from secops_triage.agent import execute_session
        with self.store._locked() as db:
            db.execute("UPDATE campaign_slots SET state='dispatching' WHERE run_id=?", (self.run,));db.commit()
        with self.assertRaises(Rejected): execute_session(self.store,self.run,self.token)
        self.assertEqual(self.recover()['outcome'],'stopped')
        with self.assertRaises(Rejected): execute_session(self.store,self.run,self.token)

    def test_recovery_serializes_with_host_dispatch_startup(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        entered=threading.Event(); release=threading.Event(); recovery_started=threading.Event()
        self.grant()
        def worker(*args,**kwargs):
            entered.set()
            if not release.wait(5): raise RuntimeError('test timed out')
            raise OSError('simulated startup stop')
        def recovering():
            recovery_started.set()
            return self.recover()
        with patch('secops_triage.agent_runner.run_agent',side_effect=worker), ThreadPoolExecutor(max_workers=2) as pool:
            execution=pool.submit(self.execute)
            self.assertTrue(entered.wait(5))
            recovery=pool.submit(recovering)
            self.assertTrue(recovery_started.wait(5))
            self.assertFalse(recovery.done())
            release.set()
            self.assertEqual(execution.result(timeout=5),recovery.result(timeout=5))

    def test_atomic_duplicate_reservations_from_two_hosts(self):
        from concurrent.futures import ThreadPoolExecutor
        # Independent new campaign store; same plan/run, simultaneous reserve.
        other=Store(Path(self.tmp.name).resolve()/'other'); ledger=CampaignStore(other)
        campaign=ledger.register(self.plan,self.token)
        run=other.ingest(get_case('case-01'),self.token,'concurrent')
        def reserve():
            try:
                CampaignStore(other).reserve(campaign,self.token,'m2-01',run,self.token)
                return 'reserved'
            except Rejected: return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:reserve(),range(2)))
        self.assertCountEqual(results,['reserved','rejected'])

    def test_host_crash_after_intent_before_worker_cannot_restart(self):
        self.grant()
        code="""
import json,os,sys
from unittest.mock import patch
from secops_triage.store import Store
from secops_triage.campaign_store import CampaignStore
v=json.load(sys.stdin)
with patch('secops_triage.campaign_store.build_plan',return_value=v['plan']), patch('secops_triage.agent_runner.run_agent',side_effect=lambda *a,**k:os._exit(74)):
 CampaignStore(Store(v['root'])).execute(v['campaign'],v['token'],'m2-01',v['token'],v['key'])
"""
        p=subprocess.run([sys.executable,'-c',code],input=json.dumps({'root':str(self.store.root),'campaign':self.campaign,'token':self.token,'plan':self.plan,'key':str(self.keyfile)}),text=True,capture_output=True)
        self.assertEqual(p.returncode,74,p.stderr)
        result=self.recover()
        self.assertEqual(result['previous_state'],'dispatching')
        self.assertEqual(result['sessions'],[])
        self.assertEqual(result['grants'][0]['state'],'closed')
        with self.assertRaises(Rejected):self.execute()

    def fake_execution(self, case, slot="m2-01"):
        from secops_triage.agent import execute_session,fixture_model
        from migration_proof.agent.openai_preflight import MODEL_ID
        script=fixture_model(IncidentBundle.from_dict(get_case(case)))
        def post(body,key):
            payload=json.loads(body); messages=[]
            if payload['messages'][-1]['role']=='tool':
                messages=[{'content':[{'toolResult':{'content':json.loads(payload['messages'][-1]['content'])}}]}]
            result=script._next(messages)
            if 'name' in result:
                message={'role':'assistant','content':None,'tool_calls':[{'id':secrets.token_hex(8),'type':'function','function':{'name':result['name'],'arguments':json.dumps(result['input'])}}]};stop='tool_calls'
            else: message={'role':'assistant','content':json.dumps(result)};stop='stop'
            return {'model':MODEL_ID,'service_tier':'default','choices':[{'message':message,'finish_reason':stop}],
                    'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110}}
        with patch('secops_triage.agent_runner.run_agent',side_effect=execute_session), patch('migration_proof.agent.openai_model._post',side_effect=post) as provider:
            result=self.ledger.execute(self.campaign,self.token,slot,self.token,self.keyfile)
            self.assertGreater(provider.call_count,0)
        return result

    def test_incomplete_result_preserves_context_without_campaign_acceptance(self):
        # Reorder only the test current-plan seam to exercise incomplete as the
        # first slot. Production build_plan always retains its fixed order.
        self.plan['slots'][0]['case_id']='case-03'
        self.plan['slots'][0]['fixture_sha256']=self.plan['cases']['case-03']['fixture_sha256']
        self.plan['plan_hash']=sha(canonical({k:v for k,v in self.plan.items() if k!='plan_hash'}))
        self.store=Store(Path(self.tmp.name).resolve()/'incomplete')
        self.ledger=CampaignStore(self.store)
        self.campaign=self.ledger.register(self.plan,self.token)
        self.run=self.ingest('case-03')
        self.ledger.reserve(self.campaign,self.token,'m2-01',self.run,self.token)
        self.grant()
        result=self.fake_execution('case-03')
        self.assertEqual(result['outcome'],'incomplete')
        self.assertTrue(result['packet_hash'])
        self.assertFalse(result['campaign_acceptance'])
        self.assertEqual(self.recover(),result)

    def test_provider_failure_keeps_unknown_reservation_and_one_attempt(self):
        from secops_triage.agent import execute_session
        self.grant()
        with patch('secops_triage.agent_runner.run_agent',side_effect=execute_session), patch('migration_proof.agent.openai_model._post',side_effect=OSError('secret-canary')) as provider:
            result=self.execute()
            with self.assertRaises(Rejected):self.execute()
            self.assertEqual(provider.call_count,1)
        self.assertEqual(result['outcome'],'stopped')
        self.assertEqual(result['requests'][0]['state'],'unknown')
        self.assertEqual(result['sessions'][0]['state'],'stopped')
        self.assertNotIn('secret-canary',json.dumps(result))
