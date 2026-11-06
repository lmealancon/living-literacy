"""Developer-supplied packages remain untrusted synthetic draft data."""
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from prototype.extension_package import (MAX_PACKAGE_BYTES, PACKAGE_FORMAT,
                                         PackageError, parse_package, validate_package)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples' / 'extensions' / 'synthetic-curriculum.json'


def package(kind='curriculum'):
    capabilities = {'curriculum': 'lesson.read', 'narration': 'asset.describe',
                    'assessment': 'form.read'}
    return {'format': PACKAGE_FORMAT,
            'manifest': {'extension_id': 'synthetic.example', 'version': '1.0.0',
                         'contract_version': '0.1', 'kind': kind,
                         'capabilities': [capabilities[kind]], 'data_scope': 'synthetic_only'},
            'records': [{'id': 'synthetic-example', 'version': '1.0.0', 'status': 'draft',
                         'provenance': 'Fictional fixture', 'rights': 'Not assessed',
                         'payload': {'value': 'fictional test'}}]}


class ExtensionPackageTests(unittest.TestCase):
    def test_all_three_kinds_are_offline_draft_only(self):
        for kind in ('curriculum', 'narration', 'assessment'):
            with self.subTest(kind=kind):
                result = parse_package(json.dumps(package(kind)).encode())
                self.assertEqual(result['kind'], kind)
                self.assertEqual(result['records'][0]['status'], 'draft')
                self.assertIn('not content approval', result['notice'])

    def test_untrusted_author_cannot_assert_approval_or_privilege(self):
        for status in ('approved', 'approved_for_prototype', 'published', 'retired'):
            draft = package()
            draft['records'][0]['status'] = status
            with self.subTest(status=status), self.assertRaises(PackageError):
                validate_package(draft)
        for key in ('module', 'command', 'credential', 'url'):
            draft = package()
            draft['manifest'][key] = 'not permitted'
            with self.subTest(key=key), self.assertRaises(PackageError):
                validate_package(draft)
        draft = package()
        draft['manifest']['data_scope'] = 'real_student_data'
        with self.assertRaises(PackageError): validate_package(draft)

    def test_digest_stable_under_key_order_and_changes_when_data_changes(self):
        first = package()
        reordered = json.loads(json.dumps(first, sort_keys=True))
        a, b = validate_package(first), validate_package(reordered)
        self.assertEqual(a['package_sha256'], b['package_sha256'])
        self.assertEqual(a['records'][0]['sha256'], b['records'][0]['sha256'])
        reordered['records'][0]['payload']['value'] = 'another fictional test'
        changed = validate_package(reordered)
        self.assertNotEqual(a['package_sha256'], changed['package_sha256'])
        self.assertNotEqual(a['records'][0]['sha256'], changed['records'][0]['sha256'])

    def test_duplicate_ids_and_json_keys_are_denied(self):
        data = package()
        data['records'].append(deepcopy(data['records'][0]))
        with self.assertRaises(PackageError): validate_package(data)
        raw = json.dumps(package()).replace('"kind": "curriculum"',
                 '"kind": "curriculum", "kind": "narration"')
        with self.assertRaises(PackageError): parse_package(raw.encode())

    def test_limits_and_invalid_numeric_or_text_fail_closed(self):
        with self.assertRaises(PackageError): parse_package(b' ' * (MAX_PACKAGE_BYTES + 1))
        for value in (float('nan'), 1.5, '\ud800'):
            data = package()
            data['records'][0]['payload']['value'] = value
            with self.subTest(value=repr(value)), self.assertRaises(PackageError): validate_package(data)
        data = package()
        obj = data['records'][0]['payload']
        for _ in range(20):
            obj['nested'] = {}
            obj = obj['nested']
        with self.assertRaises(PackageError): validate_package(data)

    def test_example_cli_outputs_hashes_not_payload_or_rights(self):
        result = subprocess.run([sys.executable, '-m', 'prototype.extension_package', str(EXAMPLE)],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report['extension_id'], 'synthetic.example')
        self.assertEqual(len(report['package_sha256']), 64)
        self.assertNotIn('Placeholder data', result.stdout)
        self.assertNotIn('Not evaluated', result.stdout)

    def test_cli_rejects_invalid_package_without_modifying_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'candidate.json'
            original = b'{"records": [{"status": "approved"}]}'
            path.write_bytes(original)
            result = subprocess.run([sys.executable, '-m', 'prototype.extension_package', str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('nothing was imported', result.stderr)
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__': unittest.main()
