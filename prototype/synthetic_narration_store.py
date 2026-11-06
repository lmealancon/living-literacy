"""Authorized, synthetic-only WAV fixture playback boundary.

No assets are seeded. Fixture setup and withdrawal are trusted local operations,
not real review or APIs for end users. Before exposing any audio endpoint the
application still needs a reviewed asset and human, privacy and deployment gates.
"""
import hashlib
import io
import json
import wave
from dataclasses import asdict

from prototype.lesson_engine import ConflictError, LessonEngine, PolicyError
from prototype.story_vibes_policy import (
    SyntheticAudio, SyntheticScript, SyntheticSource, evaluate_synthetic_playback,
)

_SCHEMA = '''CREATE TABLE IF NOT EXISTS synthetic_narration_fixtures (
 asset_id TEXT NOT NULL, asset_version TEXT NOT NULL, lesson_id TEXT NOT NULL,
 lesson_version TEXT NOT NULL, stage_index INTEGER NOT NULL, metadata TEXT NOT NULL,
 audio BLOB NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','suspended')),
 PRIMARY KEY(asset_id,asset_version))'''

# Resource bound for this synthetic prototype, not an instructional threshold.
MAX_PLAYBACKS_PER_SESSION = 200


def _valid_wav(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 5 * 1024 * 1024:
        return False
    try:
        with wave.open(io.BytesIO(data), 'rb') as audio:
            channels, width, rate, frames = audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()
            if (audio.getcomptype() != 'NONE' or channels not in (1, 2) or width not in (1, 2, 3, 4)
                    or not 8000 <= rate <= 48000 or not 0 < frames <= rate * 60):
                return False
            return len(audio.readframes(frames)) == frames * channels * width
    except (EOFError, OSError, ValueError, wave.Error):
        return False


class SyntheticNarrationStore:
    def __init__(self, store):
        self.store = store
        with store._connect() as db:
            db.execute(_SCHEMA)

    @staticmethod
    def _lesson_stage(db, lesson_id, version, stage_index):
        if type(stage_index) is not int or not 0 <= stage_index < 6:
            raise PolicyError('NARRATION_UNAVAILABLE')
        row = db.execute('SELECT payload,digest,status FROM content_versions WHERE lesson_id=? AND version=?',
                         (lesson_id, version)).fetchone()
        if not row or row[2] != 'approved_for_prototype' or hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise PolicyError('NARRATION_UNAVAILABLE')
        try:
            lesson = json.loads(row[0])
            return lesson['stages'][stage_index]['instruction']
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise PolicyError('NARRATION_UNAVAILABLE') from exc

    def add_fixture(self, source, script, audio, stage_index):
        """Install pre-reviewed *simulated* fixture, only from trusted local setup.

        This is not a real review, must never be exposed to end users, and does
        not establish rights, legal consent, or student-facing approval.
        """
        if not isinstance(source, SyntheticSource) or not isinstance(script, SyntheticScript) or not isinstance(audio, SyntheticAudio):
            raise PolicyError('NARRATION_UNAVAILABLE')
        evaluate_synthetic_playback(source, script, audio, mode=script.mode, style=script.style)
        if not _valid_wav(audio.data):
            raise PolicyError('NARRATION_UNAVAILABLE')
        metadata = {'source': asdict(source), 'script': asdict(script), 'audio': asdict(audio)}
        del metadata['audio']['data']
        with self.store._connect() as db:
            instruction = self._lesson_stage(db, source.source_id, source.version, stage_index)
            if source.text != instruction:
                raise PolicyError('NARRATION_UNAVAILABLE')
            if db.execute('SELECT 1 FROM synthetic_narration_fixtures WHERE asset_id=? AND asset_version=?',
                          (audio.asset_id, audio.version)).fetchone():
                raise PolicyError('IMMUTABLE_NARRATION_VERSION')
            db.execute('INSERT INTO synthetic_narration_fixtures VALUES (?,?,?,?,?,?,?,?)',
                       (audio.asset_id, audio.version, source.source_id, source.version, stage_index,
                        json.dumps(metadata, ensure_ascii=False, sort_keys=True), audio.data, 'active'))

    def suspend_fixture(self, asset_id, asset_version):
        """Trusted local simulated withdrawal; recorded data is retained."""
        with self.store._connect() as db:
            db.execute("UPDATE synthetic_narration_fixtures SET status='suspended' WHERE asset_id=? AND asset_version=? AND status='active'", (asset_id, asset_version))
            if db.execute('SELECT changes()').fetchone()[0] != 1:
                raise PolicyError('NARRATION_UNAVAILABLE')

    def playback(self, token, session_id, asset_id, asset_version, expected_revision):
        """Authorize, validate current content and record exposure atomically.

        Records a conservative exposure *before* returning bytes; a failed client
        delivery may therefore count as assistance. Callers must not cache bytes
        across authorization or withdrawal checks.
        """
        if type(expected_revision) is not int:
            raise PolicyError('NARRATION_UNAVAILABLE')
        with self.store._connect() as db:
            row = db.execute('SELECT payload,revision,student_id FROM sessions WHERE id=?', (session_id,)).fetchone()
            if not row:
                raise PolicyError('RESOURCE_NOT_FOUND')
            actor = self.store._actor(db, token, row[2])
            session = self.store._deserialize(row[0])
            if expected_revision != session.revision:
                raise ConflictError('REVISION_CONFLICT')
            if session.status != 'active':
                raise PolicyError('NARRATION_UNAVAILABLE')
            if len(session.narration_exposures) >= MAX_PLAYBACKS_PER_SESSION:
                raise PolicyError('NARRATION_UNAVAILABLE')
            self.store._require_active_pinned_content(db, session)
            fixture = db.execute('''SELECT lesson_id,lesson_version,stage_index,metadata,audio,status
                FROM synthetic_narration_fixtures WHERE asset_id=? AND asset_version=?''',
                                 (asset_id, asset_version)).fetchone()
            if not fixture or fixture[5] != 'active' or (fixture[0], fixture[1], fixture[2]) != (session.lesson_id, session.lesson_version, session.stage_index):
                raise PolicyError('NARRATION_UNAVAILABLE')
            try:
                data = json.loads(fixture[3])
                source = SyntheticSource(**data['source'])
                script = SyntheticScript(**data['script'])
                audio = SyntheticAudio(**data['audio'], data=bytes(fixture[4]))
                instruction = self._lesson_stage(db, session.lesson_id, session.lesson_version, session.stage_index)
                if (source.source_id, source.version, source.text, audio.asset_id, audio.version) != (session.lesson_id, session.lesson_version, instruction, asset_id, asset_version) or not _valid_wav(audio.data):
                    raise PolicyError('NARRATION_UNAVAILABLE')
                exposure = evaluate_synthetic_playback(source, script, audio, mode=script.mode, style=script.style)
            except (KeyError, TypeError, ValueError) as exc:
                raise PolicyError('NARRATION_UNAVAILABLE') from exc
            session.narration_exposures.append({'stage': session.stage_index, 'asset_id': asset_id,
                                                'asset_version': asset_version, **exposure})
            session.revision += 1
            LessonEngine._event(session, actor, 'narration_playback_requested')
            db.execute('UPDATE sessions SET payload=?,revision=? WHERE id=? AND revision=?',
                       (json.dumps(asdict(session)), session.revision, session_id, row[1]))
            if db.execute('SELECT changes()').fetchone()[0] != 1:
                raise ConflictError('REVISION_CONFLICT')
            db.execute('INSERT INTO audit_events(session_id,event,revision,actor_id) VALUES (?,?,?,?)',
                       (session_id, 'narration_playback_requested', session.revision, actor.actor_id))
            return {'content_type': 'audio/wav', 'data': audio.data, 'transcript': audio.transcript,
                    'captions': audio.captions, 'exposure': exposure, 'revision': session.revision}
