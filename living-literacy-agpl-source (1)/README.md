> **Community Edition direction — work in progress.** This repository is a local, synthetic-data-only prototype. The owner selected AGPL-3.0-only for software and approved the current name and included content for the proposed public release. This local repository has not yet been published. It is not suitable for real student data or public deployment. See [Community architecture](docs/COMMUNITY_ARCHITECTURE.md), [Community roadmap](docs/COMMUNITY_ROADMAP.md), [licensing and content](docs/LICENSING_AND_CONTENT.md), and [development progress](DEVELOPMENT_PROGRESS.md).
>
> The current parent/lesson prototype can be initialized with `python3 -m prototype.app_server --init` and started with `python3 -m prototype.app_server`; it binds to `127.0.0.1` and uses simulated family authority and consent. Run `python3 -m unittest discover -s tests -v` to test. See [operations](docs/OPERATIONS.md) and the [local container guide](CONTAINER_DEMO.md) for limitations and setup. Container build and startup are not yet verified in this environment.


## License and content

The software is offered under the GNU Affero General Public License, version 3 only (AGPL-3.0-only); see [LICENSE](LICENSE). The owner approved using the Living Literacy name and including the current sample content and documents in the proposed public repository. Educational content, other assets and trademarks are separate from software licensing; no separate content or trademark license is specified. See [licensing and content](docs/LICENSING_AND_CONTENT.md).

# Living Literacy — Master Development Package v0.6

**Status: draft architecture / not implemented / not validated.** This is an incremental extension of v0.1, not a complete transcription of the 93 planning phases.

## What changed in v0.2
- Machine-readable twelve-domain manifest with candidate counts (49 word recognition + 42 language comprehension = 91).
- Candidate skill JSON schema and intentionally empty canonical registry.
- Four-issue adjudication worksheet and source import protocol.
- Twelve instructional routine contract stubs.
- Runnable registry manifest and dependency validation script.
- Codex Task 002 (skill registry infrastructure) and initial traceability matrix.

## Quick check
`python3 scripts/validate_registry.py`

## Read order
1. `AGENTS.md` and `specs/PRODUCT_REQUIREMENTS.md`.
2. `docs/DECISION_REGISTER.md` and `registry/SOURCE_IMPORT_PROTOCOL.md`.
3. `registry/DOMAIN_MANIFEST.json` and `registry/SKILL_RECORD.schema.json`.
4. `tasks/SPRINT_01.md` then `tasks/SPRINT_02_SKILL_REGISTRY.md`.

## Commercial planning
Free $0; Family Plus $9.99/month; Solo Educator $19.99/month. School pricing and Solo Educator student limit pending.

**Do not invent the missing 91 complete skill definitions.** Obtain the full prior design source and review before canonical import. No code, vendor selection, expert validation, or production authorization is implied.

## v0.3 additions
`contracts/LESSON_RECORD.schema.json`, `contracts/LESSON_SESSION_STATES.md`, `contracts/CONTENT_PUBLICATION_POLICY.md`, `contracts/PLAN_CATALOG.json`, `registry/SOURCE_INVENTORY_TEMPLATE.csv`, `registry/ADJUDICATION_PROTOCOL.md`, `tests/test_lesson_contract.py`, `tasks/SPRINT_03_LESSON_CONTRACT.md`.

Run checks: `python scripts/validate_registry.py` and `python -m unittest discover -s tests -v`. These test specification invariants, **not** application behavior.

## v0.4 additions
A **runnable synthetic-data-only in-memory Python lesson-session reference engine** in `prototype/lesson_engine.py`, 13 behavior tests in `tests/test_reference_engine.py`, and `tasks/SPRINT_04_REFERENCE_ENGINE.md`. This is NOT a deployed web application or a production-safe student-data service.

## v0.5 synthetic persistence prototype
`prototype/persistent_store.py` adds a SQLite-backed reference boundary and persistent audit trail, using synthetic student identifiers only. It does not provide real authentication, guardian consent or production-grade student-data protection.

Run: `python -m unittest discover -s tests -v` from the project root.

## v0.6 — Local parent-facing synthetic UI

A small responsive black/gold browser interface demonstrates the existing persistent lesson engine with fictional records only. Run `python -m prototype.local_web` from the project root and open `http://127.0.0.1:8765`. The demo is local-only and resets when stopped. It is **not** a public app, a real login service, a validated reading lesson, or a child-safe deployment. Run `python -m unittest discover -s tests -v`.

## v0.7 instructional content
The local demonstration now shows six stages of a synthetic word-study lesson. Content lives in `content/SYNTHETIC_WORD_STUDY.demo-1.json`. It is **prototype-only**, not expert-approved or validated for real children.

## v0.8 — Synthetic content governance
Added `prototype/content_registry.py` with SQLite-backed immutable lesson versions, separate synthetic author/reviewer workflow, audit events, suspend/retire and demo-only approval. The current local UI is not yet wired to this registry; it remains an isolated governance reference component. Run `python -m unittest discover -s tests -v`. No child-facing publication is enabled.

## v0.9 — Content registry integration

The SQLite-backed lesson store now reads `content_versions` in the same database transaction as session creation. Only `approved_for_prototype` content with a matching SHA-256 digest may start a new session. Every new session receives a `session_content_pins` digest record. The previous `add_approved_prototype_lesson` shortcut is disabled. The local browser uses the registry's approved-only retrieval method and refuses to display withdrawn content.

The demonstration bootstraps a **simulated** author/reviewer workflow on a fresh ephemeral database. This is NOT a real review, publishing approval, or production identity system. Existing session records remain available for synthetic audit after suspension; the browser refuses to deliver suspended content. Existing session mutation is not globally halted on suspension and must be addressed before production. No actual child data, real credentials, or public deployment are supported.

Run tests: `python -m unittest discover -s tests -q` (56 tests expected).
Run local demo: `python -m prototype.local_web` (localhost only).

## v1.0 — Existing-session withdrawal enforcement
The persistent store now verifies approved content status, immutable session content pin, and SHA-256 content integrity **inside the transaction before every existing-session mutation**. Suspended, retired, missing or tampered lesson versions cannot accept responses, stage advances, or state transitions. Authorized historical reads remain available for audit. Six new tests in `tests/test_withdrawal_enforcement.py`; 62 total tests passed locally. This remains synthetic-only and does not establish production security or reviewer identity verification.
