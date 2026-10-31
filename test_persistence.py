import tempfile
import unittest
from pathlib import Path
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.lesson_engine import PolicyError, ConflictError
from prototype.instructional_content import CONTENT_PATH
import json

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'synthetic.sqlite3'
        self.db=SyntheticSQLiteStore(self.path)
        self.token=self.db.provision_synthetic_family('synthetic-family-1','adult-1','synthetic-student-1')
        content=json.loads(CONTENT_PATH.read_text(encoding='utf-8'))
        self.registry=self.db.content_registry()
        self.registry.create_draft(content,'synthetic-author')
        self.registry.transition(content['lesson_id'],content['version'],'submit','synthetic-author','ready')
        self.registry.transition(content['lesson_id'],content['version'],'approve_prototype','synthetic-reviewer','reviewed')
        self.lesson_id,self.version=content['lesson_id'],content['version']
        self.session=self.db.start(self.token,'synthetic-student-1',self.lesson_id,self.version,'key1')
    def tearDown(self): self.tmp.cleanup()
    def test_persists_across_restart(self):
        second=SyntheticSQLiteStore(self.path)
        self.assertEqual(second.get_session(self.token,self.session.session_id).status,'created')
    def test_token_required(self):
        with self.assertRaises(PolicyError): self.db.get_session('bad',self.session.session_id)
    def test_cross_workspace_denied(self):
        other=self.db.provision_synthetic_family('synthetic-family-2','adult-2','synthetic-student-2')
        with self.assertRaises(PolicyError): self.db.get_session(other,self.session.session_id)
    def test_real_data_rejected(self):
        with self.assertRaises(PolicyError): self.db.provision_synthetic_family('family','adult','real-student')
    def test_idempotency_survives_restart(self):
        again=SyntheticSQLiteStore(self.path).start(self.token,'synthetic-student-1',self.lesson_id,self.version,'key1')
        self.assertEqual(again.session_id,self.session.session_id)
    def test_idempotency_collision_rejected(self):
        with self.assertRaises(ConflictError): self.db.start(self.token,'synthetic-student-1','different','1.0','key1')
    def test_revision_conflict(self):
        self.db.transition(self.token,self.session.session_id,'active',0)
        with self.assertRaises(ConflictError): self.db.advance_stage(self.token,self.session.session_id,0)
    def test_atomic_rollback(self):
        with self.assertRaises(PolicyError): self.db.transition(self.token,self.session.session_id,'completed',0)
        self.assertEqual(self.db.get_session(self.token,self.session.session_id).revision,0)
    def test_audit_persists(self):
        self.db.transition(self.token,self.session.session_id,'active',0)
        self.assertEqual(SyntheticSQLiteStore(self.path).audit_count(self.token,self.session.session_id),2)
    def test_evidence_and_no_mastery(self):
        s=self.db.transition(self.token,self.session.session_id,'active',0)
        for _ in range(4): s=self.db.advance_stage(self.token,s.session_id,s.revision)
        r=self.db.record_response(self.token,s.session_id,s.revision,'answer',{'audio_or_modeling':True},True)
        self.assertFalse(r['independent_evidence_eligible'])
        self.assertEqual(self.db.get_session(self.token,s.session_id).mastery_status,'not_assessed')
    def test_no_unknown_lesson(self):
        with self.assertRaises(PolicyError): self.db.start(self.token,'synthetic-student-1','unapproved','1.0','new')

if __name__=='__main__': unittest.main()
