"""SQLite synthetic-only persistence boundary. Educational prototype, NOT production authentication."""
import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from prototype.content_registry import SyntheticContentRegistry
from prototype.lesson_engine import Actor, ApprovedLesson, LessonEngine, Session, PolicyError, ConflictError

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='synthetic_family'));
CREATE TABLE IF NOT EXISTS identities(id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS memberships(identity_id TEXT NOT NULL REFERENCES identities(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id), PRIMARY KEY(identity_id,workspace_id));
CREATE TABLE IF NOT EXISTS students(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), synthetic INTEGER NOT NULL CHECK(synthetic=1));
CREATE TABLE IF NOT EXISTS grants(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), PRIMARY KEY(identity_id,student_id));
CREATE TABLE IF NOT EXISTS guardian_relationships(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), status TEXT NOT NULL CHECK(status IN ('active','revoked')), PRIMARY KEY(identity_id,student_id));
CREATE TABLE IF NOT EXISTS synthetic_consents(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), purpose TEXT NOT NULL CHECK(purpose IN ('lesson','profile')), status TEXT NOT NULL CHECK(status IN ('active','withdrawn')), expires_at TEXT, PRIMARY KEY(identity_id,student_id,purpose));
CREATE TABLE IF NOT EXISTS lessons(id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(id,version));
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), student_id TEXT NOT NULL REFERENCES students(id), payload TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency(workspace_id TEXT NOT NULL, identity_id TEXT NOT NULL, key TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(id), PRIMARY KEY(workspace_id,identity_id,key));
CREATE TABLE IF NOT EXISTS session_content_pins(session_id TEXT PRIMARY KEY REFERENCES sessions(id), digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id), event TEXT NOT NULL, revision INTEGER NOT NULL, actor_id TEXT NOT NULL);
"""

class SyntheticSQLiteStore:
    def __init__(self, filename):
        self.filename = str(filename)
        with self._connect() as db: db.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.filename,timeout=5,isolation_level=None)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally: db.close()

    def provision_synthetic_family(self, workspace_id, adult_id, student_id):
        if not workspace_id.startswith('synthetic-') or not student_id.startswith('synthetic-'):
            raise PolicyError('REAL_STUDENT_DATA_NOT_SUPPORTED')
        token=secrets.token_urlsafe(32)
        with self._connect() as db:
            db.execute('INSERT INTO workspaces VALUES (?,?)',(workspace_id,'synthetic_family'))
            db.execute('INSERT INTO identities VALUES (?,?)',(adult_id,hashlib.sha256(token.encode()).hexdigest()))
            db.execute('INSERT INTO memberships VALUES (?,?)',(adult_id,workspace_id))
            db.execute('INSERT INTO students VALUES (?,?,1)',(student_id,workspace_id))
            db.execute('INSERT INTO grants VALUES (?,?)',(adult_id,student_id))
            self._create_synthetic_authority(db, adult_id, student_id)
        return token

    @staticmethod
    def _create_synthetic_authority(db, adult_id, student_id):
        # These are simulated fixtures, not proof of parental authority or legal consent.
        db.execute('INSERT INTO guardian_relationships VALUES (?,?,?)', (adult_id, student_id, 'active'))
        db.executemany('INSERT INTO synthetic_consents VALUES (?,?,?,?,NULL)',
                       [(adult_id, student_id, purpose, 'active') for purpose in ('lesson', 'profile')])

    def create_synthetic_profile(self, token, existing_student_id, new_student_id):
        """Add a fictional identifier to an already authorized family; no names or real data."""
        if not isinstance(new_student_id, str) or not new_student_id.startswith('synthetic-'):
            raise PolicyError('REAL_STUDENT_DATA_NOT_SUPPORTED')
        with self._connect() as db:
            actor = self._actor(db, token, existing_student_id, 'profile')
            db.execute('INSERT INTO students VALUES (?,?,1)', (new_student_id, actor.workspace_id))
            db.execute('INSERT INTO grants VALUES (?,?)', (actor.actor_id, new_student_id))
            self._create_synthetic_authority(db, actor.actor_id, new_student_id)
        return {'id': new_student_id, 'workspace_id': actor.workspace_id, 'synthetic': True}

    def get_synthetic_profile(self, token, student_id):
        with self._connect() as db:
            actor = self._actor(db, token, student_id, 'profile')
            return {'id': student_id, 'workspace_id': actor.workspace_id, 'synthetic': True}

    def withdraw_synthetic_consent(self, token, student_id, purpose):
        if purpose not in ('lesson', 'profile'): raise PolicyError('RESOURCE_NOT_FOUND')
        with self._connect() as db:
            actor = self._actor(db, token, student_id, 'profile')
            db.execute("UPDATE synthetic_consents SET status='withdrawn' WHERE identity_id=? AND student_id=? AND purpose=?", (actor.actor_id, student_id, purpose))

    def revoke_synthetic_guardian(self, token, student_id):
        with self._connect() as db:
            actor = self._actor(db, token, student_id, 'profile')
            db.execute("UPDATE guardian_relationships SET status='revoked' WHERE identity_id=? AND student_id=?", (actor.actor_id, student_id))

    def add_approved_prototype_lesson(self, lesson_id, version):
        raise PolicyError('LEGACY_APPROVAL_BYPASS_DISABLED')

    def content_registry(self):
        return SyntheticContentRegistry(self.filename)

    def content_for_demo(self, lesson_id, version):
        return self.content_registry().for_synthetic_demo(lesson_id, version)

    def pinned_digest(self, token, session_id):
        with self._connect() as db:
            row=db.execute('SELECT student_id FROM sessions WHERE id=?',(session_id,)).fetchone()
            if not row: raise PolicyError('RESOURCE_NOT_FOUND')
            self._actor(db,token,row[0])
            pin=db.execute('SELECT digest FROM session_content_pins WHERE session_id=?',(session_id,)).fetchone()
            return pin[0] if pin else None

    def _actor(self, db, token, student_id, purpose='lesson'):
        from prototype.synthetic_auth import resolve
        identity_id=resolve(db, token)
        row=db.execute("""SELECT i.id, s.workspace_id FROM identities i
          JOIN grants g ON g.identity_id=i.id JOIN students s ON s.id=g.student_id
          JOIN memberships m ON m.identity_id=i.id AND m.workspace_id=s.workspace_id
          JOIN guardian_relationships r ON r.identity_id=i.id AND r.student_id=s.id AND r.status='active'
          JOIN synthetic_consents c ON c.identity_id=i.id AND c.student_id=s.id
          WHERE i.id=? AND s.id=? AND s.synthetic=1 AND c.purpose=? AND c.status='active'
            AND (c.expires_at IS NULL OR (julianday(c.expires_at) IS NOT NULL AND julianday(c.expires_at)>julianday('now')))""",(identity_id,student_id,purpose)).fetchone()
        if not row: raise PolicyError('RESOURCE_NOT_FOUND')
        return Actor(row[0],row[1],frozenset({student_id}))

    @staticmethod
    def _deserialize(payload):
        data=json.loads(payload)
        return Session(**data)

    @staticmethod
    def _require_active_pinned_content(db, session):
        """Fail closed on withdrawn, missing, or modified content for any session write."""
        row = db.execute("""SELECT cv.status, cv.payload, cv.digest, scp.digest
            FROM session_content_pins scp
            JOIN content_versions cv ON cv.lesson_id=? AND cv.version=?
            WHERE scp.session_id=?""", (session.lesson_id, session.lesson_version, session.session_id)).fetchone()
        if not row:
            raise PolicyError('CONTENT_NOT_APPROVED')
        status, payload, current_digest, pinned_digest = row
        if status != 'approved_for_prototype':
            raise PolicyError('CONTENT_NOT_APPROVED')
        if current_digest != pinned_digest or hashlib.sha256(payload.encode()).hexdigest() != pinned_digest:
            raise PolicyError('CONTENT_INTEGRITY_FAILURE')

    def _run(self, db, token, session_id, action, *args, **kwargs):
        row=db.execute('SELECT payload,revision,student_id FROM sessions WHERE id=?',(session_id,)).fetchone()
        if not row: raise PolicyError('RESOURCE_NOT_FOUND')
        actor=self._actor(db,token,row[2])
        session=self._deserialize(row[0])
        self._require_active_pinned_content(db, session)
        engine=LessonEngine(); engine.sessions[session_id]=session
        prior=len(session.audit)
        result=getattr(engine,action)(actor,session_id,*args,**kwargs)
        db.execute('UPDATE sessions SET payload=?,revision=? WHERE id=? AND revision=?',
                   (json.dumps(asdict(session)),session.revision,session_id,row[1]))
        if db.execute('SELECT changes()').fetchone()[0]!=1: raise ConflictError('REVISION_CONFLICT')
        for event in session.audit[prior:]:
            db.execute('INSERT INTO audit_events(session_id,event,revision,actor_id) VALUES (?,?,?,?)',
                       (session_id,event['action'],event['revision'],event['actor_id']))
        return result if action=='record_response' else session

    def start(self, token, student_id, lesson_id, version, key):
        if not key: raise PolicyError('IDEMPOTENCY_KEY_REQUIRED')
        with self._connect() as db:
            actor=self._actor(db,token,student_id)
            existing=db.execute('SELECT session_id FROM idempotency WHERE workspace_id=? AND identity_id=? AND key=?',
                                (actor.workspace_id,actor.actor_id,key)).fetchone()
            if existing:
                session=self._deserialize(db.execute('SELECT payload FROM sessions WHERE id=?',(existing[0],)).fetchone()[0])
                if (session.student_id,session.lesson_id,session.lesson_version)!=(student_id,lesson_id,version):
                    raise ConflictError('IDEMPOTENCY_KEY_REUSED')
                return session
            lesson=db.execute('SELECT payload,digest,status FROM content_versions WHERE lesson_id=? AND version=?',(lesson_id,version)).fetchone()
            if not lesson or lesson[2]!='approved_for_prototype': raise PolicyError('CONTENT_NOT_APPROVED')
            if hashlib.sha256(lesson[0].encode()).hexdigest()!=lesson[1]: raise PolicyError('CONTENT_INTEGRITY_FAILURE')
            engine=LessonEngine()
            session=engine.start(actor,student_id,ApprovedLesson(lesson_id,version,lesson[2]),key)
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(session.session_id,session.workspace_id,student_id,json.dumps(asdict(session)),session.revision))
            db.execute('INSERT INTO session_content_pins VALUES (?,?)',(session.session_id,lesson[1]))
            db.execute('INSERT INTO idempotency VALUES (?,?,?,?)',(actor.workspace_id,actor.actor_id,key,session.session_id))
            db.execute('INSERT INTO audit_events(session_id,event,revision,actor_id) VALUES (?,?,?,?)',
                       (session.session_id,'created',0,actor.actor_id))
            return session

    def transition(self,token,session_id,target,expected_revision):
        with self._connect() as db: return self._run(db,token,session_id,'transition',target,expected_revision)

    def advance_stage(self,token,session_id,expected_revision):
        with self._connect() as db: return self._run(db,token,session_id,'advance_stage',expected_revision)

    def record_response(self,token,session_id,expected_revision,response_text,assistance,independent_task=False):
        with self._connect() as db:
            return self._run(db,token,session_id,'record_response',expected_revision,response_text,assistance,independent_task)

    def get_session(self,token,session_id):
        with self._connect() as db:
            row=db.execute('SELECT payload,student_id FROM sessions WHERE id=?',(session_id,)).fetchone()
            if not row: raise PolicyError('RESOURCE_NOT_FOUND')
            self._actor(db,token,row[1]); return self._deserialize(row[0])

    def audit_count(self,token,session_id):
        with self._connect() as db:
            row=db.execute('SELECT student_id FROM sessions WHERE id=?',(session_id,)).fetchone()
            if not row: raise PolicyError('RESOURCE_NOT_FOUND')
            self._actor(db,token,row[0])
            return db.execute('SELECT COUNT(*) FROM audit_events WHERE session_id=?',(session_id,)).fetchone()[0]
