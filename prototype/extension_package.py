"""Offline validation of data-only synthetic extension packages.

This is not an extension loader, content importer, network API, sandbox, or
approval mechanism. The manifest and all record content are untrusted claims.
Never use this validator as authorization to process real learner data or to
publish instructional content. The format is experimental and may change.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from prototype.extension_contracts import ExtensionContractError, parse_manifest

MAX_PACKAGE_BYTES = 1024 * 1024
MAX_RECORDS = 100
MAX_DEPTH = 12
MAX_NODES = 20000
PACKAGE_FORMAT = 'living-literacy.synthetic-extension-package.v0.1'
_RECORD_FIELDS = frozenset({'id', 'version', 'status', 'provenance', 'rights', 'payload'})
_ID = re.compile(r'^synthetic-[a-z0-9]+(?:[-.][a-z0-9]+)*$')
_VERSION = re.compile(r'^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$')


class PackageError(ValueError):
    """Untrusted package is malformed or exceeds an experimental limit."""


def _fail():
    raise PackageError('Invalid synthetic extension package')


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackageError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_number(_value):
    raise PackageError('Invalid JSON number')


def _check_tree(value, depth=0, count=None):
    """Bound nested values before computing a digest; reject non-JSON values."""
    if count is None:
        count = [0, 0]
    count[0] += 1
    if count[0] > MAX_NODES or depth > MAX_DEPTH:
        _fail()
    if isinstance(value, str):
        try:
            count[1] += len(value.encode('utf-8'))
        except UnicodeError as exc:
            raise PackageError('Invalid UTF-8 text') from exc
        if count[1] > MAX_PACKAGE_BYTES:
            _fail()
        return
    if value is None or isinstance(value, (bool, int)):
        return
    # Reject float values, including nan/inf, to ensure cross-runtime hash
    # consistency. Assessment scoring and numeric interpretations are not here.
    if isinstance(value, list):
        for child in value:
            _check_tree(child, depth + 1, count)
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail()
            _check_tree(key, depth + 1, count)
            _check_tree(child, depth + 1, count)
        return
    _fail()


def _digest(value):
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False)
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError('Invalid synthetic extension package') from exc


def validate_package(raw):
    """Validate and summarize untrusted JSON without storing or executing it.

    Caller-supplied provenance and rights are claims, not verified evidence.
    Output digests are reproducibility aids, not signatures or approval.
    """
    if not isinstance(raw, dict) or set(raw) != {'format', 'manifest', 'records'}:
        _fail()
    if raw['format'] != PACKAGE_FORMAT:
        _fail()
    try:
        manifest = parse_manifest(raw['manifest'])
    except ExtensionContractError as exc:
        raise PackageError('Invalid package manifest') from exc
    records = raw['records']
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        _fail()
    _check_tree(raw)
    seen = set()
    summaries = []
    for record in records:
        if not isinstance(record, dict) or set(record) != _RECORD_FIELDS:
            _fail()
        ident, version = record['id'], record['version']
        if (not isinstance(ident, str) or len(ident) > 100 or not _ID.fullmatch(ident)
                or not isinstance(version, str) or len(version) > 32 or not _VERSION.fullmatch(version)
                or record['status'] not in ('draft', 'needs_expert_review')):
            _fail()
        if (ident, version) in seen:
            _fail()
        seen.add((ident, version))
        for key in ('provenance', 'rights'):
            item = record[key]
            if not isinstance(item, str) or not 1 <= len(item.strip()) <= 500:
                _fail()
        if not isinstance(record['payload'], dict):
            _fail()
        summaries.append({'id': ident, 'version': version, 'status': record['status'],
                          'sha256': _digest(record)})
    return {'format': PACKAGE_FORMAT, 'extension_id': manifest.extension_id,
            'extension_version': manifest.version, 'kind': manifest.kind,
            'records': summaries, 'package_sha256': _digest(raw),
            'notice': 'Synthetic draft only; validation is not content approval.'}


def parse_package(data):
    """Parse bounded UTF-8 JSON while rejecting duplicate keys and non-finite numbers."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_PACKAGE_BYTES:
        _fail()
    try:
        raw = json.loads(data.decode('utf-8'), object_pairs_hook=_object_pairs,
                         parse_constant=_invalid_number)
        return validate_package(raw)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, PackageError):
            raise
        raise PackageError('Invalid synthetic extension package') from exc


def main():
    parser = argparse.ArgumentParser(description='Inspect a synthetic-only extension package without importing it')
    parser.add_argument('package', type=Path, help='Local JSON package; must not contain real student data')
    args = parser.parse_args()
    try:
        with args.package.open('rb') as source:
            data = source.read(MAX_PACKAGE_BYTES + 1)
        report = parse_package(data)
    except (OSError, PackageError):
        print('Package validation failed; nothing was imported.', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
