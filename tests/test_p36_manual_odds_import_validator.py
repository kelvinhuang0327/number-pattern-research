"""Tests for P36 manual odds import validator."""
import io
import os
import tempfile

import pandas as pd
import pytest

from wbc_backend.recommendation.p36_odds_approval_contract import (
    FORBIDDEN_ODDS_COLUMNS,
    MANUAL_ODDS_REQUIRED_COLUMNS,
    PAPER_ONLY,
    PRODUCTION_READY,
)
from wbc_backend.recommendation.p36_manual_odds_import_validator import (
    build_manual_odds_import_schema,
    load_manual_odds_file,
    summarize_manual_odds_import,
    validate_manual_odds_coverage,
    validate_manual_odds_no_outcome_leakage,
    validate_manual_odds_schema,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_valid_df(n: int = 5) -> pd.DataFrame:
    """Return a minimal valid odds DataFrame."""
    return pd.DataFrame(
        {
            "game_id": [f"2024_{i:04d}" for i in range(n)],
            "game_date": ["2024-05-01"] * n,
            "home_team": ["NYA"] * n,
            "away_team": ["BOS"] * n,
            "p_market": ["0.55"] * n,
            "odds_decimal": ["1.82"] * n,
            "sportsbook": ["DraftKings"] * n,
            "market_type": ["moneyline"] * n,
            "closing_timestamp": ["2024-05-01T19:00:00Z"] * n,
            "source_odds_ref": ["sbr_2024"] * n,
            "license_ref": ["sbr_research_approved"] * n,
        }
    )


def _make_valid_game_identity_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "game_id": [f"2024_{i:04d}" for i in range(n)],
            "game_date": ["2024-05-01"] * n,
            "home_team": ["NYA"] * n,
            "away_team": ["BOS"] * n,
        }
    )


# ---------------------------------------------------------------------------
# build_manual_odds_import_schema
# ---------------------------------------------------------------------------


def test_schema_spec_returns_correct_type():
    spec = build_manual_odds_import_schema()
    from wbc_backend.recommendation.p36_odds_approval_contract import P36ManualOddsImportSpec
    assert isinstance(spec, P36ManualOddsImportSpec)


def test_schema_spec_paper_only():
    spec = build_manual_odds_import_schema()
    assert spec.paper_only is True
    assert spec.production_ready is False


def test_schema_spec_required_columns_match_contract():
    spec = build_manual_odds_import_schema()
    assert set(spec.required_columns) == set(MANUAL_ODDS_REQUIRED_COLUMNS)


def test_schema_spec_y_true_in_forbidden():
    spec = build_manual_odds_import_schema()
    assert "y_true" in spec.forbidden_columns


def test_schema_spec_p_market_range():
    spec = build_manual_odds_import_schema()
    assert spec.p_market_range == (0.0, 1.0)


def test_schema_spec_odds_decimal_min():
    spec = build_manual_odds_import_schema()
    assert spec.odds_decimal_min == 1.0


# ---------------------------------------------------------------------------
# load_manual_odds_file
# ---------------------------------------------------------------------------


def test_load_manual_odds_file_missing_returns_none():
    assert load_manual_odds_file("/nonexistent/path.csv") is None


def test_load_manual_odds_file_valid_csv():
    df = _make_valid_df()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "odds.csv")
        df.to_csv(path, index=False)
        result = load_manual_odds_file(path)
    assert result is not None
    assert "game_id" in result.columns


# ---------------------------------------------------------------------------
# validate_manual_odds_schema
# ---------------------------------------------------------------------------


def test_validate_schema_valid_df():
    df = _make_valid_df()
    valid, reason, issues = validate_manual_odds_schema(df)
    assert valid is True
    assert issues == []


def test_validate_schema_missing_license_ref():
    df = _make_valid_df().drop(columns=["license_ref"])
    valid, reason, issues = validate_manual_odds_schema(df)
    assert valid is False
    assert any("license_ref" in i for i in issues)


def test_validate_schema_y_true_present_fails():
    df = _make_valid_df()
    df["y_true"] = 1
    valid, reason, issues = validate_manual_odds_schema(df)
    assert valid is False
    assert any("y_true" in i for i in issues)


def test_validate_schema_final_score_present_fails():
    df = _make_valid_df()
    df["final_score"] = "3-2"
    valid, reason, issues = validate_manual_odds_schema(df)
    assert valid is False
    assert any("final_score" in i for i in issues)


def test_validate_schema_extra_non_forbidden_columns_ok():
    df = _make_valid_df()
    df["extra_info"] = "x"  # not forbidden
    valid, reason, issues = validate_manual_odds_schema(df)
    assert valid is True


def test_validate_schema_requires_source_odds_ref():
    df = _make_valid_df().drop(columns=["source_odds_ref"])
    valid, reason, issues = validate_manual_odds_schema(df)
    assert valid is False


# ---------------------------------------------------------------------------
# validate_manual_odds_coverage
# ---------------------------------------------------------------------------


def test_validate_coverage_all_match():
    df = _make_valid_df(5)
    identity = _make_valid_game_identity_df(5)
    valid, reason, unmatched = validate_manual_odds_coverage(df, identity)
    assert valid is True
    assert unmatched == []


def test_validate_coverage_unmatched_game_ids():
    df = _make_valid_df(5)
    identity = _make_valid_game_identity_df(3)  # only first 3
    valid, reason, unmatched = validate_manual_odds_coverage(df, identity)
    assert valid is False
    assert len(unmatched) == 2


def test_validate_coverage_missing_game_id_col_in_odds():
    df = _make_valid_df().drop(columns=["game_id"])
    identity = _make_valid_game_identity_df()
    valid, reason, unmatched = validate_manual_odds_coverage(df, identity)
    assert valid is False


def test_validate_coverage_missing_game_id_col_in_identity():
    df = _make_valid_df()
    identity = _make_valid_game_identity_df().drop(columns=["game_id"])
    valid, reason, unmatched = validate_manual_odds_coverage(df, identity)
    assert valid is False


# ---------------------------------------------------------------------------
# validate_manual_odds_no_outcome_leakage
# ---------------------------------------------------------------------------


def test_no_leakage_valid_df():
    df = _make_valid_df()
    valid, reason, issues = validate_manual_odds_no_outcome_leakage(df)
    assert valid is True


def test_leakage_detected_y_true():
    df = _make_valid_df()
    df["y_true"] = 1
    valid, reason, issues = validate_manual_odds_no_outcome_leakage(df)
    assert valid is False
    assert any("y_true" in i for i in issues)


def test_leakage_null_game_date():
    df = _make_valid_df()
    df["game_date"] = None
    valid, reason, issues = validate_manual_odds_no_outcome_leakage(df)
    assert valid is False


def test_leakage_missing_game_date_col():
    df = _make_valid_df().drop(columns=["game_date"])
    valid, reason, issues = validate_manual_odds_no_outcome_leakage(df)
    assert valid is False


# ---------------------------------------------------------------------------
# summarize_manual_odds_import
# ---------------------------------------------------------------------------


def test_summarize_no_file():
    summary = summarize_manual_odds_import(None, None)
    assert summary["file_provided"] is False
    assert summary["status"] == "NO_FILE"
    assert summary["paper_only"] is True
    assert summary["production_ready"] is False


def test_summarize_valid_file_and_identity():
    df = _make_valid_df(5)
    identity = _make_valid_game_identity_df(5)
    summary = summarize_manual_odds_import(df, identity)
    assert summary["file_provided"] is True
    assert summary["schema_valid"] is True
    assert summary["leakage_clean"] is True
    assert summary["coverage_valid"] is True
    assert summary["status"] == "VALID"


def test_summarize_invalid_schema_reports_invalid():
    df = _make_valid_df()
    df["y_true"] = 1  # leakage
    summary = summarize_manual_odds_import(df, None)
    assert summary["status"] == "INVALID"
    assert len(summary["issues"]) > 0
