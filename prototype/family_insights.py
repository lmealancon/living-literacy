"""Fictional family preferences and activity summaries; not an assessment.

All profile and session access goes through the existing synthetic store's
relationship and purpose-specific consent checks. Interests are explicit
fictional choices, not inferred traits or educational recommendations.
This module is not suitable for real student data.
"""
import json

from prototype.lesson_engine import PolicyError, STAGES

INTEREST_OPTIONS = ('animals', 'art', 'music', 'nature', 'science', 'sports', 'stories', 'technology')
_SCHEMA = '''CREATE TABLE IF NOT EXISTS synthetic_profile_interests (
    student_id TEXT PRIMARY KEY REFERENCES students(id),
    interests_json TEXT NOT NULL
)'''


def _validate_interests(interests):
    if (not isinstance(interests, list) or len(interests) > len(INTEREST_OPTIONS)
            or any(not isinstance(item, str) or item not in INTEREST_OPTIONS for item in interests)
            or len(set(interests)) != len(interests)):
        raise PolicyError('INVALID_SYNTHETIC_INTERESTS')
    return list(interests)


class SyntheticFamilyInsights:
    """Minimal, synthetic-only preference and activity boundary."""

    def __init__(self, store):
        self.store = store
        with store._connect() as db:
            db.execute(_SCHEMA)

    def get_interests(self, token, student_id):
        with self.store._connect() as db:
            self.store._actor(db, token, student_id, 'profile')
            row = db.execute('SELECT interests_json FROM synthetic_profile_interests WHERE student_id=?', (student_id,)).fetchone()
            try:
                interests = _validate_interests(json.loads(row[0])) if row else []
            except (ValueError, TypeError) as exc:
                raise PolicyError('INVALID_SYNTHETIC_INTERESTS') from exc
            return {'interests': interests, 'options': list(INTEREST_OPTIONS)}

    def set_interests(self, token, student_id, interests):
        choices = _validate_interests(interests)
        with self.store._connect() as db:
            self.store._actor(db, token, student_id, 'profile')
            db.execute('''INSERT INTO synthetic_profile_interests (student_id, interests_json) VALUES (?,?)
                ON CONFLICT(student_id) DO UPDATE SET interests_json=excluded.interests_json''',
                (student_id, json.dumps(choices)))
        return {'interests': choices, 'options': list(INTEREST_OPTIONS)}

    def activity_summary(self, token, student_id):
        """Return observed activity counts, not learning outcomes or mastery."""
        with self.store._connect() as db:
            self.store._actor(db, token, student_id, 'lesson')
            rows = db.execute('SELECT payload FROM sessions WHERE student_id=? ORDER BY rowid DESC', (student_id,)).fetchall()
            sessions = [self.store._deserialize(row[0]) for row in rows]

        summary = {'sessions_total': len(sessions), 'sessions_completed': 0,
                   'sessions_active': 0, 'sessions_paused': 0, 'responses_total': 0,
                   'responses_assisted': 0, 'assistance_unrecorded': 0,
                   'recent_sessions': [],
                   'note': 'Activity only; no mastery or diagnosis is assessed.'}
        for session in sessions:
            if session.status == 'completed': summary['sessions_completed'] += 1
            if session.status == 'active': summary['sessions_active'] += 1
            if session.status == 'paused': summary['sessions_paused'] += 1
            assisted = 0
            for response in session.responses:
                summary['responses_total'] += 1
                assistance = response.get('assistance') if isinstance(response, dict) else None
                recorded = assistance.get('audio_or_modeling') if isinstance(assistance, dict) else None
                if recorded is True:
                    assisted += 1
                    summary['responses_assisted'] += 1
                elif recorded is not False:
                    summary['assistance_unrecorded'] += 1
            if len(summary['recent_sessions']) < 10:
                stage = STAGES[session.stage_index] if isinstance(session.stage_index, int) and 0 <= session.stage_index < len(STAGES) else None
                summary['recent_sessions'].append({'session_id': session.session_id,
                    'lesson_id': session.lesson_id, 'lesson_version': session.lesson_version,
                    'status': session.status, 'stage': stage,
                    'response_count': len(session.responses), 'assisted_count': assisted})
        return summary
