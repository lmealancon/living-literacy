"""In-process HTTP contract tests: no listening socket or real data required."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from prototype.app_server import App, bootstrap, make_handler
from prototype.synthetic_auth import SyntheticParentAuth


class AppServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Path(self.tmp.name) / 'demo.sqlite'
        bootstrap(db, 'synthetic-parent-a', 'fictional-password-a')
        self.app = App(db)
        token = self.app.store.provision_synthetic_family('synthetic-family-b', 'synthetic-parent-b', 'synthetic-student-b')
        SyntheticParentAuth(self.app.store).enroll(token, 'fictional-password-b')
        self.handler = make_handler(self.app)
        self.cookie = ''
        self.csrf = ''

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, method, path, data=None, *, origin=True, csrf=True):
        request = self.handler.__new__(self.handler)
        request.server = SimpleNamespace(server_port=8765)
        request.path = path
        request.headers = {'Host': '127.0.0.1:8765', 'Cookie': self.cookie}
        if origin: request.headers['Origin'] = 'http://127.0.0.1:8765'
        if csrf: request.headers['X-CSRF-Token'] = self.csrf
        body = json.dumps(data).encode() if data is not None else b''
        request.headers['Content-Type'] = 'application/json'
        request.headers['Content-Length'] = str(len(body))
        request.rfile = BytesIO(body); request.wfile = BytesIO(); headers = {}
        request.send_response = lambda status: headers.update(status=status)
        request.send_header = lambda key, value: headers.update({key: value})
        request.end_headers = lambda: None
        getattr(request, 'do_' + method)()
        if 'Set-Cookie' in headers: self.cookie = headers['Set-Cookie'].split(';')[0]
        return headers['status'], json.loads(request.wfile.getvalue())

    def login(self, identity='synthetic-parent-a', password='fictional-password-a'):
        status, data = self.call('POST', '/api/login', {'identity': identity, 'passphrase': password})
        self.assertEqual(status, 200)
        self.csrf = data['csrf']

    def test_login_profile_lesson_and_history(self):
        self.login()
        self.assertEqual(self.call('GET', '/api/me')[1]['identity'], 'synthetic-parent-a')
        profiles = self.call('GET', '/api/profiles')[1]['profiles']
        self.assertEqual([p['id'] for p in profiles], ['synthetic-student-1'])
        lesson = self.call('GET', '/api/lessons')[1]['lessons'][0]
        request = {'student_id': profiles[0]['id'], 'lesson_id': lesson['lesson_id'], 'version': lesson['version'], 'idempotency_key': 'synthetic-test-key-123'}
        status, data = self.call('POST', '/api/sessions', request)
        self.assertEqual(status, 201)
        sid = data['session']['session_id']
        self.assertEqual(self.call('POST', '/api/sessions', request)[1]['session']['session_id'], sid)
        status, data = self.call('POST', '/api/sessions/' + sid + '/action', {'action': 'activate', 'revision': 0})
        self.assertEqual(status, 200)
        self.assertEqual(data['session']['status'], 'active')
        self.assertEqual(self.call('POST', '/api/sessions/' + sid + '/action', {'action': 'pause', 'revision': 0})[0], 409)
        status, _ = self.call('POST', '/api/sessions/' + sid + '/action', {'action': 'respond', 'revision': 1, 'response': 'fictional'})
        self.assertEqual(status, 400)
        status, data = self.call('POST', '/api/sessions/' + sid + '/action', {'action': 'respond', 'revision': 1, 'response': 'fictional', 'assisted': True})
        self.assertEqual(status, 200)
        self.assertEqual(data['session']['responses'][0]['assistance']['audio_or_modeling'], True)
        self.assertEqual(len(self.call('GET', '/api/history/synthetic-student-1')[1]['sessions']), 1)
        self.assertEqual(self.call('POST', '/api/logout', {})[0], 200)
        self.assertEqual(self.call('GET', '/api/me')[0], 403)

    def test_csrf_and_cross_family_denied(self):
        self.login()
        self.assertEqual(self.call('POST', '/api/profiles', {'anchor_id': 'synthetic-student-1', 'student_id': 'synthetic-new'}, csrf=False)[0], 403)
        self.assertEqual(self.call('POST', '/api/profiles', {'anchor_id': 'synthetic-student-1', 'student_id': 'synthetic-new'}, origin=False)[0], 403)
        self.assertEqual(self.call('GET', '/api/history/synthetic-student-b')[0], 403)
        self.assertEqual(self.call('POST', '/api/profiles', {'anchor_id': 'synthetic-student-b', 'student_id': 'synthetic-new'})[0], 403)

    def test_interests_and_activity_require_authorized_profile_and_csrf(self):
        self.login()
        path = '/api/profiles/synthetic-student-1/interests'
        self.assertEqual(self.call('GET', path)[1]['interests'], [])
        self.assertEqual(self.call('POST', path, {'interests': ['music', 'science']}, csrf=False)[0], 403)
        self.assertEqual(self.call('POST', path, {'interests': ['music', 'science']})[0], 200)
        self.assertEqual(self.call('GET', path)[1]['interests'], ['music', 'science'])
        self.assertEqual(self.call('POST', path, {'interests': ['private text']})[0], 403)
        self.assertEqual(self.call('GET', '/api/profiles/synthetic-student-b/interests')[0], 403)
        self.assertEqual(self.call('POST', '/api/profiles/synthetic-student-b/interests', {'interests': ['music']})[0], 403)
        self.assertEqual(self.call('GET', '/api/profiles/synthetic-student-1/activity')[1]['sessions_total'], 0)
        self.assertEqual(self.call('GET', '/api/profiles/synthetic-student-b/activity')[0], 403)
        token = SyntheticParentAuth(self.app.store).login('synthetic-parent-a', 'fictional-password-a')
        self.app.store.withdraw_synthetic_consent(token, 'synthetic-student-1', 'profile')
        # Login rotates the original token; use the new identity for the revocation check.
        self.cookie = 'll_session=' + token
        self.assertEqual(self.call('GET', path)[0], 403)

    def test_withdrawn_lesson_blocks_existing_session_write(self):
        self.login()
        data = self.call('POST', '/api/sessions', {'student_id': 'synthetic-student-1', 'lesson_id': 'synthetic-lesson-word-study', 'version': 'demo-1', 'idempotency_key': 'synthetic-test-key-123'})[1]
        sid = data['session']['session_id']
        self.assertEqual(self.call('GET', '/api/lessons/synthetic-lesson-word-study/demo-1')[0], 200)
        self.app.store.content_registry().transition('synthetic-lesson-word-study', 'demo-1', 'suspend', 'synthetic-reviewer', 'withdrawn')
        self.assertEqual(self.call('POST', '/api/sessions/' + sid + '/action', {'action': 'activate', 'revision': 0})[0], 403)
        self.assertEqual(self.call('GET', '/api/lessons/synthetic-lesson-word-study/demo-1')[0], 403)
        self.assertEqual(self.call('GET', '/api/lessons')[1]['lessons'], [])
        self.assertEqual(self.call('GET', '/api/sessions/' + sid)[0], 200)


if __name__ == '__main__': unittest.main()
