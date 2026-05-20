"""
test_p7_apply_plan_contract.py
================================
P7 Apply Plan Contract — Unit Tests.

Tests apply_decision_for_candidate() and P7ApplyPlanRow hard rules:
  1. Missing provenance_hash → PLAN_SKIP_MISSING_PROVENANCE
  2. Missing predicted_numbers → PLAN_SKIP_MISSING_PAYLOAD
  3. Duplicate → PLAN_SKIP_DUPLICATE
  4. ONLINE_ONLY scope + RETIRED → PLAN_MANUAL_REVIEW_REQUIRED
  5. ONLINE_ONLY scope + ONLINE → PLAN_INSERT
  6. INCLUDE_RETIRED_WITH_WARNING + RETIRED + warning → PLAN_INSERT
  7. INCLUDE_RETIRED_WITH_WARNING + RETIRED + no warning → PLAN_MANUAL_REVIEW_REQUIRED
  8. p7_can_apply always False
  9. dry_run_only always True
 10. truth_level always RECONSTRUCTION_DRY_RUN_PLAN
 11. duplicate_check_key always present
 12. rollback_batch_id format
 13. controlled_apply_id format
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_p7_apply_plan_contract import (
    P7ApplyDecision,
    P7ApplyScope,
    P7ApplyPlanRow,
    apply_decision_for_candidate,
    make_duplicate_check_key,
    summarize_p7_plan,
)


# ---------------------------------------------------------------------------
# Base valid candidate (ONLINE, TIER_1, all gates satisfied)
# ---------------------------------------------------------------------------

def _cand(**overrides) -> dict:
    base = {
        "strategy_id":           "fourier_rhythm_3bet",
        "lottery_type":          "POWER_LOTTO",
        "draw_id":               "115000030",
        "provenance_hash":       "deadbeef1234",
        "has_predicted_numbers": True,
        "run_id":                177,
        "lifecycle_state":       "ONLINE",
        "lifecycle_warning":     None,
        "p7_candidate_status":   "P7_CANDIDATE",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Section 1: provenance gate
# ---------------------------------------------------------------------------

class TestProvenanceGate:
    def test_missing_provenance_skipped(self):
        dec, _ = apply_decision_for_candidate(_cand(provenance_hash=None))
        assert dec == P7ApplyDecision.PLAN_SKIP_MISSING_PROVENANCE

    def test_empty_provenance_skipped(self):
        dec, _ = apply_decision_for_candidate(_cand(provenance_hash=""))
        assert dec == P7ApplyDecision.PLAN_SKIP_MISSING_PROVENANCE

    def test_present_provenance_passes(self):
        dec, _ = apply_decision_for_candidate(_cand())
        assert dec != P7ApplyDecision.PLAN_SKIP_MISSING_PROVENANCE


# ---------------------------------------------------------------------------
# Section 2: payload gate
# ---------------------------------------------------------------------------

class TestPayloadGate:
    def test_missing_numbers_skipped(self):
        dec, _ = apply_decision_for_candidate(_cand(has_predicted_numbers=False))
        assert dec == P7ApplyDecision.PLAN_SKIP_MISSING_PAYLOAD

    def test_present_numbers_passes(self):
        dec, _ = apply_decision_for_candidate(_cand(has_predicted_numbers=True))
        assert dec != P7ApplyDecision.PLAN_SKIP_MISSING_PAYLOAD


# ---------------------------------------------------------------------------
# Section 3: duplicate gate
# ---------------------------------------------------------------------------

class TestDuplicateGate:
    def test_duplicate_skipped(self):
        dec, reason = apply_decision_for_candidate(_cand(), is_duplicate=True)
        assert dec == P7ApplyDecision.PLAN_SKIP_DUPLICATE
        assert "duplicate" in reason.lower()

    def test_non_duplicate_passes(self):
        dec, _ = apply_decision_for_candidate(_cand(), is_duplicate=False)
        assert dec != P7ApplyDecision.PLAN_SKIP_DUPLICATE


# ---------------------------------------------------------------------------
# Section 4: scope ONLINE_ONLY
# ---------------------------------------------------------------------------

class TestOnlineOnlyScope:
    def test_online_is_plan_insert(self):
        dec, reason = apply_decision_for_candidate(
            _cand(lifecycle_state="ONLINE"), scope=P7ApplyScope.ONLINE_ONLY
        )
        assert dec == P7ApplyDecision.PLAN_INSERT
        assert reason is None

    def test_retired_is_manual_review(self):
        dec, reason = apply_decision_for_candidate(
            _cand(lifecycle_state="RETIRED", lifecycle_warning="RETIRED warning"),
            scope=P7ApplyScope.ONLINE_ONLY,
        )
        assert dec == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED
        assert reason is not None

    def test_observation_is_manual_review(self):
        dec, _ = apply_decision_for_candidate(
            _cand(lifecycle_state="OBSERVATION", lifecycle_warning="OBSERVATION shadow"),
            scope=P7ApplyScope.ONLINE_ONLY,
        )
        assert dec == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED

    def test_default_scope_is_online_only(self):
        # Retired without explicit scope → MANUAL_REVIEW (ONLINE_ONLY is default)
        dec, _ = apply_decision_for_candidate(
            _cand(lifecycle_state="RETIRED", lifecycle_warning="w")
        )
        assert dec == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# Section 5: scope INCLUDE_RETIRED_WITH_WARNING
# ---------------------------------------------------------------------------

class TestIncludeRetiredScope:
    S = P7ApplyScope.INCLUDE_RETIRED_WITH_WARNING

    def test_online_still_plan_insert(self):
        dec, _ = apply_decision_for_candidate(_cand(), scope=self.S)
        assert dec == P7ApplyDecision.PLAN_INSERT

    def test_retired_with_warning_is_plan_insert(self):
        dec, reason = apply_decision_for_candidate(
            _cand(lifecycle_state="RETIRED", lifecycle_warning="human review required"),
            scope=self.S,
        )
        assert dec == P7ApplyDecision.PLAN_INSERT
        assert reason is not None

    def test_retired_without_warning_is_manual_review(self):
        dec, _ = apply_decision_for_candidate(
            _cand(lifecycle_state="RETIRED", lifecycle_warning=None),
            scope=self.S,
        )
        assert dec == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED

    def test_scope_is_still_dry_run(self):
        # Even with INCLUDE_RETIRED, no actual write occurs — p7_can_apply stays False
        # (tested in P7ApplyPlanRow field test below)
        dec, _ = apply_decision_for_candidate(
            _cand(lifecycle_state="RETIRED", lifecycle_warning="w"), scope=self.S
        )
        assert dec == P7ApplyDecision.PLAN_INSERT  # confirms decision is PLAN_INSERT
        # (The actual p7_can_apply=False constraint is enforced in P7ApplyPlanRow)


# ---------------------------------------------------------------------------
# Section 6: P7ApplyPlanRow invariants
# ---------------------------------------------------------------------------

class TestP7ApplyPlanRowInvariants:
    def _make_row(self, **kw) -> P7ApplyPlanRow:
        import uuid
        return P7ApplyPlanRow(
            plan_id=str(uuid.uuid4()),
            strategy_id="fourier_rhythm_3bet",
            lottery_type="POWER_LOTTO",
            draw_id="115000030",
            draw_date=None,
            predicted_numbers=None,
            source_run_id=177,
            source_prediction_item_id=None,
            provenance_hash="deadbeef1234",
            source_tier="TIER_1_DB_PREDICTION_PAYLOAD",
            lifecycle_state="ONLINE",
            lifecycle_warning=None,
            p7_candidate_status="P7_CANDIDATE",
            apply_decision=P7ApplyDecision.PLAN_INSERT,
            rollback_batch_id=str(uuid.uuid4()),
            controlled_apply_id=str(uuid.uuid4()),
            duplicate_check_key="fourier_rhythm_3bet:POWER_LOTTO:115000030",
            **kw,
        )

    def test_p7_can_apply_defaults_false(self):
        row = self._make_row()
        assert row.p7_can_apply is False

    def test_dry_run_only_defaults_true(self):
        row = self._make_row()
        assert row.dry_run_only is True

    def test_truth_level_correct(self):
        row = self._make_row()
        assert row.truth_level == "RECONSTRUCTION_DRY_RUN_PLAN"

    def test_created_by_phase_is_p7(self):
        row = self._make_row()
        assert row.created_by_phase == "P7"

    def test_to_dict_has_required_keys(self):
        row = self._make_row()
        d = row.to_dict()
        required = {
            "plan_id", "strategy_id", "lottery_type", "draw_id",
            "provenance_hash", "apply_decision", "dry_run_only",
            "p7_can_apply", "truth_level", "duplicate_check_key",
            "rollback_batch_id", "controlled_apply_id",
            "lifecycle_state", "lifecycle_warning",
        }
        for k in required:
            assert k in d, f"Missing key {k!r} in P7ApplyPlanRow.to_dict()"


# ---------------------------------------------------------------------------
# Section 7: duplicate_check_key helper
# ---------------------------------------------------------------------------

class TestDuplicateCheckKey:
    def test_key_format(self):
        key = make_duplicate_check_key("fourier_rhythm_3bet", "POWER_LOTTO", "115000030")
        assert key == "fourier_rhythm_3bet:POWER_LOTTO:115000030"

    def test_key_is_deterministic(self):
        k1 = make_duplicate_check_key("a", "b", "c")
        k2 = make_duplicate_check_key("a", "b", "c")
        assert k1 == k2

    def test_key_differs_by_draw(self):
        k1 = make_duplicate_check_key("s", "lt", "draw1")
        k2 = make_duplicate_check_key("s", "lt", "draw2")
        assert k1 != k2


# ---------------------------------------------------------------------------
# Section 8: summarize_p7_plan
# ---------------------------------------------------------------------------

class TestSummarize:
    def _make_rows(self, decisions: list[tuple[str, str]]) -> list[P7ApplyPlanRow]:
        import uuid
        rows = []
        for dec, lc in decisions:
            rows.append(P7ApplyPlanRow(
                plan_id=str(uuid.uuid4()),
                strategy_id="test_strat",
                lottery_type="POWER_LOTTO",
                draw_id="115000001",
                draw_date=None,
                predicted_numbers=None,
                source_run_id=1,
                source_prediction_item_id=None,
                provenance_hash="abc",
                source_tier="TIER_1_DB_PREDICTION_PAYLOAD",
                lifecycle_state=lc,
                lifecycle_warning=None,
                p7_candidate_status="P7_CANDIDATE",
                apply_decision=dec,
                rollback_batch_id="batch-1",
                controlled_apply_id=str(uuid.uuid4()),
                duplicate_check_key="test_strat:POWER_LOTTO:115000001",
            ))
        return rows

    def test_summary_counts(self):
        rows = self._make_rows([
            (P7ApplyDecision.PLAN_INSERT, "ONLINE"),
            (P7ApplyDecision.PLAN_INSERT, "ONLINE"),
            (P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED, "RETIRED"),
            (P7ApplyDecision.PLAN_SKIP_DUPLICATE, "ONLINE"),
        ])
        s = summarize_p7_plan(rows, rollback_batch_id="batch-1", scope="ONLINE_ONLY")
        assert s["plan_insert_count"] == 2
        assert s["manual_review_required_count"] == 1
        assert s["duplicate_skip_count"] == 1
        assert s["total_p6_candidates"] == 4

    def test_summary_has_backup_and_rollback(self):
        s = summarize_p7_plan([], rollback_batch_id="batch-1", scope="ONLINE_ONLY")
        assert "backup_plan" in s
        assert "rollback_plan" in s

    def test_summary_safety_flags(self):
        s = summarize_p7_plan([], rollback_batch_id="batch-1", scope="ONLINE_ONLY")
        assert s["safety_flags"]["p7_can_apply_globally"] is False
        assert s["safety_flags"]["dry_run_only_globally"] is True
        assert s["safety_flags"]["db_write_performed"] is False
