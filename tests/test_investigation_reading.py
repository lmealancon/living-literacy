"""Checks for unreviewed fictional reading-practice candidates."""
import shutil
import subprocess
import unittest
from pathlib import Path


class InvestigationReadingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browserless reading harness')
    def test_original_synthetic_challenges_and_feedback(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/investigation_reading_harness.js'],
                       cwd=root, check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
