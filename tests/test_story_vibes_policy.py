"""Synthetic narration policy; no test constitutes real review or publication."""
import unittest
from dataclasses import replace

from prototype.lesson_engine import PolicyError
from prototype.story_vibes_policy import (
    SyntheticSource, SyntheticScript, SyntheticAudio, digest_bytes,
    evaluate_synthetic_playback,
)


class StoryVibesPolicyTests(unittest.TestCase):
    def setUp(self):
        self.source_text = 'A synthetic passage.'
        self.script_text = self.source_text
        self.audio_bytes = b'fictional-audio-fixture'
        self.source = SyntheticSource('synthetic-source', '1', self.source_text,
                                      digest_bytes(self.source_text.encode()), 'approved_for_prototype')
        self.script = SyntheticScript(
            'synthetic-script', '1', self.source.source_id, self.source.version, self.source.digest,
            'Read Exactly', 'Reading Coach', self.script_text, digest_bytes(self.script_text.encode()),
            'approved_for_prototype', 'synthetic-author', 'synthetic-reviewer', True)
        self.audio = SyntheticAudio(
            'synthetic-asset', '1', self.script.script_id, self.script.version, self.script.digest,
            self.audio_bytes, digest_bytes(self.audio_bytes), 'approved_for_prototype',
            'synthetic-producer', 'synthetic-audio-reviewer', self.script_text, 'Fictional caption')

    def evaluate(self, source=None, script=None, audio=None, mode='Read Exactly', style='Reading Coach'):
        return evaluate_synthetic_playback(source or self.source, script or self.script,
                                           audio or self.audio, mode=mode, style=style)

    def assert_denied(self, **kwargs):
        with self.assertRaisesRegex(PolicyError, 'NARRATION_UNAVAILABLE'):
            self.evaluate(**kwargs)

    def test_approved_exact_playback_reports_assistance_not_independent_evidence(self):
        result = self.evaluate()
        self.assertTrue(result['audio_or_modeling'])
        self.assertFalse(result['independent_decoding_evidence_eligible'])
        self.assertEqual(result['source_version'], '1')

    def test_withdrawal_at_each_level_denies(self):
        for status in ('suspended', 'retired', 'draft', 'in_review'):
            with self.subTest(status=status):
                self.assert_denied(source=replace(self.source, status=status))
                self.assert_denied(script=replace(self.script, status=status))
                self.assert_denied(audio=replace(self.audio, status=status))

    def test_same_author_cannot_approve_or_skip_review(self):
        self.assert_denied(script=replace(self.script, reviewer=self.script.author))
        self.assert_denied(script=replace(self.script, fidelity_reviewed=False))
        self.assert_denied(audio=replace(self.audio, reviewer=self.audio.author))
        self.assert_denied(audio=replace(self.audio, reviewer='real-reviewer'))

    def test_changed_source_or_version_invalidates_descendants(self):
        self.assert_denied(source=replace(self.source, version='2'))
        self.assert_denied(source=replace(self.source, text='Changed source'))
        self.assert_denied(script=replace(self.script, source_digest='bad'))
        self.assert_denied(script=replace(self.script, version='2'))
        self.assert_denied(audio=replace(self.audio, script_digest='bad'))

    def test_read_exactly_must_equal_source_even_if_hashes_match_changed_script(self):
        altered = 'A different synthetic passage.'
        script = replace(self.script, text=altered, digest=digest_bytes(altered.encode()))
        audio = replace(self.audio, script_digest=script.digest, transcript=altered)
        self.assert_denied(script=script, audio=audio)

    def test_reviewed_retelling_is_labeled_and_not_treated_as_verbatim(self):
        text = 'A fictional retelling.'
        script = replace(self.script, mode='Story Vibes', style='The Tea', text=text,
                         digest=digest_bytes(text.encode()))
        audio = replace(self.audio, script_digest=script.digest, transcript=text)
        result = self.evaluate(script=script, audio=audio, mode='Story Vibes', style='The Tea')
        self.assertEqual(result['mode'], 'Story Vibes')
        self.assert_denied(script=script, audio=audio, mode='Read Exactly', style='The Tea')

    def test_unknown_styles_and_unapproved_modes_denied(self):
        self.assert_denied(style='Impersonation')
        self.assert_denied(mode='Chat')
        self.assert_denied(style='The Tea')

    def test_tampered_audio_or_accessibility_text_denied(self):
        self.assert_denied(audio=replace(self.audio, data=b'changed'))
        self.assert_denied(audio=replace(self.audio, transcript='incorrect transcript'))
        self.assert_denied(audio=replace(self.audio, captions=None))

    def test_real_or_empty_source_identifier_denied(self):
        self.assert_denied(source=replace(self.source, source_id='child-1'))
        self.assert_denied(source=replace(self.source, source_id='synthetic-'))


if __name__ == '__main__':
    unittest.main()
