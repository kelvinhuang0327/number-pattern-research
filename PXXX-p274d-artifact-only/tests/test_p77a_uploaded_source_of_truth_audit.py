"""
test_p77a_uploaded_source_of_truth_audit.py

P77A Uploaded Source-of-Truth Audit Tests

Governance:
- No DB write
- No draw insert
- No replay row insert
- No official API call
- Production replay rows must remain 46960
- POWER_LOTTO draws > 115000040 must remain 0 in production DB
"""
import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_C1_PATH = REPO_ROOT / "backups" / "lottery_v2_pre_p66_wave6_20260525_093850.db"
P77A_JSON = REPO_ROOT / "outputs" / "replay" / "p77a_uploaded_source_of_truth_audit_20260526.json"
P77A_MD = REPO_ROOT / "docs" / "replay" / "p77a_uploaded_source_of_truth_audit_20260526.md"
PRODUCTION_ROWS = 46960
POWER_LOTTO_MAX_DRAW = 115000040


@pytest.fixture(scope="module")
def prod_db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def p77a_json():
    assert P77A_JSON.exists(), f"P77A JSON not found: {P77A_JSON}"
    with open(P77A_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestP77AArtifacts:
    def test_json_exists(self):
        assert P77A_JSON.exists()

    def test_md_exists(self):
        assert P77A_MD.exists()

    def test_json_task_is_p77a(self, p77a_json):
        assert p77a_json["task"] == "P77A"

    def test_project_context_lock(self, p77a_json):
        assert p77a_json["project_context_lock"] == "LotteryNew"

    def test_classification_correct(self, p77a_json):
        assert p77a_json["final_classification"] == "P77A_SOURCE_HAS_NEW_DRAWS_DB_IMPORT_INCOMPLETE"


# ---------------------------------------------------------------------------
# 2. Governance
# ---------------------------------------------------------------------------
class TestP77AGovernance:
    def test_no_db_write(self, p77a_json):
        assert p77a_json["governance"]["no_db_write"] is True

    def test_no_draw_insert(self, p77a_json):
        assert p77a_json["governance"]["no_draw_insert"] is True

    def test_no_replay_row_insert(self, p77a_json):
        assert p77a_json["governance"]["no_replay_row_insert"] is True

    def test_no_official_api_call(self, p77a_json):
        assert p77a_json["governance"]["no_official_api_call"] is True

    def test_no_new_tables(self, p77a_json):
        assert p77a_json["governance"]["no_new_tables"] is True

    def test_production_rows_before(self, p77a_json):
        assert p77a_json["governance"]["production_rows_before"] == PRODUCTION_ROWS

    def test_production_rows_after(self, p77a_json):
        assert p77a_json["governance"]["production_rows_after"] == PRODUCTION_ROWS


# ---------------------------------------------------------------------------
# 3. Production DB unchanged
# ---------------------------------------------------------------------------
class TestProductionDBUnchanged:
    def test_production_replay_rows_unchanged(self, prod_db):
        cur = prod_db.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert cur.fetchone()[0] == PRODUCTION_ROWS

    def test_power_lotto_max_draw_unchanged(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        assert cur.fetchone()[0] == POWER_LOTTO_MAX_DRAW

    def test_power_lotto_draws_after_max_still_zero(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' "
            "AND CAST(draw AS INTEGER) > 115000040"
        )
        assert cur.fetchone()[0] == 0

    def test_power_lotto_total_draws(self, prod_db):
        cur = prod_db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'"
        )
        assert cur.fetchone()[0] == 1912


# ---------------------------------------------------------------------------
# 4. Preflight results in JSON
# ---------------------------------------------------------------------------
class TestPreflight:
    def test_preflight_rows(self, p77a_json):
        assert p77a_json["preflight"]["production_replay_rows"] == PRODUCTION_ROWS

    def test_preflight_max_draw(self, p77a_json):
        assert p77a_json["preflight"]["power_lotto_max_draw_in_db"] == "115000040"

    def test_preflight_draws_after_max(self, p77a_json):
        assert p77a_json["preflight"]["power_lotto_draws_after_115000040"] == 0

    def test_preflight_drift_guard(self, p77a_json):
        assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in p77a_json["preflight"]["drift_guard"]

    def test_preflight_branch_governance(self, p77a_json):
        assert "BRANCH_GOVERNANCE_PASS" in p77a_json["preflight"]["branch_governance_guard_pre"]


# ---------------------------------------------------------------------------
# 5. Source candidate C1 — backup with draw 115000041
# ---------------------------------------------------------------------------
class TestC1BackupPrimarySource:
    def test_backup_c1_exists_on_disk(self):
        assert BACKUP_C1_PATH.exists(), f"Backup C1 not found at {BACKUP_C1_PATH}"

    def test_backup_c1_in_candidates(self, p77a_json):
        candidates = p77a_json["source_candidates_inspected"]
        c1 = next((c for c in candidates if c["candidate_id"] == "C1"), None)
        assert c1 is not None, "Candidate C1 not found in audit"

    def test_backup_c1_contains_115000041(self, p77a_json):
        candidates = p77a_json["source_candidates_inspected"]
        c1 = next(c for c in candidates if c["candidate_id"] == "C1")
        assert c1["contains_115000041_plus"] is True

    def test_backup_c1_power_lotto_max_draw(self, p77a_json):
        candidates = p77a_json["source_candidates_inspected"]
        c1 = next(c for c in candidates if c["candidate_id"] == "C1")
        assert c1["power_lotto_max_draw"] == 115000041

    def test_backup_c1_draw_detail_present(self, p77a_json):
        candidates = p77a_json["source_candidates_inspected"]
        c1 = next(c for c in candidates if c["candidate_id"] == "C1")
        detail = c1["draw_115000041_detail"]
        assert detail["draw"] == "115000041"
        assert detail["date"] == "2026/05/21"
        assert detail["lottery_type"] == "POWER_LOTTO"
        assert detail["special"] == 1

    def test_backup_c1_draw_numbers(self, p77a_json):
        candidates = p77a_json["source_candidates_inspected"]
        c1 = next(c for c in candidates if c["candidate_id"] == "C1")
        nums = c1["draw_115000041_detail"]["numbers"]
        assert nums == [6, 14, 22, 28, 35, 38]
        assert len(nums) == 6
        assert all(1 <= n <= 38 for n in nums)

    def test_backup_c1_in_db_read_only(self):
        """Verify draw 115000041 exists in C1 by reading the backup DB (read-only)."""
        conn = sqlite3.connect(f"file:{BACKUP_C1_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type='POWER_LOTTO' AND draw='115000041'"
        )
        row = cur.fetchone()
        conn.close()
        assert row is not None, "Draw 115000041 not found in backup C1"
        assert row[0] == "115000041"
        assert row[1] == "2026/05/21"
        assert row[3] == 1  # special

    def test_backup_c1_power_lotto_draws_after_max(self):
        """Verify backup C1 has exactly 1 draw after 115000040."""
        conn = sqlite3.connect(f"file:{BACKUP_C1_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' "
            "AND CAST(draw AS INTEGER) > 115000040"
        )
        count = cur.fetchone()[0]
        conn.close()
        assert count == 1


# ---------------------------------------------------------------------------
# 6. Source-of-truth conclusion
# ---------------------------------------------------------------------------
class TestSourceConclusion:
    def test_draw_115000041_confirmed(self, p77a_json):
        conclusion = p77a_json["source_of_truth_conclusion"]
        assert conclusion["draw_115000041_confirmed"] is True

    def test_draw_115000041_source_is_c1(self, p77a_json):
        conclusion = p77a_json["source_of_truth_conclusion"]
        assert "lottery_v2_pre_p66_wave6_20260525_093850.db" in conclusion["draw_115000041_source"]

    def test_draw_115000042_plus_not_in_local(self, p77a_json):
        conclusion = p77a_json["source_of_truth_conclusion"]
        assert conclusion["draw_115000042_plus_in_local_source"] is False

    def test_no_fabrication_required(self, p77a_json):
        conclusion = p77a_json["source_of_truth_conclusion"]
        assert conclusion["no_fabrication_required"] is True

    def test_data_is_real(self, p77a_json):
        conclusion = p77a_json["source_of_truth_conclusion"]
        assert conclusion["data_is_real"] is True

    def test_classification_in_conclusion(self, p77a_json):
        assert p77a_json["final_classification"] == "P77A_SOURCE_HAS_NEW_DRAWS_DB_IMPORT_INCOMPLETE"


# ---------------------------------------------------------------------------
# 7. Other source candidates — no 115000041+
# ---------------------------------------------------------------------------
class TestOtherCandidatesNegative:
    def _get_candidate(self, p77a_json, cid):
        candidates = p77a_json["source_candidates_inspected"]
        return next((c for c in candidates if c["candidate_id"] == cid), None)

    def test_c2_no_115000041(self, p77a_json):
        c2 = self._get_candidate(p77a_json, "C2")
        assert c2 is not None
        assert c2["contains_115000041_plus"] is False

    def test_c4_no_115000041(self, p77a_json):
        c4 = self._get_candidate(p77a_json, "C4")
        assert c4 is not None
        assert c4["contains_115000041_plus"] is False

    def test_c6_lottery_history_no_power_lotto(self, p77a_json):
        c6 = self._get_candidate(p77a_json, "C6")
        assert c6 is not None
        assert c6["contains_115000041_plus"] is False
        assert c6.get("power_lotto_count", 0) == 0

    def test_c7_csv_no_power_lotto(self, p77a_json):
        c7 = self._get_candidate(p77a_json, "C7")
        assert c7 is not None
        assert c7["contains_115000041_plus"] is False

    def test_ingest_log_no_115000041_entry(self, p77a_json):
        c11 = self._get_candidate(p77a_json, "C11")
        assert c11 is not None
        assert c11["mentions_115000041"] is False


# ---------------------------------------------------------------------------
# 8. Recommended next phase
# ---------------------------------------------------------------------------
class TestRecommendedNextPhase:
    def test_recommended_phase_is_p77b(self, p77a_json):
        assert p77a_json["recommended_next_phase"]["phase"] == "P77B"

    def test_p77b_uses_existing_draws_table(self, p77a_json):
        constraints = p77a_json["recommended_next_phase"]["constraints"]
        assert any("canonical draws table" in c or "existing canonical" in c for c in constraints)

    def test_p77b_no_replay_inserts(self, p77a_json):
        constraints = p77a_json["recommended_next_phase"]["constraints"]
        assert any("replay" in c.lower() for c in constraints)

    def test_p77b_unblocks_batch_a(self, p77a_json):
        unblocks = p77a_json["recommended_next_phase"]["unblocks"]
        assert "fourier_rhythm_3bet" in unblocks
        assert "fourier30_markov30_2bet" in unblocks


# ---------------------------------------------------------------------------
# 9. Forbidden staging scan
# ---------------------------------------------------------------------------
class TestForbiddenStagingScan:
    def test_forbidden_staging_clean(self, p77a_json):
        scan = p77a_json["forbidden_staging_scan"]
        assert scan["db_files_staged"] is False
        assert scan["backup_files_staged"] is False
        assert scan["pid_runtime_files_staged"] is False
        assert scan["overall"] == "STAGE_CLEAN"


# ---------------------------------------------------------------------------
# 10. MD content checks
# ---------------------------------------------------------------------------
class TestMDContent:
    def test_md_contains_classification(self):
        content = P77A_MD.read_text()
        assert "P77A_SOURCE_HAS_NEW_DRAWS_DB_IMPORT_INCOMPLETE" in content

    def test_md_contains_draw_115000041(self):
        content = P77A_MD.read_text()
        assert "115000041" in content

    def test_md_contains_backup_path(self):
        content = P77A_MD.read_text()
        assert "lottery_v2_pre_p66_wave6_20260525_093850.db" in content

    def test_md_contains_draw_numbers(self):
        content = P77A_MD.read_text()
        assert "6, 14, 22, 28, 35, 38" in content

    def test_md_contains_p77b_recommendation(self):
        content = P77A_MD.read_text()
        assert "P77B" in content

    def test_md_no_db_write_confirmed(self):
        content = P77A_MD.read_text()
        assert "No DB write" in content or "no_db_write" in content.lower() or "No DB writes" in content

    def test_md_no_row_insert_claimed(self):
        content = P77A_MD.read_text().lower()
        assert "replay row insert" not in content or "no replay row insert" in content
