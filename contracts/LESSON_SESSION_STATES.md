# Lesson session state contract — proposed

States: `created`, `active`, `paused`, `completed`, `abandoned`, `invalidated`, `closed`.

Permitted transitions:
- created -> active, abandoned, invalidated
- active -> paused, completed, abandoned, invalidated
- paused -> active, abandoned, invalidated
- completed -> closed, invalidated
- abandoned -> closed
- invalidated -> closed
- closed -> none

All transitions require server-side authorization, revision checking, immutable approved lesson version, and auditable actor/time/reason. `completed` is NOT mastery. Responses require assistance provenance, task conditions and timestamps. An independent task with disqualifying audio/modeling assistance must not be eligible as independent evidence.
