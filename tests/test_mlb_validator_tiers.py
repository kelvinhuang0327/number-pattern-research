from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.mlb_data.schema import (
    AvailabilityField,
    MLBFeatureBundle,
    MLBGameData,
    MLBInjuryRestStatus,
    MLBOddsSnapshot,
)
from wbc_backend.mlb_data.validator import MLBValidityTier, validate_mlb_game_data


def _af(v, available=True, ts="2099-01-01T00:00:00Z"):
    return AvailabilityField(value=v if available else None, available=available, observed_at=ts, source="test")


def _game(features: MLBFeatureBundle, game_id: str = "G1", home_team: str = "A", away_team: str = "B", game_date: str = "2025-03-20"):
    return MLBGameData(
        game_id=game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
        status="Final",
        home_score=5,
        away_score=3,
        features=features,
    )


class TestMLBValidatorTiers(unittest.TestCase):
    def test_strict_valid(self):
        injury = MLBInjuryRestStatus(_af({"x": 1}), _af(1), _af(1))
        odds = MLBOddsSnapshot(_af(-120), _af(110), _af(-130), _af(120), _af(-125), _af(115), _af(-128), _af(112), _af([{"x": 1}]))
        f = MLBFeatureBundle(
            probable_home_starter=_af("H"),
            probable_away_starter=_af("A"),
            confirmed_home_starter=_af("H"),
            confirmed_away_starter=_af("A"),
            confirmed_home_lineup=_af(["h1"]),
            confirmed_away_lineup=_af(["a1"]),
            bullpen_usage_last_3d_home=_af(70),
            bullpen_usage_last_3d_away=_af(80),
            home_away_splits=_af({"h": 1}),
            platoon_splits=_af({"p": 1}),
            park_factors=_af({"run": 1.0}),
            weather=_af({"temp": 70}),
            wind=_af({"mph": 8}),
            injury_rest=injury,
            odds=odds,
        )
        res = validate_mlb_game_data([_game(f)])
        self.assertEqual(res.strict_valid_games, 1)
        self.assertEqual(res.status_by_game["G1"], MLBValidityTier.STRICT_VALID)

    def test_research_valid(self):
        injury = MLBInjuryRestStatus(_af(None, False, ""), _af(None, False, ""), _af(None, False, ""))
        odds = MLBOddsSnapshot(_af(None, False, ""), _af(None, False, ""), _af(-130), _af(120), _af(None, False, ""), _af(None, False, ""), _af(-130), _af(120), _af(None, False, ""))
        f = MLBFeatureBundle(
            probable_home_starter=_af("H"),
            probable_away_starter=_af("A"),
            confirmed_home_starter=_af(None, False, ""),
            confirmed_away_starter=_af(None, False, ""),
            confirmed_home_lineup=_af(None, False, ""),
            confirmed_away_lineup=_af(None, False, ""),
            bullpen_usage_last_3d_home=_af(None, False, ""),
            bullpen_usage_last_3d_away=_af(None, False, ""),
            home_away_splits=_af(None, False, ""),
            platoon_splits=_af(None, False, ""),
            park_factors=_af(None, False, ""),
            weather=_af(None, False, ""),
            wind=_af(None, False, ""),
            injury_rest=injury,
            odds=odds,
        )
        res = validate_mlb_game_data([_game(f)])
        self.assertEqual(res.research_valid_games, 1)
        self.assertEqual(res.status_by_game["G1"], MLBValidityTier.RESEARCH_VALID)

    def test_invalid(self):
        injury = MLBInjuryRestStatus(_af(None, False, ""), _af(None, False, ""), _af(None, False, ""))
        odds = MLBOddsSnapshot(_af(None, False, ""), _af(None, False, ""), _af(None, False, ""), _af(None, False, ""), _af(None, False, ""), _af(None, False, ""), _af(None, False, ""), _af(None, False, ""), _af(None, False, ""))
        f = MLBFeatureBundle(
            probable_home_starter=_af(None, False, ""),
            probable_away_starter=_af(None, False, ""),
            confirmed_home_starter=_af(None, False, ""),
            confirmed_away_starter=_af(None, False, ""),
            confirmed_home_lineup=_af(None, False, ""),
            confirmed_away_lineup=_af(None, False, ""),
            bullpen_usage_last_3d_home=_af(None, False, ""),
            bullpen_usage_last_3d_away=_af(None, False, ""),
            home_away_splits=_af(None, False, ""),
            platoon_splits=_af(None, False, ""),
            park_factors=_af(None, False, ""),
            weather=_af(None, False, ""),
            wind=_af(None, False, ""),
            injury_rest=injury,
            odds=odds,
        )
        res = validate_mlb_game_data([_game(f, home_team="", game_date="")])
        self.assertEqual(res.invalid_games, 1)
        self.assertEqual(res.status_by_game["G1"], MLBValidityTier.INVALID)


if __name__ == "__main__":
    unittest.main()
