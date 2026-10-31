# Contributing to Living Literacy

The owner selected AGPL-3.0-only for project software and approved the current Living Literacy name and included content for the proposed public repository. See `LICENSE` and `docs/LICENSING_AND_CONTENT.md`. Educational content, other assets, and branding have separate rights; a software license does not itself license them or grant trademark rights. Contributor terms and reporting contacts remain to be decided.

## Development

Read `AGENTS.md`, the specifications and decision register, and `DEVELOPMENT_PROGRESS.md` before changing behavior. Until the release controls are verified, use **synthetic student and adult data only**: no real names, credentials, student records, educational responses, assessment results, or identifiable examples in code, fixtures, logs, issues, screenshots, or pull requests. Do not enter secrets or commit local databases.

From the project root, the existing Python prototype and tests use the standard library:

```sh
python3 -m unittest discover -s tests -q
python3 scripts/validate_registry.py
```

The registry validator is expected to report that the canonical skill definitions are absent. When changing the browser interface, also run `node --check prototype/web/app.js` if Node.js is installed. See `docs/OPERATIONS.md` and `DEVELOPMENT_PROGRESS.md` for local prototype and operational limitations. Report the actual commands, results, skipped checks, and environment limitations.

## Proposed contribution workflow

When the project is authorized to accept contributions, discuss substantial changes with maintainers before implementation; use narrowly scoped changes and tests that exercise behavior. A change description should state the problem, approach, tests run, privacy and accessibility implications, and unresolved decisions. Reviewers must inspect server-side access and evidence/assistance rules when affected. Do not bypass content withdrawal, version pins, or review decisions to make a test pass.

Educational content, translations, audio, images, and code each require provenance and permission checks, even when supplied by a contributor. Do not copy proprietary lessons, assessment items, scores, designs, or third-party assets without documented rights. Do not invent the missing skill definitions, validation data, quotations, sources, or mastery thresholds. Content requires independent human review under `contracts/CONTENT_PUBLICATION_POLICY.md`; simulated fixture decisions are not real approval. See `docs/LICENSING_AND_CONTENT.md` for the proposed review record.

The future contribution terms, including any contributor agreement or sign-off, are undecided. This guide does not grant a license or impose an unapproved agreement. Follow `CODE_OF_CONDUCT.md`; report potential security problems as described in `SECURITY.md`, not in public issues.
