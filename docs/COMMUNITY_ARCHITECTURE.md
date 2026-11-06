# Community-first architecture (draft)

Status: target architecture and migration plan, not a claim that the Community Edition is implemented or ready for real students. `AGENTS.md`, `specs/RELEASE_GATES.md`, and `docs/DECISION_REGISTER.md` continue to govern. Use synthetic student data only. The source repository is public under the owner-selected software license; publication of source and the private synthetic staging service do not authorize use with real students or an educational production release.

## Goals and boundaries

The Community Edition (CE) is intended to be a complete, usable self-hosted application for authorized families and institutions. Its source, build and operation should be inspectable and portable. The owner selected the software license and approved the previously included name and content; newly created material still needs rights and content review. Core educational functionality must not require a cloud subscription, external payment service, proprietary vendor account, or telemetry. Optional integrations should fail without compromising unrelated CE functions. Comparable scope to commercial reading products is a long-term aspiration, not a claim of equivalent content, validation, efficacy, or current functionality. All content and code must be original or used under an explicitly verified license; do not copy proprietary questions, algorithms, designs, or assets.

The current project is a Python standard-library prototype with SQLite, localhost HTTP server, and a simple browser UI. [Synthetic skill snapshot export and dependency inspection](SKILL_SNAPSHOT_GUIDE.md) describe the limited local registry interface. `prototype/lesson_engine.py` and `prototype/persistent_store.py` implement the six-stage engine and transactional persistence; `prototype/content_registry.py` and session content pins enforce prototype approval and withdrawal; `prototype/skill_registry.py`, `prototype/synthetic_assessment.py`, and `prototype/story_vibes_policy.py` are isolated synthetic foundations. The app server binds localhost and uses simulated credentials, authority, and consent. It is not a production multi-tenant or child-data service. See `DEVELOPMENT_PROGRESS.md` for test evidence and limitations. Containerizing that prototype does not change these restrictions.

## Target distribution

| Boundary | Community Edition | Optional hosted service |
| --- | --- | --- |
| Installation | Reproducible source, migrations, container definitions and documented backup/restore; operator controls storage and network | Managed infrastructure, upgrades, backups, monitoring and support |
| Education | Versioned skill registry, six-stage lesson engine, lesson player, content governance, basic assessment framework and progress dashboard | Same educational and privacy policy controls as CE |
| Identity and privacy | Server-enforced identity, roles, workspace, relationship, purpose and consent; family and school isolation; operator-controlled records | Same authorization decisions, with managed operations and contractual controls |
| Integrations | Documented interfaces for curriculum, instruments and narration; local/no-provider operation is supported | Optional provider adapters and integrations, subject to independent review |
| Payments | No billing dependency for CE installation or educational function | Optional subscription and payment provider integration; entitlement never overrides safety or privacy |

These are targets. Existing prototype code does not yet satisfy the production capabilities in this table. Commercial hosting, identity, payments, infrastructure configuration and business-specific features must be kept outside the CE's core educational policy and interface contracts. Users must be able to operate a self-hosted CE without commercial infrastructure or payment checks; no automatic advertising use of learner data. Any dependency on a network service must be explicitly documented and either optional or replaceable with a documented open protocol.

## System shape

Use a modular monolith initially, with narrow interfaces and explicit transaction boundaries. The technical stack remains a decision for reviewed implementation: `AGENTS.md` proposes Next.js/TypeScript with PostgreSQL, while the current reference implementation is Python/SQLite. Preserve working behavior and test coverage during any migration. Do not add an independently mutable second educational rules engine; establish contract tests that compare stages, evidence and version/withdrawal decisions before moving ownership. The current Python modules remain the reference until parity is proven.

- **Presentation:** responsive, accessible browser UI with adult/admin views and age-appropriate lesson surfaces. The client is untrusted; it never makes authorization, publication, consent or scoring decisions.
- **Core application:** server-side identity and policy boundary, family/school workspaces, relationships, purpose-scoped consent, protected student operations, versioned lesson player, registry, evidence, assessment framework, audit and privacy workflows. Fail closed. Completion, practice, independent evidence and retention remain separate; no automated mastery or diagnostic equivalence.
- **Governance:** independent authorized human review, immutable published lesson versions and audit events; verify source, provenance, rights and license for every distributed asset. Suspending or retiring content denies new delivery and mutations of pinned sessions while authorized audit history is retained under approved policy. Client caches need a withdrawal/invalidation design; already delivered content cannot be recalled.
- **Storage:** transactional, versioned schema and migrations with foreign keys and documented SQLite-to-target strategy; no destructive migration by default. Tenant/relationship predicates are mandatory at the server boundary. PostgreSQL row-level security may add defense in depth but cannot replace application checks. Private object storage and backups require explicit access controls and an independently tested restore procedure.
- **Jobs and adapters:** a durable worker boundary for approved background work; network/provider failures must not bypass policy. Hosted billing, email, narration and cloud-specific integrations use explicit server-side adapter contracts and remain optional.

Never use synthetic bootstrap tokens, self-declared child identity, simulated consent, or simulated review as production proof. No real student data may be used before the mandatory release gates are satisfied and the user authorizes that release.

## Extension contract direction (not yet public APIs)

Interfaces should be versioned, documented with schemas, and tested against a shared conformance suite. The host determines identity and authorization, validates untrusted inputs and outputs, performs version/pin/status checks, records audit and provenance, and applies resource limits. Extensions cannot grant privileges, publish lessons, assert independent evidence, assign mastery, or override withdrawal. A configuration/manifest identifies extension version, capabilities, dependencies, operator-visible data flows and required permissions. Deny unavailable, malformed, incompatible or unapproved extensions; no runtime code installation from child input.

1. **Curriculum modules:** import original or licensed immutable content plus stable identifiers, content version, source references, rights/license, review status and evidence rules. Review and publication occur only in the host. Content packaging must support offline verification and clear licensing/provenance.
2. **Assessment instruments:** versioned forms, administration and response/evidence metadata, explicit review and validation status. Host controls eligibility and scoring policies; unvalidated or synthetic instruments cannot infer reading level, diagnosis or mastery. Do not invent clinical thresholds.
3. **Narration providers:** receive only the minimum authorized approved-script input; require source/script/asset versions, captions/transcripts and withdrawal state. Record narration exposure as assistance before it could affect evidence. Approved local audio and a text fallback must work without a commercial account. Any network provider requires separately reviewed privacy and vendor terms.

Storage export formats, API versioning, authentication protocols, formal package manifests, isolation/sandboxing and compatibility policy are engineering decisions, not existing features. Describe migration and deprecation behavior before declaring a stable external API.

## Open-source and content governance

The owner selected AGPL-3.0-only for the software and approved the name and previously included content for the public repository. See `LICENSE` and `docs/LICENSING_AND_CONTENT.md`. Software licensing does not automatically confer rights in content, other assets or trademarks. Review ownership, dependency notices, source history and additional contributed artifacts; maintain a provenance inventory with sources, rights, review status and distribution scope. Contributor terms and private security-reporting arrangements remain to be established. No real-learner or educational release is implied.

## Release gates

Before any real-data or public educational release: verified roles, tenant isolation and consent; independently reviewed content and rights; clinical/assessment review where relevant; legal and vendor review; accessibility checks; encryption, retention/deletion, incident response and recovery; security review and tests; documented operator responsibility; owner approval. The source-availability decision and child-data release are separate approvals. Self-hosting does not itself establish compliance, scientific validity, security or support readiness.
