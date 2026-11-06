"""Fictional-only assessment framework, not a diagnostic or production service.

Fixture methods are for local engineering setup and must not be exposed as public
content or consent administration APIs. Reviewer identity is not verified.
"""
import hashlib
import json
import uuid

from prototype.lesson_engine import PolicyError


SCHEMA = """
CREATE TABLE IF NOT EXISTS synthetic_assessment_forms (
  form_id TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
  digest TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('approved_for_prototype','suspended')),
  author TEXT NOT NULL, reviewer TEXT NOT NULL, PRIMARY KEY(form_id, version));
CREATE TABLE IF NOT EXISTS synthetic_assessment_consent (
  identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id),
  status TEXT NOT NULL CHECK(status IN ('active','withdrawn')), expires_at TEXT,
  PRIMARY KEY(identity_id, student_id));
CREATE TABLE IF NOT EXISTS synthetic_assessment_runs (
  id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id), form_id TEXT NOT NULL,
  version TEXT NOT NULL, digest TEXT NOT NULL,
  FOREIGN KEY(form_id,version) REFERENCES synthetic_assessment_forms(form_id,version));
CREATE TABLE IF NOT EXISTS synthetic_assessment_responses (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES synthetic_assessment_runs(id),
  item_id TEXT NOT NULL, response TEXT NOT NULL, assisted INTEGER NOT NULL,
  narration INTEGER NOT NULL, actor_id TEXT NOT NULL REFERENCES identities(id));
"""


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _fixture_id(value):
    return isinstance(value, str) and value.startswith('synthetic-') and 10 < len(value) <= 100


def validate_synthetic_form(form):
    """Validate fixture shape for both listing and delivery, not educational quality."""
    if (not isinstance(form, dict) or set(form) != {'language', 'items'}
            or form.get('language') not in ('en', 'es')
            or not isinstance(form.get('items'), list) or not form['items']):
        raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE')
    ids = []
    for item in form['items']:
        if (not isinstance(item, dict) or set(item) != {'id', 'prompt'}
                or not _fixture_id(item.get('id')) or not isinstance(item.get('prompt'), str)
                or not item['prompt'].strip() or len(item['prompt']) > 1000):
            raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE')
        try:
            item['id'].encode('utf-8')
            item['prompt'].encode('utf-8')
        except UnicodeError as exc:
            raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE') from exc
        ids.append(item['id'])
    if len(ids) != len(set(ids)):
        raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE')
    return form


class SyntheticAssessmentStore:
    def __init__(self, store):
        self.store = store
        with store._connect() as db:
            # executescript implicitly commits a pending transaction; execute
            # these fixed DDL statements individually so partial setup rolls back.
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement)

    def add_reviewed_fixture(self, form_id, version, language, items, author, reviewer):
        """Trusted local fixture setup; does not constitute actual content review."""
        if (not _fixture_id(form_id) or not _fixture_id(author) or not _fixture_id(reviewer)
                or author == reviewer or not isinstance(version, str) or not version
                or language not in ('en', 'es') or not isinstance(items, list) or not items):
            raise PolicyError('INVALID_SYNTHETIC_ASSESSMENT_FIXTURE')
        if any(not isinstance(i, dict) or set(i) != {'id', 'prompt'} or
               not _fixture_id(i['id']) or not isinstance(i['prompt'], str) or
               not i['prompt'].strip() or len(i['prompt']) > 1000 for i in items):
            raise PolicyError('INVALID_SYNTHETIC_ASSESSMENT_FIXTURE')
        if len({i['id'] for i in items}) != len(items):
            raise PolicyError('INVALID_SYNTHETIC_ASSESSMENT_FIXTURE')
        validate_synthetic_form({'language': language, 'items': items})
        payload = json.dumps({'language': language, 'items': items}, sort_keys=True, ensure_ascii=False)
        with self.store._connect() as db:
            if db.execute('SELECT 1 FROM synthetic_assessment_forms WHERE form_id=? AND version=?', (form_id, version)).fetchone():
                raise PolicyError('IMMUTABLE_ASSESSMENT_VERSION')
            db.execute('INSERT INTO synthetic_assessment_forms VALUES (?,?,?,?,?,?,?)',
                       (form_id, version, payload, _hash(payload), 'approved_for_prototype', author, reviewer))

    def set_synthetic_consent(self, token, student_id, active):
        """Set simulated consent only, not proof of guardian authority or legal consent."""
        if type(active) is not bool:
            raise PolicyError('INVALID_CONSENT')
        with self.store._connect() as db:
            actor = self.store._actor(db, token, student_id, 'profile')
            db.execute('''INSERT INTO synthetic_assessment_consent VALUES (?,?,?,NULL)
                ON CONFLICT(identity_id,student_id) DO UPDATE SET status=excluded.status,expires_at=NULL''',
                       (actor.actor_id, student_id, 'active' if active else 'withdrawn'))

    def _actor(self, db, token, student_id):
        actor = self.store._actor(db, token, student_id, 'profile')
        row = db.execute('''SELECT 1 FROM synthetic_assessment_consent WHERE identity_id=? AND student_id=?
            AND status='active' AND (expires_at IS NULL OR
            (julianday(expires_at) IS NOT NULL AND julianday(expires_at)>julianday('now')))''',
                         (actor.actor_id, student_id)).fetchone()
        if not row:
            raise PolicyError('RESOURCE_NOT_FOUND')
        return actor

    @staticmethod
    def _form(db, form_id, version, pinned=None):
        row = db.execute('SELECT payload,digest,status FROM synthetic_assessment_forms WHERE form_id=? AND version=?',
                         (form_id, version)).fetchone()
        if not row or row[2] != 'approved_for_prototype':
            raise PolicyError('ASSESSMENT_UNAVAILABLE')
        if _hash(row[0]) != row[1] or (pinned is not None and row[1] != pinned):
            raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE')
        try:
            return validate_synthetic_form(json.loads(row[0])), row[1]
        except (ValueError, TypeError) as exc:
            raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE') from exc

    def start(self, token, student_id, form_id, version):
        with self.store._connect() as db:
            actor = self._actor(db, token, student_id)
            form, digest = self._form(db, form_id, version)
            run_id = str(uuid.uuid4())
            db.execute('INSERT INTO synthetic_assessment_runs VALUES (?,?,?,?,?,?)',
                       (run_id, student_id, actor.workspace_id, form_id, version, digest))
            return {'id': run_id, 'form_id': form_id, 'version': version,
                    'validation_status': 'unvalidated', 'language': form['language'], 'items': form['items']}

    def record_response(self, token, run_id, item_id, response, assisted, narration):
        if (not isinstance(response, str) or not response.strip() or len(response) > 1000
                or type(assisted) is not bool or type(narration) is not bool):
            raise PolicyError('INVALID_RESPONSE')
        try:
            response.encode('utf-8')
            if not isinstance(item_id, str):
                raise ValueError('Invalid item ID')
            item_id.encode('utf-8')
        except (UnicodeError, ValueError) as exc:
            raise PolicyError('INVALID_RESPONSE') from exc
        # Listening support is assistance, even if a caller incorrectly marks
        # the response unassisted. This does not confer evidence or mastery.
        assisted = assisted or narration
        with self.store._connect() as db:
            row = db.execute('SELECT student_id,form_id,version,digest FROM synthetic_assessment_runs WHERE id=?',
                             (run_id,)).fetchone()
            if not row:
                raise PolicyError('RESOURCE_NOT_FOUND')
            actor = self._actor(db, token, row[0])
            # Workflow-managed runs must not bypass version, state, audit and
            # idempotency checks via the legacy response method. Older runs
            # without workflow state retain their original behavior.
            has_workflow = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='synthetic_assessment_workflow'").fetchone()
            if has_workflow and db.execute('SELECT 1 FROM synthetic_assessment_workflow WHERE run_id=?', (run_id,)).fetchone():
                raise PolicyError('ASSESSMENT_WORKFLOW_REQUIRED')
            form, _ = self._form(db, row[1], row[2], row[3])
            if item_id not in {item['id'] for item in form['items']}:
                raise PolicyError('INVALID_ASSESSMENT_ITEM')
            response_id = str(uuid.uuid4())
            db.execute('INSERT INTO synthetic_assessment_responses VALUES (?,?,?,?,?,?,?)',
                       (response_id, run_id, item_id, response, int(assisted), int(narration), actor.actor_id))
            return {'id': response_id, 'assisted': assisted, 'narration': narration,
                    'evidence_status': 'needs_review', 'validation_status': 'unvalidated'}

    def results(self, token, run_id):
        with self.store._connect() as db:
            row = db.execute('SELECT student_id,form_id,version FROM synthetic_assessment_runs WHERE id=?',
                             (run_id,)).fetchone()
            if not row:
                raise PolicyError('RESOURCE_NOT_FOUND')
            self._actor(db, token, row[0])
            responses = db.execute('SELECT item_id,response,assisted,narration FROM synthetic_assessment_responses WHERE run_id=? ORDER BY rowid',
                                   (run_id,)).fetchall()
            return {'form_id': row[1], 'version': row[2], 'validation_status': 'unvalidated',
                    'explanation': 'Responses require review. This is not a diagnostic or mastery score.',
                    'responses': [{'item_id': r[0], 'response': r[1], 'assisted': bool(r[2]),
                                   'narration': bool(r[3]), 'evidence_status': 'needs_review'} for r in responses]}
