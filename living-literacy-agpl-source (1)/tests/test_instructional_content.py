import json
import tempfile
import unittest
from pathlib import Path
from prototype.instructional_content import load_demo_lesson, stage_content
from prototype.lesson_engine import PolicyError
from prototype.local_web import make_demo, render

class InstructionalContentTests(unittest.TestCase):
    def test_six_stages_have_real_display_content(self):
        lesson=load_demo_lesson()
        self.assertEqual(len(lesson['stages']),6)
        self.assertEqual(stage_content(lesson,4)['display_text'],'map')
    def test_no_unvalidated_skill_mapping(self):
        self.assertEqual(load_demo_lesson()['skill_ids'],[])
    def test_independent_only_at_stage_five(self):
        self.assertEqual([s['independent_task'] for s in load_demo_lesson()['stages']],[False,False,False,False,True,False])
    def test_rejects_bad_stage_order(self):
        data=load_demo_lesson(); data['stages'][0]['id']='review'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'invalid.json';path.write_text(json.dumps(data))
            with self.assertRaises(PolicyError): load_demo_lesson(path)
    def test_rejects_pretend_approved_skill_link(self):
        data=load_demo_lesson();data['skill_ids']=['PH-999']
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'invalid.json';path.write_text(json.dumps(data))
            with self.assertRaises(PolicyError): load_demo_lesson(path)
    def test_web_displays_stage_content(self):
        tmp,store,token=make_demo()
        try:
            session=store.start(token,'synthetic-student-1','synthetic-lesson-word-study','demo-1','content-test')
            body=render(session,lesson=store.content_for_demo(session.lesson_id,session.lesson_version)).decode()
            self.assertIn('What sounds do you hear?',body)
            self.assertIn('Adult demonstration note',body)
        finally: tmp.cleanup()

if __name__=='__main__': unittest.main()
