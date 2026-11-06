"""Browserless checks for the world controls and their safe navigation fallback."""
import shutil
import subprocess
import unittest
from pathlib import Path


class World3DUIHarnessTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the browserless UI harness')
    def test_world_controls(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/world3d_ui_harness.js'], cwd=root, check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
