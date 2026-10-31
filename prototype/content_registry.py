"""Synthetic-only versioned lesson review workflow; no public publishing authority."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from prototype.lesson_engine import PolicyError
from prototype.instructional_content import load_demo_lesson

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
        record=self.get(lid,version)
        if record['status']!='approved_for_prototype':
            raise PolicyError('CONTENT_NOT_APPROVED')
        return record['content']

    def audit(self,lid,version):
        with self._db() as db:
            return db.execute('SELECT action,actor,note FROM content_events WHERE lesson_id=? AND version=? ORDER BY id',
                              (lid,version)).fetchall()
