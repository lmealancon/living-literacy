"""Synthetic version lineage preserves review and withdrawal gates."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from prototype.content_registry import SyntheticContentRegistry
from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError


class ContentRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = SyntheticContentRegistry(Path(self.temp.name) / 'synthetic.sqlite')
        self.content = json.loads(CONTENT_PATH.read_text(encoding='utf-8'))
        self.lid = self.content['lesson_id']
        self.parent_version = self.content['version']
        self.parent_digest = self.registry.create_draft(self.content, 'synthetic-author')

    def revision(self):
        content = copy.deepcopy(self.content)
        content['version'] = 'demo-2'
        content['title'] = 'A fictional revision for a separate review'
        return content

    def test_revision_is_separate_immutable_draft_with_source_pin(self):
        content = self.revision()
        digest = self.registry.create_revision(self.lid, self.parent_version, content, 'synthetic-author')
        self.assertNotEqual(digest, self.parent_digest)
        self.assertEqual(self.registry.get(self.lid, 'demo-2')['status'], 'draft')
        self.assertEqual(self.registry.get(self.lid, self.parent_version)['content'], self.content)
        self.assertEqual(self.registry.revision_source(self.lid, 'demo-2'), {
            'lesson_id': self.lid, 'version': 'demo-2', 'parent_version': self.parent_version,
            'parent_digest': self.parent_digest})
        self.assertEqual([event[0] for event in self.registry.audit(self.lid, 'demo-2')],
                         ['created', 'derived_from'])
        with self.assertRaisesRegex(PolicyError, 'CONTENT_NOT_APPROVED'):
            self.registry.for_synthetic_demo(self.lid, 'demo-2')
        with self.assertRaisesRegex(PolicyError, 'VERSION_IMMUTABLE'):
            self.registry.create_revision(self.lid, self.parent_version, content, 'synthetic-author')

    def test_approved_parent_does_not_approve_revision_or_allow_self_review(self):
        self.registry.transition(self.lid, self.parent_version, 'submit', 'synthetic-author', 'ready')
        self.registry.transition(self.lid, self.parent_version, 'approve_prototype', 'synthetic-reviewer', 'fixture')
        self.registry.create_revision(self.lid, self.parent_version, self.revision(), 'synthetic-author')
        self.registry.transition(self.lid, 'demo-2', 'submit', 'synthetic-author', 'ready')
        with self.assertRaisesRegex(PolicyError, 'SELF_APPROVAL_FORBIDDEN'):
            self.registry.transition(self.lid, 'demo-2', 'approve_prototype', 'synthetic-author', 'fixture')
        self.assertEqual(self.registry.get(self.lid, 'demo-2')['status'], 'in_review')

    def test_rejects_withdrawn_or_tampered_parent_without_writing_revision(self):
        self.registry.transition(self.lid, self.parent_version, 'submit', 'synthetic-author', 'ready')
        self.registry.transition(self.lid, self.parent_version, 'approve_prototype', 'synthetic-reviewer', 'fixture')
        self.registry.transition(self.lid, self.parent_version, 'suspend', 'synthetic-reviewer', 'withdrawn')
        with self.assertRaisesRegex(PolicyError, 'WITHDRAWN_SOURCE'):
            self.registry.create_revision(self.lid, self.parent_version, self.revision(), 'synthetic-author')
        with self.assertRaisesRegex(PolicyError, 'RESOURCE_NOT_FOUND'):
            self.registry.get(self.lid, 'demo-2')
        with self.registry._db() as db:
            db.execute('UPDATE content_versions SET status=?,payload=? WHERE lesson_id=? AND version=?',
                       ('draft', '{}', self.lid, self.parent_version))
        with self.assertRaisesRegex(PolicyError, 'CONTENT_INTEGRITY_FAILURE'):
            self.registry.create_revision(self.lid, self.parent_version, self.revision(), 'synthetic-author')
        with self.assertRaisesRegex(PolicyError, 'RESOURCE_NOT_FOUND'):
            self.registry.revision_source(self.lid, 'demo-2')

    def test_rejects_identity_version_and_unapproved_content_shape(self):
        for actor in ('synthetic-', 'real-author', '', None):
            with self.subTest(actor=actor), self.assertRaises(PolicyError):
                self.registry.create_revision(self.lid, self.parent_version, self.revision(), actor)
        same = self.revision(); same['version'] = self.parent_version
        with self.assertRaisesRegex(PolicyError, 'INVALID_REVISION'):
            self.registry.create_revision(self.lid, self.parent_version, same, 'synthetic-author')
        changed_id = self.revision(); changed_id['lesson_id'] = 'synthetic-other'
        with self.assertRaisesRegex(PolicyError, 'INVALID_REVISION'):
            self.registry.create_revision(self.lid, self.parent_version, changed_id, 'synthetic-author')
        bad_stages = self.revision(); bad_stages['stages'].pop()
        with self.assertRaises(PolicyError):
            self.registry.create_revision(self.lid, self.parent_version, bad_stages, 'synthetic-author')
        invalid_json = self.revision(); invalid_json['untrusted_number'] = float('nan')
        with self.assertRaisesRegex(PolicyError, 'INVALID_STAGE_CONTENT'):
            self.registry.create_revision(self.lid, self.parent_version, invalid_json, 'synthetic-author')
        with self.assertRaisesRegex(PolicyError, 'RESOURCE_NOT_FOUND'):
            self.registry.create_revision(self.lid, 'demo-missing', self.revision(), 'synthetic-author')

    def test_failed_audit_write_rolls_back_revision_and_lineage(self):
        with self.registry._db() as db:
            db.execute('''CREATE TRIGGER refuse_revision_audit BEFORE INSERT ON content_events
                          WHEN NEW.action = 'derived_from'
                          BEGIN SELECT RAISE(ABORT, 'simulated audit failure'); END''')
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.registry.create_revision(self.lid, self.parent_version, self.revision(), 'synthetic-author')
        with self.assertRaisesRegex(PolicyError, 'RESOURCE_NOT_FOUND'):
            self.registry.get(self.lid, 'demo-2')
        with self.assertRaisesRegex(PolicyError, 'RESOURCE_NOT_FOUND'):
            self.registry.revision_source(self.lid, 'demo-2')
        self.assertEqual(self.registry.get(self.lid, self.parent_version)['content'], self.content)

    def test_malformed_lineage_is_not_reported_as_verified(self):
        self.registry.create_revision(self.lid, self.parent_version, self.revision(), 'synthetic-author')
        with self.registry._db() as db:
            db.execute('UPDATE content_events SET note=? WHERE lesson_id=? AND version=? AND action=?',
                       ('{"parent_version":"demo-1","parent_digest":"not-a-digest"}',
                        self.lid, 'demo-2', 'derived_from'))
        with self.assertRaisesRegex(PolicyError, 'CONTENT_INTEGRITY_FAILURE'):
            self.registry.revision_source(self.lid, 'demo-2')


if __name__ == '__main__':
    unittest.main()
