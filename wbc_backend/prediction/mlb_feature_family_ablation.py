"""
wbc_backend/prediction/mlb_feature_family_ablation.py

P12: Feature-family ablation utility for MLB moneyline model.

Design:
  - Classifies CSV columns into feature families.
  - Builds ablation variant rows by enabling/disabling feature families.
  - Recomputes candidate probability using only enabled family components.
  - All outputs are PAPER-only; no production writes.

Feature scoring reference (from run_mlb_independent_feature_candidate_export.py):
  recent_form  : indep_recent_win_rate_delta  × +0.15
  rest         : indep_rest_days_delta        × +0.03/7
  bullpen      : indep_bullpen_proxy_delta    × −0.05
  starter      : indep_starter_era_delta      × −0.10
  weather      : indep_wind_kmh / indep_temp_c — symmetric, no logit contribution

  base_model   : raw_model_prob_before_p10 (or raw_model_prob_home) as logit base
"""
from __future__ import annotations

import json
import math
from typing import Any

__all__ = [
    "FEATURE_FAMILIES",
    "classify_feature_columns",
    "build_ablation_variant_rows",
    "generate_ablation_plan",
]

# ─────────────────────────────────────────────────────────────────────────────
# § 1  Feature family definitions
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_FAMILIES: dict[str, list[str]] = {
    "recent_form": [
        "indep_home_recent_win_rate",
        "indep_away_recent_win_rate",
        "indep_recent_win_rate_delta",
        "indep_home_recent_games_count",
        "indep_away_recent_games_count",
        # P9 repaired columns
        "recent_win_rate_home",
        "recent_win_rate_away",
        "win_rate_delta",
    ],
    "rest": [
        "indep_home_rest_days",
        "indep_away_rest_days",
        "indep_rest_days_delta",
        # P9 repaired columns
        "rest_days_home",
        "rest_days_away",
        "rest_delta",
    ],
    "bullpen": [
        "indep_home_bullpen_usage_3d",
        "indep_away_bullpen_usage_3d",
        "indep_bullpen_proxy_delta",
        # P9 repaired columns
        "bullpen_usage_last_3d_home",
        "bullpen_usage_last_3d_away",
        "bullpen_delta",
    ],
    "starter": [
        "indep_home_starter_era_proxy",
        "indep_away_starter_era_proxy",
        "indep_starter_era_delta",
    ],
    "weather": [
        "indep_wind_kmh",
        "indep_temp_c",
        "indep_park_roof_type",
    ],
    "market": [
        "Home ML",
        "Away ML",
        "Over",
        "Under",
        "O/U",
        "Home RL Spread",
        "RL Away",
        "RL Home",
    ],
    "base_model": [
        "model_prob_home",
        "raw_model_prob_home",
        "model_version",
        "probability_source",
        "raw_model_prob_before_p10",
        "repaired_feature_version",
        "repaired_home_bias_removed",
        "repaired_feature_trace",
    ],
}

# Columns that identify a row (never modified by ablation)
_IDENTITY_COLS: set[str] = {
    "Date",
    "Start Time (EDT)",
    "Away",
    "Home",
    "Away Score",
    "Home Score",
    "Status",
    "Away Starter",
    "Home Starter",
    "source_file",
    "source_type",
    "is_verified_real",
    "game_id",
    "paper_only",
    "leakage_safe",
    "model_prob_away",
    "model_version",
    "probability_source",
    "probability_source_trace",
    "independent_feature_version",
    "independent_feature_source",
    "feature_candidate_mode",
    "indep_date",
    "indep_home_team",
    "indep_away_team",
    "indep_feature_version",
    "indep_feature_source",
    "indep_leakage_safe",
    "indep_generated_at_utc",
    "indep_source_trace",
}

# Build a reverse index: column → family
_COL_TO_FAMILY: dict[str, str] = {}
for _fam, _cols in FEATURE_FAMILIES.items():
    for _col in _cols:
        _COL_TO_FAMILY[_col] = _fam


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Column classifier
# ─────────────────────────────────────────────────────────────────────────────

def classify_feature_columns(columns: list[str]) -> dict[str, Any]:
    """
    Classify a list of CSV column names into feature families.

    Returns a dict with:
      family_to_cols     : dict[family_name, list[column]]
      unknown_columns    : list[column] (not in any family, not identity)
      feature_count_by_family : dict[family_name, int]
    """
    family_to_cols: dict[str, list[str]] = {f: [] for f in FEATURE_FAMILIES}
    unknown: list[str] = []

    for col in columns:
        fam = _COL_TO_FAMILY.get(col)
        if fam:
            family_to_cols[fam].append(col)
        elif col not in _IDENTITY_COLS:
            unknown.append(col)

    return {
        "family_to_cols": family_to_cols,
        "unknown_columns": unknown,
        "feature_count_by_family": {f: len(v) for f, v in family_to_cols.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Probability recomputation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _logit(p: float) -> float:
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1 - p))


def _clamp(p: float, lo: float = 0.01, hi: float = 0.99) -> float:
    return max(lo, min(hi, p))


def _safe_float(v: Any) -> float | None:
    if v is None or str(v).strip() in ("", "nan", "None"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _recompute_prob(row: dict, enabled_families: list[str]) -> tuple[float, dict]:
    """
    Recompute candidate probability using only enabled feature families.

    Returns (new_prob, ablation_trace).
    """
    trace: dict[str, Any] = {}

    # Base probability
    use_base = "base_model" in enabled_families
    base_prob = 0.5
    base_source = "default_0.5"

    if use_base:
        for col in ("raw_model_prob_before_p10", "raw_model_prob_home"):
            v = _safe_float(row.get(col))
            if v is not None and 0 < v < 1:
                base_prob = v
                base_source = col
                break

    trace["base_prob"] = base_prob
    trace["base_source"] = base_source

    adj = 0.0

    # recent_form contribution
    if "recent_form" in enabled_families:
        wr_delta = _safe_float(row.get("indep_recent_win_rate_delta"))
        if wr_delta is not None:
            c = 0.15 * wr_delta
            adj += c
            trace["recent_form_contrib"] = round(c, 6)
        else:
            trace["recent_form_contrib"] = 0.0
    else:
        trace["recent_form_contrib"] = None  # disabled

    # rest contribution
    if "rest" in enabled_families:
        rest_delta = _safe_float(row.get("indep_rest_days_delta"))
        if rest_delta is not None:
            c = 0.03 * rest_delta / 7.0
            adj += c
            trace["rest_contrib"] = round(c, 6)
        else:
            trace["rest_contrib"] = 0.0
    else:
        trace["rest_contrib"] = None

    # bullpen contribution
    if "bullpen" in enabled_families:
        bp_delta = _safe_float(row.get("indep_bullpen_proxy_delta"))
        if bp_delta is not None:
            c = -0.05 * bp_delta
            adj += c
            trace["bullpen_contrib"] = round(c, 6)
        else:
            trace["bullpen_contrib"] = 0.0
    else:
        trace["bullpen_contrib"] = None

    # starter contribution
    if "starter" in enabled_families:
        era_delta = _safe_float(row.get("indep_starter_era_delta"))
        if era_delta is not None:
            c = -0.10 * era_delta
            adj += c
            trace["starter_contrib"] = round(c, 6)
        else:
            trace["starter_contrib"] = 0.0
    else:
        trace["starter_contrib"] = None

    # weather: no direct logit contribution (symmetric effect), always 0
    trace["weather_contrib"] = 0.0

    trace["total_adj"] = round(adj, 6)
    new_logit = _logit(base_prob) + adj
    new_prob = _clamp(_sigmoid(new_logit))
    trace["new_prob"] = round(new_prob, 6)

    return new_prob, trace


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Ablation variant row builder
# ─────────────────────────────────────────────────────────────────────────────

def build_ablation_variant_rows(
    rows: list[dict],
    *,
    enabled_families: list[str],
    probability_col: str = "model_prob_home",
    variant_name: str = "ablation_variant",
) -> tuple[list[dict], dict]:
    """
    Build ablation variant rows by enabling only the specified feature families.

    Parameters
    ----------
    rows : list[dict]
        Input rows from P11 feature candidate CSV.
    enabled_families : list[str]
        Feature families to include.  Unknown family names are ignored with a
        warning in the metadata.
    probability_col : str
        Output column name for the recomputed probability.
    variant_name : str
        Human-readable name for this variant (e.g. "recent_only").

    Returns
    -------
    (variant_rows, metadata)
    """
    all_families = set(FEATURE_FAMILIES.keys())
    enabled_set = set(enabled_families)
    disabled_set = all_families - enabled_set
    unknown_requested = enabled_set - all_families

    variant_rows: list[dict] = []
    recomputed_count = 0
    fallback_count = 0

    for row in rows:
        out = dict(row)

        # Preserve raw model prob
        if "raw_model_prob_home" not in out or not out["raw_model_prob_home"]:
            out["raw_model_prob_home"] = row.get("model_prob_home")

        # Nullify disabled family columns (except identity cols)
        for fam in disabled_set:
            for col in FEATURE_FAMILIES.get(fam, []):
                if col in out and col not in _IDENTITY_COLS:
                    out[col] = None

        # Recompute probability
        new_prob, trace = _recompute_prob(row, list(enabled_set))
        out[probability_col] = new_prob
        # Keep model_prob_away consistent
        out["model_prob_away"] = _clamp(1.0 - new_prob)
        recomputed_count += 1

        # Ablation metadata
        out["ablation_variant_name"] = variant_name
        out["ablation_enabled_families"] = json.dumps(sorted(enabled_set))
        out["ablation_disabled_families"] = json.dumps(sorted(disabled_set))
        out["ablation_trace"] = json.dumps(trace)
        out["probability_source"] = "feature_ablation_candidate"

        variant_rows.append(out)

    metadata: dict[str, Any] = {
        "variant_name": variant_name,
        "enabled_families": sorted(enabled_set),
        "disabled_families": sorted(disabled_set),
        "unknown_requested_families": sorted(unknown_requested),
        "total_input_rows": len(rows),
        "recomputed_count": recomputed_count,
        "fallback_count": fallback_count,
        "probability_col": probability_col,
    }
    return variant_rows, metadata


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Ablation plan generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_ablation_plan() -> list[dict]:
    """
    Return the full P12 ablation plan as a list of variant specs.

    Each spec has:
      variant_name    : str
      enabled_families: list[str]
      description     : str
    """
    ALL = list(FEATURE_FAMILIES.keys())
    CONTEXT = ["recent_form", "rest", "bullpen", "starter", "weather"]
    BASE_MARKET = ["base_model", "market"]

    plan = [
        {
            "variant_name": "all_features",
            "enabled_families": ALL,
            "description": "Baseline: all feature families enabled",
        },
        {
            "variant_name": "recent_only",
            "enabled_families": ["recent_form", "base_model"],
            "description": "Only recent form features enabled",
        },
        {
            "variant_name": "rest_only",
            "enabled_families": ["rest", "base_model"],
            "description": "Only rest days features enabled",
        },
        {
            "variant_name": "bullpen_only",
            "enabled_families": ["bullpen", "base_model"],
            "description": "Only bullpen proxy features enabled",
        },
        {
            "variant_name": "starter_only",
            "enabled_families": ["starter", "base_model"],
            "description": "Only starter ERA proxy features enabled",
        },
        {
            "variant_name": "weather_only",
            "enabled_families": ["weather", "base_model"],
            "description": "Only weather features enabled (no logit contribution)",
        },
        {
            "variant_name": "no_recent",
            "enabled_families": [f for f in ALL if f != "recent_form"],
            "description": "All features except recent form",
        },
        {
            "variant_name": "no_rest",
            "enabled_families": [f for f in ALL if f != "rest"],
            "description": "All features except rest days",
        },
        {
            "variant_name": "no_bullpen",
            "enabled_families": [f for f in ALL if f != "bullpen"],
            "description": "All features except bullpen proxy",
        },
        {
            "variant_name": "no_starter",
            "enabled_families": [f for f in ALL if f != "starter"],
            "description": "All features except starter ERA proxy",
        },
        {
            "variant_name": "no_weather",
            "enabled_families": [f for f in ALL if f != "weather"],
            "description": "All features except weather",
        },
        {
            "variant_name": "no_context_features",
            "enabled_families": BASE_MARKET,
            "description": "Base model + market only, all context features disabled",
        },
        {
            "variant_name": "recent_plus_rest",
            "enabled_families": ["recent_form", "rest", "base_model"],
            "description": "Recent form + rest days only",
        },
        {
            "variant_name": "starter_plus_bullpen",
            "enabled_families": ["starter", "bullpen", "base_model"],
            "description": "Starter ERA + bullpen proxy only",
        },
        {
            "variant_name": "recent_rest_starter",
            "enabled_families": ["recent_form", "rest", "starter", "base_model"],
            "description": "Recent form + rest + starter ERA (no bullpen, no weather)",
        },
        {
            "variant_name": "market_or_base_only_baseline",
            "enabled_families": ["base_model"],
            "description": "Pure base model only, no feature adjustments at all",
        },
    ]

    return plan
