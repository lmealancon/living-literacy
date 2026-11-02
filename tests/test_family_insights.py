import json
import tempfile
import unittest
from pathlib import Path

from prototype.family_insights import INTEREST_OPTIONS, SyntheticFamilyInsights
from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError
from prototype.persistent_store import SyntheticSQLiteStore


class FamilyInsightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SyntheticSQLiteStore(Path(self.tmp.name) / 'demo.sqlite3')
        self.a = self.store.provision_synthetic_family('synthetic-a', 'adult-a', 'synthetic-child-a')
        self.b = self.store.provision_synthetic_family('synthetic-b', 'adult-b', 'synthetic-child-b')
        self.insights = SyntheticFamilyInsights(self.store)
        content = json.loads(CONTENT_PATH.read_text())
        self.lesson, self.version = content['lesson_id'], content['version']
        registry = self.store.content_registry()
        registry.create_draft(content, 'synthetic-author')
        registry.transition(self.lesson, self.version, 'submit', 'synthetic-author', 'fixture')
        registry.transition(self.lesson, self.version, 'approve_prototype', 'synthetic-reviewer', 'fixture')

    def tearDown(self):
        self.tmp.cleanup()

    def test_interests_are_explicit_allowlisted_and_persistent(self):
        self.assertEqual(self.insights.get_interests(self.a, 'synthetic-child-a')['interests'], [])
        choices = ['music', 'stories']
        result = self.insights.set_interests(self.a, 'synthetic-child-a', choices)
        self.assertEqual(result['interests'], choices)
        self.assertEqual(result['options'], list(INTEREST_OPTIONS))
        reopened = SyntheticFamilyInsights(SyntheticSQLiteStore(self.store.filename))
        self.assertEqual(reopened.get_interests(self.a, 'synthetic-child-a')['interests'], choices)
        self.assertEqual(reopened.set_interests(self.a, 'synthetic-child-a', [])['interests'], [])

    def test_invalid_or_arbitrary_interests_are_denied(self):
        for choices in ['music', ['real personal details'], ['music', 'music'], [None], [['music']]]:
            with self.subTest(choices=choices), self.assertRaises(PolicyError):
                self.insights.set_interests(self.a, 'synthetic-child-a', choices)

    def test_other_family_and_revoked_guardian_denied(self):
        for action in (lambda: self.insights.get_interests(self.b, 'synthetic-child-a'),
                       lambda: self.insights.set_interests(self.b, 'synthetic-child-a', ['music']),
                       lambda: self.insights.activity_summary(self.b, 'synthetic-child-a')):
            with self.assertRaises(PolicyError): action()
        self.store.revoke_synthetic_guardian(self.a, 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.insights.get_interests(self.a, 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.insights.activity_summary(self.a, 'synthetic-child-a')

    def test_purpose_specific_withdrawal_denies_access(self):
        self.store.withdraw_synthetic_consent(self.a, 'synthetic-child-a', 'lesson')
        with self.assertRaises(PolicyError): self.insights.activity_summary(self.a, 'synthetic-child-a')
        self.assertEqual(self.insights.get_interests(self.a, 'synthetic-child-a')['interests'], [])
        self.store.withdraw_synthetic_consent(self.a, 'synthetic-child-a', 'profile')
        with self.assertRaises(PolicyError): self.insights.get_interests(self.a, 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.insights.set_interests(self.a, 'synthetic-child-a', ['art'])

    def test_activity_counts_do_not_expose_responses_or_infer_mastery(self):
        session = self.store.start(self.a, 'synthetic-child-a', self.lesson, self.version, 'session-key')
        self.store.transition(self.a, session.session_id, 'active', 0)
        self.store.record_response(self.a, session.session_id, 1, 'fictional response', {'audio_or_modeling': True})
        result = self.insights.activity_summary(self.a, 'synthetic-child-a')
        self.assertEqual((result['sessions_total'], result['sessions_active'], result['responses_total'], result['responses_assisted']), (1, 1, 1, 1))
        self.assertEqual(result['recent_sessions'][0]['stage'], 'activate')
        self.assertNotIn('fictional response', json.dumps(result))
        self.assertNotIn('mastery_status', result)
        self.assertEqual(result['sessions_completed'], 0)

    def test_malformed_saved_interests_fail_closed(self):
        with self.store._connect() as db:
            db.execute('INSERT INTO synthetic_profile_interests VALUES (?,?)', ('synthetic-child-a', '["private text"]'))
        with self.assertRaises(PolicyError): self.insights.get_interests(self.a, 'synthetic-child-a')


if __name__ == '__main__': unittest.main()
