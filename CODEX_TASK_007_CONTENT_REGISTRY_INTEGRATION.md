# Task 007 — Approved content integration (prototype completed)

- Store session-start authorization against `content_versions` with immutable version and SHA-256 integrity.
- Pin source content digest for new session audit.
- Disable direct approved-lesson insertion shortcut.
- Load browser instructional content only through approved registry access.
- Preserve historical session metadata when content is suspended; block new starts and browser content retrieval.
- Add six integration tests for lifecycle and tamper handling.

**Status:** Implemented in synthetic Python reference prototype. 56 tests passing as of v0.9. Not production-ready.

**Follow-up task:** Enforce suspension across all session write paths, add content snapshot/read policy for authorized historical audits, formal migrations, authenticated reviewer identity, verified approvals, and child privacy review.
