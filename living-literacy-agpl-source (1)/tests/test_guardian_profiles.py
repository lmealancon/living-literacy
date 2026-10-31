"""Synthetic authorization checks at the existing persistence boundary."""
import json
import tempfile
import unittest
from pathlib import Path

from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.synthetic_auth import SyntheticParentAuth


class GuardianProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SyntheticSQLiteStore(Path(self.tmp.name) / 'test.sqlite')
        self.token = self.store.provision_synthetic_family('synthetic-family-a', 'adult-a', 'synthetic-child-a')
        self.other = self.store.provision_synthetic_family('synthetic-family-b', 'adult-b', 'synthetic-child-b')
        content = json.loads(CONTENT_PATH.read_text())
        self.lesson_id, self.version = content['lesson_id'], content['version']
        registry = self.store.content_registry()
        registry.create_draft(content, 'synthetic-author')
        registry.transition(self.lesson_id, self.version, 'submit', 'synthetic-author', 'ready')
        registry.transition(self.lesson_id, self.version, 'approve_prototype', 'synthetic-reviewer', 'reviewed')
        self.session = self.store.start(self.token, 'synthetic-child-a', self.lesson_id, self.version, 'key')

    def tearDown(self):
        self.tmp.cleanup()

    def test_profile_creation_derives_workspace_from_existing_authority(self):
        profile = self.store.create_synthetic_profile(self.token, 'synthetic-child-a', 'synthetic-child-new')
        self.assertEqual(profile['workspace_id'], 'synthetic-family-a')
        self.assertEqual(self.store.get_synthetic_profile(self.token, 'synthetic-child-new'), profile)
        with self.assertRaises(PolicyError):
            self.store.get_synthetic_profile(self.other, 'synthetic-child-new')
        with self.assertRaises(PolicyError):
            self.store.create_synthetic_profile(self.other, 'synthetic-child-a', 'synthetic-child-forged')
        with self.assertRaises(PolicyError):
            self.store.create_synthetic_profile(self.token, 'synthetic-child-a', 'real-child')

    def test_revoked_guardian_denied_existing_and_new_operations(self):
        self.store.revoke_synthetic_guardian(self.token, 'synthetic-child-a')
        for operation in (
            lambda: self.store.get_synthetic_profile(self.token, 'synthetic-child-a'),
            lambda: self.store.get_session(self.token, self.session.session_id),
            lambda: self.store.transition(self.token, self.session.session_id, 'active', 0),
            lambda: self.store.start(self.token, 'synthetic-child-a', self.lesson_id, self.version, 'new'),
        ):
            with self.assertRaises(PolicyError): operation()

    def test_consent_withdrawal_is_purpose_specific(self):
        self.store.withdraw_synthetic_consent(self.token, 'synthetic-child-a', 'lesson')
        self.assertEqual(self.store.get_synthetic_profile(self.token, 'synthetic-child-a')['id'], 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.store.get_session(self.token, self.session.session_id)
        with self.assertRaises(PolicyError): self.store.transition(self.token, self.session.session_id, 'active', 0)

    def test_expired_and_malformed_consent_fail_closed(self):
        for expiry in ('2000-01-01T00:00:00Z', 'not-a-date'):
            with self.store._connect() as db:
                db.execute("UPDATE synthetic_consents SET expires_at=? WHERE student_id=? AND purpose='lesson'", (expiry, 'synthetic-child-a'))
            with self.assertRaises(PolicyError): self.store.get_session(self.token, self.session.session_id)

    def test_missing_relationship_or_consent_denies_access(self):
        with self.store._connect() as db:
            db.execute("DELETE FROM synthetic_consents WHERE student_id=? AND purpose='profile'", ('synthetic-child-a',))
        with self.assertRaises(PolicyError): self.store.get_synthetic_profile(self.token, 'synthetic-child-a')
        with self.store._connect() as db:
            db.execute("DELETE FROM guardian_relationships WHERE student_id=?", ('synthetic-child-a',))
        with self.assertRaises(PolicyError): self.store.get_session(self.token, self.session.session_id)

    def test_rotated_and_logged_out_tokens_cannot_access_profiles_or_sessions(self):
        auth = SyntheticParentAuth(self.store)
        rotated = auth.rotate(self.token)
        with self.assertRaises(PolicyError): self.store.get_session(self.token, self.session.session_id)
        self.assertEqual(self.store.get_synthetic_profile(rotated, 'synthetic-child-a')['id'], 'synthetic-child-a')
        auth.logout(rotated)
        with self.assertRaises(PolicyError): self.store.get_synthetic_profile(rotated, 'synthetic-child-a')
        with self.assertRaises(PolicyError): self.store.get_session(rotated, self.session.session_id)


if __name__ == '__main__':
    unittest.main()
