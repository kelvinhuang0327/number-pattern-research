"""
test_p78_batch_a_plan_regeneration.py

P78 Batch A Plan Regeneration Tests

Governance:
- No replay row insert (dry-run only)
- No draws table write
- Production replay rows must remain 46960
- POWER_LOTTO max draw must remain 115000041
- Draw 115000041 must be present with correct data
- Both Batch A strategies must have 1 eligible row each
- No duplicate risk for P78 controlled_apply_ids
- CAST(draw AS INTEGER) used for all numeric draw comparisons
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P78_JSON = REPO_ROOT / "outputs" / "replay" / "p78_batch_a_plan_regeneration_20260526.json"
P78_MD = REPO_ROOT / "docs" / "replay" / "p78_batch_a_plan_regeneration_20260526.md"

PRODUCTION_ROWS = 46960
TARGET_DRAW = "115000041"
TARGET_DATE = "2026/05/21"
ACTUAL_NUMBERS = [6, 14, 22, 28, 35, 38]
ACTUAL_SPECIAL = 1

FOURIER_RHYTHM_PREDICTED = [3, 23, 24, 28, 30, 36]
FOURIER30_MARKOV30_PREDICTED = [13, 14, 27, 29, 34, 38]

FOURIER_RHYTHM_HITS = [28]
FOURIER30_MARKOV30_HITS = [14, 38]

P78_CONTROLLED_APPLY_IDS = [
    "P78_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_DRAWEXT_20260526",
    "P78_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_DRAWEXT_20260526",
]


@pytest.fixture(scope="module")
def prod_db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def p78_json():
    assert P78_JSON.exists(), f"P78 JSON not found: {P78_JSON}"
    with open(P78_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestP78Artifacts:
    def test_json_exists(self):
        assert P78_JSON.exists()

    def test_md_exists(self):
        assert P78_MD.exists()

    def test_json_task_is_p78(self, p78_json):
        assert p78_json["task"] == "P78_BATCH_A_PLAN_REGENERATION"

    def test_project_context_lock(self, p78_json):
        assert p78_json["project_context_lock"] == "LotteryNew"

    def test_classification_correct(self, p78_json):
        assert p78_json["final_classification"] == "P78_BATCH_A_PLAN_REGENERATION_COMPLETE"

    def test_final_plan_status(self, p78_json):
        assert p78_json["final_plan_status"] == "PLAN_READY_FOR_P79_APPLY"

    def test_dry_run_flag(self, p78_json):
        assert p78_json["dry_run"] is True

    def test_no_db_write_flag(self, p78_json):
        assert p78_json["no_db_write"] is True


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------
class TestP78Governance:
    def test_no_replay_row_insert(self, p78_json):
        assert p78_json["governance"]["no_replay_row_insert"] is True

    def test_no_draws_table_write(self, p78_json):
        assert p78_json["governance"]["no_draws_table_write"] is True

    def test_no_lifecycle_promotion(self, p78_json):
        assert p78_json["governance"]["no_lifecycle_promotion"] is True

    def test_no_champion_replacement(self, p78_json):
        assert p78_json["governance"]["no_champion_replacement"] is True

    def test_no_registry_mutation(self, p78_json):
        assert p78_json["governance"]["no_registry_mutation"] is True

    def test_no_new_tables(self, p78_json):
        assert p78_json["governance"]["no_new_tables"] is True

    def test_no_official_api_insert(self, p78_json):
        assert p78_json["governance"]["no_official_api_insert"] is True

    def test_dry_run_only(self, p78_json):
        assert p78_json["governance"]["dry_run_only"] is True


# ---------------------------------------------------------------------------
# 3. Pre-flight checks in JSON
# ---------------------------------------------------------------------------
class TestPreflight:
    def test_replay_rows_before(self, p78_json):
        assert p78_json["preflight"]["production_replay_rows_before"] == PRODUCTION_ROWS

    def test_replay_rows_after(self, p78_json):
        assert p78_json["preflight"]["production_replay_rows_after"] == PRODUCTION_ROWS

    def test_power_lotto_max_draw(self, p78_json):
        assert p78_json["preflight"]["power_lotto_max_draw"] == int(TARGET_DRAW)

    def test_target_draw_in_db(self, p78_json):
        assert p78_json["preflight"]["target_draw_in_db"] is True

    def test_batch_a_rows_before_is_zero(self, p78_json):
        assert p78_json["preflight"]["batch_a_rows_for_target_draw_before"] == 0

    def test_drift_guard_pre(self, p78_json):
        assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in p78_json["preflight"]["drift_guard_pre"]

    def test_branch_governance_pre(self, p78_json):
        assert "BRANCH_GOVERNANCE_PASS" in p78_json["preflight"]["branch_governance_pre"]


# ---------------------------------------------------------------------------
# 4. Target draw verified
# ---------------------------------------------------------------------------
class TestTargetDraw:
    def test_target_draw_id(self, p78_json):
        assert p78_json["target_draw"]["draw"] == TARGET_DRAW

    def test_target_draw_date(self, p78_json):
        assert p78_json["target_draw"]["date"] == TARGET_DATE

    def test_target_draw_numbers(self, p78_json):
        assert p78_json["target_draw"]["numbers"] == ACTUAL_NUMBERS

    def test_target_draw_special(self, p78_json):
        assert p78_json["target_draw"]["special"] == ACTUAL_SPECIAL

    def test_target_draw_source(self, p78_json):
        assert "P77B" in p78_json["target_draw"]["source"]


# ---------------------------------------------------------------------------
# 5. Production DB — no rows inserted, draw present
# ---------------------------------------------------------------------------
class TestProductionDBLive:
    def test_replay_rows_unchanged(self, prod_db):
        cur = prod_db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert cur.fetchone()[0] == PRODUCTION_ROWS

    def test_draw_115000041_exists(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == TARGET_DRAW
        assert row[1] == TARGET_DATE
        assert row[3] == ACTUAL_SPECIAL

    def test_draw_115000041_numbers(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT numbers FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        numbers_str = cur.fetchone()[0]
        for n in ["6", "14", "22", "28", "35", "38"]:
            assert n in numbers_str

    def test_power_lotto_max_draw_via_cast(self, prod_db):
        """CAST(draw AS INTEGER) must return 115000041."""
        cur = prod_db.cursor()
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        assert cur.fetchone()[0] == int(TARGET_DRAW)

    def test_no_p78_rows_in_db(self, prod_db):
        """P78 is dry-run only — no controlled_apply_id rows must exist in DB."""
        cur = prod_db.cursor()
        placeholders = ",".join("?" for _ in P78_CONTROLLED_APPLY_IDS)
        cur.execute(
            f"SELECT COUNT(*) FROM strategy_prediction_replays "
            f"WHERE controlled_apply_id IN ({placeholders})",
            P78_CONTROLLED_APPLY_IDS,
        )
        assert cur.fetchone()[0] == 0, (
            "P78 is dry-run only — no rows should be present with P78 controlled_apply_ids"
        )

    def test_fourier_rhythm_no_row_for_115000041(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='fourier_rhythm_3bet' AND target_draw='115000041'"
        )
        assert cur.fetchone()[0] == 0

    def test_fourier30_markov30_no_row_for_115000041(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='fourier30_markov30_2bet' AND target_draw='115000041'"
        )
        assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 6. Plan rows — both strategies eligible
# ---------------------------------------------------------------------------
class TestPlanRows:
    def test_total_plan_rows(self, p78_json):
        assert p78_json["total_plan_insert_rows"] == 2

    def test_eligible_rows_fourier_rhythm(self, p78_json):
        assert p78_json["eligible_rows_by_strategy"]["fourier_rhythm_3bet"] == 1

    def test_eligible_rows_fourier30_markov30(self, p78_json):
        assert p78_json["eligible_rows_by_strategy"]["fourier30_markov30_2bet"] == 1

    def test_fourier_rhythm_row_exists(self, p78_json):
        rows = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"]
        assert len(rows) == 1

    def test_fourier30_markov30_row_exists(self, p78_json):
        rows = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"]
        assert len(rows) == 1

    def test_fourier_rhythm_target_draw(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        assert row["target_draw"] == TARGET_DRAW

    def test_fourier30_markov30_target_draw(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        assert row["target_draw"] == TARGET_DRAW

    def test_fourier_rhythm_dry_run_flag(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        assert row["dry_run"] == 1

    def test_fourier30_markov30_dry_run_flag(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        assert row["dry_run"] == 1

    def test_fourier_rhythm_history_cutoff(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        assert row["history_cutoff_draw"] == "115000040"

    def test_fourier30_markov30_history_cutoff(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        assert row["history_cutoff_draw"] == "115000040"


# ---------------------------------------------------------------------------
# 7. Predicted numbers validation
# ---------------------------------------------------------------------------
class TestPredictedNumbers:
    def test_fourier_rhythm_predicted_numbers(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        nums_str = row["predicted_numbers"]
        for n in ["3", "23", "24", "28", "30", "36"]:
            assert n in nums_str

    def test_fourier30_markov30_predicted_numbers(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        nums_str = row["predicted_numbers"]
        for n in ["13", "14", "27", "29", "34", "38"]:
            assert n in nums_str

    def test_fourier_rhythm_actual_numbers_correct(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        nums_str = row["actual_numbers"]
        for n in ["6", "14", "22", "28", "35", "38"]:
            assert n in nums_str

    def test_fourier30_markov30_actual_numbers_correct(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        nums_str = row["actual_numbers"]
        for n in ["6", "14", "22", "28", "35", "38"]:
            assert n in nums_str

    def test_fourier_rhythm_hit_count(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        assert row["hit_count"] == 1

    def test_fourier30_markov30_hit_count(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        assert row["hit_count"] == 2

    def test_fourier_rhythm_hit_numbers(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        assert "28" in row["hit_numbers"]

    def test_fourier30_markov30_hit_numbers(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        assert "14" in row["hit_numbers"]
        assert "38" in row["hit_numbers"]

    def test_fourier_rhythm_actual_special(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier_rhythm_3bet"][0]
        assert row["actual_special"] == ACTUAL_SPECIAL

    def test_fourier30_markov30_actual_special(self, p78_json):
        row = p78_json["plan_insert_rows_by_strategy"]["fourier30_markov30_2bet"][0]
        assert row["actual_special"] == ACTUAL_SPECIAL


# ---------------------------------------------------------------------------
# 8. Live prediction re-generation (determinism check)
# ---------------------------------------------------------------------------
class TestLivePredictionDeterminism:
    """Re-run predictions and verify they match the plan exactly."""

    def _load_history(self):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) <= 115000040 "
            "ORDER BY CAST(draw AS INTEGER) ASC"
        )
        rows = cur.fetchall()
        conn.close()
        history = []
        for draw, date, numbers_str, special in rows:
            try:
                nums = json.loads(numbers_str)
            except Exception:
                nums = [int(n.strip()) for n in numbers_str.strip("[]").split(",")]
            history.append({"draw": draw, "date": date, "numbers": nums, "special": special})
        return history

    def test_history_length(self):
        history = self._load_history()
        assert len(history) == 1912

    def test_history_cutoff_max_draw(self):
        """Last item in history must be 115000040 via CAST (not text sort)."""
        history = self._load_history()
        assert history[-1]["draw"] == "115000040"

    def test_fourier_rhythm_prediction_deterministic(self):
        """fourier_rhythm_predict is deterministic — re-running must give same bet-0."""
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        history = self._load_history()
        preds = fourier_rhythm_predict(history, n_bets=3, window=500)
        first_bet = sorted(preds[0]) if preds else []
        assert first_bet == FOURIER_RHYTHM_PREDICTED

    def test_fourier30_markov30_prediction_deterministic(self):
        """predict_fourier30_markov30_2bet_bet0 is deterministic."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import (
            predict_fourier30_markov30_2bet_bet0,
        )
        history = self._load_history()
        bet0 = sorted(predict_fourier30_markov30_2bet_bet0(history))
        assert bet0 == FOURIER30_MARKOV30_PREDICTED

    def test_fourier_rhythm_hits_correct(self):
        actual_set = set(ACTUAL_NUMBERS)
        predicted_set = set(FOURIER_RHYTHM_PREDICTED)
        hits = sorted(actual_set & predicted_set)
        assert hits == FOURIER_RHYTHM_HITS
        assert len(hits) == 1

    def test_fourier30_markov30_hits_correct(self):
        actual_set = set(ACTUAL_NUMBERS)
        predicted_set = set(FOURIER30_MARKOV30_PREDICTED)
        hits = sorted(actual_set & predicted_set)
        assert hits == FOURIER30_MARKOV30_HITS
        assert len(hits) == 2


# ---------------------------------------------------------------------------
# 9. Duplicate check — P78 IDs are clean
# ---------------------------------------------------------------------------
class TestDuplicateCheck:
    def test_duplicate_check_collision_free(self, p78_json):
        assert p78_json["duplicate_check_result"]["collision_free"] is True

    def test_duplicate_check_p78_existing_rows(self, p78_json):
        assert p78_json["duplicate_check_result"]["p78_existing_rows"] == 0

    def test_duplicate_check_risk_none(self, p78_json):
        assert p78_json["duplicate_check_result"]["duplicate_risk"] == "NONE"

    def test_p78_controlled_apply_ids_not_in_db(self, prod_db):
        cur = prod_db.cursor()
        placeholders = ",".join("?" for _ in P78_CONTROLLED_APPLY_IDS)
        cur.execute(
            f"SELECT COUNT(*) FROM strategy_prediction_replays "
            f"WHERE controlled_apply_id IN ({placeholders})",
            P78_CONTROLLED_APPLY_IDS,
        )
        assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 10. CAST(draw AS INTEGER) verification
# ---------------------------------------------------------------------------
class TestNumericDrawComparison:
    def test_cast_method_documented(self, p78_json):
        assert p78_json["numeric_draw_comparison_verified"]["method_used"] == "CAST(draw AS INTEGER)"

    def test_text_sort_disabled(self, p78_json):
        assert p78_json["numeric_draw_comparison_verified"]["text_sort_disabled"] is True

    def test_cast_gives_correct_max(self, prod_db):
        """CAST(draw AS INTEGER) must return 115000041 — text sort would give wrong result."""
        cur = prod_db.cursor()
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        assert cur.fetchone()[0] == int(TARGET_DRAW)

    def test_draws_after_115000040_exactly_1(self, prod_db):
        """CAST(draw AS INTEGER) > 115000040 must be exactly 1."""
        cur = prod_db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > 115000040"
        )
        assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# 11. Strategy lifecycle unchanged
# ---------------------------------------------------------------------------
class TestStrategyLifecycle:
    def test_fourier_rhythm_lifecycle_online(self, p78_json):
        lc = p78_json["strategy_lifecycle_check"]["fourier_rhythm_3bet"]
        assert lc["lifecycle_label"] == "ONLINE"
        assert lc["changed"] is False

    def test_fourier30_markov30_lifecycle_active(self, p78_json):
        lc = p78_json["strategy_lifecycle_check"]["fourier30_markov30_2bet"]
        assert lc["lifecycle_label"] == "ACTIVE"
        assert lc["changed"] is False


# ---------------------------------------------------------------------------
# 12. P79 readiness
# ---------------------------------------------------------------------------
class TestP79Readiness:
    def test_p79_can_proceed(self, p78_json):
        assert p78_json["p79_readiness"]["can_proceed"] is True

    def test_p79_eligible_rows(self, p78_json):
        assert p78_json["p79_readiness"]["eligible_rows_total"] == 2

    def test_p79_insert_delta(self, p78_json):
        assert p78_json["p79_readiness"]["expected_p79_insert_delta"] == 2

    def test_p79_rows_before(self, p78_json):
        assert p78_json["p79_readiness"]["rows_before_p79"] == PRODUCTION_ROWS

    def test_p79_rows_after_expected(self, p78_json):
        assert p78_json["p79_readiness"]["rows_after_p79_expected"] == PRODUCTION_ROWS + 2

    def test_p79_no_blocker(self, p78_json):
        assert p78_json["p79_readiness"]["blocker"] is None

    def test_p79_authorization_phrase_present(self, p78_json):
        phrase = p78_json["p79_readiness"]["authorization_phrase_required"]
        assert "P79" in phrase
        assert "115000041" in phrase


# ---------------------------------------------------------------------------
# 13. Dry-run summary
# ---------------------------------------------------------------------------
class TestDryRunSummary:
    def test_dry_run_classification(self, p78_json):
        assert p78_json["dry_run_summary"]["classification"] == "P78_BATCH_A_DRY_RUN_PLAN_READY"

    def test_dry_run_total_plan_rows(self, p78_json):
        assert p78_json["dry_run_summary"]["total_plan_rows"] == 2

    def test_dry_run_eligible_rows(self, p78_json):
        assert p78_json["dry_run_summary"]["eligible_rows"] == 2

    def test_dry_run_skipped_rows(self, p78_json):
        assert p78_json["dry_run_summary"]["skipped_rows"] == 0

    def test_dry_run_collision_free(self, p78_json):
        assert p78_json["dry_run_summary"]["collision_free"] is True

    def test_dry_run_no_db_write(self, p78_json):
        assert p78_json["dry_run_summary"]["db_write_occurred"] is False

    def test_dry_run_replay_rows_unchanged(self, p78_json):
        assert p78_json["dry_run_summary"]["replay_rows_before"] == PRODUCTION_ROWS
        assert p78_json["dry_run_summary"]["replay_rows_after"] == PRODUCTION_ROWS

    def test_dry_run_p79_delta(self, p78_json):
        assert p78_json["dry_run_summary"]["p79_delta"] == 2


# ---------------------------------------------------------------------------
# 14. Forbidden staging scan
# ---------------------------------------------------------------------------
class TestForbiddenStagingScan:
    def test_forbidden_staging_clean(self, p78_json):
        scan = p78_json["forbidden_staging_scan"]
        assert scan["db_files_staged"] is False
        assert scan["backup_files_staged"] is False
        assert scan["pid_runtime_files_staged"] is False
        assert scan["overall"] == "STAGE_CLEAN"


# ---------------------------------------------------------------------------
# 15. MD content checks
# ---------------------------------------------------------------------------
class TestMDContent:
    def test_md_classification(self):
        content = P78_MD.read_text()
        assert "P78_BATCH_A_PLAN_REGENERATION_COMPLETE" in content

    def test_md_target_draw(self):
        content = P78_MD.read_text()
        assert "115000041" in content

    def test_md_actual_numbers(self):
        content = P78_MD.read_text()
        assert "6, 14, 22, 28, 35, 38" in content

    def test_md_fourier_rhythm_predicted(self):
        content = P78_MD.read_text()
        assert "3, 23, 24, 28, 30, 36" in content

    def test_md_fourier30_markov30_predicted(self):
        content = P78_MD.read_text()
        assert "13, 14, 27, 29, 34, 38" in content

    def test_md_p79_readiness(self):
        content = P78_MD.read_text()
        assert "P79" in content

    def test_md_dry_run_confirmed(self):
        content = P78_MD.read_text().lower()
        assert "dry-run" in content or "dry_run" in content

    def test_md_no_replay_row_insert_claimed(self):
        content = P78_MD.read_text()
        assert "No replay row" in content or "no replay row" in content.lower()

    def test_md_authorization_phrase_present(self):
        content = P78_MD.read_text()
        assert "YES proceed with P79" in content
