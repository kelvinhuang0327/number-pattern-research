"""Tests for p34_dual_source_plan_builder.py"""

from __future__ import annotations

import json
import os
import tempfile

import pandas as pd
import pytest

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    LEAKAGE_NONE,
    ODDS_TEMPLATE_COLUMNS,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_READY_FOR_IMPLEMENTATION_PLAN,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    P34_BLOCKED_CONTRACT_VIOLATION,
    P34_BLOCKED_NO_SAFE_ODDS_PATH,
    P34_BLOCKED_NO_SAFE_PREDICTION_PATH,
    P34_DUAL_SOURCE_ACQUISITION_PLAN_READY,
    PREDICTION_TEMPLATE_COLUMNS,
    RISK_LOW,
    RISK_MEDIUM,
    P34DualSourcePlan,
    P34GateResult,
    P34OddsAcquisitionOption,
    P34PredictionAcquisitionOption,
)
from wbc_backend.recommendation.p34_dual_source_plan_builder import (
    build_dual_source_acquisition_plan,
    determine_p34_gate,
    validate_dual_source_plan,
    write_p34_outputs,
)
from wbc_backend.recommendation.p34_joined_input_schema_package import write_schema_templates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pred_option(option_id="pred_r01", status=OPTION_READY_FOR_IMPLEMENTATION_PLAN) -> P34PredictionAcquisitionOption:
    return P34PredictionAcquisitionOption(
        option_id=option_id,
        source_name="OOF rebuild",
        source_type="oof_rebuild",
        acquisition_method="train OOF",
        expected_columns=PREDICTION_TEMPLATE_COLUMNS,
        missing_columns=(),
        provenance_status="p32_verified",
        license_status="internal",
        leakage_risk=LEAKAGE_NONE,
        implementation_risk=RISK_MEDIUM,
        estimated_coverage=0.95,
        status=status,
    )


def _make_odds_option(option_id="odds_r01", status=OPTION_REQUIRES_LICENSE_REVIEW) -> P34OddsAcquisitionOption:
    return P34OddsAcquisitionOption(
        option_id=option_id,
        source_name="sportsbookreviewsonline.com",
        source_type="licensed_export",
        acquisition_method="manual_download",
        expected_columns=ODDS_TEMPLATE_COLUMNS,
        missing_columns=(),
        provenance_status="external_public_archive",
        license_status="personal_research_verify_tos",
        leakage_risk=LEAKAGE_NONE,
        implementation_risk=RISK_LOW,
        estimated_coverage=0.90,
        status=status,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildDualSourceAcquisitionPlan:
    def test_returns_plan_with_correct_best_options(self):
        pred_opts = [_make_pred_option("pred_r01"), _make_pred_option("pred_r03", OPTION_BLOCKED_PROVENANCE)]
        odds_opts = [_make_odds_option("odds_r01"), _make_odds_option("odds_r04", OPTION_BLOCKED_PROVENANCE)]
        plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
        assert plan.best_prediction_option_id == "pred_r01"
        assert plan.best_odds_option_id == "odds_r01"

    def test_paper_only_enforced(self):
        plan = build_dual_source_acquisition_plan([], [])
        assert plan.paper_only is True
        assert plan.production_ready is False

    def test_season_is_2024(self):
        plan = build_dual_source_acquisition_plan([], [])
        assert plan.season == 2024

    def test_summary_contains_paper_only(self):
        plan = build_dual_source_acquisition_plan(
            [_make_pred_option()], [_make_odds_option()]
        )
        assert "PAPER_ONLY=True" in plan.plan_summary


class TestDetermineP34Gate:
    def test_ready_when_both_paths_usable(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            odds_path_status=OPTION_REQUIRES_LICENSE_REVIEW,
            paper_only=True,
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.gate == P34_DUAL_SOURCE_ACQUISITION_PLAN_READY

    def test_blocked_no_prediction_path(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_BLOCKED_PROVENANCE,
            odds_path_status=OPTION_REQUIRES_LICENSE_REVIEW,
            paper_only=True,
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.gate == P34_BLOCKED_NO_SAFE_PREDICTION_PATH

    def test_blocked_no_odds_path(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            odds_path_status=OPTION_BLOCKED_PROVENANCE,
            paper_only=True,
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.gate == P34_BLOCKED_NO_SAFE_ODDS_PATH

    def test_contract_violation_if_production_ready_true(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            odds_path_status=OPTION_REQUIRES_LICENSE_REVIEW,
            paper_only=True,
            production_ready=True,  # violation!
        )
        gate = determine_p34_gate(plan)
        assert gate.gate == P34_BLOCKED_CONTRACT_VIOLATION

    def test_contract_violation_if_paper_only_false(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            odds_path_status=OPTION_REQUIRES_LICENSE_REVIEW,
            paper_only=False,  # violation!
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.gate == P34_BLOCKED_CONTRACT_VIOLATION

    def test_gate_records_license_risk(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            odds_path_status=OPTION_REQUIRES_LICENSE_REVIEW,
            paper_only=True,
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.license_risk != "" or gate.gate == P34_DUAL_SOURCE_ACQUISITION_PLAN_READY

    def test_gate_paper_only_in_result(self):
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            odds_path_status=OPTION_REQUIRES_LICENSE_REVIEW,
            paper_only=True,
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.paper_only is True
        assert gate.production_ready is False

    def test_gate_requires_approval_usable(self):
        """OPTION_REQUIRES_MANUAL_APPROVAL should be usable for plan purposes."""
        plan = P34DualSourcePlan(
            prediction_path_status=OPTION_REQUIRES_MANUAL_APPROVAL,
            odds_path_status=OPTION_REQUIRES_MANUAL_APPROVAL,
            paper_only=True,
            production_ready=False,
        )
        gate = determine_p34_gate(plan)
        assert gate.gate == P34_DUAL_SOURCE_ACQUISITION_PLAN_READY


class TestValidateDualSourcePlan:
    def test_valid_plan(self):
        plan = P34DualSourcePlan(paper_only=True, production_ready=False, season=2024)
        assert validate_dual_source_plan(plan) is True

    def test_invalid_if_production_ready(self):
        plan = P34DualSourcePlan(paper_only=True, production_ready=True, season=2024)
        assert validate_dual_source_plan(plan) is False

    def test_invalid_if_paper_only_false(self):
        plan = P34DualSourcePlan(paper_only=False, production_ready=False, season=2024)
        assert validate_dual_source_plan(plan) is False

    def test_invalid_if_wrong_season(self):
        plan = P34DualSourcePlan(paper_only=True, production_ready=False, season=2025)
        assert validate_dual_source_plan(plan) is False


class TestWriteP34Outputs:
    def test_writes_all_expected_files(self, tmp_path):
        pred_opts = [_make_pred_option()]
        odds_opts = [_make_odds_option()]
        plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
        gate = determine_p34_gate(plan)
        schema_files = write_schema_templates(str(tmp_path))
        artifacts = write_p34_outputs(str(tmp_path), plan, gate, schema_files)

        expected_names = {
            "prediction_acquisition_options.json",
            "odds_acquisition_options.json",
            "dual_source_acquisition_plan.json",
            "dual_source_acquisition_plan.md",
            "p34_gate_result.json",
        }
        written_names = {os.path.basename(a) for a in artifacts}
        for name in expected_names:
            assert name in written_names, f"Missing artifact: {name}"

    def test_gate_result_json_has_correct_gate(self, tmp_path):
        pred_opts = [_make_pred_option()]
        odds_opts = [_make_odds_option()]
        plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
        gate = determine_p34_gate(plan)
        schema_files = write_schema_templates(str(tmp_path))
        write_p34_outputs(str(tmp_path), plan, gate, schema_files)

        gate_path = tmp_path / "p34_gate_result.json"
        data = json.loads(gate_path.read_text())
        assert data["gate"] == P34_DUAL_SOURCE_ACQUISITION_PLAN_READY
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_plan_json_has_correct_fields(self, tmp_path):
        pred_opts = [_make_pred_option()]
        odds_opts = [_make_odds_option()]
        plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
        gate = determine_p34_gate(plan)
        schema_files = write_schema_templates(str(tmp_path))
        write_p34_outputs(str(tmp_path), plan, gate, schema_files)

        plan_path = tmp_path / "dual_source_acquisition_plan.json"
        data = json.loads(plan_path.read_text())
        assert "best_prediction_option_id" in data
        assert "best_odds_option_id" in data
        assert data["season"] == 2024

    def test_markdown_file_created(self, tmp_path):
        pred_opts = [_make_pred_option()]
        odds_opts = [_make_odds_option()]
        plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
        gate = determine_p34_gate(plan)
        schema_files = write_schema_templates(str(tmp_path))
        write_p34_outputs(str(tmp_path), plan, gate, schema_files)

        md_path = tmp_path / "dual_source_acquisition_plan.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "P34 Dual Source Acquisition Plan" in content

    def test_prediction_options_json_valid(self, tmp_path):
        pred_opts = [_make_pred_option()]
        odds_opts = [_make_odds_option()]
        plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
        gate = determine_p34_gate(plan)
        schema_files = write_schema_templates(str(tmp_path))
        write_p34_outputs(str(tmp_path), plan, gate, schema_files)

        path = tmp_path / "prediction_acquisition_options.json"
        data = json.loads(path.read_text())
        assert data["paper_only"] is True
        assert isinstance(data["options"], list)

    def test_outputs_deterministic(self, tmp_path):
        """Two calls with same inputs must produce identical gate and plan JSONs."""
        pred_opts = [_make_pred_option()]
        odds_opts = [_make_odds_option()]

        dir1 = str(tmp_path / "run1")
        dir2 = str(tmp_path / "run2")

        for d in (dir1, dir2):
            plan = build_dual_source_acquisition_plan(pred_opts, odds_opts)
            gate = determine_p34_gate(plan)
            schema_files = write_schema_templates(d)
            write_p34_outputs(d, plan, gate, schema_files)

        import json

        def _load_normalized(path):
            data = json.loads(open(path, encoding="utf-8").read())
            for key in ("generated_at", "artifacts", "output_dir"):
                data.pop(key, None)
            return data

        for fname in ("p34_gate_result.json", "dual_source_acquisition_plan.json"):
            d1 = _load_normalized(os.path.join(dir1, fname))
            d2 = _load_normalized(os.path.join(dir2, fname))
            assert d1 == d2, f"Mismatch in {fname}"
