-- Frozen v1.0 synthetic content registry schema; approvals are simulated.
CREATE TABLE content_versions (
 lesson_id TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
 digest TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
 ('draft','in_review','approved_for_prototype','suspended','retired')),
 PRIMARY KEY(lesson_id,version));
CREATE TABLE content_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id TEXT NOT NULL, version TEXT NOT NULL,
 action TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL,
 FOREIGN KEY(lesson_id,version) REFERENCES content_versions(lesson_id,version));
