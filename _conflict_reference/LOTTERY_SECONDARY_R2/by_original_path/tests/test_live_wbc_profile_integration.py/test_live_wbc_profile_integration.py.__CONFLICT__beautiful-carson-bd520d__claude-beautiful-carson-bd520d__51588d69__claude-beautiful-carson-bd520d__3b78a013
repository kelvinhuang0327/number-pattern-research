from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.betting.market import market_adjustment
from wbc_backend.config.settings import AppConfig
from wbc_backend.domain.schemas import AnalyzeRequest, Matchup, TeamSnapshot
from wbc_backend.ingestion.unified_loader import UnifiedDataLoader
from wbc_backend.pipeline.service import PredictionService


class TestWBCProfileLoader(unittest.TestCase):
    def test_loader_exposes_extended_wbc_profile_columns(self):
        loader = UnifiedDataLoader(AppConfig())
        df = loader.load_team_metrics().set_index("team")

        self.assertIn("runs_per_game", df.columns)
        self.assertIn("bullpen_era", df.columns)
        self.assertIn("roster_strength_index", df.columns)
        self.assertAlmostEqual(float(df.loc["PAN", "runs_per_game"]), 3.8, places=2)
        self.assertAlmostEqual(float(df.loc["CAN", "bullpen_era"]), 3.6, places=2)


class TestWBCLiveOddsAndMatchup(unittest.TestCase):
    def _make_service(self) -> PredictionService:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        base = AppConfig()
        config = replace(
            base,
            sources=replace(
                base.sources,
                bankroll_storage_db=str(Path(td.name) / "bankroll.db"),
            ),
        )
        return PredictionService(config)

    def test_get_odds_rejects_seed_lines_for_live_predictions(self):
        svc = self._make_service()
        request = AnalyzeRequest(game_id="A06")
        matchup = Matchup(
            game_id="A06",
            tournament="WBC2026",
            game_time_utc="2026-03-09T00:00:00Z",
            home=TeamSnapshot("CAN", 1500, 0.32, 100, 3.8, 1.25, 100, 0.70, 8.0, 65),
            away=TeamSnapshot("PAN", 1500, 0.32, 100, 3.8, 1.25, 100, 0.70, 8.0, 65),
        )

        odds = svc._get_odds(request, matchup)

        self.assertEqual(odds, [])

    def test_build_matchup_hydrates_non_default_team_profile(self):
        svc = self._make_service()

        matchup = svc._build_matchup(AnalyzeRequest(game_id="A06"))

        self.assertAlmostEqual(matchup.home.runs_per_game, 4.8, places=2)
        self.assertAlmostEqual(matchup.away.runs_per_game, 3.8, places=2)
        self.assertEqual(matchup.home.sample_size, 152)
        self.assertAlmostEqual(matchup.away.roster_strength_index, 60.0, places=2)
        self.assertGreater(len(matchup.home_bullpen), 0)
        self.assertGreater(len(matchup.away_bullpen), 0)


class TestMarketFallbackBehavior(unittest.TestCase):
    def test_market_adjustment_leaves_model_prob_when_no_matching_odds(self):
        result = market_adjustment(0.6123, [], "CAN", "PAN")

        self.assertAlmostEqual(result["adjusted_home_prob"], 0.6123, places=4)
        self.assertAlmostEqual(result["market_implied_home"], 0.6123, places=4)
        self.assertEqual(result["market_weight_applied"], 0.0)
        self.assertEqual(result["model_weight_applied"], 1.0)

    def test_market_adjustment_downweights_tsl_when_feed_blocked(self):
        from wbc_backend.domain.schemas import OddsLine

        odds = [
            OddsLine("TSL", "ML", "CAN", None, 1.70, "tsl"),
            OddsLine("TSL", "ML", "PAN", None, 2.20, "tsl"),
        ]

        result = market_adjustment(
            0.58,
            odds,
            "CAN",
            "PAN",
            feed_status={
                "success": False,
                "note": "modern_pre_2026-03-13=HTTP Error 403: Forbidden",
            },
        )

        self.assertEqual(result["tsl_feed_state"], "blocked_cached")
        self.assertLess(result["market_weight_applied"], 0.15)
        self.assertGreater(result["model_weight_applied"], 0.85)

    def test_market_adjustment_downweights_when_feed_is_healthy_but_matchup_unlisted(self):
        result = market_adjustment(
            0.58,
            [],
            "CAN",
            "PAN",
            feed_status={"success": True, "source": "TSL_BLOB3RD"},
            matchup_status={"in_snapshot": False},
        )

        self.assertEqual(result["tsl_feed_state"], "healthy_unlisted")
        self.assertEqual(result["market_support_summary"], "TSL healthy, matchup unavailable")
        self.assertEqual(result["market_support_by_market"]["ML"], "unlisted_matchup")
        self.assertEqual(result["market_support_by_market"]["OU"], "unlisted_matchup")
        self.assertEqual(result["market_weight_applied"], 0.0)
        self.assertEqual(result["model_weight_applied"], 1.0)


class TestCategoryNBlowoutRisk(unittest.TestCase):
    """Category N: mismatch_blowout_propensity / mercy_rule_hazard / data quality signals."""

    def _make_matchup(self, home_elo: float, away_elo: float,
                      home_lineup_n: int = 9, away_lineup_n: int = 9,
                      home_bp_7d: int = 0, away_bp_7d: int = 0) -> Matchup:
        from wbc_backend.domain.schemas import BatterSnapshot, PitcherSnapshot

        def _batter(team: str) -> BatterSnapshot:
            return BatterSnapshot(
                name="Player", team=team, avg=0.260, obp=0.330, slg=0.420,
                woba=0.330, ops_plus=100, clutch_woba=0.330,
                vs_left_avg=0.260, vs_right_avg=0.260,
            )

        def _pitcher(name: str, team: str) -> PitcherSnapshot:
            return PitcherSnapshot(
                name=name, team=team, era=3.50, fip=3.60, whip=1.20,
                k_per_9=9.0, bb_per_9=2.5, stuff_plus=100,
                ip_last_30=25.0, era_last_3=3.50, pitch_count_last_3d=0,
                fastball_velo=93.0, high_leverage_era=3.80,
            )

        home = TeamSnapshot(
            team="MEX", elo=home_elo,
            batting_woba=0.340, batting_ops_plus=108, pitching_fip=3.50,
            pitching_whip=1.18, pitching_stuff_plus=105, der=0.700,
            bullpen_depth=0.80, pitch_limit=65,
            bullpen_era=3.5, bullpen_fip=3.6, bullpen_k_pct=0.24,
            roster_strength_index=0.85, wbc_experience_games=20,
            intl_win_pct=0.62, intl_run_diff=1.8, bullpen_workload_7d=home_bp_7d,
        )
        away = TeamSnapshot(
            team="BRA", elo=away_elo,
            batting_woba=0.290, batting_ops_plus=78, pitching_fip=5.20,
            pitching_whip=1.55, pitching_stuff_plus=82, der=0.660,
            bullpen_depth=0.45, pitch_limit=65,
            bullpen_era=5.2, bullpen_fip=5.4, bullpen_k_pct=0.18,
            roster_strength_index=0.45, wbc_experience_games=4,
            intl_win_pct=0.32, intl_run_diff=-2.1, bullpen_workload_7d=away_bp_7d,
        )
        return Matchup(
            game_id="B06", tournament="WBC2026", game_time_utc="2026-03-09T18:00:00Z",
            home=home, away=away,
            home_sp=_pitcher("SP_Home", "MEX"),
            away_sp=_pitcher("TBD", "BRA"),
            home_lineup=[_batter("MEX") for _ in range(home_lineup_n)],
            away_lineup=[_batter("BRA") for _ in range(away_lineup_n)],
            round_name="Pool", tournament_round_num=1,
        )

    def test_high_elo_gap_raises_blowout_propensity(self):
        """Elo gap 300 should give mismatch_blowout_propensity ≈ 0.90 (tanh(2))."""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = self._make_matchup(home_elo=1800, away_elo=1500)
        signals = build_alpha_signals(matchup)
        f = signals.feature_dict

        self.assertIn("mismatch_blowout_propensity", f)
        self.assertGreater(f["mismatch_blowout_propensity"], 0.70)
        self.assertEqual(f["elo_gap_abs"], 300.0)
        self.assertGreater(f["mercy_rule_hazard"], 0.0)

    def test_equal_elo_gives_low_blowout_propensity(self):
        """Elo gap 0 → mismatch_blowout_propensity = 0.0."""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = self._make_matchup(home_elo=1700, away_elo=1700)
        signals = build_alpha_signals(matchup)
        f = signals.feature_dict

        self.assertEqual(f["mismatch_blowout_propensity"], 0.0)
        self.assertEqual(f["elo_gap_abs"], 0.0)

    def test_starter_identity_confidence_tbd(self):
        """Away SP named 'TBD' should get confidence 0.5."""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = self._make_matchup(home_elo=1700, away_elo=1600)
        signals = build_alpha_signals(matchup)
        f = signals.feature_dict

        self.assertEqual(f["starter_identity_confidence_home"], 1.0)
        self.assertEqual(f["starter_identity_confidence_away"], 0.5)
        self.assertEqual(f["starter_identity_confidence_min"], 0.5)

    def test_lineup_coverage_partial(self):
        """5-man lineup → coverage_min = 5/9 ≈ 0.555."""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = self._make_matchup(home_elo=1700, away_elo=1600,
                                     home_lineup_n=5, away_lineup_n=9)
        signals = build_alpha_signals(matchup)
        f = signals.feature_dict

        self.assertAlmostEqual(f["lineup_coverage_min"], round(5 / 9, 4), places=3)

    def test_bullpen_cascade_fatigue_normalized(self):
        """300 pitches in 7d → fatigue=1.0; 150 → 0.5."""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = self._make_matchup(home_elo=1700, away_elo=1700,
                                     home_bp_7d=300, away_bp_7d=150)
        signals = build_alpha_signals(matchup)
        f = signals.feature_dict

        self.assertEqual(f["bullpen_cascade_fatigue_home"], 1.0)
        self.assertAlmostEqual(f["bullpen_cascade_fatigue_away"], 0.5, places=3)
        self.assertAlmostEqual(f["bullpen_cascade_fatigue_diff"], 0.5, places=3)

    def test_category_n_in_computed_categories(self):
        """Category N should appear in categories_computed."""
        from wbc_backend.features.alpha_signals import build_alpha_signals
        matchup = self._make_matchup(home_elo=1700, away_elo=1600)
        signals = build_alpha_signals(matchup)
        self.assertIn("N:BlowoutRisk", signals.categories_computed)


class TestOUUnderBlowoutSuppression(unittest.TestCase):
    """OU Under bet suppression when mismatch_blowout_propensity > 0.65."""

    def _make_odds(self, market: str, side: str, decimal_odds: float = 1.85):
        from wbc_backend.domain.schemas import OddsLine
        return OddsLine(
            sportsbook="TSL", market=market, side=side,
            line=None, decimal_odds=decimal_odds, source_type="tsl",
        )

    def _true_probs(self) -> dict:
        return {
            "ML_MEX": 0.78, "ML_BRA": 0.22,
            "RL_MEX": 0.60, "RL_BRA": 0.40,
            "OU_Over": 0.72, "OU_Under": 0.28,
            "F5_MEX": 0.75, "F5_BRA": 0.25,
        }

    def test_ou_under_suppressed_when_blowout_propensity_high(self):
        """OU Under should be skipped when blowout_propensity > 0.65."""
        from wbc_backend.betting.optimizer import find_top_bets

        odds = [
            self._make_odds("OU", "Over", 1.90),
            self._make_odds("OU", "Under", 1.90),   # should be skipped
            self._make_odds("ML", "MEX", 1.30),
        ]
        bets = find_top_bets(
            odds, self._true_probs(), "MEX", "BRA",
            confidence_score=0.70, blowout_propensity=0.85,
        )
        bet_keys = [(b.market, b.side) for b in bets]
        self.assertNotIn(("OU", "Under"), bet_keys)

    def test_ou_under_not_suppressed_when_blowout_propensity_low(self):
        """OU Under suppression should NOT fire for equal-strength matchups."""
        from wbc_backend.betting.optimizer import find_top_bets

        odds = [self._make_odds("OU", "Under", 1.90)]
        true_probs = {"OU_Over": 0.40, "OU_Under": 0.60}
        # With low blowout, Under with 60% win prob vs 52.6% implied should pass EV filter
        bets = find_top_bets(
            odds, true_probs, "MEX", "BRA",
            confidence_score=0.70, blowout_propensity=0.20,
        )
        # The bet may or may not pass other gates (CLV etc.), but suppression should not block it
        # We verify by checking that no BLOWOUT suppression log was triggered
        # (functional check: Under can be a candidate)
        # Since other gates may reject, just check suppression logic specifically
        from unittest.mock import patch
        logged_skips = []
        orig_debug = __import__("logging").getLogger("wbc_backend.betting.optimizer").debug

        with patch("wbc_backend.betting.optimizer.logger") as mock_logger:
            find_top_bets(
                odds, true_probs, "MEX", "BRA",
                confidence_score=0.70, blowout_propensity=0.20,
            )
            # Check no "blowout_propensity" skip was logged
            for call in mock_logger.debug.call_args_list:
                if "blowout_propensity" in str(call):
                    logged_skips.append(call)
        self.assertEqual(logged_skips, [])


if __name__ == "__main__":
    unittest.main()
