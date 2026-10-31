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


def _checksum(statements):
    return hashlib.sha256('\n'.join(statements).encode('utf-8')).hexdigest()


def _normalized(sql):
    return ''.join(sql.split()).lower()


def _expected_tables():
    """Derive the current known synthetic baseline; no application data is added."""
    with sqlite3.connect(':memory:') as reference:
        reference.executescript(SCHEMA)
        return dict(reference.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))


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


def migrate(filename):
    """Upgrade one existing recognized database atomically; return newly applied versions.

    A schema check and all pending migrations share one transaction. Missing files,
    incompatible schemas, foreign-key violations, changed checksums, and unknown
    migration histories abort without granting privileges or changing user data.
    """
    path = Path(filename).resolve()
    if not path.is_file():
        raise MigrationError('An existing SQLite database file is required')
    db = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, isolation_level=None, timeout=5)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
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


def main():
    parser = argparse.ArgumentParser(description='Migrate an existing synthetic-only SQLite prototype database')
    parser.add_argument('--db', required=True, help='Existing database file (back it up first)')
    args = parser.parse_args()
    try:
        versions = migrate(args.db)
    except (MigrationError, sqlite3.DatabaseError, OSError) as exc:
        parser.exit(1, f'Migration failed; no changes committed: {exc}\n')
    print('Applied migrations: ' + (', '.join(map(str, versions)) if versions else 'none'))


if __name__ == '__main__':
    main()
