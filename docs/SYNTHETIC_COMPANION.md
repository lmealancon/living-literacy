# Synthetic companion fixture

`prototype/synthetic_companion.py` is an offline, fixed-response fixture for
adult testing. `SyntheticCompanionDemo()` is disabled; trusted test code may
construct `SyntheticCompanionDemo(enabled=True)` and call `reply()` with one of
the fixed action IDs `hello`, `encourage`, or `break`. It accepts no arbitrary
text, does not send data to a provider, does not collect audio, and stores no
conversation. The returned mode is explicitly `scripted_synthetic_fixture`.

The `CompanionProvider` protocol is a preliminary shape, not a dynamic plugin
loader or approval to connect any outside service. It is not a real AI model.
The fixture is not associated with lessons, students, identities or progress
and must not be connected to real learners. No speech playback or assistance
tracking is implemented by this module. Before any actual child-facing AI,
speech or transcription, resolve the existing privacy, consent, provider,
content, safety, accessibility and independent review gates described in
`docs/AI_AUDIO_DEVELOPMENT_PLAN.md` and `specs/RELEASE_GATES.md`.
