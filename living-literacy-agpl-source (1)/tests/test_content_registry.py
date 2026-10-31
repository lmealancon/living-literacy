import copy
import json
import tempfile
import unittest
from pathlib import Path
from prototype.content_registry import SyntheticContentRegistry
from prototype.lesson_engine import PolicyError
from prototype.instructional_content import CONTENT_PATH

class ContentRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.registry=SyntheticContentRegistry(Path(self.tmp.name)/'content.sqlite')
        self.content=json.loads(CONTENT_PATH.read_text(encoding='utf-8'))
    def tearDown(self): self.tmp.cleanup()
    def draft(self): return self.registry.create_draft(self.content,'synthetic-author')
    def submit(self):
        self.draft()
        self.registry.transition(self.content['lesson_id'],self.content['version'],'submit','synthetic-author','ready for review')
    def approve(self):
        self.submit()
        return self.registry.transition(self.content['lesson_id'],self.content['version'],'approve_prototype','synthetic-reviewer','reviewed for demo only')
    def test_draft_created_and_integrity(self):
        digest=self.draft()
        self.assertEqual(self.registry.get(self.content['lesson_id'],self.content['version'])['digest'],digest)
    def test_immutable_version(self):
        self.draft()
        with self.assertRaisesRegex(PolicyError,'VERSION_IMMUTABLE'): self.draft()
    def test_requires_review_before_approval(self):
        self.draft()
        with self.assertRaisesRegex(PolicyError,'INVALID_CONTENT_TRANSITION'):
            self.registry.transition(self.content['lesson_id'],self.content['version'],'approve_prototype','synthetic-reviewer','no')
    def test_self_approval_forbidden(self):
        self.submit()
        with self.assertRaisesRegex(PolicyError,'SELF_APPROVAL_FORBIDDEN'):
            self.registry.transition(self.content['lesson_id'],self.content['version'],'approve_prototype','synthetic-author','no')
    def test_reviewed_prototype_access(self):
        self.approve()
        self.assertEqual(self.registry.for_synthetic_demo(self.content['lesson_id'],self.content['version'])['title'],self.content['title'])
    def test_draft_not_served(self):
        self.draft()
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):
            self.registry.for_synthetic_demo(self.content['lesson_id'],self.content['version'])
    def test_suspended_not_served(self):
        self.approve()
        self.registry.transition(self.content['lesson_id'],self.content['version'],'suspend','synthetic-reviewer','withdrawn')
        with self.assertRaisesRegex(PolicyError,'CONTENT_NOT_APPROVED'):
            self.registry.for_synthetic_demo(self.content['lesson_id'],self.content['version'])
    def test_retired_terminal(self):
        self.approve()
        self.registry.transition(self.content['lesson_id'],self.content['version'],'suspend','synthetic-reviewer','withdrawn')
        self.registry.transition(self.content['lesson_id'],self.content['version'],'retire','synthetic-reviewer','obsolete')
        with self.assertRaisesRegex(PolicyError,'INVALID_CONTENT_TRANSITION'):
            self.registry.transition(self.content['lesson_id'],self.content['version'],'submit','synthetic-author','retry')
    def test_invalid_stage_rejected(self):
        self.content['stages'].pop()
        with self.assertRaisesRegex(PolicyError,'INVALID_LESSON_STAGES'): self.draft()
    def test_nonfictional_real_student_rejected(self):
        self.content['publication_status']='published'
        with self.assertRaisesRegex(PolicyError,'PROTOTYPE_ONLY'): self.draft()
    def test_review_note_required(self):
        self.draft()
        with self.assertRaisesRegex(PolicyError,'REVIEW_AUDIT_REQUIRED'):
            self.registry.transition(self.content['lesson_id'],self.content['version'],'submit','synthetic-author','')
    def test_persists_after_reopen(self):
        self.approve()
        reopened=SyntheticContentRegistry(Path(self.tmp.name)/'content.sqlite')
        self.assertEqual(reopened.get(self.content['lesson_id'],self.content['version'])['status'],'approved_for_prototype')
        self.assertEqual(len(reopened.audit(self.content['lesson_id'],self.content['version'])),3)

if __name__=='__main__': unittest.main()
