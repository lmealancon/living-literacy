"""Governance invariants for synthetic content; not proof of reviewer identity."""
import json
import tempfile
import unittest
from pathlib import Path

from prototype.content_registry import SyntheticContentRegistry
from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError


class ReviewIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = SyntheticContentRegistry(Path(self.temp.name) / 'registry.sqlite')
        self.content = json.loads(CONTENT_PATH.read_text(encoding='utf-8'))
        self.key = (self.content['lesson_id'], self.content['version'])
        self.registry.create_draft(self.content, 'synthetic-author')

    def test_submitter_cannot_approve_own_submission(self):
        self.registry.transition(*self.key, 'submit', 'synthetic-submitter', 'Ready')
        with self.assertRaisesRegex(PolicyError, 'SELF_APPROVAL_FORBIDDEN'):
            self.registry.transition(*self.key, 'approve_prototype', 'synthetic-submitter', 'Reviewed')
        self.assertEqual(self.registry.get(*self.key)['status'], 'in_review')
        self.assertEqual(len(self.registry.audit(*self.key)), 2)
        self.registry.transition(*self.key, 'approve_prototype', 'synthetic-reviewer', 'Reviewed')

    def test_integrity_is_verified_before_approval(self):
        self.registry.transition(*self.key, 'submit', 'synthetic-author', 'Ready')
        with self.registry._db() as db:
            db.execute('UPDATE content_versions SET payload=? WHERE lesson_id=? AND version=?',
                       ('{}', *self.key))
        with self.assertRaisesRegex(PolicyError, 'CONTENT_INTEGRITY_FAILURE'):
            self.registry.transition(*self.key, 'approve_prototype', 'synthetic-reviewer', 'Reviewed')
        with self.registry._db() as db:
            status = db.execute('SELECT status FROM content_versions WHERE lesson_id=? AND version=?', self.key).fetchone()[0]
        self.assertEqual(status, 'in_review')
        self.assertEqual(len(self.registry.audit(*self.key)), 2)

    def test_invalid_actor_is_policy_error(self):
        with self.assertRaisesRegex(PolicyError, 'REVIEW_AUDIT_REQUIRED'):
            self.registry.transition(*self.key, 'submit', 42, 'Ready')


if __name__ == '__main__':
    unittest.main()
