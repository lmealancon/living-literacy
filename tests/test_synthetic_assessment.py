"""Assessment behavior on fictional profiles; these tests do not validate a screener."""
import tempfile
import unittest
from pathlib import Path

from prototype.lesson_engine import PolicyError
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.synthetic_assessment import SyntheticAssessmentStore


class SyntheticAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SyntheticSQLiteStore(Path(self.tmp.name) / 'store.sqlite')
        self.a = self.store.provision_synthetic_family('synthetic-a', 'synthetic-parent-a', 'synthetic-child-a')
        self.b = self.store.provision_synthetic_family('synthetic-b', 'synthetic-parent-b', 'synthetic-child-b')
        self.assessment = SyntheticAssessmentStore(self.store)
        self.assessment.add_reviewed_fixture('synthetic-form', 'v1', 'en',
            [{'id': 'synthetic-item', 'prompt': 'Fictional test item'}], 'synthetic-author', 'synthetic-reviewer')

    def tearDown(self):
        self.tmp.cleanup()

    def start(self):
        return self.assessment.start(self.a, 'synthetic-child-a', 'synthetic-form', 'v1')

    def test_explicit_consent_and_cross_family_isolation(self):
        with self.assertRaises(PolicyError): self.start()
        with self.assertRaises(PolicyError): self.assessment.set_synthetic_consent(self.b, 'synthetic-child-a', True)
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        with self.assertRaises(PolicyError): self.assessment.results(self.b, run['id'])
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', False)
        with self.assertRaises(PolicyError): self.assessment.results(self.a, run['id'])

    def test_expired_consent_and_revoked_guardian_deny(self):
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        with self.store._connect() as db:
            db.execute("UPDATE synthetic_assessment_consent SET expires_at='2000-01-01T00:00:00Z'")
        with self.assertRaises(PolicyError): self.assessment.results(self.a, run['id'])
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        self.store.revoke_synthetic_guardian(self.a, 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.assessment.results(self.a, run['id'])

    def test_assistance_recorded_without_automatic_scoring(self):
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        recorded = self.assessment.record_response(self.a, run['id'], 'synthetic-item', 'synthetic response', True, True)
        self.assertEqual(recorded['evidence_status'], 'needs_review')
        self.assertEqual(recorded['validation_status'], 'unvalidated')
        results = self.assessment.results(self.a, run['id'])
        self.assertTrue(results['responses'][0]['narration'])
        self.assertTrue(results['responses'][0]['assisted'])
        self.assertNotIn('score', results)
        with self.assertRaises(PolicyError):
            self.assessment.record_response(self.a, run['id'], 'synthetic-item', 'x', 'false', False)

    def test_narration_is_recorded_as_assistance_even_if_unchecked(self):
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        result = self.assessment.record_response(self.a, run['id'], 'synthetic-item', 'fictional', False, True)
        self.assertTrue(result['assisted'])
        self.assertTrue(self.assessment.results(self.a, run['id'])['responses'][0]['assisted'])

    def test_invalid_unicode_response_rejected(self):
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        with self.assertRaises(PolicyError):
            self.assessment.record_response(self.a, run['id'], 'synthetic-item', 'invalid-\ud800', False, False)
        self.assertEqual(self.assessment.results(self.a, run['id'])['responses'], [])

    def test_version_is_immutable_and_self_approval_rejected(self):
        with self.assertRaises(PolicyError):
            self.assessment.add_reviewed_fixture('synthetic-form', 'v1', 'en', [{'id': 'synthetic-i', 'prompt': 'x'}], 'synthetic-a', 'synthetic-b')
        with self.assertRaises(PolicyError):
            self.assessment.add_reviewed_fixture('synthetic-new', 'v1', 'en', [{'id': 'synthetic-i', 'prompt': 'x'}], 'synthetic-a', 'synthetic-a')

    def test_suspension_blocks_write_historical_read_remains(self):
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        with self.store._connect() as db:
            db.execute("UPDATE synthetic_assessment_forms SET status='suspended'")
        with self.assertRaises(PolicyError): self.start()
        with self.assertRaises(PolicyError):
            self.assessment.record_response(self.a, run['id'], 'synthetic-item', 'x', False, False)
        self.assertEqual(self.assessment.results(self.a, run['id'])['validation_status'], 'unvalidated')

    def test_payload_and_session_pin_tampering_denied(self):
        self.assessment.set_synthetic_consent(self.a, 'synthetic-child-a', True)
        run = self.start()
        with self.store._connect() as db:
            db.execute("UPDATE synthetic_assessment_forms SET payload='{}'")
        with self.assertRaises(PolicyError):
            self.assessment.record_response(self.a, run['id'], 'synthetic-item', 'x', False, False)


if __name__ == '__main__': unittest.main()
