"""Run the real 3D engine and landmark labels together with mocked graphics."""
from pathlib import Path
import shutil
import subprocess
import unittest


class SignsIntegrationTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the browserless harness')
    def test_labels_follow_the_real_camera_and_hide_on_graphics_loss(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/world3d_signs_integration_harness.js'],
                       cwd=root, check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
