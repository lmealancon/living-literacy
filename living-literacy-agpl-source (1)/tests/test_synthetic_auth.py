"""Tests use fictional accounts and credentials only."""
import tempfile
import unittest
from unittest.mock import patch

from prototype.lesson_engine import PolicyError
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.synthetic_auth import SyntheticParentAuth, resolve


class SyntheticParentAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SyntheticSQLiteStore(self.temp.name + '/test.sqlite')
        self.token = self.store.provision_synthetic_family('synthetic-family', 'synthetic-parent', 'synthetic-child')
        self.auth = SyntheticParentAuth(self.store)
        self.auth.enroll(self.token, 'fictional-passphrase')

    def resolved(self, token):
        with self.store._connect() as db:
            return resolve(db, token)

    def test_login_requires_credentials_and_invalidates_prior_session(self):
        with self.assertRaises(PolicyError):
            self.auth.login('synthetic-parent', 'incorrect-passphrase')
        with self.assertRaises(PolicyError):
            self.auth.login('synthetic-other', 'fictional-passphrase')
        token = self.auth.login('synthetic-parent', 'fictional-passphrase')
        self.assertEqual(self.resolved(token), 'synthetic-parent')
        with self.assertRaises(PolicyError):
            self.resolved(self.token)

    def test_rotation_and_logout_invalidate_session(self):
        rotated = self.auth.rotate(self.token)
        with self.assertRaises(PolicyError):
            self.resolved(self.token)
        self.assertEqual(self.resolved(rotated), 'synthetic-parent')
        self.auth.logout(rotated)
        with self.assertRaises(PolicyError):
            self.resolved(rotated)
        with self.assertRaises(PolicyError):
            self.auth.rotate(rotated)
        self.assertEqual(self.resolved(self.auth.login('synthetic-parent', 'fictional-passphrase')), 'synthetic-parent')

    def test_expired_session_is_denied(self):
        with patch('prototype.synthetic_auth.time.time', return_value=100):
            token = self.auth.rotate(self.token)
        with patch('prototype.synthetic_auth.time.time', return_value=3700):
            with self.assertRaises(PolicyError):
                self.resolved(token)
            with self.assertRaises(PolicyError):
                self.auth.rotate(token)

    def test_enrollment_requires_existing_token_and_cannot_replace_credentials(self):
        with self.assertRaises(PolicyError):
            self.auth.enroll('not-a-token', 'fictional-passphrase')
        with self.assertRaises(PolicyError):
            self.auth.enroll(self.token, 'new-fictional-passphrase')
        with self.assertRaises(PolicyError):
            self.auth.enroll(self.token, 'short')

if __name__ == '__main__':
    unittest.main()
