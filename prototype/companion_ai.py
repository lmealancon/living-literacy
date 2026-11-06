"""Optional, constrained local-model adapter for synthetic adult experiments.

There is no microphone, arbitrary input, student context, conversation history,
or learner-facing integration. The model selects only from fixed phrases.
"""
import http.client
import json
import re
import threading

from prototype.lesson_engine import PolicyError


_CHOICES = {
    'hello': ('Hello! It is nice to meet you.', 'Hello! I am happy to be here.'),
    'encourage': ('Take your time. We can keep going together.', 'We can try again together.'),
    'break': ('It is okay to take a break.', 'We can pause and come back later.'),
}
_MAX_RESPONSE_BYTES = 16384
_MODEL_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
_MODEL_SLOT = threading.BoundedSemaphore(1)
_CALLER_TIMEOUT_SECONDS = 5


class LocalAICompanion:
    """Make bounded fixed-prompt requests to a loopback Ollama-compatible API.

    Explicit opt-in is necessary. The loopback address and API route cannot
    be configured; no redirect, proxy, free text, or student data is accepted.
    Generated output is rejected unless it exactly matches a fixed phrase.
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

    def reply(self, action_id):
        if not self.enabled or not isinstance(action_id, str) or action_id not in _CHOICES:
            raise PolicyError('COMPANION_UNAVAILABLE')
        if not _MODEL_SLOT.acquire(blocking=False):
            raise PolicyError('COMPANION_UNAVAILABLE')
        result = []
        finished = threading.Event()

        def run():
            try:
                result.append(self._reply_from_model(action_id))
            except Exception:
                # Do not expose the model's output, endpoint or internal errors.
                pass
            finally:
                _MODEL_SLOT.release()
                finished.set()

        try:
            threading.Thread(target=run, daemon=True).start()
        except RuntimeError:
            _MODEL_SLOT.release()
            raise PolicyError('COMPANION_UNAVAILABLE') from None
        if not finished.wait(_CALLER_TIMEOUT_SECONDS) or not result:
            raise PolicyError('COMPANION_UNAVAILABLE')
        return result[0]

    def _reply_from_model(self, action_id):
        choices = _CHOICES[action_id]
        prompt = (
            'Choose exactly one of the following two fixed demo phrases. '
            'Return the chosen phrase exactly, with no extra text.\n'
            f'1. {choices[0]}\n2. {choices[1]}'
        )
        payload = json.dumps({
            'model': self.model, 'prompt': prompt, 'stream': False,
            'options': {'num_predict': 48},
        }).encode('utf-8')
        connection = None
        try:
            # http.client does not consult HTTP proxy settings or follow redirects.
            connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
            connection.request('POST', '/api/generate', body=payload,
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError('unexpected model status')
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError('model response too large')
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict) or data.get('done') is not True:
                raise ValueError('incomplete model response')
            result = data.get('response')
            if not isinstance(result, str) or result.strip() not in choices:
                raise ValueError('unapproved output')
            return {'text': result.strip(), 'mode': 'local_ai_synthetic'}
        except (OSError, http.client.HTTPException, ValueError, TypeError, RecursionError):
            raise PolicyError('COMPANION_UNAVAILABLE') from None
        finally:
            if connection is not None:
                connection.close()
