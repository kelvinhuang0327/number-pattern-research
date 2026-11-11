from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.mlb_data.context_connectors import is_stale_record, load_connectors
from wbc_backend.mlb_data.external_sources import fetch_and_materialize_external_context
from wbc_backend.mlb_data.ids import make_mlb_game_id
import wbc_backend.mlb_data.external_sources as ext


class TestMLBExternalConnectors(unittest.TestCase):
    def test_stale_detection(self):
        now = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)
        fresh = {"fetched_at": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")}
        stale = {"fetched_at": (now - timedelta(hours=30)).isoformat().replace("+00:00", "Z")}
        self.assertFalse(is_stale_record(fresh, now_utc=now))
        self.assertTrue(is_stale_record(stale, now_utc=now))
        self.assertTrue(is_stale_record({}, now_utc=now))

    def test_external_materialization_mapping_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "mlb.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Date", "Start Time (EDT)", "Away", "Home", "Home ML", "Away ML"])
                writer.writeheader()
                writer.writerow(
                    {
                        "Date": "2025-03-18",
                        "Start Time (EDT)": "6:10 PM",
                        "Away": "New York Mets",
                        "Home": "Los Angeles Dodgers",
                        "Home ML": "-125",
                        "Away ML": "+115",
                    }
                )

            gid = make_mlb_game_id("2025-03-18", "6:10 PM", "NEW YORK METS", "LOS ANGELES DODGERS")
            saved_schedule = ext._schedule_games
            saved_http = ext._safe_http_json
            saved_odds = ext._fetch_odds_timeline
            try:
                ext._schedule_games = lambda _s, _e: [  # type: ignore[assignment]
                    {
                        "gamePk": 123,
                        "gameDate": "2025-03-18T22:10:00Z",
                        "teams": {
                            "home": {"team": {"name": "Los Angeles Dodgers"}},
                            "away": {"team": {"name": "New York Mets"}},
                        },
                    }
                ]

                def _mock_http(url: str):
                    if "/boxscore" in url:
                        return {
                            "teams": {
                                "home": {
                                    "battingOrder": [10],
                                    "pitchers": [1],
                                    "players": {
                                        "ID10": {"person": {"fullName": "Hitter H1"}, "batSide": {"code": "L"}},
                                        "ID1": {"person": {"fullName": "Home SP"}, "stats": {"pitching": {"inningsPitched": "5.0"}}},
                                    },
                                },
                                "away": {
                                    "battingOrder": [20],
                                    "pitchers": [2],
                                    "players": {
                                        "ID20": {"person": {"fullName": "Hitter A1"}, "batSide": {"code": "R"}},
                                        "ID2": {"person": {"fullName": "Away SP"}, "stats": {"pitching": {"inningsPitched": "5.0"}}},
                                    },
                                },
                            }
                        }
                    if "/venues/" in url:
                        return {"venues": [{"roofType": "open", "turfType": "grass", "location": {"defaultCoordinates": {"latitude": 34.0739, "longitude": -118.24}}}]}
                    if "open-meteo.com" in url:
                        return {"hourly": {"temperature_2m": [15.0], "windspeed_10m": [8.0]}}
                    return {}

                ext._safe_http_json = _mock_http  # type: ignore[assignment]
                ext._fetch_odds_timeline = lambda *_args, **_kwargs: []  # type: ignore[assignment]
                summary = fetch_and_materialize_external_context(csv_path=csv_path, output_dir=root / "ctx")
                self.assertEqual(summary.failures, 0)
            finally:
                ext._schedule_games = saved_schedule  # type: ignore[assignment]
                ext._safe_http_json = saved_http  # type: ignore[assignment]
                ext._fetch_odds_timeline = saved_odds  # type: ignore[assignment]

            lineups_path = root / "ctx" / "confirmed_lineups.jsonl"
            self.assertTrue(lineups_path.exists())
            rows = [json.loads(x) for x in lineups_path.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["game_id"], gid)
            self.assertTrue(rows[0]["fetched_at"])
            self.assertEqual(rows[0]["confirmed_home_starter"], "Home SP")
            self.assertEqual(rows[0]["confirmed_away_starter"], "Away SP")

    def test_duplicate_latest_wins_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gid = "MLB-2025_03_18-6_10_PM-NEW_YORK_METS-AT-LOS_ANGELES_DODGERS"
            (root / "lineups.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"game_id": gid, "confirmed_home_starter": "old", "fetched_at": "2026-03-19T10:00:00Z"}),
                        json.dumps({"game_id": gid, "confirmed_home_starter": "new", "fetched_at": "2026-03-19T11:00:00Z"}),
                    ]
                ),
                encoding="utf-8",
            )
            for name in ("bullpen_usage_3d.jsonl", "odds_timeline.jsonl", "weather_wind.jsonl", "injury_rest.jsonl"):
                (root / name).write_text("", encoding="utf-8")
            bundle = load_connectors(root)
            self.assertEqual(bundle.lineups[gid]["confirmed_home_starter"], "new")


if __name__ == "__main__":
    unittest.main()
