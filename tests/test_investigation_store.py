"""Transaction and authority checks for fictional case progress only."""
import json
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prototype.instructional_content import CONTENT_PATH
from prototype.investigation_store import CASE_ID, SyntheticInvestigationStore, _CHOICES
from prototype.lesson_engine import ConflictError, PolicyError
from prototype.migrations import migrate
from prototype.persistent_store import SyntheticSQLiteStore


class InvestigationStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional.sqlite'
        self.store = SyntheticSQLiteStore(self.path)
        self.student = 'synthetic-student-1'
        self.token = self.store.provision_synthetic_family('synthetic-family-1', 'synthetic-parent-1', self.student)
        self.other_token = self.store.provision_synthetic_family('synthetic-family-2', 'synthetic-parent-2', 'synthetic-student-2')
        lesson = json.loads(CONTENT_PATH.read_text())
        self.registry = self.store.content_registry()
        self.registry.create_draft(lesson, 'synthetic-author')
        self.registry.transition(lesson['lesson_id'], lesson['version'], 'submit', 'synthetic-author', 'fixture')
        self.registry.transition(lesson['lesson_id'], lesson['version'], 'approve_prototype', 'synthetic-reviewer', 'fixture')
        self.case = SyntheticInvestigationStore(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def start_case_lesson(self):
        state = self.case.get(self.token, self.student)
        state = self.case.visit(self.token, self.student, state['revision'], 'voice')
        state = self.case.answer(self.token, self.student, state['revision'], 'decode', 'a', False)
        state = self.case.visit(self.token, self.student, state['revision'], 'activities')
        state = self.case.answer(self.token, self.student, state['revision'], 'context', 'b', False)
        session = self.store.start(self.token, self.student, 'synthetic-lesson-word-study', 'demo-1', 'fictional-case-key-1')
        state = self.case.bind_lesson(self.token, self.student, state['revision'], session.session_id)
        return state, session

    def complete_lesson(self, session, response='map'):
        session = self.store.transition(self.token, session.session_id, 'active', session.revision)
        for _ in range(3):
            session = self.store.advance_stage(self.token, session.session_id, session.revision)
        if response is not None:
            self.store.record_response(self.token, session.session_id, session.revision, response, {'audio_or_modeling': False})
            session = self.store.get_session(self.token, session.session_id)
        for _ in range(2):
            session = self.store.advance_stage(self.token, session.session_id, session.revision)
        return self.store.transition(self.token, session.session_id, 'completed', session.revision)

    def test_order_wrong_answer_hints_and_revisions(self):
        state = self.case.get(self.token, self.student)
        self.assertEqual((state['step'], state['revision'], state['clues']), ('post_office', 0, []))
        with self.assertRaises(PolicyError):
            self.case.visit(self.token, self.student, 0, 'signin')
        state = self.case.visit(self.token, self.student, 0, 'voice')
        with self.assertRaises(ConflictError):
            self.case.answer(self.token, self.student, 0, 'decode', 'a', False)
        state = self.case.answer(self.token, self.student, state['revision'], 'decode', 'b', True)
        self.assertEqual(state['step'], 'decode')
        self.assertEqual(state['clues'], [])
        self.assertTrue(state['pendingHint'])
        state = self.case.answer(self.token, self.student, state['revision'], 'decode', 'a', False)
        self.assertEqual(state['step'], 'archive')
        self.assertTrue(state['clues'][0]['usedHint'])
        self.assertEqual(self.case.get(self.token, self.student), state | {'feedback': ''})
        with self.assertRaises(PolicyError):
            self.case.answer(self.token, self.student, state['revision'], 'sequence', 'c', False)

    def test_hint_is_persisted_before_reveal_and_survives_reopening(self):
        state = self.case.visit(self.token, self.student, 0, 'voice')
        before = self.case.get(self.token, self.student)
        with self.assertRaises(PolicyError):
            self.case.hint(self.token, self.student, state['revision'], 'context')
        self.assertEqual(self.case.get(self.token, self.student), before)
        with self.assertRaises(ConflictError):
            self.case.hint(self.token, self.student, 0, 'decode')
        self.assertEqual(self.case.get(self.token, self.student), before)
        state = self.case.hint(self.token, self.student, state['revision'], 'decode')
        self.assertTrue(state['pendingHint'])
        self.assertEqual(state['clues'], [])
        reopened = SyntheticInvestigationStore(SyntheticSQLiteStore(self.path))
        state = reopened.get(self.token, self.student)
        self.assertTrue(state['pendingHint'])
        # A later client cannot erase the earlier hint flag by sending false.
        state = reopened.answer(self.token, self.student, state['revision'], 'decode', 'a', False)
        self.assertTrue(state['clues'][0]['usedHint'])
        self.assertFalse(state['pendingHint'])

    def test_hint_denied_after_consent_withdrawal_without_mutation(self):
        state = self.case.visit(self.token, self.student, 0, 'voice')
        self.store.withdraw_synthetic_consent(self.token, self.student, 'lesson')
        with self.assertRaises(PolicyError):
            self.case.hint(self.token, self.student, state['revision'], 'decode')
        with self.store._connect() as db:
            row = db.execute('SELECT revision,pending_hint FROM synthetic_case_progress WHERE case_id=?',(CASE_ID,)).fetchone()
        self.assertEqual(row, (state['revision'], 0))

    def test_revisit_active_lesson_preserves_bound_session(self):
        state, session = self.start_case_lesson()
        resumed = self.case.visit(self.token, self.student, state['revision'], 'activities')
        self.assertEqual(resumed['step'], 'lesson_active')
        self.assertEqual(resumed['boundSessionId'], session.session_id)
        self.assertEqual(resumed['revision'], state['revision'] + 1)
        self.complete_lesson(session)
        state = self.case.finish_lesson(self.token, self.student, resumed['revision'])
        self.assertEqual(state['step'], 'bookshop')

    def test_complete_case_and_reset_persists(self):
        state, session = self.start_case_lesson()
        self.complete_lesson(session, ' MAP ')
        state = self.case.finish_lesson(self.token, self.student, state['revision'])
        self.assertEqual(state['step'], 'bookshop')
        state = self.case.visit(self.token, self.student, state['revision'], 'signin')
        state = self.case.answer(self.token, self.student, state['revision'], 'sequence', 'c', False)
        self.assertEqual(state['phase'], 'case_solved')
        self.assertEqual(len(state['clues']), 3)
        self.assertNotIn('mastery', state)
        again = SyntheticInvestigationStore(SyntheticSQLiteStore(self.path)).get(self.token, self.student)
        self.assertEqual(again['phase'], 'case_solved')
        state = self.case.reset(self.token, self.student, state['revision'])
        self.assertEqual((state['step'], state['clues']), ('post_office', []))
        self.assertGreater(state['revision'], 0)

    def test_completed_session_requires_exact_practice_word(self):
        for answer in (None, 'mop'):
            with self.subTest(answer=answer):
                state, session = self.start_case_lesson()
                self.complete_lesson(session, answer)
                previous_revision = state['revision']
                state = self.case.finish_lesson(self.token, self.student, previous_revision)
                self.assertEqual((state['step'], state['revision'], state['boundSessionId']),
                                 ('lesson', previous_revision + 1, None))
                self.assertEqual(len(state['clues']), 2)
                self.assertIn('Practice step', state['message'])
                state = self.case.reset(self.token, self.student, state['revision'])
                # Subsequent sample needs its own idempotency key.
                with self.store._connect() as db:
                    db.execute('DELETE FROM idempotency')

    def test_consent_revocation_and_cross_family_denied(self):
        with self.assertRaises(PolicyError):
            self.case.get(self.other_token, self.student)
        with self.assertRaises(PolicyError):
            self.case.visit(self.other_token, self.student, 0, 'voice')
        self.store.withdraw_synthetic_consent(self.token, self.student, 'lesson')
        with self.assertRaises(PolicyError):
            self.case.get(self.token, self.student)
        with self.assertRaises(PolicyError):
            self.case.visit(self.token, self.student, 0, 'voice')

    def test_cross_family_session_cannot_bind(self):
        state, _ = self.start_case_lesson()
        state = self.case.cancel_lesson(self.token, self.student, state['revision'])
        foreign = self.store.start(self.other_token, 'synthetic-student-2', 'synthetic-lesson-word-study', 'demo-1', 'fictional-other-key')
        with self.assertRaises(PolicyError):
            self.case.bind_lesson(self.token, self.student, state['revision'], foreign.session_id)
        self.assertEqual(self.case.get(self.token, self.student)['step'], 'lesson')

    def test_guardian_revocation_blocks_existing_case(self):
        self.case.visit(self.token, self.student, 0, 'voice')
        self.store.revoke_synthetic_guardian(self.token, self.student)
        with self.assertRaises(PolicyError):
            self.case.get(self.token, self.student)
        with self.assertRaises(PolicyError):
            self.case.answer(self.token, self.student, 1, 'decode', 'a', False)

    def test_concurrent_same_revision_has_one_winner(self):
        barrier = threading.Barrier(2)
        def attempt():
            barrier.wait(timeout=3)
            try:
                self.case.visit(self.token, self.student, 0, 'voice')
                return 'success'
            except ConflictError:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ['success', 'conflict'])
        self.assertEqual(self.case.get(self.token, self.student)['revision'], 1)

    def test_strict_input_and_revision_types(self):
        for revision in (True, -1, '0', 2**53):
            with self.subTest(revision=revision), self.assertRaises(PolicyError):
                self.case.visit(self.token, self.student, revision, 'voice')
        state = self.case.visit(self.token, self.student, 0, 'voice')
        for challenge,choice,hint in [('decode','a',1),('decode','secret',False),('other','a',False)]:
            with self.subTest(challenge=challenge,choice=choice,hint=hint), self.assertRaises(PolicyError):
                self.case.answer(self.token, self.student, state['revision'], challenge, choice, hint)
        self.assertEqual(self.case.get(self.token, self.student)['revision'], state['revision'])

    def test_withdrawn_and_tampered_pinned_content_denied(self):
        state, session = self.start_case_lesson()
        self.complete_lesson(session)
        self.registry.transition('synthetic-lesson-word-study','demo-1','suspend','synthetic-reviewer','withdrawn')
        with self.assertRaises(PolicyError):
            self.case.finish_lesson(self.token, self.student, state['revision'])

    def test_malformed_content_storage_fails_closed(self):
        state, session = self.start_case_lesson()
        self.complete_lesson(session)
        with self.store._connect() as db:
            db.execute('UPDATE content_versions SET payload=? WHERE lesson_id=? AND version=?',
                       (sqlite3.Binary(b'not a valid payload'), 'synthetic-lesson-word-study', 'demo-1'))
        with self.assertRaises(PolicyError):
            self.case.finish_lesson(self.token, self.student, state['revision'])
        self.assertEqual(self.case.get(self.token, self.student)['revision'], state['revision'])

    def test_modified_session_metadata_and_content_digest_denied(self):
        state, session = self.start_case_lesson()
        self.complete_lesson(session)
        with self.store._connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM sessions WHERE id=?',(session.session_id,)).fetchone()[0])
            payload['workspace_id'] = 'synthetic-family-2'
            db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(payload),session.session_id))
        with self.assertRaises(PolicyError):
            self.case.finish_lesson(self.token, self.student, state['revision'])
        with self.store._connect() as db:
            payload['workspace_id'] = 'synthetic-family-1'
            db.execute('UPDATE sessions SET payload=? WHERE id=?',(json.dumps(payload),session.session_id))
            db.execute("UPDATE content_versions SET payload=payload || ' ' WHERE lesson_id=? AND version=?",('synthetic-lesson-word-study','demo-1'))
        with self.assertRaises(PolicyError):
            self.case.finish_lesson(self.token, self.student, state['revision'])

    def test_schema_trigger_and_corrupt_state_fail_closed(self):
        state = self.case.visit(self.token, self.student, 0, 'voice')
        with self.store._connect() as db:
            db.execute("UPDATE synthetic_case_progress SET step='archive' WHERE case_id=?",(CASE_ID,))
        with self.assertRaises(PolicyError):
            self.case.get(self.token, self.student)
        with self.store._connect() as db:
            db.execute("UPDATE synthetic_case_progress SET step='decode' WHERE case_id=?",(CASE_ID,))
            db.execute('CREATE TRIGGER dangerous_case AFTER UPDATE ON synthetic_case_progress BEGIN DELETE FROM grants; END')
        with self.assertRaises(PolicyError):
            self.case.answer(self.token, self.student, state['revision'], 'decode', 'a', False)
        with self.store._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM grants').fetchone()[0], 2)

    def test_unknown_existing_table_rejected_and_migration_compatible(self):
        self.assertEqual(migrate(self.path), [1, 2])
        self.assertEqual(migrate(self.path), [])
        other = Path(self.tmp.name) / 'other.sqlite'
        store = SyntheticSQLiteStore(other)
        with store._connect() as db:
            db.execute('CREATE TABLE synthetic_case_progress (fake TEXT)')
        with self.assertRaises(PolicyError):
            SyntheticInvestigationStore(store)

    def test_no_raw_response_in_case_row(self):
        state, session = self.start_case_lesson()
        self.complete_lesson(session)
        self.case.finish_lesson(self.token, self.student, state['revision'])
        with self.store._connect() as db:
            row = db.execute('SELECT * FROM synthetic_case_progress').fetchone()
        self.assertNotIn('map', [str(value).lower() for value in row])

    def test_frontend_candidates_match_server_unlock_answers(self):
        # Contract test across separately maintained UI fixtures and authority:
        # a wording/content update must not leave the only correct option locked.
        script = """const fs=require('fs'),vm=require('vm'),window={};
vm.runInNewContext(fs.readFileSync('prototype/web/investigation-reading.js','utf8'),{window});
const x=window.LivingInvestigationReading;
const answer={}; for(const c of x.list()) answer[c.id]=c.options.filter(o=>x.evaluate(c.id,o.id,false).solved).map(o=>o.id);
process.stdout.write(JSON.stringify(answer));"""
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node','-e',script], cwd=root, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), {key:[value] for key,value in _CHOICES.items()})


if __name__ == '__main__': unittest.main()
