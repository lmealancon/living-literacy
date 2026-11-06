"""Synthetic-only versioned lesson review workflow; no public publishing authority."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from prototype.lesson_engine import PolicyError
from prototype.instructional_content import load_demo_lesson, validate_demo_lesson

SCHEMA = """
CREATE TABLE IF NOT EXISTS content_versions (
 lesson_id TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
 digest TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
 ('draft','in_review','approved_for_prototype','suspended','retired')),
 PRIMARY KEY(lesson_id,version));
CREATE TABLE IF NOT EXISTS content_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id TEXT NOT NULL, version TEXT NOT NULL,
 action TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL,
 FOREIGN KEY(lesson_id,version) REFERENCES content_versions(lesson_id,version));
"""

class SyntheticContentRegistry:
    def __init__(self, filename):
        self.filename=str(filename)
        with self._db() as db: db.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.filename, isolation_level=None)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally: db.close()

    def create_draft(self, content, actor):
        if not isinstance(actor,str) or not actor.startswith('synthetic-'):
            raise PolicyError('SYNTHETIC_ACTOR_REQUIRED')
        if isinstance(content,(str,Path)):
            content=json.loads(Path(content).read_text(encoding='utf-8'))
        # Reuse strict six-stage demo validator, without changing canonical loader.
        if content.get('publication_status') != 'prototype_only':
            raise PolicyError('PROTOTYPE_ONLY')
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'lesson.json'
            p.write_text(json.dumps(content),encoding='utf-8')
            load_demo_lesson(p)
        lid,version=content.get('lesson_id'),content.get('version')
        if not all(isinstance(v,str) and v.startswith(('synthetic-','demo-')) for v in (lid,version)):
            raise PolicyError('SYNTHETIC_CONTENT_IDENTIFIERS_REQUIRED')
        payload=json.dumps(content,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        digest=hashlib.sha256(payload.encode()).hexdigest()
        with self._db() as db:
            try:
                db.execute('INSERT INTO content_versions VALUES (?,?,?,?,?)',(lid,version,payload,digest,'draft'))
            except sqlite3.IntegrityError:
                raise PolicyError('VERSION_IMMUTABLE') from None
            self._event(db,lid,version,'created',actor,'draft created')
        return digest

    @staticmethod
    def _event(db,lid,version,action,actor,note):
        db.execute('INSERT INTO content_events(lesson_id,version,action,actor,note) VALUES (?,?,?,?,?)',
                   (lid,version,action,actor,note))

    def create_revision(self, lesson_id, parent_version, content, actor):
        """Create a separate synthetic draft and record the immutable source pin.

        This is a local fixture workflow, not authentication, real reviewer
        authority, or a student-facing publishing mechanism. The caller must
        use a new version and submit it for a separate simulated review.
        Withdrawn sources cannot be used to create a new draft.
        """
        if (not isinstance(actor, str) or not actor.startswith('synthetic-')
                or len(actor) <= len('synthetic-') or len(actor) > 100):
            raise PolicyError('SYNTHETIC_ACTOR_REQUIRED')
        if not isinstance(content, dict):
            raise PolicyError('INVALID_STAGE_CONTENT')
        validate_demo_lesson(content)
        new_version = content.get('version')
        if (content.get('lesson_id') != lesson_id or not isinstance(new_version, str)
                or not new_version.startswith(('synthetic-', 'demo-'))
                or new_version == parent_version):
            raise PolicyError('INVALID_REVISION')
        if not isinstance(content.get('title'), str) or not content['title'].strip():
            raise PolicyError('INVALID_STAGE_CONTENT')
        try:
            payload = json.dumps(content, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        except (ValueError, TypeError, UnicodeError) as exc:
            raise PolicyError('INVALID_STAGE_CONTENT') from exc
        with self._db() as db:
            row = db.execute('SELECT payload,digest,status FROM content_versions WHERE lesson_id=? AND version=?',
                             (lesson_id, parent_version)).fetchone()
            if not row:
                raise PolicyError('RESOURCE_NOT_FOUND')
            if row[2] in ('suspended', 'retired'):
                raise PolicyError('WITHDRAWN_SOURCE')
            if hashlib.sha256(row[0].encode('utf-8')).hexdigest() != row[1]:
                raise PolicyError('CONTENT_INTEGRITY_FAILURE')
            try:
                parent = validate_demo_lesson(json.loads(row[0]))
            except (ValueError, TypeError, AttributeError) as exc:
                raise PolicyError('CONTENT_INTEGRITY_FAILURE') from exc
            if parent.get('lesson_id') != lesson_id or parent.get('version') != parent_version:
                raise PolicyError('CONTENT_INTEGRITY_FAILURE')
            try:
                db.execute('INSERT INTO content_versions VALUES (?,?,?,?,?)',
                           (lesson_id, new_version, payload, digest, 'draft'))
            except sqlite3.IntegrityError:
                raise PolicyError('VERSION_IMMUTABLE') from None
            self._event(db, lesson_id, new_version, 'created', actor, 'revision draft created')
            lineage = json.dumps({'parent_version': parent_version, 'parent_digest': row[1]},
                                 sort_keys=True, separators=(',', ':'))
            self._event(db, lesson_id, new_version, 'derived_from', actor, lineage)
        return digest

    def revision_source(self, lesson_id, version):
        """Return a synthetic draft's source version and recorded digest."""
        with self._db() as db:
            rows = db.execute('SELECT note FROM content_events WHERE lesson_id=? AND version=? AND action=?',
                              (lesson_id, version, 'derived_from')).fetchall()
            if not rows:
                raise PolicyError('RESOURCE_NOT_FOUND')
            if len(rows) != 1:
                raise PolicyError('CONTENT_INTEGRITY_FAILURE')
            try:
                source = json.loads(rows[0][0])
                if (not isinstance(source, dict) or set(source) != {'parent_version', 'parent_digest'}
                        or not isinstance(source['parent_version'], str)
                        or not isinstance(source['parent_digest'], str)
                        or len(source['parent_digest']) != 64
                        or any(c not in '0123456789abcdef' for c in source['parent_digest'])):
                    raise ValueError('Invalid lineage')
            except (ValueError, TypeError) as exc:
                raise PolicyError('CONTENT_INTEGRITY_FAILURE') from exc
            return {'lesson_id': lesson_id, 'version': version,
                    'parent_version': source['parent_version'], 'parent_digest': source['parent_digest']}

    def transition(self,lid,version,action,actor,note):
        if not isinstance(actor,str) or not actor.startswith('synthetic-') or not isinstance(note,str) or not note.strip():
            raise PolicyError('REVIEW_AUDIT_REQUIRED')
        allowed={('draft','submit'): 'in_review',
                 ('in_review','approve_prototype'): 'approved_for_prototype',
                 ('approved_for_prototype','suspend'): 'suspended',
                 ('suspended','retire'): 'retired',
                 ('in_review','reject'): 'draft'}
        with self._db() as db:
            row=db.execute('SELECT status,payload,digest FROM content_versions WHERE lesson_id=? AND version=?',(lid,version)).fetchone()
            if not row: raise PolicyError('RESOURCE_NOT_FOUND')
            new=allowed.get((row[0],action))
            if not new: raise PolicyError('INVALID_CONTENT_TRANSITION')
            if action=='approve_prototype':
                # A reviewer must be independent of both the original author and
                # the person submitting the current revision for review. Synthetic
                # actor names do not establish real identity or reviewer authority.
                creator=db.execute('SELECT actor FROM content_events WHERE lesson_id=? AND version=? AND action=?',
                                   (lid,version,'created')).fetchone()
                submitter=db.execute('SELECT actor FROM content_events WHERE lesson_id=? AND version=? AND action=? ORDER BY id DESC LIMIT 1',
                                     (lid,version,'submit')).fetchone()
                if not creator or not submitter: raise PolicyError('REVIEW_AUDIT_REQUIRED')
                if actor in (creator[0],submitter[0]): raise PolicyError('SELF_APPROVAL_FORBIDDEN')
                if hashlib.sha256(row[1].encode()).hexdigest()!=row[2]:
                    raise PolicyError('CONTENT_INTEGRITY_FAILURE')
            db.execute('UPDATE content_versions SET status=? WHERE lesson_id=? AND version=?',(new,lid,version))
            self._event(db,lid,version,action,actor,note)
            return new

    def get(self,lid,version):
        with self._db() as db:
            row=db.execute('SELECT payload,digest,status FROM content_versions WHERE lesson_id=? AND version=?',
                           (lid,version)).fetchone()
            if not row: raise PolicyError('RESOURCE_NOT_FOUND')
            payload,digest,status=row
            if hashlib.sha256(payload.encode()).hexdigest()!=digest:
                raise PolicyError('CONTENT_INTEGRITY_FAILURE')
            return {'content':json.loads(payload),'digest':digest,'status':status}

    def for_synthetic_demo(self,lid,version):
        try:
            record=self.get(lid,version)
        except (ValueError,TypeError,AttributeError) as exc:
            raise PolicyError('CONTENT_INTEGRITY_FAILURE') from exc
        if record['status']!='approved_for_prototype':
            raise PolicyError('CONTENT_NOT_APPROVED')
        try:
            content=validate_demo_lesson(record['content'])
            if (content.get('lesson_id')!=lid or content.get('version')!=version
                    or not isinstance(content.get('title'),str) or not content['title'].strip()):
                raise PolicyError('CONTENT_INTEGRITY_FAILURE')
        except (ValueError,TypeError,AttributeError) as exc:
            raise PolicyError('CONTENT_INTEGRITY_FAILURE') from exc
        return content

    def list_for_synthetic_demo(self):
        """List valid, prototype-approved lessons from one database snapshot.

        Simulated approval is not independent human review or permission for
        use with students. A fresh content check is still required on delivery
        and on every session mutation, because a lesson may be withdrawn after
        this snapshot is returned.
        """
        lessons=[]
        with self._db() as db:
            rows=db.execute('''SELECT lesson_id,version,payload,digest FROM content_versions
                               WHERE status=? ORDER BY lesson_id,version''',
                            ('approved_for_prototype',)).fetchall()
            for lesson_id,version,payload,digest in rows:
                try:
                    if hashlib.sha256(payload.encode()).hexdigest()!=digest:
                        continue
                    content=validate_demo_lesson(json.loads(payload))
                    if (content.get('lesson_id')!=lesson_id or content.get('version')!=version
                            or not isinstance(content.get('title'),str) or not content['title'].strip()):
                        continue
                except (PolicyError,ValueError,TypeError,AttributeError):
                    continue
                lessons.append(content)
        return lessons

    def audit(self,lid,version):
        with self._db() as db:
            return db.execute('SELECT action,actor,note FROM content_events WHERE lesson_id=? AND version=? ORDER BY id',
                              (lid,version)).fetchall()
