from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.mlb_data.historical_odds_ingestion import build_mlb_2025_historical_odds_timeline_asset


class TestMLBHistoricalOddsIngestion(unittest.TestCase):
    def test_builds_strict_timeline_when_four_ordered_snapshots_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "mlb.csv"
            src_path = root / "timeline.jsonl"
            out_path = root / "canonical.jsonl"
            qa_path = root / "qa.json"

            pd.DataFrame(
                [
                    {
                        "Date": "2025-04-20",
                        "Start Time (EDT)": "7:10 PM",
                        "Away": "San Diego Padres",
                        "Home": "Houston Astros",
                    }
                ]
            ).to_csv(csv_path, index=False)
            gid = "MLB-2025_04_20-7_10_PM-SAN_DIEGO_PADRES-AT-HOUSTON_ASTROS"
            src_path.write_text(
                json.dumps(
                    {
                        "game_id": gid,
                        "fetched_at": "2025-04-20T22:00:00Z",
                        "odds_history": [
                            {"ts": "2025-04-20T20:00:00Z", "home_ml": -120, "away_ml": 100},
                            {"ts": "2025-04-20T21:00:00Z", "home_ml": -122, "away_ml": 102},
                            {"ts": "2025-04-20T22:15:00Z", "home_ml": -125, "away_ml": 105},
                            {"ts": "2025-04-20T22:45:00Z", "home_ml": -128, "away_ml": 108}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = build_mlb_2025_historical_odds_timeline_asset(
                csv_path=csv_path,
                canonical_output_path=out_path,
                qa_report_path=qa_path,
                local_source_paths=[str(src_path)],
            )

            self.assertEqual(result.total_games, 1)
            self.assertEqual(result.games_strict_valid_count, 1)
            row = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(row["strict_valid"])
            self.assertEqual(row["validation_flags"], [])
            self.assertIsNotNone(row["decision_home_ml"])

    def test_marks_unavailable_when_only_post_start_snapshot_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "mlb.csv"
            src_path = root / "timeline.jsonl"
            out_path = root / "canonical.jsonl"
            qa_path = root / "qa.json"

            pd.DataFrame(
                [
                    {
                        "Date": "2025-04-20",
                        "Start Time (EDT)": "7:10 PM",
                        "Away": "San Diego Padres",
                        "Home": "Houston Astros",
                    }
                ]
            ).to_csv(csv_path, index=False)
            gid = "MLB-2025_04_20-7_10_PM-SAN_DIEGO_PADRES-AT-HOUSTON_ASTROS"
            src_path.write_text(
                json.dumps(
                    {
                        "game_id": gid,
                        "fetched_at": "2025-04-21T01:00:00Z",
                        "odds_history": [{"ts": "2025-04-21T01:00:00Z", "home_ml": -120, "away_ml": 100}],
                    }
                ),
                encoding="utf-8",
            )

            result = build_mlb_2025_historical_odds_timeline_asset(
                csv_path=csv_path,
                canonical_output_path=out_path,
                qa_report_path=qa_path,
                local_source_paths=[str(src_path)],
            )

            self.assertEqual(result.games_strict_valid_count, 0)
            row = json.loads(out_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertFalse(row["strict_valid"])
            self.assertIn("missing_opening", row["validation_flags"])
            self.assertIn("closing_home_ml", row["unavailable_fields"])


if __name__ == "__main__":
    unittest.main()
