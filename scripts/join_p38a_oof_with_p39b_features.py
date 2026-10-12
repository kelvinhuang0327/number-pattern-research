#!/usr/bin/env python3
"""
P39C / P39E — Join P38A OOF Predictions with P39B Rolling Pybaseball Features

SCRIPT_VERSION = "p39c_feature_join_v1"
PAPER_ONLY = True
production_ready = False

Usage:
  # Summary-only (default, no file write):
  python scripts/join_p38a_oof_with_p39b_features.py --summary-only

  # Fixture smoke (synthetic data, no network):
  python scripts/join_p38a_oof_with_p39b_features.py --fixture-mode --summary-only

  # Custom paths, execute + write (with team code normalization on by default):
  python scripts/join_p38a_oof_with_p39b_features.py \\
    --p38a-path outputs/predictions/PAPER/p38a_2024_oof/p38a_2024_oof_predictions.csv \\
    --p39b-path data/pybaseball/local_only/p39e_rolling_features_2024_04_08_04_30.csv \\
    --execute --out-file data/pybaseball/local_only/p39e_enriched_p38a_april_sample.csv

Acceptance markers:
  P39C_JOIN_UTILITY_READY_20260515
  P39E_JOIN_UTILITY_TEAM_NORMALIZATION_READY_20260515
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from typing import Any

import pandas as pd

from scripts.team_code_normalization import normalize_team_code

SCRIPT_VERSION = "p39c_feature_join_v1"
PREV_VERSION = "p39b_pybaseball_rolling_v1"
PAPER_ONLY = True

# Forbidden odds columns (exact match, lowercase)
FORBIDDEN_ODDS_COLUMNS: frozenset[str] = frozenset({
    "moneyline", "closing_line", "opening_line", "odds", "vig",
    "implied_prob", "home_ml", "away_ml", "home_odds", "away_odds",
    "clv", "closing_implied_prob", "no_vig_prob", "spread", "over_under",
    "sportsbook", "line_move", "sharp_money",
})

# Forbidden keyword substrings (case-insensitive)
FORBIDDEN_ODDS_KEYWORDS: frozenset[str] = frozenset({
    "odds", "moneyline", "spread", "sportsbook", "vig", "implied",
})

REQUIRED_P38A_COLS: frozenset[str] = frozenset({
    "game_id", "p_oof", "fold_id", "model_version",
})

REQUIRED_P39B_COLS: frozenset[str] = frozenset({
    "as_of_date", "team", "feature_window_end", "leakage_status",
})

# Default paths
DEFAULT_P38A_PATH = "outputs/predictions/PAPER/p38a_2024_oof/p38a_2024_oof_predictions.csv"
DEFAULT_P39B_PATH = "data/pybaseball/fixtures/P39C_SYNTHETIC_ROLLING_FEATURES_20260515.csv"

# Feature columns from P39B to carry into joined output
P39B_VALUE_COLS = [
    "rolling_pa_proxy",
    "rolling_avg_launch_speed",
    "rolling_hard_hit_rate_proxy",
    "rolling_barrel_rate_proxy",
    "sample_size",
]

# P39B metadata columns (not prefixed; used for join only)
P39B_META_COLS = {
    "as_of_date", "team", "feature_window_start",
    "feature_window_end", "window_days", "leakage_status", "source",
}


# ──────────────────────────────────────────────────────────────────────────────
# Pure Functions
# ──────────────────────────────────────────────────────────────────────────────


def normalize_team_codes_in_df(
    df: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """
    Normalize team code columns in a DataFrame to canonical Statcast codes.

    Missing columns are silently skipped (e.g., away_team absent from real P38A).
    Unknown codes are kept as-is and reported in the returned dict.

    Args:
        df: Input DataFrame.
        columns: Column names to normalize (e.g. ["home_team", "away_team"] or ["team"]).

    Returns:
        Tuple of (normalized DataFrame copy, dict mapping column → list of unknown codes seen).
    """
    result = df.copy()
    unknown_by_col: dict[str, list[str]] = {}
    for col in columns:
        if col not in result.columns:
            continue
        unknowns: list[str] = []
        new_vals: list[Any] = []
        for val in result[col]:
            if pd.isna(val):
                new_vals.append(val)
            else:
                normalized = normalize_team_code(str(val))
                if normalized is None:
                    unknowns.append(str(val))
                    new_vals.append(str(val))  # keep original; caller decides how to handle
                else:
                    new_vals.append(normalized)
        result[col] = new_vals
        if unknowns:
            unknown_by_col[col] = unknowns
    return result, unknown_by_col


def assert_no_odds_columns(columns: list[str] | pd.Index) -> None:
    """
    Reject any odds-related column names (exact match or keyword substring).
    Raises ValueError on first violation.
    """
    cols_lower = [c.lower() for c in columns]
    for col in cols_lower:
        if col in FORBIDDEN_ODDS_COLUMNS:
            raise ValueError(f"Forbidden odds column detected (exact match): {col!r}")
    for col in cols_lower:
        for keyword in FORBIDDEN_ODDS_KEYWORDS:
            if keyword in col:
                raise ValueError(
                    f"Forbidden odds keyword {keyword!r} found in column: {col!r}"
                )


def validate_join_leakage(
    p38a_df: pd.DataFrame,  # noqa: ARG001 — reserved for future game-date cross-check
    feature_df: pd.DataFrame,
) -> list[str]:
    """
    Validate that all P39B feature rows satisfy pregame-safe invariants:
      - leakage_status == "pregame_safe"
      - feature_window_end < as_of_date (strict D-1)

    Returns list of violation messages. Empty list = no violations.
    """
    violations: list[str] = []

    if "leakage_status" in feature_df.columns:
        bad_status = feature_df[feature_df["leakage_status"] != "pregame_safe"]
        if not bad_status.empty:
            violations.append(
                f"leakage_status != pregame_safe: {len(bad_status)} rows affected"
            )

    if "feature_window_end" in feature_df.columns and "as_of_date" in feature_df.columns:
        wend = pd.to_datetime(feature_df["feature_window_end"].astype(str)).dt.date
        asof = pd.to_datetime(feature_df["as_of_date"].astype(str)).dt.date
        bad_window = feature_df[wend >= asof]
        if not bad_window.empty:
            violations.append(
                f"feature_window_end >= as_of_date: {len(bad_window)} rows (pregame leakage!)"
            )

    return violations


def _extract_game_meta(game_id: str) -> tuple[str | None, str | None]:
    """
    Extract (home_team, game_date_iso) from Retrosheet game_id format HOME-YYYYMMDD-N.
    Returns (None, None) on parse failure.
    """
    try:
        parts = game_id.split("-")
        if len(parts) < 3:
            return None, None
        home_team = parts[0]
        raw_date = parts[1]  # YYYYMMDD
        if len(raw_date) != 8 or not raw_date.isdigit():
            return None, None
        game_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        return home_team, game_date
    except Exception:
        return None, None


def _enrich_p38a_with_game_meta(p38a_df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive home_team and game_date columns from game_id when not already present.
    """
    df = p38a_df.copy()
    meta = df["game_id"].apply(_extract_game_meta)
    if "home_team" not in df.columns:
        df["home_team"] = meta.apply(lambda x: x[0])
    if "game_date" not in df.columns:
        df["game_date"] = meta.apply(lambda x: x[1])
    return df


def join_home_away_features(
    p38a_df: pd.DataFrame,
    feature_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join rolling features onto P38A predictions for both home and away teams.

    Join logic:
    - home: P38A.game_date == feature.as_of_date AND P38A.home_team == feature.team
    - away: P38A.game_date == feature.as_of_date AND P38A.away_team == feature.team
    - home feature columns prefixed with home_
    - away feature columns prefixed with away_
    - derives differential features when both sides matched

    Returns enriched DataFrame (left join — missing features become NaN, no crash).
    """
    # Determine which P39B value cols are actually present
    value_cols = [c for c in P39B_VALUE_COLS if c in feature_df.columns]

    # Normalise join keys to string
    p38a = p38a_df.copy()
    feat = feature_df.copy()
    p38a["game_date"] = p38a["game_date"].astype(str)
    feat["as_of_date"] = feat["as_of_date"].astype(str)

    # Slim feature frame: join keys + value cols only
    feat_slim = feat[["as_of_date", "team"] + value_cols]

    # ── Home join ────────────────────────────────────────────────────────────
    home_rename = {"as_of_date": "game_date", "team": "home_team"}
    home_rename.update({c: f"home_{c}" for c in value_cols})
    home_feat = feat_slim.rename(columns=home_rename)
    joined = p38a.merge(home_feat, on=["game_date", "home_team"], how="left")

    # ── Away join ────────────────────────────────────────────────────────────
    if "away_team" in joined.columns:
        away_rename = {"as_of_date": "game_date", "team": "away_team"}
        away_rename.update({c: f"away_{c}" for c in value_cols})
        away_feat = feat_slim.rename(columns=away_rename)
        joined = joined.merge(away_feat, on=["game_date", "away_team"], how="left")

    # ── Differential features ────────────────────────────────────────────────
    home_ls = "home_rolling_avg_launch_speed"
    away_ls = "away_rolling_avg_launch_speed"
    if home_ls in joined.columns and away_ls in joined.columns:
        joined["diff_rolling_avg_launch_speed"] = joined[home_ls] - joined[away_ls]

    home_hh = "home_rolling_hard_hit_rate_proxy"
    away_hh = "away_rolling_hard_hit_rate_proxy"
    if home_hh in joined.columns and away_hh in joined.columns:
        joined["diff_rolling_hard_hit_rate_proxy"] = joined[home_hh] - joined[away_hh]

    home_ss = "home_sample_size"
    away_ss = "away_sample_size"
    if home_ss in joined.columns and away_ss in joined.columns:
        joined["diff_sample_size"] = joined[home_ss] - joined[away_ss]

    return joined


def summarize_join_result(joined_df: pd.DataFrame) -> dict[str, Any]:
    """
    Produce a structured summary dict for a completed join result.
    Includes match rates, odds boundary status, and a deterministic hash.
    """
    total = len(joined_df)

    home_ls_col = "home_rolling_avg_launch_speed"
    away_ls_col = "away_rolling_avg_launch_speed"
    home_matched = int(joined_df[home_ls_col].notna().sum()) if home_ls_col in joined_df.columns else 0
    away_matched = int(joined_df[away_ls_col].notna().sum()) if away_ls_col in joined_df.columns else 0

    # Odds boundary
    try:
        assert_no_odds_columns(list(joined_df.columns))
        odds_boundary = "CONFIRMED"
    except ValueError as exc:
        odds_boundary = f"VIOLATED: {exc}"

    # Deterministic hash over sorted p_oof values
    if "p_oof" in joined_df.columns:
        vals = "|".join(joined_df.sort_values("game_id")["p_oof"].astype(str).tolist())
        det_hash = hashlib.sha256(vals.encode()).hexdigest()[:16]
    else:
        det_hash = "n/a"

    return {
        "script_version": SCRIPT_VERSION,
        "paper_only": PAPER_ONLY,
        "total_p38a_rows": total,
        "home_feature_match_count": home_matched,
        "home_feature_match_rate": round(home_matched / max(total, 1), 4),
        "away_feature_match_count": away_matched,
        "away_feature_match_rate": round(away_matched / max(total, 1), 4),
        "unmatched_home_count": total - home_matched,
        "unmatched_away_count": total - away_matched,
        "odds_boundary": odds_boundary,
        "leakage_violations": 0,
        "deterministic_hash": det_hash,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Fixture (synthetic inline data for --fixture-mode smoke)
# ──────────────────────────────────────────────────────────────────────────────


def _build_fixture_p38a() -> pd.DataFrame:
    """Synthetic P38A fixture for --fixture-mode. 5 games with home + away team."""
    return pd.DataFrame([
        {
            "game_id": "BAL-20240415-0", "p_oof": 0.52, "fold_id": 0,
            "model_version": "p38a_fixture", "game_date": "2024-04-15",
            "home_team": "BAL", "away_team": "BOS",
        },
        {
            "game_id": "NYY-20240416-0", "p_oof": 0.61, "fold_id": 0,
            "model_version": "p38a_fixture", "game_date": "2024-04-16",
            "home_team": "NYY", "away_team": "TBR",
        },
        {
            "game_id": "HOU-20240417-0", "p_oof": 0.45, "fold_id": 0,
            "model_version": "p38a_fixture", "game_date": "2024-04-17",
            "home_team": "HOU", "away_team": "LAA",
        },
        {
            "game_id": "ATL-20240418-0", "p_oof": 0.58, "fold_id": 0,
            "model_version": "p38a_fixture", "game_date": "2024-04-18",
            "home_team": "ATL", "away_team": "NYM",
        },
        {
            "game_id": "CHC-20240419-0", "p_oof": 0.50, "fold_id": 0,
            "model_version": "p38a_fixture", "game_date": "2024-04-19",
            "home_team": "CHC", "away_team": "MIL",
        },
    ])


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P39C: Join P38A OOF predictions with P39B rolling features"
    )
    parser.add_argument(
        "--p38a-path",
        default=DEFAULT_P38A_PATH,
        help="Path to P38A OOF predictions CSV",
    )
    parser.add_argument(
        "--p39b-path",
        default=DEFAULT_P39B_PATH,
        help="Path to P39B rolling features CSV",
    )
    parser.add_argument(
        "--out-file",
        default=None,
        help="Output path for enriched CSV (requires --execute)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        default=False,
        help="Print summary only (default behaviour if --execute not passed)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Enable file write to --out-file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be written without writing",
    )
    parser.add_argument(
        "--fixture-mode",
        action="store_true",
        default=False,
        help="Use synthetic inline P38A fixture (smoke testing without raw data)",
    )
    parser.add_argument(
        "--normalize-team-codes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Normalize team codes (Retrosheet→Statcast) before join (default: on). "
            "Use --no-normalize-team-codes to disable."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"P39C Join Utility — {SCRIPT_VERSION}")
    print(f"  prev_version  : {PREV_VERSION}")
    print(f"  PAPER_ONLY    : {PAPER_ONLY}")

    # ── Load P38A ─────────────────────────────────────────────────────────────
    if args.fixture_mode:
        print("  mode          : FIXTURE (synthetic inline P38A + file-based P39B)")
        p38a_df = _build_fixture_p38a()
    else:
        print(f"  p38a_path     : {args.p38a_path}")
        try:
            p38a_df = pd.read_csv(args.p38a_path)
        except FileNotFoundError:
            print(f"  ERROR: P38A file not found: {args.p38a_path}", file=sys.stderr)
            sys.exit(1)
        # Derive game_date + home_team from game_id if not present
        if "game_date" not in p38a_df.columns or "home_team" not in p38a_df.columns:
            p38a_df = _enrich_p38a_with_game_meta(p38a_df)
        missing = REQUIRED_P38A_COLS - set(p38a_df.columns)
        if missing:
            print(f"  ERROR: P38A missing required columns: {missing}", file=sys.stderr)
            sys.exit(1)

    print(f"  p38a_rows     : {len(p38a_df)}")

    # ── Load P39B rolling features ─────────────────────────────────────────────
    print(f"  p39b_path     : {args.p39b_path}")
    try:
        feature_df = pd.read_csv(args.p39b_path)
    except FileNotFoundError:
        print(f"  ERROR: P39B fixture not found: {args.p39b_path}", file=sys.stderr)
        sys.exit(1)
    print(f"  p39b_rows     : {len(feature_df)}")

    # ── Team code normalization (default: ON) ────────────────────────────────
    if args.normalize_team_codes:
        p38a_df, p38a_unknown = normalize_team_codes_in_df(
            p38a_df, ["home_team", "away_team"]
        )
        feature_df, feat_unknown = normalize_team_codes_in_df(feature_df, ["team"])
        all_unknown = {**p38a_unknown, **feat_unknown}
        if all_unknown:
            print(f"  [WARN] Unknown team codes (kept as-is): {all_unknown}")
        else:
            print(f"  team_code_normalization : OK (no unknowns)")
    else:
        print(f"  team_code_normalization : DISABLED (--no-normalize-team-codes)")

    # ── Odds boundary check on inputs ─────────────────────────────────────────
    try:
        assert_no_odds_columns(list(p38a_df.columns))
        assert_no_odds_columns(list(feature_df.columns))
    except ValueError as exc:
        print(f"  ERROR: Odds boundary violation in input: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Leakage validation ────────────────────────────────────────────────────
    missing_p39b = REQUIRED_P39B_COLS - set(feature_df.columns)
    if missing_p39b:
        print(f"  ERROR: P39B missing required columns: {missing_p39b}", file=sys.stderr)
        sys.exit(1)

    violations = validate_join_leakage(p38a_df, feature_df)
    if violations:
        for v in violations:
            print(f"  LEAKAGE VIOLATION: {v}", file=sys.stderr)
        sys.exit(1)
    print(f"  leakage_violations : 0")

    # ── Perform join ──────────────────────────────────────────────────────────
    joined = join_home_away_features(p38a_df, feature_df)
    print(f"  joined_rows   : {len(joined)}")

    # ── Odds boundary check on output ─────────────────────────────────────────
    try:
        assert_no_odds_columns(list(joined.columns))
    except ValueError as exc:
        print(f"  ERROR: Odds boundary violation in output: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = summarize_join_result(joined)
    print("\n  Join Summary:")
    for k, v in summary.items():
        print(f"    {k:<40}: {v}")

    print(f"\n  Markers:")
    print(f"    P39C_JOIN_UTILITY_READY_20260515")
    print(f"    P39E_JOIN_UTILITY_TEAM_NORMALIZATION_READY_20260515")
    print(f"  PAPER_ONLY=True — no production write")

    # ── Write output (only with --execute) ───────────────────────────────────
    if args.execute:
        if args.out_file is None:
            print("  execute mode enabled but --out-file not specified; skipping write")
        elif args.dry_run:
            print(f"  DRY-RUN: would write {len(joined)} rows to {args.out_file}")
        else:
            joined.to_csv(args.out_file, index=False)
            print(f"  Written: {args.out_file}")


if __name__ == "__main__":
    main()
