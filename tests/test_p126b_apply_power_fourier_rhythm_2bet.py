"""
Tests for P126B: Apply power_fourier_rhythm_2bet Controlled Replay Rows
=======================================================================
Covers:
  - Authorization gate (valid / missing / placeholder / wrong prefix)
  - Provenance hash determinism
  - Post-apply DB state (via live production DB)
  - Artifact JSON integrity
  - Governance: no other P126A candidates touched
  - Drift guard consistency
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.p126b_apply_power_fourier_rhythm_2bet import (
    CLASSIFICATION,
    CONTROLLED_APPLY_ID,
    EXACT_AUTH_PREFIX,
    EXPECTED_INSERT_ROWS,
    EXPECTED_ROWS_AFTER,
    EXPECTED_ROWS_BEFORE,
    EXPECTED_STRATEGY_ROWS,
    LOTTERY_TYPE,
    OTHER_CANDIDATES,
    STRATEGY_ID,
    TASK_ID,
    _provenance_hash,
    validate_authorization,
)

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON = REPO_ROOT / "outputs" / "replay" / "p126b_apply_power_fourier_rhythm_2bet_20260528.json"


# ---------------------------------------------------------------------------
# Authorization gate tests
# ---------------------------------------------------------------------------

class TestValidateAuthorization:
    def test_none_returns_not_authorized(self):
        r = validate_authorization(None)
        assert r["authorization_present"] is False
        assert r["apply_allowed"] is False
        assert r["stop_reason"] == "NO_AUTHORIZATION_TEXT_PROVIDED"

    def test_empty_string_returns_not_authorized(self):
        r = validate_authorization("")
        assert r["authorization_present"] is False

    def test_exact_valid_phrase_authorized(self):
        phrase = (
            "YES authorize controlled_apply for power_fourier_rhythm_2bet because "
            "P126A confirmed bet_index schema is ready and this is the lowest-risk +1500 row candidate"
        )
        r = validate_authorization(phrase)
        assert r["authorization_present"] is True
        assert r["apply_allowed"] is True
        assert r["stop_reason"] is None
        assert "P126A confirmed" in r["reason_text"]

    def test_placeholder_reason_blocked(self):
        phrase = f"{EXACT_AUTH_PREFIX}<reason>"
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False
        assert r["apply_allowed"] is False

    def test_wrong_strategy_prefix_blocked(self):
        phrase = "YES authorize controlled_apply for daily539_f4cold_3bet because some reason"
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False

    def test_missing_because_blocked(self):
        phrase = "YES authorize controlled_apply for power_fourier_rhythm_2bet and more"
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False

    def test_lowercase_no_not_authorized(self):
        phrase = (
            "yes authorize controlled_apply for power_fourier_rhythm_2bet because reason"
        )
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False

    def test_returns_strategy_id(self):
        r = validate_authorization(None)
        assert r["strategy_id"] == STRATEGY_ID

    def test_exact_required_phrase_contains_placeholder(self):
        r = validate_authorization(None)
        assert "<reason>" in r["exact_required_phrase"]
        assert EXACT_AUTH_PREFIX in r["exact_required_phrase"]

    def test_valid_phrase_strips_whitespace(self):
        phrase = f"  {EXACT_AUTH_PREFIX}some reason  "
        r = validate_authorization(phrase)
        assert r["authorization_present"] is True

    def test_stop_reason_invalid_phrase(self):
        r = validate_authorization("not the right thing")
        assert r["stop_reason"] == "AUTHORIZATION_PHRASE_INVALID_OR_PLACEHOLDER"


# ---------------------------------------------------------------------------
# Provenance hash tests
# ---------------------------------------------------------------------------

class TestProvenanceHash:
    def test_deterministic(self):
        h1 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [2, 8, 14, 20, 26, 32], 2)
        h2 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [2, 8, 14, 20, 26, 32], 2)
        assert h1 == h2

    def test_hex_16_chars(self):
        h = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [1, 2, 3, 4, 5, 6], 2)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_draw_different_hash(self):
        h1 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [1, 2, 3, 4, 5, 6], 2)
        h2 = _provenance_hash("power_fourier_rhythm_2bet", "101000004", [1, 2, 3, 4, 5, 6], 2)
        assert h1 != h2

    def test_different_bet_index_different_hash(self):
        h1 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [1, 2, 3, 4, 5, 6], 1)
        h2 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [1, 2, 3, 4, 5, 6], 2)
        assert h1 != h2

    def test_different_numbers_different_hash(self):
        h1 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [1, 2, 3, 4, 5, 6], 2)
        h2 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [7, 8, 9, 10, 11, 12], 2)
        assert h1 != h2

    def test_unsorted_input_same_as_sorted(self):
        h1 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [6, 5, 4, 3, 2, 1], 2)
        h2 = _provenance_hash("power_fourier_rhythm_2bet", "101000003", [1, 2, 3, 4, 5, 6], 2)
        assert h1 == h2


# ---------------------------------------------------------------------------
# Constants integrity tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_task_id(self):
        assert TASK_ID == "P126B"

    def test_classification(self):
        assert CLASSIFICATION == "P126B_POWER_FOURIER_RHYTHM_2BET_APPLIED"

    def test_strategy_id(self):
        assert STRATEGY_ID == "power_fourier_rhythm_2bet"

    def test_lottery_type(self):
        assert LOTTERY_TYPE == "POWER_LOTTO"

    def test_controlled_apply_id(self):
        assert CONTROLLED_APPLY_ID == "P126B_POWER_FOURIER_RHYTHM_2BET_20260528"

    def test_expected_rows_before(self):
        assert EXPECTED_ROWS_BEFORE == 54462

    def test_expected_rows_after(self):
        assert EXPECTED_ROWS_AFTER == 55962

    def test_expected_insert(self):
        assert EXPECTED_INSERT_ROWS == 1500

    def test_expected_strategy_rows(self):
        assert EXPECTED_STRATEGY_ROWS == 3000

    def test_delta_consistent(self):
        assert EXPECTED_ROWS_AFTER - EXPECTED_ROWS_BEFORE == EXPECTED_INSERT_ROWS

    def test_other_candidates_count(self):
        assert len(OTHER_CANDIDATES) == 4

    def test_other_candidates_names(self):
        expected = {
            "daily539_f4cold_3bet",
            "biglotto_echo_aware_3bet",
            "biglotto_ts3_markov_4bet_w30",
            "daily539_f4cold_5bet",
        }
        assert set(OTHER_CANDIDATES) == expected

    def test_strategy_not_in_other_candidates(self):
        assert STRATEGY_ID not in OTHER_CANDIDATES

    def test_exact_auth_prefix(self):
        assert EXACT_AUTH_PREFIX == "YES authorize controlled_apply for power_fourier_rhythm_2bet because "


# ---------------------------------------------------------------------------
# Live production DB tests (post-apply)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not DB_PATH.exists(), reason="production DB not present")
class TestLiveProductionDB:
    def _conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    def test_total_row_count(self):
        conn = self._conn()
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        # After P126C applied 3000 biglotto_echo_aware_3bet rows, total is 58962
        assert total >= EXPECTED_ROWS_AFTER, f"Expected >= {EXPECTED_ROWS_AFTER}, got {total}"

    def test_strategy_total_rows(self):
        conn = self._conn()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (STRATEGY_ID,)
        ).fetchone()[0]
        conn.close()
        assert cnt == EXPECTED_STRATEGY_ROWS

    def test_bet1_count(self):
        conn = self._conn()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=1",
            (STRATEGY_ID,)
        ).fetchone()[0]
        conn.close()
        assert cnt == 1500

    def test_bet2_count(self):
        conn = self._conn()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchone()[0]
        conn.close()
        assert cnt == 1500

    def test_bet2_controlled_apply_id(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT controlled_apply_id FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        ids = {r[0] for r in rows}
        assert ids == {CONTROLLED_APPLY_ID}

    def test_bet2_source(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT source FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        sources = {r[0] for r in rows}
        assert sources == {"P126B_CONTROLLED_APPLY"}

    def test_bet2_truth_level(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT truth_level FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        tls = {r[0] for r in rows}
        assert tls == {"TIERB_DRYRUN_VALIDATED"}

    def test_bet2_dry_run_zero(self):
        conn = self._conn()
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2 AND dry_run!=0",
            (STRATEGY_ID,)
        ).fetchone()[0]
        conn.close()
        assert cnt == 0

    def test_bet2_lottery_type(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT lottery_type FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        types = {r[0] for r in rows}
        assert types == {LOTTERY_TYPE}

    def test_bet2_predicted_numbers_valid_json(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2 LIMIT 20",
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        for row in rows:
            nums = json.loads(row[0])
            assert len(nums) == 6
            for n in nums:
                assert 1 <= int(n) <= 38

    def test_bet2_predicted_numbers_sorted(self):
        conn = self._conn()
        rows = conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2 LIMIT 50",
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        for row in rows:
            nums = json.loads(row[0])
            assert nums == sorted(nums)

    def test_bet2_no_duplicates_within_draw(self):
        conn = self._conn()
        # Each (lottery_type, target_draw, strategy_id, bet_index) must be unique
        dups = conn.execute(
            """
            SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*) as cnt
            FROM strategy_prediction_replays
            WHERE strategy_id=? AND bet_index=2
            GROUP BY lottery_type, target_draw, strategy_id, bet_index
            HAVING cnt > 1
            """,
            (STRATEGY_ID,)
        ).fetchall()
        conn.close()
        assert len(dups) == 0

    def test_bet2_draws_match_bet1_draws(self):
        conn = self._conn()
        bet1_draws = set(
            r[0] for r in conn.execute(
                "SELECT target_draw FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND bet_index=1",
                (STRATEGY_ID,)
            ).fetchall()
        )
        bet2_draws = set(
            r[0] for r in conn.execute(
                "SELECT target_draw FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND bet_index=2",
                (STRATEGY_ID,)
            ).fetchall()
        )
        conn.close()
        assert bet1_draws == bet2_draws

    def test_bet2_provenance_hashes_unique(self):
        conn = self._conn()
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchone()[0]
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT provenance_hash) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchone()[0]
        conn.close()
        assert distinct == total

    def test_other_candidates_not_bet2_touched(self):
        conn = self._conn()
        for cid in OTHER_CANDIDATES:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND controlled_apply_id=?",
                (cid, CONTROLLED_APPLY_ID)
            ).fetchone()[0]
            assert cnt == 0, f"{cid} was touched by P126B controlled_apply_id"
        conn.close()

    def test_other_candidates_row_count_unchanged(self):
        """P126F applied daily539_f4cold_5bet bet-2..bet-5 after P126B/C/D/E.
        All 5 Tier-B candidates are now complete. Verify post-P126F state:
        daily539_f4cold_5bet has exactly 6000 extra bet rows (bet_index>1)."""
        conn = self._conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='daily539_f4cold_5bet' AND bet_index>1"
        ).fetchone()[0]
        assert count == 6000, f"Expected 6000 (P126F applied), got {count}"
        conn.close()

    def test_bet_index_column_exists(self):
        conn = self._conn()
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(strategy_prediction_replays)"
        ).fetchall()]
        conn.close()
        assert "bet_index" in cols

    def test_unique_constraint_on_bet_index(self):
        conn = self._conn()
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        conn.close()
        assert "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl

    def test_duplicate_insert_rejected(self):
        """Attempting to insert a duplicate (bet_index=2) must raise IntegrityError."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            row = conn.execute(
                "SELECT lottery_type, target_draw, strategy_id, bet_index "
                "FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2 LIMIT 1",
                (STRATEGY_ID,)
            ).fetchone()
            assert row is not None
            lt, td, sid, bi = row
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO strategy_prediction_replays "
                    "(lottery_type, target_draw, strategy_id, bet_index, "
                    " replay_status, predicted_numbers) "
                    "VALUES (?,?,?,?,'PREDICTED','[1,2,3,4,5,6]')",
                    (lt, td, sid, bi)
                )
        finally:
            conn.execute("ROLLBACK")
            conn.close()


# ---------------------------------------------------------------------------
# Artifact JSON tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not OUT_JSON.exists(), reason="P126B output JSON not generated yet")
class TestArtifactJSON:
    @pytest.fixture(scope="class")
    def data(self):
        return json.loads(OUT_JSON.read_text())

    def test_task_id(self, data):
        assert data["task_id"] == "P126B"

    def test_classification(self, data):
        assert data["classification"] == CLASSIFICATION

    def test_strategy_id(self, data):
        assert data["apply_scope"]["strategy_id"] == STRATEGY_ID

    def test_lottery_type(self, data):
        assert data["apply_scope"]["lottery_type"] == LOTTERY_TYPE

    def test_controlled_apply_id(self, data):
        assert data["apply_scope"]["controlled_apply_id"] == CONTROLLED_APPLY_ID

    def test_apply_execution_performed(self, data):
        assert data["apply_scope"]["apply_executed"] is True

    def test_rows_inserted(self, data):
        assert data["apply_scope"]["actual_insert_rows"] == EXPECTED_INSERT_ROWS

    def test_db_before_count(self, data):
        assert data["db_snapshot_before"]["replay_rows"] == EXPECTED_ROWS_BEFORE

    def test_db_after_total(self, data):
        assert data["db_snapshot_after"]["replay_rows"] == EXPECTED_ROWS_AFTER

    def test_db_after_strategy_rows(self, data):
        assert data["db_snapshot_after"]["power_fourier_rhythm_2bet_rows"] == EXPECTED_STRATEGY_ROWS

    def test_db_after_bet1(self, data):
        assert data["bet_index_validation"]["bet1_count"] == 1500

    def test_db_after_bet2(self, data):
        assert data["bet_index_validation"]["bet2_count"] == 1500

    def test_all_validations_ok(self, data):
        assert data["bet_index_validation"]["distribution_ok"] is True

    def test_governance_no_other_applied(self, data):
        assert data["duplicate_guard"]["other_candidates_untouched"] is True
        for cid in OTHER_CANDIDATES:
            assert data["duplicate_guard"]["other_candidates_bet2_inserted"][cid] == 0

    def test_backup_ok(self, data):
        assert data["backup"]["backup_ok"] is True

    def test_backup_row_count_before(self, data):
        assert data["backup"]["backup_row_count"] == EXPECTED_ROWS_BEFORE

    def test_drift_guard_update_total_count(self, data):
        dg = data.get("drift_guard_update", {})
        assert dg.get("new_total") == EXPECTED_ROWS_AFTER

    def test_drift_guard_update_rows_added(self, data):
        dg = data.get("drift_guard_update", {})
        assert dg.get("rows_added") == EXPECTED_INSERT_ROWS

    def test_authorization_confirmed(self, data):
        assert data["authorization"]["authorization_present"] is True
        assert data["authorization"]["apply_allowed"] is True


# ---------------------------------------------------------------------------
# Drift guard consistency test
# ---------------------------------------------------------------------------

class TestDriftGuardBaseline:
    """Verify the drift guard baseline was updated for P126B."""

    def test_drift_guard_has_p126b_apply_id(self):
        from scripts.replay_lifecycle_drift_guard import BASELINE
        assert "p126b_apply_id" in BASELINE

    def test_drift_guard_p126b_apply_id_value(self):
        from scripts.replay_lifecycle_drift_guard import BASELINE
        assert BASELINE["p126b_apply_id"] == CONTROLLED_APPLY_ID

    def test_drift_guard_p126b_count(self):
        from scripts.replay_lifecycle_drift_guard import BASELINE
        assert BASELINE["p126b_count"] == EXPECTED_INSERT_ROWS

    def test_drift_guard_total_count(self):
        from scripts.replay_lifecycle_drift_guard import BASELINE
        # After P126C, total_count was updated to 58962
        assert BASELINE["total_count"] >= EXPECTED_ROWS_AFTER

    def test_tierb_dryrun_validated_in_allowed(self):
        from scripts.replay_lifecycle_drift_guard import ALLOWED_TRUTH_LEVELS
        assert "TIERB_DRYRUN_VALIDATED" in ALLOWED_TRUTH_LEVELS

    def test_p126b_apply_id_in_known_apply_ids_via_run(self):
        """Run drift guard against live DB and confirm PASS."""
        if not DB_PATH.exists():
            pytest.skip("production DB not present")
        from scripts.replay_lifecycle_drift_guard import run_checks
        result = run_checks(DB_PATH)
        assert result["status"] == "PASS", (
            f"Drift guard FAIL: {result['violations']}"
        )
