"""Scripted, offline companion fixtures for adult-only experiments.

This is not AI or speech recognition and accepts no arbitrary user input. It
does not authorize, assess, or interact with a learner, lesson, or student
record. Its strings are unreviewed synthetic demonstration material.
"""
from types import MappingProxyType
from typing import Protocol

from prototype.lesson_engine import PolicyError


class CompanionProvider(Protocol):
    """Future adapter shape; conformance is not a privacy or safety review."""

    def reply(self, action_id: str) -> str:
        """Respond to a fixed demonstration action, never a child transcript."""
        ...


_SCRIPTS = MappingProxyType({
    'hello': 'Hello! I am here with you for this activity.',
    'encourage': 'Take your time. We can keep going together.',
    'break': 'It is okay to take a break and come back when you are ready.',
})


class SyntheticFixtureCompanionProvider:
    """Fixed demonstration replies; no network calls, state, or saved chat."""

    def reply(self, action_id: str) -> str:
        if not isinstance(action_id, str) or action_id not in _SCRIPTS:
            raise PolicyError('COMPANION_UNAVAILABLE')
        return _SCRIPTS[action_id]


class SyntheticCompanionDemo:
    """Disabled unless explicitly enabled by trusted adult test code.

    No provider can be injected or configured here. A future generative or
    voice provider requires a separate safety and privacy design and review.
    """

    def __init__(self, enabled=False):
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean')
        self.enabled = enabled
        self._provider = SyntheticFixtureCompanionProvider()

    def reply(self, action_id):
        if not self.enabled:
            raise PolicyError('COMPANION_UNAVAILABLE')
        return {'text': self._provider.reply(action_id), 'mode': 'scripted_synthetic_fixture'}
