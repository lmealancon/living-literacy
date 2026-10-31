# Changelog

## v0.3 — 2026-10-28
- Added machine-readable six-stage lesson candidate schema.
- Added lesson session transition and content publication contracts.
- Added subscription catalog at $9.99 family / $19.99 solo educator.
- Added four-skills adjudication protocol and source inventory template.
- Added automated contract tests and next engineering task.
- Did **not** fabricate missing canonical skill definitions or claim a live application.

## v0.4
Added runnable synthetic-only reference lesson engine, authorization illustration, session transitions, idempotency, response provenance and behavior tests. No real student support.

## v0.5
- Added synthetic-only SQLite persistence and audit trail; token-hash lookup, student/workspace grants, optimistic revisions and durable idempotency.
- Added persistence tests; no production identity or real-child storage.

## v0.6
- Added localhost-only responsive synthetic family UI with session stage progression and practice recording.
- Added HTML escaping and browser-facing synthetic-only warning; four additional unit tests.
- No production auth, real child data, or live AI.

## v0.7
Added synthetic six-stage word-study instructional content, validation and browser display. No real-student use or validated instructional claims.

## v0.8
- Added synthetic lesson version governance registry and 12 tests.
- Explicitly withheld public publishing, production reviewer verification and UI integration.

## Synthetic guardian foundation (development)
- Added `prototype/synthetic_auth.py` and `tests/test_synthetic_auth.py` for synthetic parent credential enrollment, login, expiring sessions, rotation and logout.
- Extended `prototype/persistent_store.py` with simulated guardian relationships, purpose-specific consent checks and minimal synthetic profile creation/read; added `tests/test_guardian_profiles.py`.
- Verification: `python3 -m unittest discover -s tests -q` passed 72 tests; `python3 scripts/validate_registry.py` passed manifest checks and reported the expected missing canonical definitions.
- Existing databases lack simulated authority records and fail closed until separately migrated. Bootstrap tokens are demo fixtures. The local UI remains a shared-token demo and does not provide parent login or profile management. No real identity verification, guardian authority or legal consent is implemented. Synthetic data only; independent security/privacy review and production decisions remain required.
- Next bounded task: design and review migration and browser integration without weakening the authorization boundary.

## Local demo usability
- `prototype/local_web.py`: allow a new synthetic lesson after completing or abandoning the current demo; prior session and audit remain in the temporary store until the demo stops.
- `tests/test_local_web.py`: test completing and restarting through the request handler; `python3 -m unittest discover -s tests -q` passed 73 tests. Network socket binding is unavailable in this sandbox, so the handler test runs in process.
- The demo still uses one shared synthetic account and an ephemeral database, with no real authentication or multi-user isolation. It remains local-only. The next bounded task is a reviewed hosting and identity design before any real-data launch.
