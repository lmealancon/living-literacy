import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prototype.lesson_engine import PolicyError
from prototype.migrations import MigrationError, migrate, _LEDGER, _MIGRATIONS, _normalized
from prototype.investigation_schema import CASE_PROGRESS_CREATE_SQL
from prototype.persistent_store import SCHEMA, SyntheticSQLiteStore


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fixtures.sqlite3'
        self.store = SyntheticSQLiteStore(self.path)
        self.token = self.store.provision_synthetic_family(
            'synthetic-family-1', 'synthetic-parent-1', 'synthetic-student-1')

    def tearDown(self):
        self.tmp.cleanup()

    def test_migration_is_idempotent_and_preserves_fixture_access(self):
        self.assertEqual(migrate(self.path), [1, 2])
        self.assertEqual(migrate(self.path), [])
        self.assertEqual(self.store.get_synthetic_profile(self.token, 'synthetic-student-1')['id'], 'synthetic-student-1')
        with sqlite3.connect(self.path) as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            self.assertIn('ll_idx_sessions_student', names)
            self.assertIn('ll_idx_audit_events_session', names)
            self.assertEqual(db.execute('SELECT count(*) FROM ll_schema_migrations').fetchone()[0], 2)

    def test_missing_or_revoked_authority_is_never_recreated(self):
        self.store.revoke_synthetic_guardian(self.token, 'synthetic-student-1')
        with self.store._connect() as db:
            db.execute('DELETE FROM synthetic_consents')
        migrate(self.path)
        with self.store._connect() as db:
            self.assertEqual(db.execute('SELECT status FROM guardian_relationships').fetchone()[0], 'revoked')
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_consents').fetchone()[0], 0)
        with self.assertRaises(PolicyError):
            self.store.get_synthetic_profile(self.token, 'synthetic-student-1')

    def test_unknown_schema_does_not_create_ledger_or_change_data(self):
        with sqlite3.connect(self.path) as db:
            db.execute('ALTER TABLE students ADD COLUMN unexpected TEXT')
        with self.assertRaises(MigrationError):
            migrate(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM students').fetchone()[0], 1)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())

    def test_migration_failure_rolls_back_ddl_and_ledger(self):
        failing = ((1, 'deliberate test migration', (
            'CREATE INDEX test_partial_index ON sessions(student_id)',
            'CREATE INDEX test_failing_index ON table_that_does_not_exist(id)',
        )),)
        with patch('prototype.migrations._MIGRATIONS', failing):
            with self.assertRaises(sqlite3.OperationalError):
                migrate(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='test_partial_index'").fetchone())
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())

    def test_unrecognized_or_tampered_history_fails_closed(self):
        migrate(self.path)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE ll_schema_migrations SET checksum='changed' WHERE version=1")
        with self.assertRaises(MigrationError):
            migrate(self.path)

    def test_missing_migration_index_is_not_silently_accepted(self):
        migrate(self.path)
        with sqlite3.connect(self.path) as db:
            db.execute('DROP INDEX ll_idx_sessions_student')
        with self.assertRaises(MigrationError):
            migrate(self.path)

    def test_missing_file_is_never_created(self):
        missing = Path(self.tmp.name) / 'missing.sqlite3'
        with self.assertRaises(MigrationError):
            migrate(missing)
        self.assertFalse(missing.exists())

    def test_unknown_ledger_trigger_cannot_mutate_existing_grants(self):
        with sqlite3.connect(self.path) as db:
            db.execute(_LEDGER)
            db.execute('CREATE TRIGGER hostile AFTER INSERT ON ll_schema_migrations BEGIN DELETE FROM grants; END')
        with self.assertRaises(MigrationError):
            migrate(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM grants').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM ll_schema_migrations').fetchone()[0], 0)

    def test_schema_comparison_preserves_quoted_sql_literals(self):
        self.assertEqual(_normalized("CHECK (kind = 'synthetic_family')"),
                         _normalized("check(kind='synthetic_family')"))
        self.assertNotEqual(_normalized("CHECK(kind='SYNTHETIC_FAMILY')"),
                            _normalized("CHECK(kind='synthetic_family')"))
        self.assertNotEqual(_normalized("CHECK(kind='synthetic family')"),
                            _normalized("CHECK(kind='syntheticfamily')"))
        self.assertNotEqual(_normalized("CHECK(kind='it''s A')"),
                            _normalized("CHECK(kind='it''s a')"))

    def test_changed_literal_in_database_schema_is_rejected_without_ledger(self):
        path = Path(self.tmp.name) / 'changed-literal.sqlite3'
        with sqlite3.connect(path) as db:
            db.executescript(SCHEMA.replace("kind='synthetic_family'", "kind='SYNTHETIC_FAMILY'"))
        with self.assertRaises(MigrationError):
            migrate(path)
        with sqlite3.connect(path) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())

    def test_unknown_view_is_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE VIEW unexpected AS SELECT id FROM students')
        with self.assertRaises(MigrationError):
            migrate(self.path)

    def test_case_migration_creates_an_empty_case_table(self):
        self.assertEqual(migrate(self.path), [1, 2])
        with sqlite3.connect(self.path) as db:
            sql = db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_case_progress'").fetchone()[0]
            self.assertEqual(_normalized(sql), _normalized(CASE_PROGRESS_CREATE_SQL))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_case_progress').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guardian_relationships').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_consents').fetchone()[0], 2)

    def test_migration_adopts_exact_populated_case_without_modifying_it(self):
        from prototype.investigation_store import SyntheticInvestigationStore
        case = SyntheticInvestigationStore(self.store)
        case.visit(self.token, 'synthetic-student-1', 0, 'voice')
        with sqlite3.connect(self.path) as db:
            before = db.execute('SELECT * FROM synthetic_case_progress').fetchall()
        self.assertEqual(migrate(self.path), [1, 2])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT * FROM synthetic_case_progress').fetchall(), before)
            self.assertIsNone(db.execute('PRAGMA foreign_key_check').fetchone())
        self.assertEqual(case.get(self.token, 'synthetic-student-1')['step'], 'decode')
        self.assertEqual(migrate(self.path), [])

    def test_existing_version_one_database_upgrades_without_rewriting_history(self):
        with patch('prototype.migrations._MIGRATIONS', _MIGRATIONS[:1]):
            self.assertEqual(migrate(self.path), [1])
        with sqlite3.connect(self.path) as db:
            before = db.execute('SELECT * FROM ll_schema_migrations WHERE version=1').fetchone()
        self.assertEqual(migrate(self.path), [2])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT * FROM ll_schema_migrations WHERE version=1').fetchone(), before)

    def test_unrecognized_existing_case_table_rolls_back_all_migration_changes(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE synthetic_case_progress (fictional_value TEXT)')
            db.execute("INSERT INTO synthetic_case_progress VALUES ('keep me')")
        with self.assertRaises(MigrationError):
            migrate(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT * FROM synthetic_case_progress').fetchall(), [('keep me',)])
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_idx_sessions_student'").fetchone())

    def test_adopting_case_table_rejects_broken_foreign_keys(self):
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute(CASE_PROGRESS_CREATE_SQL)
            db.execute('INSERT INTO synthetic_case_progress VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                ('synthetic-missing','synthetic-student-1','synthetic-parent-1',
                 'synthetic-vanishing-storybook-v1','post_office',0,-1,-1,-1,0,None))
        with self.assertRaises(MigrationError):
            migrate(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_case_progress').fetchone()[0], 1)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())

    def test_applied_case_table_cannot_be_silently_recreated(self):
        from prototype.investigation_store import SyntheticInvestigationStore
        migrate(self.path)
        with sqlite3.connect(self.path) as db:
            db.execute('DROP TABLE synthetic_case_progress')
        with self.assertRaises(MigrationError):
            migrate(self.path)
        with self.assertRaises(PolicyError):
            SyntheticInvestigationStore(self.store)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='synthetic_case_progress'").fetchone())


if __name__ == '__main__':
    unittest.main()
