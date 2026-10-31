"""Synthetic-only parent credential and session experiment, not a real identity provider.

Do not enter real credentials. Existing demo bootstrap tokens remain valid until rotated.
"""
import hashlib
import hmac
import secrets
import time

from prototype.lesson_engine import PolicyError

SESSION_SECONDS = 3600


def ensure_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS synthetic_parent_credentials (
        identity_id TEXT PRIMARY KEY REFERENCES identities(id), salt BLOB NOT NULL,
        verifier BLOB NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS synthetic_auth_sessions (
        identity_id TEXT PRIMARY KEY REFERENCES identities(id), expires_at REAL NOT NULL)''')


def _digest(token):
    if not isinstance(token, str) or not token:
        raise PolicyError('RESOURCE_NOT_FOUND')
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def resolve(db, token):
    """Resolve an unexpired bearer token to an adult identity inside the caller's transaction."""
    ensure_schema(db)
    row = db.execute('''SELECT i.id, s.expires_at FROM identities i
        LEFT JOIN synthetic_auth_sessions s ON s.identity_id=i.id
        WHERE i.token_hash=?''', (_digest(token),)).fetchone()
    if not row or (row[1] is not None and row[1] <= time.time()):
        raise PolicyError('RESOURCE_NOT_FOUND')
    return row[0]


def _verifier(passphrase, salt):
    return hashlib.scrypt(passphrase.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)


def _check_passphrase(passphrase):
    if not isinstance(passphrase, str) or not 12 <= len(passphrase) <= 256:
        raise PolicyError('INVALID_SYNTHETIC_PASSPHRASE')


class SyntheticParentAuth:
    """Operates only on pre-provisioned fictional adults; not a production login system."""
    def __init__(self, store):
        self.store = store
        with store._connect() as db:
            ensure_schema(db)

    def enroll(self, token, passphrase):
        _check_passphrase(passphrase)
        with self.store._connect() as db:
            identity = resolve(db, token)
            if not identity.startswith('synthetic-'):
                raise PolicyError('SYNTHETIC_IDENTITY_REQUIRED')
            if db.execute('SELECT 1 FROM synthetic_parent_credentials WHERE identity_id=?', (identity,)).fetchone():
                raise PolicyError('ALREADY_ENROLLED')
            salt = secrets.token_bytes(16)
            db.execute('INSERT INTO synthetic_parent_credentials VALUES (?,?,?)',
                       (identity, salt, _verifier(passphrase, salt)))

    @staticmethod
    def _issue(db, identity):
        token = secrets.token_urlsafe(32)
        db.execute('UPDATE identities SET token_hash=? WHERE id=?', (_digest(token), identity))
        db.execute('''INSERT INTO synthetic_auth_sessions VALUES (?,?)
            ON CONFLICT(identity_id) DO UPDATE SET expires_at=excluded.expires_at''',
                   (identity, time.time() + SESSION_SECONDS))
        return token

    def login(self, identity, passphrase):
        _check_passphrase(passphrase)
        with self.store._connect() as db:
            row = db.execute('SELECT salt,verifier FROM synthetic_parent_credentials WHERE identity_id=?',
                             (identity,)).fetchone()
            if not row or not hmac.compare_digest(_verifier(passphrase, row[0]), row[1]):
                raise PolicyError('INVALID_CREDENTIALS')
            return self._issue(db, identity)

    def rotate(self, token):
        with self.store._connect() as db:
            return self._issue(db, resolve(db, token))

    def logout(self, token):
        with self.store._connect() as db:
            identity = resolve(db, token)
            # Invalidate all previously issued tokens without retaining their bearer values.
            db.execute('UPDATE identities SET token_hash=? WHERE id=?',
                       (_digest(secrets.token_urlsafe(32)), identity))
            db.execute('DELETE FROM synthetic_auth_sessions WHERE identity_id=?', (identity,))
