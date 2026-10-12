from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.config.settings import AppConfig
from wbc_backend.data.wbc_verification import (
    WBCDataVerificationError,
    verify_game_artifact,
)
from wbc_backend.pipeline.service import PredictionService


def _snapshot_payload() -> dict:
    return {
        "version": 1,
        "generated_at": "2026-03-07T00:00:00+08:00",
        "games": [
            {
                "canonical_game_id": "WBC2026_TPE_JPN_001",
                "aliases": ["C04"],
                "tournament": "WBC2026",
                "round_name": "Pool C",
                "game_time_utc": "2026-03-06T10:00:00Z",
                "game_time_local": "2026-03-06T19:00:00+09:00",
                "venue": "Tokyo Dome, Tokyo",
                "home": "JPN",
                "away": "TPE",
                "verification": {
                    "schedule_verified": True,
                    "rosters_verified": True,
                    "starters_verified": True,
                    "lineups_verified": True,
                    "last_verified_at": "2026-03-06T08:30:00Z",
                    "max_age_hours": 999999
                },
                "home_roster": [
                    "Shohei Ohtani",
                    "Lars Nootbaar",
                    "Masataka Yoshida",
                    "Munetaka Murakami",
                    "Kensuke Kondoh",
                    "Seiya Suzuki",
                    "Sosuke Genda",
                    "Shugo Maki",
                    "Kazuma Okamoto",
                    "Yoshinobu Yamamoto"
                ],
                "away_roster": [
                    "Chen Chieh-Hsien",
                    "Lin Li",
                    "Lin An-Ko",
                    "Yu Chang",
                    "Cheng Tsung-Che",
                    "Lee Hao-Yu",
                    "Chiang Kun-Yu",
                    "Wu Nien-Ting",
                    "Chen Chen-Wei",
                    "Lin Yu-Min"
                ],
                "home_sp": {"name": "Yoshinobu Yamamoto", "team": "JPN", "era": 3.10, "fip": 3.25, "whip": 1.12},
                "away_sp": {"name": "Lin Yu-Min", "team": "TPE", "era": 3.20, "fip": 3.35, "whip": 1.18},
                "home_lineup": [
                    {"name": "Shohei Ohtani", "team": "JPN"},
                    {"name": "Lars Nootbaar", "team": "JPN"},
                    {"name": "Masataka Yoshida", "team": "JPN"},
                    {"name": "Munetaka Murakami", "team": "JPN"},
                    {"name": "Kensuke Kondoh", "team": "JPN"},
                    {"name": "Seiya Suzuki", "team": "JPN"},
                    {"name": "Sosuke Genda", "team": "JPN"},
                    {"name": "Shugo Maki", "team": "JPN"},
                    {"name": "Kazuma Okamoto", "team": "JPN"}
                ],
                "away_lineup": [
                    {"name": "Chen Chieh-Hsien", "team": "TPE"},
                    {"name": "Lin Li", "team": "TPE"},
                    {"name": "Lin An-Ko", "team": "TPE"},
                    {"name": "Yu Chang", "team": "TPE"},
                    {"name": "Cheng Tsung-Che", "team": "TPE"},
                    {"name": "Lee Hao-Yu", "team": "TPE"},
                    {"name": "Chiang Kun-Yu", "team": "TPE"},
                    {"name": "Wu Nien-Ting", "team": "TPE"},
                    {"name": "Chen Chen-Wei", "team": "TPE"}
                ]
            }
        ]
    }


class TestWBCDataVerificationGate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.snapshot_path = Path(self.tmpdir.name) / "wbc_snapshot.json"
        self.snapshot_path.write_text(
            json.dumps(_snapshot_payload(), ensure_ascii=False),
            encoding="utf-8",
        )
        base = AppConfig()
        self.config = replace(
            base,
            sources=replace(
                base.sources,
                wbc_authoritative_snapshot_json=str(self.snapshot_path),
            ),
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_verify_game_artifact_accepts_verified_snapshot(self):
        result = verify_game_artifact(
            game_id="C04",
            expected_home="JPN",
            expected_away="TPE",
            expected_game_time="2026-03-06T19:00:00+09:00",
            expected_home_sp="Yoshinobu Yamamoto",
            expected_away_sp="Lin Yu-Min",
            expected_home_lineup=[
                "Shohei Ohtani",
                "Lars Nootbaar",
                "Masataka Yoshida",
                "Munetaka Murakami",
                "Kensuke Kondoh",
                "Seiya Suzuki",
                "Sosuke Genda",
                "Shugo Maki",
                "Kazuma Okamoto",
            ],
            expected_away_lineup=[
                "Chen Chieh-Hsien",
                "Lin Li",
                "Lin An-Ko",
                "Yu Chang",
                "Cheng Tsung-Che",
                "Lee Hao-Yu",
                "Chiang Kun-Yu",
                "Wu Nien-Ting",
                "Chen Chen-Wei",
            ],
            snapshot_path=str(self.snapshot_path),
        )
        self.assertEqual(result.status, "VERIFIED")
        self.assertFalse(result.blocking)

    def test_verify_game_artifact_rejects_wrong_starter(self):
        result = verify_game_artifact(
            game_id="C04",
            expected_home="JPN",
            expected_away="TPE",
            expected_game_time="2026-03-06T19:00:00+09:00",
            expected_home_sp="Yoshinobu Yamamoto",
            expected_away_sp="Cheng Hao-Chun",
            expected_home_lineup=[
                "Shohei Ohtani",
                "Lars Nootbaar",
                "Masataka Yoshida",
                "Munetaka Murakami",
                "Kensuke Kondoh",
                "Seiya Suzuki",
                "Sosuke Genda",
                "Shugo Maki",
                "Kazuma Okamoto",
            ],
            expected_away_lineup=[
                "Chen Chieh-Hsien",
                "Lin Li",
                "Lin An-Ko",
                "Yu Chang",
                "Cheng Tsung-Che",
                "Lee Hao-Yu",
                "Chiang Kun-Yu",
                "Wu Nien-Ting",
                "Chen Chen-Wei",
            ],
            snapshot_path=str(self.snapshot_path),
        )
        self.assertTrue(result.blocking)
        self.assertTrue(any(issue.code == "away_sp_mismatch" for issue in result.issues))

    def test_prediction_service_builds_verified_matchup_from_snapshot(self):
        service = PredictionService(self.config)
        request = type("Req", (), {"game_id": "WBC2026_TPE_JPN_001"})()
        matchup = service._build_matchup(request)

        self.assertEqual(matchup.home.team, "JPN")
        self.assertEqual(matchup.away.team, "TPE")
        self.assertEqual(matchup.home_sp.name, "Yoshinobu Yamamoto")
        self.assertEqual(matchup.away_sp.name, "Lin Yu-Min")
        self.assertEqual(len(matchup.home_lineup), 9)
        self.assertEqual(len(matchup.away_lineup), 9)

    def test_prediction_service_blocks_unverified_game(self):
        empty_snapshot = Path(self.tmpdir.name) / "empty_snapshot.json"
        empty_snapshot.write_text(
            json.dumps({"version": 1, "generated_at": "2026-03-07T00:00:00+08:00", "games": []}),
            encoding="utf-8",
        )
        config = replace(
            self.config,
            sources=replace(
                self.config.sources,
                wbc_authoritative_snapshot_json=str(empty_snapshot),
            ),
        )
        service = PredictionService(config)
        request = type("Req", (), {"game_id": "WBC2026_TPE_JPN_001"})()

        with self.assertRaises(WBCDataVerificationError):
            service._build_matchup(request)

    def test_previous_game_lineup_fallback_is_allowed(self):
        payload = _snapshot_payload()
        game = payload["games"][0]
        game["home_previous_lineup"] = game["home_lineup"]
        game["away_previous_lineup"] = game["away_lineup"]
        game["home_lineup"] = []
        game["away_lineup"] = []
        game["verification"]["lineups_verified"] = False
        self.snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        result = verify_game_artifact(
            game_id="C04",
            expected_home="JPN",
            expected_away="TPE",
            expected_game_time="2026-03-06T19:00:00+09:00",
            expected_home_sp="Yoshinobu Yamamoto",
            expected_away_sp="Lin Yu-Min",
            expected_home_lineup=[
                "Shohei Ohtani",
                "Lars Nootbaar",
                "Masataka Yoshida",
                "Munetaka Murakami",
                "Kensuke Kondoh",
                "Seiya Suzuki",
                "Sosuke Genda",
                "Shugo Maki",
                "Kazuma Okamoto",
            ],
            expected_away_lineup=[
                "Chen Chieh-Hsien",
                "Lin Li",
                "Lin An-Ko",
                "Yu Chang",
                "Cheng Tsung-Che",
                "Lee Hao-Yu",
                "Chiang Kun-Yu",
                "Wu Nien-Ting",
                "Chen Chen-Wei",
            ],
            snapshot_path=str(self.snapshot_path),
        )
        self.assertEqual(result.status, "VERIFIED_WITH_FALLBACK")
        self.assertTrue(result.used_fallback_lineup)
