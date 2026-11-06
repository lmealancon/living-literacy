"""Synthetic adults only; mocks never contact an actual model service."""
import json
import threading
import unittest
from unittest.mock import patch

from prototype.companion_conversation import LocalSyntheticConversation
from prototype.lesson_engine import PolicyError


class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status, self.limit = body, status, None

    def read(self, size):
        self.limit = size
        return self.body[:size]


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.adapter = LocalSyntheticConversation(enabled=True, model='local:test')

    def response(self, text):
        return FakeResponse(json.dumps({'done': True, 'message': {'role': 'assistant', 'content': text}}).encode())

    def test_actual_freeform_output_and_prior_turns_use_local_chat_api(self):
        prior = [{'role': 'user', 'content': 'What is a rhyme?'},
                 {'role': 'assistant', 'content': 'Words can rhyme when their endings sound alike.'}]
        answer = 'For example, cat and hat rhyme.'
        response = self.response(answer)
        with patch('prototype.companion_conversation.http.client.HTTPConnection') as connect:
            connect.return_value.getresponse.return_value = response
            result = self.adapter.reply('Can you give another example?', prior)
            connect.assert_called_once_with('127.0.0.1', 11434, timeout=30)
            args, kwargs = connect.return_value.request.call_args
            self.assertEqual(args, ('POST', '/api/chat'))
            body = json.loads(kwargs['body'])
            self.assertEqual(body['messages'][0]['role'], 'system')
            self.assertEqual(body['messages'][1:-1], prior)
            self.assertEqual(body['messages'][-1], {'role': 'user', 'content': 'Can you give another example?'})
            self.assertFalse(body['stream'])
            self.assertEqual(result, {'text': answer, 'mode': 'local_ai_unreviewed'})
            self.assertEqual(response.limit, 16385)
            connect.return_value.close.assert_called_once()

    def test_disabled_or_bad_input_never_contacts_model(self):
        invalid = [('', []), ('x' * 401, []), ('\ud800', []), ('hello', None),
                   ('hello', [{'role': 'user', 'content': 'one'}]),
                   ('hello', [{'role': 'assistant', 'content': 'one'}, {'role': 'user', 'content': 'two'}]),
                   ('hello', [{'role': 'user', 'content': 'one', 'student_id': 'synthetic-1'},
                              {'role': 'assistant', 'content': 'two'}]),
                   ('hello', [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': 'x' * 1201}]),
                   ('hello', [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': 'x'}] * 4),
                   ('🌞' * 400, [{'role': 'user', 'content': '🌞' * 400}, {'role': 'assistant', 'content': 'ok'}])]
        with patch('prototype.companion_conversation.http.client.HTTPConnection') as connect:
            with self.assertRaises(PolicyError):
                LocalSyntheticConversation().reply('hello', [])
            for message, history in invalid:
                with self.subTest(message=repr(message)[:30], history_type=type(history)):
                    with self.assertRaises(PolicyError):
                        self.adapter.reply(message, history)
            connect.assert_not_called()

    def test_bad_model_responses_fail_without_leaking_details(self):
        failures = [FakeResponse(b'{}', 302), FakeResponse(b'{'), FakeResponse(b'\xff'),
                    FakeResponse(b'x' * 16385), FakeResponse(b'{"done":false}'),
                    self.response(''), self.response('x' * 1201),
                    self.response('invisible\x00value')]
        for response in failures:
            with self.subTest(body=response.body[:40]):
                with patch('prototype.companion_conversation.http.client.HTTPConnection') as connect:
                    connect.return_value.getresponse.return_value = response
                    with self.assertRaisesRegex(PolicyError, '^COMPANION_UNAVAILABLE$'):
                        self.adapter.reply('hello', [])
                    connect.return_value.close.assert_called_once()

    def test_connection_failure_and_invalid_config(self):
        with patch('prototype.companion_conversation.http.client.HTTPConnection', side_effect=OSError('private')):
            with self.assertRaisesRegex(PolicyError, '^COMPANION_UNAVAILABLE$'):
                self.adapter.reply('hello', [])
        for config in ({'enabled': 1}, {'port': True}, {'port': 0}, {'port': 65536},
                       {'model': 'http://external'}, {'model': 'model\nheader'}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                LocalSyntheticConversation(**config)

    def test_busy_and_timeout_fail_closed(self):
        entered, release = threading.Event(), threading.Event()

        def slow(*_):
            entered.set()
            release.wait(2)
            return 'delayed'

        try:
            with patch.object(self.adapter, '_reply_from_model', side_effect=slow), \
                 patch('prototype.companion_conversation._CALLER_TIMEOUT_SECONDS', 0.03):
                with self.assertRaises(PolicyError):
                    self.adapter.reply('hello', [])
                self.assertTrue(entered.is_set())
                with self.assertRaises(PolicyError):
                    self.adapter.reply('hello', [])
        finally:
            release.set()
            from prototype.companion_ai import _MODEL_SLOT
            self.assertTrue(_MODEL_SLOT.acquire(timeout=2))
            _MODEL_SLOT.release()


if __name__ == '__main__':
    unittest.main()
