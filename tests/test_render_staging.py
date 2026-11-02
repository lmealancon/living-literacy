"""Contract tests for configuration only; no live Render or nginx assertion."""
import io
import subprocess
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import Mock, patch
import deploy.render.start as starter
from deploy.render.start import settings, nginx_config, proxy_config


class RenderStagingTests(unittest.TestCase):
    def setUp(self):
        self.env = {'LL_STAGING_ORIGIN': 'https://literacy-stage.onrender.com',
                    'PORT': '10000',
                    'LIVING_LITERACY_STAGING_PROXY_SECRET': 'a' * 40,
                    'LL_GATEWAY_PASSWORD': 'b' * 40,
                    'LL_DEMO_PASSWORD': 'c' * 40}

    def test_validates_explicit_safe_settings(self):
        cfg = settings(self.env)
        self.assertEqual(cfg['host'], 'literacy-stage.onrender.com')
        self.assertEqual(cfg['port'], 10000)

    def test_missing_or_reused_secrets_fail_closed(self):
        for key in ('LIVING_LITERACY_STAGING_PROXY_SECRET', 'LL_GATEWAY_PASSWORD', 'LL_DEMO_PASSWORD'):
            bad = self.env.copy(); del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError): settings(bad)
        bad = self.env.copy(); bad['LL_GATEWAY_PASSWORD'] = bad['LL_DEMO_PASSWORD']
        with self.assertRaises(ValueError): settings(bad)

    def test_rejects_untrusted_origins_and_bad_port(self):
        for origin in ('http://literacy-stage.onrender.com', 'https://evil.com',
                       'https://literacy-stage.onrender.com/extra', 'https://evil.onrender.com:443'):
            bad = self.env.copy(); bad['LL_STAGING_ORIGIN'] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError): settings(bad)
        for port in ('80', '8765', 'not-a-port', '65536'):
            bad = self.env.copy(); bad['PORT'] = port
            with self.subTest(port=port), self.assertRaises(ValueError): settings(bad)

    def test_template_restricts_access_and_replaces_proxy_header(self):
        cfg = settings(self.env)
        config = nginx_config(cfg, '/tmp/ll-test')
        proxy = proxy_config(cfg)
        self.assertIn('auth_basic_user_file /tmp/ll-test/users;', config)
        self.assertIn('limit_req zone=staging_login', config)
        self.assertIn('limit_req zone=staging_all', config)
        self.assertIn('access_log off;', config)
        self.assertIn('proxy_pass http://127.0.0.1:8765;', proxy)
        self.assertIn('proxy_set_header Authorization "";', proxy)
        self.assertIn('proxy_set_header X-Living-Literacy-Gateway ' + 'a' * 40 + ';', proxy)
        self.assertNotIn(self.env['LL_GATEWAY_PASSWORD'], config + proxy)
        self.assertNotIn(self.env['LL_DEMO_PASSWORD'], config + proxy)

    def test_startup_never_passes_passwords_in_child_arguments(self):
        app, nginx = Mock(), Mock()
        app.poll.return_value = 1
        nginx.poll.return_value = None
        digest = SimpleNamespace(stdout='$6$randomsalt$fakehash')
        with patch.dict('os.environ', self.env, clear=True), patch.object(starter, 'bootstrap'), \
             patch.object(starter.signal, 'signal'), \
             patch.object(starter.subprocess, 'run', return_value=digest) as run, \
             patch.object(starter.subprocess, 'Popen', side_effect=[app, nginx]) as popen:
            self.assertEqual(starter.main(), 1)
        all_args = str(run.call_args.args) + str([c.args for c in popen.call_args_list])
        self.assertNotIn(self.env['LL_GATEWAY_PASSWORD'], all_args)
        self.assertNotIn(self.env['LL_DEMO_PASSWORD'], all_args)
        self.assertNotIn(self.env['LIVING_LITERACY_STAGING_PROXY_SECRET'], all_args)
        self.assertEqual(run.call_args.kwargs['input'], self.env['LL_GATEWAY_PASSWORD'] + '\n')
        app_env = popen.call_args_list[0].kwargs['env']
        nginx_env = popen.call_args_list[1].kwargs['env']
        self.assertNotIn('LL_GATEWAY_PASSWORD', app_env)
        self.assertNotIn('LL_DEMO_PASSWORD', app_env)
        self.assertNotIn('LIVING_LITERACY_STAGING_PROXY_SECRET', nginx_env)

    def test_subprocess_failure_does_not_log_credentials(self):
        error = io.StringIO()
        failure = subprocess.CalledProcessError(1, 'sensitive-test-command', stderr=self.env['LL_GATEWAY_PASSWORD'])
        with patch.dict('os.environ', self.env, clear=True), patch.object(starter.signal, 'signal'), \
             patch.object(starter.subprocess, 'run', side_effect=failure), redirect_stderr(error):
            self.assertEqual(starter.main(), 1)
        self.assertNotIn(self.env['LL_GATEWAY_PASSWORD'], error.getvalue())
        self.assertNotIn('sensitive-test-command', error.getvalue())

    def test_rejects_configuration_injection_characters(self):
        for key in ('LIVING_LITERACY_STAGING_PROXY_SECRET', 'LL_GATEWAY_PASSWORD', 'LL_DEMO_PASSWORD'):
            for suffix in (';', '\n', '$', ' ', '"'):
                bad = self.env.copy(); bad[key] = 'a' * 40 + suffix
                with self.subTest(key=key, suffix=suffix), self.assertRaises(ValueError): settings(bad)


if __name__ == '__main__': unittest.main()
