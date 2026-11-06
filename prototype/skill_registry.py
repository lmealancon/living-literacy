"""Synthetic-only, immutable skill inventory snapshots; not an approval service.

The source package contains no canonical skill definitions. This module never
creates them and never confers instructional, scientific, or release approval.
Snapshots accept explicitly supplied *draft* records only. Caller-controlled
review labels are simulation metadata, not verified reviewer identity.
"""
import json
import hashlib
import hmac
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from prototype.lesson_engine import PolicyError

_ROOT = Path(__file__).resolve().parents[1]
_DOMAINS = {item['code']: item for item in json.loads(
    (_ROOT / 'registry' / 'DOMAIN_MANIFEST.json').read_text(encoding='utf-8'))['domains']}
_ID = re.compile(r'^[A-Z]{2}-[0-9]{3}$')
_VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_EXPORT_FORMAT = 'living-literacy.synthetic-skill-snapshot'
_REQUIRED = {'skill_id', 'version', 'domain_code', 'name', 'observable_behavior',
             'instructional_routine_id', 'status', 'prerequisite_skill_ids',
             'eligible_evidence', 'review'}
_ALLOWED = _REQUIRED | {'related_skill_ids', 'examples', 'adjudication_ref'}
_SCHEMA = '''
CREATE TABLE IF NOT EXISTS skill_snapshots (
 snapshot_id TEXT PRIMARY KEY, source_ref TEXT NOT NULL, author_ref TEXT NOT NULL,
 records_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skill_snapshot_reviews (
 snapshot_id TEXT NOT NULL REFERENCES skill_snapshots(snapshot_id),
 reviewer_ref TEXT NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('request_changes','approve_synthetic_review')),
 note TEXT NOT NULL, PRIMARY KEY(snapshot_id, reviewer_ref)
);
'''


def _invalid():
    raise PolicyError('INVALID_SYNTHETIC_SKILL_SNAPSHOT')


def _fixture_ref(value):
    return isinstance(value, str) and value.startswith('synthetic-') and len(value) > len('synthetic-')


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _validate(records):
    if not isinstance(records, list): _invalid()
    graph = {}
    for item in records:
        if not isinstance(item, dict) or not _REQUIRED <= item.keys() or not item.keys() <= _ALLOWED: _invalid()
        sid, version, domain = item['skill_id'], item['version'], item['domain_code']
        if not isinstance(sid, str) or not _ID.fullmatch(sid): _invalid()
        if sid in graph or not isinstance(version, str) or not _VERSION.fullmatch(version): _invalid()
        if not isinstance(domain, str) or domain not in _DOMAINS or sid[:2] != domain: _invalid()
        if not isinstance(item['name'], str) or len(item['name']) < 3: _invalid()
        if not isinstance(item['observable_behavior'], str) or len(item['observable_behavior']) < 20: _invalid()
        if not isinstance(item['instructional_routine_id'], str) or not item['instructional_routine_id']: _invalid()
        # Import must not turn unverified records into approved content.
        if item['status'] not in ('draft', 'needs_expert_review'): _invalid()
        deps = item['prerequisite_skill_ids']
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps) or len(deps) != len(set(deps)): _invalid()
        evidence = item['eligible_evidence']
        if not isinstance(evidence, list): _invalid()
        for rule in evidence:
            if not isinstance(rule, dict) or any(not isinstance(rule.get(k), str) or not rule[k]
                 for k in ('task_condition', 'response_type', 'assistance_rule')): _invalid()
        review = item['review']
        if not isinstance(review, dict) or any(k not in review or review[k] is not None for k in ('reviewer_ref','decision_ref','decision_date')): _invalid()
        for key in ('related_skill_ids', 'examples'):
            if key in item and (not isinstance(item[key], list) or any(not isinstance(v, str) for v in item[key])): _invalid()
        if 'related_skill_ids' in item and len(item['related_skill_ids']) != len(set(item['related_skill_ids'])): _invalid()
        if 'adjudication_ref' in item and item['adjudication_ref'] is not None and not isinstance(item['adjudication_ref'], str): _invalid()
        graph[sid] = deps
    if any(dep not in graph for deps in graph.values() for dep in deps): _invalid()
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting: _invalid()
        if node in visited: return
        visiting.add(node)
        for dep in graph[node]: visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph: visit(node)


def verify_snapshot_export(envelope):
    """Validate and return an exported fictional snapshot without importing it.

    Its checksum detects accidental changes, not a malicious rewrite or proof
    of authorship. No review, educational approval or data access is implied.
    """
    if not isinstance(envelope, dict) or set(envelope) != {'payload', 'sha256'}:
        _invalid()
    payload, checksum = envelope['payload'], envelope['sha256']
    if (not isinstance(checksum, str) or not _SHA256.fullmatch(checksum)
            or not isinstance(payload, dict) or set(payload) != {'format', 'format_version', 'snapshot'}
            or payload['format'] != _EXPORT_FORMAT or type(payload['format_version']) is not int
            or payload['format_version'] != 1):
        _invalid()
    try:
        encoded = _canonical(payload).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _invalid()
    if not hmac.compare_digest(checksum, hashlib.sha256(encoded).hexdigest()):
        _invalid()
    snapshot = payload['snapshot']
    if (not isinstance(snapshot, dict) or set(snapshot) != {'snapshot_id', 'source_ref', 'author_ref', 'records'}
            or not all(_fixture_ref(snapshot[key]) for key in ('snapshot_id', 'source_ref', 'author_ref'))):
        _invalid()
    _validate(snapshot['records'])
    # Return a deep copy: callers cannot change the verified envelope by alias.
    return json.loads(_canonical(snapshot))


class SyntheticSkillRegistry:
    """Persistence for fictional, self-contained inventory snapshots only.

    Each snapshot has one version per skill ID; cross-snapshot version resolution
    and dependency semantics remain subject to decision D-017. No prerequisite
    gates or automated recommendations are applied by this class.
    """
    def __init__(self, filename):
        self.filename = str(filename)
        with self._connect() as db: db.executescript(_SCHEMA)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.filename)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_snapshot(self, snapshot_id, source_ref, author_ref, records):
        if not all(_fixture_ref(v) for v in (snapshot_id, source_ref, author_ref)): _invalid()
        _validate(records)
        payload = _canonical(records)
        try:
            with self._connect() as db:
                db.execute('INSERT INTO skill_snapshots VALUES (?,?,?,?)', (snapshot_id, source_ref, author_ref, payload))
        except sqlite3.IntegrityError as exc:
            raise PolicyError('SNAPSHOT_ALREADY_EXISTS') from exc

    def get_snapshot(self, snapshot_id):
        with self._connect() as db:
            row = db.execute('SELECT source_ref,author_ref,records_json FROM skill_snapshots WHERE snapshot_id=?', (snapshot_id,)).fetchone()
        if row is None: raise PolicyError('RESOURCE_NOT_FOUND')
        return {'snapshot_id': snapshot_id, 'source_ref': row[0], 'author_ref': row[1], 'records': json.loads(row[2])}

    def export_snapshot(self, snapshot_id):
        """Export a validated, version-pinned fixture, without executing providers.

        The content remains a draft. Separate simulated reviews are deliberately
        excluded: their presence does not constitute instructional approval.
        """
        try:
            snapshot = self.get_snapshot(snapshot_id)
            payload = {'format': _EXPORT_FORMAT, 'format_version': 1, 'snapshot': snapshot}
            envelope = {'payload': payload, 'sha256': hashlib.sha256(_canonical(payload).encode('utf-8')).hexdigest()}
            verify_snapshot_export(envelope)
            return envelope
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise PolicyError('INVALID_SYNTHETIC_SKILL_SNAPSHOT') from exc

    def dependency_view(self, snapshot_id):
        """Inspect only explicitly declared draft dependencies, with no gating.

        Strand labels come from the supplied domain manifest. A cross-strand
        edge identifies only the declaration; it imposes no strand-wide lock
        and does not determine eligibility or make a recommendation.
        """
        snapshot = verify_snapshot_export(self.export_snapshot(snapshot_id))
        by_id = {record['skill_id']: record for record in snapshot['records']}
        items = []
        for sid in sorted(by_id):
            record = by_id[sid]
            strand = _DOMAINS[record['domain_code']]['strand']
            dependencies = []
            for dep_id in sorted(record['prerequisite_skill_ids']):
                dep_strand = _DOMAINS[by_id[dep_id]['domain_code']]['strand']
                dependencies.append({'skill_id': dep_id, 'strand': dep_strand,
                                     'cross_strand': dep_strand != strand})
            items.append({'skill_id': sid, 'version': record['version'], 'status': record['status'],
                          'strand': strand, 'declared_dependencies': dependencies})
        return {'snapshot_id': snapshot['snapshot_id'], 'skills': items,
                'note': 'Draft declarations only; no eligibility, mastery, or recommendation is inferred.'}

    def record_synthetic_review(self, snapshot_id, reviewer_ref, decision, note):
        if not isinstance(reviewer_ref, str) or not reviewer_ref.startswith('synthetic-') or len(reviewer_ref) <= len('synthetic-'): _invalid()
        if decision not in ('request_changes', 'approve_synthetic_review') or not isinstance(note, str) or not note.strip(): _invalid()
        with self._connect() as db:
            row = db.execute('SELECT author_ref FROM skill_snapshots WHERE snapshot_id=?', (snapshot_id,)).fetchone()
            if row is None: raise PolicyError('RESOURCE_NOT_FOUND')
            if row[0] == reviewer_ref: raise PolicyError('SELF_REVIEW_FORBIDDEN')
            try:
                db.execute('INSERT INTO skill_snapshot_reviews VALUES (?,?,?,?)', (snapshot_id, reviewer_ref, decision, note.strip()))
            except sqlite3.IntegrityError as exc:
                raise PolicyError('REVIEW_ALREADY_EXISTS') from exc
