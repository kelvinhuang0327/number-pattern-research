"""
wbc_backend/prediction/mlb_ml_feature_matrix.py

P13: Build leakage-safe MLB ML feature matrices and walk-forward folds.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if s in {"", "None", "nan", "NaN"}:
        return None
    try:
        f = float(s)
    except (ValueError, TypeError):
        return None
    return f


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _month_key(d: date) -> tuple[int, int]:
    return d.year, d.month


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, (idx % 12) + 1


def _build_feature_policy(
    feature_policy: str,
    include_bullpen: bool,
    include_market_feature: bool,
) -> tuple[list[str], list[str], list[str]]:
    # policy-specific include list, always leakage-safe pregame fields only
    if feature_policy == "p13_recent_only":
        include_cols = ["indep_recent_win_rate_delta"]
    elif feature_policy == "p13_starter_only":
        include_cols = ["indep_starter_era_delta"]
    elif feature_policy == "p13_with_bullpen":
        include_cols = [
            "indep_recent_win_rate_delta",
            "indep_starter_era_delta",
            "indep_bullpen_proxy_delta",
        ]
    else:  # default p13_v1
        include_cols = [
            "indep_recent_win_rate_delta",
            "indep_starter_era_delta",
        ]
        if include_bullpen:
            include_cols.append("indep_bullpen_proxy_delta")

    if include_market_feature:
        include_cols.append("raw_model_prob_before_p10")

    excluded_default = [
        "indep_rest_days_delta",
        "indep_home_rest_days",
        "indep_away_rest_days",
        "indep_wind_kmh",
        "indep_temp_c",
        "indep_park_roof_type",
    ]
    if not include_bullpen and "indep_bullpen_proxy_delta" not in include_cols:
        excluded_default.append("indep_bullpen_proxy_delta")

    return include_cols, excluded_default, ["home_win", "Home Score", "Away Score"]


def build_ml_feature_matrix(
    rows: list[dict],
    *,
    target_col: str = "home_win",
    date_col: str = "Date",
    feature_policy: str = "p13_v1",
    allow_market_prob_feature: bool = False,
) -> tuple[list[dict], dict]:
    """
    Build leakage-safe ML training rows for P13 walk-forward model candidate.
    """
    include_bullpen = feature_policy == "p13_with_bullpen"
    feature_cols, excluded_cols, leakage_cols = _build_feature_policy(
        feature_policy=feature_policy,
        include_bullpen=include_bullpen,
        include_market_feature=allow_market_prob_feature,
    )

    matrix_rows: list[dict] = []
    missing_by_feature: dict[str, int] = {c: 0 for c in feature_cols}
    dropped_count = 0

    for row in rows:
        # Hard leakage-safe precondition propagated from upstream builders
        leakage_safe = str(row.get("leakage_safe", "")).lower() == "true"
        if not leakage_safe:
            dropped_count += 1
            continue

        d = _parse_date(row.get(date_col) or row.get("Date") or row.get("date"))
        if d is None:
            dropped_count += 1
            continue

        y = _safe_float(row.get(target_col))
        if y is None:
            # fallback for historical CSVs that use scores
            hs = _safe_float(row.get("Home Score") or row.get("home_score"))
            a_s = _safe_float(row.get("Away Score") or row.get("away_score"))
            if hs is None or a_s is None:
                dropped_count += 1
                continue
            y = 1.0 if hs > a_s else 0.0
        y = 1.0 if y >= 0.5 else 0.0

        out: dict[str, Any] = {
            "game_id": row.get("game_id") or "",
            "date": d.isoformat(),
            "home_team": row.get("Home") or row.get("home_team") or "",
            "away_team": row.get("Away") or row.get("away_team") or "",
            "y_home_win": y,
            # keep market/prob fields for downstream simulation merge
            "Home ML": row.get("Home ML"),
            "Away ML": row.get("Away ML"),
            "Date": row.get("Date") or d.isoformat(),
            "Home": row.get("Home") or row.get("home_team"),
            "Away": row.get("Away") or row.get("away_team"),
            "Status": row.get("Status") or "Final",
            "Home Score": row.get("Home Score") or row.get("home_score"),
            "Away Score": row.get("Away Score") or row.get("away_score"),
            "raw_model_prob_home": row.get("raw_model_prob_home"),
            "raw_model_prob_before_p10": row.get("raw_model_prob_before_p10"),
        }

        any_missing = False
        for col in feature_cols:
            v = _safe_float(row.get(col))
            if v is None:
                missing_by_feature[col] += 1
                any_missing = True
                break
            out[col] = v
        if any_missing:
            dropped_count += 1
            continue

        out["leakage_safe"] = True
        out["ml_feature_policy"] = feature_policy
        matrix_rows.append(out)

    matrix_rows.sort(key=lambda r: r["date"])
    meta = {
        "input_count": len(rows),
        "output_count": len(matrix_rows),
        "dropped_count": dropped_count,
        "features_used": feature_cols,
        "features_excluded": excluded_cols,
        "leakage_forbidden_columns": leakage_cols,
        "missing_by_feature": missing_by_feature,
        "leakage_safe": True,
        "feature_policy": feature_policy,
    }
    return matrix_rows, meta


def split_walk_forward_folds(
    matrix_rows: list[dict],
    *,
    date_col: str = "date",
    min_train_size: int = 300,
    validation_months: int = 1,
    initial_train_months: int = 2,
) -> list[dict]:
    """
    Build walk-forward folds with strict train_end < validation_start.
    """
    if not matrix_rows:
        return []

    dates = [_parse_date(r.get(date_col)) for r in matrix_rows]
    dates = [d for d in dates if d is not None]
    if not dates:
        return []

    unique_months = sorted({_month_key(d) for d in dates})
    if len(unique_months) <= initial_train_months:
        return []

    folds: list[dict] = []
    for i in range(initial_train_months, len(unique_months)):
        val_start_m = unique_months[i]
        val_end_m = _add_months(val_start_m[0], val_start_m[1], validation_months - 1)

        train_months = unique_months[:i]
        train_indices: list[int] = []
        val_indices: list[int] = []

        for idx, row in enumerate(matrix_rows):
            d = _parse_date(row.get(date_col))
            if d is None:
                continue
            mk = _month_key(d)
            if mk in train_months:
                train_indices.append(idx)
            if val_start_m <= mk <= val_end_m:
                val_indices.append(idx)

        if len(train_indices) < min_train_size or not val_indices:
            continue

        train_start = _parse_date(matrix_rows[train_indices[0]][date_col]).isoformat()
        train_end = _parse_date(matrix_rows[train_indices[-1]][date_col]).isoformat()
        val_start = _parse_date(matrix_rows[val_indices[0]][date_col]).isoformat()
        val_end = _parse_date(matrix_rows[val_indices[-1]][date_col]).isoformat()

        # strict leakage guard
        if train_end >= val_start:
            continue

        folds.append(
            {
                "fold_id": f"wf_{len(folds)+1:03d}",
                "train_start": train_start,
                "train_end": train_end,
                "validation_start": val_start,
                "validation_end": val_end,
                "train_indices": train_indices,
                "validation_indices": val_indices,
                "train_size": len(train_indices),
                "validation_size": len(val_indices),
                "leakage_safe": True,
            }
        )
    return folds

