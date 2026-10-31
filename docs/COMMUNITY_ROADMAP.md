# Community Edition roadmap (draft)

This roadmap prioritizes a self-hostable core before optional hosted commerce. Each phase is incremental: preserve working behavior, ship tests and operational documentation, record actual results in `DEVELOPMENT_PROGRESS.md`, and explicitly retain unresolved gates. No phase implies approval to publish the repository or process real student data.

## 0. Inventory and publication decisions — current

- Inventory the v1.0 project, tests, code/asset origin, current data flows, third-party dependencies, names and marks; identify what may be distributed and what needs separate permission.
- Document the CE/hosted boundary, extension design and release gates. The owner selected AGPL-3.0-only for software and approved the current name and included content for the proposed release; record separate rights and provenance for content and any additional material.
- Make local development reproducible with clear warnings, contribution guidance and a private reporting procedure that does not invent contact details. Audit secrets and personal data before any public release.

Done when the inventory and decisions are reviewable, and the owner explicitly approves publication scope. Publication must accurately describe prototype status and applicable rights.

## 1. Reproducible synthetic development environment

- Add non-destructive, versioned database migrations, synthetic fixtures, environment examples, local container setup, isolation of persistent data, and backup/restore documentation. Keep the existing prototype local-only; a container does not make it production-safe.
- Run all original and added tests; verify migration from an empty database and representative previous schema, rollback/failure handling, persistence across restart and restore. Document which host operating systems and container tools were actually tested.
- Add continuous integration when the repository is ready to host it; do not publish or enable remote services without approval.

Done when a new developer can reproduce the synthetic-only environment and documented checks, and migration/restore evidence is recorded. Container security and child-data readiness are separate gates.

## 2. CE security and identity boundary

- Replace simulated credentials and guardianship with a reviewed, self-hostable identity and authorization design; validate roles, workspace isolation, relationships, purpose and consent on every protected operation. Include revocation, expiration and audited privacy requests; support separate family and institutional boundaries.
- Specify threat model, session lifetime, CSRF/rate limits, audit, logging redaction, encryption, retention and data export/deletion. Test cross-family, cross-school, missing-consent and revoked-access scenarios, including concurrent requests and recovery.
- Resolve legal authority, privacy notices, retention, vendor and institutional agreements with qualified reviewers before any real-data deployment.

Done only after independent security/privacy review and documented approval; synthetic identifiers or sample data are not proof of guardian authority.

## 3. Core lesson and governance parity

- Preserve all six ordered stages, separate assistance from independent evidence, session transitions and idempotency. Maintain immutable version pins, transactional withdrawal checks and auditable historical records through any stack migration.
- Implement authenticated curriculum author/reviewer workflows and independent review without trusting caller-supplied reviewer labels. Verify rights/provenance, publication and withdrawal state at delivery and on every relevant mutation. Add reviewed original content only after the required human and rights approvals.
- Provide accessible parent/student dashboards, history and reproducible end-to-end tests without displaying invented mastery or grade equivalents.

Done when parity, adversarial authorization, withdrawal, accessibility and version-integrity tests pass and independent reviewers have approved any actual released material. Content and code approvals are separate.

## 4. Skills, evidence and assessments

- Import the missing 91 candidate definitions only from verified authorized sources after adjudication and expert review. Store versioned dependencies without blanket locks between word recognition and language comprehension. Recommendations require transparent rules and approved evidence; unavailable or insufficient data produces a limited result.
- Provide versioned assessment administration, response and assistance provenance and reviewable results. No unvalidated scoring threshold, diagnostic, reading-level, Lexile or mastery claim. Any later instrument requires documented review and validation.
- Test fixtures must be original and synthetic; keep unapproved material off real learner paths.

Done when the framework and contracts are tested and source/review records are complete; scientific validity remains a separate review decision.

## 5. Community extensions and operations

- Formalize and version curriculum, assessment and narration interfaces, package manifests and compatibility/conformance tests. Apply server authorization, permissions, input validation, resource limits, provenance and withdrawal checks to every adapter. Support a no-provider/offline fallback where feasible.
- Add operator-controlled deployment configuration, metrics without learner secrets, audited administration, recovery/restore drills, updates and rollback. Document accessibility and data portability. No mandatory hosted subscription, analytics service or external provider for CE core.
- Enable narration only after reviewed scripts, licensed audio, accessible transcripts/captions, tested withdrawal, and atomic assistance logging are available.

Done when independent self-hosted installation and upgrade, extension compatibility, incident handling and data export/recovery have been tested and documented.

## 6. Optional managed service — after functional CE

- Isolate hosting operations and billing adapters from CE core. Add hosted subscriptions, verified idempotent webhooks and customer management only after provider and consumer-policy review; pricing must never override data or educational policy. Keep self-hosted CE payment-free.
- Resolve educator and institutional authority, contracts and separate workspace controls before enabling school records. Do not imply educator payment grants roster rights.
- Deploy to staging first, run end-to-end tests and release-gate review, and obtain explicit approvals for live charges, real child data, and production release. A valid public repository license does not itself approve those actions.
