-- Frozen schema from the synthetic-only v1.0 store, before guardian/consent tables.
CREATE TABLE workspaces(id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='synthetic_family'));
CREATE TABLE identities(id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE);
CREATE TABLE memberships(identity_id TEXT NOT NULL REFERENCES identities(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id), PRIMARY KEY(identity_id,workspace_id));
CREATE TABLE students(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), synthetic INTEGER NOT NULL CHECK(synthetic=1));
CREATE TABLE grants(identity_id TEXT NOT NULL REFERENCES identities(id), student_id TEXT NOT NULL REFERENCES students(id), PRIMARY KEY(identity_id,student_id));
CREATE TABLE lessons(id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(id,version));
CREATE TABLE sessions(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), student_id TEXT NOT NULL REFERENCES students(id), payload TEXT NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE idempotency(workspace_id TEXT NOT NULL, identity_id TEXT NOT NULL, key TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(id), PRIMARY KEY(workspace_id,identity_id,key));
CREATE TABLE session_content_pins(session_id TEXT PRIMARY KEY REFERENCES sessions(id), digest TEXT NOT NULL);
CREATE TABLE audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id), event TEXT NOT NULL, revision INTEGER NOT NULL, actor_id TEXT NOT NULL);
