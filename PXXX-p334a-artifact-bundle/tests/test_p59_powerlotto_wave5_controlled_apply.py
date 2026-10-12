"""
P59 — POWER_LOTTO Wave 5 Controlled Production Apply: Test Suite.

Verifies the integrity of the 1500 production rows inserted by P59
for fourier30_markov30_2bet.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Constants ────────────────────────────────────────────────────────────────

PROD_DB = Path(__file__).resolve().parent.parent / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON = (
    Path(__file__).resolve().parent.parent
    / "outputs" / "replay" / "p59_powerlotto_wave5_controlled_apply_20260525.json"
)

STRATEGY_ID        = "fourier30_markov30_2bet"
LOTTERY_TYPE       = "POWER_LOTTO"
CONTROLLED_APPLY_ID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
EXPECTED_TOTAL_ROWS    = 43960
EXPECTED_STRATEGY_ROWS = 1500
EXCLUDED_STRATEGIES = ["cold_complement_2bet", "zonal_entropy_2bet"]

POOL   = 38
PICK   = 6
SPEC   = 8


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_conn():
    uri = f"file:{PROD_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def output_json():
    assert OUTPUT_JSON.exists(), f"P59 output JSON not found: {OUTPUT_JSON}"
    with open(OUTPUT_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def p59_rows(db_conn):
    rows = db_conn.execute(
        "SELECT * FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ?",
        (CONTROLLED_APPLY_ID,),
    ).fetchall()
    return rows


# ─── JSON classification tests ────────────────────────────────────────────────

class TestP59OutputJSON:
    def test_classification(self, output_json):
        assert output_json["classification"] == "P59_POWERLOTTO_WAVE5_CONTROLLED_APPLY_COMPLETED"

    def test_overall_ok(self, output_json):
        assert output_json["overall_ok"] is True

    def test_phase(self, output_json):
        assert output_json["phase"] == "P59"

    def test_mode(self, output_json):
        assert output_json["mode"] == "CONTROLLED_APPLY"

    def test_prod_write_true(self, output_json):
        gov = output_json.get("governance", {})
        assert gov.get("production_db_write") is True

    def test_no_lifecycle_promotion(self, output_json):
        gov = output_json.get("governance", {})
        assert gov.get("lifecycle_promotion") is False

    def test_no_champion_replacement(self, output_json):
        gov = output_json.get("governance", {})
        assert gov.get("champion_replacement") is False

    def test_no_online_promotion(self, output_json):
        gov = output_json.get("governance", {})
        assert gov.get("online_promotion") is False

    def test_no_registry_mutation(self, output_json):
        gov = output_json.get("governance", {})
        assert gov.get("registry_mutation") is False

    def test_watchlist_excluded(self, output_json):
        excluded = output_json.get("governance", {}).get("watchlist_strategies_excluded", [])
        assert "cold_complement_2bet" in excluded
        assert "zonal_entropy_2bet" in excluded

    def test_inserted_rows(self, output_json):
        assert output_json.get("inserted_rows") == EXPECTED_STRATEGY_ROWS

    def test_production_rows_after(self, output_json):
        assert output_json.get("production_rows_after") == EXPECTED_TOTAL_ROWS

    def test_controlled_apply_id(self, output_json):
        assert output_json.get("controlled_apply_id") == CONTROLLED_APPLY_ID

    def test_leakage_pass(self, output_json):
        lk = output_json.get("leakage_check", {})
        assert lk.get("pass") is True, f"Leakage violations: {lk.get('violations')}"

    def test_schema_valid(self, output_json):
        sv = output_json.get("schema_validation", {})
        assert sv.get("valid") is True

    def test_post_verify_total_ok(self, output_json):
        pv = output_json.get("post_apply_verification", {})
        assert pv.get("total_ok") is True

    def test_post_verify_strategy_rows_ok(self, output_json):
        pv = output_json.get("post_apply_verification", {})
        assert pv.get("strategy_rows_ok") is True

    def test_post_verify_online_ok(self, output_json):
        pv = output_json.get("post_apply_verification", {})
        assert pv.get("online_promotion_ok") is True

    def test_post_verify_semantic_ok(self, output_json):
        pv = output_json.get("post_apply_verification", {})
        assert pv.get("semantic_ok") is True, f"Semantic errors: {pv.get('semantic_errors')}"

    def test_post_verify_dry_run_zero_ok(self, output_json):
        pv = output_json.get("post_apply_verification", {})
        assert pv.get("dry_run_zero_ok") is True

    def test_p58_ref_classification(self, output_json):
        ref = output_json.get("p58_ref", {})
        assert ref.get("classification") == "P58_CONTROLLED_APPLY_PROPOSAL_READY"

    def test_p58_ref_mode(self, output_json):
        ref = output_json.get("p58_ref", {})
        assert ref.get("mode") == "PROPOSAL_ONLY"


# ─── DB row count tests ───────────────────────────────────────────────────────

class TestP59DBRowCounts:
    def test_total_rows(self, db_conn):
        total = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert total == EXPECTED_TOTAL_ROWS, f"total={total} expected={EXPECTED_TOTAL_ROWS}"

    def test_strategy_rows(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_ID),
        ).fetchone()[0]
        assert count == EXPECTED_STRATEGY_ROWS

    def test_caid_rows(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        assert count == EXPECTED_STRATEGY_ROWS

    def test_no_online_rows(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND replay_status='ONLINE'",
            (LOTTERY_TYPE, STRATEGY_ID),
        ).fetchone()[0]
        assert count == 0

    def test_all_dry_run_zero(self, db_conn):
        bad = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run != 0",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        assert bad == 0, f"dry_run != 0 for {bad} rows"

    def test_excluded_strategies_not_present(self, db_conn):
        for strat in EXCLUDED_STRATEGIES:
            count = db_conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE lottery_type=? AND strategy_id=? AND controlled_apply_id=?",
                (LOTTERY_TYPE, strat, CONTROLLED_APPLY_ID),
            ).fetchone()[0]
            assert count == 0, f"Excluded strategy {strat} has {count} rows with this CAID"

    def test_p59_row_count_equals_caid_count(self, db_conn):
        strategy_count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_ID),
        ).fetchone()[0]
        caid_count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        assert strategy_count == caid_count == EXPECTED_STRATEGY_ROWS


# ─── POWER_LOTTO semantic tests ───────────────────────────────────────────────

class TestP59Semantics:
    def test_predicted_numbers_format(self, p59_rows):
        """All predicted_numbers must be valid JSON arrays of 6 ints in [1..38]."""
        errors = []
        for row in p59_rows:
            raw = row["predicted_numbers"]
            try:
                nums = json.loads(raw)
                if len(nums) != PICK:
                    errors.append(f"draw {row['target_draw']}: len={len(nums)}")
                if any(not (1 <= n <= POOL) for n in nums):
                    errors.append(f"draw {row['target_draw']}: out of range {nums}")
                if len(set(nums)) != len(nums):
                    errors.append(f"draw {row['target_draw']}: duplicates {nums}")
            except Exception as e:
                errors.append(f"draw {row['target_draw']}: parse error {e}")
        assert not errors, f"Semantic errors ({len(errors)}): {errors[:5]}"

    def test_predicted_special_format(self, p59_rows):
        """All predicted_special must be int in [1..8]."""
        errors = []
        for row in p59_rows:
            sp_raw = row["predicted_special"]
            try:
                sp = int(sp_raw)
                if not (1 <= sp <= SPEC):
                    errors.append(f"draw {row['target_draw']}: special={sp}")
            except Exception as e:
                errors.append(f"draw {row['target_draw']}: special parse error {e}")
        assert not errors, f"Special errors ({len(errors)}): {errors[:5]}"

    def test_no_duplicate_target_draws(self, p59_rows):
        """Each target draw must appear exactly once."""
        draws = [row["target_draw"] for row in p59_rows]
        assert len(draws) == len(set(draws)), "Duplicate target draws found"

    def test_strategy_id_correct(self, p59_rows):
        for row in p59_rows:
            assert row["strategy_id"] == STRATEGY_ID

    def test_lottery_type_correct(self, p59_rows):
        for row in p59_rows:
            assert row["lottery_type"] == LOTTERY_TYPE

    def test_controlled_apply_id_correct(self, p59_rows):
        for row in p59_rows:
            assert row["controlled_apply_id"] == CONTROLLED_APPLY_ID

    def test_dry_run_is_zero(self, p59_rows):
        for row in p59_rows:
            assert row["dry_run"] == 0

    def test_hit_count_consistent(self, p59_rows):
        """hit_count must equal len(hit_numbers) for every row."""
        errors = []
        for row in p59_rows:
            try:
                hit_nums = json.loads(row["hit_numbers"]) if row["hit_numbers"] else []
                hc = row["hit_count"]
                if len(hit_nums) != hc:
                    errors.append(f"draw {row['target_draw']}: hit_count={hc} len(hit_nums)={len(hit_nums)}")
            except Exception as e:
                errors.append(f"draw {row['target_draw']}: {e}")
        assert not errors, f"hit_count inconsistencies: {errors[:5]}"

    def test_hit_numbers_subset_of_actual(self, p59_rows):
        """hit_numbers must be a subset of actual_numbers."""
        errors = []
        for row in p59_rows:
            try:
                hit = set(json.loads(row["hit_numbers"])) if row["hit_numbers"] else set()
                actual = set(json.loads(row["actual_numbers"])) if row["actual_numbers"] else set()
                if not hit.issubset(actual):
                    errors.append(f"draw {row['target_draw']}: hit not subset of actual")
            except Exception as e:
                errors.append(f"draw {row['target_draw']}: {e}")
        assert len(errors) == 0, f"Hit/actual consistency errors: {errors[:5]}"

    def test_hit_numbers_in_predicted(self, p59_rows):
        """hit_numbers must be a subset of predicted_numbers."""
        errors = []
        for row in p59_rows:
            try:
                hit = set(json.loads(row["hit_numbers"])) if row["hit_numbers"] else set()
                pred = set(json.loads(row["predicted_numbers"])) if row["predicted_numbers"] else set()
                if not hit.issubset(pred):
                    errors.append(f"draw {row['target_draw']}: hit not subset of predicted")
            except Exception as e:
                errors.append(f"draw {row['target_draw']}: {e}")
        assert len(errors) == 0, f"Hit/predicted consistency errors: {errors[:5]}"


# ─── Leakage tests ────────────────────────────────────────────────────────────

class TestP59Leakage:
    def test_leakage_check_from_json(self, output_json):
        """No leakage violations reported in P59 JSON."""
        lk = output_json.get("leakage_check", {})
        assert lk.get("violation_count") == 0
        assert lk.get("pass") is True

    def test_cutoff_before_draw_date(self, p59_rows):
        """prediction_cutoff_date < target_date for all rows with both dates present."""
        violations = []
        for row in p59_rows:
            cutoff = row["prediction_cutoff_date"] or ""
            draw_date = row["target_date"] or ""
            if cutoff and draw_date and cutoff >= draw_date:
                violations.append(
                    f"draw {row['target_draw']}: cutoff={cutoff} >= draw={draw_date}"
                )
        assert not violations, f"Leakage violations ({len(violations)}): {violations[:5]}"


# ─── Governance guard tests ───────────────────────────────────────────────────

class TestP59GovernanceGuards:
    def test_no_champion_replacement(self, db_conn):
        """fourier_rhythm_3bet champion must still exist."""
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, "fourier_rhythm_3bet"),
        ).fetchone()[0]
        assert count > 0, "Champion fourier_rhythm_3bet rows missing — possible replacement"

    def test_no_extra_caids_from_p59(self, db_conn):
        """Only one controlled_apply_id from P59 must exist."""
        caids = db_conn.execute(
            "SELECT DISTINCT controlled_apply_id FROM strategy_prediction_replays "
            "WHERE controlled_apply_id LIKE 'P58_POWERLOTTO_WAVE5%'"
        ).fetchall()
        caid_list = [r[0] for r in caids]
        assert CONTROLLED_APPLY_ID in caid_list
        assert len(caid_list) == 1, f"Unexpected extra CAIDs: {caid_list}"

    def test_hit_stats_within_expected_range(self, output_json):
        """M3+ hit rate must be in a reasonable range [1%..20%]."""
        hs = output_json.get("hit_stats", {})
        rate = hs.get("hit_3plus_rate", 0)
        assert 0.01 <= rate <= 0.20, f"M3+ rate out of expected range: {rate}"
