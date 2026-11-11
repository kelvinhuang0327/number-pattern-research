"""Tests for p34_dual_source_acquisition_contract.py"""

from __future__ import annotations

import pytest

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    ALL_OPTION_STATUSES,
    ALL_P34_GATES,
    LEAKAGE_CONFIRMED,
    LEAKAGE_HIGH,
    LEAKAGE_LOW,
    LEAKAGE_MEDIUM,
    LEAKAGE_NONE,
    ODDS_TEMPLATE_COLUMNS,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_BLOCKED_SCHEMA_GAP,
    OPTION_READY_FOR_IMPLEMENTATION_PLAN,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    P34_BLOCKED_CONTRACT_VIOLATION,
    P34_BLOCKED_LICENSE_PROVENANCE_UNSAFE,
    P34_BLOCKED_NO_SAFE_ODDS_PATH,
    P34_BLOCKED_NO_SAFE_PREDICTION_PATH,
    P34_DUAL_SOURCE_ACQUISITION_PLAN_READY,
    P34_FAIL_INPUT_MISSING,
    P34_FAIL_NON_DETERMINISTIC,
    PAPER_ONLY,
    PREDICTION_TEMPLATE_COLUMNS,
    PRODUCTION_READY,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    P34DualSourcePlan,
    P34GateResult,
    P34OddsAcquisitionOption,
    P34PredictionAcquisitionOption,
    P34SchemaRequirement,
)


class TestGuardConstants:
    def test_paper_only_is_true(self):
        assert PAPER_ONLY is True

    def test_production_ready_is_false(self):
        assert PRODUCTION_READY is False

    def test_paper_only_cannot_be_reassigned(self):
        """PAPER_ONLY is a module-level constant (immutable by convention)."""
        assert PAPER_ONLY is True
        assert not PRODUCTION_READY


class TestGateConstants:
    def test_all_gates_present(self):
        assert P34_DUAL_SOURCE_ACQUISITION_PLAN_READY in ALL_P34_GATES
        assert P34_BLOCKED_NO_SAFE_PREDICTION_PATH in ALL_P34_GATES
        assert P34_BLOCKED_NO_SAFE_ODDS_PATH in ALL_P34_GATES
        assert P34_BLOCKED_LICENSE_PROVENANCE_UNSAFE in ALL_P34_GATES
        assert P34_BLOCKED_CONTRACT_VIOLATION in ALL_P34_GATES
        assert P34_FAIL_INPUT_MISSING in ALL_P34_GATES
        assert P34_FAIL_NON_DETERMINISTIC in ALL_P34_GATES

    def test_all_gates_count(self):
        assert len(ALL_P34_GATES) == 7

    def test_ready_gate_name(self):
        assert P34_DUAL_SOURCE_ACQUISITION_PLAN_READY == "P34_DUAL_SOURCE_ACQUISITION_PLAN_READY"

    def test_blocked_gates_start_with_p34_blocked(self):
        blocked_gates = [g for g in ALL_P34_GATES if "BLOCKED" in g]
        assert all(g.startswith("P34_BLOCKED") for g in blocked_gates)


class TestOptionStatusConstants:
    def test_all_statuses_present(self):
        expected = {
            OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            OPTION_REQUIRES_MANUAL_APPROVAL,
            OPTION_REQUIRES_LICENSE_REVIEW,
            OPTION_BLOCKED_PROVENANCE,
            OPTION_BLOCKED_SCHEMA_GAP,
            OPTION_REJECTED_FAKE_OR_LEAKAGE,
        }
        assert set(ALL_OPTION_STATUSES) == expected

    def test_count(self):
        assert len(ALL_OPTION_STATUSES) == 6


class TestLeakageAndRiskConstants:
    def test_leakage_constants(self):
        assert LEAKAGE_NONE == "none"
        assert LEAKAGE_LOW == "low"
        assert LEAKAGE_MEDIUM == "medium"
        assert LEAKAGE_HIGH == "high"
        assert LEAKAGE_CONFIRMED == "confirmed"

    def test_risk_constants(self):
        assert RISK_LOW == "low"
        assert RISK_MEDIUM == "medium"
        assert RISK_HIGH == "high"


class TestTemplateColumns:
    def test_prediction_columns(self):
        assert "game_id" in PREDICTION_TEMPLATE_COLUMNS
        assert "p_oof" in PREDICTION_TEMPLATE_COLUMNS
        assert "generated_without_y_true" in PREDICTION_TEMPLATE_COLUMNS
        assert "source_prediction_ref" in PREDICTION_TEMPLATE_COLUMNS
        assert len(PREDICTION_TEMPLATE_COLUMNS) == 9

    def test_odds_columns(self):
        assert "game_id" in ODDS_TEMPLATE_COLUMNS
        assert "p_market" in ODDS_TEMPLATE_COLUMNS
        assert "odds_decimal" in ODDS_TEMPLATE_COLUMNS
        assert "license_ref" in ODDS_TEMPLATE_COLUMNS
        assert "source_odds_ref" in ODDS_TEMPLATE_COLUMNS
        assert len(ODDS_TEMPLATE_COLUMNS) == 11

    def test_prediction_columns_are_tuple(self):
        assert isinstance(PREDICTION_TEMPLATE_COLUMNS, tuple)

    def test_odds_columns_are_tuple(self):
        assert isinstance(ODDS_TEMPLATE_COLUMNS, tuple)


class TestP34PredictionAcquisitionOption:
    def _make_option(self, **kwargs) -> P34PredictionAcquisitionOption:
        defaults = dict(
            option_id="pred_test",
            source_name="Test source",
            source_type="oof_rebuild",
            acquisition_method="test",
            expected_columns=PREDICTION_TEMPLATE_COLUMNS,
            missing_columns=(),
            provenance_status="ok",
            license_status="internal",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_MEDIUM,
            estimated_coverage=0.9,
        )
        defaults.update(kwargs)
        return P34PredictionAcquisitionOption(**defaults)

    def test_default_paper_only_true(self):
        opt = self._make_option()
        assert opt.paper_only is True

    def test_default_production_ready_false(self):
        opt = self._make_option()
        assert opt.production_ready is False

    def test_rejects_production_ready_true(self):
        """Frozen dataclass does not allow post-init modification."""
        opt = self._make_option(production_ready=False)
        with pytest.raises(Exception):
            opt.production_ready = True  # type: ignore

    def test_rejects_paper_only_false(self):
        opt = self._make_option(paper_only=True)
        with pytest.raises(Exception):
            opt.paper_only = False  # type: ignore

    def test_option_is_frozen(self):
        opt = self._make_option()
        with pytest.raises(Exception):
            opt.status = "something_else"  # type: ignore

    def test_estimated_coverage_range(self):
        opt = self._make_option(estimated_coverage=0.95)
        assert 0.0 <= opt.estimated_coverage <= 1.0


class TestP34OddsAcquisitionOption:
    def _make_option(self, **kwargs) -> P34OddsAcquisitionOption:
        defaults = dict(
            option_id="odds_test",
            source_name="Test odds",
            source_type="licensed_export",
            acquisition_method="manual_download",
            expected_columns=ODDS_TEMPLATE_COLUMNS,
            missing_columns=(),
            provenance_status="external_archive",
            license_status="review_required",
            leakage_risk=LEAKAGE_NONE,
            implementation_risk=RISK_LOW,
            estimated_coverage=0.90,
        )
        defaults.update(kwargs)
        return P34OddsAcquisitionOption(**defaults)

    def test_default_paper_only_true(self):
        opt = self._make_option()
        assert opt.paper_only is True

    def test_default_production_ready_false(self):
        opt = self._make_option()
        assert opt.production_ready is False

    def test_frozen(self):
        opt = self._make_option()
        with pytest.raises(Exception):
            opt.option_id = "new_id"  # type: ignore


class TestP34DualSourcePlan:
    def test_default_flags(self):
        plan = P34DualSourcePlan()
        assert plan.paper_only is True
        assert plan.production_ready is False
        assert plan.season == 2024

    def test_not_frozen(self):
        """P34DualSourcePlan is mutable."""
        plan = P34DualSourcePlan()
        plan.best_prediction_option_id = "pred_r01"
        assert plan.best_prediction_option_id == "pred_r01"


class TestP34SchemaRequirement:
    def test_all_columns(self):
        schema = P34SchemaRequirement(
            season=2024,
            prediction_columns=PREDICTION_TEMPLATE_COLUMNS,
            odds_columns=ODDS_TEMPLATE_COLUMNS,
        )
        all_cols = schema.all_columns()
        assert len(all_cols) == len(PREDICTION_TEMPLATE_COLUMNS) + len(ODDS_TEMPLATE_COLUMNS)

    def test_default_flags(self):
        schema = P34SchemaRequirement(
            season=2024,
            prediction_columns=(),
            odds_columns=(),
        )
        assert schema.paper_only is True
        assert schema.production_ready is False

    def test_frozen(self):
        schema = P34SchemaRequirement(
            season=2024,
            prediction_columns=PREDICTION_TEMPLATE_COLUMNS,
            odds_columns=ODDS_TEMPLATE_COLUMNS,
        )
        with pytest.raises(Exception):
            schema.season = 2025  # type: ignore


class TestP34GateResult:
    def test_default_gate(self):
        gate = P34GateResult()
        assert gate.gate == P34_DUAL_SOURCE_ACQUISITION_PLAN_READY

    def test_default_flags(self):
        gate = P34GateResult()
        assert gate.paper_only is True
        assert gate.production_ready is False
        assert gate.season == 2024
        assert gate.next_phase == "P35_DUAL_SOURCE_IMPORT_VALIDATION"

    def test_mutable(self):
        gate = P34GateResult()
        gate.gate = P34_BLOCKED_NO_SAFE_ODDS_PATH
        assert gate.gate == P34_BLOCKED_NO_SAFE_ODDS_PATH
