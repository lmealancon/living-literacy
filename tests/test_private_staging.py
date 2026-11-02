"""Private staging boundary tests; not evidence of a secured gateway or production readiness."""
import json
import secrets
import tempfile
import unittest
from io import BytesIO
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from prototype import app_server

ORIGIN = 'https://literacy.example.org'
SECRET = 'fictional-gateway-secret-for-testing-only'


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'synthetic.sqlite'
        app_server.bootstrap(self.db, 'synthetic-parent-1', 'fictional-demo-password')
        self.app = app_server.App(self.db, staging_origin=ORIGIN, proxy_secret=SECRET)
        self.handler = app_server.make_handler(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, method='GET', path='/', *, host='literacy.example.org', origin=ORIGIN,
                gateway=SECRET, peer='127.0.0.1', body=None, cookie='', csrf=''):
        h = self.handler.__new__(self.handler)
        h.server = SimpleNamespace(server_port=8765)
        h.client_address = (peer, 12345)
        h.path = path
        h.headers = {'Host': host, 'Origin': origin, 'X-Living-Literacy-Gateway': gateway,
                     'Content-Type': 'application/json', 'Cookie': cookie,
                     'X-CSRF-Token': csrf}
        data = json.dumps(body).encode() if body is not None else b''
        h.headers['Content-Length'] = str(len(data))
        h.rfile, h.wfile = BytesIO(data), BytesIO()
        result = {}
        h.send_response = lambda status: result.update(status=status)
        h.send_header = lambda key, value: result.update({key: value})
        h.end_headers = lambda: None
        getattr(h, 'do_' + method)()
        return result, h.wfile.getvalue()

    def test_origin_requires_https_exact_dns_and_valid_secret(self):
        for origin in ['http://literacy.example.org', 'https://literacy.example.org/',
                       'https://user@literacy.example.org', 'https://literacy.example.org?x=1',
                       'https://127.0.0.1', 'https://literacy.example.org:65536',
                       'https://bad..example.org', 'https://LOCAL.example.org']:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                app_server.validate_staging_config(origin, SECRET)
        with self.assertRaises(ValueError):
            app_server.validate_staging_config(ORIGIN, 'short')
        for invalid in ('a' * 257, 'a' * 31 + ' ', 'a' * 31 + '"',
                        'a' * 31 + '$', 'a' * 31 + ':', 'a' * 31 + 'é'):
            with self.subTest(secret='invalid syntax or length'), self.assertRaises(ValueError):
                app_server.validate_staging_config(ORIGIN, invalid)
        self.assertEqual(app_server.validate_staging_config(ORIGIN, secrets.token_urlsafe(32)),
                         'literacy.example.org')
        self.assertEqual(app_server.validate_staging_config(ORIGIN, 'A' * 30 + '-_'),
                         'literacy.example.org')
        self.assertEqual(app_server.validate_staging_config('https://literacy.example.org:8443', SECRET),
                         'literacy.example.org:8443')

    def test_gateway_requires_loopback_and_secret_on_every_request(self):
        self.assertEqual(self.request()[0]['status'], 200)
        for params in [{'gateway': ''}, {'gateway': 'wrong'}, {'gateway': 'é' * 32},
                       {'peer': '203.0.113.12'}, {'host': 'evil.example.org'}]:
            with self.subTest(params=params):
                self.assertEqual(self.request(**params)[0]['status'], 403)

    def test_login_checks_https_origin_and_sets_secure_cookie(self):
        payload = {'identity': 'synthetic-parent-1', 'passphrase': 'fictional-demo-password'}
        self.assertEqual(self.request('POST', '/api/login', body=payload, origin='http://literacy.example.org')[0]['status'], 403)
        self.assertEqual(self.request('POST', '/api/login', body=payload, origin='https://evil.example.org')[0]['status'], 403)
        result, _ = self.request('POST', '/api/login', body=payload)
        self.assertEqual(result['status'], 200)
        self.assertIn('Secure', result['Set-Cookie'])
        self.assertIn('HttpOnly', result['Set-Cookie'])
        self.assertIn('SameSite=Strict', result['Set-Cookie'])

    def test_authenticated_stage_and_withdrawal_still_enforced(self):
        payload = {'identity': 'synthetic-parent-1', 'passphrase': 'fictional-demo-password'}
        headers, body = self.request('POST', '/api/login', body=payload)
        cookie = headers['Set-Cookie'].split(';')[0]
        csrf = json.loads(body)['csrf']
        start = {'student_id': 'synthetic-student-1', 'lesson_id': 'synthetic-lesson-word-study',
                 'version': 'demo-1', 'idempotency_key': 'staging-fictional-key-123'}
        headers, body = self.request('POST', '/api/sessions', body=start, cookie=cookie, csrf=csrf)
        self.assertEqual(headers['status'], 201)
        sid = json.loads(body)['session']['session_id']
        action = {'action': 'activate', 'revision': 0}
        self.assertEqual(self.request('POST', '/api/sessions/' + sid + '/action', body=action,
                                      cookie=cookie, csrf='')[0]['status'], 403)
        self.app.store.content_registry().transition('synthetic-lesson-word-study', 'demo-1',
                                                     'suspend', 'synthetic-reviewer', 'withdrawn')
        self.assertEqual(self.request('POST', '/api/sessions/' + sid + '/action', body=action,
                                      cookie=cookie, csrf=csrf)[0]['status'], 403)
        self.assertEqual(self.request('GET', '/api/lessons/synthetic-lesson-word-study/demo-1',
                                      cookie=cookie)[0]['status'], 403)

    def test_staging_is_explicit_and_listener_remains_loopback(self):
        with patch('sys.argv', ['app_server', '--db', str(self.db), '--private-staging-origin', ORIGIN]), \
             patch.dict('os.environ', {'LIVING_LITERACY_STAGING_PROXY_SECRET': SECRET}), \
             patch('builtins.print'), patch.object(app_server, 'ThreadingHTTPServer') as server:
            app_server.main()
            self.assertEqual(server.call_args.args[0], ('127.0.0.1', 8765))

    def test_staging_rejects_missing_gateway_secret_and_wider_container_listener(self):
        with patch('sys.argv', ['app_server', '--db', str(self.db), '--private-staging-origin', ORIGIN]), \
             patch.dict('os.environ', {}, clear=True), patch('sys.stderr', new_callable=StringIO), self.assertRaises(SystemExit):
            app_server.main()
        with patch('sys.argv', ['app_server', '--db', str(self.db), '--private-staging-origin', ORIGIN, '--container-demo']), \
             patch.dict('os.environ', {'LIVING_LITERACY_STAGING_PROXY_SECRET': SECRET}), patch('sys.stderr', new_callable=StringIO), self.assertRaises(SystemExit):
            app_server.main()


if __name__ == '__main__':
    unittest.main()
