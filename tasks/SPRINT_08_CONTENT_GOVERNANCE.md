# Sprint 08 — Content review and version governance (synthetic prototype)

Implemented: immutable `(lesson_id, version)` JSON content, SHA-256 integrity check, staged review, separate author/reviewer, suspension and retirement, audit log, SQLite persistence. `approved_for_prototype` is NOT publication approval for children or real families. A reviewer name beginning `synthetic-` is not verified human identity. The prototype local UI still uses its own fixed demonstration lesson loader; future integration must use the content registry as the sole source for eligible lesson versions and enforce suspension at session creation.

## Next sprint acceptance criteria
- Integrate registry approval with lesson session creation and UI; no separate bypass path.
- Pin immutable version and digest in session history.
- Verify approval identity through production authorization before real use.
- Add accessibility, evidence-source and expert-review fields and review workflows.
- Build Story Vibes invalidation on content version changes.
- Retain synthetic-only guard; do not ingest actual child data.
