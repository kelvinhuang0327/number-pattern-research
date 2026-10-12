"""
Phase 1 — Edge Validity Engine
================================
Determines whether each prediction carries a REAL statistical edge
versus noise/randomness. No bet is placed unless the edge is provably
robust across multiple independent checks.

Inputs
------
- sub_model_probs : dict[str, float]   — each model's home-win probability
- ensemble_prob   : float              — blended ensemble probability
- market_odds     : float              — current decimal odds
- calibration_a/b : float              — Platt calibration parameters
- historical_brier: float              — model's running Brier score

Output
------
EdgeScore 0–100.  If < 65 → FORBIDDEN to bet.

Scoring rubric (max 100):
  Consensus Variance    0-25  (lower var → higher score)
  Prediction Entropy    0-25  (more decisive → higher)
  Calibration Confidence 0-25 (better calibration → higher)
  Market Efficiency      0-25 (less efficient → higher)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


# ─── Configuration ───────────────────────────────────────────────────────────

EDGE_THRESHOLD = 65        # minimum EdgeScore to allow a bet
EDGE_STRONG = 80           # strong edge territory
EDGE_ELITE = 90            # elite edge — max sizing
MAX_CONSENSUS_STDDEV = 0.15  # above this → max penalty
IDEAL_ENTROPY_RANGE = (0.40, 0.92)  # decisive but not overconfident (sports betting realistic)
BRIER_BASELINE = 0.25       # coin-flip baseline


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class EdgeReport:
    """Complete edge validity assessment for a single prediction."""
    # Component scores (0-25 each)
    consensus_score: float = 0.0
    entropy_score: float = 0.0
    calibration_score: float = 0.0
    market_efficiency_score: float = 0.0

    # Final
    edge_score: float = 0.0      # 0-100
    is_valid: bool = False        # True if edge_score >= threshold
    tier: str = "FORBIDDEN"       # FORBIDDEN | WEAK | MODERATE | STRONG | ELITE

    # Diagnostics
    model_stddev: float = 0.0
    prediction_entropy: float = 0.0
    calibration_gap: float = 0.0
    market_deviation: float = 0.0
    model_agreement_pct: float = 0.0
    n_models_positive_ev: int = 0
    details: dict[str, float] = field(default_factory=dict)


# ─── Scoring Functions ──────────────────────────────────────────────────────

def _score_consensus_variance(
    sub_model_probs: dict[str, float],
    ensemble_prob: float,
) -> tuple[float, float, float]:
    """
    Score 0-25 based on how tightly the sub-models agree.

    Lower variance → higher score.
    Also returns stddev and agreement percentage.
    """
    if not sub_model_probs:
        return 0.0, 1.0, 0.0

    probs = list(sub_model_probs.values())
    n = len(probs)
    mean = sum(probs) / n
    variance = sum((p - mean) ** 2 for p in probs) / n
    stddev = math.sqrt(variance)

    # Agreement: what % of models agree on the side (>0.5 or <0.5)
    side = 1 if ensemble_prob >= 0.5 else 0
    agree = sum(1 for p in probs if (p >= 0.5) == bool(side)) / n

    # Score: perfect agreement (stddev→0) = 25, stddev≥0.15 = 0
    if stddev >= MAX_CONSENSUS_STDDEV:
        score = 0.0
    else:
        score = 25.0 * (1.0 - stddev / MAX_CONSENSUS_STDDEV)

    # Bonus for high agreement
    if agree >= 0.85:
        score = min(25.0, score * 1.15)

    return round(score, 2), round(stddev, 4), round(agree, 3)


def _score_prediction_entropy(
    ensemble_prob: float,
) -> tuple[float, float]:
    """
    Score 0-25 based on prediction entropy.

    We want a prediction that is decisive (away from 0.5) but not
    pathologically overconfident (away from 0.0 or 1.0).

    Best range: entropy in [0.10, 0.40] bits.
    """
    # Binary entropy: H = -p*log2(p) - (1-p)*log2(1-p)
    p = max(0.001, min(0.999, ensemble_prob))
    entropy = -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    # Maximum entropy at p=0.5 → H=1.0

    lo, hi = IDEAL_ENTROPY_RANGE
    if lo <= entropy <= hi:
        # Optimal: scale within ideal range (center is best)
        center = (lo + hi) / 2.0
        dist = abs(entropy - center) / (hi - lo) * 2.0
        score = 25.0 * (1.0 - dist * 0.3)
    elif entropy < lo:
        # Too confident — risky overconfidence
        score = 25.0 * (entropy / lo) * 0.8
    else:
        # Too uncertain — near 50/50
        if entropy >= 0.95:
            score = 0.0
        else:
            score = 25.0 * max(0, (1.0 - entropy) / (1.0 - hi)) * 0.6

    return round(max(0, min(25, score)), 2), round(entropy, 4)


def _score_calibration_confidence(
    model_brier: float,
    ensemble_prob: float,
    actual_implied: float,
    calibration_a: float = 1.0,
    calibration_b: float = 0.0,
) -> tuple[float, float]:
    """
    Score 0-25 based on how well-calibrated the model is.

    Factors:
      - Running Brier vs baseline (0.25)
      - Platt calibration slope deviation from 1.0
      - Gap between raw and calibrated probability
    """
    # 1. Brier improvement over baseline
    brier_improvement = max(0, BRIER_BASELINE - model_brier) / BRIER_BASELINE
    brier_score = brier_improvement * 12.0  # max 12 from Brier alone

    # 2. Calibration quality: slope a should be ~1.0, intercept b ~0.0
    slope_penalty = abs(calibration_a - 1.0) * 5.0
    intercept_penalty = abs(calibration_b) * 10.0
    calib_quality = max(0, 8.0 - slope_penalty - intercept_penalty)

    # 3. Raw vs calibrated gap — big gap = model needs heavy correction
    raw_logit = math.log(max(0.001, ensemble_prob) / max(0.001, 1 - ensemble_prob))
    calibrated = 1.0 / (1.0 + math.exp(-(calibration_a * raw_logit + calibration_b)))
    gap = abs(calibrated - ensemble_prob)
    gap_penalty = gap * 20.0
    gap_score = max(0, 5.0 - gap_penalty)

    total = brier_score + calib_quality + gap_score
    return round(max(0, min(25, total)), 2), round(gap, 4)


def _score_market_efficiency(
    ensemble_prob: float,
    market_implied_prob: float,
    sharp_signals: int = 0,
    line_movement_count: int = 0,
) -> tuple[float, float]:
    """
    Score 0-25 based on perceived market inefficiency.

    More edge available in less efficient markets:
      - Wide gap between model and market → potential edge
      - Few sharp signals → market hasn't converged
      - Low line movement → bookmaker hasn't adjusted
    """
    # Model-vs-market deviation
    deviation = abs(ensemble_prob - market_implied_prob)

    # Sweet spot: 3-18% deviation. Too large = model wrong. Too small = no edge.
    if deviation < 0.02:
        dev_score = deviation / 0.02 * 3.0  # near-zero edge
    elif deviation <= 0.18:
        dev_score = 3.0 + (deviation - 0.02) / 0.16 * 12.0  # scaling up
    else:
        # Excessive deviation: likely model error — penalise
        overshoot = (deviation - 0.18) / 0.10
        dev_score = max(0, 15.0 - overshoot * 10.0)

    # Sharp signal penalty: more sharps → more efficient
    sharp_penalty = min(5, sharp_signals) * 1.5
    sharp_score = max(0, 7.5 - sharp_penalty)

    # Movement penalty: lots of movement → closing rapidly
    move_penalty = min(5, line_movement_count) * 0.5
    move_score = max(0, 2.5 - move_penalty)

    total = dev_score + sharp_score + move_score
    return round(max(0, min(25, total)), 2), round(deviation, 4)


# ─── Main Engine ────────────────────────────────────────────────────────────

def compute_edge_score(
    sub_model_probs: dict[str, float],
    ensemble_prob: float,
    market_odds: float,
    model_brier: float = 0.248,
    calibration_a: float = 1.111,
    calibration_b: float = -0.019,
    sharp_signals: int = 0,
    line_movements: int = 0,
    odds_band_roi: float | None = None,
) -> EdgeReport:
    """
    Compute the Edge Validity Score (0-100).

    Parameters
    ----------
    sub_model_probs : dict
        {model_name: home_win_probability} from each sub-model
    ensemble_prob : float
        Blended ensemble probability (home win)
    market_odds : float
        Current decimal odds for the side being evaluated
    model_brier : float
        Running Brier score of ensemble
    calibration_a, calibration_b : float
        Platt calibration parameters
    sharp_signals : int
        Number of detected sharp-money signals
    line_movements : int
        Number of detected line movements
    odds_band_roi : float, optional
        Historical ROI for this odds band (from backtest)

    Returns
    -------
    EdgeReport
    """
    report = EdgeReport()

    # Market implied probability
    market_implied = 1.0 / max(1.01, market_odds)

    # ── Component 1: Consensus Variance ───────────────────
    cons_score, stddev, agreement = _score_consensus_variance(
        sub_model_probs, ensemble_prob
    )
    report.consensus_score = cons_score
    report.model_stddev = stddev
    report.model_agreement_pct = agreement

    # Count models with positive EV
    n_positive_ev = sum(
        1 for p in sub_model_probs.values()
        if p * market_odds > 1.0
    )
    report.n_models_positive_ev = n_positive_ev

    # ── Component 2: Prediction Entropy ───────────────────
    ent_score, entropy = _score_prediction_entropy(ensemble_prob)
    report.entropy_score = ent_score
    report.prediction_entropy = entropy

    # ── Component 3: Calibration Confidence ───────────────
    cal_score, cal_gap = _score_calibration_confidence(
        model_brier, ensemble_prob, market_implied,
        calibration_a, calibration_b,
    )
    report.calibration_score = cal_score
    report.calibration_gap = cal_gap

    # ── Component 4: Market Efficiency ────────────────────
    mkt_score, deviation = _score_market_efficiency(
        ensemble_prob, market_implied,
        sharp_signals, line_movements,
    )
    report.market_efficiency_score = mkt_score
    report.market_deviation = deviation

    # ── Odds Band Bonus/Penalty ───────────────────────────
    band_bonus = 0.0
    if odds_band_roi is not None:
        if odds_band_roi > 0.01:
            band_bonus = min(5.0, odds_band_roi * 100)  # up to +5
        elif odds_band_roi < -0.03:
            band_bonus = max(-10.0, odds_band_roi * 100)  # down to -10

    # ── Final Score ───────────────────────────────────────
    raw_score = (
        report.consensus_score
        + report.entropy_score
        + report.calibration_score
        + report.market_efficiency_score
        + band_bonus
    )
    report.edge_score = round(max(0, min(100, raw_score)), 1)

    # ── Tier Classification ───────────────────────────────
    if report.edge_score >= EDGE_ELITE:
        report.tier = "ELITE"
        report.is_valid = True
    elif report.edge_score >= EDGE_STRONG:
        report.tier = "STRONG"
        report.is_valid = True
    elif report.edge_score >= EDGE_THRESHOLD:
        report.tier = "MODERATE"
        report.is_valid = True
    elif report.edge_score >= 50:
        report.tier = "WEAK"
        report.is_valid = False
    else:
        report.tier = "FORBIDDEN"
        report.is_valid = False

    # ── Diagnostics ───────────────────────────────────────
    report.details = {
        "consensus_raw": cons_score,
        "entropy_raw": ent_score,
        "calibration_raw": cal_score,
        "market_eff_raw": mkt_score,
        "band_bonus": band_bonus,
        "model_stddev": stddev,
        "agreement": agreement,
        "n_models_pos_ev": n_positive_ev,
        "entropy_bits": entropy,
        "calibration_gap": cal_gap,
        "market_deviation": deviation,
    }

    return report


def get_odds_band_roi(odds: float) -> float | None:
    """
    Return historical ROI for the given odds band.
    Based on walk-forward backtest results (model_artifacts.json).
    """
    BAND_ROI = {
        (1.50, 1.80): -0.0519,
        (1.81, 2.10): +0.0254,
        (2.11, 2.60): +0.0151,
        (2.61, 3.50): -0.0721,
        (3.51, 10.0): -0.0704,
    }
    for (lo, hi), roi in BAND_ROI.items():
        if lo <= odds <= hi:
            return roi
    return None
