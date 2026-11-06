import shutil
import subprocess
import unittest
from pathlib import Path


class InvestigationClientTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for the browserless client harness')
    def test_client_contract(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', 'tests/investigation_client_harness.js'], cwd=root,
                       check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
