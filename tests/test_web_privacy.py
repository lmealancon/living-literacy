"""Run browserless UI behavior checks when Node is available.

This exercises asynchronous privacy clearing and assistance selection; it is
not a substitute for real-browser, accessibility, or cross-origin testing.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebPrivacyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for browserless JavaScript checks')
    def test_account_switch_and_explicit_assistance(self):
        result = subprocess.run(['node', 'tests/web_privacy_harness.js'], cwd=ROOT,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Web privacy and assistance checks passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
