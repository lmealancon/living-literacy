"""Transactional assessment activity for synthetic fixtures only.

This module does not administer an approved student assessment, validate an
instrument, score answers, infer mastery, or establish guardian consent.
Fixture setup remains a trusted local operation and is not an end-user API.
"""
import hashlib
import json
import re
import uuid

from prototype.lesson_engine import ConflictError, PolicyError
from prototype.synthetic_assessment import SyntheticAssessmentStore, validate_synthetic_form

_KEY = re.compile(r'^[A-Za-z0-9_-]{16,100}$')
_SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS synthetic_assessment_workflow (
        run_id TEXT PRIMARY KEY REFERENCES synthetic_assessment_runs(id),
        status TEXT NOT NULL CHECK(status IN ('active','completed')),
        revision INTEGER NOT NULL CHECK(revision >= 0))''',
    '''CREATE TABLE IF NOT EXISTS synthetic_assessment_start_keys (
        identity_id TEXT NOT NULL REFERENCES identities(id),
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        key TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES synthetic_assessment_runs(id),
        PRIMARY KEY(identity_id,workspace_id,key))''',
    '''CREATE TABLE IF NOT EXISTS synthetic_assessment_commands (
        run_id TEXT NOT NULL REFERENCES synthetic_assessment_runs(id),
        identity_id TEXT NOT NULL REFERENCES identities(id), key TEXT NOT NULL,
        digest TEXT NOT NULL, result_json TEXT NOT NULL,
        PRIMARY KEY(run_id,identity_id,key))''',
    '''CREATE TABLE IF NOT EXISTS synthetic_assessment_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES synthetic_assessment_runs(id),
        identity_id TEXT NOT NULL REFERENCES identities(id),
        action TEXT NOT NULL CHECK(action IN ('started','response_recorded','completed')),
        revision INTEGER NOT NULL)''',
)


def _key(value):
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise PolicyError('IDEMPOTENCY_KEY_REQUIRED')
    return value


def _revision(value):
    if type(value) is not int or value < 0:
        raise PolicyError('INVALID_REVISION')
    return value


def _fingerprint(value):
    try:
        payload = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PolicyError('INVALID_ASSESSMENT_INPUT') from exc


def _valid_text(value):
    if not isinstance(value, str) or not value:
        raise PolicyError('INVALID_ASSESSMENT_INPUT')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise PolicyError('INVALID_ASSESSMENT_INPUT') from exc
    return value


class SyntheticAssessmentWorkflow:
    """Explicitly scoped, non-scoring activity orchestration for fictional forms."""

    def __init__(self, store):
        self.store = store
        self.assessments = SyntheticAssessmentStore(store)
        with self.store._connect() as db:
            for statement in _SCHEMA:
                db.execute(statement)

    @staticmethod
    def _validate_form(form):
        return validate_synthetic_form(form)

    def _authorized_run(self, db, token, run_id, require_form):
        row = db.execute('''SELECT r.student_id,r.workspace_id,r.form_id,r.version,r.digest,w.status,w.revision
            FROM synthetic_assessment_runs r JOIN synthetic_assessment_workflow w ON w.run_id=r.id
            WHERE r.id=?''', (run_id,)).fetchone()
        if not row:
            raise PolicyError('RESOURCE_NOT_FOUND')
        actor = self.assessments._actor(db, token, row[0])
        if actor.workspace_id != row[1]:
            raise PolicyError('RESOURCE_NOT_FOUND')
        form = None
        if require_form:
            form, _ = self.assessments._form(db, row[2], row[3], row[4])
            form = self._validate_form(form)
        return actor, row, form

    def start(self, token, student_id, form_id, version, key):
        """Start once per adult/workspace/key; no questions are created by this method."""
        _key(key)
        for value in (student_id, form_id, version):
            _valid_text(value)
        with self.store._connect() as db:
            actor = self.assessments._actor(db, token, student_id)
            form, digest = self.assessments._form(db, form_id, version)
            self._validate_form(form)
            prior = db.execute('''SELECT r.id,r.student_id,r.form_id,r.version,w.status,w.revision,r.digest
                FROM synthetic_assessment_start_keys k JOIN synthetic_assessment_runs r ON r.id=k.run_id
                JOIN synthetic_assessment_workflow w ON w.run_id=r.id
                WHERE k.identity_id=? AND k.workspace_id=? AND k.key=?''',
                (actor.actor_id,actor.workspace_id,key)).fetchone()
            if prior:
                if (prior[1],prior[2],prior[3]) != (student_id,form_id,version):
                    raise ConflictError('IDEMPOTENCY_KEY_REUSED')
                if prior[6] != digest:
                    raise PolicyError('ASSESSMENT_INTEGRITY_FAILURE')
                return {'id': prior[0], 'status': prior[4], 'revision': prior[5], 'validation_status': 'unvalidated'}
            run_id = str(uuid.uuid4())
            db.execute('INSERT INTO synthetic_assessment_runs VALUES (?,?,?,?,?,?)',
                       (run_id,student_id,actor.workspace_id,form_id,version,digest))
            db.execute("INSERT INTO synthetic_assessment_workflow VALUES (?,'active',0)", (run_id,))
            db.execute('INSERT INTO synthetic_assessment_start_keys VALUES (?,?,?,?)',
                       (actor.actor_id,actor.workspace_id,key,run_id))
            db.execute("INSERT INTO synthetic_assessment_events(run_id,identity_id,action,revision) VALUES (?,?,'started',0)",
                       (run_id,actor.actor_id))
            return {'id':run_id,'status':'active','revision':0,'validation_status':'unvalidated'}

    def _command(self, token, run_id, expected_revision, key, action, params):
        _valid_text(run_id); _key(key); _revision(expected_revision)
        digest = _fingerprint({'action': action, 'revision': expected_revision, 'params': params})
        with self.store._connect() as db:
            actor, row, form = self._authorized_run(db, token, run_id, require_form=True)
            previous = db.execute('SELECT digest,result_json FROM synthetic_assessment_commands WHERE run_id=? AND identity_id=? AND key=?',
                                  (run_id,actor.actor_id,key)).fetchone()
            if previous:
                if previous[0] != digest:
                    raise ConflictError('IDEMPOTENCY_KEY_REUSED')
                return json.loads(previous[1])
            if row[6] != expected_revision:
                raise ConflictError('REVISION_CONFLICT')
            if row[5] != 'active':
                raise PolicyError('ASSESSMENT_NOT_ACTIVE')
            revision = row[6] + 1
            if action == 'response_recorded':
                if params['item_id'] not in {x['id'] for x in form['items']}:
                    raise PolicyError('INVALID_ASSESSMENT_ITEM')
                response_id = str(uuid.uuid4())
                # Any narration counts as assistance even if the caller labels
                # the response unassisted. No proficiency is inferred.
                assisted = params['assisted'] or params['narration']
                db.execute('INSERT INTO synthetic_assessment_responses VALUES (?,?,?,?,?,?,?)',
                    (response_id,run_id,params['item_id'],params['response'],int(assisted),int(params['narration']),actor.actor_id))
                result = {'id':response_id,'revision':revision,'assisted':assisted,
                          'narration':params['narration'],'evidence_status':'needs_review',
                          'validation_status':'unvalidated'}
            elif action == 'completed':
                result = {'id':run_id,'status':'completed','revision':revision,
                          'validation_status':'unvalidated','mastery_status':'not_assessed'}
            else:
                raise PolicyError('INVALID_ASSESSMENT_ACTION')
            status = 'completed' if action == 'completed' else 'active'
            db.execute('UPDATE synthetic_assessment_workflow SET status=?,revision=? WHERE run_id=? AND revision=?',
                       (status,revision,run_id,row[6]))
            if db.execute('SELECT changes()').fetchone()[0] != 1:
                raise ConflictError('REVISION_CONFLICT')
            db.execute('INSERT INTO synthetic_assessment_events(run_id,identity_id,action,revision) VALUES (?,?,?,?)',
                       (run_id,actor.actor_id,action,revision))
            db.execute('INSERT INTO synthetic_assessment_commands VALUES (?,?,?,?,?)',
                       (run_id,actor.actor_id,key,digest,json.dumps(result,sort_keys=True)))
            return result

    def record_response(self, token, run_id, item_id, response, assisted, narration, expected_revision, key):
        if (not isinstance(item_id, str) or not isinstance(response, str) or not response.strip()
                or len(response) > 1000 or type(assisted) is not bool or type(narration) is not bool):
            raise PolicyError('INVALID_RESPONSE')
        _valid_text(item_id); _valid_text(response)
        return self._command(token, run_id, expected_revision, key, 'response_recorded',
                             {'item_id':item_id,'response':response,'assisted':assisted,'narration':narration})

    def complete(self, token, run_id, expected_revision, key):
        """Complete an activity; this is not a score, mastery or reading level."""
        return self._command(token, run_id, expected_revision, key, 'completed', {})

    def get_run(self, token, run_id):
        """Resume an authorized intact fixture with its actual workflow revision."""
        _valid_text(run_id)
        with self.store._connect() as db:
            _actor, row, form = self._authorized_run(db, token, run_id, require_form=True)
            return {'id':run_id,'form_id':row[2],'version':row[3],
                    'status':row[5],'revision':row[6],'language':form['language'],
                    'items':form['items'],'validation_status':'unvalidated',
                    'mastery_status':'not_assessed'}

    def history(self, token, student_id):
        """Read activity metadata even after form withdrawal, subject to consent."""
        _valid_text(student_id)
        with self.store._connect() as db:
            actor = self.assessments._actor(db, token, student_id)
            rows = db.execute('''SELECT r.id,r.form_id,r.version,w.status,w.revision,COUNT(a.id)
                FROM synthetic_assessment_runs r JOIN synthetic_assessment_workflow w ON w.run_id=r.id
                LEFT JOIN synthetic_assessment_responses a ON a.run_id=r.id
                WHERE r.student_id=? AND r.workspace_id=?
                GROUP BY r.id,r.form_id,r.version,w.status,w.revision ORDER BY r.rowid DESC''',
                (student_id,actor.workspace_id)).fetchall()
            return {'runs':[{'id':r[0],'form_id':r[1],'version':r[2],'status':r[3],
                             'revision':r[4],'responses_recorded':r[5],
                             'validation_status':'unvalidated','mastery_status':'not_assessed'} for r in rows]}
