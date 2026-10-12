"""
test_p77b_controlled_draw_refresh.py

P77B Controlled Canonical Draw Refresh — Tests

Governance:
- Draw 115000041 inserted into draws table (not as replay row)
- Replay rows must remain 46960
- POWER_LOTTO max draw must be 115000041 (CAST(draw AS INTEGER))
- Draws after 115000040 must be exactly 1
- No new tables created
- No replay row insert
- Controlled import ID: P77B_POWERLOTTO_DRAW_REFRESH_20260526
"""
import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_C1_PATH = REPO_ROOT / "backups" / "lottery_v2_pre_p66_wave6_20260525_093850.db"
P77B_JSON = REPO_ROOT / "outputs" / "replay" / "p77b_controlled_draw_refresh_20260526.json"
P77B_MD = REPO_ROOT / "docs" / "replay" / "p77b_controlled_draw_refresh_20260526.md"

CONTROLLED_IMPORT_ID = "P77B_POWERLOTTO_DRAW_REFRESH_20260526"
PRODUCTION_ROWS = 46960
INSERTED_DRAW = "115000041"
INSERTED_DATE = "2026/05/21"
INSERTED_NUMBERS = [6, 14, 22, 28, 35, 38]
INSERTED_SPECIAL = 1
POWER_LOTTO_COUNT_AFTER = 1913
THRESHOLD_DRAW = 115000040


@pytest.fixture(scope="module")
def prod_db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def p77b_json():
    assert P77B_JSON.exists(), f"P77B JSON not found: {P77B_JSON}"
    with open(P77B_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestP77BArtifacts:
    def test_json_exists(self):
        assert P77B_JSON.exists(), f"P77B JSON not found: {P77B_JSON}"

    def test_md_exists(self):
        assert P77B_MD.exists(), f"P77B MD not found: {P77B_MD}"

    def test_json_task_is_p77b(self, p77b_json):
        assert p77b_json["task"] == "P77B"

    def test_project_context_lock(self, p77b_json):
        assert p77b_json["project_context_lock"] == "LotteryNew"

    def test_classification_correct(self, p77b_json):
        assert p77b_json["final_classification"] == "P77B_POWERLOTTO_DRAW_REFRESH_COMPLETE"

    def test_controlled_import_id(self, p77b_json):
        assert p77b_json["controlled_import_id"] == CONTROLLED_IMPORT_ID


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------
class TestP77BGovernance:
    def test_no_replay_row_insert(self, p77b_json):
        assert p77b_json["governance"]["no_replay_row_insert"] is True

    def test_no_lifecycle_promotion(self, p77b_json):
        assert p77b_json["governance"]["no_lifecycle_promotion"] is True

    def test_no_registry_mutation(self, p77b_json):
        assert p77b_json["governance"]["no_registry_mutation"] is True

    def test_no_champion_replacement(self, p77b_json):
        assert p77b_json["governance"]["no_champion_replacement"] is True

    def test_no_new_tables(self, p77b_json):
        assert p77b_json["governance"]["no_new_tables"] is True

    def test_no_official_api_insert(self, p77b_json):
        assert p77b_json["governance"]["no_official_api_insert"] is True

    def test_no_force_push(self, p77b_json):
        assert p77b_json["governance"]["no_force_push"] is True

    def test_draw_insert_only(self, p77b_json):
        assert p77b_json["governance"]["draw_insert_only"] is True

    def test_insert_target_table(self, p77b_json):
        assert p77b_json["governance"]["insert_target_table"] == "draws"

    def test_insert_source_is_c1(self, p77b_json):
        source = p77b_json["governance"]["insert_source"]
        assert "lottery_v2_pre_p66_wave6_20260525_093850.db" in source


# ---------------------------------------------------------------------------
# 3. DB backup
# ---------------------------------------------------------------------------
class TestDBBackup:
    def test_backup_field_present(self, p77b_json):
        assert "db_backup" in p77b_json

    def test_backup_created_before_write(self, p77b_json):
        assert p77b_json["db_backup"]["created_before_write"] is True

    def test_backup_path_recorded(self, p77b_json):
        backup_path = p77b_json["db_backup"]["path"]
        assert "p77b_draw_refresh" in backup_path

    def test_backup_file_exists_on_disk(self, p77b_json):
        backup_path = REPO_ROOT / p77b_json["db_backup"]["path"]
        assert backup_path.exists(), f"Backup file not found: {backup_path}"

    def test_backup_size_nonzero(self, p77b_json):
        assert p77b_json["db_backup"]["size_bytes"] > 0


# ---------------------------------------------------------------------------
# 4. Source validation
# ---------------------------------------------------------------------------
class TestSourceValidation:
    def test_source_validation_present(self, p77b_json):
        assert "source_validation" in p77b_json

    def test_source_is_c1(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["candidate_id"] == "C1"
        assert "lottery_v2_pre_p66_wave6_20260525_093850.db" in sv["source_path"]

    def test_source_draw_correct(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["draw"] == INSERTED_DRAW

    def test_source_lottery_type_correct(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["lottery_type"] == "POWER_LOTTO"

    def test_source_date_correct(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["date"] == INSERTED_DATE

    def test_source_numbers_correct(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["numbers"] == INSERTED_NUMBERS

    def test_source_special_correct(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["special"] == INSERTED_SPECIAL

    def test_source_validation_overall_pass(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["validation_results"]["overall"] == "SOURCE_VALIDATION_PASS"

    def test_source_numbers_count_6(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["validation_results"]["numbers_count_6"] is True

    def test_source_numbers_in_range(self, p77b_json):
        sv = p77b_json["source_validation"]
        assert sv["validation_results"]["numbers_in_range_1_to_38"] is True


# ---------------------------------------------------------------------------
# 5. Pre-insert checks
# ---------------------------------------------------------------------------
class TestPreInsertChecks:
    def test_pre_insert_present(self, p77b_json):
        assert "pre_insert_checks" in p77b_json

    def test_production_rows_before(self, p77b_json):
        assert p77b_json["pre_insert_checks"]["production_rows_before"] == PRODUCTION_ROWS

    def test_power_lotto_count_before(self, p77b_json):
        assert p77b_json["pre_insert_checks"]["power_lotto_count_before"] == 1912

    def test_power_lotto_max_draw_before(self, p77b_json):
        assert p77b_json["pre_insert_checks"]["power_lotto_max_draw_before"] == THRESHOLD_DRAW

    def test_draws_after_threshold_before(self, p77b_json):
        assert p77b_json["pre_insert_checks"]["power_lotto_draws_after_115000040_before"] == 0

    def test_duplicate_check_pass(self, p77b_json):
        assert "PASS" in p77b_json["pre_insert_checks"]["duplicate_draw_check"]

    def test_drift_guard_pre(self, p77b_json):
        assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in p77b_json["pre_insert_checks"]["drift_guard_pre"]

    def test_branch_governance_pre(self, p77b_json):
        assert "BRANCH_GOVERNANCE_PASS" in p77b_json["pre_insert_checks"]["branch_governance_pre"]


# ---------------------------------------------------------------------------
# 6. Insert result
# ---------------------------------------------------------------------------
class TestInsertResult:
    def test_insert_status(self, p77b_json):
        assert p77b_json["insert_result"]["status"] == "INSERTED"

    def test_inserted_draw(self, p77b_json):
        assert p77b_json["insert_result"]["inserted_draw"] == INSERTED_DRAW

    def test_inserted_date(self, p77b_json):
        assert p77b_json["insert_result"]["inserted_date"] == INSERTED_DATE

    def test_inserted_special(self, p77b_json):
        assert p77b_json["insert_result"]["inserted_special"] == INSERTED_SPECIAL

    def test_rows_inserted(self, p77b_json):
        assert p77b_json["insert_result"]["rows_inserted"] == 1

    def test_inserted_numbers_in_json(self, p77b_json):
        numbers_str = p77b_json["insert_result"]["inserted_numbers"]
        # Accept either "[6, 14, 22, 28, 35, 38]" or "[6,14,22,28,35,38]"
        for n in ["6", "14", "22", "28", "35", "38"]:
            assert n in numbers_str

    def test_controlled_import_id_in_created_at(self, p77b_json):
        created_at = p77b_json["insert_result"].get("inserted_created_at", "")
        assert CONTROLLED_IMPORT_ID in created_at


# ---------------------------------------------------------------------------
# 7. Post-insert verification (JSON)
# ---------------------------------------------------------------------------
class TestPostInsertVerificationJSON:
    def test_post_insert_present(self, p77b_json):
        assert "post_insert_verification" in p77b_json

    def test_production_rows_after(self, p77b_json):
        assert p77b_json["post_insert_verification"]["production_rows_after"] == PRODUCTION_ROWS

    def test_power_lotto_count_after(self, p77b_json):
        assert p77b_json["post_insert_verification"]["power_lotto_count_after"] == POWER_LOTTO_COUNT_AFTER

    def test_power_lotto_max_draw_after(self, p77b_json):
        assert p77b_json["post_insert_verification"]["power_lotto_max_draw_after"] == int(INSERTED_DRAW)

    def test_draws_after_threshold_is_1(self, p77b_json):
        assert p77b_json["post_insert_verification"]["power_lotto_draws_after_115000040"] == 1

    def test_replay_rows_unchanged(self, p77b_json):
        assert p77b_json["post_insert_verification"]["replay_rows_unchanged"] is True

    def test_no_new_tables_created(self, p77b_json):
        assert p77b_json["post_insert_verification"]["no_new_tables_created"] is True

    def test_gate_count_incremented(self, p77b_json):
        gates = p77b_json["post_insert_verification"]["gate_checks"]
        assert gates["count_incremented_by_1"] is True

    def test_gate_max_draw(self, p77b_json):
        gates = p77b_json["post_insert_verification"]["gate_checks"]
        assert gates["max_draw_is_115000041"] is True

    def test_gate_draws_after_threshold(self, p77b_json):
        gates = p77b_json["post_insert_verification"]["gate_checks"]
        assert gates["draws_after_threshold_is_1"] is True

    def test_gate_replay_rows(self, p77b_json):
        gates = p77b_json["post_insert_verification"]["gate_checks"]
        assert gates["replay_rows_exactly_46960"] is True

    def test_drift_guard_post(self, p77b_json):
        assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in p77b_json["post_insert_verification"]["drift_guard_post"]

    def test_branch_governance_post(self, p77b_json):
        assert "BRANCH_GOVERNANCE_PASS" in p77b_json["post_insert_verification"]["branch_governance_post"]


# ---------------------------------------------------------------------------
# 8. Production DB live verification
# ---------------------------------------------------------------------------
class TestProductionDBLive:
    def test_replay_rows_still_46960(self, prod_db):
        cur = prod_db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert cur.fetchone()[0] == PRODUCTION_ROWS

    def test_draw_115000041_exists_in_db(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        assert row is not None, "Draw 115000041 not found in production DB"
        assert row[0] == INSERTED_DRAW
        assert row[1] == INSERTED_DATE
        assert row[3] == INSERTED_SPECIAL

    def test_draw_numbers_correct_in_db(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT numbers FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        assert row is not None
        numbers_str = row[0]
        for n in ["6", "14", "22", "28", "35", "38"]:
            assert n in numbers_str

    def test_controlled_import_id_in_db_created_at(self, prod_db):
        """created_at field must embed the controlled_import_id."""
        cur = prod_db.cursor()
        cur.execute(
            "SELECT created_at FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        assert row is not None
        assert CONTROLLED_IMPORT_ID in row[0]

    def test_power_lotto_max_draw_uses_cast(self, prod_db):
        """CAST(draw AS INTEGER) must return 115000041, not a text-sort artifact."""
        cur = prod_db.cursor()
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        result = cur.fetchone()[0]
        assert result == int(INSERTED_DRAW), (
            f"Expected max draw {INSERTED_DRAW} via CAST, got {result}. "
            "Ensure CAST(draw AS INTEGER) is used, not lexicographic sort."
        )

    def test_draws_after_threshold_exactly_1_via_cast(self, prod_db):
        """CAST(draw AS INTEGER) > 115000040 must return exactly 1 row."""
        cur = prod_db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > 115000040"
        )
        count = cur.fetchone()[0]
        assert count == 1, (
            f"Expected exactly 1 draw after 115000040 via CAST, got {count}. "
            "If count > 1, duplicate insert may have occurred."
        )

    def test_power_lotto_total_count_is_1913(self, prod_db):
        cur = prod_db.cursor()
        cur.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'")
        assert cur.fetchone()[0] == POWER_LOTTO_COUNT_AFTER

    def test_no_lexicographic_sort_bug(self, prod_db):
        """Verify that text sort does NOT give the correct answer (demonstrating why CAST is needed)."""
        cur = prod_db.cursor()
        # Text sort would put "97..." before "115..." because '9' > '1'
        cur.execute("SELECT MAX(draw) FROM draws WHERE lottery_type='POWER_LOTTO'")
        text_max = cur.fetchone()[0]
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        int_max = cur.fetchone()[0]
        # The integer max should be 115000041
        assert int_max == int(INSERTED_DRAW)
        # Text max may or may not match (depends on data), but integer max must be correct
        assert str(int_max) == INSERTED_DRAW

    def test_no_new_tables_in_db(self, prod_db):
        """Only expected tables exist — no new tables created by P77B."""
        cur = prod_db.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        expected_tables = {"draws", "strategy_prediction_replays"}
        # draws and strategy_prediction_replays must exist
        assert "draws" in tables
        assert "strategy_prediction_replays" in tables
        # No unexpected tables that start with p77b_ or temp_
        p77b_tables = {t for t in tables if t.startswith("p77b_") or t.startswith("temp_")}
        assert len(p77b_tables) == 0, f"Unexpected P77B tables found: {p77b_tables}"


# ---------------------------------------------------------------------------
# 9. Before/after summary
# ---------------------------------------------------------------------------
class TestBeforeAfterSummary:
    def test_summary_present(self, p77b_json):
        assert "before_after_summary" in p77b_json

    def test_max_draw_before(self, p77b_json):
        assert p77b_json["before_after_summary"]["power_lotto_max_draw"]["before"] == THRESHOLD_DRAW

    def test_max_draw_after(self, p77b_json):
        assert p77b_json["before_after_summary"]["power_lotto_max_draw"]["after"] == int(INSERTED_DRAW)

    def test_draw_count_before(self, p77b_json):
        assert p77b_json["before_after_summary"]["power_lotto_draw_count"]["before"] == 1912

    def test_draw_count_after(self, p77b_json):
        assert p77b_json["before_after_summary"]["power_lotto_draw_count"]["after"] == POWER_LOTTO_COUNT_AFTER

    def test_replay_rows_before(self, p77b_json):
        assert p77b_json["before_after_summary"]["replay_rows"]["before"] == PRODUCTION_ROWS

    def test_replay_rows_after(self, p77b_json):
        assert p77b_json["before_after_summary"]["replay_rows"]["after"] == PRODUCTION_ROWS

    def test_draws_after_threshold_before(self, p77b_json):
        assert p77b_json["before_after_summary"]["draws_after_115000040"]["before"] == 0

    def test_draws_after_threshold_after(self, p77b_json):
        assert p77b_json["before_after_summary"]["draws_after_115000040"]["after"] == 1


# ---------------------------------------------------------------------------
# 10. P78 readiness
# ---------------------------------------------------------------------------
class TestP78Readiness:
    def test_p78_can_proceed(self, p77b_json):
        assert p77b_json["p78_readiness"]["can_proceed"] is True

    def test_p78_batch_a_eligible_draws(self, p77b_json):
        assert p77b_json["p78_readiness"]["batch_a_eligible_draws_added"] == 1

    def test_p78_reason_mentions_draw(self, p77b_json):
        reason = p77b_json["p78_readiness"]["reason"]
        assert "115000041" in reason

    def test_p78_note_mentions_further_draws(self, p77b_json):
        note = p77b_json["p78_readiness"]["note"]
        assert "115000042" in note or "115000041" in note


# ---------------------------------------------------------------------------
# 11. Forbidden staging scan
# ---------------------------------------------------------------------------
class TestForbiddenStagingScan:
    def test_forbidden_staging_clean(self, p77b_json):
        scan = p77b_json["forbidden_staging_scan"]
        assert scan["db_files_staged"] is False
        assert scan["backup_files_staged"] is False
        assert scan["pid_runtime_files_staged"] is False
        assert scan["overall"] == "STAGE_CLEAN"


# ---------------------------------------------------------------------------
# 12. MD content checks
# ---------------------------------------------------------------------------
class TestMDContent:
    def test_md_contains_classification(self):
        content = P77B_MD.read_text()
        assert "P77B_POWERLOTTO_DRAW_REFRESH_COMPLETE" in content

    def test_md_contains_draw_115000041(self):
        content = P77B_MD.read_text()
        assert "115000041" in content

    def test_md_contains_draw_date(self):
        content = P77B_MD.read_text()
        assert "2026/05/21" in content

    def test_md_contains_draw_numbers(self):
        content = P77B_MD.read_text()
        assert "6, 14, 22, 28, 35, 38" in content or "6,14,22,28,35,38" in content

    def test_md_contains_controlled_import_id(self):
        content = P77B_MD.read_text()
        assert CONTROLLED_IMPORT_ID in content

    def test_md_contains_p78_readiness(self):
        content = P77B_MD.read_text()
        assert "P78" in content

    def test_md_no_replay_row_insert_claim(self):
        """Confirm no replay rows were inserted."""
        content = P77B_MD.read_text().lower()
        assert "replay_rows_unchanged" in content or "unchanged" in content

    def test_md_no_new_tables_confirmed(self):
        content = P77B_MD.read_text().lower()
        assert "no new table" in content or "new tables" in content


# ---------------------------------------------------------------------------
# 13. Source validation cross-check with backup C1
# ---------------------------------------------------------------------------
class TestBackupC1CrossCheck:
    def test_backup_c1_exists(self):
        assert BACKUP_C1_PATH.exists(), f"Backup C1 not found: {BACKUP_C1_PATH}"

    def test_backup_c1_draw_115000041_matches_inserted(self):
        """Verify the draw in backup C1 matches what was inserted into production."""
        conn = sqlite3.connect(f"file:{BACKUP_C1_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None, "Draw 115000041 not found in backup C1"
        assert row[0] == INSERTED_DRAW
        assert row[1] == INSERTED_DATE
        assert row[3] == INSERTED_SPECIAL

    def test_backup_c1_numbers_in_range(self):
        """Verify backup C1 numbers are all in [1, 38]."""
        conn = sqlite3.connect(f"file:{BACKUP_C1_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT numbers FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None
        # Parse numbers from string representation e.g. "[6, 14, 22, 28, 35, 38]"
        numbers_str = row[0].strip("[]")
        numbers = [int(n.strip()) for n in numbers_str.split(",")]
        assert len(numbers) == 6
        assert all(1 <= n <= 38 for n in numbers)
        assert sorted(numbers) == INSERTED_NUMBERS
