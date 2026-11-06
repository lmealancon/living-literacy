import json
import threading
import unittest
from unittest.mock import patch

from prototype.companion_ai import LocalAICompanion
from prototype.lesson_engine import PolicyError


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.limit = None

    def read(self, size):
        self.limit = size
        return self.body[:size]


class LocalAICompanionTests(unittest.TestCase):
    def test_disabled_and_unknown_action_never_connect(self):
        with patch('prototype.companion_ai.http.client.HTTPConnection') as connect:
            for adapter, action in [(LocalAICompanion(), 'hello'),
                                    (LocalAICompanion(enabled=True), 'arbitrary text'),
                                    (LocalAICompanion(enabled=True), ['hello'])]:
                with self.assertRaises(PolicyError):
                    adapter.reply(action)
            connect.assert_not_called()

    def test_success_only_sends_fixed_prompt_to_loopback_and_returns_allowlist(self):
        response = FakeResponse(json.dumps({'response': 'Hello! It is nice to meet you.', 'done': True}).encode())
        with patch('prototype.companion_ai.http.client.HTTPConnection') as connect:
            connect.return_value.getresponse.return_value = response
            result = LocalAICompanion(enabled=True, model='local:test', port=11434).reply('hello')
            connect.assert_called_once_with('127.0.0.1', 11434, timeout=3)
            args, kwargs = connect.return_value.request.call_args
            self.assertEqual(args, ('POST', '/api/generate'))
            request = json.loads(kwargs['body'])
            self.assertEqual(request['model'], 'local:test')
            self.assertFalse(request['stream'])
            self.assertNotIn('student', kwargs['body'].decode().lower())
            self.assertEqual(result, {'text': 'Hello! It is nice to meet you.', 'mode': 'local_ai_synthetic'})
            self.assertEqual(response.limit, 16385)
            connect.return_value.close.assert_called_once()

    def test_rejects_redirects_bad_json_oversize_incomplete_and_unapproved_text(self):
        bad = [FakeResponse(b'{}', 302), FakeResponse(b'{'), FakeResponse(b'\xff'),
               FakeResponse(b'x' * 16385), FakeResponse(b'{"response":"Hello! It is nice to meet you.","done":false}'),
               FakeResponse(b'{"response":"Here is unsafe or unreviewed text.","done":true}')]
        for response in bad:
            with self.subTest(response=response.body[:100], status=response.status):
                with patch('prototype.companion_ai.http.client.HTTPConnection') as connect:
                    connect.return_value.getresponse.return_value = response
                    with self.assertRaisesRegex(PolicyError, 'COMPANION_UNAVAILABLE'):
                        LocalAICompanion(enabled=True).reply('hello')
                    connect.return_value.close.assert_called_once()

    def test_failure_does_not_leak_provider_error(self):
        with patch('prototype.companion_ai.http.client.HTTPConnection', side_effect=OSError('private provider detail')):
            with self.assertRaisesRegex(PolicyError, '^COMPANION_UNAVAILABLE$'):
                LocalAICompanion(enabled=True).reply('hello')

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({'enabled': 1}, {'port': True}, {'port': 0}, {'port': 65536},
                       {'model': 'example.com/model'}, {'model': 'model\nheader'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LocalAICompanion(**kwargs)

    def test_busy_and_caller_timeout_fail_closed(self):
        entered = threading.Event()
        finish = threading.Event()
        adapter = LocalAICompanion(enabled=True)

        def slow(_):
            entered.set()
            finish.wait(2)
            return {'text': 'Hello! It is nice to meet you.', 'mode': 'local_ai_synthetic'}

        try:
            with patch.object(adapter, '_reply_from_model', side_effect=slow), \
                 patch('prototype.companion_ai._CALLER_TIMEOUT_SECONDS', 0.03):
                with self.assertRaises(PolicyError):
                    adapter.reply('hello')
                self.assertTrue(entered.is_set())
                with self.assertRaises(PolicyError):
                    adapter.reply('hello')
        finally:
            finish.set()
            # Wait for the worker to release the process-wide slot before other tests.
            from prototype.companion_ai import _MODEL_SLOT
            self.assertTrue(_MODEL_SLOT.acquire(timeout=2))
            _MODEL_SLOT.release()


if __name__ == '__main__':
    unittest.main()
