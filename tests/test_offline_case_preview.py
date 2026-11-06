"""Exercise the offline simulator through the original fictional case."""
import subprocess
import unittest
from pathlib import Path


class OfflinePreviewTests(unittest.TestCase):
    def test_fictional_offline_case_can_be_solved_without_network(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/offline_case_preview_harness.js'], cwd=root,
                       check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
