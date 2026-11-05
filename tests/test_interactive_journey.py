"""In-process test of the synthetic interactive journey, not browser or student QA."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from prototype.app_server import App, bootstrap, make_handler
from prototype.lesson_engine import STAGES


class InteractiveJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / 'fictional.sqlite'
        bootstrap(path, 'synthetic-parent', 'fictional-password')
        self.app = App(path)
        self.handler = make_handler(self.app)
        self.cookie = ''
        self.csrf = ''

    def request(self, method, path, data=None):
        handler = self.handler.__new__(self.handler)
        handler.server = SimpleNamespace(server_port=8765)
        handler.path = path
        handler.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765',
                           'Content-Type': 'application/json', 'Cookie': self.cookie,
                           'X-CSRF-Token': self.csrf}
        body = json.dumps(data).encode() if data is not None else b''
        handler.headers['Content-Length'] = str(len(body))
        handler.rfile, handler.wfile = BytesIO(body), BytesIO()
        headers = {}
        handler.send_response = lambda status: headers.update(status=status)
        handler.send_header = lambda key, value: headers.update({key: value})
        handler.end_headers = lambda: None
        getattr(handler, 'do_' + method)()
        if 'Set-Cookie' in headers:
            self.cookie = headers['Set-Cookie'].split(';')[0]
        return headers['status'], json.loads(handler.wfile.getvalue())

    def login_and_start(self):
        status, body = self.request('POST', '/api/login', {'identity': 'synthetic-parent',
                                                           'passphrase': 'fictional-password'})
        self.assertEqual(status, 200)
        self.csrf = body['csrf']
        status, body = self.request('POST', '/api/sessions', {'student_id': 'synthetic-student-1',
            'lesson_id': 'synthetic-lesson-word-study', 'version': 'demo-1',
            'idempotency_key': 'synthetic-interactive-test-key'})
        self.assertEqual(status, 201)
        return body['session']

    def action(self, session, action, **extra):
        return self.request('POST', '/api/sessions/' + session['session_id'] + '/action',
                            {'action': action, 'revision': session['revision'], **extra})

    def test_six_stages_pause_resume_and_recorded_assistance(self):
        session = self.login_and_start()
        status, body = self.action(session, 'activate')
        self.assertEqual(status, 200)
        session = body['session']
        for index, stage in enumerate(STAGES):
            self.assertEqual(session['stage_index'], index)
            # A fictional response is stored, not automatically scored as mastery.
            status, body = self.action(session, 'respond', response='fictional practice', assisted=index == 4)
            self.assertEqual(status, 200)
            session = body['session']
            self.assertEqual(session['responses'][-1]['stage'], stage)
            if index == 4:
                self.assertFalse(session['responses'][-1]['independent_evidence_eligible'])
            if index == 2:
                status, body = self.action(session, 'pause')
                self.assertEqual(status, 200)
                session = body['session']
                self.assertEqual(self.action(session, 'next')[0], 403)
                status, body = self.action(session, 'resume')
                self.assertEqual(status, 200)
                session = body['session']
            if index < len(STAGES) - 1:
                status, body = self.action(session, 'next')
                self.assertEqual(status, 200)
                session = body['session']
        status, body = self.action(session, 'complete')
        self.assertEqual(status, 200)
        session = body['session']
        self.assertEqual(session['status'], 'completed')
        self.assertEqual(session['mastery_status'], 'not_assessed')
        status, history = self.request('GET', '/api/history/synthetic-student-1')
        self.assertEqual(status, 200)
        self.assertEqual(history['sessions'][0]['session_id'], session['session_id'])
        self.assertEqual(len(history['sessions'][0]['responses']), 6)


if __name__ == '__main__':
    unittest.main()
