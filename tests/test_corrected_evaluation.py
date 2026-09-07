"""Corrected-candidate authority, history preservation, and atomic schema upgrade."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import importlib.util
import json
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_openai_transport as helpers
from migration_proof.agent.contracts import Limits
from migration_proof.agent.journal import Journal
from migration_proof.agent.openai_preflight import OpenAIPlan, MODEL_ID, preflight
from migration_proof.agent.spend import SpendLedger
from migration_proof.core.artifacts import PATCH_PATH, REGRESSION
from migration_proof.core.contracts import Rejected
from migration_proof.core.store import Store

HAS_STRANDS = importlib.util.find_spec('strands') is not None
if HAS_STRANDS:
    import test_agent_orchestration as offline_helpers
    from migration_proof.agent.offline_model import OfflineModel
    from migration_proof.agent.openai_model import OpenAIModel
    from migration_proof.agent.runtime import execute_session

# Original shipped schema, independent of the new schema declaration.
LEGACY_SCHEMA = '''
CREATE TABLE inference_grants(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
 initial_digest TEXT NOT NULL, model_id TEXT NOT NULL, plan_json TEXT NOT NULL,
 actor TEXT NOT NULL, issued REAL NOT NULL, expires REAL NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('issued','claimed','closed','revoked')),
 session_id TEXT UNIQUE REFERENCES agent_sessions(id));
CREATE TABLE inference_requests(
 id TEXT PRIMARY KEY, grant_id TEXT NOT NULL REFERENCES inference_grants(id),
 ordinal INTEGER NOT NULL, reserved_microusd INTEGER NOT NULL CHECK(reserved_microusd>0),
 status TEXT NOT NULL CHECK(status IN ('pending','recorded','unknown')),
 input_tokens INTEGER, output_tokens INTEGER, estimated_microusd INTEGER,
 started REAL NOT NULL, finished REAL, UNIQUE(grant_id,ordinal));
'''


class MigrationTests(helpers.LedgerFixture):
    def legacy(self):
        grant = uuid4().hex
        with self.store._locked() as db:
            db.execute('DROP TABLE inference_requests')
            db.execute('DROP TABLE inference_grants')
            db.execute('DROP TABLE inference_schema')
            db.executescript(LEGACY_SCHEMA)
            old_plan = asdict(OpenAIPlan()); old_plan.pop('scenario')
            db.execute('INSERT INTO inference_grants VALUES(?,?,?,?,?,?,?,?,?,NULL)',
                       (grant,self.run['run_id'],self.run['digest'],MODEL_ID,json.dumps(old_plan),
                        'legacy-owner',1,2,'closed'))
            db.execute('INSERT INTO inference_requests VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (uuid4().hex,grant,1,422308,'recorded',100,20,72,1,2))
            db.execute('INSERT INTO inference_requests VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (uuid4().hex,grant,2,422308,'unknown',None,None,None,3,4))
        return grant

    def rows(self):
        with self.store._locked() as db:
            return {table:[tuple(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY id')]
                    for table in ('inference_grants','inference_requests')}

    def test_migration_preserves_every_historical_value_and_foreign_key(self):
        grant=self.legacy(); before=self.rows()
        ledger=SpendLedger(self.store)
        self.assertEqual(self.rows(),before)
        report=ledger.read(self.run['run_id'],self.run['token'],grant)
        self.assertEqual(report['reserved_microusd'],844616)
        self.assertEqual(report['reported_estimate_microusd'],72)
        self.assertFalse(report['usage_complete'])
        self.assertEqual(ledger.plan(self.run['run_id'],self.run['token'],grant).scenario,'faulty')
        with self.store._locked() as db:
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(db.execute('SELECT version FROM inference_schema').fetchone()[0],2)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
        SpendLedger(self.store)
        self.assertEqual(self.rows(),before)

    def test_failure_mid_migration_rolls_back_ddl_and_data(self):
        from migration_proof.agent.spend import _create_schema
        self.legacy(); before=self.rows()
        def fail(db):
            _create_schema(db)
            raise RuntimeError('simulated crash boundary')
        with patch('migration_proof.agent.spend._create_schema',side_effect=fail), self.assertRaises(RuntimeError):
            SpendLedger(self.store)
        self.assertEqual(self.rows(),before)
        with self.store._locked() as db:
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='inference_schema'").fetchone())
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'inference_%_v1'").fetchone())
        SpendLedger(self.store)
        self.assertEqual(self.rows(),before)

    def test_process_exit_during_migration_recovers_original_schema(self):
        self.legacy(); before=self.rows()
        code = """import os,sys
from migration_proof.core.store import Store
import migration_proof.agent.spend as spend
original=spend._create_schema
def crash(db):
    original(db)
    os._exit(79)
spend._create_schema=crash
spend.SpendLedger(Store(sys.argv[1]))
"""
        result=subprocess.run([sys.executable,'-B','-c',code,str(self.store.root)],timeout=10)
        self.assertEqual(result.returncode,79)
        self.assertEqual(self.rows(),before)
        SpendLedger(self.store)
        self.assertEqual(self.rows(),before)

    def test_concurrent_migration_is_idempotent(self):
        self.legacy(); before=self.rows()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:SpendLedger(self.store),range(4)))
        self.assertEqual(self.rows(),before)

    def test_active_legacy_session_must_be_recovered_first(self):
        self.legacy(); before=self.rows()
        session=self.journal.start(self.run['run_id'],self.run['token'],Limits())
        with self.assertRaises(Rejected):
            SpendLedger(self.store)
        self.assertEqual(self.rows(),before)
        self.journal.finish(session,'interrupted')
        SpendLedger(self.store)
        self.assertEqual(self.rows(),before)

    def test_unknown_schema_version_fails_closed(self):
        with self.store._locked() as db:
            db.execute('UPDATE inference_schema SET version=99')
        with self.assertRaises(Rejected):
            SpendLedger(self.store)

    def test_explicit_scenario_is_validated_and_preflight_stays_disabled(self):
        for value in (None, True, [], 'approved', 'original'):
            with self.assertRaises(Rejected):
                OpenAIPlan(scenario=value)
        result=preflight(OpenAIPlan(model_calls=4,budget_microusd=1_700_000,scenario='corrected'),environ={})
        self.assertEqual(result['scenario'],'one_corrected_candidate_attempt')
        self.assertEqual(result['total_reservation_microusd'],1689232)
        self.assertFalse(result['execution_enabled'])


@unittest.skipUnless(HAS_STRANDS,'install the locked agent extra')
class CorrectedTests(helpers.LedgerFixture):
    def fake_completion(self, body, key):
        return helpers.TransportTests.fake_completion(self,body,key)

    def investigate(self, *, live=False):
        self.sent=[]
        self.script=OfflineModel({'run_id':self.run['run_id'],'version':'faulty'})
        if live:
            grant,session=self.start()
            model=OpenAIModel(self.ledger,session,'fake-key')
        else:
            grant=None
            session=self.journal.start(self.run['run_id'],self.run['token'],Limits())
            model=self.script
        with patch.object(Store,'_execute',staticmethod(offline_helpers.AgentTests.checks)), \
             patch('migration_proof.agent.openai_model._post',side_effect=self.fake_completion):
            result=asyncio.run(execute_session(self.store,self.run['run_id'],self.run['token'],session,model))
        self.assertEqual(result['status'],'completed',result)
        self.assertFalse(result['summary']['ready'])
        return grant

    def correct(self):
        return self.store.replace_candidate(self.run['run_id'],self.run['token'],'corrected','test-owner')

    def corrected_grant(self):
        return self.grant(OpenAIPlan(model_calls=4,budget_microusd=1_700_000,scenario='corrected'))

    def test_corrected_live_adapter_reruns_all_gates_preserves_patch_and_history(self):
        first=self.investigate(live=True)
        before=self.report(first)
        corrected=self.correct()
        bundle=self.store._bundle(self.run['run_id'],corrected)
        self.assertEqual(bundle['files'][PATCH_PATH],REGRESSION)
        grant=self.corrected_grant()
        session=self.journal.start(self.run['run_id'],self.run['token'],Limits(model_calls=4),model_id=MODEL_ID)
        self.ledger.claim(self.run['run_id'],self.run['token'],grant,session)
        self.script=OfflineModel({'run_id':self.run['run_id'],'version':'corrected','has_patch':True})
        self.sent=[]
        # Actual isolated fixture workers, including execution of the carried test.
        with patch('migration_proof.agent.openai_model._post',side_effect=self.fake_completion):
            result=asyncio.run(execute_session(self.store,self.run['run_id'],self.run['token'],session,
                                               OpenAIModel(self.ledger,session,'fake-key')))
        self.assertEqual(result['status'],'completed',result)
        self.assertTrue(result['summary']['ready'])
        self.assertEqual(result['model_calls'],4)
        self.assertEqual(result['tool_calls'],3)
        self.assertEqual(result['summary']['candidate_digest'],corrected)
        self.assertEqual(self.report(first),before)
        self.assertEqual(self.report(grant)['status'],'closed')
        self.assertEqual(self.report(grant)['reserved_microusd'],1689232)
        with self.store._locked() as db:
            rows=db.execute('SELECT check_id,passed FROM evidence WHERE run_id=? AND digest=?',
                            (self.run['run_id'],corrected)).fetchall()
            self.assertEqual({r['check_id'] for r in rows},
                             {'manifest_integrity','fixture_health','baseline_tests','tenant_boundary'})
            self.assertTrue(all(r['passed'] for r in rows))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM approvals').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM promotions').fetchone()[0],0)
        # The old grant and this digest cannot be reused.
        with self.assertRaises(Rejected): self.corrected_grant()
        with self.assertRaises(Rejected): self.ledger.reserve(before['session_id'])

    def test_offline_preparation_can_feed_separately_authorized_corrected_attempt(self):
        self.investigate(); self.correct()
        grant=self.corrected_grant()
        self.assertEqual(self.ledger.plan(self.run['run_id'],self.run['token'],grant).scenario,'corrected')
        self.assertEqual(self.report(grant)['reserved_microusd'],0)

    def test_wrong_scenario_or_no_owner_correction_rejected(self):
        with self.assertRaises(Rejected): self.corrected_grant()
        self.investigate()
        with self.assertRaises(Rejected): self.corrected_grant()
        self.correct()
        with self.assertRaises(Rejected): self.grant()

    def test_corrected_seed_without_carried_regression_is_rejected(self):
        with self.store._locked() as db:
            self.store._invalidate(db,self.run['run_id'],'test correction without regression')
        self.correct()
        with self.assertRaises(Rejected): self.corrected_grant()

    def test_outstanding_prior_grant_must_be_explicitly_revoked(self):
        first=self.grant()
        self.investigate(); self.correct()
        with self.assertRaises(Rejected): self.corrected_grant()
        self.ledger.revoke(self.run['run_id'],self.run['token'],first)
        self.corrected_grant()
        self.assertEqual(self.report(first)['status'],'revoked')

    def test_wrong_owner_cannot_authorize_corrected_scope(self):
        self.investigate(); self.correct()
        with self.assertRaises(Rejected):
            self.ledger.authorize(self.run['run_id'],'wrong',OpenAIPlan(scenario='corrected'),'owner')

    def test_forged_readiness_cannot_skip_current_boundary_check(self):
        self.investigate(); digest=self.correct(); grant=self.corrected_grant()
        session=self.journal.start(self.run['run_id'],self.run['token'],Limits(model_calls=4),model_id=MODEL_ID)
        self.ledger.claim(self.run['run_id'],self.run['token'],grant,session)
        responses=iter([
            helpers.response(call={'name':'inspect_candidate','input':{'run_id':self.run['run_id'],'version':'corrected'}}),
            helpers.response(call={'name':'run_baseline_tests','input':{'run_id':self.run['run_id'],'digest':digest}}),
            helpers.response(content=json.dumps({'recommendation':'ready_for_approval','reason_codes':['all_gates_passed']}))])
        with patch.object(Store,'_execute',staticmethod(offline_helpers.AgentTests.checks)), \
             patch('migration_proof.agent.openai_model._post',side_effect=lambda *_:next(responses)):
            result=asyncio.run(execute_session(self.store,self.run['run_id'],self.run['token'],session,
                                               OpenAIModel(self.ledger,session,'fake-key')))
        self.assertEqual(result['status'],'completed',result)
        self.assertFalse(result['summary']['ready'])
        with self.assertRaises(Rejected):
            self.store.approve(self.run['run_id'],self.run['token'],result['summary']['packet_id'],'owner')

    def test_concurrent_corrected_authorization_issues_only_one_grant(self):
        self.investigate(); self.correct()
        def authorize(_):
            try: return self.corrected_grant()
            except Rejected: return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            grants=list(pool.map(authorize,range(4)))
        self.assertEqual(sum(g is not None for g in grants),1)
