# The Vanishing Storybook: synthetic case notes

This original fictional case is set in an imagined Victorian London. The
environment, characters, narrative and reading prompts are newly created for
Living Literacy; they are not adaptations of a particular Sherlock Holmes
story or copied game assets. The illustration's origin and pending review are
recorded in `ARTWORK_PROVENANCE.md`.

An adult using fictional data signs in and visits the Post Office, the City
Archive and the Bookshop. Each stop offers an original, unreviewed reading
practice candidate in `prototype/web/investigation-reading.js`. Correct choices
unlock the next clue; hint exposure is recorded before the hint is shown.
After the archive clue, the existing fictional map lesson must also return a
completed session containing the existing target word “map” as a practice-stage
response. This fixed game rule does not establish reading mastery. The third clue resolves the
fictional case.

The synthetic server stores case state per authorized fictional identity and
profile, and rechecks relationship and lesson consent on each read or mutation.
It can resume after a page reload while its database remains available. The free
Render staging service uses a temporary database, so all progress is lost on
restart or spin-down. This is not a secure assessment, an evidence record, or a
measure of reading level. The lesson
continues to use the existing server-side identity, relationship, consent,
content version and withdrawal checks. When a lesson is abandoned or becomes
unavailable, the case returns to the activity step rather than becoming stuck.
The adult-only offline review preview uses a separate in-memory simulator and
must not be deployed as the real server. The case table is created and checked
transactionally by the synthetic store; explicit migration 2 can create it or
adopt an exact existing table into the ledger. Legacy databases require the
documented migration before enabling it. Case
prompt fixtures are not yet integrated into the content governance registry and
cannot be withdrawn individually.

The case, art, learning prompts and hints are unreviewed candidates. Owner,
qualified educational and accessibility review, a content licensing decision,
real identity and privacy safeguards, and broader testing are required before
children use them or the new content is published. There is no live AI tutor
or microphone conversation on the existing Render deployment.
