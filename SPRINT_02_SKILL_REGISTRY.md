# Codex Task 002 — Skill registry infrastructure (synthetic records only)

Prerequisites: Sprint 01 and reviewed database/authorization foundations as appropriate.

## Scope
- Implement a typed skill-record model aligned with `registry/SKILL_RECORD.schema.json`.
- Create immutable versioned skill definitions and explicit status transitions.
- Implement dependency-target checks, cycle detection and safe import rejection.
- Build internal read-only inspection using synthetic fixtures; no student-facing canonical skills.
- Add a domain count comparison report without treating 91 as imported.
- Add authorization for internal draft/review actions and audit transitions.

## Tests
- Reject duplicate skill IDs within the same version.
- Reject missing dependency targets and dependency cycles.
- Reject malformed routine references and invalid statuses.
- Block publication of unreviewed skills.
- Confirm no auto-mastery API or behavior is introduced.
- Confirm both reading strands remain independently addressable.

## Explicit exclusions
Do not fabricate 91 skills; do not infer missing definitions from domain totals; do not resolve the four adjudications automatically; do not import real child data.
