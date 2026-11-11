from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.mlb_data.odds_timeline_asset import (  # noqa: E402
    build_canonical_mlb_odds_timeline,
    build_mlb_odds_timeline_qa_report,
)


class TestMLBOddsTimelineAsset(unittest.TestCase):
    def test_builds_canonical_timeline_with_decision_and_closing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "tsl_odds_history.jsonl"
            out = root / "odds_timeline_canonical.jsonl"
            csv = root / "mlb.csv"

            snapshots = [
                ("2026-03-18T10:00:00Z", "1.95", "1.86"),
                ("2026-03-18T16:00:00Z", "1.91", "1.90"),
                ("2026-03-18T16:40:00Z", "1.88", "1.93"),
            ]
            lines = []
            for ts, away_odds, home_odds in snapshots:
                lines.append(
                    json.dumps(
                        {
                            "source": "TSL_BLOB3RD",
                            "fetched_at": ts,
                            "match_id": "X1",
                            "game_time": "2026-03-19T01:05:00+08:00",
                            "home_team_name": "波士頓紅襪",
                            "away_team_name": "亞特蘭大勇士",
                            "markets": [
                                {
                                    "marketCode": "MNL",
                                    "outcomes": [
                                        {"outcomeName": "亞特蘭大勇士", "odds": away_odds, "specialBetValue": None},
                                        {"outcomeName": "波士頓紅襪", "odds": home_odds, "specialBetValue": None},
                                    ],
                                }
                            ],
                        },
                        ensure_ascii=False,
                    )
                )
            src.write_text("\n".join(lines), encoding="utf-8")

            # ET conversion from 2026-03-19T01:05:00+08:00 -> 2026-03-18 1:05 PM ET
            pd.DataFrame(
                [
                    {
                        "Date": "2026-03-18",
                        "Start Time (EDT)": "1:05 PM",
                        "Away": "Atlanta Braves",
                        "Home": "Boston Red Sox",
                    }
                ]
            ).to_csv(csv, index=False)

            summary = build_canonical_mlb_odds_timeline(
                source_path=src,
                output_path=out,
                decision_lead_minutes=60,
            )
            self.assertEqual(summary.canonical_games_written, 1)
            self.assertEqual(summary.games_with_decision, 1)

            rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(rows), 1)
            rec = rows[0]
            self.assertIsNotNone(rec["opening_home_ml"])
            self.assertIsNotNone(rec["decision_home_ml"])
            self.assertIsNotNone(rec["closing_home_ml"])
            self.assertNotEqual(rec["opening_home_ml"], rec["closing_home_ml"])

            qa = build_mlb_odds_timeline_qa_report(canonical_path=out, csv_path=csv)
            self.assertEqual(qa["mapped_games_to_csv"], 1)
            self.assertEqual(qa["timestamp_monotonic_failures"], 0)
            self.assertGreaterEqual(qa["availability"]["decision_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
