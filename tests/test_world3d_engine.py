"""Smoke-test the synthetic 3D engine and its WebGL fallback with a mock GPU."""
import shutil
import subprocess
import unittest
from pathlib import Path


class World3DEngineTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the browserless harness')
    def test_mock_webgl_movement_and_fallback(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/world3d_engine_harness.js'], cwd=root, check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
