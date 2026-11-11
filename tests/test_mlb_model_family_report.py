from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.backtesting.mlb_report import run_mlb_model_family_report


class TestMLBModelFamilyReport(unittest.TestCase):
    def test_moneyline_report_fields(self):
        report = run_mlb_model_family_report()
        self.assertEqual(report.moneyline_strict.model_name, "mlb_moneyline")
        self.assertEqual(report.moneyline_research.model_name, "mlb_moneyline")
        self.assertGreaterEqual(report.strict_valid_rate, 0.0)
        self.assertLessEqual(report.strict_valid_rate, 1.0)
        self.assertIn(report.f5_moneyline["status"], {"ready", "rejected"})
        self.assertIn(report.team_total["status"], {"ready", "blocked"})


if __name__ == "__main__":
    unittest.main()
