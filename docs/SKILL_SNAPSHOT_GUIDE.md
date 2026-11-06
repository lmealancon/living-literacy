# Synthetic skill snapshot export and dependency inspection

This is an **experimental, local Python interface for fictional development fixtures only**, not a stable public API, an authorization boundary, or a real skill registry for students. The package contains candidate domain counts but no approved canonical skill definitions; an empty snapshot stays empty. Do not use student data or invent missing definitions.

The existing `SyntheticSkillRegistry` accepts only explicitly supplied draft records and simulated source and author references. After creating a snapshot using synthetic fixtures, a developer can inspect or export it:

```python
from prototype.skill_registry import SyntheticSkillRegistry, verify_snapshot_export

registry = SyntheticSkillRegistry('/path/to/fictional.sqlite3')
# Create the synthetic snapshot with explicitly supplied draft records first.
envelope = registry.export_snapshot('synthetic-snapshot')
validated_snapshot = verify_snapshot_export(envelope)
view = registry.dependency_view('synthetic-snapshot')
```

`export_snapshot` returns a JSON-serializable envelope with a format/version, the immutable snapshot ID, declared synthetic source and author references, unchanged draft records, and a SHA-256 checksum of the canonical payload. The `verify_snapshot_export` function validates the format, checksum, synthetic references and existing draft/graph rules, then returns a detached copy of the snapshot. It does not write or import anything. Separate simulated review decisions are not exported as approvals. This feature does **not** sign data, authenticate authorship, establish provenance or prevent a deliberate edit followed by a recalculated checksum. Protect storage and verify source rights separately before trusting any artifact.

`dependency_view` groups each skill with the strand defined by its domain in the existing candidate manifest and the *explicitly declared* dependencies. Cross-strand flags are descriptive only. They do not impose a blanket prerequisite between word recognition and language comprehension, determine which learner may start an activity, create skill definitions, or make recommendations or mastery claims. A missing dependency, cycle, malformed record, invalid checksum or unsupported export format is rejected; no approved state is inferred.

Actual registry publication, version-policy adjudication (D-017), source identifiers and real educational review remain unresolved. APIs, access controls, data retention, and signatures for real use require further design and review.
