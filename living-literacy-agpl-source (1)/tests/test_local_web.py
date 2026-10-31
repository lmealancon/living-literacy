from prototype.instructional_content import load_demo_lesson as _demo_lesson
import unittest
from io import BytesIO
from urllib.parse import urlencode
from prototype.local_web import render, make_demo, make_handler
from prototype.lesson_engine import STAGES

class LocalWebTests(unittest.TestCase):
    def test_start_page_has_synthetic_warning(self):
        body=render(lesson=_demo_lesson()).decode()
        self.assertIn('SYNTHETIC DATA ONLY',body)
        self.assertIn('Start demo lesson',body)
    def test_html_escapes_errors(self):
        self.assertIn('&lt;script&gt;',render(error='<script>',lesson=_demo_lesson()).decode())
        self.assertNotIn('<script>',render(error='<script>',lesson=_demo_lesson()).decode())
    def test_session_progress_and_no_mastery(self):
        tmp,store,token=make_demo()
        try:
            session=store.start(token,'synthetic-student-1','synthetic-lesson-word-study','demo-1','test-key')
            session=store.transition(token,session.session_id,'active',0)
            html=render(session,lesson=store.content_for_demo(session.lesson_id,session.lesson_version)).decode()
            self.assertIn('not assessed',html)
            self.assertIn('Next stage',html)
            self.assertIn('Practice response',html)
        finally: tmp.cleanup()
    def test_handler_instantiation(self):
        tmp,store,token=make_demo()
        try: self.assertTrue(make_handler(store,token))
        finally: tmp.cleanup()

    def test_finished_demo_can_start_again(self):
        tmp,store,token=make_demo()
        handler=make_handler(store,token)
        def post(**fields):
            body=urlencode(fields).encode()
            request=handler.__new__(handler)
            request.path='/action'; request.rfile=BytesIO(body); request.wfile=BytesIO()
            request.headers={'Content-Length':str(len(body)), 'Content-Type':'application/x-www-form-urlencoded'}
            request.send_response=lambda code: None
            request.send_header=lambda *args: None
            request.end_headers=lambda: None
            request.do_POST()
            request.path='/'
            request.do_GET()
            return request.wfile.getvalue().decode()
        try:
            post(action='start')
            post(action='activate',revision=0)
            for revision in range(1,6): post(action='next',revision=revision)
            finished=post(action='complete',revision=6)
            self.assertIn('Start another demo lesson',finished)
            restarted=post(action='restart',revision=7)
            self.assertIn('Begin lesson',restarted)
            self.assertIn('Status:</strong> created',restarted)
        finally:
            tmp.cleanup()

if __name__=='__main__': unittest.main()
