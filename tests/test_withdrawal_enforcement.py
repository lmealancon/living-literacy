"""Withdrawal must block all existing-session mutations, not just new sessions."""
import json
import tempfile
import unittest
from pathlib import Path
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError

class WithdrawalEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SyntheticSQLiteStore(Path(self.temp.name) / 'demo.db')
        self.token = self.store.provision_synthetic_family('synthetic-family','synthetic-adult','synthetic-child')
        content = json.loads(CONTENT_PATH.read_text())
        self.lesson_id, self.version = content['lesson_id'], content['version']
        self.registry = self.store.content_registry()
        self.registry.create_draft(content, 'synthetic-author')
        self.registry.transition(self.lesson_id,self.version,'submit','synthetic-author','submit')
        self.registry.transition(self.lesson_id,self.version,'approve_prototype','synthetic-reviewer','approve')
        self.session = self.store.start(self.token,'synthetic-child',self.lesson_id,self.version,'first')
        self.session = self.store.transition(self.token,self.session.session_id,'active',0)
    def tearDown(self): self.temp.cleanup()
    def withdraw(self):
        self.registry.transition(self.lesson_id,self.version,'suspend','synthetic-reviewer','withdraw')
    def test_suspension_blocks_response_and_preserves_history(self):
        self.withdraw()
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):
            self.store.record_response(self.token,self.session.session_id,1,'map',{'audio_or_modeling':False})
        saved = self.store.get_session(self.token,self.session.session_id)
        self.assertEqual(saved.revision,1)
        self.assertEqual(len(saved.responses),0)
    def test_suspension_blocks_stage_advance(self):
        self.withdraw()
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):
            self.store.advance_stage(self.token,self.session.session_id,1)
    def test_suspension_blocks_transitions(self):
        self.withdraw()
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):
            self.store.transition(self.token,self.session.session_id,'paused',1)
    def test_digest_tamper_blocks_existing_session_write(self):
        with self.store._connect() as db:
            db.execute('UPDATE content_versions SET payload=? WHERE lesson_id=? AND version=?',('{}',self.lesson_id,self.version))
        with self.assertRaisesRegex(PolicyError,'CONTENT_INTEGRITY_FAILURE'):
            self.store.record_response(self.token,self.session.session_id,1,'map',{'audio_or_modeling':False})
    def test_pin_tamper_blocks_existing_session_write(self):
        with self.store._connect() as db:
            db.execute('UPDATE session_content_pins SET digest=? WHERE session_id=?',('invalid',self.session.session_id))
        with self.assertRaisesRegex(PolicyError,'CONTENT_INTEGRITY_FAILURE'):
            self.store.advance_stage(self.token,self.session.session_id,1)
    def test_approved_content_remains_usable(self):
        result=self.store.record_response(self.token,self.session.session_id,1,'map',{'audio_or_modeling':False})
        self.assertEqual(result['response'],'map')
        self.assertEqual(self.store.get_session(self.token,self.session.session_id).revision,2)

if __name__=='__main__': unittest.main()
