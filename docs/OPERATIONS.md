# Operations: synthetic prototype only

The Python/SQLite application is a development prototype. It is not a production service and is not approved for real student information. Keep it on a trusted local machine; do not expose the existing local web server to the internet. Its shared fixture token and session are not suitable for multiple users, and the demo database is temporary.

## Run and verify locally

From the project root, using Python 3 and its standard library:

```sh
python3 -m unittest discover -s tests -q
python3 scripts/validate_registry.py
python3 -m prototype.local_web
```

Open `http://127.0.0.1:8765` on the same machine. Stop the server with Ctrl+C. The demo creates a temporary SQLite database and removes it at shutdown, so its activity is not durable. A successful registry check still reports the missing canonical skill definitions. The test output, not this document, is the source of truth for the current result.

## SQLite backup and restore for synthetic development databases

These instructions apply only to a separately managed, file-backed synthetic SQLite database, not the ephemeral demo database. A database can contain fixture tokens, credentials, and responses; store backups in a restricted location and follow the environment's access rules. Do not commit databases, backups, credentials, or environment secrets to source control.

Use SQLite's online backup API instead of copying a database file while it may be in use. The following command creates a new backup and refuses to overwrite an existing file. Replace the example paths. The target directory must already exist.

```sh
python3 - /path/to/synthetic.sqlite /path/to/new-backup.sqlite <<'PY'
import sqlite3
import sys
from pathlib import Path

source = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
if not source.is_file():
    raise SystemExit('Source database does not exist')
if target.exists():
    raise SystemExit('Target already exists; choose a new path')
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        result = dst.execute('PRAGMA integrity_check').fetchone()[0]
        if result != 'ok':
            raise SystemExit('Backup integrity check failed: ' + result)
print('Backup created and SQLite integrity check passed')
PY
```

For a restore drill, run the same command with the backup as the source and a **new** temporary path as the target. Open the restored copy with the application in an isolated synthetic environment and verify expected records, authorization denial, and content-withdrawal behavior. An integrity check alone does not verify application correctness. Do not replace an active database; any production cutover or destructive restore needs an independently reviewed procedure and explicit authorization. If a backup command fails, inspect and remove only its incomplete target when it is safe to do so.

No automated backup schedule, retention policy, encrypted backup store, or tested recovery objective is established by this prototype. Record actual restore-drill results before claiming recoverability.

## Deployment and release blockers

A restricted synthetic Render staging instance has been set up separately; it is not a production deployment and its free-tier filesystem is ephemeral. The local changes documented here are not necessarily deployed there. Before hosting a service for real families, select and review managed identity, database, private object storage and infrastructure vendors; design and test isolation, encryption, monitoring, rate limits, backups, incident handling and rollback; complete legal and privacy reviews; and independently verify guardian authority and consent. Migrate to a reviewed production database design with transactional migrations and tenant isolation. The synthetic SQLite credentials and simulated reviewer identifiers cannot supply those controls.

Student-facing content requires qualified independent approval and licensed assets. Canonical skills and assessment thresholds remain unresolved. Paid tiers and provider integrations require reviewed terms and verified webhook handling before live charges. Follow `specs/RELEASE_GATES.md` and `docs/DECISION_REGISTER.md`; capture human approvals, test results, accessibility findings, backup/restore evidence, and unresolved risks. Never describe a synthetic prototype or an unverified deployment as production-ready.

## Synthetic SQLite migrations

The explicit migration command supports the current synthetic prototype schema and an opt-in path for a specifically recognized v1.0 synthetic schema. It does not migrate arbitrary older, partial, or unrecognized schemas, or PostgreSQL. Back up the stopped database first using the procedure above; then run:

```sh
python3 -m prototype.migrations --db /path/to/synthetic.sqlite3
```

If the database was created by the original v1.0 prototype and does not yet have guardian-relationship or consent tables, opt into the separate upgrade explicitly:

```sh
python3 -m prototype.migrations --db /path/to/synthetic.sqlite3 --from-legacy-v1
```

The legacy upgrade accepts only the frozen known v1.0 table structures, optional matching v1 content tables, and no unexpected tables, views or triggers. It creates **empty** guardian-relationship and consent tables; legacy grants and tokens do not imply authority, so protected records remain inaccessible until a separately authorized migration or manual review is designed. Do not work around this deny-by-default behavior. It preserves existing students, lesson sessions, content and audit history, then adds the same indexes in one transaction. A partial schema, unrecognized object, or foreign-key error is rejected and rolled back. The opt-in is one-time: use the normal migration command after a successful upgrade.

The tool records checksummed migration history and fails closed on mismatches or foreign-key violations. Its first migration adds indexes; it does not backfill guardian relationships, grants or consent. Re-running a successfully migrated database with the normal command applies nothing. Restore the backup if needed; the tool does not provide automatic downgrades. A successful migration is not authorization for real student data.
