# Community prototype API (experimental)

These interfaces are for fictional data in the local or restricted synthetic staging prototype. They are **not** a stable production API, a validated assessment, or evidence of legal guardianship. Do not connect real students, schools or real personal data. The server enforces the existing synthetic identity, workspace, relationship and purpose-specific consent checks and denies missing authority. Login is a synthetic fixture; it is not a real identity provider. Administrative fixture creation, consent granting, content review and real onboarding are deliberately not exposed over HTTP.

## Request boundary

The existing app requires a valid session cookie for protected routes. Mutating requests require `application/json`, the exact configured same-origin `Origin`, and the session-bound `X-CSRF-Token` returned by `/api/me` or synthetic login. Requests and responses must not be cached. Staging additionally requires its restricted gateway; it is not a public service. Invalid/unauthorized or unavailable resources generally return 403, invalid requests 400, conflicts 409 and a storage error 503. Error bodies are intentionally generic and must not be treated as detailed policy decisions.

## Curriculum overview

`GET /api/curriculum/domains` returns the existing draft 12-domain manifest as `status: candidate_counts_only`, `canonical_skill_definitions_present: false`, and a list of `code`, `name`, `strand` and `candidate_count`. These counts are planning data. They are not published skill definitions, student progress, diagnostic recommendations, or mastery. Both strands remain available concurrently. Missing or malformed data fails closed. The lesson catalog and session APIs still enforce simulated prototype content status, integrity and withdrawal on delivery and mutation.

## Synthetic assessment workflow

All paths below are under `/api/v1` and require a pre-existing fictional student relationship, profile purpose and a **separate, active synthetic assessment consent fixture**. Nothing in the shipped web app grants this consent or approves/creates forms. The existing app seeds no assessment form or assessment consent; consequently this interface provides no learner assessment by default.

| Method and path | Purpose |
| --- | --- |
| `GET /students/{student_id}/assessment-forms` | List metadata for intact synthetic prototype fixtures; `validation_status` is always `unvalidated`. |
| `GET /students/{student_id}/assessment-history` | List authorized run status and response counts, including limited history after a form is suspended. |
| `GET /assessment-runs/{run_id}` | Retrieve pinned fixture items only while the source remains approved for prototype and intact. |
| `POST /assessment-runs` | Start/retry a run using JSON `student_id`, `form_id`, `version`, and `idempotency_key`. |
| `POST /assessment-runs/{run_id}/responses` | Record JSON `item_id`, `response`, explicit Boolean `assisted`, explicit Boolean `narration`, integer `revision`, and `idempotency_key`. Narration is always recorded as assistance. |
| `POST /assessment-runs/{run_id}/complete` | Finish an active run using integer `revision` and `idempotency_key`; completion is not mastery. |

Idempotency keys are 16–100 URL-safe letters, digits, `_` or `-`. Reuse of a key with a different request or a stale revision results in a conflict. The server rechecks relationship, consent, pinned form integrity and status in the same transaction as each mutation. Response results carry `evidence_status: needs_review`; completed runs carry `mastery_status: not_assessed`. No scores, diagnoses, reading levels or recommendations are produced. Explicitly reporting narration is not the same as automatic playback provenance; no live audio or microphone is enabled by these APIs.

## Extension packages

The experimental offline curriculum, narration and assessment package formats and validation CLI are described in `docs/EXTENSION_PACKAGES.md`. They validate data-only synthetic drafts and do not execute provider code, import or approve instructional content, bypass authorization, or claim provenance. Their schema and API may change before a documented compatibility release.
