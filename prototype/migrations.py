"""Explicit migrations for recognized synthetic SQLite prototype databases only.

This is a local-development bridge, not a production or PostgreSQL migration.
Back up first. Unrecognized base schemas or migration histories are rejected;
a migration never creates guardian relationships, grants, or consent records.
"""
import argparse
import hashlib
import sqlite3
from pathlib import Path

from prototype.persistent_store import SCHEMA


class MigrationError(Exception):
    """The database is not a recognized, safely migratable prototype."""


# Keep applied migration text immutable. Changes belong in a new version.
_MIGRATIONS = (
    (1, 'Add indexes for synthetic activity history and audit lookup', (
        'CREATE INDEX ll_idx_sessions_student ON sessions(student_id)',
        'CREATE INDEX ll_idx_audit_events_session ON audit_events(session_id)',
    )),
)
_LEDGER = '''CREATE TABLE ll_schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)'''

# Frozen v1.0 prototype schema. Never derive an old version from the current
# SCHEMA: changing the application schema later must not redefine what an old
# database is allowed to look like.
_LEGACY_V1_SCHEMA = '''
CREATE TABLE workspaces(id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='synthetic_family'));
CREATE TABLE identities(id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE);
CREATE TABLE memberships(identity_id TEXT NOT NULL REFERENCES identities(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id), PRIMARY KEY(identity_id,workspace_id));
CREATE TABLE students(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), synthetic INTEGER NOT NULL CHECK(synthetic=1));
CREATE TABLE grants(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), PRIMARY KEY(identity_id,student_id));
CREATE TABLE lessons(id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(id,version));
CREATE TABLE sessions(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), student_id TEXT NOT NULL REFERENCES students(id), payload TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE idempotency(workspace_id TEXT NOT NULL, identity_id TEXT NOT NULL, key TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(id), PRIMARY KEY(workspace_id,identity_id,key));
CREATE TABLE session_content_pins(session_id TEXT PRIMARY KEY REFERENCES sessions(id), digest TEXT NOT NULL);
CREATE TABLE audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id), event TEXT NOT NULL, revision INTEGER NOT NULL, actor_id TEXT NOT NULL);
'''

_LEGACY_V1_CONTENT_SCHEMA = '''
CREATE TABLE content_versions (
 lesson_id TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
 digest TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
 ('draft','in_review','approved_for_prototype','suspended','retired')),
 PRIMARY KEY(lesson_id,version));
CREATE TABLE content_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id TEXT NOT NULL, version TEXT NOT NULL,
 action TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL,
 FOREIGN KEY(lesson_id,version) REFERENCES content_versions(lesson_id,version));
'''

_LEGACY_V1_AUTHORITY = (
    "CREATE TABLE guardian_relationships(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), status TEXT NOT NULL CHECK(status IN ('active','revoked')), PRIMARY KEY(identity_id,student_id))",
    "CREATE TABLE synthetic_consents(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), purpose TEXT NOT NULL CHECK(purpose IN ('lesson','profile')), status TEXT NOT NULL CHECK(status IN ('active','withdrawn')), expires_at TEXT, PRIMARY KEY(identity_id,student_id,purpose))",
)


def _checksum(statements):
    return hashlib.sha256('\n'.join(statements).encode('utf-8')).hexdigest()


def _normalized(sql):
    """Ignore SQL formatting outside quoted tokens, never alter literal contents."""
    result = []
    quote = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            result.append(char)
            closing = ']' if quote == '[' else quote
            if char == closing:
                if quote != '[' and index + 1 < len(sql) and sql[index + 1] == closing:
                    index += 1
                    result.append(sql[index])
                else:
                    quote = None
        elif char in ("'", '"', '`', '['):
            quote = char
            result.append(char)
        elif not char.isspace():
            result.append(char.lower())
        index += 1
    return ''.join(result)


def _tables_for(schema):
    with sqlite3.connect(':memory:') as reference:
        reference.executescript(schema)
        return dict(reference.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))


def _expected_tables():
    """Derive the current known synthetic baseline; no application data is added."""
    return _tables_for(SCHEMA)


def _check_legacy_v1(db):
    """Recognize the frozen 1.0 synthetic database without inventing authority."""
    actual = dict(db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    expected = _tables_for(_LEGACY_V1_SCHEMA)
    content = _tables_for(_LEGACY_V1_CONTENT_SCHEMA)
    if not set(expected) <= set(actual) or set(actual) - set(expected) - set(content):
        raise MigrationError('Unrecognized legacy v1 tables')
    if bool(set(actual) & set(content)) and not set(content) <= set(actual):
        raise MigrationError('Incomplete legacy content schema')
    for name in actual:
        if _normalized(actual[name]) != _normalized((expected | content)[name]):
            raise MigrationError('Unrecognized legacy v1 schema: ' + name)
    if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
        raise MigrationError('Legacy views or triggers require manual review')


def _check_baseline(db):
    actual = dict(db.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"))
    for name, sql in _expected_tables().items():
        if name not in actual or _normalized(actual[name]) != _normalized(sql):
            raise MigrationError('Unrecognized prototype schema: ' + name)
    # The existing prototype marks workspaces and students as synthetic. Check
    # both schema constraints (above) and stored data; never infer guardian rights.
    if db.execute("SELECT 1 FROM workspaces WHERE kind != 'synthetic_family' OR id NOT LIKE 'synthetic-%' LIMIT 1").fetchone():
        raise MigrationError('Non-synthetic workspace data is unsupported')
    if db.execute("SELECT 1 FROM students WHERE synthetic != 1 OR id NOT LIKE 'synthetic-%' OR workspace_id NOT LIKE 'synthetic-%' LIMIT 1").fetchone():
        raise MigrationError('Non-synthetic student data is unsupported')
    if db.execute('PRAGMA foreign_key_check').fetchone():
        raise MigrationError('Database has foreign key violations')


def _check_migration_objects(db, migrations):
    # Each migrated index is immutable. A ledger alone does not prove that its
    # expected index is still present with the right definition.
    for _, _, statements in migrations:
        for statement in statements:
            words = statement.split()
            if len(words) < 3 or words[:2] != ['CREATE', 'INDEX']:
                raise MigrationError('Unsupported migration object')
            row = db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (words[2],)).fetchone()
            if not row or _normalized(row[0]) != _normalized(statement):
                raise MigrationError('Migration index missing or changed: ' + words[2])


def _migrate_open_database(filename, legacy_v1):
    path = Path(filename).resolve()
    if not path.is_file():
        raise MigrationError('An existing SQLite database file is required')
    db = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, isolation_level=None, timeout=5)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        # Unrecognized triggers can run on the migration ledger or protected
        # tables and mutate existing records. Reject before any migration DDL.
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
            raise MigrationError('Views or triggers require manual review')
        if legacy_v1:
            _check_legacy_v1(db)
            # Legacy identity tokens and grants are retained, but they alone do
            # not authorize access. Newly created relationships/consents are
            # intentionally empty and must never be inferred or backfilled.
            for statement in _LEGACY_V1_AUTHORITY:
                db.execute(statement)
        _check_baseline(db)
        present = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ll_schema_migrations'").fetchone()
        if present:
            if _normalized(present[0]) != _normalized(_LEDGER):
                raise MigrationError('Unrecognized migration ledger')
        else:
            db.execute(_LEDGER)
        applied = list(db.execute('SELECT version, description, checksum FROM ll_schema_migrations ORDER BY version'))
        expected = [(version, description, _checksum(statements)) for version, description, statements in _MIGRATIONS]
        if applied != expected[:len(applied)] or len(applied) > len(expected):
            raise MigrationError('Unrecognized or modified migration history')
        _check_migration_objects(db, _MIGRATIONS[:len(applied)])
        newly_applied = []
        for version, description, statements in _MIGRATIONS[len(applied):]:
            for statement in statements:
                db.execute(statement)
            db.execute('INSERT INTO ll_schema_migrations(version, description, checksum) VALUES (?,?,?)',
                       (version, description, _checksum(statements)))
            newly_applied.append(version)
        _check_migration_objects(db, _MIGRATIONS)
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise MigrationError('Database has foreign key violations')
        db.commit()
        return newly_applied
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def migrate(filename):
    """Upgrade an existing recognized current synthetic schema atomically.

    Back up first. Unknown schemas, foreign-key violations, changed checksums,
    and unknown migration histories abort without modifying user data.
    """
    return _migrate_open_database(filename, False)


def upgrade_legacy_v1(filename):
    """Opt in to a fail-closed upgrade from the frozen v1.0 synthetic schema.

    Adds only empty relationship/consent tables, then applies known migrations
    in the same transaction. It cannot establish guardian authority or consent.
    """
    return _migrate_open_database(filename, True)


def main():
    parser = argparse.ArgumentParser(description='Migrate an existing synthetic-only SQLite prototype database')
    parser.add_argument('--db', required=True, help='Existing database file (back it up first)')
    parser.add_argument('--from-legacy-v1', action='store_true',
                        help='Explicitly upgrade recognized v1.0; new guardian/consent tables remain empty')
    args = parser.parse_args()
    try:
        versions = upgrade_legacy_v1(args.db) if args.from_legacy_v1 else migrate(args.db)
    except (MigrationError, sqlite3.DatabaseError, OSError) as exc:
        parser.exit(1, f'Migration failed; no changes committed: {exc}\n')
    print('Applied migrations: ' + (', '.join(map(str, versions)) if versions else 'none'))


if __name__ == '__main__':
    main()
