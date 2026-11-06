# Synthetic lesson version governance

The local `SyntheticContentRegistry` is a reference component for fictional development records. Its actor IDs are simulated names, not verified identities or reviewer qualifications. The component does not approve content for children or enable production publication; the project release gates and independent human review remain mandatory. It is not an authorization boundary for untrusted users.

`create_draft(content, actor)` inserts an immutable synthetic lesson version in `draft`. An explicit `submit` transition moves that version to `in_review`; a different simulated reviewer must use `approve_prototype`. Only `approved_for_prototype` material is available via `list_for_synthetic_demo` and `for_synthetic_demo`; each validates status, integrity and six-stage shape. `suspend` blocks further delivery and lesson-session writes. `retire` is terminal. Existing historic records remain subject to the separate authorization and retention policies.

`create_revision(lesson_id, parent_version, content, actor)` creates a **new draft version** and records its parent version and source digest. It never changes the source version or inherits its approval. Even when the parent was approved for prototype use, the revision must be submitted and reviewed separately. The new version must carry the same lesson ID, a distinct synthetic version ID, and valid prototype-only content. Tampered, suspended, retired, or missing parent versions fail closed. The revision, lineage record, and audit events are written atomically: if any write fails, none is kept.

`revision_source(lesson_id, version)` returns the recorded parent version and digest for a revision; `audit(lesson_id, version)` lists synthetic workflow events. These entries describe source lineage for a fixture, not ownership, a content license, approval from a qualified reviewer, or verified facts. Rights, provenance, identity and actual review need independent evidence and a production-capable authorization system before distribution to students.

Run the targeted checks with:

```sh
python3 -m unittest discover -s tests -p 'test_content_revisions.py' -v
```
