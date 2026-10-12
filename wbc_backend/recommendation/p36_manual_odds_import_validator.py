"""P36 Manual Odds Import Validator.

Validates a manually provided CSV of historical odds against:
- Required schema (11 columns)
- P32 game identity coverage
- No look-ahead leakage (no outcome columns)
- Value range checks

PAPER_ONLY=True, PRODUCTION_READY=False.
No scraping, no automated download.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from wbc_backend.recommendation.p36_odds_approval_contract import (
    ALLOWED_MARKET_TYPES,
    FORBIDDEN_ODDS_COLUMNS,
    MANUAL_ODDS_REQUIRED_COLUMNS,
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P36ManualOddsImportSpec,
)

logger = logging.getLogger(__name__)


def build_manual_odds_import_schema() -> P36ManualOddsImportSpec:
    """Return the canonical manual odds import specification."""
    return P36ManualOddsImportSpec(
        required_columns=MANUAL_ODDS_REQUIRED_COLUMNS,
        forbidden_columns=FORBIDDEN_ODDS_COLUMNS,
        allowed_market_types=ALLOWED_MARKET_TYPES,
        p_market_range=(0.0, 1.0),
        odds_decimal_min=1.0,
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
        notes=(
            "Manual licensed odds import only. "
            "No automated scraping or downloading. "
            "File must be obtained by the researcher after explicit ToS review. "
            "Raw odds files must NOT be committed to the repository."
        ),
        season=SEASON,
    )


def load_manual_odds_file(path: str) -> Optional[Any]:
    """Load a manual odds CSV as a pandas DataFrame.

    Returns None if path is missing, unreadable, or pandas is unavailable.
    """
    try:
        import pandas as pd  # local import — optional dependency
    except ImportError:
        logger.warning("pandas not available; cannot load manual odds file.")
        return None

    try:
        df = pd.read_csv(path, dtype=str)
        return df
    except FileNotFoundError:
        logger.warning("Manual odds file not found: %s", path)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load manual odds file %s: %s", path, exc)
        return None


def validate_manual_odds_schema(df: Any) -> Tuple[bool, str, List[str]]:
    """Check that *df* has all required columns and no forbidden columns.

    Returns (valid, reason, issues).
    """
    issues: List[str] = []

    present_cols = set(df.columns.tolist())
    missing_required = [c for c in MANUAL_ODDS_REQUIRED_COLUMNS if c not in present_cols]
    if missing_required:
        issues.append(f"Missing required columns: {missing_required}")

    found_forbidden = [c for c in FORBIDDEN_ODDS_COLUMNS if c in present_cols]
    if found_forbidden:
        issues.append(
            f"Forbidden outcome/leakage columns present: {found_forbidden}. "
            "These indicate look-ahead leakage."
        )

    if issues:
        return False, " | ".join(issues), issues
    return True, "Schema valid — all required columns present, no forbidden columns.", []


def validate_manual_odds_coverage(
    df: Any, game_identity_df: Any
) -> Tuple[bool, str, List[str]]:
    """Check that game_ids in *df* match P32 game identity.

    Returns (valid, reason, unmatched_game_ids).
    """
    if "game_id" not in df.columns:
        return False, "odds file missing game_id column.", []
    if "game_id" not in game_identity_df.columns:
        return False, "P32 game identity file missing game_id column.", []

    odds_ids = set(df["game_id"].dropna().astype(str).unique())
    p32_ids = set(game_identity_df["game_id"].dropna().astype(str).unique())

    unmatched = sorted(odds_ids - p32_ids)
    if unmatched:
        return (
            False,
            f"{len(unmatched)} game_id(s) in odds file not found in P32 identity "
            f"(first 5: {unmatched[:5]}).",
            unmatched,
        )

    coverage_pct = 100.0 * len(odds_ids & p32_ids) / max(len(p32_ids), 1)
    return (
        True,
        f"All odds game_ids match P32 ({len(odds_ids)} games, "
        f"{coverage_pct:.1f}% P32 coverage).",
        [],
    )


def validate_manual_odds_no_outcome_leakage(df: Any) -> Tuple[bool, str, List[str]]:
    """Check there are no outcome-derived columns and no missing game_date.

    Returns (valid, reason, issues).
    """
    issues: List[str] = []

    # No forbidden columns (belt-and-suspenders — also checked in schema)
    found_forbidden = [c for c in FORBIDDEN_ODDS_COLUMNS if c in df.columns]
    if found_forbidden:
        issues.append(f"Outcome/leakage columns: {found_forbidden}")

    # game_date must not be all-null
    if "game_date" in df.columns:
        null_count = int(df["game_date"].isna().sum())
        if null_count == len(df):
            issues.append("game_date is entirely missing.")
        elif null_count > 0:
            issues.append(f"game_date has {null_count} null values.")
    else:
        issues.append("game_date column not present.")

    if issues:
        return False, " | ".join(issues), issues
    return True, "No outcome leakage detected; game_date present.", []


def validate_manual_odds_value_ranges(df: Any) -> Tuple[bool, str, List[str]]:
    """Validate p_market [0,1] and odds_decimal > 1.

    Returns (valid, reason, issues).
    """
    import pandas as pd

    issues: List[str] = []

    if "p_market" in df.columns:
        try:
            p_vals = pd.to_numeric(df["p_market"], errors="coerce")
            out_of_range = int(((p_vals < 0) | (p_vals > 1)).sum())
            if out_of_range:
                issues.append(f"p_market has {out_of_range} values outside [0, 1].")
        except Exception:  # noqa: BLE001
            issues.append("p_market could not be parsed as numeric.")

    if "odds_decimal" in df.columns:
        try:
            o_vals = pd.to_numeric(df["odds_decimal"], errors="coerce")
            invalid = int((o_vals <= 1.0).sum())
            if invalid:
                issues.append(f"odds_decimal has {invalid} values <= 1.0.")
        except Exception:  # noqa: BLE001
            issues.append("odds_decimal could not be parsed as numeric.")

    if "market_type" in df.columns:
        bad_types = [
            str(v)
            for v in df["market_type"].dropna().unique()
            if str(v).lower().strip() not in ALLOWED_MARKET_TYPES
        ]
        if bad_types:
            issues.append(
                f"Unsupported market_type values: {bad_types[:5]}. "
                f"Allowed: {list(ALLOWED_MARKET_TYPES)}"
            )

    if issues:
        return False, " | ".join(issues), issues
    return True, "Value ranges valid.", []


def summarize_manual_odds_import(
    df: Optional[Any],
    game_identity_df: Optional[Any],
) -> Dict[str, Any]:
    """Run all validations and return a consolidated dict.

    If *df* is None (file not provided), returns a summary indicating no file.
    """
    if df is None:
        return {
            "file_provided": False,
            "schema_valid": False,
            "coverage_valid": False,
            "leakage_clean": False,
            "value_ranges_valid": False,
            "row_count": 0,
            "game_count": 0,
            "issues": ["No manual odds file provided."],
            "paper_only": PAPER_ONLY,
            "production_ready": PRODUCTION_READY,
            "season": SEASON,
            "status": "NO_FILE",
        }

    schema_valid, schema_reason, schema_issues = validate_manual_odds_schema(df)
    leakage_valid, leakage_reason, leakage_issues = (
        validate_manual_odds_no_outcome_leakage(df)
    )

    if game_identity_df is not None:
        coverage_valid, coverage_reason, _ = validate_manual_odds_coverage(
            df, game_identity_df
        )
    else:
        coverage_valid = False
        coverage_reason = "No P32 game identity file provided for coverage check."

    try:
        import pandas as pd

        value_valid, value_reason, value_issues = validate_manual_odds_value_ranges(df)
        row_count = len(df)
        game_count = df["game_id"].nunique() if "game_id" in df.columns else 0
    except Exception as exc:  # noqa: BLE001
        value_valid = False
        value_reason = f"Could not run value range checks: {exc}"
        value_issues = [value_reason]
        row_count = 0
        game_count = 0

    all_issues = schema_issues + leakage_issues + (
        [] if coverage_valid else [coverage_reason]
    ) + ([] if value_valid else [value_reason])

    overall_valid = schema_valid and leakage_valid and coverage_valid and value_valid

    return {
        "file_provided": True,
        "schema_valid": schema_valid,
        "schema_reason": schema_reason,
        "coverage_valid": coverage_valid,
        "coverage_reason": coverage_reason,
        "leakage_clean": leakage_valid,
        "leakage_reason": leakage_reason,
        "value_ranges_valid": value_valid,
        "value_ranges_reason": value_reason,
        "row_count": row_count,
        "game_count": game_count,
        "issues": all_issues,
        "overall_valid": overall_valid,
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "season": SEASON,
        "status": "VALID" if overall_valid else "INVALID",
    }
