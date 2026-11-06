# Living Literacy development progress

## Scope and release status

Synthetic student data only. This is not approved for production use with children, real guardian consent, live payment, schools, or validated assessment. `specs/RELEASE_GATES.md` and `docs/DECISION_REGISTER.md` remain authoritative. The v1.0 Python prototype and original tests are retained. The supplied archive does not include the complete skill definitions, independently approved instructional inventory, assessment forms, source material, or human review decisions. Those are not invented here.

## Phase 1: inspection and baseline — complete

Read README, AGENTS, product and privacy specifications, decision register, lesson and content code, and test suite. The baseline `python3 -m unittest discover -s tests -q` ran 73 tests successfully. `python3 scripts/validate_registry.py` passed the 12-domain manifest check and reported 91 candidate count and zero imported canonical skills (expected blocker).

Existing components: six-stage in-memory lesson engine, SQLite synthetic persistence, simulated content review and version pinning, withdrawal enforcement, localhost demo, and synthetic-only credential and guardian checks. The local demo shares a fixture and is not a live multi-user app. Earlier README sections have stale status text.

## Requirements and decisions missing before dependent release

- D-004/D-005/D-016: approved source definitions, identity provenance and adjudication for skills; no skill definitions or mastery thresholds may be invented.
- D-008/D-012: independently reviewed lessons, reviewer identity and publishing authority; synthetic review identifiers are not real approval.
- D-006/D-007: validated evidence rules, thresholds and assessment instruments; no diagnostic, grade, Lexile, disability, or mastery claims.
- D-010/D-011: vendors, contracts, privacy notices, retention and deletion; real child processing remains blocked. Guardian fixtures are not legal authority or consent.
- D-009/D-013: educator permissions, procurement and contracts; paid access is not student-record authorization.
- D-015: reviewed API and migrations; PostgreSQL, identity provider and storage choices unresolved.
- Story Vibes requires reviewed source/script fidelity, licensed voices and approved audio assets. Billing requires provider configuration, verified webhook testing and legal review before charges.
- Accessibility, incident response, audit, backups/restores and security review must be verified before launch.

## Phase tracking

1. Inspection and baseline — complete.
2. Full-stack foundation — in progress; existing stdlib Python/SQLite implementation is being extended. The npm registry was reachable with additional network permission and a writable cache; Next.js is not installed and no PostgreSQL server is available. No production migration has been verified.
3. Parent authentication, guardian permissions and child profiles — synthetic backend foundations exist; real identity and consent are blocked.
4. Six-stage engine and content registry — existing prototype; retain version pinning and withdrawal safeguards.
5. Parent and student dashboards — in progress, synthetic only.
6. Skill registry and recommendations — in progress; zero approved canonical skills; no unsupported recommendations.
7. Assessment framework — in progress; no validated instrument or scoring thresholds.
8. Story Vibes — gated until reviewed scripts and approved licensed audio are available.
9. Curriculum and resources — synthetic content governance only; production resources pending review.
10. Billing and educator features — not implemented; no live billing or real student records.
11. Admin, privacy workflows, observability and protections — incomplete; human review and production authorization required.
12. Staging, deployment and release review — not done. No live URL claimed.

## Implemented in this development pass

- `prototype/content_registry.py`, `tests/test_review_integrity.py`: synthetic submitter cannot approve their own submission; approval rechecks the content digest. Simulated identities are not proof of independent review.
- `prototype/skill_registry.py`, `tests/test_skill_registry.py`: immutable synthetic draft snapshots, missing-dependency and cycle checks, and simulated separate review; no canonical definitions or automatic recommendations added.
- `prototype/synthetic_assessment.py`, `tests/test_synthetic_assessment.py`: synthetic forms and response/assistance capture with explicit simulated consent, authorization, content version and withdrawal checks; no scoring or diagnostic claims.
- `prototype/story_vibes_policy.py`, `tests/test_story_vibes_policy.py`: isolated synthetic source/script/asset and narration eligibility checks. No audio playback, real approval, or persisted exposure integration.
- `prototype/web/`: synthetic login, profile, history and lesson user interface. API integration and browser verification pending.
- `docs/OPERATIONS.md`: local operations guidance and synthetic SQLite backup/restore drill; production recovery remains unverified.

Intermediate verification: `python3 -m unittest discover -s tests -q` passed 96 tests. `python3 scripts/validate_registry.py` passed manifest validation and reported the expected empty canonical registry. `node --check prototype/web/app.js` passed. This evidence does not establish security, accessibility, or release readiness.

## Local application integration update

`prototype/app_server.py` connects `prototype/web/` to the existing synthetic store, credential fixture, profile authorization, lesson engine and approved-prototype content registry. `tests/test_app_server.py` exercises the request handlers in process, including cross-family denial, CSRF, session history, content withdrawal, required assistance and idempotency. The UI refreshes approved lesson content before rendering a stage; already displayed content cannot be recalled from an open browser until another request or render. Keyboard focus target was added to the stage heading. Browser and screen-reader tests have not been performed.

To initialize and run locally (fictional data only):

```sh
python3 -m prototype.app_server --init
python3 -m prototype.app_server
```

Enter a fictional passphrase at initialization; the default identity is `synthetic-parent-1`. Open `http://127.0.0.1:8765` on the machine running the server. This is not a public deployment: the server binds localhost, lacks production security, and simulates guardian authority and consent. Do not enter real personal or student data. Existing demo databases are never overwritten by initialization.

Latest verification: `python3 -m unittest discover -s tests -q` passed 99 tests; `node --check prototype/web/app.js` passed; `python3 scripts/validate_registry.py` passed with the expected zero-skill blocker. These include in-process HTTP handler tests, not real network or browser testing. The features remain incomplete: no real signup, managed authentication, public deployment, billing, production content review, approved assessments, audio playback, classroom features, PostgreSQL migration, complete public website or release authorization. Next bounded task: browser integration testing and review of the local authorization and withdrawal boundary, followed by explicit architecture and production-service integration decisions.

## Community Edition direction — 2026-10-31

Audited the existing v1.0 project and documented the target separation of self-hosted educational core from optional hosted services in `docs/COMMUNITY_ARCHITECTURE.md` and phased work in `docs/COMMUNITY_ROADMAP.md`. A local Git repository was initialized, with ignore rules and a CI workflow. No remote was configured and nothing was published. A final code license, branding approval, and rights/provenance review remain unresolved; `docs/LICENSING_AND_CONTENT.md` records the decisions, and `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` are drafts pending reporting contacts and owner approval.

Implemented incremental foundations:

- `prototype/migrations.py`, `tests/test_migrations.py`: explicit transactional SQLite migration for the recognized synthetic schema only, with a checksummed ledger and two indexes. Back up first; it never creates guardian grants or consent, and does not migrate PostgreSQL. See `docs/OPERATIONS.md`.
- `prototype/extension_contracts.py`, `tests/test_extension_contracts.py`, `docs/EXTENSION_CONTRACTS.md`: experimental data-only curriculum, narration and assessment interfaces with validation. They do not load plugins, expose stable HTTP APIs, bypass authorization or publish content.
- `Dockerfile`, `compose.yaml`, `.dockerignore`, `.env.example`, `CONTAINER_DEMO.md`, and `tests/test_container_demo.py`: local synthetic demo scaffolding with localhost host-port publication and simulated credentials. A container does not make the prototype appropriate for real learners or public use. `app_server.py` retains normal loopback default and has a deliberate opt-in container listener.
- `.github/workflows/ci.yml`: test workflow configuration; no remote CI run has occurred.

Verification: the complete suite passed 114 tests (`python3 -m unittest discover -s tests -q`); `python3 scripts/validate_registry.py` passed and confirmed zero canonical skill imports; `node --check prototype/web/app.js` passed; `docker compose --env-file .env.example config --quiet` passed. Docker image build, startup, persistent volume and connectivity were not verified because the Docker daemon socket returned permission denied. Existing tests run in-process and do not establish browser accessibility, actual container behavior, production security or scientific validity.

Community Edition is not finished: real role/relationship/consent enforcement, institution isolation, production-ready identity, reviewed content and rights, integrated registry/assessment/narration interfaces, documented stable APIs, cross-platform container verification, reliable migrations for other schemas, accessible browser testing, and release review remain. The 91 candidate definitions and validated instruments are still absent. Self-hosted functionality must not depend on hosted billing. No final license has been chosen and the user must approve license, branding and included content before publication.


## License and proposed release approval

The owner chose AGPL-3.0 for the software; the repository applies version 3 only (AGPL-3.0-only), with the full text in `LICENSE`. The owner also approved the current Living Literacy name and included sample content and documents for the proposed public repository. The software license does not automatically confer a separate educational-content or trademark license. Contributor terms, private reporting routes and detailed third-party/content provenance remain to be resolved. Earlier entries describing the license decision as pending are historical.

The approval to publish source does not authorize live operation with real child data, scientific claims, or production release.

## Private online staging preparation

`prototype/app_server.py` now supports an explicit HTTPS-origin staging mode behind a same-host authenticated gateway: it retains a loopback-only app listener, requires a server-held gateway secret for every request, validates Host and Origin, and sets Secure cookies. Default localhost and container modes remain intact. `tests/test_private_staging.py` covers the new boundary and preserves content withdrawal. `deploy/private-staging/README.md` and `Caddyfile.example` describe a restricted gateway deployment.

`python3 -m unittest discover -s tests -q` passed 120 tests. Registry validation and JavaScript syntax checks passed. The tests exercise handlers in process only; no browser, actual TLS gateway, Caddy configuration, hosted instance, rate limiter, live URL, or backup on a host has been verified. No provider has been configured. The Caddy example is not a ready-to-deploy public service. An experienced operator must establish restricted access, review gateway configuration and implement independently tested rate limiting and monitoring before private fictional-data staging. Real student data, family onboarding and production release remain blocked by the release gates.

## Free hosting investigation and Render staging scaffold

The user requested no Lovable service and no associated Lovable charges. The separate existing Lovable project was inspected read-only and was not edited or deployed. Its existing scoring and lesson rules differ from this project, and the latest tool check showed its original commit unchanged.

Added `deploy/render/` and `tests/test_render_staging.py` for experimental restricted synthetic staging using the existing Python engine behind an authenticated nginx gateway. Render's free local filesystem is ephemeral, so all synthetic progress is discarded at restart or idle spin-down. This is not a durable website or a production service for families. Render free tier and billing terms require review before account use. Matching AGPL source must be public before network use; `prototype/web/index.html` links to the source repository, but this local revision has not been uploaded to the public GitHub repository.

Final local verification: `python3 -m unittest discover -s tests -q` passed 127 tests; registry validation and JavaScript syntax checks passed. Docker daemon access was denied and nginx was unavailable, so the container, proxy, TLS, authentication via real browser, Render deployment and any public URL are unverified. The template must not be represented as safe for real children or ready for production. Further work is required for durable data, secure real-family identity and authorization, content review and deployment.

## Family dashboard and distinctive interaction update

Based on the founder's request for the broader Living Literacy vision, added an improved fictional family dashboard with user-selected interest choices (not yet used to personalize instruction), observed activity counts and history filters, a six-stage pathway, accessible single-use letter tiles for the existing synthetic 'map' lesson, and a quiet break that pauses the existing session. Story Vibes styles are described as planned; no audio assets, unreviewed content or unsupported mastery claims are enabled. `prototype/family_insights.py` persists allowlisted choices and produces activity-only summaries behind existing profile/lesson consent and relationship checks. `prototype/app_server.py` exposes these protected operations. Input requires explicit yes/no assistance recording. The interface clears prior user data on sign-out and protects against stale asynchronous responses.

`prototype/assessment_service.py` adds an independently tested consent-scoped synthetic assessment presentation boundary; it is not connected to a user-facing assessment, and no reviewed forms, scoring or diagnostic are available. Test coverage includes `tests/test_family_insights.py`, `tests/test_assessment_service.py`, API tests, and a browserless Node DOM/fetch harness for stale data, logout, and assistance handling. Final local run: 139 tests passed; `node --check prototype/web/app.js` and registry validation passed. The browserless test is not real browser or screen-reader testing. This change does not implement durable storage, real-family accounts, individualized recommendations, Story Vibes playback, the missing skill definitions, approved curricular inventory or validated assessment. Render's free staging resets the fictional database on service restart and this local revision is not yet deployed.

## Reading content and audio foundations

The user confirmed the additional lessons and audio need to be created. Prepared three original six-stage fictional lesson drafts and four-style Story Vibes script candidates in `content/drafts/`; all remain unreviewed and are rejected by the live prototype catalog. Expanded synthetic catalog listing to verify status, schema, version and digest in one transaction; it still contains one available demo lesson. Added `prototype/synthetic_narration_store.py` for trusted synthetic WAV fixtures, authorization, pinned-content checks, transactional exposure recording, and conservative exclusion of assisted responses from independent evidence. An authenticated narration endpoint exists only behind an in-process test opt-in; it is disabled in shipped CLI modes, and no narrated asset has been enabled. An offline generated spoken sample and provenance notes are held outside the repository for review, with no claim of voice rights, approved pronunciation or educational suitability. The project still has no AI conversation, microphone, speech recognition, approved audio or complete lesson inventory.

Verification: `python3 -m unittest discover -s tests -q` passed 164 tests; registry validation and JavaScript syntax checks passed. These tests do not establish educational effectiveness, legal compliance, real-family security or a verified voice license. Live site unchanged; changes exist only locally pending review and GitHub/hosting update.

## Interactive visual redesign and external baseline research

Reviewed public descriptions of [ABCmouse](https://support.abcmouse.com/hc/en-gb/articles/4919113704855-Getting-Started-with-ABCmouse-Watch-the-Intro-Video), [i-Ready](https://www.curriculumassociates.com/programs/product-updates?ppcp_platform=adroll), and [Reading Eggs](https://readingeggs.com/schools/lesson-overview/) for high-level interaction patterns: visual learning journeys, short activities, learner choice, age-appropriate presentation, motion controls and a separate family view. This is not a hands-on comparison of authenticated products; no proprietary content, scoring or artwork was copied.

Updated `prototype/web/index.html`, `styles.css`, and `app.js` with an original animated book illustration and reading-world styling, a clear six-stage path, large tap/drag word tiles with undo and clear, optional reduced-motion and simplified visuals, and respect for system reduced-motion changes. Existing backend lesson, content and authorization paths are preserved. No new approved lessons, audio playback, AI tutor, assessment or real-child capability was added. The available lesson is still a fictional test and the free Render service resets data.

`tests/test_interactive_journey.py` and `tests/web_privacy_harness.js` exercise synthetic six-stage progression, explicit assistance, history, tile behavior, motion controls and reduced-motion changes using in-process handlers and a mocked DOM. Final local verification: `python3 -m unittest discover -s tests -q` passed 165 tests; `node --check prototype/web/app.js` and the registry validator passed, with zero canonical skills. Real-browser, mobile-device, screen-reader and full WCAG testing have not been performed. Local source changes are not yet deployed to GitHub or Render.

## Community Edition audit and synthetic foundations — 2026-11-06

Audited the existing prototype and updated `README.md`, `docs/COMMUNITY_ARCHITECTURE.md`, and `docs/COMMUNITY_ROADMAP.md` to reflect the public repository, the owner's AGPL-3.0-only software choice and the remaining work. The source changes below are local and have not been uploaded or deployed. The license does not automatically license educational content or trademarks.

- `prototype/assessment_workflow.py`, `prototype/synthetic_assessment.py`, `prototype/assessment_service.py`, and `prototype/app_server.py` add consent-scoped fictional assessment sessions, resumable revisions, idempotent response capture, withdrawal checks and API routes. Assessment forms are trusted synthetic fixtures; no reviewed instruments, scoring, diagnoses or mastery claims are enabled. Related tests cover authorization, revocation, tampering and transaction behavior.
- `prototype/content_registry.py` adds auditable draft revisions and separate simulated review; `prototype/skill_registry.py` adds synthetic snapshots and dependency views. Neither supplies real editorial approval or missing canonical skills.
- `prototype/curriculum_overview.py` and `prototype/web/` expose existing candidate domains and recorded activity counts without claiming a student's reading level or mastery. They do not create the missing skill definitions.
- `prototype/migrations.py` supports an explicitly selected, recognized legacy synthetic SQLite schema with empty relationship and consent tables. It rejects triggers and views, verifies schema and migration history, and applies changes transactionally. It does not infer authorization or migrate arbitrary databases. See `docs/OPERATIONS.md`.
- `prototype/extension_package.py`, `examples/extensions/`, and the new guides under `docs/` describe and validate offline, data-only experimental extension packages and synthetic APIs; they do not execute third-party code or connect paid services.

Verification: `python3 -m unittest discover -s tests -q` passed 214 tests; `node --check prototype/web/app.js`, `git diff --check`, and `python3 scripts/validate_registry.py` passed. The registry validator still reports zero imported canonical skills and 91 candidate definitions missing. Tests use synthetic identities, in-process HTTP handlers, and a mocked DOM; they do not establish real-world privacy, browser accessibility, assessment validity, production readiness, or Docker runtime behavior. Docker startup was not verified because daemon access was denied.

Remaining work includes independently reviewed and licensed lessons and assessment instruments, actual skill definitions, real family and institutional identity and authorization, durable production deployment, accessible browser/device testing, and the requested AI, speaking, listening and approved narration capabilities. No real student data should be used in this prototype. Next bounded task: complete reviewed curriculum and a separately security-reviewed identity and data-isolation design before expanding access.

## Original animated lesson guide

After reviewing official descriptions of ABCmouse and i-Ready, added an original decorative seed-like guide to `prototype/web/index.html` and `styles.css`. `prototype/web/app.js` changes its animation state when a letter is selected or a response is saved; celebration acknowledges the save, not correctness or mastery. Existing reduced-motion preferences stop animation and simplified visuals hide the guide. `tests/web_privacy_harness.js` checks these synthetic interaction states. No third-party characters, art, lessons or assessment algorithms were copied.

The full local suite passed 214 tests, including the mocked-DOM harness. This is an incremental visual prototype, not the complete interactive platform. There is no new speech, listening, audio, AI or lesson content. Playback of the reference videos and real-browser and screen-reader behavior were not verified. The guide has not been uploaded or deployed; the owner must review the new character before it is published.

## Synthetic voice and companion foundations

The owner approved the original character and requested that it become an AI companion able to talk back to children. `prototype/web/` now has a separate adult demonstration that speaks two fixed, non-instructional phrases only on a button click, using the browser or device's speech service. It displays the words, supports stop and text fallback, and cancels speech when leaving the dashboard or signing out. The browser's voice processing may be remote. This demo does not accept personal information, use a microphone, use lesson text, or represent itself as AI; it is kept out of the lesson workflow and cannot be treated as assistance tracking.

`prototype/synthetic_companion.py` adds a disabled-by-default scripted provider fixture and an experimental protocol for future integrations, with no conversation storage, network, student context or model connection. `docs/SYNTHETIC_COMPANION.md` describes its limits. Tests in `tests/test_synthetic_companion.py` and `tests/web_privacy_harness.js` cover fixed inputs, opt-in, audio fallback and cancellation. These are local changes and have not been deployed.

The desired AI tutor and voice input remain unimplemented. Real-child interaction needs an actual AI and speech architecture, verified child and guardian authorization, data-flow and retention controls, age-appropriate safety behavior, content review, assistance tracking, accessibility checks and independent security/privacy review. The existing synthetic site must not be used with real children or student data. Next bounded task: design and review a self-hostable, constrained provider boundary and synthetic conversation test harness without transmitting child data.

## Sitewide companion and local AI experiment

The owner requested that the companion greet visitors and guide the whole experience. `prototype/web/` now shows the original character on the welcome view, offers navigation from its greeting, and shows it beside the existing lesson stages. The character's voice sample remains separate from lessons and uses fixed non-instructional phrases. The guide does not yet deliver interactive AI-based instruction or replace the lesson engine.

`prototype/companion_ai.py` adds an opt-in adapter for a separately installed, local Ollama-compatible model. The authenticated, CSRF-protected synthetic demo API in `prototype/app_server.py` accepts fixed action IDs only and can return only predefined sample phrases; it sends no lesson, response, student or identity information to the model. It is disabled by default and the CLI refuses to enable it for staging or container mode. The web demo reveals an experimental text button only when that local adapter is enabled. See `docs/COMPANION_AI.md` for setup and its limitations. A real model and network socket could not be tested in this environment; adapter tests mock the local service. No generative output is accepted as reviewed instructional content, and no real learner may use this prototype.

The owner has established the product direction for a speaking, listening, sitewide AI companion. The former D-014 deferral no longer represents the owner's product intent. Actual conversational and speech input capabilities, child-safe responses, verified real-user authorization, privacy protections, content review and transactional help tracking are still required. Next bounded task: design the real conversation and speech boundaries and verify those protections using synthetic data before any child-facing deployment.

Verification: `python3 -m unittest discover -s tests -q` passed 225 tests; `node --check prototype/web/app.js`, `git diff --check`, and registry manifest validation passed. Registry validation reports the expected zero canonical skill definitions. The model tests use mocks; browser, screen-reader, real local-model and socket tests remain unverified.

## Adult synthetic conversation and speech experiment

The owner emphasized that listening and answering questions are central to the requested experience. `prototype/companion_conversation.py` now supplies an opt-in, localhost-only Ollama-compatible conversation adapter with bounded fictional test messages and prior turns, a response size limit and a shared request limit. It returns real model-generated, unreviewed text when a separately installed model is available; it does not save or log conversations itself. The authenticated synthetic `/api/companion/conversation` endpoint accepts only a message and history, and is disabled by default and in shipped staging and container modes. The model service may itself log or forward data and the app cannot reliably detect personal information.

The separate adult dashboard experiment in `prototype/web/` supports typed questions, follow-ups, optional click-to-start browser speech recognition and optional click-to-play synthesized replies. It shows provider disclosures and text alternatives, aborts speech and clears local history on navigation, profile change or sign-out, and guards late responses. Browser speech services may transmit audio or text. It does not send lesson content or student profile information to the model, but operators must not enter or speak personal details. It is not a child-facing tutor or integrated instructional help.

`tests/test_companion_conversation.py`, `tests/test_app_server.py`, and the browserless harness exercise validation, access, bounded history, response handling and speech controls with mocks. The real model, browser microphone, audio playback and end-to-end conversation remain unverified because no model was installed and local socket access was denied. Live Render cannot run this experiment with its current settings. Remaining requirements include age-appropriate safety, verified identity and consent, privacy and retention, model and voice review, lesson-specific authorization, withdrawal and transactional assistance tracking, and real-device accessibility testing before children use the feature. Next bounded task: configure an appropriate self-hosted or hosted model for synthetic-only testing, then test real browser and model behavior.

Verification: `python3 -m unittest discover -s tests -q` passed 231 tests; `node --check prototype/web/app.js` and `git diff --check` passed. These are not real-device, real-model or child-safety tests.

## Illustrated welcome redesign

In response to the owner's request for a more polished and playful welcome page,
`prototype/web/index.html` and `styles.css` have been redesigned around an
original generated reading-garden illustration in `prototype/web/hero-world.png`.
The image is served through the explicit static allowlist in
`prototype/app_server.py`, with an in-process delivery test in
`tests/test_app_server.py`. `docs/ARTWORK_PROVENANCE.md` records the artwork's
origin and pending owner approval for publication. Existing login, lesson,
synthetic-data notice, reduced-motion and simplified-visual controls remain.

Verification: `python3 -m unittest discover -s tests -q` passed 232 tests;
`node --check prototype/web/app.js`, `git diff --check`, and a check of all
JavaScript-referenced HTML IDs passed. A Chromium screenshot was attempted but
the environment denied the required browser sandbox socket, so actual browser,
mobile and accessibility rendering remain unverified. This is a visual redesign,
not an implementation of child-facing AI, conversation, or additional lessons.
The new artwork and code are local and have not been deployed. Next bounded
task: owner review of the artwork and visual browser testing after staging.

## Animated companion scene

After the owner asked for a more cinematic, animated experience, replaced the
static welcome illustration with an original generated reading-garden
background and a layered SVG seed character. CSS animates its breathing, eyes,
arms, leaves, gestures and speaking mouth; `prototype/web/app.js` connects its
reaction, celebration and talking states to the wave button, fictional lesson
interactions and explicitly started voice sample. The companion also appears in
the existing lesson and voice demo. The animation respects reduced-motion and
simplified-visual settings; celebration acknowledges a saved response, not
correctness or mastery. The source and asset remain local pending owner review.

This is an interactive 2D web animation, not a 3D animated film or AI tutor.
No actual AI conversation is enabled on Render, and the fictional-data limits
still apply. Browser rendering and animation have not been verified because the
environment denied Chromium's sandbox socket. The static image and HTML/JS
interfaces are covered by automated tests and the mocked DOM interaction
harness. Next bounded task: owner review followed by real-browser and mobile
testing of the staged animation.

## Exploratory Reading Garden prototype

The owner requested a playful animated world with game-like exploration.
Reviewed the official *The Secret Life of Pets* teaser listing and film
descriptions for broad character and world-building inspiration; direct trailer
playback was unavailable. No characters, visuals or game content were copied.

`prototype/web/reading-world.js` and `reading-world.css` implement an original
2D canvas garden over the generated local background. The fictional companion
moves using keyboard or on-screen controls; map hotspots and ordinary buttons
navigate to the existing sign-in, activity and voice sections. The game does not
create or authorize a lesson. Signed-out visitors are directed to sign-in; the
map pauses during lessons and resets on sign-out. A text-button fallback works
when canvas is unavailable, and simplified visuals retain the destination
buttons. `prototype/app_server.py` serves the new self-hosted assets.

`tests/reading_world_harness.js`, `tests/test_reading_world.py`,
`tests/web_privacy_harness.js`, and `tests/test_app_server.py` cover movement,
navigation, fallback, app lifecycle and asset delivery using mocks. The full
local suite passed 234 tests, and both JavaScript syntax checks and
`git diff --check` passed. The app has not been tested in a real browser,
on a phone or with a screen reader, and the changes remain local. This is a
small interactive 2D prototype, not a 3D open-world game or animated feature,
and it does not enable real-child use, a new lesson library or live AI.
The generated background and character are still pending owner review for
publication. Next bounded task: obtain the owner's visual review and run
real-browser interaction and accessibility tests before expanding the world.

## Original 3D Reading Garden prototype

The owner requested an explorable 3D game with a reading companion and learning
journey. `prototype/web/world3d-engine.js` renders an original low-poly world
using native WebGL, with a third-person companion, terrain, trees, paths, and
three landmark gates. `world3d-ui.js` and `world3d.css` provide keyboard and
touch controls, a color legend, journey status, simplified-visual controls, and
a direct-navigation fallback when WebGL is unavailable. No external engine,
game artwork, model weights or paid service is bundled.

`prototype/web/world3d-journey.js` tracks an ephemeral synthetic journey. The
activity destination leads to the existing authorized activity selector. The
journey binds only after the server creates a matching session and its content
passes the existing availability check; only a matching, newer, server-returned
completed session can mark the activity complete. This is not mastery. The game
pauses during lessons and resets on sign-out or profile change. Existing
fictional-data authorization, withdrawal and assistance checks remain in force.

`prototype/app_server.py` serves the four new static assets. Engine, HUD,
journey and app-integration harnesses exercise mocked WebGL, movement, fallback
including graphics-context loss, touch controls, lifecycle, lesson completion,
stale sessions and withdrawal. Lost graphics are not automatically restored.
The full local suite passed 237 tests, JavaScript syntax checks passed, and
`git diff --check` passed. Actual GPU rendering, mobile touch, screen-reader
behavior and full browser end-to-end flows remain unverified; the environment
previously blocked Chromium's sandbox socket. Changes are local, not deployed.

This is a small synthetic 3D prototype with one existing fictional sample
activity, not the requested complete game, production service, or a finished
AI companion. No AI conversation or microphone is enabled on Render; model
hosting, child-safe behavior, verified authorization, privacy controls,
reviewed content, and educational validation remain outstanding. Next bounded
task: verify the world in a real browser and integrate reviewed activities and a
separately reviewed companion service without bypassing lesson protections.

## The Vanishing Storybook investigation

The owner requested a clue-led reading investigation in Victorian London.
`prototype/web/world3d-engine.js` now renders an original, imagined London
street with a Post Office, City Archive, Bookshop and a moving companion.
The fallback map uses the same locations. `prototype/web/hero-world.png` is a
new generated character-free city illustration; `docs/ARTWORK_PROVENANCE.md`
records its origin and pending owner review.

`prototype/web/investigation-reading.js` contains three original fictional,
unreviewed adult-demo practice candidates. `world3d-journey.js` enforces a
three-clue case order, evaluates the selected answer before awarding each clue,
and tracks hints in temporary state. The archive clue also opens the existing
authorized fictional map lesson. A matching server-returned completed session
must contain a nonempty practice response to continue; this does not establish
its correctness or any reading ability. The case resets on reload, sign-out or
profile change and does not store learning data. Lesson interruptions and
withdrawal return the case to a retryable state. The game HUD displays the
casebook, clues, reading prompts and locked locations. No real student data or
child use is supported.

`tools/offline-case-preview.js` is a local-file-only fictional simulator used
solely in a separately packaged review preview. It is not included in the live
web page or deployed server. Tests cover the three-clue case, wrong answers,
hint state, locked destinations, profile/identity changes, stale responses,
missing practice, retry after leaving or withdrawal, optional browser graphics
fallback, and the offline simulator. `docs/INVESTIGATION_CASE.md` records the
scope, provenance and review gates. Automated checks cannot establish teaching
quality, child safety or browser accessibility. The original content and art
need owner and qualified educational review before publication or student use;
there is still no live AI tutor or speech conversation on Render. Real browser,
GPU, touch and screen-reader behavior remain unverified.

Verification: `python3 -m unittest discover -s tests -q` passed 239 tests;
JavaScript syntax checks and `git diff --check` passed. These include mocked
browser, GPU, model and API components rather than real-device validation.
