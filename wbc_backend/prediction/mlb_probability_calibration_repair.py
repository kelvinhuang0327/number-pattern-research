"""
wbc_backend/prediction/mlb_probability_calibration_repair.py

P6: Monotonic bin calibration repair for MLB model probabilities.

Approach:
  - Divide model_prob_home into n equal-width bins.
  - Replace raw probability with the empirical win rate in each bin.
  - Bins with fewer than min_bin_size samples fall back to global win rate.
  - Output probability_source = "calibrated_model".
  - Preserves raw_model_prob_home for traceability.

IMPORTANT: This is IN-SAMPLE calibration.
  - It is NOT deployable without OOF/walk-forward validation.
  - All outputs carry calibration_source_trace with in_sample_warning.

Design rules:
  - No external API calls.
  - No future-aware data access.
  - paper_only always.
  - All calibrated probabilities are in [0, 1].
"""
from __future__ import annotations

import copy
import math
from typing import Any

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)

__all__ = [
    "calibrate_probabilities_by_bins",
    "evaluate_calibration_candidate",
]

_IN_SAMPLE_WARNING = (
    "in-sample calibration candidate — not production deployable unless OOF validated"
)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        s = str(v).replace("+", "").strip()
        if not s or s.lower() in ("nan", "none", ""):
            return None
        f = float(s)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def _clamp(v: float, lo: float = 1e-6, hi: float = 1.0 - 1e-6) -> float:
    return max(lo, min(hi, v))


def _parse_outcome(row: dict) -> int | None:
    """1 = home win, 0 = home loss, None if unknown."""
    status = str(row.get("Status") or row.get("status") or "").strip().lower()
    if status not in ("final", "completed", "complete"):
        return None
    home_score = _safe_float(row.get("Home Score") or row.get("home_score"))
    away_score = _safe_float(row.get("Away Score") or row.get("away_score"))
    if home_score is None or away_score is None:
        return None
    return 1 if home_score > away_score else 0


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Bin calibration
# ─────────────────────────────────────────────────────────────────────────────

def calibrate_probabilities_by_bins(
    rows: list[dict],
    *,
    model_prob_col: str = "model_prob_home",
    outcome_col: str = "home_win",
    n_bins: int = 10,
    min_bin_size: int = 30,
) -> list[dict]:
    """
    Isotonic-style bin calibration: replace model_prob_home with empirical
    win rate in each equal-width probability bin.

    Parameters
    ----------
    rows : list[dict]
        Historical game records with model_prob_home.
    model_prob_col : str
        Column name for model probabilities.
    outcome_col : str
        Column name for binary outcome (1=home win, 0=home loss).
    n_bins : int
        Number of equal-width bins over [0, 1].
    min_bin_size : int
        Minimum samples per bin; fallback to global rate if below this.

    Returns
    -------
    list[dict]
        Copy of rows with:
          - raw_model_prob_home: original model probability
          - model_prob_home: calibrated probability (bin win rate)
          - model_prob_away: 1 - model_prob_home
          - probability_source: "calibrated_model"
          - calibration_source_trace: dict with calibration metadata
    """
    # Step 1: collect (raw_prob, outcome) pairs
    pairs: list[tuple[float, float]] = []
    for row in rows:
        raw_p = _safe_float(row.get(model_prob_col))
        if raw_p is None or not (0.0 <= raw_p <= 1.0):
            continue
        outcome: int | None = None
        explicit = _safe_float(row.get(outcome_col))
        if explicit is not None:
            outcome = int(explicit)
        else:
            outcome = _parse_outcome(row)
        if outcome is None:
            continue
        pairs.append((raw_p, float(outcome)))

    # Step 2: build bins
    bin_width = 1.0 / n_bins
    # bins[i] = list of outcomes for probs in [i*w, (i+1)*w)
    bin_outcomes: list[list[float]] = [[] for _ in range(n_bins)]
    for raw_p, outcome in pairs:
        idx = min(int(raw_p / bin_width), n_bins - 1)
        bin_outcomes[idx].append(outcome)

    # Step 3: compute global win rate as fallback
    if pairs:
        global_win_rate = sum(o for _, o in pairs) / len(pairs)
    else:
        global_win_rate = 0.5

    # Step 4: compute bin calibrated probabilities
    bin_map: list[tuple[float, int, str]] = []  # (calibrated_prob, bin_size, fallback_reason)
    for i, bin_outs in enumerate(bin_outcomes):
        n = len(bin_outs)
        if n >= min_bin_size:
            cal_p = sum(bin_outs) / n
            fallback = "none"
        else:
            # Blend with global rate weighted by available samples
            if n > 0:
                raw_cal = sum(bin_outs) / n
                # Weighted blend: n samples toward raw, rest toward global
                weight = n / min_bin_size
                cal_p = weight * raw_cal + (1 - weight) * global_win_rate
                fallback = f"sparse_blend(n={n},global={global_win_rate:.4f})"
            else:
                cal_p = global_win_rate
                fallback = f"empty_bin_global({global_win_rate:.4f})"
        cal_p = _clamp(cal_p)
        bin_map.append((cal_p, len(bin_outs), fallback))

    # Step 5: apply calibration to each row
    calibrated_rows: list[dict] = []
    bin_stats = [
        {
            "bin_index": i,
            "bin_lo": i * bin_width,
            "bin_hi": (i + 1) * bin_width,
            "bin_size": bin_map[i][1],
            "calibrated_prob": round(bin_map[i][0], 6),
            "fallback": bin_map[i][2],
        }
        for i in range(n_bins)
    ]

    calibration_trace = {
        "method": "equal_width_bin_calibration",
        "n_bins": n_bins,
        "min_bin_size": min_bin_size,
        "global_win_rate": round(global_win_rate, 6),
        "usable_pairs": len(pairs),
        "in_sample_warning": _IN_SAMPLE_WARNING,
        "bin_stats": bin_stats,
    }

    for row in rows:
        new_row = copy.copy(row)
        raw_p = _safe_float(row.get(model_prob_col))

        # Preserve raw probability
        new_row["raw_model_prob_home"] = raw_p

        if raw_p is not None and 0.0 <= raw_p <= 1.0:
            idx = min(int(raw_p / bin_width), n_bins - 1)
            cal_p, _, _ = bin_map[idx]
        else:
            # No model prob → keep as-is (don't calibrate)
            cal_p = raw_p

        if cal_p is not None:
            new_row[model_prob_col] = round(cal_p, 6)
            new_row["model_prob_away"] = round(1.0 - cal_p, 6)
        new_row["probability_source"] = "calibrated_model"
        new_row["calibration_source_trace"] = calibration_trace

        calibrated_rows.append(new_row)

    return calibrated_rows


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_calibration_candidate(
    original_rows: list[dict],
    calibrated_rows: list[dict],
    *,
    model_prob_col: str = "model_prob_home",
    outcome_col: str = "home_win",
) -> dict:
    """
    Compare original vs calibrated probabilities.

    Returns
    -------
    dict with:
      original_bss, calibrated_bss, original_ece, calibrated_ece,
      delta_bss, delta_ece, recommendation
    """
    def _extract_probs_outcomes(rows: list[dict]) -> tuple[list[float], list[float], list[float]]:
        model_probs, market_probs, outcomes = [], [], []
        from wbc_backend.evaluation.metrics import american_moneyline_pair_to_no_vig
        for row in rows:
            raw_p = _safe_float(row.get(model_prob_col))
            if raw_p is None or not (0.0 <= raw_p <= 1.0):
                continue
            # Outcome
            outcome: int | None = None
            explicit = _safe_float(row.get(outcome_col))
            if explicit is not None:
                outcome = int(explicit)
            else:
                outcome = _parse_outcome(row)
            if outcome is None:
                continue
            # Market prob
            home_ml = row.get("Home ML") or row.get("home_ml")
            away_ml = row.get("Away ML") or row.get("away_ml")
            if home_ml is None or away_ml is None:
                continue
            try:
                mp = american_moneyline_pair_to_no_vig(home_ml, away_ml)["home_no_vig"]
            except Exception:
                continue
            model_probs.append(raw_p)
            market_probs.append(mp)
            outcomes.append(float(outcome))
        return model_probs, market_probs, outcomes

    orig_model, orig_market, orig_outcomes = _extract_probs_outcomes(original_rows)
    cal_model, cal_market, cal_outcomes = _extract_probs_outcomes(calibrated_rows)

    # Original metrics
    orig_bss: float | None = None
    orig_ece: float | None = None
    if len(orig_model) >= 2 and len(orig_market) >= 2:
        try:
            ob = brier_score(orig_model, orig_outcomes)
            mb = brier_score(orig_market, orig_outcomes)
            raw = brier_skill_score(ob, mb)
            orig_bss = round(raw, 6) if raw is not None else None
        except Exception:
            pass
        result = expected_calibration_error(orig_model, orig_outcomes)
        orig_ece = round(result.get("ece", 0.0), 6) if result else None

    # Calibrated metrics
    cal_bss: float | None = None
    cal_ece: float | None = None
    if len(cal_model) >= 2 and len(cal_market) >= 2:
        try:
            cb = brier_score(cal_model, cal_outcomes)
            mb2 = brier_score(cal_market, cal_outcomes)
            raw2 = brier_skill_score(cb, mb2)
            cal_bss = round(raw2, 6) if raw2 is not None else None
        except Exception:
            pass
        result2 = expected_calibration_error(cal_model, cal_outcomes)
        cal_ece = round(result2.get("ece", 0.0), 6) if result2 else None

    # Delta
    delta_bss: float | None = None
    if orig_bss is not None and cal_bss is not None:
        delta_bss = round(cal_bss - orig_bss, 6)

    delta_ece: float | None = None
    if orig_ece is not None and cal_ece is not None:
        delta_ece = round(cal_ece - orig_ece, 6)

    # Recommendation
    if cal_bss is None or orig_bss is None:
        recommendation = "CANDIDATE_REJECTED"
    elif cal_bss <= 0:
        recommendation = "KEEP_BLOCKED"
    elif delta_bss is not None and delta_bss > 0:
        recommendation = "CANDIDATE_IMPROVED_BUT_NEEDS_OOF"
    else:
        recommendation = "CANDIDATE_REJECTED"

    return {
        "original_bss": orig_bss,
        "calibrated_bss": cal_bss,
        "original_ece": orig_ece,
        "calibrated_ece": cal_ece,
        "delta_bss": delta_bss,
        "delta_ece": delta_ece,
        "recommendation": recommendation,
        "in_sample_warning": _IN_SAMPLE_WARNING,
        "usable_original_rows": len(orig_model),
        "usable_calibrated_rows": len(cal_model),
    }
