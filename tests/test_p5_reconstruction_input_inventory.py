"""
tests/test_p5_reconstruction_input_inventory.py
================================================
P5 Reconstruction Input Inventory tests.

Verifies:
  1. Inventory is read-only (DB rows = 460)
  2. Only RECONSTRUCTIBLE strategies are scanned
  3. Evidence classes are classified correctly
  4. SOURCE_AVAILABLE strategies have actual draw coverage
  5. CODE_SCAN strategies classified NEEDS_P6_POLICY
  6. REJECTED_JSON strategies classified PROVENANCE_MISSING or SOURCE_MISSING
  7. Total plannable + skippable = 300 (all P4 pending cells)
  8. No DB writes during inventory
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.p5_reconstruction_input_inventory import (
    run_inventory,
    SOURCE_AVAILABLE,
    SOURCE_MISSING,
    PROVENANCE_MISSING,
    NEEDS_P6_POLICY,
)

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
P4_JSON = REPO_ROOT / "outputs" / "replay" / "p4_coverage_matrix_dry_run_20260520.json"


@pytest.fixture(scope="module")
def inventory():
    return run_inventory(
        db_path=DB_PATH, p2_json=P2_JSON, p1_json=P1_JSON, p4_json=P4_JSON
    )


class TestReadOnlySafety:
    def test_db_row_count_unchanged(self, inventory):
        assert inventory["db_row_count_before"] == 460
        assert inventory["db_row_count_after"] == 460

    def test_is_dry_run(self, inventory):
        assert inventory["dry_run"] is True

    def test_phase_p5(self, inventory):
        assert inventory["phase"] == "P5"

    def test_direct_db_count_still_460(self):
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == 460


class TestReconstructibleScope:
    def test_exactly_12_reconstructible_strategies(self, inventory):
        assert inventory["reconstructible_count"] == 12

    def test_target_cells_is_300(self, inventory):
        assert inventory["target_draws_total"] == 300

    def test_plannable_plus_skippable_equals_300(self, inventory):
        total = inventory["total_plannable_cells"] + inventory["total_skippable_cells"]
        assert total == 300, f"Expected 300, got {total}"

    def test_plannable_cells_is_62(self, inventory):
        assert inventory["total_plannable_cells"] == 62

    def test_skippable_cells_is_238(self, inventory):
        assert inventory["total_skippable_cells"] == 238


class TestEvidenceClassification:
    def test_source_available_strategies_exist(self, inventory):
        source_avail = inventory["by_evidence_class"].get(SOURCE_AVAILABLE, [])
        assert len(source_avail) > 0, "Should have SOURCE_AVAILABLE strategies"

    def test_needs_p6_policy_for_code_scan(self, inventory):
        p6_strats = inventory["by_evidence_class"].get(NEEDS_P6_POLICY, [])
        # CODE_SCAN strategies: acb_markov_midfreq, midfreq_fourier_2bet (DAILY_539)
        # Plus BIG/POWER CODE_SCAN strategies
        assert len(p6_strats) >= 2

    def test_code_scan_strategies_in_p6_policy(self, inventory):
        p6_strats = set(inventory["by_evidence_class"].get(NEEDS_P6_POLICY, []))
        # acb_markov_midfreq and midfreq_fourier_2bet are CODE_SCAN DAILY_539
        assert "acb_markov_midfreq" in p6_strats
        assert "midfreq_fourier_2bet" in p6_strats

    def test_source_available_for_prediction_log_strategies(self, inventory):
        avail = set(inventory["by_evidence_class"].get(SOURCE_AVAILABLE, []))
        # acb_markov_midfreq_3bet has PREDICTION_LOG with 44/50 draws covered
        assert "acb_markov_midfreq_3bet" in avail

    def test_rejected_json_not_source_available(self, inventory):
        avail = set(inventory["by_evidence_class"].get(SOURCE_AVAILABLE, []))
        assert "p1_deviation_2bet_539" not in avail


class TestPerStrategyDetail:
    def test_all_strategies_have_required_fields(self, inventory):
        required = [
            "strategy_id", "lottery_type", "lifecycle_state",
            "catalog_visibility_state", "artifact_source_type",
            "evidence_class", "target_draw_count", "covered_draws_count",
            "missing_draws_count",
        ]
        for inv in inventory["strategies"]:
            for f in required:
                assert f in inv, f"{inv['strategy_id']!r} missing {f!r}"

    def test_all_strategies_are_reconstructible(self, inventory):
        for inv in inventory["strategies"]:
            assert inv["catalog_visibility_state"] == "RECONSTRUCTIBLE", (
                f"{inv['strategy_id']!r} has unexpected state "
                f"{inv['catalog_visibility_state']!r}"
            )

    def test_acb_markov_midfreq_3bet_has_44_covered_draws(self, inventory):
        strat = next(
            (i for i in inventory["strategies"]
             if i["strategy_id"] == "acb_markov_midfreq_3bet"), None
        )
        assert strat is not None
        assert strat["covered_draws_count"] == 44

    def test_code_scan_strategies_have_0_covered_draws(self, inventory):
        code_scan_strats = ["acb_markov_midfreq", "midfreq_fourier_2bet"]
        for inv in inventory["strategies"]:
            if inv["strategy_id"] in code_scan_strats:
                assert inv["covered_draws_count"] == 0, (
                    f"CODE_SCAN {inv['strategy_id']!r} should have 0 covered draws"
                )
