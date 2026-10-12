"""
wbc_backend/prediction/mlb_oof_calibration.py

P7: Walk-forward Out-of-Fold (OOF) calibration validation for MLB model probabilities.

Design:
  - Sort rows chronologically by date.
  - Build a rolling calibration map:  for each validation month, fit only on all
    prior rows that have both model_prob_home and a known outcome.
  - Do NOT use validation-period outcomes to fit its own calibration map.
  - Output rows are labelled calibration_mode = "walk_forward_oof" and
    leakage_safe = true.
  - Rows before sufficient training data (< min_train_size) are skipped (not
    included in the OOF output) but are counted in skipped_row_count.

Safety guarantees:
  - Chronological sort is enforced by this module.
  - train_end is always strictly before validation_start.
  - Each calibration map is built exclusively from rows chronologically prior to
    the validation window.
  - Validation outcomes are never exposed to the calibration fitting loop.

Rules:
  - paper_only always.
  - No external API calls.
  - No live data access.
  - All calibrated probabilities are in [0, 1].
"""
from __future__ import annotations

import copy
import math
from datetime import date as DateType
from typing import Any

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)

__all__ = [
    "build_walk_forward_calibrated_rows",
    "evaluate_oof_calibration",
]

_OOF_WARNING = (
    "walk-forward OOF calibration candidate; production still requires human approval"
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


def _parse_row_date(row: dict, date_col: str) -> str | None:
    """Return ISO date string (YYYY-MM-DD) or None."""
    raw = row.get(date_col) or row.get("Date") or row.get("date")
    if not raw:
        return None
    s = str(raw).strip()
    # Accept YYYY-MM-DD or YYYY/MM/DD
    s = s.replace("/", "-")
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def _year_month(date_str: str | None) -> str | None:
    """Return YYYY-MM from a YYYY-MM-DD string, or None."""
    if date_str and len(date_str) >= 7:
        return date_str[:7]
    return None


def _add_months(ym: str, n: int) -> str:
    """Add n months to a YYYY-MM string. Returns YYYY-MM."""
    year, month = int(ym[:4]), int(ym[5:7])
    month += n
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Bin-calibration map builder (from a training set)
# ─────────────────────────────────────────────────────────────────────────────

def _build_bin_map(
    training_pairs: list[tuple[float, float]],
    n_bins: int,
    min_bin_size: int,
) -> tuple[list[float], float, list[dict]]:
    """
    Build bin-calibration map from (raw_prob, outcome) training pairs.

    Returns
    -------
    bin_cal : list[float]
        Calibrated probability for each bin index (length n_bins).
    global_win_rate : float
    bin_stats : list[dict]
    """
    bin_width = 1.0 / n_bins
    bin_outcomes: list[list[float]] = [[] for _ in range(n_bins)]
    for raw_p, outcome in training_pairs:
        idx = min(int(raw_p / bin_width), n_bins - 1)
        bin_outcomes[idx].append(outcome)

    global_win_rate = (
        sum(o for _, o in training_pairs) / len(training_pairs)
        if training_pairs
        else 0.5
    )

    bin_cal: list[float] = []
    bin_stats: list[dict] = []
    for i, bin_outs in enumerate(bin_outcomes):
        n = len(bin_outs)
        if n >= min_bin_size:
            cal_p = sum(bin_outs) / n
            fallback = "none"
        elif n > 0:
            weight = n / min_bin_size
            raw_cal = sum(bin_outs) / n
            cal_p = weight * raw_cal + (1 - weight) * global_win_rate
            fallback = f"sparse_blend(n={n},global={global_win_rate:.4f})"
        else:
            cal_p = global_win_rate
            fallback = f"empty_bin_global({global_win_rate:.4f})"

        cal_p = _clamp(cal_p)
        bin_cal.append(cal_p)
        bin_stats.append({
            "bin_index": i,
            "bin_lo": round(i * bin_width, 4),
            "bin_hi": round((i + 1) * bin_width, 4),
            "bin_size": n,
            "calibrated_prob": round(cal_p, 6),
            "fallback": fallback,
        })

    return bin_cal, global_win_rate, bin_stats


def _apply_bin_map(raw_p: float, bin_cal: list[float]) -> float:
    n_bins = len(bin_cal)
    bin_width = 1.0 / n_bins
    idx = min(int(raw_p / bin_width), n_bins - 1)
    return bin_cal[idx]


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Walk-forward OOF calibration
# ─────────────────────────────────────────────────────────────────────────────

def build_walk_forward_calibrated_rows(
    rows: list[dict],
    *,
    date_col: str = "date",
    model_prob_col: str = "model_prob_home",
    outcome_col: str = "home_win",
    n_bins: int = 10,
    min_train_size: int = 300,
    min_bin_size: int = 30,
    initial_train_months: int = 2,
) -> tuple[list[dict], dict]:
    """
    Build walk-forward OOF calibrated rows.

    Walk-forward protocol:
    1. Sort all rows chronologically by date_col.
    2. Collect the full set of enriched rows (have model_prob_home + outcome).
    3. Determine the first "training cutoff" month: the earliest month after
       which at least min_train_size enriched rows have been seen.
    4. For each subsequent month (validation window), fit a calibration map on
       all enriched rows strictly before the validation month.
    5. Apply the calibration map to all rows (enriched or not) in the validation
       month. Rows from the warm-up period (before min_train_size) are SKIPPED.

    Leakage safety:
    - Calibration maps are fit on PAST data only (train_end < validation_start).
    - Validation-month outcomes are not used in the calibration fit.
    - leakage_safe = True is set in all output row traces.

    Parameters
    ----------
    rows : list[dict]
        Full game records including model_prob_home (may be empty for some rows).
    date_col : str
        Column name for game date. Falls back to "Date" or "date".
    model_prob_col : str
        Column for model probability.
    outcome_col : str
        Column for binary outcome if explicit; otherwise derived from scores.
    n_bins : int
        Number of equal-width probability bins.
    min_train_size : int
        Minimum number of enriched training rows needed before calibration begins.
    min_bin_size : int
        Minimum samples per bin for direct calibration (else blend with global).
    initial_train_months : int
        Minimum number of calendar months in training before validation begins
        (enforced alongside min_train_size).

    Returns
    -------
    oof_rows : list[dict]
        Calibrated rows for the validation windows only.
    meta : dict
        Fold metadata summary.
    """
    # Step 1: parse date + model_prob for every row
    parsed: list[tuple[str | None, float | None, int | None, dict]] = []
    for row in rows:
        d = _parse_row_date(row, date_col)
        raw_p = _safe_float(row.get(model_prob_col))
        outcome: int | None = (
            int(_safe_float(row.get(outcome_col)))
            if _safe_float(row.get(outcome_col)) is not None
            else _parse_outcome(row)
        )
        parsed.append((d, raw_p, outcome, row))

    # Step 2: sort chronologically; rows with no date go to end (will be skipped)
    parsed.sort(key=lambda x: (x[0] or "9999-99-99"))

    # Step 3: identify all months present
    all_months: list[str] = sorted({
        _year_month(d) for d, _, _, _ in parsed
        if _year_month(d) is not None
    })

    if not all_months:
        return [], {"error": "no_parseable_dates", "oof_row_count": 0, "skipped_row_count": len(rows)}

    # Step 4: determine warm-up cutoff
    # Walk through months accumulating enriched training rows until we have
    # min_train_size AND at least initial_train_months calendar months.
    enriched_up_to: dict[str, list[tuple[float, float]]] = {}  # month -> cumulative training pairs
    cumulative_pairs: list[tuple[float, float]] = []

    for month in all_months:
        # Add enriched rows from this month to cumulative
        for d, raw_p, outcome, row in parsed:
            if _year_month(d) == month and raw_p is not None and outcome is not None and 0.0 <= raw_p <= 1.0:
                cumulative_pairs.append((raw_p, float(outcome)))
        enriched_up_to[month] = list(cumulative_pairs)

    # Find first validation month: must have >= min_train_size pairs in prior months
    # AND >= initial_train_months calendar months of data
    first_val_month: str | None = None
    for i, month in enumerate(all_months):
        # Pairs available BEFORE this month = enriched_up_to[all_months[i-1]] if i > 0
        prior_pairs = enriched_up_to[all_months[i - 1]] if i > 0 else []
        # Calendar months already passed
        n_prior_months = i  # months before index i
        if (
            len(prior_pairs) >= min_train_size
            and n_prior_months >= initial_train_months
        ):
            first_val_month = month
            break

    if first_val_month is None:
        # Not enough training data to calibrate any month
        return [], {
            "error": "insufficient_training_data",
            "total_enriched": len(cumulative_pairs),
            "min_train_size": min_train_size,
            "oof_row_count": 0,
            "skipped_row_count": len(rows),
        }

    # Step 5: build OOF rows for each validation month >= first_val_month
    oof_rows: list[dict] = []
    folds: list[dict] = []
    skipped_row_count = 0

    # Count rows in warm-up period
    for d, raw_p, _, row in parsed:
        ym = _year_month(d)
        if ym is None or ym < first_val_month:
            skipped_row_count += 1

    val_months = [m for m in all_months if m >= first_val_month]

    for val_month in val_months:
        # Training = all enriched rows from months strictly before val_month
        val_month_idx = all_months.index(val_month)
        prior_month = all_months[val_month_idx - 1] if val_month_idx > 0 else None
        train_pairs = enriched_up_to[prior_month] if prior_month else []

        if len(train_pairs) < min_train_size:
            # Still not enough — skip this month
            for d, raw_p, _, row in parsed:
                if _year_month(d) == val_month:
                    skipped_row_count += 1
            continue

        # Build calibration map from training data
        bin_cal, global_win_rate, bin_stats = _build_bin_map(train_pairs, n_bins, min_bin_size)

        # Determine train date range
        train_dates = [d for d, _, _, _ in parsed if _year_month(d) is not None and _year_month(d) < val_month and d is not None]
        train_start_date = train_dates[0] if train_dates else "N/A"
        train_end_date = train_dates[-1] if train_dates else "N/A"

        # Collect validation rows for this month
        val_rows_this_month = [
            (d, raw_p, outcome, row)
            for d, raw_p, outcome, row in parsed
            if _year_month(d) == val_month
        ]
        val_dates = [d for d, _, _, _ in val_rows_this_month if d]

        fold_meta: dict = {
            "validation_month": val_month,
            "train_start": train_start_date,
            "train_end": train_end_date,
            "validation_start": val_dates[0] if val_dates else val_month + "-01",
            "validation_end": val_dates[-1] if val_dates else val_month + "-28",
            "train_size": len(train_pairs),
            "validation_total_rows": len(val_rows_this_month),
            "validation_enriched_rows": sum(
                1 for _, rp, _, _ in val_rows_this_month if rp is not None
            ),
            "n_bins": n_bins,
            "min_bin_size": min_bin_size,
            "global_win_rate": round(global_win_rate, 6),
            "leakage_safe": True,
        }
        folds.append(fold_meta)

        calibration_trace = {
            "calibration_mode": "walk_forward_oof",
            "train_start": fold_meta["train_start"],
            "train_end": fold_meta["train_end"],
            "validation_start": fold_meta["validation_start"],
            "validation_end": fold_meta["validation_end"],
            "train_size": len(train_pairs),
            "validation_size": len(val_rows_this_month),
            "n_bins": n_bins,
            "min_bin_size": min_bin_size,
            "global_win_rate": round(global_win_rate, 6),
            "leakage_safe": True,
            "bin_stats": bin_stats,
        }

        for d, raw_p, outcome, row in val_rows_this_month:
            new_row = copy.copy(row)
            new_row["raw_model_prob_home"] = raw_p

            if raw_p is not None and 0.0 <= raw_p <= 1.0:
                cal_p = _apply_bin_map(raw_p, bin_cal)
                new_row["model_prob_home"] = str(round(cal_p, 6))
                new_row["model_prob_away"] = str(round(1.0 - cal_p, 6))
            else:
                # No model prob — pass through as-is, no calibration
                new_row["model_prob_home"] = row.get("model_prob_home", "")
                new_row["model_prob_away"] = row.get("model_prob_away", "")

            new_row["probability_source"] = "calibrated_model"
            new_row["calibration_source_trace"] = calibration_trace

            oof_rows.append(new_row)

    meta = {
        "oof_row_count": len(oof_rows),
        "skipped_row_count": skipped_row_count,
        "first_val_month": first_val_month,
        "total_folds": len(folds),
        "folds": folds,
        "n_bins": n_bins,
        "min_bin_size": min_bin_size,
        "min_train_size": min_train_size,
        "initial_train_months": initial_train_months,
    }
    return oof_rows, meta


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _collect_usable(rows: list[dict], prob_col: str = "model_prob_home") -> list[tuple[float, float, float]]:
    """Return list of (model_prob, market_prob, outcome) for rows with all three."""
    from wbc_backend.evaluation.metrics import american_moneyline_pair_to_no_vig

    result: list[tuple[float, float, float]] = []
    for row in rows:
        p = _safe_float(row.get(prob_col))
        if p is None or not (0.0 <= p <= 1.0):
            continue

        # Derive market prob
        home_ml = _safe_float(row.get("Home ML") or row.get("home_ml"))
        away_ml = _safe_float(row.get("Away ML") or row.get("away_ml"))
        if home_ml is not None and away_ml is not None:
            try:
                no_vig = american_moneyline_pair_to_no_vig(home_ml, away_ml)
                if isinstance(no_vig, dict):
                    market_prob = no_vig.get("home_no_vig")
                else:
                    market_prob = no_vig[0] if no_vig else None
            except Exception:
                market_prob = None
        else:
            market_prob = None

        if market_prob is None:
            continue

        # Derive outcome
        outcome_raw = _safe_float(row.get("home_win"))
        if outcome_raw is not None:
            outcome = float(outcome_raw)
        else:
            o = _parse_outcome(row)
            if o is None:
                continue
            outcome = float(o)

        result.append((p, market_prob, outcome))
    return result


def evaluate_oof_calibration(
    original_rows: list[dict],
    oof_rows: list[dict],
) -> dict:
    """
    Compare original model BSS/ECE vs OOF-calibrated BSS/ECE.

    Parameters
    ----------
    original_rows : list[dict]
        Raw rows from the P5 enriched CSV (with model_prob_home = raw model prob).
    oof_rows : list[dict]
        Rows produced by build_walk_forward_calibrated_rows.

    Returns
    -------
    dict with:
        original_bss, oof_bss, original_ece, oof_ece,
        delta_bss, delta_ece,
        oof_row_count, skipped_row_count,
        recommendation, deployability_status, gate_reasons
    """
    orig_usable = _collect_usable(original_rows)
    oof_usable = _collect_usable(oof_rows)

    def _compute(usable: list[tuple[float, float, float]]) -> tuple[float | None, float | None]:
        if not usable:
            return None, None
        model_probs = [u[0] for u in usable]
        market_probs = [u[1] for u in usable]
        outcomes = [u[2] for u in usable]
        m_brier = brier_score(model_probs, outcomes)
        mkt_brier = brier_score(market_probs, outcomes)
        bss = brier_skill_score(m_brier, mkt_brier)
        ece_result = expected_calibration_error(model_probs, outcomes)
        # expected_calibration_error may return a dict or a float
        if isinstance(ece_result, dict):
            ece = ece_result.get("ece")
        else:
            ece = ece_result
        return bss, ece

    original_bss, original_ece = _compute(orig_usable)
    oof_bss, oof_ece = _compute(oof_usable)

    delta_bss = (
        (oof_bss - original_bss)
        if oof_bss is not None and original_bss is not None
        else None
    )
    delta_ece = (
        (oof_ece - original_ece)
        if oof_ece is not None and original_ece is not None
        else None
    )

    gate_reasons: list[str] = []

    # Determine recommendation
    recommendation: str
    deployability_status: str

    if oof_bss is None:
        recommendation = "OOF_REJECTED"
        deployability_status = "REJECTED"
        gate_reasons.append("OOF evaluation failed: no usable rows in OOF output.")
    elif oof_bss > 0.0 and oof_ece is not None and oof_ece <= 0.12:
        recommendation = "OOF_PASS_CANDIDATE"
        deployability_status = "PRODUCTION_CANDIDATE"
        gate_reasons.append(
            "OOF BSS > 0 and ECE <= 0.12: qualifies as production candidate. "
            "Production enablement still requires human approval and P38 governance clearance."
        )
    elif oof_bss > 0.0:
        recommendation = "OOF_PASS_CANDIDATE"
        deployability_status = "PAPER_ONLY_CANDIDATE"
        gate_reasons.append(
            f"OOF BSS > 0 but ECE={oof_ece:.4f} exceeds threshold 0.12. "
            "Paper-only candidate only."
        )
    elif oof_bss is not None and oof_bss > original_bss:  # type: ignore[operator]
        recommendation = "OOF_IMPROVED_BUT_STILL_BLOCKED"
        deployability_status = "PAPER_ONLY_CANDIDATE"
        gate_reasons.append(
            f"OOF BSS={oof_bss:.4f} improved over original BSS={original_bss:.4f} "
            "but remains <= 0. Gate stays blocked."
        )
    else:
        recommendation = "OOF_REJECTED"
        deployability_status = "REJECTED"
        gate_reasons.append(
            f"OOF BSS={oof_bss:.4f} did not improve over original BSS={original_bss:.4f}. "
            "Calibration does not generalize out-of-fold."
        )

    gate_reasons.append(_OOF_WARNING)

    return {
        "original_bss": round(original_bss, 6) if original_bss is not None else None,
        "oof_bss": round(oof_bss, 6) if oof_bss is not None else None,
        "original_ece": round(original_ece, 6) if original_ece is not None else None,
        "oof_ece": round(oof_ece, 6) if oof_ece is not None else None,
        "delta_bss": round(delta_bss, 6) if delta_bss is not None else None,
        "delta_ece": round(delta_ece, 6) if delta_ece is not None else None,
        "oof_row_count": len(oof_usable),
        "skipped_row_count": len(orig_usable) - len(oof_usable),
        "recommendation": recommendation,
        "deployability_status": deployability_status,
        "gate_reasons": gate_reasons,
    }
