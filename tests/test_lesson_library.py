"""Synthetic catalog is not educational publication or review approval."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prototype.app_server import App, bootstrap
from prototype.instructional_content import CONTENT_PATH
from prototype.lesson_engine import PolicyError


class LessonLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'library.sqlite'
        bootstrap(self.db, 'synthetic-parent-1', 'fictional-password-123')
        self.app = App(self.db)
        self.registry = self.app.store.content_registry()
        self.fixture = json.loads(CONTENT_PATH.read_text(encoding='utf-8'))

    def tearDown(self):
        self.temp.cleanup()

    def draft(self, name):
        content = copy.deepcopy(self.fixture)
        content['lesson_id'] = 'synthetic-lesson-' + name
        content['title'] = 'Synthetic fixture ' + name
        self.registry.create_draft(content, 'synthetic-author')
        return content

    def approve(self, content):
        key = (content['lesson_id'], content['version'])
        self.registry.transition(*key, 'submit', 'synthetic-author', 'fictional fixture submission')
        self.registry.transition(*key, 'approve_prototype', 'synthetic-reviewer', 'fictional fixture review')

    def test_multiple_approved_versions_listed_but_draft_and_review_hidden(self):
        second = self.draft('second')
        self.approve(second)
        self.draft('draft')
        in_review = self.draft('in-review')
        self.registry.transition(in_review['lesson_id'], in_review['version'], 'submit',
                                 'synthetic-author', 'fictional submission')
        ids = [lesson['lesson_id'] for lesson in self.app.lessons()]
        self.assertEqual(ids, ['synthetic-lesson-second', 'synthetic-lesson-word-study'])
        self.assertEqual(len(self.app.lessons()[0]['stages']), 6)

    def test_withdrawn_versions_disappear_and_original_remains(self):
        second = self.draft('second')
        self.approve(second)
        self.registry.transition(second['lesson_id'], second['version'], 'suspend',
                                 'synthetic-reviewer', 'fictional withdrawal')
        self.assertEqual([lesson['lesson_id'] for lesson in self.app.lessons()],
                         ['synthetic-lesson-word-study'])

    def test_tampered_or_malformed_records_are_not_listed(self):
        second = self.draft('second')
        self.approve(second)
        with self.app.store._connect() as db:
            db.execute('UPDATE content_versions SET payload=? WHERE lesson_id=? AND version=?',
                       ('{}', second['lesson_id'], second['version']))
        self.assertEqual([lesson['lesson_id'] for lesson in self.app.lessons()],
                         ['synthetic-lesson-word-study'])
        # Even a matching digest must not make invalid JSON a valid lesson.
        malformed = '{invalid json'
        with self.app.store._connect() as db:
            db.execute('UPDATE content_versions SET payload=?,digest=? WHERE lesson_id=? AND version=?',
                       (malformed, hashlib.sha256(malformed.encode()).hexdigest(),
                        second['lesson_id'], second['version']))
        self.assertEqual([lesson['lesson_id'] for lesson in self.app.lessons()],
                         ['synthetic-lesson-word-study'])
        with self.assertRaises(PolicyError):
            self.registry.for_synthetic_demo(second['lesson_id'], second['version'])

    def test_list_rechecks_prototype_stage_rules_and_record_identity(self):
        second = self.draft('second')
        self.approve(second)
        for mutation in ('wrong-id', 'stages'):
            altered = copy.deepcopy(second)
            if mutation == 'wrong-id':
                altered['lesson_id'] = 'synthetic-some-other-lesson'
            else:
                altered['stages'].pop()
            payload = json.dumps(altered, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            with self.app.store._connect() as db:
                db.execute('UPDATE content_versions SET payload=?,digest=? WHERE lesson_id=? AND version=?',
                           (payload, hashlib.sha256(payload.encode()).hexdigest(),
                            second['lesson_id'], second['version']))
            self.assertEqual([lesson['lesson_id'] for lesson in self.app.lessons()],
                             ['synthetic-lesson-word-study'])


if __name__ == '__main__':
    unittest.main()
