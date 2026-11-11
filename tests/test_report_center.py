from __future__ import annotations

import unittest

from wbc_backend.ux.report_center import build_report_center


class TestReportCenter(unittest.TestCase):
    def test_report_center_includes_modes_and_latest_artifacts(self):
        report = build_report_center()
        self.assertIn("BETTING-POOL REPORT CENTER", report)
        self.assertIn("WBC PRODUCTION", report)
        self.assertIn("MLB PAPER / BENCHMARK", report)
        self.assertIn("SPRING TRAINING SANDBOX", report)
        self.assertIn("REPORT CENTER", report)
        self.assertIn("WBC_Review_Meeting_Latest.md", report)
        self.assertIn("Next Step:", report)
        self.assertIn("single-snapshot benchmark", report)
        self.assertIn("Observe and collect spring snapshots", report)


if __name__ == "__main__":
    unittest.main()
