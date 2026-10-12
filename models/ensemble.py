"""
Ensemble Prediction Engine.

Combines all sub-models with configurable weights and applies WBC
adjustment coefficients before producing final probabilities.
"""
from __future__ import annotations
from typing import Dict, Tuple
from data.wbc_data import MatchData
from config.settings import MODEL_WEIGHTS, WBC_SCORE_VARIANCE
from models import elo as elo_model
from models import bayesian as bayes_model
from models import poisson as poisson_model
from models import gradient_boosting as gbm_model
from models import monte_carlo as mc_model
from models import baseline_heuristics as baseline_model


def predict(match: MatchData) -> Tuple[float, float, Dict]:
    """
    Run all sub-models, blend with configured weights, and return
    (away_wp, home_wp, full_details).
    """
    away = match.away
    home = match.home

    # ── 1. Elo ────────────────────────────────────────────
    elo_aw, elo_hw = elo_model.predict(away, home, neutral=match.neutral_site)

    # ── 2. Bayesian ───────────────────────────────────────
    bay_aw, bay_hw, bay_det = bayes_model.predict(away, home)

    # ── 3. Poisson ────────────────────────────────────────
    poi_aw, poi_hw, poi_det = poisson_model.predict(
        away, home, match.away_sp, match.home_sp,
    )

    # ── 4. Gradient Boosting ──────────────────────────────
    gbm_aw, gbm_hw, gbm_det = gbm_model.predict(
        away, home, match.away_sp, match.home_sp,
    )

    # ── 5. Monte Carlo ───────────────────────────────────
    mc_aw, mc_hw, mc_det = mc_model.predict(match)

    # ── 6. Baseline Heuristics (GitHub Repo Logic) ───────
    # We map MatchData to the simple dict format baseline expects
    home_stats = {
        "win_pct": getattr(home.win_loss_record, 'win_pct', 0.5) if getattr(home, 'win_loss_record', None) else 0.5,
        "ha_win_pct": getattr(home.home_away_record, 'home_win_pct', 0.5) if getattr(home, 'home_away_record', None) else 0.5,
        "last_10_win_pct": getattr(home.recent_form, 'last_10_win_pct', 0.5) if getattr(home, 'recent_form', None) else 0.5,
        "avg_runs": getattr(home, 'runs_per_game', 4.5)
    }
    away_stats = {
        "win_pct": getattr(away.win_loss_record, 'win_pct', 0.5) if getattr(away, 'win_loss_record', None) else 0.5,
        "opp_ha_win_pct": getattr(away.home_away_record, 'away_win_pct', 0.5) if getattr(away, 'home_away_record', None) else 0.5,
        "last_10_win_pct": getattr(away.recent_form, 'last_10_win_pct', 0.5) if getattr(away, 'recent_form', None) else 0.5,
        "avg_runs": getattr(away, 'runs_per_game', 4.5)
    }
    bsl_aw, bsl_hw = baseline_model.get_baseline_prediction(match.game_type, home_stats, away_stats)

    # ── 7. Stacking Meta-Learner ──────────────────────────
    from models.stacking_model import meta_predict

    sub_results = {
        "elo": (elo_aw, elo_hw),
        "bayesian": (bay_aw, bay_hw),
        "poisson": (poi_aw, poi_hw),
        "gbm": (gbm_aw, gbm_hw),
        "monte_carlo": (mc_aw, mc_hw),
        "baseline": (bsl_aw, bsl_hw),
    }

    context = {
        "roster_strength_index": away.roster_vol.roster_strength_index if away.roster_vol else 100,
        "is_neutral": match.neutral_site,
        "round": match.round_name,
        "game_type": match.game_type,
        "steam_move": match.steam_move
    }

    away_wp, home_wp, confidence = meta_predict(sub_results, context)

    # ── Build details ─────────────────────────────────────
    details = {
        "sub_models": {
            "elo":        {"away": round(elo_aw, 4), "home": round(elo_hw, 4)},
            "bayesian":   {"away": round(bay_aw, 4), "home": round(bay_hw, 4), **bay_det},
            "poisson":    {"away": round(poi_aw, 4), "home": round(poi_hw, 4), **poi_det},
            "gbm":        {"away": round(gbm_aw, 4), "home": round(gbm_hw, 4), **gbm_det},
            "monte_carlo": {"away": round(mc_aw, 4), "home": round(mc_hw, 4), **mc_det},
            "baseline":   {"away": round(bsl_aw, 4), "home": round(bsl_hw, 4)},
        },
        "meta_learning": True,
        "confidence_score": round(confidence, 4),
        "ensemble_final": {"away": round(away_wp, 4), "home": round(home_wp, 4)},
    }

    return away_wp, home_wp, details
