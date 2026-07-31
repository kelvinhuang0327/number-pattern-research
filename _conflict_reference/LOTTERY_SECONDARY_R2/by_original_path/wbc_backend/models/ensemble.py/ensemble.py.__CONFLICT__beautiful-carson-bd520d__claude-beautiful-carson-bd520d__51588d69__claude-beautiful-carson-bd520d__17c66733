"""
Hybrid Ensemble Prediction Engine — § 二 模型架構

Combines all sub-models (Elo, Poisson, Bayesian, Baseline, XGB, LGBM, NN)
via the Stacking meta-learner, applying WBC adjustments and advanced features.
"""
from __future__ import annotations

import logging

from wbc_backend.config.settings import ModelConfig
from wbc_backend.domain.schemas import (
    Matchup, PredictionResult, SubModelResult,
)
from wbc_backend.features.advanced import build_advanced_features
from wbc_backend.features.alpha_signals import build_alpha_signals
from wbc_backend.models import elo as elo_model
from wbc_backend.models import poisson as poisson_model
from wbc_backend.models import bayesian as bayesian_model
from wbc_backend.models import baseline as baseline_model
from wbc_backend.models.stacking import StackingModel
from wbc_backend.models.dynamic_ensemble import blend_predictions
from wbc_backend.intelligence.regime_classifier import RegimeClassifier
from wbc_backend.models.gbm_stack import RealGBMStack

logger = logging.getLogger(__name__)


def predict_matchup(  # NOSONAR  # noqa: C901
    matchup: Matchup,
    config: ModelConfig | None = None,
) -> PredictionResult:
    """
    Run all sub-models, blend via stacking meta-learner,
    and return final PredictionResult.
    """
    config = config or ModelConfig()

    # ── 1. Statistical models ────────────────────────────
    sub_results: list[SubModelResult] = []

    elo_result = elo_model.predict(matchup, config.elo_home_advantage)
    sub_results.append(elo_result)

    poisson_result = poisson_model.predict(matchup)
    sub_results.append(poisson_result)

    bayesian_result = bayesian_model.predict(matchup)
    sub_results.append(bayesian_result)

    baseline_result = baseline_model.predict(matchup)
    sub_results.append(baseline_result)

    # ── 2. Advanced + Alpha features ─────────────────────
    adv_features = build_advanced_features(matchup)
    alpha_signals = build_alpha_signals(matchup)
    merged_features = dict(adv_features.feature_dict)
    merged_features.update(alpha_signals.feature_dict)

    # ── 3. Machine learning models (RealGBMStack) ───
    try:
        # P0.1 Upgrade: RealGBM Stack replaces separate XGB/LGBM
        gbm_stack = RealGBMStack(config)
        gbm_result = gbm_stack.predict_single(merged_features)
        sub_results.append(gbm_result)
    except Exception as e:
        logger.warning("RealGBMStack failed: %s — using fallback", e)
        sub_results.append(SubModelResult(
            model_name="real_gbm_stack", home_win_prob=0.5, away_win_prob=0.5, confidence=0.2
        ))

    # Neural Net provides an orthogonal signal to the tree models
    from wbc_backend.models.neural_net import NeuralNetModel
    try:
        nn = NeuralNetModel(config)
        sub_results.append(nn.predict_single(merged_features))
    except Exception as e:
        logger.warning("NeuralNet failed: %s", e)

    # ── 4. Stacking + Dynamic Ensemble ───────────────────
    stacker = StackingModel()
    stack_home_wp, _, stack_confidence = stacker.predict(sub_results)

    dynamic_blend = blend_predictions(
        sub_results,
        tournament=matchup.tournament,
        round_name=matchup.round_name,
    )

    # Blend static stacker and dynamic Bayesian ensemble to stabilize live output.
    home_wp = 0.4 * stack_home_wp + 0.6 * dynamic_blend.home_win_prob
    away_wp = 1.0 - home_wp
    confidence = max(0.1, min(0.98, 0.4 * stack_confidence + 0.6 * dynamic_blend.confidence))

    alpha_quality = float(alpha_signals.n_signals) / 276.0 if alpha_signals.n_signals > 0 else 0.0
    confidence *= (0.92 + 0.08 * min(1.0, alpha_quality))
    diagnostics = {
        "model_count": float(len(sub_results)),
        "stack_confidence": float(confidence),
        "stack_home_wp": float(stack_home_wp),
        "dynamic_home_wp": float(dynamic_blend.home_win_prob),
        "dynamic_confidence": float(dynamic_blend.confidence),
        "alpha_signals_n": float(alpha_signals.n_signals),
        "alpha_categories_n": float(len(alpha_signals.categories_computed)),
        "dynamic_weight_updates": float(dynamic_blend.diagnostics.get("n_weight_updates", 0.0)),
    }

    # ── 5. Use Poisson expected runs ─────────────────────
    exp_home_runs = poisson_result.expected_home_runs
    exp_away_runs = poisson_result.expected_away_runs

    # ── 6. Apply fatigue adjustments to expected runs ────
    if adv_features.home_sp_fatigue > 0.3:
        exp_home_runs -= adv_features.home_sp_fatigue * 0.5
        exp_away_runs += adv_features.home_sp_fatigue * 0.3
    if adv_features.away_sp_fatigue > 0.3:
        exp_away_runs -= adv_features.away_sp_fatigue * 0.5
        exp_home_runs += adv_features.away_sp_fatigue * 0.3

    # Ensure reasonable bounds
    exp_home_runs = max(1.5, min(10.0, exp_home_runs))
    exp_away_runs = max(1.5, min(10.0, exp_away_runs))

    # ── 7. Build x-factors list ──────────────────────────
    x_factors: list[str] = []

    if adv_features.home_sp_fatigue > 0.5:
        x_factors.append(f"Home SP fatigue alert (score={adv_features.home_sp_fatigue:.2f})")
    if adv_features.away_sp_fatigue > 0.5:
        x_factors.append(f"Away SP fatigue alert (score={adv_features.away_sp_fatigue:.2f})")
    if adv_features.home_bullpen_stress > 0.6:
        x_factors.append(f"Home bullpen high stress ({adv_features.home_bullpen_stress:.2f})")
    if adv_features.away_bullpen_stress > 0.6:
        x_factors.append(f"Away bullpen high stress ({adv_features.away_bullpen_stress:.2f})")

    edge_diff = adv_features.home_matchup_edge - adv_features.away_matchup_edge
    if abs(edge_diff) > 0.05:
        side = "Home" if edge_diff > 0 else "Away"
        x_factors.append(f"{side} has matchup edge advantage ({edge_diff:+.3f})")

    clutch_diff = adv_features.home_clutch_index - adv_features.away_clutch_index
    if abs(clutch_diff) > 0.2:
        side = "Home" if clutch_diff > 0 else "Away"
        x_factors.append(f"{side} has clutch advantage ({clutch_diff:+.3f})")

    if not x_factors:
        x_factors.append("No significant X-factors detected")

    x_factors.append(
        f"Alpha signals computed: {alpha_signals.n_signals} ({', '.join(alpha_signals.categories_computed[:3])}{'...' if len(alpha_signals.categories_computed) > 3 else ''})"
    )

    # ── 9. SNR (Signal-to-Noise Ratio) Optimization ──────
    # Institutional safeguard: Divergence check vs. Sharp Market (Pinnacle)
    snr_score = 1.0
    odds_feed = getattr(matchup, "odds", [])
    p_home_odds = next(
        (
            o.decimal_odds
            for o in odds_feed
            if getattr(o, "sportsbook", "") == "Pinnacle"
            and getattr(o, "market", "") == "ML"
            and getattr(o, "side", "") == matchup.home.team
        ),
        None,
    )

    divergence = 0.0
    if p_home_odds:
        p_home_prob = 1.0 / p_home_odds
        divergence = abs(home_wp - p_home_prob)
        # If model is too 'arrogant' (>15% gap) without high internal consensus, degrade SNR
        if divergence > 0.15 and confidence < 0.65:
            snr_score = 0.45
            # Shrinkage: pull 40% toward market consensus
            home_wp = 0.6 * home_wp + 0.4 * p_home_prob
            away_wp = 1.0 - home_wp
            logger.warning("[STRATEGY] High Market Divergence (%.3f). SNR penalty applied.", divergence)

    home_wp = max(0.03, min(0.97, home_wp))
    away_wp = 1.0 - home_wp

    diagnostics["snr"] = snr_score
    diagnostics["divergence"] = divergence
    diagnostics["regime"] = RegimeClassifier.classify(matchup.round_name).value

    return PredictionResult(
        game_id=matchup.game_id,
        home_win_prob=round(home_wp, 4),
        away_win_prob=round(away_wp, 4),
        expected_home_runs=round(exp_home_runs, 2),
        expected_away_runs=round(exp_away_runs, 2),
        x_factors=x_factors,
        diagnostics=diagnostics,
        sub_model_results=sub_results,
        confidence_score=round(confidence * snr_score, 4),
    )
