# Sprint 04 — Lesson session reference engine

A runnable **in-memory, synthetic-only** Python reference implementation is included in `prototype/lesson_engine.py`.

## Scope implemented
- Immutable approved lesson-version reference at session creation.
- Synthetic-only guard, scoped actor-to-student authorization **illustration**.
- Idempotent session creation with conflicting-key detection.
- Session state machine and six-stage progression.
- Optimistic revision checks and basic audit event records.
- Assistance provenance and restricted independent-evidence eligibility.
- Completion never changes mastery status.

## Deliberately NOT implemented
- Database persistence, authenticated sessions, guardian verification, real student records, API, production authorization, deletion, security hardening, or validated measurement.
- Assistance eligibility is intentionally conservative and incomplete: future task-specific evidence policies must be reviewed.
- In-memory audit events are not immutable, persistent, or tamper-resistant.

## Run
`python3 -m unittest discover -s tests -v`

## Next bounded Codex task
Translate this reference state machine into a persisted application module **after** approved database, authorization, consent, and privacy contracts exist. Add concurrency, tenant isolation and transaction tests. Do not deploy this prototype to children.
