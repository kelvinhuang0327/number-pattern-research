"""
wbc_backend/prediction/mlb_model_probability_audit.py

P6: Audit module for MLB model probability quality.

Computes orientation checks, Brier / BSS / ECE, and segmented diagnostics
to explain why model_prob_home underperforms the market baseline.

Design rules:
  - Derives home_win from (Home Score > Away Score, Status=Final).
  - Derives market_prob_home from american_moneyline_pair_to_no_vig().
  - No external API calls.
  - No modification to probability values.
  - Paper-only; no production writes.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from wbc_backend.evaluation.metrics import (
    american_moneyline_pair_to_no_vig,
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)

__all__ = [
    "audit_model_probability_rows",
    "segment_model_probability_audit",
]

# ─────────────────────────────────────────────────────────────────────────────
# § 1  Internal helpers
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


def _parse_outcome(row: dict) -> int | None:
    """Return 1 if home won, 0 if home lost, None if unavailable."""
    status = str(row.get("Status") or row.get("status") or "").strip().lower()
    if status not in ("final", "completed", "complete"):
        return None
    home_score = _safe_float(row.get("Home Score") or row.get("home_score"))
    away_score = _safe_float(row.get("Away Score") or row.get("away_score"))
    if home_score is None or away_score is None:
        return None
    return 1 if home_score > away_score else 0


def _parse_market_prob_home(row: dict) -> float | None:
    """No-vig home win probability from moneyline columns."""
    # Explicit column first
    explicit = _safe_float(row.get("market_prob_home"))
    if explicit is not None:
        return explicit
    home_ml = row.get("Home ML") or row.get("home_ml")
    away_ml = row.get("Away ML") or row.get("away_ml")
    if home_ml is None or away_ml is None:
        return None
    try:
        result = american_moneyline_pair_to_no_vig(home_ml, away_ml)
        return result["home_no_vig"]
    except Exception:
        return None


def _parse_model_prob(row: dict, col: str) -> float | None:
    v = _safe_float(row.get(col))
    if v is None:
        return None
    if not (0.0 <= v <= 1.0):
        return None  # invalid range — counted separately
    return v


def _is_invalid_prob(row: dict, col: str) -> bool:
    """Return True if the column value is present but outside [0, 1]."""
    v = _safe_float(row.get(col))
    if v is None:
        return False
    return not (0.0 <= v <= 1.0)


def _ece_from_rows(
    model_probs: list[float],
    outcomes: list[float],
    n_bins: int = 10,
) -> float | None:
    if len(model_probs) < 2:
        return None
    try:
        result = expected_calibration_error(model_probs, outcomes, n_bins=n_bins)
        return result.get("ece")
    except Exception:
        return None


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Full audit
# ─────────────────────────────────────────────────────────────────────────────

def audit_model_probability_rows(
    rows: list[dict],
    *,
    model_prob_col: str = "model_prob_home",
    market_prob_col: str = "market_prob_home",
    outcome_col: str = "home_win",
) -> dict:
    """
    Audit real model probability quality for a list of historical game rows.

    Derives outcome from (Home Score > Away Score, Status=Final) if the
    explicit outcome_col is absent. Derives market_prob_home from moneyline
    odds if the explicit market_prob_col is absent.

    Parameters
    ----------
    rows : list[dict]
        Historical game records with model probabilities merged in.
    model_prob_col : str
        Column name for model win probability (home side).
    market_prob_col : str
        Column name for market no-vig win probability (home side).
    outcome_col : str
        Column name for binary outcome (1=home win, 0=home loss).

    Returns
    -------
    dict
        Audit results including BSS, ECE, orientation checks, source counts.
    """
    row_count = len(rows)
    missing_model_prob_count = 0
    missing_market_prob_count = 0
    missing_outcome_count = 0
    invalid_prob_count = 0

    model_probs: list[float] = []
    market_probs: list[float] = []
    outcomes: list[float] = []

    source_counter: dict[str, int] = defaultdict(int)

    for row in rows:
        # Source counting
        src = str(row.get("probability_source") or "unknown").lower().strip()
        if "calibrated" in src or src == "calibrated_model":
            source_counter["calibrated_model"] += 1
        elif src in ("real_model",):
            source_counter["real_model"] += 1
        elif "proxy" in src or "market" in src:
            source_counter["market_proxy"] += 1
        else:
            source_counter["unknown"] += 1

        # Invalid range check
        if _is_invalid_prob(row, model_prob_col):
            invalid_prob_count += 1

        # Outcome
        outcome: int | None = None
        # Try explicit column first
        explicit_outcome = _safe_float(row.get(outcome_col))
        if explicit_outcome is not None:
            outcome = int(explicit_outcome)
        else:
            outcome = _parse_outcome(row)

        if outcome is None:
            missing_outcome_count += 1
            continue

        # Model prob
        model_p = _parse_model_prob(row, model_prob_col)
        if model_p is None:
            missing_model_prob_count += 1
            continue

        # Market prob
        market_p = _safe_float(row.get(market_prob_col))
        if market_p is None:
            market_p = _parse_market_prob_home(row)
        if market_p is None:
            missing_market_prob_count += 1
            continue

        model_probs.append(model_p)
        market_probs.append(market_p)
        outcomes.append(float(outcome))

    usable_count = len(model_probs)

    # Brier scores
    model_brier: float | None = None
    market_brier: float | None = None
    bss: float | None = None
    ece: float | None = None

    if usable_count >= 2:
        try:
            model_brier = round(brier_score(model_probs, outcomes), 6)
            market_brier = round(brier_score(market_probs, outcomes), 6)
            raw_bss = brier_skill_score(model_brier, market_brier)
            bss = round(raw_bss, 6) if raw_bss is not None else None
        except Exception:
            pass
        ece = _ece_from_rows(model_probs, outcomes)
        if ece is not None:
            ece = round(ece, 6)

    avg_model_prob = _avg(model_probs)
    avg_market_prob = _avg(market_probs)
    avg_outcome = _avg(outcomes)

    # Orientation checks
    model_gt_05 = [m for m, o in zip(model_probs, outcomes) if m > 0.5]
    model_lt_05 = [m for m, o in zip(model_probs, outcomes) if m < 0.5]
    model_gt_05_outcomes = [o for m, o in zip(model_probs, outcomes) if m > 0.5]
    model_lt_05_outcomes = [o for m, o in zip(model_probs, outcomes) if m < 0.5]
    win_when_gt_05 = _avg(model_gt_05_outcomes)
    win_when_lt_05 = _avg(model_lt_05_outcomes)

    model_when_win = [m for m, o in zip(model_probs, outcomes) if o == 1.0]
    model_when_lose = [m for m, o in zip(model_probs, outcomes) if o == 0.0]
    avg_prob_when_home_wins = _avg(model_when_win)
    avg_prob_when_home_loses = _avg(model_when_lose)

    return {
        "row_count": row_count,
        "usable_count": usable_count,
        "missing_model_prob_count": missing_model_prob_count,
        "missing_market_prob_count": missing_market_prob_count,
        "missing_outcome_count": missing_outcome_count,
        "model_brier": model_brier,
        "market_brier": market_brier,
        "brier_skill_score": bss,
        "ece": ece,
        "avg_model_prob": round(avg_model_prob, 6) if avg_model_prob is not None else None,
        "avg_market_prob": round(avg_market_prob, 6) if avg_market_prob is not None else None,
        "avg_outcome": round(avg_outcome, 6) if avg_outcome is not None else None,
        "orientation_checks": {
            "home_win_rate_when_model_gt_0_5": (
                round(win_when_gt_05, 4) if win_when_gt_05 is not None else None
            ),
            "home_win_rate_when_model_lt_0_5": (
                round(win_when_lt_05, 4) if win_when_lt_05 is not None else None
            ),
            "avg_model_prob_when_home_wins": (
                round(avg_prob_when_home_wins, 4) if avg_prob_when_home_wins is not None else None
            ),
            "avg_model_prob_when_home_loses": (
                round(avg_prob_when_home_loses, 4) if avg_prob_when_home_loses is not None else None
            ),
        },
        "probability_range": {
            "min_model_prob": round(min(model_probs), 6) if model_probs else None,
            "max_model_prob": round(max(model_probs), 6) if model_probs else None,
            "invalid_prob_count": invalid_prob_count,
        },
        "source_counts": {
            "real_model": source_counter.get("real_model", 0),
            "calibrated_model": source_counter.get("calibrated_model", 0),
            "market_proxy": source_counter.get("market_proxy", 0),
            "unknown": source_counter.get("unknown", 0),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Segmented audit
# ─────────────────────────────────────────────────────────────────────────────

_SUPPORTED_SEGMENTS = frozenset({
    "month",
    "confidence_bucket",
    "market_prob_bucket",
    "favorite_side",
    "probability_source",
})


def _assign_segment(row: dict, segment_by: str, model_prob_col: str) -> str | None:
    """Return the segment label for a row."""
    if segment_by == "month":
        date_str = str(row.get("Date") or row.get("date") or "")
        if len(date_str) >= 7:
            return date_str[:7]  # YYYY-MM
        return None

    elif segment_by == "confidence_bucket":
        p = _parse_model_prob(row, model_prob_col)
        if p is None:
            return None
        diff = abs(p - 0.5)
        if diff < 0.05:
            return "low_conf_<0.55"
        elif diff < 0.10:
            return "med_conf_<0.60"
        elif diff < 0.15:
            return "hi_conf_<0.65"
        else:
            return "very_hi_conf_>=0.65"

    elif segment_by == "market_prob_bucket":
        mp = _parse_market_prob_home(row)
        if mp is None:
            return None
        if mp < 0.40:
            return "underdog_home_<0.40"
        elif mp < 0.50:
            return "slight_underdog_0.40-0.50"
        elif mp < 0.60:
            return "slight_fav_0.50-0.60"
        else:
            return "heavy_fav_>=0.60"

    elif segment_by == "favorite_side":
        mp = _parse_market_prob_home(row)
        if mp is None:
            return None
        return "home_fav" if mp >= 0.5 else "away_fav"

    elif segment_by == "probability_source":
        src = str(row.get("probability_source") or "unknown").strip()
        return src

    return None


def segment_model_probability_audit(
    rows: list[dict],
    segment_by: str,
    *,
    model_prob_col: str = "model_prob_home",
    market_prob_col: str = "market_prob_home",
    outcome_col: str = "home_win",
) -> list[dict]:
    """
    Segment rows and compute per-segment audit metrics.

    Parameters
    ----------
    rows : list[dict]
        Historical game records.
    segment_by : str
        One of: month | confidence_bucket | market_prob_bucket |
                favorite_side | probability_source
    model_prob_col : str
        Column for model probabilities.
    market_prob_col : str
        Column for market probabilities.
    outcome_col : str
        Column for binary outcome.

    Returns
    -------
    list[dict]
        One dict per segment with: segment, row_count, model_brier,
        market_brier, bss, ece, avg_edge.
    """
    if segment_by not in _SUPPORTED_SEGMENTS:
        raise ValueError(
            f"Unsupported segment_by={segment_by!r}. "
            f"Supported: {sorted(_SUPPORTED_SEGMENTS)}"
        )

    # Group rows by segment label
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        label = _assign_segment(row, segment_by, model_prob_col)
        if label is None:
            label = "__unassigned__"
        buckets[label].append(row)

    results: list[dict] = []
    for segment_label in sorted(buckets):
        seg_rows = buckets[segment_label]
        seg_model_probs: list[float] = []
        seg_market_probs: list[float] = []
        seg_outcomes: list[float] = []
        edges: list[float] = []

        for row in seg_rows:
            outcome: int | None = None
            explicit_outcome = _safe_float(row.get(outcome_col))
            if explicit_outcome is not None:
                outcome = int(explicit_outcome)
            else:
                outcome = _parse_outcome(row)
            if outcome is None:
                continue

            model_p = _parse_model_prob(row, model_prob_col)
            if model_p is None:
                continue

            market_p = _safe_float(row.get(market_prob_col))
            if market_p is None:
                market_p = _parse_market_prob_home(row)
            if market_p is None:
                continue

            seg_model_probs.append(model_p)
            seg_market_probs.append(market_p)
            seg_outcomes.append(float(outcome))
            edges.append(model_p - market_p)

        n = len(seg_model_probs)
        seg_model_brier: float | None = None
        seg_market_brier: float | None = None
        seg_bss: float | None = None
        seg_ece: float | None = None

        if n >= 2:
            try:
                seg_model_brier = round(brier_score(seg_model_probs, seg_outcomes), 6)
                seg_market_brier = round(brier_score(seg_market_probs, seg_outcomes), 6)
                raw_bss = brier_skill_score(seg_model_brier, seg_market_brier)
                seg_bss = round(raw_bss, 6) if raw_bss is not None else None
            except Exception:
                pass
            seg_ece = _ece_from_rows(seg_model_probs, seg_outcomes)
            if seg_ece is not None:
                seg_ece = round(seg_ece, 6)

        avg_edge = _avg(edges)

        results.append({
            "segment": segment_label,
            "segment_by": segment_by,
            "row_count": n,
            "model_brier": seg_model_brier,
            "market_brier": seg_market_brier,
            "bss": seg_bss,
            "ece": seg_ece,
            "avg_edge": round(avg_edge, 6) if avg_edge is not None else None,
        })

    return results
