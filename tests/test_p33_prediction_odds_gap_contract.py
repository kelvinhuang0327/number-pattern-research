"""
Tests for P33 Prediction/Odds Gap Contract
"""

import pytest

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    ALL_P33_GATE_VALUES,
    ALL_SOURCE_STATUSES,
    FORBIDDEN_LEAKAGE_PREFIXES,
    PAPER_ONLY,
    PRODUCTION_READY,
    REQUIRED_JOINED_INPUT_FIELDS,
    P33_BLOCKED_CONTRACT_VIOLATION,
    P33_BLOCKED_LICENSE_PROVENANCE_UNSAFE,
    P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE,
    P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
    P33_BLOCKED_SCHEMA_GAP,
    P33_FAIL_INPUT_MISSING,
    P33_FAIL_NON_DETERMINISTIC,
    P33_PREDICTION_ODDS_GAP_PLAN_READY,
    SOURCE_BLOCKED_LICENSE,
    SOURCE_BLOCKED_SCHEMA,
    SOURCE_MISSING,
    SOURCE_PARTIAL,
    SOURCE_READY,
    SOURCE_UNKNOWN,
    P33GateResult,
    P33OddsSourceCandidate,
    P33PredictionSourceCandidate,
    P33RequiredJoinedInputSpec,
    P33SourceGapSummary,
)


# ---------------------------------------------------------------------------
# Safety guards
# ---------------------------------------------------------------------------


class TestSafetyGuards:
    def test_paper_only_is_true(self):
        assert PAPER_ONLY is True

    def test_production_ready_is_false(self):
        assert PRODUCTION_READY is False


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


class TestGateConstants:
    def test_all_gate_values_registered(self):
        assert P33_PREDICTION_ODDS_GAP_PLAN_READY in ALL_P33_GATE_VALUES
        assert P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE in ALL_P33_GATE_VALUES
        assert P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE in ALL_P33_GATE_VALUES
        assert P33_BLOCKED_LICENSE_PROVENANCE_UNSAFE in ALL_P33_GATE_VALUES
        assert P33_BLOCKED_SCHEMA_GAP in ALL_P33_GATE_VALUES
        assert P33_BLOCKED_CONTRACT_VIOLATION in ALL_P33_GATE_VALUES
        assert P33_FAIL_INPUT_MISSING in ALL_P33_GATE_VALUES
        assert P33_FAIL_NON_DETERMINISTIC in ALL_P33_GATE_VALUES

    def test_gate_values_are_strings(self):
        for gv in ALL_P33_GATE_VALUES:
            assert isinstance(gv, str)
            assert len(gv) > 0

    def test_gate_values_unique(self):
        assert len(ALL_P33_GATE_VALUES) == len(set(ALL_P33_GATE_VALUES))

    def test_gate_values_uppercase(self):
        for gv in ALL_P33_GATE_VALUES:
            assert gv == gv.upper(), f"Gate value not uppercase: {gv}"

    def test_gate_count(self):
        assert len(ALL_P33_GATE_VALUES) == 8


# ---------------------------------------------------------------------------
# Source status constants
# ---------------------------------------------------------------------------


class TestSourceStatusConstants:
    def test_all_statuses_registered(self):
        assert SOURCE_READY in ALL_SOURCE_STATUSES
        assert SOURCE_PARTIAL in ALL_SOURCE_STATUSES
        assert SOURCE_MISSING in ALL_SOURCE_STATUSES
        assert SOURCE_BLOCKED_LICENSE in ALL_SOURCE_STATUSES
        assert SOURCE_BLOCKED_SCHEMA in ALL_SOURCE_STATUSES
        assert SOURCE_UNKNOWN in ALL_SOURCE_STATUSES

    def test_statuses_are_strings(self):
        for s in ALL_SOURCE_STATUSES:
            assert isinstance(s, str)

    def test_statuses_unique(self):
        assert len(ALL_SOURCE_STATUSES) == len(set(ALL_SOURCE_STATUSES))

    def test_status_count(self):
        assert len(ALL_SOURCE_STATUSES) == 6


# ---------------------------------------------------------------------------
# Required joined input fields
# ---------------------------------------------------------------------------


class TestRequiredJoinedInputFields:
    def test_required_fields_not_empty(self):
        assert len(REQUIRED_JOINED_INPUT_FIELDS) > 0

    def test_required_fields_count(self):
        assert len(REQUIRED_JOINED_INPUT_FIELDS) == 13

    def test_core_fields_present(self):
        core = ["game_id", "game_date", "home_team", "away_team", "y_true_home_win"]
        for f in core:
            assert f in REQUIRED_JOINED_INPUT_FIELDS, f"Missing core field: {f}"

    def test_prediction_fields_present(self):
        assert "p_model" in REQUIRED_JOINED_INPUT_FIELDS
        assert "p_oof" in REQUIRED_JOINED_INPUT_FIELDS

    def test_odds_fields_present(self):
        assert "p_market" in REQUIRED_JOINED_INPUT_FIELDS
        assert "odds_decimal" in REQUIRED_JOINED_INPUT_FIELDS

    def test_source_ref_fields_present(self):
        assert "source_prediction_ref" in REQUIRED_JOINED_INPUT_FIELDS
        assert "source_odds_ref" in REQUIRED_JOINED_INPUT_FIELDS

    def test_safety_fields_present(self):
        assert "paper_only" in REQUIRED_JOINED_INPUT_FIELDS
        assert "production_ready" in REQUIRED_JOINED_INPUT_FIELDS

    def test_fields_are_strings(self):
        for f in REQUIRED_JOINED_INPUT_FIELDS:
            assert isinstance(f, str)

    def test_fields_unique(self):
        assert len(REQUIRED_JOINED_INPUT_FIELDS) == len(set(REQUIRED_JOINED_INPUT_FIELDS))

    def test_fields_snake_case(self):
        for f in REQUIRED_JOINED_INPUT_FIELDS:
            assert f == f.lower(), f"Field not snake_case: {f}"
            assert " " not in f, f"Field contains space: {f}"


# ---------------------------------------------------------------------------
# Leakage prefix guard
# ---------------------------------------------------------------------------


class TestLeakagePrefixes:
    def test_leakage_prefixes_not_empty(self):
        assert len(FORBIDDEN_LEAKAGE_PREFIXES) > 0

    def test_future_prefix_present(self):
        assert "future_" in FORBIDDEN_LEAKAGE_PREFIXES

    def test_final_prefix_present(self):
        assert "final_" in FORBIDDEN_LEAKAGE_PREFIXES


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestP33RequiredJoinedInputSpec:
    def test_instantiation(self):
        spec = P33RequiredJoinedInputSpec()
        assert spec.season == 2024
        assert spec.paper_only is True
        assert spec.production_ready is False
        assert len(spec.required_fields) == len(REQUIRED_JOINED_INPUT_FIELDS)

    def test_is_frozen(self):
        spec = P33RequiredJoinedInputSpec()
        with pytest.raises((AttributeError, TypeError)):
            spec.season = 2025  # type: ignore[misc]

    def test_required_fields_match_constant(self):
        spec = P33RequiredJoinedInputSpec()
        assert set(spec.required_fields) == set(REQUIRED_JOINED_INPUT_FIELDS)


class TestP33PredictionSourceCandidate:
    def test_instantiation(self):
        c = P33PredictionSourceCandidate(
            candidate_id="pred_001",
            file_path="/tmp/pred.csv",
            detected_season=2024,
            has_game_id_column=True,
            has_p_model_column=True,
            has_p_oof_column=False,
            detected_columns=("game_id", "p_model"),
            row_count=100,
            status=SOURCE_PARTIAL,
            blocker_reason="",
            is_dry_run=False,
            is_paper_only=True,
            year_verified=True,
        )
        assert c.candidate_id == "pred_001"
        assert c.status == SOURCE_PARTIAL
        assert c.is_paper_only is True

    def test_is_frozen(self):
        c = P33PredictionSourceCandidate(
            candidate_id="pred_001",
            file_path="/tmp/pred.csv",
            detected_season=2024,
            has_game_id_column=True,
            has_p_model_column=True,
            has_p_oof_column=False,
            detected_columns=("game_id", "p_model"),
            row_count=100,
            status=SOURCE_PARTIAL,
            blocker_reason="",
            is_dry_run=False,
            is_paper_only=True,
            year_verified=True,
        )
        with pytest.raises((AttributeError, TypeError)):
            c.status = SOURCE_READY  # type: ignore[misc]


class TestP33OddsSourceCandidate:
    def test_instantiation(self):
        c = P33OddsSourceCandidate(
            candidate_id="odds_001",
            file_path="/tmp/odds.csv",
            detected_season=2024,
            has_game_id_column=True,
            has_moneyline_column=True,
            has_closing_odds_column=False,
            detected_columns=("game_id", "home_ml", "away_ml"),
            row_count=200,
            status=SOURCE_PARTIAL,
            blocker_reason="",
            sportsbook_reference="Pinnacle",
            year_verified=True,
        )
        assert c.candidate_id == "odds_001"
        assert c.year_verified is True

    def test_is_frozen(self):
        c = P33OddsSourceCandidate(
            candidate_id="odds_001",
            file_path="/tmp/odds.csv",
            detected_season=None,
            has_game_id_column=False,
            has_moneyline_column=False,
            has_closing_odds_column=False,
            detected_columns=(),
            row_count=0,
            status=SOURCE_MISSING,
            blocker_reason="",
            sportsbook_reference="UNKNOWN",
            year_verified=False,
        )
        with pytest.raises((AttributeError, TypeError)):
            c.status = SOURCE_READY  # type: ignore[misc]


class TestP33SourceGapSummary:
    def test_default_instantiation(self):
        summary = P33SourceGapSummary()
        assert summary.season == 2024
        assert summary.paper_only is True
        assert summary.production_ready is False
        assert summary.prediction_missing is True
        assert summary.odds_missing is True
        assert summary.prediction_candidates == []
        assert summary.odds_candidates == []

    def test_mutable(self):
        summary = P33SourceGapSummary()
        summary.prediction_missing = False
        assert summary.prediction_missing is False


class TestP33GateResult:
    def test_default_instantiation(self):
        result = P33GateResult(gate=P33_PREDICTION_ODDS_GAP_PLAN_READY)
        assert result.season == 2024
        assert result.paper_only is True
        assert result.production_ready is False
        assert result.artifacts == []
        assert result.next_phase == "P34_DUAL_SOURCE_ACQUISITION_PLAN"

    def test_blocked_gate(self):
        result = P33GateResult(
            gate=P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
            prediction_gap_blocked=True,
            blocker_reason="No prediction files.",
        )
        assert result.gate == P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE
        assert result.prediction_gap_blocked is True

    def test_gate_must_be_valid_string(self):
        # Just verify it accepts any string (validation is caller's responsibility)
        result = P33GateResult(gate="CUSTOM_GATE")
        assert result.gate == "CUSTOM_GATE"
