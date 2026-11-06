"""Synthetic-only narration route contract; no real reviewed audio is supplied."""
import io
import json
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from prototype.app_server import App, bootstrap, make_handler
from prototype.instructional_content import CONTENT_PATH
from prototype.story_vibes_policy import SyntheticAudio, SyntheticScript, SyntheticSource, digest_bytes
from prototype.synthetic_auth import SyntheticParentAuth


def silent_fixture():
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x00\x00' * 800)
    return out.getvalue()


class NarrationHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'demo.sqlite'
        bootstrap(self.db, 'synthetic-parent-1', 'fictional-demo-password')
        self.app = App(self.db, synthetic_audio_enabled=True)
        self.handler = make_handler(self.app)
        self.cookie = ''
        self.csrf = ''

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, method, path, data=None, *, csrf=True, origin=True):
        request = self.handler.__new__(self.handler)
        request.server = SimpleNamespace(server_port=8765)
        request.path = path
        request.headers = {'Host': '127.0.0.1:8765', 'Cookie': self.cookie,
                           'Content-Type': 'application/json'}
        if origin:
            request.headers['Origin'] = 'http://127.0.0.1:8765'
        if csrf:
            request.headers['X-CSRF-Token'] = self.csrf
        body = json.dumps(data).encode() if data is not None else b''
        request.headers['Content-Length'] = str(len(body))
        request.rfile, request.wfile = BytesIO(body), BytesIO()
        headers = {}
        request.send_response = lambda status: headers.update(status=status)
        request.send_header = lambda key, value: headers.update({key: value})
        request.end_headers = lambda: None
        getattr(request, 'do_' + method)()
        if 'Set-Cookie' in headers:
            self.cookie = headers['Set-Cookie'].split(';')[0]
        return headers, request.wfile.getvalue()

    def session_and_fixture(self):
        headers, body = self.call('POST', '/api/login',
                                  {'identity': 'synthetic-parent-1', 'passphrase': 'fictional-demo-password'})
        self.assertEqual(headers['status'], 200)
        self.csrf = json.loads(body)['csrf']
        headers, body = self.call('POST', '/api/sessions', {'student_id': 'synthetic-student-1',
            'lesson_id': 'synthetic-lesson-word-study', 'version': 'demo-1',
            'idempotency_key': 'synthetic-audio-http-key'})
        self.assertEqual(headers['status'], 201)
        sid = json.loads(body)['session']['session_id']
        headers, _ = self.call('POST', f'/api/sessions/{sid}/action', {'action': 'activate', 'revision': 0})
        self.assertEqual(headers['status'], 200)
        text = json.loads(CONTENT_PATH.read_text())['stages'][0]['instruction']
        source = SyntheticSource('synthetic-lesson-word-study', 'demo-1', text,
                                 digest_bytes(text.encode()), 'approved_for_prototype')
        script = SyntheticScript('synthetic-script', '1', source.source_id, source.version,
            source.digest, 'Read Exactly', 'Reading Coach', text, digest_bytes(text.encode()),
            'approved_for_prototype', 'synthetic-writer', 'synthetic-reviewer', True)
        data = silent_fixture()
        audio = SyntheticAudio('synthetic-audio', '1', script.script_id, script.version,
            script.digest, data, digest_bytes(data), 'approved_for_prototype',
            'synthetic-producer', 'synthetic-audio-reviewer', text, 'Synthetic captions')
        self.app.synthetic_narration.add_fixture(source, script, audio, 0)
        return sid, data

    def test_default_is_disabled_even_for_valid_login(self):
        sid, _ = self.session_and_fixture()
        self.app.synthetic_narration = None
        headers, _ = self.call('POST', f'/api/sessions/{sid}/narration',
            {'asset_id': 'synthetic-audio', 'asset_version': '1', 'revision': 1})
        self.assertEqual(headers['status'], 403)
        self.assertEqual(App(self.db).synthetic_narration, None)

    def test_authorization_csrf_stale_and_audit(self):
        sid, audio = self.session_and_fixture()
        path = f'/api/sessions/{sid}/narration'
        body = {'asset_id': 'synthetic-audio', 'asset_version': '1', 'revision': 1}
        self.assertEqual(self.call('POST', path, body, csrf=False)[0]['status'], 403)
        self.assertEqual(self.call('POST', path, body, origin=False)[0]['status'], 403)
        headers, payload = self.call('POST', path, body)
        self.assertEqual(headers['status'], 200)
        self.assertEqual(headers['Content-Type'], 'audio/wav')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Living-Literacy-Revision'], '2')
        self.assertEqual(payload, audio)
        self.assertEqual(self.call('POST', path, body)[0]['status'], 409)
        self.assertEqual(len(self.app.store.get_session(self.cookie.split('=', 1)[1], sid).narration_exposures), 1)
        self.cookie = ''
        self.assertEqual(self.call('POST', path, body)[0]['status'], 403)

    def test_missing_withdrawn_and_tampered_assets_fail_closed(self):
        sid, _ = self.session_and_fixture()
        path = f'/api/sessions/{sid}/narration'
        body = {'asset_id': 'synthetic-missing', 'asset_version': '1', 'revision': 1}
        self.assertEqual(self.call('POST', path, body)[0]['status'], 403)
        body['asset_id'] = 'synthetic-audio'
        with self.app.store._connect() as db:
            db.execute('UPDATE synthetic_narration_fixtures SET audio=?', (b'tampered',))
        self.assertEqual(self.call('POST', path, body)[0]['status'], 403)
        self.app.store.content_registry().transition('synthetic-lesson-word-study', 'demo-1',
                                                     'suspend', 'synthetic-reviewer', 'withdrawn')
        self.assertEqual(self.call('POST', path, body)[0]['status'], 403)

    def test_cross_family_denied(self):
        sid, _ = self.session_and_fixture()
        token = self.app.store.provision_synthetic_family('synthetic-family-b', 'synthetic-parent-b', 'synthetic-student-b')
        SyntheticParentAuth(self.app.store).enroll(token, 'fictional-password-b')
        headers, payload = self.call('POST', '/api/login',
            {'identity': 'synthetic-parent-b', 'passphrase': 'fictional-password-b'})
        self.assertEqual(headers['status'], 200)
        self.csrf = json.loads(payload)['csrf']
        headers, _ = self.call('POST', f'/api/sessions/{sid}/narration',
            {'asset_id': 'synthetic-audio', 'asset_version': '1', 'revision': 1})
        self.assertEqual(headers['status'], 403)

    def test_audio_exposure_cannot_become_independent_decoding_evidence(self):
        sid, _ = self.session_and_fixture()
        path = f'/api/sessions/{sid}/narration'
        body = {'asset_id': 'synthetic-audio', 'asset_version': '1', 'revision': 1}
        self.assertEqual(self.call('POST', path, body)[0]['status'], 200)
        revision = 2
        for _ in range(4):
            headers, _ = self.call('POST', f'/api/sessions/{sid}/action', {'action': 'next', 'revision': revision})
            self.assertEqual(headers['status'], 200)
            revision += 1
        headers, result = self.call('POST', f'/api/sessions/{sid}/action',
            {'action': 'respond', 'revision': revision, 'response': 'fictional', 'assisted': False})
        self.assertEqual(headers['status'], 200)
        response = json.loads(result)['session']['responses'][-1]
        self.assertTrue(response['assistance']['audio_or_modeling'])
        self.assertFalse(response['independent_evidence_eligible'])

    def test_no_fixture_admin_route_is_available(self):
        self.session_and_fixture()
        self.assertEqual(self.call('POST', '/api/narration/fixtures', {'action': 'approve'})[0]['status'], 404)


if __name__ == '__main__':
    unittest.main()
