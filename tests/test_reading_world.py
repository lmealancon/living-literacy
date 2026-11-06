"""Exercise fictional game controls without a browser or real learner data."""
import shutil
import subprocess
import unittest
from pathlib import Path


class ReadingWorldTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browserless game harness')
    def test_keyboard_navigation_pause_and_fallback(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/reading_world_harness.js'], cwd=root, check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
