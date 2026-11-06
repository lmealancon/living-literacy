# Synthetic assessment activity workflow

This is a local engineering fixture for fictional data, not a real student assessment, research pilot, or validated diagnostic. It does not create educational items, scores, mastery states, grade equivalents or recommended interventions. A form must already exist as a trusted `SyntheticAssessmentStore` fixture and the existing simulated guardian and assessment-purpose consent must both permit access. Simulated review and consent are not verified human authority. No fixture-authoring or consent-bypass interface is exposed to untrusted users.

`SyntheticAssessmentWorkflow` is an additive boundary around the existing SQLite prototype. It uses an atomic transaction for each start, response, and completion; records non-content audit events; pins the form version and digest; denies withdrawn or tampered forms for activity writes; and requires a distinct explicit `assisted` and `narration` boolean. Narration is always recorded as assistance even if a caller says otherwise. A completed activity remains `mastery_status: not_assessed`. Authorized activity history retains limited metadata after withdrawal and remains subject to active purpose-specific consent. Assessment questions are presented through the existing assessment presentation service, which rechecks current form status and digest.

Methods:

- `start(token, student_id, form_id, version, key)` returns a fictional run ID, `status`, `revision`, and `validation_status`.
- `record_response(token, run_id, item_id, response, assisted, narration, expected_revision, key)` records a bounded fictional text response and returns its ID, next revision, assistance metadata, and `needs_review` evidence status.
- `complete(token, run_id, expected_revision, key)` records activity completion, never a score or mastery finding.
- `history(token, student_id)` lists activity-only records after authorization and consent.

Clients must supply an idempotency key of 16–100 ASCII letters, numbers, underscores or hyphens. Repeating a successful request with the same key and payload returns the original result; changing a payload with a previously used key is a conflict. Mutations require the expected nonnegative integer revision. Idempotent replays are still denied after consent or content withdrawal. Legacy synthetic assessment runs retain their old behavior, but legacy response entry is denied for a workflow-managed run, preventing bypass of its closure, revision, audit or idempotency checks.

Run tests from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_assessment*.py' -v
python3 -m unittest discover -s tests -p 'test_synthetic_assessment.py' -v
```

Open decisions: independently approved instruments and reviewer identity, legal guardian authority and consent, assessed purpose and retention/deletion, production database migrations, accessible assessment delivery, validation research, supported scoring policies, and independent security/privacy review. No actual screener or threshold is supplied. This module does not itself make the platform safe for real student data.
