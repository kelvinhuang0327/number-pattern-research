from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.build_wbc_authoritative_snapshot import build_snapshot


class TestWBCSnapshotBuilder(unittest.TestCase):
    def test_build_snapshot_generates_all_pool_games(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "snapshot.json"
            payload = build_snapshot(
                roster_path=Path("data/wbc_all_players_realtime.json"),
                overrides_path=Path("data/wbc_verified_overrides.json"),
                output_path=out,
            )

            self.assertEqual(len(payload["games"]), 40)
            self.assertTrue(out.exists())

            c04 = next(game for game in payload["games"] if game["canonical_game_id"] == "C04")
            self.assertEqual(c04["home"], "JPN")
            self.assertEqual(c04["away"], "TPE")
            self.assertEqual(c04["home_sp"]["name"], "Yoshinobu Yamamoto")
            self.assertEqual(c04["away_sp"]["name"], "Hao-Chun Cheng")
            self.assertTrue(c04["verification"]["schedule_verified"])
            self.assertTrue(c04["verification"]["rosters_verified"])
            self.assertTrue(c04["verification"]["starters_verified"])
            self.assertFalse(c04["verification"]["lineups_verified"])
            self.assertEqual(len(c04["home_previous_lineup"]), 9)
            self.assertEqual(len(c04["away_previous_lineup"]), 9)

    def test_build_snapshot_writes_json_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "snapshot.json"
            build_snapshot(
                roster_path=Path("data/wbc_all_players_realtime.json"),
                overrides_path=Path("data/wbc_verified_overrides.json"),
                output_path=out,
            )
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("generated_at", saved)
            self.assertEqual(saved["version"], 2)
            self.assertEqual(len(saved["games"]), 40)
