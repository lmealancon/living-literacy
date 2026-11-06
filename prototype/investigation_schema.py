"""Frozen SQLite schema for the fictional investigation fixture.

Keep this DDL immutable: it is used by migration 2's recorded checksum.
Future schema changes require a new migration, not editing this definition.
"""

CASE_PROGRESS_TABLE = 'synthetic_case_progress'
CASE_PROGRESS_CREATE_SQL = '''CREATE TABLE synthetic_case_progress (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    student_id TEXT NOT NULL REFERENCES students(id),
    identity_id TEXT NOT NULL REFERENCES identities(id),
    case_id TEXT NOT NULL,
    step TEXT NOT NULL CHECK(step IN ('post_office','decode','archive','context','lesson','lesson_active','bookshop','sequence','solved')),
    revision INTEGER NOT NULL CHECK(revision >= 0),
    decode_hint INTEGER NOT NULL CHECK(decode_hint IN (-1,0,1)),
    context_hint INTEGER NOT NULL CHECK(context_hint IN (-1,0,1)),
    sequence_hint INTEGER NOT NULL CHECK(sequence_hint IN (-1,0,1)),
    pending_hint INTEGER NOT NULL CHECK(pending_hint IN (0,1)),
    session_id TEXT REFERENCES sessions(id),
    PRIMARY KEY(workspace_id,student_id,identity_id,case_id)
)'''
