"""Local, unreviewed conversation experiment for synthetic adult testing only.

This is not a child-facing service or a safety boundary. The operator must run
a separately installed model and must not enter real student information.
Nothing in this module stores or logs the prompt, history, or response.
"""
import http.client
import json
import re
import threading

from prototype.companion_ai import _MODEL_SLOT
from prototype.lesson_engine import PolicyError


_MODEL_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
_SYSTEM = (
    'You are a reading companion for a fictional adult software demonstration. '
    'Offer brief, friendly reading-related explanations or suggestions. '
    'Say when you are unsure. Do not claim to assess, diagnose, or establish '
    'reading level or mastery. Do not ask for personal details. '
    'This is not reviewed instruction and is not for a child.'
)
_MAX_HISTORY = 6
_MAX_INPUT_BYTES = 3000
_MAX_RESPONSE_BYTES = 16384
_CALLER_TIMEOUT_SECONDS = 45


def _valid_text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        return False
    try:
        value.encode('utf-8', 'strict')
    except UnicodeError:
        return False
    return not any(ord(char) < 32 and char not in '\n\t' for char in value)


def _validate_input(message, history):
    if not _valid_text(message, 400) or not isinstance(history, list) or len(history) > _MAX_HISTORY or len(history) % 2:
        raise PolicyError('COMPANION_UNAVAILABLE')
    contents = [message]
    for index, item in enumerate(history):
        expected = 'user' if index % 2 == 0 else 'assistant'
        if (not isinstance(item, dict) or set(item) != {'role', 'content'}
                or item['role'] != expected
                or not _valid_text(item['content'], 400 if expected == 'user' else 1200)):
            raise PolicyError('COMPANION_UNAVAILABLE')
        contents.append(item['content'])
    if sum(len(content.encode('utf-8')) for content in contents) > _MAX_INPUT_BYTES:
        raise PolicyError('COMPANION_UNAVAILABLE')
    # Make an independent copy; a caller cannot change the request mid-flight.
    return [{'role': item['role'], 'content': item['content']} for item in history]


class LocalSyntheticConversation:
    """Stateless, opt-in conversation using a loopback Ollama-compatible API.

    Both the user message and model reply are untrusted, unreviewed text. A
    local provider may itself log or forward requests. Adults must use only
    fictional test information; input validation cannot detect personal data.
    """
    def __init__(self, *, enabled=False, model='llama3.2:1b', port=11434):
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('invalid local model port')
        if not isinstance(model, str) or not _MODEL_PATTERN.fullmatch(model):
            raise ValueError('invalid model name')
        self.enabled = enabled
        self.model = model
        self.port = port

    def reply(self, message, history):
        if not self.enabled:
            raise PolicyError('COMPANION_UNAVAILABLE')
        prior = _validate_input(message, history)
        if not _MODEL_SLOT.acquire(blocking=False):
            raise PolicyError('COMPANION_UNAVAILABLE')
        results = []
        finished = threading.Event()

        def run():
            try:
                results.append(self._reply_from_model(message, prior))
            except Exception:
                pass  # Do not log input, generated text, or provider errors.
            finally:
                _MODEL_SLOT.release()
                finished.set()

        try:
            threading.Thread(target=run, daemon=True).start()
        except RuntimeError:
            _MODEL_SLOT.release()
            raise PolicyError('COMPANION_UNAVAILABLE') from None
        if not finished.wait(_CALLER_TIMEOUT_SECONDS) or not results:
            raise PolicyError('COMPANION_UNAVAILABLE')
        return {'text': results[0], 'mode': 'local_ai_unreviewed'}

    def _reply_from_model(self, message, history):
        messages = [{'role': 'system', 'content': _SYSTEM}, *history,
                    {'role': 'user', 'content': message}]
        payload = json.dumps({'model': self.model, 'messages': messages,
                              'stream': False,
                              'options': {'num_predict': 180, 'temperature': 0.4}},
                             ensure_ascii=False).encode('utf-8')
        connection = None
        try:
            # Direct loopback HTTP: no environment proxy or redirect handling.
            connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
            connection.request('POST', '/api/chat', body=payload,
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError('unexpected model status')
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError('response too large')
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict) or data.get('done') is not True or not isinstance(data.get('message'), dict):
                raise ValueError('incomplete response')
            text = data['message'].get('content')
            if not _valid_text(text, 1200) or len(text.encode('utf-8')) > 3000:
                raise ValueError('invalid response')
            return text.strip()
        except (OSError, http.client.HTTPException, ValueError, TypeError, RecursionError):
            raise PolicyError('COMPANION_UNAVAILABLE') from None
        finally:
            if connection is not None:
                connection.close()
