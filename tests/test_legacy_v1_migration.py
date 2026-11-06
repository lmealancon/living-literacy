"""Migration from the frozen v1.0 synthetic schema never confers authority."""
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from prototype.lesson_engine import PolicyError
from prototype.content_registry import SyntheticContentRegistry
from prototype.instructional_content import CONTENT_PATH
from prototype.migrations import MigrationError, migrate, upgrade_legacy_v1
from prototype.persistent_store import SyntheticSQLiteStore

FIXTURE = Path(__file__).parent / 'fixtures' / 'synthetic_v1_schema.sql'
CONTENT_FIXTURE = Path(__file__).parent / 'fixtures' / 'synthetic_v1_content_schema.sql'


class LegacyV1MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional.sqlite'
        self.token = 'fictional-test-token'
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(FIXTURE.read_text())
            db.execute("INSERT INTO workspaces VALUES ('synthetic-family','synthetic_family')")
            db.execute('INSERT INTO identities VALUES (?,?)', ('fictional-parent', hashlib.sha256(self.token.encode()).hexdigest()))
            db.execute("INSERT INTO memberships VALUES ('fictional-parent','synthetic-family')")
            db.execute("INSERT INTO students VALUES ('synthetic-student','synthetic-family',1)")
            db.execute("INSERT INTO grants VALUES ('fictional-parent','synthetic-student')")
            db.execute("INSERT INTO sessions VALUES ('session-1','synthetic-family','synthetic-student','{}',0)")
            db.execute("INSERT INTO audit_events(session_id,event,revision,actor_id) VALUES ('session-1','created',0,'fictional-parent')")

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_upgrade_preserves_records_but_never_infers_authority(self):
        with self.assertRaises(MigrationError):
            migrate(self.path)
        self.assertEqual(upgrade_legacy_v1(self.path), [1])
        self.assertEqual(migrate(self.path), [])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM students').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM grants').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM guardian_relationships').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_consents').fetchone()[0], 0)
        with self.assertRaises(PolicyError):
            SyntheticSQLiteStore(self.path).get_synthetic_profile(self.token, 'synthetic-student')
        with self.assertRaises(MigrationError):
            upgrade_legacy_v1(self.path)

    def test_unknown_partial_schema_is_rejected_without_changes(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE guardian_relationships (identity_id TEXT)')
        with self.assertRaises(MigrationError):
            upgrade_legacy_v1(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='synthetic_consents'").fetchone())
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM grants').fetchone()[0], 1)

    def test_failing_foreign_key_validation_rolls_back_added_tables(self):
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute("INSERT INTO grants VALUES ('unknown-parent','synthetic-student')")
        with self.assertRaises(MigrationError):
            upgrade_legacy_v1(self.path)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='guardian_relationships'").fetchone())
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='synthetic_consents'").fetchone())
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone())

    def test_database_with_unknown_trigger_is_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TRIGGER unexpected AFTER INSERT ON students BEGIN UPDATE students SET synthetic=1; END')
        with self.assertRaises(MigrationError):
            upgrade_legacy_v1(self.path)

    def test_existing_approved_prototype_content_and_audit_are_preserved(self):
        lesson = json.loads(CONTENT_PATH.read_text(encoding='utf-8'))
        key = (lesson['lesson_id'], lesson['version'])
        payload = json.dumps(lesson, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        # Populate the historical schema directly. Initializing the *current*
        # registry here could silently add newer tables to the old database.
        with sqlite3.connect(self.path) as db:
            db.executescript(CONTENT_FIXTURE.read_text())
            db.execute('INSERT INTO content_versions VALUES (?,?,?,?,?)', (*key, payload, digest, 'approved_for_prototype'))
            db.execute('INSERT INTO content_events(lesson_id,version,action,actor,note) VALUES (?,?,?,?,?)',
                       (*key, 'approve_prototype', 'synthetic-reviewer', 'fictional approval'))
        with sqlite3.connect(self.path) as db:
            original_record = db.execute('SELECT * FROM content_versions').fetchall()
            original_events = db.execute('SELECT * FROM content_events').fetchall()
        self.assertEqual(upgrade_legacy_v1(self.path), [1])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT * FROM content_versions').fetchall(), original_record)
            self.assertEqual(db.execute('SELECT * FROM content_events').fetchall(), original_events)
        registry = SyntheticContentRegistry(self.path)
        self.assertEqual(registry.for_synthetic_demo(*key), lesson)
        # Content being preserved does not override the missing guardian consent.
        with self.assertRaises(PolicyError):
            SyntheticSQLiteStore(self.path).get_synthetic_profile(self.token, 'synthetic-student')

    def test_cli_requires_explicit_legacy_option(self):
        project = Path(__file__).resolve().parents[1]
        command = [sys.executable, '-m', 'prototype.migrations', '--db', str(self.path)]
        denied = subprocess.run(command, cwd=project, capture_output=True, text=True)
        self.assertNotEqual(denied.returncode, 0)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='guardian_relationships'").fetchone())
        accepted = subprocess.run(command + ['--from-legacy-v1'], cwd=project, capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn('Applied migrations: 1', accepted.stdout)
        self.assertEqual(migrate(self.path), [])


if __name__ == '__main__':
    unittest.main()
