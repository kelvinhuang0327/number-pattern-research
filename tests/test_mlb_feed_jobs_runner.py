from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.mlb_data.feed_jobs import run_all_feed_jobs


class TestMLBFeedJobsRunner(unittest.TestCase):
    def test_run_all_feed_jobs_outputs_files_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "mlb_context"
            summary = run_all_feed_jobs(
                csv_path="data/mlb_2025/mlb_odds_2025_real.csv",
                output_dir=out,
            )
            self.assertIn("feeds", summary)
            self.assertIn("source_audit", summary)
            self.assertIn("strict_validation_recovery", summary)
            self.assertIn("feed_impact_tracking", summary)
            self.assertEqual(len(summary["feeds"]), 5)
            files = {
                "lineups.jsonl",
                "bullpen_usage_3d.jsonl",
                "odds_timeline.jsonl",
                "weather_wind.jsonl",
                "injury_rest.jsonl",
            }
            self.assertTrue(files.issubset({p.name for p in out.glob("*.jsonl")}))
            for feed in summary["feeds"]:
                self.assertIn("total_records_written", feed)
                self.assertIn("missing_required_field_count", feed)
            self.assertEqual(len(summary["feed_impact_tracking"]), 5)


if __name__ == "__main__":
    unittest.main()
