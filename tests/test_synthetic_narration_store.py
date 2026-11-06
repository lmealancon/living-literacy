"""Synthetic fixture boundary tests: no real voices, learners or approval."""
import io
import json
import sqlite3
import tempfile
import unittest
import wave
from dataclasses import replace
from pathlib import Path

from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import ConflictError, PolicyError
from prototype.persistent_store import SyntheticSQLiteStore
from prototype.story_vibes_policy import SyntheticAudio, SyntheticScript, SyntheticSource, digest_bytes
from prototype.synthetic_narration_store import MAX_PLAYBACKS_PER_SESSION, SyntheticNarrationStore


def synthetic_silence():
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b'\x00\x00' * 800)
    return stream.getvalue()


class SyntheticNarrationStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SyntheticSQLiteStore(Path(self.tmp.name) / 'fictional.sqlite')
        self.token = self.store.provision_synthetic_family('synthetic-family-a', 'synthetic-adult-a', 'synthetic-student-a')
        self.other = self.store.provision_synthetic_family('synthetic-family-b', 'synthetic-adult-b', 'synthetic-student-b')
        lesson = json.loads(CONTENT_PATH.read_text())
        self.lesson_id, self.version = lesson['lesson_id'], lesson['version']
        registry = self.store.content_registry()
        registry.create_draft(lesson, 'synthetic-author')
        registry.transition(self.lesson_id, self.version, 'submit', 'synthetic-author', 'fixture')
        registry.transition(self.lesson_id, self.version, 'approve_prototype', 'synthetic-reviewer', 'fixture')
        self.narration = SyntheticNarrationStore(self.store)
        text = lesson['stages'][0]['instruction']
        self.source = SyntheticSource(self.lesson_id, self.version, text, digest_bytes(text.encode()), 'approved_for_prototype')
        self.script = SyntheticScript('synthetic-script', '1', self.source.source_id, self.source.version,
            self.source.digest, 'Read Exactly', 'Reading Coach', text, digest_bytes(text.encode()),
            'approved_for_prototype', 'synthetic-writer', 'synthetic-reviewer', True)
        audio = synthetic_silence()
        self.audio = SyntheticAudio('synthetic-audio', '1', self.script.script_id, self.script.version,
            self.script.digest, audio, digest_bytes(audio), 'approved_for_prototype',
            'synthetic-producer', 'synthetic-audio-reviewer', text, 'Synthetic captions')
        self.session = self.store.start(self.token, 'synthetic-student-a', self.lesson_id, self.version, 'fixture-key')
        self.store.transition(self.token, self.session.session_id, 'active', 0)

    def tearDown(self):
        self.tmp.cleanup()

    def play(self, token=None, revision=1):
        return self.narration.playback(token or self.token, self.session.session_id, self.audio.asset_id, self.audio.version, revision)

    def test_no_fixtures_seeded_and_silent_wav_only_test_fixture(self):
        with self.assertRaises(PolicyError): self.play()
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        result = self.play()
        self.assertEqual(result['content_type'], 'audio/wav')
        self.assertEqual(result['data'], self.audio.data)
        self.assertTrue(result['exposure']['audio_or_modeling'])
        self.assertEqual(result['revision'], 2)
        self.assertEqual(self.store.audit_count(self.token, self.session.session_id), 3)

    def test_playback_conservatively_marks_later_independent_response_assisted(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        self.play()
        revision = 2
        for _ in range(4):
            self.store.advance_stage(self.token, self.session.session_id, revision)
            revision += 1
        response = self.store.record_response(self.token, self.session.session_id, revision,
            'synthetic response', {'audio_or_modeling': False}, independent_task=True)
        self.assertTrue(response['assistance']['audio_or_modeling'])
        self.assertTrue(response['assistance']['narration_exposure'])
        self.assertFalse(response['independent_evidence_eligible'])

    def test_denies_cross_family_revoked_consent_and_stale_revision(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        with self.assertRaises(PolicyError): self.play(token=self.other)
        with self.assertRaises(ConflictError): self.play(revision=0)
        self.store.withdraw_synthetic_consent(self.token, 'synthetic-student-a', 'lesson')
        with self.assertRaises(PolicyError): self.play()

    def test_suspended_lesson_or_asset_never_delivers_or_records_exposure(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        self.narration.suspend_fixture(self.audio.asset_id, self.audio.version)
        with self.assertRaises(PolicyError): self.play()
        self.assertEqual(self.store.get_session(self.token, self.session.session_id).narration_exposures, [])

    def test_withdrawn_lesson_blocks_existing_session_audio(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        self.store.content_registry().transition(self.lesson_id, self.version, 'suspend', 'synthetic-reviewer', 'fixture')
        with self.assertRaises(PolicyError): self.play()
        self.assertEqual(self.store.get_session(self.token, self.session.session_id).narration_exposures, [])

    def test_tampered_audio_and_wrong_stage_fail_closed(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        with self.store._connect() as db:
            db.execute('UPDATE synthetic_narration_fixtures SET audio=?', (b'changed',))
        with self.assertRaises(PolicyError): self.play()
        self.assertEqual(self.store.get_session(self.token, self.session.session_id).narration_exposures, [])
        self.store.advance_stage(self.token, self.session.session_id, 1)
        with self.assertRaises(PolicyError): self.play(revision=2)

    def test_cannot_register_invalid_audio_or_nonmatching_script(self):
        with self.assertRaises(PolicyError):
            self.narration.add_fixture(self.source, self.script, replace(self.audio, data=b'bad', digest=digest_bytes(b'bad')), 0)
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        with self.assertRaises(PolicyError): self.narration.add_fixture(self.source, self.script, self.audio, 0)

    def test_legacy_session_without_exposure_field_remains_readable(self):
        with self.store._connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM sessions WHERE id=?', (self.session.session_id,)).fetchone()[0])
            del payload['narration_exposures']
            db.execute('UPDATE sessions SET payload=? WHERE id=?', (json.dumps(payload), self.session.session_id))
        self.assertEqual(self.store.get_session(self.token, self.session.session_id).narration_exposures, [])
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        self.assertEqual(self.play()['revision'], 2)

    def test_audit_failure_rolls_back_exposure_and_revision(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        with self.store._connect() as db:
            db.execute('''CREATE TRIGGER fail_narration_audit BEFORE INSERT ON audit_events
                WHEN NEW.event='narration_playback_requested'
                BEGIN SELECT RAISE(ABORT, 'injected audit failure'); END''')
        with self.assertRaises(sqlite3.IntegrityError): self.play()
        session = self.store.get_session(self.token, self.session.session_id)
        self.assertEqual(session.revision, 1)
        self.assertEqual(session.narration_exposures, [])
        self.assertEqual(self.store.audit_count(self.token, self.session.session_id), 2)

    def test_resource_limit_denies_further_playback(self):
        self.narration.add_fixture(self.source, self.script, self.audio, 0)
        with self.store._connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM sessions WHERE id=?', (self.session.session_id,)).fetchone()[0])
            payload['narration_exposures'] = [{'stage': 0}] * MAX_PLAYBACKS_PER_SESSION
            db.execute('UPDATE sessions SET payload=? WHERE id=?', (json.dumps(payload), self.session.session_id))
        with self.assertRaises(PolicyError): self.play()
        self.assertEqual(self.store.get_session(self.token, self.session.session_id).revision, 1)


if __name__ == '__main__': unittest.main()
