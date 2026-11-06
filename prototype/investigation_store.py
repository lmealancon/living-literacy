"""Versioned, fictional-only investigation state. Not an assessment service.

All operations authorize the simulated identity, relationship and lesson
consent in the same transaction as any read or write. The case records only
fixed fixture identifiers and hint flags; it does not store question text or
free-form learner responses. Existing sample lesson records remain separate.

The fixed v1 table is created transactionally for synthetic demo compatibility;
explicit migration 2 can also create it or adopt an identical existing table.
Convert a recognized legacy-v1 database using the documented migration before
initializing this service. The hard-coded case clues are unreviewed fixtures,
not content-registry records, and do not have independent withdrawal support.
"""
import json
import re

from prototype.lesson_engine import ConflictError, PolicyError
from prototype.migrations import _LEDGER, _normalized
from prototype.investigation_schema import CASE_PROGRESS_CREATE_SQL as _CREATE, CASE_PROGRESS_TABLE as _TABLE

CASE_ID = 'synthetic-vanishing-storybook-v1'
LESSON_ID = 'synthetic-lesson-word-study'
LESSON_VERSION = 'demo-1'
_DEFAULT = {'step':'post_office', 'revision':0, 'decode_hint':-1,
            'context_hint':-1, 'sequence_hint':-1, 'pending_hint':0, 'session_id':None}
_COLUMNS = ('step','revision','decode_hint','context_hint','sequence_hint','pending_hint','session_id')
_STUDENT = re.compile(r'synthetic-[A-Za-z0-9_-]{1,80}\Z')
_ORDER = {'post_office':0,'decode':0,'archive':1,'context':1,'lesson':2,
          'lesson_active':2,'bookshop':2,'sequence':2,'solved':3}
_CHOICES = {'decode':'a','context':'b','sequence':'c'}
_CLUES = (
    ('decode_hint','clue-decode','The folded map','The folded map shows a blue lantern outside the archive.'),
    ('context_hint','clue-context','The lantern note','Beside the blue lantern, a note says: Take the key to the bookshop.'),
    ('sequence_hint','clue-sequence','The missing storybook','Inside the box is the missing storybook.'),
)
_MESSAGES = {
    'post_office':'A storybook is missing! Visit the Post Office to investigate the first clue.',
    'decode':'A folded note arrived at the Post Office. Read it to find the first clue.',
    'archive':'Clue found! Follow the map to the blue lantern at the archive.',
    'context':'A note waits beside the blue lantern at the archive.',
    'lesson':'Complete the fictional map activity before continuing to the bookshop.',
    'lesson_active':'Complete the fictional map activity, then return to the investigation.',
    'bookshop':'Follow the note to the bookshop and investigate the locked box.',
    'sequence':'At the bookshop, use the clues to work out what happens next.',
    'solved':'The storybook is found! Case complete. This fictional game does not establish mastery.',
}


class SyntheticInvestigationStore:
    """Fictional case fixture using the existing synthetic SQLite authority."""

    def __init__(self, store):
        self.store = store
        with store._connect() as db:
            row = db.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (_TABLE,)).fetchone()
            if row is None:
                ledger = db.execute("SELECT type,sql FROM sqlite_master WHERE name='ll_schema_migrations'").fetchone()
                if ledger:
                    if ledger[0] != 'table' or _normalized(ledger[1]) != _normalized(_LEDGER):
                        raise PolicyError('CASE_SCHEMA_UNAVAILABLE')
                    if db.execute('SELECT 1 FROM ll_schema_migrations WHERE version >= 2 LIMIT 1').fetchone():
                        # Once migration 2 is recorded, a missing table is damage;
                        # do not hide it by silently recreating an empty table.
                        raise PolicyError('CASE_SCHEMA_UNAVAILABLE')
                db.execute(_CREATE)
            elif row[0] != 'table' or _normalized(row[1]) != _normalized(_CREATE):
                raise PolicyError('CASE_SCHEMA_UNAVAILABLE')
            self._check_schema(db)

    @staticmethod
    def _check_schema(db):
        row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,)).fetchone()
        if not row or _normalized(row[0]) != _normalized(_CREATE):
            raise PolicyError('CASE_SCHEMA_UNAVAILABLE')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (_TABLE,)).fetchone():
            raise PolicyError('CASE_SCHEMA_UNAVAILABLE')

    @staticmethod
    def _revision(value):
        if type(value) is not int or value < 0 or value > 2**53-1:
            raise PolicyError('CASE_UNAVAILABLE')

    @staticmethod
    def _student(value):
        if not isinstance(value,str) or not _STUDENT.fullmatch(value):
            raise PolicyError('CASE_UNAVAILABLE')

    @staticmethod
    def _validate(state):
        step = state['step']
        if step not in _ORDER or type(state['revision']) is not int or not 0 <= state['revision'] <= 2**53-1:
            raise PolicyError('CASE_INTEGRITY_FAILURE')
        flags = [state['decode_hint'],state['context_hint'],state['sequence_hint']]
        if any(type(v) is not int or v not in (-1,0,1) for v in flags):
            raise PolicyError('CASE_INTEGRITY_FAILURE')
        earned = _ORDER[step]
        if any((flag != -1) != (i < earned) for i, flag in enumerate(flags)):
            raise PolicyError('CASE_INTEGRITY_FAILURE')
        if type(state['pending_hint']) is not int or state['pending_hint'] not in (0,1):
            raise PolicyError('CASE_INTEGRITY_FAILURE')
        if state['pending_hint'] and step not in ('decode','context','sequence'):
            raise PolicyError('CASE_INTEGRITY_FAILURE')
        if step == 'lesson_active':
            if not isinstance(state['session_id'],str) or not 1 <= len(state['session_id']) <= 128:
                raise PolicyError('CASE_INTEGRITY_FAILURE')
        elif state['session_id'] is not None:
            raise PolicyError('CASE_INTEGRITY_FAILURE')

    def _load(self, db, actor, student):
        self._check_schema(db)
        row=db.execute('SELECT step,revision,decode_hint,context_hint,sequence_hint,pending_hint,session_id FROM synthetic_case_progress WHERE workspace_id=? AND student_id=? AND identity_id=? AND case_id=?',
                       (actor.workspace_id,student,actor.actor_id,CASE_ID)).fetchone()
        state = dict(zip(_COLUMNS,row)) if row else dict(_DEFAULT)
        self._validate(state)
        return state

    @staticmethod
    def _save(db, actor, student, state):
        SyntheticInvestigationStore._validate(state)
        db.execute('''INSERT INTO synthetic_case_progress
          (workspace_id,student_id,identity_id,case_id,step,revision,decode_hint,context_hint,sequence_hint,pending_hint,session_id)
          VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(workspace_id,student_id,identity_id,case_id)
          DO UPDATE SET step=excluded.step,revision=excluded.revision,decode_hint=excluded.decode_hint,
          context_hint=excluded.context_hint,sequence_hint=excluded.sequence_hint,
          pending_hint=excluded.pending_hint,session_id=excluded.session_id''',
          (actor.workspace_id,student,actor.actor_id,CASE_ID,*(state[k] for k in _COLUMNS)))

    @staticmethod
    def _snapshot(state, feedback=''):
        step=state['step']
        clues=[{'id':cid,'title':title,'text':text,'usedHint':bool(state[key])}
               for key,cid,title,text in _CLUES if state[key] != -1]
        allowed = {'post_office':['voice'],'decode':['voice'],'archive':['activities'],
                   'context':['activities'],'lesson':['activities'],
                   'lesson_active':['activities'],'bookshop':['signin'],'sequence':['signin'],
                   'solved':['signin','activities','voice']}[step]
        phase = {'lesson':'activity_requested','lesson_active':'activity_started',
                 'bookshop':'returned','sequence':'returned','solved':'case_solved'}.get(step,'exploring')
        visited=[]
        if step != 'post_office': visited.append('voice')
        if step in ('context','lesson','lesson_active','bookshop','sequence','solved'): visited.append('activities')
        if step in ('sequence','solved'): visited.append('signin')
        message = feedback if step == 'lesson' and feedback else _MESSAGES[step]
        return {'case_id':CASE_ID,'revision':state['revision'],'phase':phase,'step':step,
                'caseTitle':'The Vanishing Storybook','message':message,
                'clues':clues,'visited':visited,'challengeId':step if step in _CHOICES else None,
                'feedback':feedback,'allowedDestinations':allowed,
                'pendingHint':bool(state['pending_hint']),'boundSessionId':state['session_id']}

    def _transaction(self, token, student, revision, operation):
        self._revision(revision)
        self._student(student)
        with self.store._connect() as db:
            actor=self.store._actor(db,token,student,'lesson')
            state=self._load(db,actor,student)
            if state['revision'] != revision: raise ConflictError('REVISION_CONFLICT')
            feedback=operation(db,actor,state) or ''
            state['revision']+=1
            self._save(db,actor,student,state)
            return self._snapshot(state,feedback)

    def get(self, token, student):
        self._student(student)
        with self.store._connect() as db:
            actor=self.store._actor(db,token,student,'lesson')
            return self._snapshot(self._load(db,actor,student))

    def visit(self, token, student, revision, destination):
        if not isinstance(destination,str) or destination not in ('voice','activities','signin'):
            raise PolicyError('CASE_UNAVAILABLE')
        def change(db,actor,state):
            pair = {'post_office':('voice','decode'),'decode':('voice','decode'),
                    'archive':('activities','context'),'context':('activities','context'),
                    'lesson':('activities','lesson'), 'lesson_active':('activities','lesson_active'),
                    'bookshop':('signin','sequence'),
                    'sequence':('signin','sequence')}.get(state['step'])
            if state['step'] == 'solved': return
            if not pair or destination != pair[0]: raise PolicyError('CASE_UNAVAILABLE')
            state['step']=pair[1]
        return self._transaction(token,student,revision,change)

    def answer(self, token, student, revision, challenge, choice, hint_used):
        if not isinstance(challenge,str) or challenge not in _CHOICES or not isinstance(choice,str) or choice not in ('a','b','c') or type(hint_used) is not bool:
            raise PolicyError('CASE_UNAVAILABLE')
        def change(db,actor,state):
            if state['step'] != challenge: raise PolicyError('CASE_UNAVAILABLE')
            state['pending_hint']=int(bool(state['pending_hint']) or hint_used)
            if choice != _CHOICES[challenge]: return 'Not quite. Read the clue and try again.'
            state[challenge+'_hint']=state['pending_hint']; state['pending_hint']=0
            state['step']={'decode':'archive','context':'lesson','sequence':'solved'}[challenge]
            return 'Clue found.'
        return self._transaction(token,student,revision,change)

    def hint(self, token, student, revision, challenge):
        """Record a hint request before displaying the fixed synthetic hint."""
        if not isinstance(challenge,str) or challenge not in _CHOICES:
            raise PolicyError('CASE_UNAVAILABLE')
        def change(db,actor,state):
            if state['step'] != challenge: raise PolicyError('CASE_UNAVAILABLE')
            state['pending_hint']=1
        return self._transaction(token,student,revision,change)

    def _session(self, db, actor, student, session_id):
        if not isinstance(session_id,str) or not 1 <= len(session_id) <= 128:
            raise PolicyError('CASE_UNAVAILABLE')
        row=db.execute('SELECT workspace_id,student_id,payload,revision FROM sessions WHERE id=?',(session_id,)).fetchone()
        if not row or (row[0],row[1]) != (actor.workspace_id,student): raise PolicyError('CASE_UNAVAILABLE')
        try:
            session=self.store._deserialize(row[2])
        except (ValueError,TypeError,KeyError,json.JSONDecodeError):
            raise PolicyError('CASE_INTEGRITY_FAILURE') from None
        if (type(session.revision) is not int or type(session.stage_index) is not int
                or (session.session_id,session.workspace_id,session.student_id,session.revision) != (session_id,row[0],row[1],row[3])
                or (session.lesson_id,session.lesson_version) != (LESSON_ID,LESSON_VERSION)):
            raise PolicyError('CASE_INTEGRITY_FAILURE')
        try:
            self.store._require_active_pinned_content(db,session)
        except (AttributeError, TypeError, UnicodeError):
            raise PolicyError('CASE_INTEGRITY_FAILURE') from None
        return session

    def bind_lesson(self, token, student, revision, session_id):
        def change(db,actor,state):
            if state['step'] != 'lesson': raise PolicyError('CASE_UNAVAILABLE')
            session=self._session(db,actor,student,session_id)
            if session.status not in ('created','active','paused'): raise PolicyError('CASE_UNAVAILABLE')
            state['session_id']=session_id; state['step']='lesson_active'
        return self._transaction(token,student,revision,change)

    def finish_lesson(self, token, student, revision):
        def change(db,actor,state):
            if state['step'] != 'lesson_active': raise PolicyError('CASE_UNAVAILABLE')
            session=self._session(db,actor,student,state['session_id'])
            if session.status != 'completed' or session.stage_index != 5 or not isinstance(session.responses,list):
                raise PolicyError('CASE_UNAVAILABLE')
            # This exact word is the existing demo lesson's fixed target. It is
            # a game unlock rule, not evidence of reading mastery or level.
            if not any(isinstance(item,dict) and item.get('stage') == 'practice' and isinstance(item.get('response'),str) and item['response'].strip().casefold() == 'map' for item in session.responses):
                state['session_id']=None; state['step']='lesson'
                return 'Reopen the map activity and answer its Practice step to continue.'
            state['session_id']=None; state['step']='bookshop'
        return self._transaction(token,student,revision,change)

    def cancel_lesson(self, token, student, revision):
        def change(db,actor,state):
            if state['step'] != 'lesson_active': raise PolicyError('CASE_UNAVAILABLE')
            state['session_id']=None; state['step']='lesson'
        return self._transaction(token,student,revision,change)

    def reset(self, token, student, revision):
        def change(db,actor,state):
            current_revision=state['revision']; state.update(_DEFAULT); state['revision']=current_revision
        return self._transaction(token,student,revision,change)
