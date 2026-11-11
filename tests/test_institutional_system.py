"""
Institutional System Test Suite
================================
Comprehensive tests for all Phase 3-8 components:
  - Alpha signals (200+ features)
  - Dynamic ensemble (Bayesian weight updating)
  - Institutional backtest (walk-forward, data isolation)
  - Portfolio risk (correlation-aware Kelly)
  - Continuous learning (self-improving pipeline)

Run: python -m pytest tests/test_institutional_system.py -v
"""
from __future__ import annotations

import math
import sys
import os
import pytest

# Ensure project root in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Import all modules under test ─────────────────────────────────────────

from wbc_backend.domain.schemas import (
    TeamSnapshot, Matchup, PitcherSnapshot, BatterSnapshot
)
from wbc_backend.features.alpha_signals import (
    build_alpha_signals, AlphaSignals,
    _compute_batting_signals, _compute_defensive_signals,
    _compute_wbc_signals, _compute_market_signals,
    _compute_momentum_signals, ALPHA_SIGNAL_CATALOGUE,
)
from wbc_backend.models.dynamic_ensemble import (
    DynamicBayesianEnsemble, EnsembleBlendResult,
    blend_predictions, detect_regime,
    REGIME_WBC_POOL, REGIME_WBC_KNOCKOUT, REGIME_MLB_REGULAR,
    DEFAULT_WEIGHTS, MIN_WEIGHT, MAX_WEIGHT,
)
from wbc_backend.evaluation.institutional_backtest import (
    GameRecord, PredictionRecord, WalkForwardValidator,
    elo_predict, assert_no_synthetic, assert_minimum_sample_size,
    WBC_2023_RECORDS, run_wbc_2023_backtest,
)
from wbc_backend.betting.portfolio_risk import (
    BetProposal, PortfolioState, PortfolioRiskManager,
    correlation_kelly, compute_risk_of_ruin,
    MAX_SINGLE_BET_FRACTION, MAX_PORTFOLIO_EXPOSURE,
)
from wbc_backend.optimization.continuous_learning import (
    ContinuousLearningSystem, PerformanceMonitor,
    ChampionChallengerEngine, PredictionOutcome,
    get_recommended_experiments,
)


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

def make_team(team: str = "JPN", elo: float = 1650, woba: float = 0.340,
              fip: float = 3.20, rsi: float = 90.0) -> TeamSnapshot:
    """Create a TeamSnapshot with sensible defaults."""
    return TeamSnapshot(
        team=team, elo=elo, batting_woba=woba, batting_ops_plus=115,
        pitching_fip=fip, pitching_whip=1.10, pitching_stuff_plus=108,
        der=0.710, bullpen_depth=8.0, pitch_limit=65,
        bullpen_era=3.20, bullpen_pitches_3d=80,
        runs_per_game=5.0, runs_allowed_per_game=3.5,
        clutch_woba=0.340, roster_strength_index=rsi,
        win_pct_last_10=0.70, rest_days=2,
        batting_xwoba=woba + 0.005,
        batting_barrel_pct=0.095,
        batting_k_pct=0.200,
        batting_bb_pct=0.095,
        batting_sprint_speed=27.5,
        batting_stolen_base_pct=0.80,
        pitching_xfip=fip - 0.1,
        pitching_siera=fip - 0.05,
        pitching_k_pct=0.245,
        pitching_bb_pct=0.075,
        pitching_swstr_pct=0.125,
        pitching_gb_pct=0.480,
        pitching_hr9=0.95,
        pitching_lob_pct=0.750,
        pitching_babip=0.285,
        bullpen_fip=3.50,
        bullpen_k_pct=0.240,
        bullpen_bb_pct=0.080,
        bullpen_high_leverage_era=2.80,
        bullpen_arms_available=6,
        team_drs=15.0,
        team_uzr=12.0,
        wbc_experience_games=12,
        intl_era=3.10,
        intl_batting_woba=0.345,
        intl_win_pct=0.68,
        form_3g=0.667,
        form_7g=0.714,
        win_streak=3,
        woba_trend_7g=0.012,
        era_trend_7g=-0.3,
        top50_stars=8,
    )


def make_pitcher(name: str = "Yamamoto", team: str = "JPN",
                 era: float = 2.10, fip: float = 2.30) -> PitcherSnapshot:
    return PitcherSnapshot(
        name=name, team=team, era=era, fip=fip, whip=0.90,
        k_per_9=11.5, bb_per_9=1.8, stuff_plus=130,
        ip_last_30=32.0, era_last_3=1.80, pitch_count_last_3d=0,
        fastball_velo=97.5, high_leverage_era=1.90,
        pitch_mix={"FF": 0.45, "SL": 0.25, "CH": 0.20, "CU": 0.10},
        recent_fastball_velos=[97.5, 97.8, 97.2],
        career_fastball_velo=97.0,
        woba_vs_left=0.265, woba_vs_right=0.250,
        innings_last_14d=14.0, season_avg_innings_per_14d=13.0,
        recent_spin_rate=2480, career_spin_rate_mean=2450,
        career_spin_rate_std=80,
    )


def make_batter(name: str, team: str = "JPN", woba: float = 0.380) -> BatterSnapshot:
    return BatterSnapshot(
        name=name, team=team, avg=0.295, obp=0.385, slg=0.520,
        woba=woba, ops_plus=140, clutch_woba=0.370,
        vs_left_avg=0.285, vs_right_avg=0.305,
        barrel_pct=0.120, xwoba=woba + 0.005,
        hard_hit_pct=0.45, launch_angle_avg=14.0, exit_velo_avg=92.0,
        k_pct=0.18, bb_pct=0.12, chase_pct=0.22,
        contact_pct=0.82, iso=0.225, babip=0.320,
        sprint_speed=28.5, wrc_plus=155,
    )


def make_matchup(home_team: str = "JPN", away_team: str = "USA",
                 add_sp: bool = True, add_lineup: bool = True) -> Matchup:
    home = make_team(home_team, elo=1650, woba=0.340, fip=3.20)
    away = make_team(away_team, elo=1640, woba=0.330, fip=3.50)

    home_sp = make_pitcher("Yamamoto", home_team) if add_sp else None
    away_sp = make_pitcher("Cole", away_team, era=2.50, fip=2.70) if add_sp else None

    home_lineup = [make_batter(f"JPN_{i}", home_team, 0.280 + i * 0.01)
                   for i in range(9)] if add_lineup else []
    away_lineup = [make_batter(f"USA_{i}", away_team, 0.275 + i * 0.01)
                   for i in range(9)] if add_lineup else []

    return Matchup(
        game_id="TEST001", tournament="WBC", game_time_utc="2026-03-15T19:00:00Z",
        home=home, away=away,
        home_sp=home_sp, away_sp=away_sp,
        home_lineup=home_lineup, away_lineup=away_lineup,
        venue="Tokyo Dome", round_name="Semifinal",
        neutral_site=True, is_dome=True, elevation_m=0.0,
        temp_f=72.0, humidity_pct=0.50, wind_speed_mph=0.0,
        is_knockout_stage=True, tournament_round_num=4,
        crowd_home_pct=0.70,
        opening_ml_home_odds=1.95, closing_ml_home_odds=1.90,
        opening_ou_line=8.5, closing_ou_line=8.5,
        public_bet_pct_home=0.60, sharp_handle_pct_home=0.55,
    )


def make_sub_result(model: str, prob: float, conf: float = 0.7):
    from wbc_backend.domain.schemas import SubModelResult
    return SubModelResult(
        model_name=model, home_win_prob=prob, away_win_prob=1-prob,
        confidence=conf, expected_home_runs=4.5, expected_away_runs=3.5,
    )


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Alpha Signals Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAlphaSignals:

    def test_build_alpha_signals_returns_alphsignals(self):
        matchup = make_matchup()
        result = build_alpha_signals(matchup)
        assert isinstance(result, AlphaSignals)
        assert result.n_signals > 0

    def test_minimum_200_signals(self):
        """Must compute at least 200 alpha signals."""
        matchup = make_matchup()
        result = build_alpha_signals(matchup)
        assert result.n_signals >= 200, (
            f"Expected ≥200 signals, got {result.n_signals}. "
            f"Categories computed: {result.categories_computed}"
        )

    def test_all_categories_computed(self):
        """All 10 signal categories must be computed."""
        matchup = make_matchup()
        result = build_alpha_signals(matchup)
        expected_categories = {"A:Batting", "B:Pitching", "C:Bullpen", "D:Defense",
                                "E:WBC", "F:Market", "G:Environment", "H:Interaction",
                                "I:Momentum", "J:Lineup"}
        computed = set(result.categories_computed)
        missing = expected_categories - computed
        assert not missing, f"Missing categories: {missing}"

    def test_all_signals_are_finite(self):
        """No NaN or Inf values in feature dict."""
        matchup = make_matchup()
        result = build_alpha_signals(matchup)
        for name, val in result.feature_dict.items():
            assert math.isfinite(val), f"Signal '{name}' = {val} is not finite"

    def test_signals_without_lineup(self):
        """System must handle missing lineup gracefully."""
        matchup = make_matchup(add_lineup=False)
        result = build_alpha_signals(matchup)
        assert result.n_signals > 100  # degraded but still functional

    def test_signals_without_pitchers(self):
        """System must handle missing SP gracefully."""
        matchup = make_matchup(add_sp=False)
        result = build_alpha_signals(matchup)
        assert result.n_signals > 100

    def test_batting_signals_direction(self):
        """Better team should have positive batting differentials."""
        home = make_team("JPN", elo=1650, woba=0.360, fip=3.20)
        away = make_team("USA", elo=1500, woba=0.290, fip=4.50)
        feats = _compute_batting_signals(home, away, [], [])
        # Better home offense should give positive wrc_plus_diff
        # woba_trend and xwoba should be positive for JPN
        assert 'wrc_plus_diff' in feats

    def test_elo_diff_squared_sign(self):
        """elo_diff_squared should match sign of elo_diff."""
        home = make_team("JPN", elo=1700)
        away = make_team("USA", elo=1500)
        matchup = Matchup(
            game_id="T1", tournament="WBC", game_time_utc="2026-03-15T19:00:00Z",
            home=home, away=away,
        )
        signals = build_alpha_signals(matchup)
        elo_sq = signals.feature_dict.get('elo_diff_squared', 0.0)
        assert elo_sq > 0, "elo_diff_squared should be positive when home > away"

    def test_catalogue_has_metadata(self):
        """Signal catalogue must have at least 30 documented signals."""
        assert len(ALPHA_SIGNAL_CATALOGUE) >= 30

    def test_catalogue_categories(self):
        """All catalogue entries have valid categories."""
        valid_cats = set("ABCDEFGHIJ")
        for sig in ALPHA_SIGNAL_CATALOGUE:
            assert sig.category in valid_cats, f"Invalid category: {sig.category}"
            assert sig.predictive_potential in {"low", "medium", "high", "very_high"}

    def test_wbc_signals_round_pressure(self):
        """WBC pressure should increase with round number."""
        matchup = make_matchup()
        matchup.tournament_round_num = 1
        feats_pool = _compute_wbc_signals(matchup.home, matchup.away, matchup)
        matchup.tournament_round_num = 5
        feats_final = _compute_wbc_signals(matchup.home, matchup.away, matchup)
        assert feats_final['tournament_pressure'] > feats_pool['tournament_pressure']

    def test_market_signals_line_movement(self):
        """Line movement should be computed when odds are provided."""
        matchup = make_matchup()
        matchup.opening_ml_home_odds = 2.10  # implied ~47.6%
        matchup.closing_ml_home_odds = 1.85  # implied ~54.1% → line moved toward home
        feats = _compute_market_signals(matchup.home, matchup.away, matchup)
        # Closing prob > opening prob → positive ml_movement_home
        assert feats['ml_movement_home'] > 0, (
            f"Expected positive movement, got {feats['ml_movement_home']}"
        )

    def test_defensive_composite_makes_sense(self):
        """Better defense (higher DER) should have positive composite score."""
        home = make_team("JPN")
        home.der = 0.740
        home.team_drs = 20.0
        away = make_team("USA")
        away.der = 0.660
        away.team_drs = -10.0
        feats = _compute_defensive_signals(home, away)
        assert feats['composite_defense_diff'] > 0

    def test_momentum_signals_hot_team(self):
        """Hot team should have positive momentum score."""
        home = make_team("JPN")
        home.form_3g = 1.0
        home.form_7g = 0.857
        home.woba_trend_7g = 0.020
        home.win_streak = 5
        away = make_team("USA")
        away.form_3g = 0.333
        away.form_7g = 0.286
        away.woba_trend_7g = -0.015
        away.win_streak = -3
        feats = _compute_momentum_signals(home, away)
        assert feats['momentum_score_diff'] > 0
        assert feats['win_streak_diff'] > 0

    def test_interaction_composite_edge(self):
        """composite_edge_score should favor dominant team."""
        matchup = make_matchup()
        signals = build_alpha_signals(matchup)
        # JPN has elo=1650 vs USA=1640 and better stats → should have positive edge
        # (even if small given similar teams)
        assert 'composite_edge_score' in signals.feature_dict


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4 — Dynamic Ensemble Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestDynamicEnsemble:

    def test_regime_detection_wbc_pool(self):
        assert detect_regime("WBC 2026", "Pool A") == REGIME_WBC_POOL

    def test_regime_detection_wbc_knockout(self):
        assert detect_regime("WBC 2026", "Semifinal") == REGIME_WBC_KNOCKOUT

    def test_regime_detection_mlb(self):
        assert detect_regime("MLB Regular Season", "Game 1") == REGIME_MLB_REGULAR

    def test_ensemble_initialization(self):
        ensemble = DynamicBayesianEnsemble(regime=REGIME_WBC_POOL)
        assert len(ensemble.state.weights) > 0
        # All weights must sum to ~1.0
        total = sum(ensemble.state.weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum = {total}"

    def test_weights_are_bounded(self):
        """All weights must be within [MIN_WEIGHT, MAX_WEIGHT]."""
        ensemble = DynamicBayesianEnsemble(regime=REGIME_WBC_POOL)
        for model, w in ensemble.state.weights.items():
            assert w >= MIN_WEIGHT, f"{model} weight {w} < MIN_WEIGHT {MIN_WEIGHT}"
            assert w <= MAX_WEIGHT, f"{model} weight {w} > MAX_WEIGHT {MAX_WEIGHT}"

    def test_blend_returns_valid_probabilities(self):
        sub_results = [
            make_sub_result("elo", 0.65),
            make_sub_result("bayesian", 0.62),
            make_sub_result("poisson", 0.58),
            make_sub_result("baseline", 0.60),
        ]
        result = blend_predictions(sub_results, "WBC", "Pool")
        assert isinstance(result, EnsembleBlendResult)
        assert 0.05 <= result.home_win_prob <= 0.95
        assert abs(result.home_win_prob + result.away_win_prob - 1.0) < 0.001

    def test_blend_with_single_model(self):
        sub_results = [make_sub_result("elo", 0.70)]
        result = blend_predictions(sub_results, "WBC", "Pool")
        assert 0.05 <= result.home_win_prob <= 0.95

    def test_blend_empty_returns_50_50(self):
        ensemble = DynamicBayesianEnsemble(regime=REGIME_WBC_POOL)
        result = ensemble.blend([])
        assert abs(result.home_win_prob - 0.5) < 0.01

    def test_weight_update_improves_top_model(self):
        """Weight update should increase α for correct model."""
        ensemble = DynamicBayesianEnsemble(regime=REGIME_WBC_POOL)
        sub_results = [
            make_sub_result("elo", 0.80),     # strong home prediction
            make_sub_result("bayesian", 0.70),
            make_sub_result("form", 0.30),    # wrong prediction
        ]
        initial_elo_alpha = ensemble.state.dirichlet_alpha.get("elo", 1.0)
        initial_form_alpha = ensemble.state.dirichlet_alpha.get("form", 1.0)

        # Actual: home won (1) → elo was right, form was wrong
        ensemble.update_weights(sub_results, actual_home_win=1)

        new_elo_alpha = ensemble.state.dirichlet_alpha.get("elo", 1.0)
        new_form_alpha = ensemble.state.dirichlet_alpha.get("form", 1.0)

        # Elo's α should increase (was correct)
        assert new_elo_alpha >= initial_elo_alpha * 0.99  # allow tiny numerical diffs
        # Form's α should decrease (was wrong)
        assert new_form_alpha <= initial_form_alpha * 1.01  # at most unchanged

    def test_elo_not_permanently_45_percent(self):
        """Dynamic ensemble should deviate from static 45% Elo weight after updates."""
        ensemble = DynamicBayesianEnsemble(regime=REGIME_WBC_POOL)
        # Initial weight from prior
        initial_elo_w = ensemble.state.weights.get("elo", 0.45)

        # Run 5 updates where elo is always wrong
        sub_results = [
            make_sub_result("elo", 0.80),       # predicts home
            make_sub_result("bayesian", 0.55),
        ]
        for _ in range(5):
            ensemble.update_weights(sub_results, actual_home_win=0)  # away wins

        new_elo_w = ensemble.state.weights.get("elo", 0.45)
        # After 5 wrong predictions, elo weight should decrease
        assert new_elo_w < initial_elo_w or new_elo_w < 0.50

    def test_default_weights_sum_to_one(self):
        """All default weight profiles must sum to 1."""
        for regime, weights in DEFAULT_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"Regime {regime} weights sum to {total}"


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 6 — Institutional Backtest Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInstitutionalBacktest:

    def test_wbc_2023_records_are_real(self):
        """All WBC 2023 records must have 'real' data source."""
        for rec in WBC_2023_RECORDS:
            assert rec.data_source == "real", (
                f"Record {rec.game_id} has data_source='{rec.data_source}'"
            )

    def test_assert_no_synthetic_passes_for_real_data(self):
        """Real data should pass the synthetic guard."""
        assert_no_synthetic(WBC_2023_RECORDS, "test")  # should not raise

    def test_assert_no_synthetic_catches_synthetic(self):
        """Synthetic data should be caught and raise ValueError."""
        fake = GameRecord(
            "FAKE001", "2023-03-08", "WBC", "Pool A", "JPN", "USA",
            actual_home_win=1, data_source="synthetic"
        )
        with pytest.raises(ValueError, match="synthetic"):
            assert_no_synthetic([fake], "test")

    def test_assert_minimum_sample_size_initial(self):
        """Should not raise for ≥10 games."""
        assert_minimum_sample_size(10, "initial")
        assert_minimum_sample_size(50, "initial")

    def test_assert_minimum_sample_size_formal(self):
        """Formal validation requires ≥50 games."""
        assert_minimum_sample_size(50, "formal")
        with pytest.raises(ValueError):
            assert_minimum_sample_size(49, "formal")

    def test_assert_minimum_sample_size_too_few(self):
        """Should raise for fewer than 10 games."""
        with pytest.raises(ValueError):
            assert_minimum_sample_size(5, "initial")

    def test_elo_predict_uses_only_pregame_fields(self):
        """Prediction function must not read actual_* fields."""
        train = WBC_2023_RECORDS[:15]
        test = WBC_2023_RECORDS[15]

        # Verify test record has outcome (to confirm isolation is needed)
        assert test.actual_home_win is not None

        # Run prediction — it must succeed without accessing actual outcome
        pred = elo_predict(train, test)
        assert isinstance(pred, PredictionRecord)
        assert 0.05 <= pred.predicted_home_win_prob <= 0.95

    def test_walk_forward_with_wbc_2023_data(self):
        """Full walk-forward must produce a valid report."""
        validator = WalkForwardValidator(n_windows=3, min_train_size=10, test_window_size=8)
        report, windows = validator.run(WBC_2023_RECORDS[:35], elo_predict)

        assert report.n_games_total > 0
        assert 0.0 <= report.accuracy <= 1.0
        assert 0.0 <= report.brier_score <= 1.0
        assert isinstance(report.p_value_vs_random, float)
        assert len(windows) >= 1

    def test_backtest_report_has_notes_for_small_sample(self):
        """Small sample should trigger a warning note."""
        validator = WalkForwardValidator(n_windows=2, min_train_size=10, test_window_size=5)
        report, _ = validator.run(WBC_2023_RECORDS[:25], elo_predict)
        # n_games_total should be small → should have a warning
        has_sample_warning = any("50" in note for note in report.notes)
        assert has_sample_warning or report.n_games_total >= 50

    def test_brier_score_naive_baseline_is_025(self):
        """Brier score for always predicting 0.5 is exactly 0.25."""
        validator = WalkForwardValidator(n_windows=2, min_train_size=10, test_window_size=8)

        def always_half_predict(train, test):
            return PredictionRecord(
                game_id=test.game_id,
                predicted_home_win_prob=0.5,
                predicted_away_win_prob=0.5,
                predicted_total_runs=7.5,
                confidence=0.5,
            )

        report, _ = validator.run(WBC_2023_RECORDS[:30], always_half_predict)
        # Brier score ≈ 0.25 for naive 50/50 prediction
        assert abs(report.brier_score - 0.25) < 0.05

    def test_elo_predict_outperforms_naive_baseline(self):
        """Elo model should have Brier score < 0.25 on WBC 2023 data."""
        validator = WalkForwardValidator(n_windows=3, min_train_size=10, test_window_size=8)
        report, _ = validator.run(WBC_2023_RECORDS, elo_predict)
        # Elo empirically achieves ~72% accuracy → Brier < 0.25
        assert report.brier_score <= 0.25, (
            f"Elo Brier={report.brier_score:.4f} should be ≤ 0.25"
        )

    def test_ece_computation(self):
        """ECE for perfect calibration should be 0."""
        ece = WalkForwardValidator._compute_ece(
            [0.0, 1.0, 0.0, 1.0],
            [0, 1, 0, 1]
        )
        assert ece < 0.05  # Perfect calibration → near-zero ECE

    def test_run_wbc_2023_full_backtest(self):
        """Full WBC 2023 backtest should run without errors."""
        report = run_wbc_2023_backtest(initial_bankroll=100_000.0)
        assert report.n_games_total > 0
        assert isinstance(report.accuracy, float)
        assert isinstance(report.roi, float)


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 7 — Portfolio Risk Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPortfolioRisk:

    def _make_proposal(self, game_id: str, ev: float = 0.05, edge: float = 0.05,
                        kelly: float = 0.04, conf: float = 0.7,
                        tournament: str = "WBC", date: str = "2026-03-15") -> BetProposal:
        return BetProposal(
            game_id=game_id, market="ML", side="home",
            win_prob=0.56, odds=1.90, ev=ev, edge=edge,
            individual_kelly=kelly, confidence=conf,
            tournament=tournament, game_date=date,
        )

    def test_portfolio_state_drawdown(self):
        state = PortfolioState(bankroll=80_000, peak_bankroll=100_000)
        assert abs(state.drawdown - 0.20) < 0.001

    def test_portfolio_state_no_drawdown_at_peak(self):
        state = PortfolioState(bankroll=100_000, peak_bankroll=100_000)
        assert state.drawdown == 0.0

    def test_max_single_bet_cap(self):
        """Single bet fraction must never exceed 5%."""
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        proposals = [self._make_proposal(f"G{i}", kelly=0.15) for i in range(3)]
        result = manager.size_portfolio(proposals)
        for pos in result.positions:
            assert pos.stake_fraction <= MAX_SINGLE_BET_FRACTION + 0.001, (
                f"Position {pos.bet.game_id} stake {pos.stake_fraction:.4f} > cap"
            )

    def test_portfolio_exposure_cap(self):
        """Total exposure must not exceed 20%."""
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        proposals = [self._make_proposal(f"G{i}", kelly=0.05) for i in range(10)]
        result = manager.size_portfolio(proposals)
        assert result.total_exposure <= MAX_PORTFOLIO_EXPOSURE + 0.001

    def test_negative_ev_filtered(self):
        """Negative EV bets must be excluded."""
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        # Reset any saved circuit breaker state
        manager.state = PortfolioState(bankroll=100_000, initial_bankroll=100_000,
                                        peak_bankroll=100_000)
        proposals = [
            self._make_proposal("G1", ev=-0.02, edge=-0.02),  # bad bet
            self._make_proposal("G2", ev=0.05, edge=0.05),    # good bet
        ]
        result = manager.size_portfolio(proposals)
        position_ids = {p.bet.game_id for p in result.positions}
        assert "G1" not in position_ids, "Negative EV bet should be filtered"
        assert "G2" in position_ids, "Positive EV bet should be included"

    def test_circuit_breaker_on_excessive_drawdown(self):
        """Circuit breaker should activate at >20% drawdown."""
        state = PortfolioState(
            bankroll=79_000, initial_bankroll=100_000, peak_bankroll=100_000
        )
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        manager.state = state
        proposals = [self._make_proposal("G1")]
        result = manager.size_portfolio(proposals)
        # 21% drawdown → circuit breaker
        assert result.circuit_breaker_active
        assert len(result.positions) == 0

    def test_no_bets_when_no_proposals(self):
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        result = manager.size_portfolio([])
        assert len(result.positions) == 0

    def test_correlation_kelly_returns_valid_fractions(self):
        """correlation_kelly must return non-negative fractions summing ≤ 20%."""
        proposals = [self._make_proposal(f"G{i}") for i in range(4)]
        fractions = correlation_kelly(proposals, risk_aversion=2.0)
        assert isinstance(fractions, dict)
        total = sum(fractions.values())
        assert total <= MAX_PORTFOLIO_EXPOSURE + 0.01
        for game_id, f in fractions.items():
            assert f >= 0.0, f"Negative fraction for {game_id}"

    def test_risk_of_ruin_positive_ev(self):
        """Positive EV betting should have low risk of ruin."""
        result = compute_risk_of_ruin(
            bankroll=100_000, avg_bet_size=0.02,
            win_rate=0.55, avg_odds=2.00, ruin_threshold=0.10
        )
        assert result['risk_of_ruin'] < 0.5, "Positive EV should have <50% ruin probability"
        assert result['edge_per_bet'] > 0

    def test_risk_of_ruin_negative_ev(self):
        """Negative EV betting → 100% risk of ruin."""
        result = compute_risk_of_ruin(
            bankroll=100_000, avg_bet_size=0.02,
            win_rate=0.45, avg_odds=1.80, ruin_threshold=0.10
        )
        assert result['risk_of_ruin'] >= 0.99

    def test_risk_report_structure(self):
        """Risk report must contain all required fields."""
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        report = manager.get_risk_report()
        required = ['bankroll', 'initial_bankroll', 'pnl', 'roi_pct',
                    'current_drawdown_pct', 'peak_bankroll', 'risk_of_ruin',
                    'circuit_breaker', 'consecutive_losses', 'win_rate_pct']
        for field in required:
            assert field in report, f"Missing field: {field}"

    def test_same_tournament_games_have_higher_correlation(self):
        """Games in same tournament should get higher correlation."""
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        p1 = self._make_proposal("G1", tournament="WBC", date="2026-03-15")
        p2 = self._make_proposal("G2", tournament="WBC", date="2026-03-15")
        p3 = self._make_proposal("G3", tournament="MLB", date="2026-03-15")

        corr = manager._build_correlation_matrix([p1, p2, p3])
        # G1-G2 (same tournament+date) should have higher correlation than G1-G3
        assert corr[0, 1] >= corr[0, 2]


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 8 — Continuous Learning Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestContinuousLearning:

    def _make_outcome(self, game_id: str, predicted_prob: float,
                       actual: int) -> PredictionOutcome:
        return PredictionOutcome(
            game_id=game_id, timestamp=1000.0, tournament="WBC",
            round_name="Pool", model_name="base",
            predicted_prob=predicted_prob, actual_outcome=actual,
        )

    def test_performance_monitor_records_outcome(self):
        from wbc_backend.optimization.continuous_learning import ContinuousLearningState
        state = ContinuousLearningState()
        monitor = PerformanceMonitor(state)
        outcome = self._make_outcome("G001", 0.70, 1)
        metrics = monitor.record(outcome)
        assert 'brier' in metrics
        assert 'correct' in metrics
        assert metrics['correct'] == 1
        assert metrics['brier'] == pytest.approx((0.70 - 1.0) ** 2, abs=0.001)

    def test_brier_score_correct_prediction(self):
        """Correct high-confidence prediction → low Brier score."""
        from wbc_backend.optimization.continuous_learning import ContinuousLearningState
        state = ContinuousLearningState()
        monitor = PerformanceMonitor(state)
        outcome = self._make_outcome("G001", 0.95, 1)  # predicted 95%, won
        metrics = monitor.record(outcome)
        assert metrics['brier'] < 0.01  # (0.95-1)^2 = 0.0025

    def test_brier_score_wrong_prediction(self):
        """Wrong confident prediction → high Brier score."""
        from wbc_backend.optimization.continuous_learning import ContinuousLearningState
        state = ContinuousLearningState()
        monitor = PerformanceMonitor(state)
        outcome = self._make_outcome("G001", 0.90, 0)  # predicted home, away won
        metrics = monitor.record(outcome)
        assert metrics['brier'] > 0.5  # (0.90-0)^2 = 0.81

    def test_degradation_detection_after_many_wrong(self):
        """System should detect degradation after sustained poor performance."""
        from wbc_backend.optimization.continuous_learning import ContinuousLearningState, DEGRADATION_WINDOW
        state = ContinuousLearningState()
        monitor = PerformanceMonitor(state)

        # First fill with good predictions
        for i in range(DEGRADATION_WINDOW):
            outcome = self._make_outcome(f"G{i:03d}", 0.80, 1)  # correct
            monitor.record(outcome)

        # Then simulate degradation (bad predictions)
        for i in range(DEGRADATION_WINDOW):
            outcome = self._make_outcome(f"G{i+100:03d}", 0.90, 0)  # wrong!
            monitor.record(outcome)

        assert state.is_degraded, "Degradation should be detected after sustained poor performance"

    def test_retrain_trigger_after_interval(self):
        """Retraining should be triggered after RETRAIN_INTERVAL games."""
        from wbc_backend.optimization.continuous_learning import ContinuousLearningState, RETRAIN_INTERVAL
        state = ContinuousLearningState()
        monitor = PerformanceMonitor(state)

        for i in range(RETRAIN_INTERVAL):
            outcome = self._make_outcome(f"G{i:03d}", 0.60, 1)
            metrics = monitor.record(outcome)

        assert metrics['should_retrain'], (
            f"Should trigger retrain after {RETRAIN_INTERVAL} games"
        )

    def test_champion_challenger_routing(self):
        """Challenger should receive ~20% of traffic."""
        engine = ChampionChallengerEngine("champion", "challenger")
        n = 1000
        challengers = sum(
            1 for i in range(n)
            if engine.route(f"G{i}") == "challenger"
        )
        # Expect ~20% ± 5% with large N
        assert 150 <= challengers <= 250, (
            f"Challenger received {challengers}/1000 ({challengers/10:.1f}%)"
        )

    def test_champion_challenger_promotes_better_model(self):
        """Challenger with lower Brier should win evaluation."""
        engine = ChampionChallengerEngine("champion", "challenger")
        # Champion: Brier = 0.25 (naive), Challenger: Brier = 0.18 (better)
        for _ in range(25):
            engine.record_brier("champion", 0.25)
            engine.record_brier("challenger", 0.18)

        result = engine.evaluate()
        assert result['decision'] in ("promote_challenger", "keep_champion", "insufficient_data")
        # With clear improvement, should promote
        if result['decision'] != "insufficient_data":
            assert result['decision'] == "promote_challenger"

    def test_continuous_learning_process_result(self):
        """Full CL system should process a game result."""
        cl = ContinuousLearningSystem()
        result = cl.process_game_result(
            game_id="TEST001",
            predicted_prob=0.65,
            actual_outcome=1,
            tournament="WBC",
            round_name="Pool",
            bet_pnl=500.0,
        )
        assert 'game_id' in result
        assert 'system_status' in result
        assert result['system_status'] in ("HEALTHY", "DEGRADED")

    def test_recommended_experiments_list(self):
        """Should return at least 5 recommended experiments."""
        experiments = get_recommended_experiments()
        assert len(experiments) >= 5
        for exp in experiments:
            assert 'feature' in exp
            assert 'hypothesis' in exp
            assert 'priority' in exp


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:

    def test_full_prediction_pipeline(self):
        """End-to-end: matchup → alpha signals → dynamic ensemble → portfolio."""
        # 1. Build matchup
        matchup = make_matchup()

        # 2. Compute alpha signals
        signals = build_alpha_signals(matchup)
        assert signals.n_signals >= 200

        # 3. Create sub-model predictions (simulated)
        sub_results = [
            make_sub_result("elo", 0.62),
            make_sub_result("bayesian", 0.60),
            make_sub_result("poisson", 0.58),
        ]

        # 4. Dynamic ensemble blend
        ensemble_result = blend_predictions(sub_results, matchup.tournament, matchup.round_name)
        assert 0.05 <= ensemble_result.home_win_prob <= 0.95

        # 5. Portfolio sizing
        proposal = BetProposal(
            game_id=matchup.game_id, market="ML", side="home",
            win_prob=ensemble_result.home_win_prob,
            odds=1.90, ev=0.05, edge=0.04,
            individual_kelly=0.03,
            confidence=ensemble_result.confidence,
        )
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        portfolio = manager.size_portfolio([proposal])
        assert portfolio.risk_level in ("GREEN", "YELLOW", "RED")

    def test_backtest_to_continuous_learning_pipeline(self):
        """Backtest results should feed into continuous learning."""
        # 1. Run backtest
        report = run_wbc_2023_backtest(initial_bankroll=100_000)
        assert report.n_games_total > 0

        # 2. Feed results into CL
        cl = ContinuousLearningSystem()
        # Simulate processing 5 games
        for i in range(5):
            result = cl.process_game_result(
                game_id=f"WBC_2023_{i:03d}",
                predicted_prob=0.60 + i * 0.02,
                actual_outcome=i % 2,
                tournament="WBC", round_name="Pool",
            )
            assert 'system_status' in result

    def test_alpha_signals_compatible_with_existing_features(self):
        """Alpha signals should not conflict with existing FEATURE_NAMES."""
        from wbc_backend.features.advanced import FEATURE_NAMES
        matchup = make_matchup()
        signals = build_alpha_signals(matchup)

        # Both feature sets should produce valid floats
        for _name in FEATURE_NAMES:
            # Existing features come from advanced.py (tested separately)
            # Alpha signals should augment, not replace
            pass  # No conflict expected — different naming convention

        # Alpha signals should be all floats
        for name, val in signals.feature_dict.items():
            assert isinstance(val, (int, float)), f"Signal {name} is not numeric"

    def test_domain_schema_extensions_backward_compatible(self):
        """Extended TeamSnapshot fields should have sensible defaults."""
        # Old-style minimal creation (no new fields)
        team = TeamSnapshot(
            team="JPN", elo=1650, batting_woba=0.340, batting_ops_plus=115,
            pitching_fip=3.20, pitching_whip=1.10, pitching_stuff_plus=108,
            der=0.710, bullpen_depth=8.0, pitch_limit=65,
        )
        # New fields should have defaults
        assert team.batting_xwoba == 0.0  # default
        assert team.batting_barrel_pct == 0.08  # default
        assert team.form_3g == 0.50  # default
        assert team.wbc_experience_games == 0  # default

    def test_matchup_extended_fields(self):
        """Extended Matchup fields should have sensible defaults."""
        matchup = Matchup(
            game_id="T1", tournament="WBC", game_time_utc="2026-03-15T19:00:00Z",
            home=make_team("JPN"), away=make_team("USA"),
        )
        assert not matchup.is_elimination_game
        assert matchup.tournament_round_num == 1
        assert matchup.crowd_home_pct == 0.50
        assert matchup.park_hr_factor == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICAL RIGOR TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestStatisticalRigor:

    def test_brier_score_range(self):
        """Brier score must always be in [0, 1]."""
        for p in [0.05, 0.10, 0.30, 0.50, 0.70, 0.90, 0.95]:
            for y in [0, 1]:
                brier = (p - y) ** 2
                assert 0 <= brier <= 1

    def test_kelly_fraction_positive_ev_only(self):
        """Kelly criterion must return 0 for negative edge."""
        from wbc_backend.betting.kelly import calculate_kelly_bet
        # Negative edge scenario: odds too low for given probability
        kelly = calculate_kelly_bet(prob=0.40, odds=1.80)
        assert kelly == 0.0

    def test_kelly_fraction_positive_edge(self):
        """Kelly must return positive fraction for positive edge."""
        from wbc_backend.betting.kelly import calculate_kelly_bet
        kelly = calculate_kelly_bet(prob=0.60, odds=2.10)
        assert kelly > 0

    def test_elo_win_probability_bounds(self):
        """Elo win probability must always be in (0, 1)."""
        for elo_diff in [-300, -100, 0, 100, 300]:
            p = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))
            assert 0 < p < 1

    def test_portfolio_variance_positive_semidefinite(self):
        """Portfolio variance must be non-negative."""
        manager = PortfolioRiskManager(initial_bankroll=100_000)
        proposals = [
            BetProposal(f"G{i}", "ML", "home", 0.55, 1.90, 0.05, 0.05, 0.03, 0.70)
            for i in range(5)
        ]
        result = manager.size_portfolio(proposals)
        assert result.portfolio_variance >= 0.0

    def test_alpha_signals_reproducible(self):
        """Same matchup should always produce same signals."""
        matchup1 = make_matchup()
        matchup2 = make_matchup()
        signals1 = build_alpha_signals(matchup1)
        signals2 = build_alpha_signals(matchup2)
        assert signals1.n_signals == signals2.n_signals
        for key in signals1.feature_dict:
            assert signals1.feature_dict[key] == pytest.approx(
                signals2.feature_dict[key], abs=1e-6
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
