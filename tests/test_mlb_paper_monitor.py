from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.research.mlb_paper_monitor import run_mlb_paper_tracking_monitor


class TestMLBPaperMonitor(unittest.TestCase):
    def test_mlb_paper_tracking_report_has_governance_and_trend_blocks(self):
        out_path = "data/wbc_backend/reports/mlb_paper_tracking_report_test.json"
        summary = run_mlb_paper_tracking_monitor(output_path=out_path)
        self.assertEqual(summary.status, "OK")

        payload = json.loads(open(out_path, "r", encoding="utf-8").read())
        self.assertIn("report_summary", payload)
        self.assertIn("report_header", payload)
        self.assertEqual(payload["report_header"]["mode"], "PAPER_ONLY")
        self.assertEqual(payload["report_header"]["safety"], "NO LIVE BETTING")
        self.assertEqual(payload["report_summary"]["mode"], "PAPER_ONLY")
        self.assertEqual(payload["report_summary"]["safety"], "NO LIVE BETTING")
        self.assertEqual(payload["governance_visibility"]["execution_mode"], "PAPER_ONLY")
        self.assertEqual(payload["governance_visibility"]["clv_mode"], "SANDBOX_ONLY")
        self.assertEqual(payload["governance_visibility"]["decision_quality_scale"], "UNAVAILABLE")
        self.assertIn("weekly_tracking", payload)
        self.assertIn("monthly_tracking", payload)
        self.assertIn("trend_monitoring", payload)
        self.assertIn("regime_monitoring", payload)
        self.assertEqual(payload["frozen_recommendation"], "KEEP_MLB_FROZEN")
        self.assertGreaterEqual(len(payload["regime_monitoring"]["summary"]), 1)


if __name__ == "__main__":
    unittest.main()
