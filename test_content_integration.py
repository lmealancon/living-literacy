import json
import tempfile
import unittest
from pathlib import Path
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError

class IntegratedContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=SyntheticSQLiteStore(Path(self.tmp.name)/'db.sqlite')
        self.token=self.store.provision_synthetic_family('synthetic-family','synthetic-adult','synthetic-child')
        self.content=json.loads(CONTENT_PATH.read_text())
        self.lid=self.content['lesson_id'];self.version=self.content['version']
        self.registry=self.store.content_registry()
    def tearDown(self):self.tmp.cleanup()
    def approve(self):
        self.registry.create_draft(self.content,'synthetic-author')
        self.registry.transition(self.lid,self.version,'submit','synthetic-author','ready')
        self.registry.transition(self.lid,self.version,'approve_prototype','synthetic-reviewer','reviewed')
    def start(self,key='key'):
        return self.store.start(self.token,'synthetic-child',self.lid,self.version,key)
    def test_draft_cannot_start(self):
        self.registry.create_draft(self.content,'synthetic-author')
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):self.start()
    def test_review_cannot_start(self):
        self.registry.create_draft(self.content,'synthetic-author')
        self.registry.transition(self.lid,self.version,'submit','synthetic-author','ready')
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):self.start()
    def test_approved_version_pinned(self):
        self.approve();s=self.start()
        self.assertEqual(self.store.pinned_digest(self.token,s.session_id),self.registry.get(self.lid,self.version)['digest'])
    def test_suspension_blocks_new_sessions_but_preserves_history(self):
        self.approve();s=self.start()
        self.registry.transition(self.lid,self.version,'suspend','synthetic-reviewer','withdrawn')
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):self.start('second')
        self.assertEqual(self.store.get_session(self.token,s.session_id).lesson_version,self.version)
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):self.store.content_for_demo(self.lid,self.version)
    def test_manual_approval_bypass_disabled(self):
        with self.assertRaisesRegex(PolicyError,'LEGACY_APPROVAL_BYPASS_DISABLED'):
            self.store.add_approved_prototype_lesson(self.lid,self.version)
    def test_tampering_blocks_start(self):
        self.approve()
        with self.store._connect() as db:
            db.execute('UPDATE content_versions SET payload=? WHERE lesson_id=? AND version=?',('{}',self.lid,self.version))
        with self.assertRaisesRegex(PolicyError,'CONTENT_INTEGRITY_FAILURE'):self.start()

if __name__=='__main__':unittest.main()
