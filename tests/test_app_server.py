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

    def test_welcome_illustration_is_served_as_png(self):
        request = self.handler.__new__(self.handler)
        request.server = SimpleNamespace(server_port=8765)
        request.path = '/hero-world.png'
        request.headers = {'Host': '127.0.0.1:8765'}
        request.rfile = BytesIO(); request.wfile = BytesIO(); headers = {}
        request.send_response = lambda status: headers.update(status=status)
        request.send_header = lambda key, value: headers.update({key: value})
        request.end_headers = lambda: None
        request.do_GET()
        self.assertEqual(headers['status'], 200)
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertTrue(request.wfile.getvalue().startswith(b'\x89PNG\r\n\x1a\n'))

    def test_reading_world_assets_are_served_with_expected_types(self):
        for path, expected in [('/reading-world.js', 'application/javascript; charset=utf-8'),
                               ('/reading-world.css', 'text/css; charset=utf-8'),
                               ('/world3d-engine.js', 'application/javascript; charset=utf-8'),
                               ('/world3d-journey.js', 'application/javascript; charset=utf-8'),
                               ('/investigation-reading.js', 'application/javascript; charset=utf-8'),
                               ('/world3d-ui.js', 'application/javascript; charset=utf-8'),
                               ('/world3d.css', 'text/css; charset=utf-8')]:
            with self.subTest(path=path):
                request = self.handler.__new__(self.handler)
                request.server = SimpleNamespace(server_port=8765)
                request.path = path
                request.headers = {'Host': '127.0.0.1:8765'}
                request.rfile = BytesIO(); request.wfile = BytesIO(); headers = {}
                request.send_response = lambda status: headers.update(status=status)
                request.send_header = lambda key, value: headers.update({key: value})
                request.end_headers = lambda: None
                request.do_GET()
                self.assertEqual(headers['status'], 200)
                self.assertEqual(headers['Content-Type'], expected)
                self.assertTrue(request.wfile.getvalue())

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

    def test_curriculum_domains_require_sign_in_and_remain_draft(self):
        self.assertEqual(self.call('GET', '/api/curriculum/domains')[0], 403)
        self.login()
        status, data = self.call('GET', '/api/curriculum/domains')
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'candidate_counts_only')
        self.assertFalse(data['canonical_skill_definitions_present'])
        self.assertEqual(len(data['domains']), 12)

    def test_companion_demo_is_authenticated_and_disabled_by_default(self):
        self.assertEqual(self.call('GET', '/api/companion/status')[0], 403)
        self.login()
        self.assertEqual(self.call('GET', '/api/companion/status')[1], {'enabled': False})
        self.assertEqual(self.call('POST', '/api/companion/reply', {'action': 'hello'})[0], 403)

        class FakeProvider:
            calls = []
            def reply(self, action):
                self.calls.append(action)
                return {'text': 'Hello! It is nice to meet you.', 'mode': 'local_ai_synthetic'}
        provider = FakeProvider()
        self.app.synthetic_companion = provider
        self.app.synthetic_conversation = object()
        self.assertEqual(self.call('GET', '/api/companion/status')[1], {'enabled': True})
        self.assertEqual(self.call('POST', '/api/companion/reply', {'action': 'hello'}, csrf=False)[0], 403)
        self.assertEqual(self.call('POST', '/api/companion/reply', {'action': 'hello'}, origin=False)[0], 403)
        self.assertEqual(self.call('POST', '/api/companion/reply', {'action': 'hello', 'student': 'synthetic-secret'})[0], 400)
        self.assertEqual(provider.calls, [])
        status, result = self.call('POST', '/api/companion/reply', {'action': 'hello'})
        self.assertEqual((status, result['mode'], provider.calls), (200, 'local_ai_synthetic', ['hello']))
        self.assertEqual(self.call('POST', '/api/logout', {})[0], 200)
        self.assertEqual(self.call('POST', '/api/companion/reply', {'action': 'hello'})[0], 403)

    def test_companion_model_cannot_be_enabled_for_private_staging(self):
        with self.assertRaises(ValueError):
            App(Path(self.tmp.name) / 'other.sqlite', staging_origin='https://example.test',
                proxy_secret='a' * 32, synthetic_companion_model='local-model')

    def test_synthetic_conversation_route_authentication_and_payload(self):
        payload = {'message': 'What is a story?', 'history': []}
        self.assertEqual(self.call('POST', '/api/companion/conversation', payload)[0], 403)
        self.login()
        self.assertEqual(self.call('POST', '/api/companion/conversation', payload)[0], 403)

        class FakeConversation:
            calls = []
            def reply(self, message, history):
                self.calls.append((message, history))
                return {'text': 'A fictional reply.', 'mode': 'local_ai_unreviewed'}
        provider = FakeConversation()
        self.app.synthetic_conversation = provider
        self.assertEqual(self.call('POST', '/api/companion/conversation', payload, csrf=False)[0], 403)
        self.assertEqual(self.call('POST', '/api/companion/conversation', payload, origin=False)[0], 403)
        self.assertEqual(self.call('POST', '/api/companion/conversation', dict(payload, student_id='synthetic-a'))[0], 400)
        self.assertEqual(provider.calls, [])
        status, result = self.call('POST', '/api/companion/conversation', payload)
        self.assertEqual((status, result['mode'], provider.calls), (200, 'local_ai_unreviewed', [('What is a story?', [])]))
        self.assertEqual(self.call('POST', '/api/logout', {})[0], 200)
        self.assertEqual(self.call('POST', '/api/companion/conversation', payload)[0], 403)

    def test_synthetic_assessment_api_requires_separate_consent_and_withdrawal(self):
        forms_path = '/api/v1/students/synthetic-student-1/assessment-forms'
        history_path = '/api/v1/students/synthetic-student-1/assessment-history'
        self.assertEqual(self.call('GET', forms_path)[0], 403)
        self.login()
        self.assertEqual(self.call('GET', forms_path)[0], 403)
        token = self.cookie.split('=', 1)[1]
        trusted = self.app.assessment_workflow.assessments
        trusted.add_reviewed_fixture('synthetic-form', 'demo-1', 'en',
            [{'id': 'synthetic-item-1', 'prompt': 'What do you notice?'}],
            'synthetic-author', 'synthetic-reviewer')
        trusted.set_synthetic_consent(token, 'synthetic-student-1', True)
        status, data = self.call('GET', forms_path)
        self.assertEqual(status, 200)
        self.assertEqual(data['forms'][0]['validation_status'], 'unvalidated')
        request = {'student_id': 'synthetic-student-1', 'form_id': 'synthetic-form',
                   'version': 'demo-1', 'idempotency_key': 'fictional-start-key-123'}
        self.assertEqual(self.call('POST', '/api/v1/assessment-runs', request, csrf=False)[0], 403)
        status, data = self.call('POST', '/api/v1/assessment-runs', request)
        self.assertEqual(status, 200)
        run_id = data['run']['id']
        self.assertEqual(self.call('POST', '/api/v1/assessment-runs', request)[1]['run']['id'], run_id)
        self.assertEqual(self.call('GET', '/api/v1/assessment-runs/' + run_id)[1]['items'][0]['id'], 'synthetic-item-1')
        response = {'item_id': 'synthetic-item-1', 'response': 'fictional response',
                    'assisted': False, 'narration': True, 'revision': 0,
                    'idempotency_key': 'fictional-reply-key-123'}
        malformed = dict(response, response='\ud800')
        self.assertIn(self.call('POST', '/api/v1/assessment-runs/' + run_id + '/responses', malformed)[0], (400, 403))
        status, data = self.call('POST', '/api/v1/assessment-runs/' + run_id + '/responses', response)
        self.assertEqual(status, 200)
        self.assertTrue(data['response']['assisted'])
        self.assertEqual(data['response']['evidence_status'], 'needs_review')
        resumed = self.call('GET', '/api/v1/assessment-runs/' + run_id)[1]
        self.assertEqual((resumed['status'], resumed['revision']), ('active', 1))
        self.assertEqual(self.call('GET', history_path)[1]['runs'][0]['mastery_status'], 'not_assessed')
        self.assertEqual(self.call('GET', '/api/v1/students/synthetic-student-b/assessment-forms')[0], 403)
        with self.app.store._connect() as db:
            db.execute("UPDATE synthetic_assessment_forms SET status='suspended' WHERE form_id='synthetic-form'")
        self.assertEqual(self.call('GET', '/api/v1/assessment-runs/' + run_id)[0], 403)
        self.assertEqual(self.call('POST', '/api/v1/assessment-runs/' + run_id + '/complete',
                                   {'revision': 1, 'idempotency_key': 'fictional-complete-key'})[0], 403)
        self.assertEqual(self.call('GET', history_path)[0], 200)
        trusted.set_synthetic_consent(token, 'synthetic-student-1', False)
        self.assertEqual(self.call('GET', history_path)[0], 403)

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
