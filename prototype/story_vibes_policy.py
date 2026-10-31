"""Synthetic-only playback eligibility policy, not an audio server or real review.

This pure boundary must be called only after server-side identity, relationship,
purpose and consent checks. A playback service must record narration exposure
atomically before serving bytes; this module does not authorize or serve audio.
"""
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional

from prototype.lesson_engine import PolicyError

STYLES = frozenset({'The Tea', 'Bro, Listen', 'Movie Mode', 'Reading Coach'})
MODES = frozenset({'Read Exactly', 'Story Vibes'})


def digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


@dataclass(frozen=True)
class SyntheticSource:
    source_id: str
    version: str
    text: str
    digest: str
    status: str


@dataclass(frozen=True)
class SyntheticScript:
    script_id: str
    version: str
    source_id: str
    source_version: str
    source_digest: str
    mode: str
    style: str
    text: str
    digest: str
    status: str
    author: str
    reviewer: str
    # A simulated review record, never evidence of real editorial approval.
    fidelity_reviewed: bool


@dataclass(frozen=True)
class SyntheticAudio:
    asset_id: str
    version: str
    script_id: str
    script_version: str
    script_digest: str
    data: bytes
    digest: str
    status: str
    author: str
    reviewer: str
    transcript: str
    captions: Optional[str]


def _synthetic(value):
    return isinstance(value, str) and value.startswith('synthetic-') and len(value) > len('synthetic-')


def _reviewed(author, reviewer):
    return _synthetic(author) and _synthetic(reviewer) and author != reviewer


def evaluate_synthetic_playback(source, script, audio, *, mode, style):
    """Return exposure metadata only for intact, simulated approved records.

    Raises the same policy error for missing, withdrawn, unreviewed, mismatched,
    inaccessible or corrupt records. Actual bytes are never returned here.
    Caller must independently authorize and log exposure before playback.
    """
    try:
        eligible = (
            isinstance(source, SyntheticSource)
            and isinstance(script, SyntheticScript)
            and isinstance(audio, SyntheticAudio)
            and all(_synthetic(x) for x in (source.source_id, script.script_id, audio.asset_id))
            and all(isinstance(x, str) and bool(x.strip()) for x in (source.version, script.version, audio.version))
            and mode in MODES and style in STYLES
            and script.mode == mode and script.style == style
            and source.status == 'approved_for_prototype'
            and script.status == 'approved_for_prototype'
            and audio.status == 'approved_for_prototype'
            and _reviewed(script.author, script.reviewer)
            and _reviewed(audio.author, audio.reviewer)
            and script.fidelity_reviewed is True
            and isinstance(source.text, str) and bool(source.text.strip())
            and isinstance(script.text, str) and bool(script.text.strip())
            and (mode != 'Read Exactly' or script.text == source.text)
            and (script.source_id, script.source_version) == (source.source_id, source.version)
            and script.source_digest == source.digest == digest_bytes(source.text.encode('utf-8'))
            and (audio.script_id, audio.script_version) == (script.script_id, script.version)
            and audio.script_digest == script.digest == digest_bytes(script.text.encode('utf-8'))
            and isinstance(audio.data, bytes) and bool(audio.data)
            and audio.digest == digest_bytes(audio.data)
            and isinstance(audio.transcript, str) and audio.transcript == script.text
            and isinstance(audio.captions, str) and bool(audio.captions.strip())
        )
    except (AttributeError, TypeError, ValueError, UnicodeError):
        eligible = False
    if not eligible:
        raise PolicyError('NARRATION_UNAVAILABLE')
    # Exposure cannot count as independent decoding evidence; recording is the caller's responsibility.
    return {'audio_or_modeling': True, 'independent_decoding_evidence_eligible': False,
            'source_version': source.version, 'script_version': script.version,
            'asset_version': audio.version, 'mode': mode, 'style': style}
