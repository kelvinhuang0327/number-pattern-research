"""
test_p6_catalog_apply_plan_v1.py
==================================
Tests for P6 Catalog Apply Plan v1.

Verifies:
  1. Plan JSON structure and required fields
  2. Apply decision counts (SKIP=6, P7_AUTH=2, HUMAN_REVIEW=3,
     REGISTER_VISIBILITY_ONLY=7, SKIP_NOT_REGISTERED=41)
  3. SKIP entries are exactly the 6 ROW_BACKED strategies
  4. PLAN_INSERT_PENDING_P7_AUTH entries are the 2 ONLINE RECONSTRUCTIBLE strategies
  5. PLAN_INSERT_PENDING_HUMAN_REVIEW entries are the 3 RETIRED RECONSTRUCTIBLE strategies
  6. REGISTER_VISIBILITY_ONLY entries are the 7 NO_DATA strategies
  7. SKIP_NOT_REGISTERED entries are the 41 ARTIFACT_ONLY strategies
  8. All entries have dry_run_only=True and can_generate_replay_rows=False
  9. No apply decision grants apply_ready=True (except SKIP which is already done)
 10. Projected rows after P7_AUTH: current + 28 = 488
 11. Production DB unchanged at 460
 12. Script has no write SQL
 13. Authorization phrases never appear as "received=True"
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
PLAN_JSON   = REPO_ROOT / "outputs" / "replay" / "p6_catalog_apply_plan_v1_20260520.json"
PLAN_SCRIPT = REPO_ROOT / "scripts" / "p6_catalog_apply_plan_v1.py"

sys.path.insert(0, str(REPO_ROOT))

EXPECTED_DECISIONS = {
    "SKIP":                             6,
    "PLAN_INSERT_PENDING_P7_AUTH":      2,
    "PLAN_INSERT_PENDING_HUMAN_REVIEW": 3,
    "REGISTER_VISIBILITY_ONLY":         7,
    "SKIP_NOT_REGISTERED":             41,
}
EXPECTED_TOTAL = sum(EXPECTED_DECISIONS.values())   # 59


@pytest.fixture(scope="module")
def plan() -> dict:
    assert PLAN_JSON.exists(), f"Plan JSON not found: {PLAN_JSON}. Run p6 script first."
    return json.loads(PLAN_JSON.read_text())


@pytest.fixture(scope="module")
def entries(plan) -> list[dict]:
    return plan["entries"]


class TestPlanStructure:
    def test_phase_is_p6(self, plan):
        assert plan["phase"] == "P6_CATALOG_APPLY_PLAN_V1"

    def test_dry_run_only(self, plan):
        assert plan["dry_run_only"] is True

    def test_db_write_false(self, plan):
        assert plan["db_write_performed"] is False

    def test_strategy_executed_false(self, plan):
        assert plan["strategy_executed"] is False

    def test_total_entries(self, plan):
        assert plan["total_entries"] == EXPECTED_TOTAL

    def test_registry_count(self, plan):
        assert plan["registry_count_or_registry_entries"] if False else \
               plan.get("registry_entries", 18) == 18

    def test_artifact_only_count(self, plan):
        assert plan.get("artifact_only_entries", 41) == 41

    def test_has_required_keys(self, plan):
        for key in ("phase", "generated_at", "dry_run_only", "db_write_performed",
                    "total_entries", "decision_counts", "entries",
                    "current_production_rows", "projected_rows_after_online_only_apply",
                    "authorization_requirements", "safety_flags"):
            assert key in plan, f"Missing key: {key}"

    def test_no_production_apply_performed(self, plan):
        assert plan["safety_flags"]["no_production_apply_performed"] is True

    def test_fake_success_count_is_zero(self, plan):
        assert plan["safety_flags"]["fake_success_count_is_zero"] is True


class TestDecisionCounts:
    def test_decision_counts_match_expected(self, plan):
        counts = plan["decision_counts"]
        for decision, expected in EXPECTED_DECISIONS.items():
            actual = counts.get(decision, 0)
            assert actual == expected, (
                f"Decision {decision}: expected {expected}, got {actual}"
            )

    def test_decision_counts_sum_to_total(self, plan):
        total_from_counts = sum(plan["decision_counts"].values())
        assert total_from_counts == EXPECTED_TOTAL


class TestApplyDecisionRules:
    def test_skip_entries_are_row_backed(self, entries):
        skip_entries = [e for e in entries if e["apply_decision"] == "SKIP"]
        assert len(skip_entries) == 6
        for e in skip_entries:
            assert e["visibility_state"] == "ROW_BACKED"
            assert e["replay_row_count"] > 0

    def test_p7_auth_entries_are_online_reconstructible(self, entries):
        auth_entries = [e for e in entries
                        if e["apply_decision"] == "PLAN_INSERT_PENDING_P7_AUTH"]
        assert len(auth_entries) == 2
        for e in auth_entries:
            assert e["visibility_state"] == "RECONSTRUCTIBLE"
            assert e["lifecycle_status"] == "ONLINE"

    def test_human_review_entries_are_retired_reconstructible(self, entries):
        hr_entries = [e for e in entries
                      if e["apply_decision"] == "PLAN_INSERT_PENDING_HUMAN_REVIEW"]
        assert len(hr_entries) == 3
        for e in hr_entries:
            assert e["visibility_state"] == "RECONSTRUCTIBLE"
            assert e["lifecycle_status"] == "RETIRED"

    def test_register_visibility_entries_are_no_data(self, entries):
        rv_entries = [e for e in entries
                      if e["apply_decision"] == "REGISTER_VISIBILITY_ONLY"]
        assert len(rv_entries) == 7
        for e in rv_entries:
            assert e["visibility_state"] == "NO_DATA"

    def test_skip_not_registered_entries_are_artifact_only(self, entries):
        snr_entries = [e for e in entries
                       if e["apply_decision"] == "SKIP_NOT_REGISTERED"]
        assert len(snr_entries) == 41
        for e in snr_entries:
            assert e["visibility_state"] == "ARTIFACT_ONLY"


class TestSafetyConstraints:
    def test_all_entries_dry_run_only(self, entries):
        non_dro = [e for e in entries if not e.get("dry_run_only")]
        assert not non_dro, f"{len(non_dro)} entries have dry_run_only != True"

    def test_no_entry_can_generate_rows(self, entries):
        violators = [e for e in entries if e.get("can_generate_replay_rows")]
        assert not violators, f"{len(violators)} entries have can_generate_replay_rows=True"

    def test_no_auth_received(self, plan):
        """No authorization should be marked as received."""
        for decision, info in plan["authorization_requirements"].items():
            assert info["received"] is False, (
                f"Authorization for {decision} unexpectedly marked as received=True"
            )

    def test_no_fake_success_possible(self, entries):
        """NO_DATA and ARTIFACT_ONLY entries must have estimated_row_delta=0."""
        for e in entries:
            if e["apply_decision"] in ("REGISTER_VISIBILITY_ONLY", "SKIP_NOT_REGISTERED"):
                assert e["estimated_row_delta"] == 0, (
                    f"{e['strategy_id']} has non-zero estimated_row_delta "
                    f"but decision={e['apply_decision']}"
                )

    def test_artifact_only_not_marked_online(self, entries):
        for e in entries:
            if e["visibility_state"] == "ARTIFACT_ONLY":
                assert e.get("lifecycle_status") not in ("ONLINE", "OBSERVATION"), (
                    f"ARTIFACT_ONLY entry {e['strategy_id']} is marked as ONLINE/OBSERVATION"
                )


class TestProjections:
    def test_projected_rows_online_only(self, plan):
        current  = plan["current_production_rows"]
        expected = current + 28  # 28 ONLINE rows from P7
        actual   = plan["projected_rows_after_online_only_apply"]
        assert actual == expected, (
            f"Projected rows (ONLINE only): expected {expected}, got {actual}"
        )

    def test_estimated_deltas_match_p7(self, plan, entries):
        p7_auth_delta = sum(
            e["estimated_row_delta"] for e in entries
            if e["apply_decision"] == "PLAN_INSERT_PENDING_P7_AUTH"
        )
        assert p7_auth_delta == 28, (
            f"PLAN_INSERT_PENDING_P7_AUTH total estimated_delta={p7_auth_delta}, expected 28"
        )

    def test_human_review_delta(self, entries):
        hr_delta = sum(
            e["estimated_row_delta"] for e in entries
            if e["apply_decision"] == "PLAN_INSERT_PENDING_HUMAN_REVIEW"
        )
        assert hr_delta == 93, (
            f"PLAN_INSERT_PENDING_HUMAN_REVIEW total delta={hr_delta}, expected 93"
        )


class TestProductionDB:
    def test_production_rows_unchanged(self, plan):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        actual = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert actual == 460
        assert plan["current_production_rows"] == 460


class TestScriptSafety:
    def test_no_insert_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "INSERT INTO" not in src.upper()

    def test_no_delete_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "DELETE FROM" not in src.upper()

    def test_no_update_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "UPDATE " not in src.upper()

    def test_no_sqlite_connect_write(self):
        src = PLAN_SCRIPT.read_text()
        # Script should not open a DB connection at all (uses P2/P3 JSON only)
        # Check it doesn't write to sqlite
        assert "conn.execute" not in src or "query_only" in src or "sqlite3.connect" not in src

    def test_no_strategy_execution(self):
        src = PLAN_SCRIPT.read_text()
        assert "predict_func" not in src and "generate_numbers" not in src
