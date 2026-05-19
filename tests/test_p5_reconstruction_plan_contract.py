"""
tests/test_p5_reconstruction_plan_contract.py
==============================================
P5 Reconstruction Plan Contract tests.

Verifies:
  1. can_apply() always False
  2. dry_run_only always True
  3. truth_level always RECONSTRUCTION_PLAN_ONLY
  4. Only RECONSTRUCTIBLE entries produce plan rows
  5. ARTIFACT_CANDIDATE cannot produce PLAN_INSERT_REPLAY_ROW
  6. NO_DATA cannot produce plan rows
  7. PLAN_INSERT_REPLAY_ROW requires provenance_hash
  8. PLAN_INSERT_REPLAY_ROW requires predicted_numbers
  9. PlannedAction enum is exhaustive
 10. validate_plan_row catches violations
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_reconstruction_plan_contract import (
    ReconstructionPlanRow,
    PlannedAction,
    TrustLevel,
    TruthLevel,
    validate_plan_row,
)


# ---------------------------------------------------------------------------
# Fixtures: valid minimal plan rows
# ---------------------------------------------------------------------------

def _make_plannable_row(**overrides) -> ReconstructionPlanRow:
    defaults = dict(
        plan_id="P5|acb_markov_midfreq_3bet|115000080",
        strategy_id="acb_markov_midfreq_3bet",
        lottery_type="DAILY_539",
        draw_id="115000080",
        draw_date="2026/04/01",
        catalog_visibility_state="RECONSTRUCTIBLE",
        coverage_status_before="RECONSTRUCTIBLE_PENDING",
        planned_action=PlannedAction.PLAN_INSERT_REPLAY_ROW,
        provenance_hash="abc123def456",
        provenance_source="DB:prediction_items[run_id=180]",
        reconstruction_reason="Has payload from prediction_items",
        trust_level=TrustLevel.ARTIFACT_DERIVED,
        predicted_numbers=[[4, 7, 20, 27, 35], [9, 18, 23, 29, 30]],
        item_count=2,
        run_id=180,
        artifact_source_type="PREDICTION_LOG",
    )
    defaults.update(overrides)
    return ReconstructionPlanRow(**defaults)


def _make_skip_row(action: str = PlannedAction.SKIP_SOURCE_MISSING, **overrides) -> ReconstructionPlanRow:
    defaults = dict(
        plan_id="P5|p1_deviation_2bet_539|115000080",
        strategy_id="p1_deviation_2bet_539",
        lottery_type="DAILY_539",
        draw_id="115000080",
        draw_date="2026/04/01",
        catalog_visibility_state="RECONSTRUCTIBLE",
        coverage_status_before="RECONSTRUCTIBLE_PENDING",
        planned_action=action,
        skip_reason="no payload",
        artifact_source_type="REJECTED_JSON",
    )
    defaults.update(overrides)
    return ReconstructionPlanRow(**defaults)


# ---------------------------------------------------------------------------
# Section 1: Core invariants
# ---------------------------------------------------------------------------

class TestCoreInvariants:
    def test_can_apply_always_false_plannable(self):
        row = _make_plannable_row()
        assert row.can_apply() is False

    def test_can_apply_always_false_skip(self):
        row = _make_skip_row()
        assert row.can_apply() is False

    def test_dry_run_only_default_true(self):
        row = _make_plannable_row()
        assert row.dry_run_only is True

    def test_dry_run_only_cannot_be_false(self):
        row = _make_plannable_row(dry_run_only=False)
        errors = validate_plan_row(row)
        assert any("dry_run_only" in e for e in errors)

    def test_truth_level_always_reconstruction_plan_only(self):
        row = _make_plannable_row()
        assert row.truth_level == TruthLevel.RECONSTRUCTION_PLAN_ONLY

    def test_wrong_truth_level_fails_validation(self):
        row = _make_plannable_row(truth_level="REGENERATED")
        errors = validate_plan_row(row)
        assert any("truth_level" in e for e in errors)

    def test_created_by_phase_is_p5(self):
        row = _make_plannable_row()
        assert row.created_by_phase == "P5"

    def test_created_at_is_set(self):
        row = _make_plannable_row()
        assert row.created_at is not None and len(row.created_at) > 10


# ---------------------------------------------------------------------------
# Section 2: Visibility state restrictions
# ---------------------------------------------------------------------------

class TestVisibilityStateRestrictions:
    def test_only_reconstructible_produces_plan_row(self):
        row = _make_plannable_row(catalog_visibility_state="RECONSTRUCTIBLE")
        errors = validate_plan_row(row)
        assert not errors

    def test_artifact_candidate_cannot_be_plan_insert(self):
        row = _make_plannable_row(catalog_visibility_state="ARTIFACT_CANDIDATE")
        errors = validate_plan_row(row)
        assert any("RECONSTRUCTIBLE" in e for e in errors)

    def test_registered_no_data_cannot_be_plan_insert(self):
        row = _make_plannable_row(catalog_visibility_state="REGISTERED_NO_DATA")
        errors = validate_plan_row(row)
        assert errors  # must fail

    def test_registered_with_rows_gets_skip_already_covered(self):
        row = _make_skip_row(
            action=PlannedAction.SKIP_ALREADY_COVERED,
            catalog_visibility_state="RECONSTRUCTIBLE",
            skip_reason="already has replay row",
        )
        assert row.planned_action == PlannedAction.SKIP_ALREADY_COVERED
        errors = validate_plan_row(row)
        assert not errors


# ---------------------------------------------------------------------------
# Section 3: PLAN_INSERT_REPLAY_ROW requirements
# ---------------------------------------------------------------------------

class TestPlanInsertRequirements:
    def test_valid_plan_row_passes(self):
        row = _make_plannable_row()
        errors = validate_plan_row(row)
        assert not errors, f"Unexpected errors: {errors}"

    def test_plan_insert_requires_provenance_hash(self):
        row = _make_plannable_row(provenance_hash=None)
        errors = validate_plan_row(row)
        assert any("provenance_hash" in e for e in errors)

    def test_plan_insert_requires_predicted_numbers(self):
        row = _make_plannable_row(predicted_numbers=None)
        errors = validate_plan_row(row)
        assert any("predicted_numbers" in e for e in errors)

    def test_plan_insert_with_empty_provenance_hash_fails(self):
        row = _make_plannable_row(provenance_hash="")
        errors = validate_plan_row(row)
        assert any("provenance_hash" in e for e in errors)

    def test_skip_row_does_not_need_provenance(self):
        row = _make_skip_row(provenance_hash=None)
        errors = validate_plan_row(row)
        assert not errors

    def test_skip_row_does_not_need_predicted_numbers(self):
        row = _make_skip_row(predicted_numbers=None)
        errors = validate_plan_row(row)
        assert not errors


# ---------------------------------------------------------------------------
# Section 4: PlannedAction completeness
# ---------------------------------------------------------------------------

class TestPlannedActionCompleteness:
    def test_all_planned_actions_defined(self):
        expected = {
            "PLAN_INSERT_REPLAY_ROW",
            "SKIP_SOURCE_MISSING",
            "SKIP_NO_HISTORICAL_PAYLOAD",
            "SKIP_PROVENANCE_MISSING",
            "SKIP_UNSAFE",
            "SKIP_ALREADY_COVERED",
            "SKIP_ARTIFACT_ONLY",
            "NEEDS_P6_POLICY",
        }
        assert set(PlannedAction._ALL) == expected

    @pytest.mark.parametrize("action", [
        PlannedAction.SKIP_SOURCE_MISSING,
        PlannedAction.SKIP_NO_HISTORICAL_PAYLOAD,
        PlannedAction.SKIP_PROVENANCE_MISSING,
        PlannedAction.SKIP_UNSAFE,
        PlannedAction.SKIP_ALREADY_COVERED,
        PlannedAction.SKIP_ARTIFACT_ONLY,
        PlannedAction.NEEDS_P6_POLICY,
    ])
    def test_all_skip_actions_are_skip(self, action):
        assert PlannedAction.is_skip(action) is True

    def test_plan_insert_is_not_skip(self):
        assert PlannedAction.is_skip(PlannedAction.PLAN_INSERT_REPLAY_ROW) is False


# ---------------------------------------------------------------------------
# Section 5: Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_has_required_fields(self):
        row = _make_plannable_row()
        d = row.to_dict()
        required = [
            "plan_id", "strategy_id", "lottery_type", "draw_id",
            "catalog_visibility_state", "coverage_status_before",
            "planned_action", "dry_run_only", "can_apply",
            "truth_level", "trust_level", "provenance_hash",
            "predicted_numbers", "created_by_phase", "created_at",
        ]
        for f in required:
            assert f in d, f"Missing field: {f!r}"

    def test_can_apply_serialized_false(self):
        row = _make_plannable_row()
        assert row.to_dict()["can_apply"] is False

    def test_dry_run_only_serialized_true(self):
        row = _make_plannable_row()
        assert row.to_dict()["dry_run_only"] is True
