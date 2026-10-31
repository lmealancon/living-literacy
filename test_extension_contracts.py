"""The manifest boundary accepts metadata; it does not load providers."""
import unittest

from prototype.extension_contracts import ExtensionContractError, parse_manifest


def manifest(kind='curriculum'):
    return {'extension_id': 'synthetic.example', 'version': '1.0.0',
            'contract_version': '0.1', 'kind': kind,
            'capabilities': [{'curriculum': 'lesson.read',
                              'narration': 'asset.describe',
                              'assessment': 'form.read'}[kind]],
            'data_scope': 'synthetic_only'}


class ExtensionContractTests(unittest.TestCase):
    def test_each_declared_kind_can_be_validated_without_import(self):
        for kind in ('curriculum', 'narration', 'assessment'):
            with self.subTest(kind=kind):
                parsed = parse_manifest(manifest(kind))
                self.assertEqual(parsed.kind, kind)
                self.assertIsInstance(parsed.capabilities, tuple)

    def test_mismatched_capability_and_undeclared_permission_are_denied(self):
        for capabilities in (['asset.describe'], ['lesson.read', 'student.write'], [], ['lesson.read', 'lesson.read']):
            data = manifest()
            data['capabilities'] = capabilities
            with self.subTest(capabilities=capabilities), self.assertRaises(ExtensionContractError):
                parse_manifest(data)

    def test_unrecognized_fields_cannot_smuggle_loader_or_secrets(self):
        for key in ('module', 'command', 'credential', 'url'):
            data = manifest()
            data[key] = 'untrusted'
            with self.subTest(key=key), self.assertRaises(ExtensionContractError):
                parse_manifest(data)

    def test_version_and_scope_fail_closed(self):
        for key, value in [('contract_version', '2.0'), ('version', 'latest'),
                           ('data_scope', 'production'), ('kind', 'unknown')]:
            data = manifest()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ExtensionContractError):
                parse_manifest(data)

    def test_missing_and_wrong_types_are_rejected(self):
        for bad in (None, [], {'extension_id': 'synthetic.x'}):
            with self.subTest(bad=bad), self.assertRaises(ExtensionContractError):
                parse_manifest(bad)
        data = manifest()
        data['capabilities'] = [None]
        with self.assertRaises(ExtensionContractError):
            parse_manifest(data)

    def test_parsed_capabilities_are_not_mutable_through_input(self):
        data = manifest()
        parsed = parse_manifest(data)
        data['capabilities'].append('student.write')
        self.assertEqual(parsed.capabilities, ('lesson.read',))


if __name__ == '__main__':
    unittest.main()
