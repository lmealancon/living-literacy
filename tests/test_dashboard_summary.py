"""Exercise dashboard data rendering with a simulated DOM and fetch boundary."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DashboardSummaryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for dashboard browserless checks')
    def test_activity_counts_domains_and_account_isolation(self):
        result = subprocess.run(['node', 'tests/dashboard_summary_harness.js'], cwd=ROOT,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Dashboard summary checks passed', result.stdout)
