"""Behavioral tests for fictional, in-memory journey progress."""
import shutil
import subprocess
import unittest
from pathlib import Path


class JourneyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browserless journey harness')
    def test_journey_requires_matching_completed_session(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/world3d_journey_harness.js'], cwd=root,
                       check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
