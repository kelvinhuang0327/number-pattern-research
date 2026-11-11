"""
Tests for P33 Joined Input Spec Validator
"""

import pytest
import pandas as pd

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    FORBIDDEN_LEAKAGE_PREFIXES,
    REQUIRED_JOINED_INPUT_FIELDS,
)
from wbc_backend.recommendation.p33_joined_input_spec_validator import (
    P33JoinedInputValidationReport,
    build_required_joined_input_spec,
    build_schema_gap_dict,
    identify_leakage_columns,
    identify_missing_joined_input_fields,
    summarize_joined_input_readiness,
    validate_candidate_joined_input,
    validate_no_leakage_columns,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_valid_df(rows: int = 5) -> pd.DataFrame:
    """Build a minimal DataFrame with all required fields populated."""
    data = {f: [None] * rows for f in REQUIRED_JOINED_INPUT_FIELDS}
    # Provide non-null values for required fields
    data["game_id"] = [f"g{i}" for i in range(rows)]
    data["game_date"] = ["2024-04-01"] * rows
    data["home_team"] = ["NYY"] * rows
    data["away_team"] = ["BOS"] * rows
    data["y_true_home_win"] = [1] * rows
    data["p_model"] = [0.55] * rows
    data["p_oof"] = [0.53] * rows
    data["p_market"] = [0.52] * rows
    data["odds_decimal"] = [1.92] * rows
    data["source_prediction_ref"] = ["elo_2024"] * rows
    data["source_odds_ref"] = ["pinnacle_2024"] * rows
    data["paper_only"] = [True] * rows
    data["production_ready"] = [False] * rows
    return pd.DataFrame(data)


def _make_incomplete_df() -> pd.DataFrame:
    """DataFrame missing p_model, p_oof, and odds fields."""
    return pd.DataFrame(
        {
            "game_id": ["g1"],
            "game_date": ["2024-04-01"],
            "home_team": ["NYY"],
            "away_team": ["BOS"],
            "y_true_home_win": [1],
        }
    )


def _make_leaky_df() -> pd.DataFrame:
    df = _make_valid_df(2)
    df["future_score"] = [5, 3]
    df["final_result_extra"] = ["W", "L"]
    return df


# ---------------------------------------------------------------------------
# build_required_joined_input_spec
# ---------------------------------------------------------------------------


class TestBuildRequiredJoinedInputSpec:
    def test_returns_spec(self):
        spec = build_required_joined_input_spec()
        assert spec.season == 2024
        assert spec.paper_only is True
        assert spec.production_ready is False

    def test_required_fields_match_constant(self):
        spec = build_required_joined_input_spec()
        assert set(spec.required_fields) == set(REQUIRED_JOINED_INPUT_FIELDS)


# ---------------------------------------------------------------------------
# identify_missing_joined_input_fields
# ---------------------------------------------------------------------------


class TestIdentifyMissingJoinedInputFields:
    def test_valid_df_no_missing(self):
        df = _make_valid_df()
        missing = identify_missing_joined_input_fields(df)
        assert missing == []

    def test_incomplete_df_has_missing(self):
        df = _make_incomplete_df()
        missing = identify_missing_joined_input_fields(df)
        assert "p_model" in missing
        assert "p_oof" in missing
        assert "odds_decimal" in missing
        assert "p_market" in missing

    def test_empty_df_all_missing(self):
        df = pd.DataFrame()
        missing = identify_missing_joined_input_fields(df)
        assert set(missing) == set(REQUIRED_JOINED_INPUT_FIELDS)

    def test_case_insensitive_column_detection(self):
        df = pd.DataFrame({"Game_ID": ["g1"], "GAME_DATE": ["2024-04-01"]})
        missing = identify_missing_joined_input_fields(df)
        assert "game_id" not in missing
        assert "game_date" not in missing


# ---------------------------------------------------------------------------
# identify_leakage_columns
# ---------------------------------------------------------------------------


class TestIdentifyLeakageColumns:
    def test_no_leakage_on_valid_df(self):
        df = _make_valid_df()
        assert identify_leakage_columns(df) == []

    def test_detects_future_prefix(self):
        df = pd.DataFrame({"future_result": [1]})
        leaky = identify_leakage_columns(df)
        assert "future_result" in leaky

    def test_detects_final_prefix(self):
        df = pd.DataFrame({"final_score": [5]})
        leaky = identify_leakage_columns(df)
        assert "final_score" in leaky

    def test_detects_multiple_leakage_cols(self):
        df = _make_leaky_df()
        leaky = identify_leakage_columns(df)
        assert len(leaky) >= 2

    def test_no_false_positive_on_valid_columns(self):
        df = _make_valid_df()
        leaky = identify_leakage_columns(df)
        assert leaky == []


# ---------------------------------------------------------------------------
# validate_no_leakage_columns
# ---------------------------------------------------------------------------


class TestValidateNoLeakageColumns:
    def test_clean_df_returns_true(self):
        df = _make_valid_df()
        assert validate_no_leakage_columns(df) is True

    def test_leaky_df_returns_false(self):
        df = _make_leaky_df()
        assert validate_no_leakage_columns(df) is False


# ---------------------------------------------------------------------------
# validate_candidate_joined_input
# ---------------------------------------------------------------------------


class TestValidateCandidateJoinedInput:
    def test_valid_df_is_valid(self):
        df = _make_valid_df()
        report = validate_candidate_joined_input(df)
        assert report.is_valid is True
        assert report.missing_fields == []
        assert report.leakage_risk_fields == []
        assert report.row_count == 5

    def test_incomplete_df_is_invalid(self):
        df = _make_incomplete_df()
        report = validate_candidate_joined_input(df)
        assert report.is_valid is False
        assert len(report.missing_fields) > 0
        assert len(report.blocker_reason) > 0

    def test_leaky_df_is_invalid(self):
        df = _make_leaky_df()
        report = validate_candidate_joined_input(df)
        assert report.is_valid is False
        assert len(report.leakage_risk_fields) > 0

    def test_report_is_instance(self):
        df = _make_valid_df()
        report = validate_candidate_joined_input(df)
        assert isinstance(report, P33JoinedInputValidationReport)

    def test_paper_only_flag(self):
        df = _make_valid_df()
        report = validate_candidate_joined_input(df)
        assert report.paper_only is True
        assert report.production_ready is False

    def test_null_counts_populated(self):
        df = _make_valid_df()
        df["p_model"] = None  # All null
        report = validate_candidate_joined_input(df)
        assert "p_model" in report.null_counts
        assert report.null_counts["p_model"] == 5

    def test_schema_gap_fields_populated_on_missing(self):
        df = _make_incomplete_df()
        report = validate_candidate_joined_input(df)
        assert len(report.schema_gap_fields) > 0

    def test_empty_df_all_missing(self):
        df = pd.DataFrame()
        report = validate_candidate_joined_input(df)
        assert report.is_valid is False
        assert len(report.missing_fields) == len(REQUIRED_JOINED_INPUT_FIELDS)


# ---------------------------------------------------------------------------
# summarize_joined_input_readiness
# ---------------------------------------------------------------------------


class TestSummarizeJoinedInputReadiness:
    def test_valid_returns_tick(self):
        df = _make_valid_df()
        summary = summarize_joined_input_readiness(df)
        assert "VALID" in summary

    def test_invalid_returns_cross(self):
        df = _make_incomplete_df()
        summary = summarize_joined_input_readiness(df)
        assert "INVALID" in summary

    def test_returns_string(self):
        df = _make_valid_df()
        result = summarize_joined_input_readiness(df)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# build_schema_gap_dict
# ---------------------------------------------------------------------------


class TestBuildSchemaGapDict:
    def test_none_df_all_missing(self):
        gap = build_schema_gap_dict(None)
        assert all(v == "MISSING" for v in gap.values())
        assert set(gap.keys()) == set(REQUIRED_JOINED_INPUT_FIELDS)

    def test_valid_df_all_present(self):
        df = _make_valid_df()
        gap = build_schema_gap_dict(df)
        for field in REQUIRED_JOINED_INPUT_FIELDS:
            assert gap[field] == "PRESENT", f"Field {field} should be PRESENT"

    def test_partial_df_mixed(self):
        df = _make_incomplete_df()
        gap = build_schema_gap_dict(df)
        assert gap["game_id"] == "PRESENT"
        assert gap["p_model"] == "MISSING"
        assert gap["odds_decimal"] == "MISSING"

    def test_null_column_reported(self):
        df = _make_valid_df()
        df["p_model"] = None
        gap = build_schema_gap_dict(df)
        assert gap["p_model"].startswith("PRESENT_NULLS=")
