from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.mlb_data.context_connectors import (
    get_bullpen_usage_last_3d,
    get_confirmed_lineups,
    get_injury_rest_status,
    get_odds_timeline,
    get_weather_wind,
    load_connectors,
    record_age_hours,
)


class TestMLBContextConnectorsContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game_id = "MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS"

        (self.root / "lineups.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "game_id": self.game_id,
                            "confirmed_home_starter": "Old Starter",
                            "confirmed_away_starter": "Old Away",
                            "confirmed_home_lineup": ["a"],
                            "confirmed_away_lineup": ["b"],
                            "fetched_at": "2026-03-18T10:00:00Z",
                        }
                    ),
                    json.dumps(
                        {
                            "game_id": self.game_id,
                            "confirmed_home_starter": "New Starter",
                            "confirmed_away_starter": "New Away",
                            "confirmed_home_lineup": ["a1", "a2"],
                            "confirmed_away_lineup": ["b1", "b2"],
                            "fetched_at": "2026-03-18T12:00:00Z",
                            "home_away_splits": {"home_wrc_plus": 110},
                            "platoon_splits": {"home_vs_rhp_woba": 0.325},
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )
        (self.root / "bullpen_usage_3d.jsonl").write_text(
            json.dumps(
                {
                    "game_id": self.game_id,
                    "bullpen_usage_last_3d_home": 82,
                    "bullpen_usage_last_3d_away": 101,
                    "fetched_at": "2026-03-18T12:30:00Z",
                }
            ),
            encoding="utf-8",
        )
        (self.root / "odds_timeline.jsonl").write_text(
            json.dumps(
                {
                    "game_id": self.game_id,
                    "opening_home_ml": -120,
                    "opening_away_ml": 100,
                    "current_home_ml": -128,
                    "current_away_ml": 108,
                    "closing_home_ml": -132,
                    "closing_away_ml": 112,
                    "odds_history": [{"ts": "2026-03-18T11:00:00Z", "home_ml": -120}],
                    "fetched_at": "2026-03-18T12:40:00Z",
                }
            ),
            encoding="utf-8",
        )
        (self.root / "weather_wind.jsonl").write_text(
            json.dumps(
                {
                    "game_id": self.game_id,
                    "weather": {"temp_f": 58, "condition": "clear"},
                    "wind": {"mph": 9, "direction": "out_to_rf"},
                    "park_factors": {"run_factor": 1.02},
                    "fetched_at": "2026-03-18T12:20:00Z",
                }
            ),
            encoding="utf-8",
        )
        (self.root / "injury_rest.jsonl").write_text(
            json.dumps(
                {
                    "game_id": self.game_id,
                    "injury_report": {"home_out": ["X"]},
                    "rest_days_home": 1,
                    "rest_days_away": 0,
                    "fetched_at": "2026-03-18T12:10:00Z",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_and_mapping(self):
        bundle = load_connectors(self.root)
        lineups = get_confirmed_lineups(bundle, self.game_id)
        bullpen = get_bullpen_usage_last_3d(bundle, self.game_id)
        odds = get_odds_timeline(bundle, self.game_id)
        weather = get_weather_wind(bundle, self.game_id)
        injury = get_injury_rest_status(bundle, self.game_id)

        self.assertIn("confirmed_home_lineup", lineups)
        self.assertIn("bullpen_usage_last_3d_home", bullpen)
        self.assertIn("odds_history", odds)
        self.assertIn("weather", weather)
        self.assertIn("injury_report", injury)

    def test_duplicate_latest_wins(self):
        bundle = load_connectors(self.root)
        lineups = get_confirmed_lineups(bundle, self.game_id)
        self.assertEqual(lineups["confirmed_home_starter"], "New Starter")
        self.assertEqual(lineups["fetched_at"], "2026-03-18T12:00:00Z")

    def test_missing_game_id_behavior(self):
        bundle = load_connectors(self.root)
        missing = get_confirmed_lineups(bundle, "MLB-NOT-EXIST")
        self.assertEqual(missing, {})

    def test_timestamp_consistency(self):
        bundle = load_connectors(self.root)
        odds = get_odds_timeline(bundle, self.game_id)
        age = record_age_hours(odds)
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0.0)


if __name__ == "__main__":
    unittest.main()
