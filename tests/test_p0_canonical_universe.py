"""
test_p0_canonical_universe.py
==============================
P0 Schema Stabilization — Canonical Strategy Universe Tests

Verifies:
1. Total = canonical count (18 as of 2026-05-18)
2. Four-category classification sum = total
3. No duplicate canonical_ids
4. All strategies have valid lifecycle_status
5. Coverage matrix computes without error using sandbox/temporary DB
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
UNIVERSE_JSON = (
    PROJECT_ROOT
    / "outputs"
    / "replay"
    / "p0_canonical_strategy_universe_20260518.json"
)

VALID_LIFECYCLE_STATUSES = {
    "ONLINE",
    "OFFLINE",
    "REJECTED",
    "OBSERVATION",
    "RETIRED",
}
VALID_CATEGORIES = {
    "row_backed",
    "historical_reconstructable",
    "display_only",
    "tombstone",
}


class TestCanonicalUniverse:
    """Canonical strategy universe correctness tests."""

    @pytest.fixture(scope="class")
    def universe(self):
        assert UNIVERSE_JSON.exists(), (
            f"Universe JSON not found: {UNIVERSE_JSON}"
        )
        with open(str(UNIVERSE_JSON), encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def temp_db(self, tmp_path):
        db_file = tmp_path / "fixture.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            """
            CREATE TABLE draws (
                draw TEXT,
                date TEXT,
                lottery_type TEXT,
                PRIMARY KEY (draw, lottery_type)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE strategy_prediction_replays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT,
                lottery_type TEXT,
                target_draw TEXT,
                truth_level TEXT,
                generated_at TEXT
            )
            """
        )
        lottery_types = ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]
        for lt in lottery_types:
            for d_idx in range(1, 6):
                draw_id = f"1150000{d_idx:02d}"
                conn.execute(
                    "INSERT INTO draws (draw, date, lottery_type) "
                    "VALUES (?, ?, ?)",
                    (draw_id, "2026/05/01", lt),
                )
                if lt == "POWER_LOTTO":
                    strat_id = "power_precision_3bet"
                elif lt == "BIG_LOTTO":
                    strat_id = "biglotto_triple_strike"
                else:
                    strat_id = "daily539_f4cold"
                conn.execute(
                    """
                    INSERT INTO strategy_prediction_replays
                    (strategy_id, lottery_type, target_draw, truth_level,
                     generated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        strat_id,
                        lt,
                        draw_id,
                        "OFFICIAL",
                        "2026-05-01T00:00:00Z",
                    ),
                )
        conn.commit()
        conn.close()
        return db_file

    def test_universe_json_exists(self):
        assert UNIVERSE_JSON.exists(), f"Missing: {UNIVERSE_JSON}"

    def test_canonical_total_matches_strategies_list(self, universe):
        """canonical_total must equal the length of the strategies list."""
        total = universe["canonical_total"]
        listed = len(universe["strategies"])
        assert total == listed, (
            f"canonical_total={total} but strategies list has {listed} entries"
        )

    def test_four_category_sum_equals_total(self, universe):
        """row_backed + historical_reconstructable + display_only

        + tombstone = canonical_total.
        """
        classification = universe["classification"]
        cat_sum = sum(v["count"] for v in classification.values())
        total = universe["canonical_total"]
        assert cat_sum == total, (
            f"Category sum {cat_sum} != canonical_total {total}"
        )

    def test_no_duplicate_canonical_ids(self, universe):
        """All canonical_ids in strategies list must be unique."""
        ids = [s["canonical_id"] for s in universe["strategies"]]
        duplicates = [cid for cid, cnt in Counter(ids).items() if cnt > 1]
        assert not duplicates, f"Duplicate canonical_ids: {duplicates}"

    def test_all_lifecycle_statuses_valid(self, universe):
        """All strategies have a recognized lifecycle_status."""
        for s in universe["strategies"]:
            assert s["lifecycle_status"] in VALID_LIFECYCLE_STATUSES, (
                f"{s['canonical_id']} has invalid lifecycle_status: "
                f"{s['lifecycle_status']}"
            )

    def test_all_categories_valid(self, universe):
        """All strategies have a recognized category."""
        for s in universe["strategies"]:
            assert s["category"] in VALID_CATEGORIES, (
                f"{s['canonical_id']} has invalid category: {s['category']}"
            )

    def test_by_lifecycle_sums_to_total(self, universe):
        """by_lifecycle counts must sum to canonical_total."""
        total = universe["canonical_total"]
        lc_sum = sum(universe["by_lifecycle"].values())
        assert lc_sum == total, (
            f"by_lifecycle sum {lc_sum} != canonical_total {total}"
        )

    def test_canonical_total_is_positive(self, universe):
        """canonical_total must be positive."""
        assert universe["canonical_total"] > 0

    def test_each_strategy_has_required_fields(self, universe):
        """Every strategy entry has required fields."""
        required = {
            "canonical_id",
            "strategy_name",
            "lifecycle_status",
            "replay_rows",
            "category",
        }
        for s in universe["strategies"]:
            missing = required - set(s.keys())
            assert not missing, (
                f"{s.get('canonical_id', '?')} missing fields: {missing}"
            )

    def test_row_backed_have_positive_rows(self, universe):
        """row_backed strategies must have replay_rows > 0."""
        for s in universe["strategies"]:
            if s["category"] == "row_backed":
                assert s["replay_rows"] > 0, (
                    f"{s['canonical_id']} is row_backed but replay_rows=0"
                )

    def test_tombstone_have_zero_or_few_rows(self, universe):
        """tombstone strategies should have 0 replay rows."""
        for s in universe["strategies"]:
            if s["category"] == "tombstone":
                assert s["replay_rows"] == 0, (
                    f"{s['canonical_id']} is tombstone but has "
                    f"replay_rows={s['replay_rows']} — should be "
                    f"recategorized to row_backed"
                )

    def test_coverage_matrix_script_runs(self, temp_db):
        """Coverage matrix script runs without error using temporary DB."""
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.p0_per_draw_coverage_matrix import run_coverage_matrix

        matrix = run_coverage_matrix(db_path=temp_db)
        assert "error" not in matrix, (
            f"Coverage matrix error: {matrix.get('error')}"
        )
        assert "by_lottery" in matrix
        # BIG_LOTTO, DAILY_539, POWER_LOTTO
        assert len(matrix["by_lottery"]) == 3

    def test_coverage_matrix_lottery_types(self, temp_db):
        """Coverage matrix covers all three lottery types."""
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.p0_per_draw_coverage_matrix import run_coverage_matrix

        matrix = run_coverage_matrix(db_path=temp_db)
        expected = {"BIG_LOTTO", "DAILY_539", "POWER_LOTTO"}
        actual = set(matrix["by_lottery"].keys())
        assert expected == actual, (
            f"Missing lottery types: {expected - actual}"
        )

    def test_coverage_matrix_draws_count(self, temp_db):
        """Coverage matrix returns up to 10 draws per lottery type."""
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.p0_per_draw_coverage_matrix import run_coverage_matrix

        matrix = run_coverage_matrix(db_path=temp_db)
        for lt, data in matrix["by_lottery"].items():
            assert len(data["draws"]) <= 10, (
                f"{lt} returned more than 10 draws"
            )
            assert len(data["draws"]) > 0, f"{lt} returned 0 draws"
