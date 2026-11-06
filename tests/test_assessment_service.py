"""Presentation boundary for fictional-only assessment fixtures."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from prototype.assessment_service import SyntheticAssessmentService
from prototype.lesson_engine import PolicyError
from prototype.persistent_store import SyntheticSQLiteStore


class AssessmentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SyntheticSQLiteStore(Path(self.tmp.name) / 'test.sqlite')
        self.a = self.store.provision_synthetic_family('synthetic-a', 'synthetic-adult-a', 'synthetic-child-a')
        self.b = self.store.provision_synthetic_family('synthetic-b', 'synthetic-adult-b', 'synthetic-child-b')
        self.service = SyntheticAssessmentService(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def add_fixture(self):
        self.service.assessments.add_reviewed_fixture('synthetic-form', 'v1', 'en',
            [{'id': 'synthetic-item', 'prompt': 'Fictional item for an automated test'}],
            'synthetic-author', 'synthetic-reviewer')
        self.service.assessments.set_synthetic_consent(self.a, 'synthetic-child-a', True)

    def test_no_forms_are_fabricated(self):
        self.service.assessments.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        self.assertEqual(self.service.list_forms(self.a, 'synthetic-child-a'), {'forms': []})

    def test_listing_requires_specific_authorization_and_hides_questions(self):
        self.add_fixture()
        with self.assertRaises(PolicyError): self.service.list_forms(self.b, 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.service.list_forms(self.b, 'synthetic-child-b')
        forms = self.service.list_forms(self.a, 'synthetic-child-a')['forms']
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['validation_status'], 'unvalidated')
        self.assertNotIn('items', forms[0])

    def test_run_history_and_withdrawal(self):
        self.add_fixture()
        run = self.service.assessments.start(self.a, 'synthetic-child-a', 'synthetic-form', 'v1')
        self.assertEqual(self.service.get_run(self.a, run['id'])['items'][0]['id'], 'synthetic-item')
        with self.assertRaises(PolicyError): self.service.get_run(self.b, run['id'])
        self.service.assessments.record_response(self.a, run['id'], 'synthetic-item', 'synthetic text', True, True)
        self.assertEqual(self.service.list_history(self.a, 'synthetic-child-a')['runs'][0]['responses_recorded'], 1)
        with self.store._connect() as db: db.execute("UPDATE synthetic_assessment_forms SET status='suspended'")
        self.assertEqual(self.service.list_forms(self.a, 'synthetic-child-a'), {'forms': []})
        with self.assertRaises(PolicyError): self.service.get_run(self.a, run['id'])
        self.assertEqual(len(self.service.list_history(self.a, 'synthetic-child-a')['runs']), 1)
        self.service.assessments.set_synthetic_consent(self.a, 'synthetic-child-a', False)
        with self.assertRaises(PolicyError): self.service.list_history(self.a, 'synthetic-child-a')

    def test_tampering_blocks_listing_and_active_delivery(self):
        self.add_fixture()
        run = self.service.assessments.start(self.a, 'synthetic-child-a', 'synthetic-form', 'v1')
        with self.store._connect() as db: db.execute("UPDATE synthetic_assessment_forms SET payload='{}'")
        self.assertEqual(self.service.list_forms(self.a, 'synthetic-child-a'), {'forms': []})
        with self.assertRaises(PolicyError): self.service.get_run(self.a, run['id'])

    def test_malformed_rehashed_form_is_not_listed(self):
        self.add_fixture()
        payload = json.dumps({'language': 'en', 'items': [{'id': 'not-a-synthetic-id', 'prompt': 'Question'}]})
        with self.store._connect() as db:
            db.execute('UPDATE synthetic_assessment_forms SET payload=?,digest=?',
                       (payload, hashlib.sha256(payload.encode()).hexdigest()))
        self.assertEqual(self.service.list_forms(self.a, 'synthetic-child-a'), {'forms': []})

    def test_mismatched_recorded_workspace_denies_run_and_excludes_history(self):
        self.add_fixture()
        run = self.service.assessments.start(self.a, 'synthetic-child-a', 'synthetic-form', 'v1')
        with self.store._connect() as db:
            db.execute('UPDATE synthetic_assessment_runs SET workspace_id=? WHERE id=?', ('synthetic-b', run['id']))
        with self.assertRaises(PolicyError):
            self.service.get_run(self.a, run['id'])
        self.assertEqual(self.service.list_history(self.a, 'synthetic-child-a'), {'runs': []})

    def test_assessment_schema_creation_is_atomic(self):
        from prototype.synthetic_assessment import SyntheticAssessmentStore
        path = Path(self.tmp.name) / 'schema-test.sqlite'
        store = SyntheticSQLiteStore(path)
        original = store._connect
        @contextmanager
        def deny_second_table():
            with original() as db:
                db.set_authorizer(lambda action, name, *args:
                    sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TABLE
                    and name == 'synthetic_assessment_consent' else sqlite3.SQLITE_OK)
                try:
                    yield db
                finally:
                    db.set_authorizer(None)
        with patch.object(store, '_connect', deny_second_table):
            with self.assertRaises(sqlite3.DatabaseError):
                SyntheticAssessmentStore(store)
        with store._connect() as db:
            row = db.execute("SELECT 1 FROM sqlite_master WHERE name='synthetic_assessment_forms'").fetchone()
            self.assertIsNone(row)


if __name__ == '__main__':
    unittest.main()
