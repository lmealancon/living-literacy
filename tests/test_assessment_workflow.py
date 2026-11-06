"""Synthetic workflow tests. These do not validate an assessment instrument."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from prototype.assessment_workflow import SyntheticAssessmentWorkflow
from prototype.lesson_engine import ConflictError, PolicyError
from prototype.persistent_store import SyntheticSQLiteStore


class SyntheticAssessmentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'synthetic.sqlite'
        self.store = SyntheticSQLiteStore(self.path)
        self.a = self.store.provision_synthetic_family('synthetic-family-a', 'synthetic-adult-a', 'synthetic-child-a')
        self.b = self.store.provision_synthetic_family('synthetic-family-b', 'synthetic-adult-b', 'synthetic-child-b')
        self.workflow = SyntheticAssessmentWorkflow(self.store)
        self.workflow.assessments.add_reviewed_fixture('synthetic-form','v1','en',
            [{'id':'synthetic-item','prompt':'A fictional test-only prompt.'}], 'synthetic-author', 'synthetic-reviewer')
        self.workflow.assessments.set_synthetic_consent(self.a, 'synthetic-child-a', True)

    def tearDown(self):
        self.tmp.cleanup()

    def start(self):
        return self.workflow.start(self.a, 'synthetic-child-a', 'synthetic-form', 'v1', 'start-idempotency-001')

    def record(self, run_id, key='response-key-00001', revision=0, **kwargs):
        return self.workflow.record_response(self.a, run_id, 'synthetic-item',
            kwargs.get('response','fictional response'), kwargs.get('assisted',False),
            kwargs.get('narration',False), revision, key)

    def test_start_requires_assessment_specific_consent_and_family_authority(self):
        with self.assertRaises(PolicyError):
            self.workflow.start(self.b,'synthetic-child-a','synthetic-form','v1','start-idempotency-001')
        with self.assertRaises(PolicyError):
            self.workflow.start(self.b,'synthetic-child-b','synthetic-form','v1','start-idempotency-001')
        with self.assertRaises(PolicyError):
            self.workflow.start(self.a,'synthetic-child-a','synthetic-form','v1','short')

    def test_start_is_idempotent_after_reopen_and_collisions_rejected(self):
        run = self.start()
        self.assertEqual(self.start()['id'], run['id'])
        reopened = SyntheticAssessmentWorkflow(SyntheticSQLiteStore(self.path))
        self.assertEqual(reopened.start(self.a,'synthetic-child-a','synthetic-form','v1','start-idempotency-001')['id'],run['id'])
        self.workflow.assessments.add_reviewed_fixture('synthetic-other','v1','en',
            [{'id':'synthetic-other-item','prompt':'Another fictional test prompt.'}], 'synthetic-author', 'synthetic-reviewer')
        with self.assertRaises(ConflictError):
            self.workflow.start(self.a,'synthetic-child-a','synthetic-other','v1','start-idempotency-001')

    def test_response_replay_is_idempotent_narration_is_assistance_and_no_score(self):
        run = self.start()
        response = self.record(run['id'], narration=True)
        self.assertTrue(response['assisted'])
        self.assertTrue(response['narration'])
        self.assertEqual(response['evidence_status'],'needs_review')
        self.assertNotIn('score',response)
        self.assertEqual(self.record(run['id'], narration=True),response)
        with self.assertRaises(ConflictError): self.record(run['id'], narration=False)
        self.assertEqual(self.workflow.history(self.a,'synthetic-child-a')['runs'][0]['responses_recorded'],1)

    def test_completion_is_not_mastery_and_rejects_future_writes(self):
        run = self.start(); self.record(run['id'])
        result = self.workflow.complete(self.a,run['id'],1,'completion-key-001')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['mastery_status'],'not_assessed')
        self.assertEqual(self.workflow.complete(self.a,run['id'],1,'completion-key-001'),result)
        with self.assertRaises(PolicyError): self.record(run['id'],key='other-response-001',revision=2)

    def test_workflow_runs_cannot_bypass_checks_via_legacy_response_api(self):
        run = self.start()
        with self.assertRaises(PolicyError):
            self.workflow.assessments.record_response(self.a,run['id'],'synthetic-item','fictional',False,False)
        self.workflow.complete(self.a,run['id'],0,'completion-key-001')
        with self.assertRaises(PolicyError):
            self.workflow.assessments.record_response(self.a,run['id'],'synthetic-item','fictional',False,False)
        legacy = self.workflow.assessments.start(self.a,'synthetic-child-a','synthetic-form','v1')
        result = self.workflow.assessments.record_response(self.a,legacy['id'],'synthetic-item','fictional',False,False)
        self.assertEqual(result['validation_status'],'unvalidated')

    def test_resume_returns_current_revision_and_denies_cross_workspace(self):
        run = self.start()
        first = self.workflow.get_run(self.a,run['id'])
        self.assertEqual((first['status'],first['revision']),('active',0))
        self.assertEqual(first['items'][0]['id'],'synthetic-item')
        self.record(run['id'])
        self.assertEqual(self.workflow.get_run(self.a,run['id'])['revision'],1)
        self.workflow.complete(self.a,run['id'],1,'completion-key-001')
        completed = self.workflow.get_run(self.a,run['id'])
        self.assertEqual((completed['status'],completed['revision']),('completed',2))
        self.assertEqual(completed['mastery_status'],'not_assessed')
        with self.assertRaises(PolicyError): self.workflow.get_run(self.b,run['id'])
        with self.store._connect() as db:
            db.execute('UPDATE synthetic_assessment_runs SET workspace_id=? WHERE id=?',('synthetic-family-b',run['id']))
        with self.assertRaises(PolicyError): self.workflow.get_run(self.a,run['id'])

    def test_revocation_and_withdrawal_deny_all_writes_even_replay(self):
        run = self.start(); self.record(run['id'])
        with self.store._connect() as db: db.execute("UPDATE synthetic_assessment_forms SET status='suspended'")
        with self.assertRaises(PolicyError): self.record(run['id'])
        with self.assertRaises(PolicyError): self.workflow.complete(self.a,run['id'],1,'completion-key-001')
        self.assertEqual(self.workflow.history(self.a,'synthetic-child-a')['runs'][0]['responses_recorded'],1)
        self.workflow.assessments.set_synthetic_consent(self.a,'synthetic-child-a',False)
        with self.assertRaises(PolicyError): self.workflow.history(self.a,'synthetic-child-a')

    def test_tampering_and_wrong_family_denied(self):
        run = self.start()
        with self.assertRaises(PolicyError): self.workflow.complete(self.b,run['id'],0,'completion-key-001')
        with self.store._connect() as db: db.execute("UPDATE synthetic_assessment_forms SET payload='{}'")
        with self.assertRaises(PolicyError): self.record(run['id'])

    def test_malformed_form_fails_closed_even_with_matching_digest(self):
        for payload in ('{', '{"language":"en","items":[{"id":"synthetic-item"}]}'):
            with self.subTest(payload=payload):
                with self.store._connect() as db:
                    db.execute('UPDATE synthetic_assessment_forms SET payload=?,digest=?',
                               (payload,hashlib.sha256(payload.encode()).hexdigest()))
                with self.assertRaises(PolicyError): self.start()

    def test_invalid_unicode_fails_closed_without_recording(self):
        run = self.start()
        with self.assertRaises(PolicyError):
            self.record(run['id'], response='fictional-\ud800')
        with self.assertRaises(PolicyError):
            self.workflow.record_response(self.a,run['id'],'synthetic-\ud800','fictional',False,False,0,'response-key-00001')
        with self.store._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_assessment_responses').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT revision FROM synthetic_assessment_workflow WHERE run_id=?',(run['id'],)).fetchone()[0],0)

    def test_audit_failure_rolls_back_response_revision_and_idempotency(self):
        run = self.start()
        with self.store._connect() as db:
            db.execute("""CREATE TRIGGER synthetic_fail_audit BEFORE INSERT ON synthetic_assessment_events
                WHEN NEW.action='response_recorded' BEGIN SELECT RAISE(ABORT,'test failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError): self.record(run['id'])
        with self.store._connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_assessment_responses').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT revision FROM synthetic_assessment_workflow WHERE run_id=?',(run['id'],)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_assessment_commands').fetchone()[0],0)
            db.execute('DROP TRIGGER synthetic_fail_audit')
        self.assertEqual(self.record(run['id'])['revision'],1)

    def test_concurrent_conflicting_writes_only_one_succeeds(self):
        run = self.start(); barrier = threading.Barrier(2)
        def work(key):
            barrier.wait()
            try:
                self.record(run['id'],key=key)
                return 'success'
            except ConflictError:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(work,'response-key-00001'),pool.submit(work,'response-key-00002')]
            self.assertCountEqual([f.result() for f in futures],['success','conflict'])
        self.assertEqual(self.workflow.history(self.a,'synthetic-child-a')['runs'][0]['responses_recorded'],1)


if __name__ == '__main__': unittest.main()
