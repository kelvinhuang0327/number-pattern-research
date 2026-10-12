"""
Gradient Boosting proxy model.

In a full production system this would be a trained XGBoost / LightGBM model.
Here we implement a feature-engineered logistic function that mimics the output
of a tuned GBM, using the same feature vector that would feed the real model.
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import math
from data.wbc_data import TeamStats, PitcherStats


# Feature weights (learned from hypothetical training run)
WEIGHTS: Dict[str, float] = {
    "elo_diff":              0.0018,
    "rpg_diff":              0.075,
    "sp_era_diff":          -0.12,
    "sp_whip_diff":         -0.35,
    "sp_k9_diff":            0.025,
    "bullpen_era_diff":     -0.08,
    "bp_fatigue_diff":      -0.0008,
    "lineup_wrc_diff":       0.004,
    "def_eff_diff":          1.8,
    "recent_form":           0.15,
    "intercept":             0.0,
}


def _feature_vector(
    team: TeamStats,
    opp: TeamStats,
    sp: PitcherStats,
    opp_sp: PitcherStats,
) -> Dict[str, float]:
    """Build feature dict (team − opponent)."""
    return {
        "elo_diff":         team.elo - opp.elo,
        "rpg_diff":         team.runs_per_game - opp.runs_per_game,
        "sp_era_diff":      sp.era - opp_sp.era,          # negative is good for `team`
        "sp_whip_diff":     sp.whip - opp_sp.whip,
        "sp_k9_diff":       sp.k_per_9 - opp_sp.k_per_9,
        "bullpen_era_diff": team.bullpen_era - opp.bullpen_era,
        "bp_fatigue_diff":  team.bullpen_pitches_3d - opp.bullpen_pitches_3d,
        "lineup_wrc_diff":  team.lineup_wrc_plus - opp.lineup_wrc_plus,
        "def_eff_diff":     team.defense_efficiency - opp.defense_efficiency,
        "recent_form":      (team.runs_per_game - team.runs_allowed_per_game)
                            - (opp.runs_per_game - opp.runs_allowed_per_game),
    }


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ez = math.exp(x)
        return ez / (1.0 + ez)


def predict(
    away: TeamStats,
    home: TeamStats,
    away_sp: PitcherStats,
    home_sp: PitcherStats,
) -> Tuple[float, float, Dict]:
    """Return (away_wp, home_wp, feature_dict)."""
    feats = _feature_vector(away, home, away_sp, home_sp)

    logit = WEIGHTS["intercept"]
    for k, v in feats.items():
        if k in WEIGHTS:
            logit += WEIGHTS[k] * v

    away_wp = _sigmoid(logit)
    home_wp = 1.0 - away_wp

    details = {k: round(v, 4) for k, v in feats.items()}
    details["logit"] = round(logit, 4)

    return away_wp, home_wp, details
