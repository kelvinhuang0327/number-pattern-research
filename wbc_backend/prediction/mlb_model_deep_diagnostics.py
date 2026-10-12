"""
wbc_backend/prediction/mlb_model_deep_diagnostics.py

P8: Deep diagnostic module for MLB model probability quality.

Implements:
  run_model_deep_diagnostics()   — full audit of model vs market
  find_worst_model_segments()    — surface worst-performing segments

Design rules:
  - No external API calls.
  - No modification to input rows.
  - Paper-only; never writes to production.
  - Derives outcomes from (Home Score > Away Score, Status=Final) when
    explicit home_win column is absent.
  - orientation_diagnostics tests inverted and swapped orientations to
    detect systematic probability flip bugs.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from wbc_backend.evaluation.metrics import (
    american_moneyline_pair_to_no_vig,
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)

__all__ = [
    "run_model_deep_diagnostics",
    "find_worst_model_segments",
]


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sf(v: Any) -> float | None:
    """Safe float coerce; strips leading '+'; returns None on failure."""
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
    """1 if home won, 0 if home lost, None if unavailable."""
    # Explicit column
    for col in ("home_win", "Home Win"):
        val = _sf(row.get(col))
        if val is not None:
            return int(round(val))
    # Derive from scores
    status = str(row.get("Status") or row.get("status") or "").strip().lower()
    if status not in ("final", "completed", "complete"):
        return None
    hs = _sf(row.get("Home Score") or row.get("home_score"))
    as_ = _sf(row.get("Away Score") or row.get("away_score"))
    if hs is None or as_ is None:
        return None
    return 1 if hs > as_ else 0


def _market_prob(row: dict) -> float | None:
    """No-vig home win probability from row ML columns."""
    explicit = _sf(row.get("market_prob_home"))
    if explicit is not None and 0.0 <= explicit <= 1.0:
        return explicit
    home_ml = row.get("Home ML") or row.get("home_ml")
    away_ml = row.get("Away ML") or row.get("away_ml")
    if home_ml is None or away_ml is None:
        return None
    try:
        result = american_moneyline_pair_to_no_vig(home_ml, away_ml)
        v = result.get("home_no_vig")
        return v if v is not None and 0.0 <= v <= 1.0 else None
    except Exception:
        return None


def _std(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    try:
        return statistics.stdev(vals)
    except Exception:
        return None


def _year_month(date_str: str) -> str:
    """Return 'YYYY-MM' from any YYYY-MM-DD string."""
    return date_str[:7] if date_str and len(date_str) >= 7 else date_str


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Core segment computation
# ─────────────────────────────────────────────────────────────────────────────

def _segment_metrics(
    model_probs: list[float],
    market_probs: list[float],
    outcomes: list[float],
) -> dict:
    """Compute BSS, ECE, avg_edge for a single segment."""
    n = len(model_probs)
    if n == 0:
        return {
            "row_count": 0,
            "model_brier": None,
            "market_brier": None,
            "bss": None,
            "ece": None,
            "avg_edge": None,
            "avg_model_prob": None,
            "avg_market_prob": None,
            "avg_outcome": None,
        }
    mb = brier_score(model_probs, outcomes)
    mkb = brier_score(market_probs, outcomes)
    bss_val = brier_skill_score(mb, mkb)
    ece_result = expected_calibration_error(model_probs, outcomes)
    ece_val = ece_result.get("ece") if isinstance(ece_result, dict) else ece_result
    edges = [mp - mk for mp, mk in zip(model_probs, market_probs)]
    return {
        "row_count": n,
        "model_brier": round(mb, 6),
        "market_brier": round(mkb, 6),
        "bss": round(bss_val, 6),
        "ece": round(ece_val, 6) if ece_val is not None else None,
        "avg_edge": round(sum(edges) / n, 6),
        "avg_model_prob": round(sum(model_probs) / n, 6),
        "avg_market_prob": round(sum(market_probs) / n, 6),
        "avg_outcome": round(sum(outcomes) / n, 6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Main diagnostic function
# ─────────────────────────────────────────────────────────────────────────────

def run_model_deep_diagnostics(
    rows: list[dict],
    *,
    model_prob_col: str = "model_prob_home",
    market_prob_col: str = "market_prob_home",
    outcome_col: str = "home_win",
    date_col: str = "date",
) -> dict:
    """
    Run full deep diagnostics on MLB model probability rows.

    Parameters
    ----------
    rows:
        List of row dicts — typically from the P5/P6/P7 CSV.
    model_prob_col:
        Column containing model home win probability.
    market_prob_col:
        Column containing pre-computed market no-vig probability.
        If absent, derived from Home ML / Away ML columns.
    outcome_col:
        Column containing explicit binary outcome (0/1).
        If absent, derived from scores + Status.
    date_col:
        Column containing game date (YYYY-MM-DD).

    Returns
    -------
    dict with keys: row_count, usable_count, model_brier, market_brier,
        brier_skill_score, ece, avg_model_prob, avg_market_prob,
        avg_home_win_rate, avg_model_minus_market,
        orientation_diagnostics, join_diagnostics, outcome_diagnostics,
        probability_diagnostics, segment_summary.
    """
    # ── Step 1: collect usable rows ──────────────────────────────────────────
    usable_model: list[float] = []
    usable_market: list[float] = []
    usable_outcomes: list[float] = []
    usable_dates: list[str] = []
    usable_rows: list[dict] = []

    outcome_zero = outcome_one = outcome_null = 0

    for row in rows:
        # Derive outcome
        outcome_raw = _sf(row.get(outcome_col))
        if outcome_raw is not None:
            outcome = int(round(outcome_raw))
        else:
            outcome = _parse_outcome(row)

        if outcome is None:
            outcome_null += 1
        elif outcome == 0:
            outcome_zero += 1
        elif outcome == 1:
            outcome_one += 1

        mp = _sf(row.get(model_prob_col))
        if mp is None or not (0.0 <= mp <= 1.0):
            continue

        mkp = _sf(row.get(market_prob_col))
        if mkp is None:
            mkp = _market_prob(row)
        if mkp is None or not (0.0 <= mkp <= 1.0):
            continue

        if outcome is None:
            continue

        usable_model.append(mp)
        usable_market.append(mkp)
        usable_outcomes.append(float(outcome))
        usable_dates.append(str(row.get(date_col) or row.get("Date") or ""))
        usable_rows.append(row)

    n_usable = len(usable_model)

    # ── Step 2: core metrics ─────────────────────────────────────────────────
    if n_usable == 0:
        model_brier = market_brier = bss = ece_val = None
        avg_model = avg_market = avg_outcome = avg_diff = None
    else:
        model_brier = round(brier_score(usable_model, usable_outcomes), 6)
        market_brier = round(brier_score(usable_market, usable_outcomes), 6)
        bss_val = round(brier_skill_score(model_brier, market_brier), 6)
        ece_r = expected_calibration_error(usable_model, usable_outcomes)
        ece_val = round((ece_r.get("ece") if isinstance(ece_r, dict) else ece_r) or 0.0, 6)
        avg_model = round(sum(usable_model) / n_usable, 6)
        avg_market = round(sum(usable_market) / n_usable, 6)
        avg_outcome = round(sum(usable_outcomes) / n_usable, 6)
        avg_diff = round(avg_model - avg_market, 6)
        bss = bss_val

    # ── Step 3: orientation diagnostics ─────────────────────────────────────
    orientation_diag = _compute_orientation_diagnostics(
        usable_model, usable_market, usable_outcomes, usable_rows
    )

    # ── Step 4: join diagnostics ─────────────────────────────────────────────
    join_diag = _compute_join_diagnostics(rows, date_col)

    # ── Step 5: outcome diagnostics ──────────────────────────────────────────
    total = len(rows)
    outcome_diag = {
        "outcome_zero_count": outcome_zero,
        "outcome_one_count": outcome_one,
        "outcome_null_count": outcome_null,
        "outcome_balance": (
            round(outcome_one / (outcome_zero + outcome_one), 4)
            if (outcome_zero + outcome_one) > 0 else None
        ),
    }

    # ── Step 6: probability diagnostics ─────────────────────────────────────
    prob_diag = _compute_probability_diagnostics(usable_model, usable_market)

    # ── Step 7: segment summary ──────────────────────────────────────────────
    seg_summary = _compute_segment_summary(
        usable_model, usable_market, usable_outcomes, usable_dates, usable_rows
    )

    return {
        "row_count": total,
        "usable_count": n_usable,
        "model_brier": model_brier,
        "market_brier": market_brier,
        "brier_skill_score": bss,
        "ece": ece_val,
        "avg_model_prob": avg_model,
        "avg_market_prob": avg_market,
        "avg_home_win_rate": avg_outcome,
        "avg_model_minus_market": avg_diff,
        "orientation_diagnostics": orientation_diag,
        "join_diagnostics": join_diag,
        "outcome_diagnostics": outcome_diag,
        "probability_diagnostics": prob_diag,
        "segment_summary": seg_summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Orientation diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def _compute_orientation_diagnostics(
    model_probs: list[float],
    market_probs: list[float],
    outcomes: list[float],
    rows: list[dict],
) -> dict:
    """
    Test three orientations:
      normal          — model_prob_home as-is
      inverted_model  — 1 - model_prob_home
      swapped_home_away — use model_prob_away (or 1-model_prob_home)
    """
    n = len(model_probs)
    if n == 0:
        return {
            "bss_normal": None,
            "bss_inverted_model": None,
            "bss_swapped_home_away": None,
            "best_orientation": "unknown",
            "orientation_warning": "no usable rows",
        }

    mb = brier_score(model_probs, outcomes)
    mkb = brier_score(market_probs, outcomes)
    bss_normal = round(brier_skill_score(mb, mkb), 6)

    # Inverted: 1 - model_prob_home
    inv_probs = [1.0 - p for p in model_probs]
    mb_inv = brier_score(inv_probs, outcomes)
    bss_inverted = round(brier_skill_score(mb_inv, mkb), 6)

    # Swapped: use model_prob_away column if available, else 1 - model_prob_home
    swapped_probs = []
    for i, row in enumerate(rows):
        away_col = _sf(row.get("model_prob_away"))
        if away_col is not None and 0.0 <= away_col <= 1.0:
            # model_prob_away gives P(away wins) — we want P(home wins) = 1-away
            swapped_probs.append(1.0 - away_col)
        else:
            # Fall back to inverted
            swapped_probs.append(1.0 - model_probs[i])

    mb_swapped = brier_score(swapped_probs, outcomes)
    bss_swapped = round(brier_skill_score(mb_swapped, mkb), 6)

    # Pick best
    candidates = {
        "normal": bss_normal,
        "inverted_model": bss_inverted,
        "swapped_home_away": bss_swapped,
    }
    best = max(candidates, key=lambda k: candidates[k])

    # Build warning
    warning = None
    if bss_inverted > bss_normal + 0.005:
        warning = (
            f"INVERTED model outperforms normal orientation by "
            f"{bss_inverted - bss_normal:.4f} BSS points. "
            "Possible probability flip bug."
        )
    elif bss_swapped > bss_normal + 0.005:
        warning = (
            f"SWAPPED (away→home) model outperforms normal by "
            f"{bss_swapped - bss_normal:.4f} BSS points. "
            "Possible home/away column assignment error."
        )
    elif bss_normal >= bss_inverted and bss_normal >= bss_swapped:
        warning = None  # normal is best — no orientation bug
    else:
        warning = f"Best orientation is '{best}' (BSS={candidates[best]:.4f}); normal orientation may be suboptimal."

    return {
        "bss_normal": bss_normal,
        "bss_inverted_model": bss_inverted,
        "bss_swapped_home_away": bss_swapped,
        "best_orientation": best,
        "orientation_warning": warning,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Join diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def _compute_join_diagnostics(rows: list[dict], date_col: str) -> dict:
    """Detect missing/duplicate game keys without requiring a full join audit."""
    game_ids: list[str] = []
    date_team_keys: list[str] = []
    missing_game_id = 0
    missing_home = 0
    missing_away = 0
    same_team_count = 0

    for row in rows:
        gid = row.get("game_id") or row.get("Game ID") or ""
        if not gid:
            missing_game_id += 1
        else:
            game_ids.append(str(gid))

        date_val = str(row.get(date_col) or row.get("Date") or "").strip()
        home = str(row.get("Home") or row.get("home_team") or "").strip()
        away = str(row.get("Away") or row.get("away_team") or "").strip()

        if not home:
            missing_home += 1
        if not away:
            missing_away += 1
        if home and away and home.lower() == away.lower():
            same_team_count += 1
        if date_val and home and away:
            date_team_keys.append(f"{date_val}|{home}|{away}")

    duplicate_game_id = len(game_ids) - len(set(game_ids))
    duplicate_date_team = len(date_team_keys) - len(set(date_team_keys))

    return {
        "missing_game_id_count": missing_game_id,
        "duplicate_game_id_count": duplicate_game_id,
        "duplicate_date_team_count": duplicate_date_team,
        "missing_home_team_count": missing_home,
        "missing_away_team_count": missing_away,
        "suspicious_same_team_count": same_team_count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 6  Probability diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def _compute_probability_diagnostics(
    model_probs: list[float],
    market_probs: list[float],
) -> dict:
    n = len(model_probs)
    if n == 0:
        return {
            "model_prob_min": None,
            "model_prob_max": None,
            "model_prob_std": None,
            "market_prob_min": None,
            "market_prob_max": None,
            "market_prob_std": None,
            "overconfident_count": 0,
            "underconfident_count": 0,
        }
    # Overconfident: model > market + 0.05
    over = sum(1 for m, mk in zip(model_probs, market_probs) if m > mk + 0.05)
    under = sum(1 for m, mk in zip(model_probs, market_probs) if m < mk - 0.05)
    return {
        "model_prob_min": round(min(model_probs), 6),
        "model_prob_max": round(max(model_probs), 6),
        "model_prob_std": round(_std(model_probs) or 0.0, 6),
        "market_prob_min": round(min(market_probs), 6),
        "market_prob_max": round(max(market_probs), 6),
        "market_prob_std": round(_std(market_probs) or 0.0, 6),
        "overconfident_count": over,
        "underconfident_count": under,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 7  Segment summary
# ─────────────────────────────────────────────────────────────────────────────

def _compute_segment_summary(
    model_probs: list[float],
    market_probs: list[float],
    outcomes: list[float],
    dates: list[str],
    rows: list[dict],
) -> dict:
    """Break down performance by month, confidence bucket, favorite side, home bias bucket."""

    # ── by_month ──────────────────────────────────────────────────────────────
    month_buckets: dict[str, tuple[list, list, list]] = defaultdict(lambda: ([], [], []))
    for mp, mkp, out, d in zip(model_probs, market_probs, outcomes, dates):
        ym = _year_month(d) if d else "__unknown__"
        month_buckets[ym][0].append(mp)
        month_buckets[ym][1].append(mkp)
        month_buckets[ym][2].append(out)

    by_month = []
    for ym in sorted(month_buckets):
        m, mk, o = month_buckets[ym]
        seg = _segment_metrics(m, mk, o)
        by_month.append({"segment": ym, "segment_by": "month", **seg})

    # ── by_confidence_bucket ─────────────────────────────────────────────────
    def _conf_bucket(p: float) -> str:
        if p >= 0.70:
            return "very_hi_conf_>=0.70"
        elif p >= 0.65:
            return "hi_conf_>=0.65"
        elif p >= 0.60:
            return "med_hi_conf_0.60-0.65"
        elif p >= 0.55:
            return "med_conf_0.55-0.60"
        else:
            return "low_conf_<0.55"

    conf_buckets: dict[str, tuple[list, list, list]] = defaultdict(lambda: ([], [], []))
    for mp, mkp, out in zip(model_probs, market_probs, outcomes):
        cb = _conf_bucket(mp)
        conf_buckets[cb][0].append(mp)
        conf_buckets[cb][1].append(mkp)
        conf_buckets[cb][2].append(out)

    bucket_order = [
        "low_conf_<0.55",
        "med_conf_0.55-0.60",
        "med_hi_conf_0.60-0.65",
        "hi_conf_>=0.65",
        "very_hi_conf_>=0.70",
    ]
    by_confidence_bucket = []
    for bk in bucket_order:
        if bk in conf_buckets:
            m, mk, o = conf_buckets[bk]
            seg = _segment_metrics(m, mk, o)
            by_confidence_bucket.append({"segment": bk, "segment_by": "confidence_bucket", **seg})

    # ── by_favorite_side ─────────────────────────────────────────────────────
    fav_buckets: dict[str, tuple[list, list, list]] = defaultdict(lambda: ([], [], []))
    for mp, mkp, out in zip(model_probs, market_probs, outcomes):
        if mkp >= 0.50:
            side = "home_fav"
        else:
            side = "away_fav"
        fav_buckets[side][0].append(mp)
        fav_buckets[side][1].append(mkp)
        fav_buckets[side][2].append(out)

    by_favorite_side = []
    for side in ("home_fav", "away_fav"):
        if side in fav_buckets:
            m, mk, o = fav_buckets[side]
            seg = _segment_metrics(m, mk, o)
            by_favorite_side.append({"segment": side, "segment_by": "favorite_side", **seg})

    # ── by_home_bias_bucket ───────────────────────────────────────────────────
    # home_bias_per_row = model_prob - market_prob
    def _bias_bucket(diff: float) -> str:
        if diff >= 0.15:
            return "extreme_home_bias_>=0.15"
        elif diff >= 0.08:
            return "strong_home_bias_0.08-0.15"
        elif diff >= 0.02:
            return "mild_home_bias_0.02-0.08"
        elif diff >= -0.02:
            return "neutral_-0.02-0.02"
        elif diff >= -0.08:
            return "mild_away_bias_-0.08--0.02"
        else:
            return "strong_away_bias_<-0.08"

    bias_buckets: dict[str, tuple[list, list, list]] = defaultdict(lambda: ([], [], []))
    for mp, mkp, out in zip(model_probs, market_probs, outcomes):
        bb = _bias_bucket(mp - mkp)
        bias_buckets[bb][0].append(mp)
        bias_buckets[bb][1].append(mkp)
        bias_buckets[bb][2].append(out)

    bias_order = [
        "strong_away_bias_<-0.08",
        "mild_away_bias_-0.08--0.02",
        "neutral_-0.02-0.02",
        "mild_home_bias_0.02-0.08",
        "strong_home_bias_0.08-0.15",
        "extreme_home_bias_>=0.15",
    ]
    by_home_bias_bucket = []
    for bb in bias_order:
        if bb in bias_buckets:
            m, mk, o = bias_buckets[bb]
            seg = _segment_metrics(m, mk, o)
            by_home_bias_bucket.append({
                "segment": bb,
                "segment_by": "home_bias_bucket",
                **seg,
            })

    return {
        "by_month": by_month,
        "by_confidence_bucket": by_confidence_bucket,
        "by_favorite_side": by_favorite_side,
        "by_home_bias_bucket": by_home_bias_bucket,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 8  find_worst_model_segments
# ─────────────────────────────────────────────────────────────────────────────

def find_worst_model_segments(
    diagnostics: dict,
    *,
    top_n: int = 10,
) -> list[dict]:
    """
    Surface the worst-performing segments from deep diagnostics output.

    Ranked by composite score = -bss (higher is worse) + ece + |avg_edge|*0.5.
    Segments with None bss are excluded unless row_count > 0.

    Returns list of dicts with keys: segment, segment_by, row_count,
    bss, ece, avg_edge, rank_score, rank_reason.
    """
    seg_summary = diagnostics.get("segment_summary", {})
    candidates: list[dict] = []

    for group_key, segs in seg_summary.items():
        if not isinstance(segs, list):
            continue
        for seg in segs:
            bss = seg.get("bss")
            ece = seg.get("ece")
            row_count = seg.get("row_count", 0)
            avg_edge = seg.get("avg_edge")
            if row_count == 0:
                continue
            if bss is None:
                continue
            rank_score = (
                -bss
                + (ece or 0.0)
                + abs(avg_edge or 0.0) * 0.5
            )
            reason_parts = []
            if bss < 0:
                reason_parts.append(f"negative_bss={bss:.4f}")
            if ece is not None and ece > 0.05:
                reason_parts.append(f"high_ece={ece:.4f}")
            if avg_edge is not None and avg_edge > 0.05:
                reason_parts.append(f"high_home_bias_edge={avg_edge:.4f}")
            candidates.append({
                "segment": seg.get("segment"),
                "segment_by": seg.get("segment_by"),
                "row_count": row_count,
                "bss": bss,
                "ece": ece,
                "avg_edge": avg_edge,
                "avg_model_prob": seg.get("avg_model_prob"),
                "avg_market_prob": seg.get("avg_market_prob"),
                "avg_outcome": seg.get("avg_outcome"),
                "rank_score": round(rank_score, 6),
                "rank_reason": "; ".join(reason_parts) if reason_parts else "low_bss",
            })

    candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    return candidates[:top_n]
