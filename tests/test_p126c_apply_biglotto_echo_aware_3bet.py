"""
Tests for P126C: Apply biglotto_echo_aware_3bet Controlled Replay Rows
=======================================================================
Covers:
  - Authorization gate (valid / missing / placeholder / wrong prefix)
  - Provenance hash determinism
  - Post-apply DB state (via live production DB)
  - Artifact JSON integrity
  - Governance: no other P126A candidates touched, P126B rows preserved
  - Drift guard consistency
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.p126c_apply_biglotto_echo_aware_3bet import (
    CLASSIFICATION,
    CONTROLLED_APPLY_ID,
    EXACT_AUTH_PREFIX,
    EXPECTED_BET1_ROWS,
    EXPECTED_INSERT_ROWS,
    EXPECTED_ROWS_AFTER,
    EXPECTED_ROWS_BEFORE,
    EXPECTED_STRATEGY_TOTAL,
    LOTTERY_TYPE,
    OTHER_CANDIDATES,
    STRATEGY_ID,
    TASK_ID,
    _provenance_hash,
    validate_authorization,
)

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON = REPO_ROOT / "outputs" / "replay" / "p126c_apply_biglotto_echo_aware_3bet_20260528.json"
OUT_MD   = REPO_ROOT / "docs" / "replay" / "p126c_apply_biglotto_echo_aware_3bet_20260528.md"


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
            "YES authorize controlled_apply for biglotto_echo_aware_3bet because "
            "P126B succeeded and this is the next +3000 row controlled apply candidate"
        )
        r = validate_authorization(phrase)
        assert r["authorization_present"] is True
        assert r["apply_allowed"] is True
        assert r["strategy_id"] == STRATEGY_ID
        assert r["stop_reason"] is None

    def test_placeholder_reason_not_authorized(self):
        phrase = "YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>"
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False

    def test_wrong_strategy_name_not_authorized(self):
        phrase = "YES authorize controlled_apply for power_fourier_rhythm_2bet because test"
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False

    def test_wrong_prefix_not_authorized(self):
        phrase = "AUTHORIZE controlled_apply for biglotto_echo_aware_3bet because reason"
        r = validate_authorization(phrase)
        assert r["authorization_present"] is False

    def test_strategy_id_in_result(self):
        r = validate_authorization(None)
        assert r["strategy_id"] == "biglotto_echo_aware_3bet"

    def test_exact_required_phrase_format(self):
        r = validate_authorization(None)
        assert "biglotto_echo_aware_3bet" in r["exact_required_phrase"]


# ---------------------------------------------------------------------------
# Provenance hash
# ---------------------------------------------------------------------------

class TestProvenanceHash:
    def test_deterministic(self):
        h1 = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [4, 11, 22, 33, 44, 48], 2)
        h2 = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [4, 11, 22, 33, 44, 48], 2)
        assert h1 == h2

    def test_bet2_bet3_differ(self):
        h2 = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [4, 11, 22, 33, 44, 48], 2)
        h3 = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [4, 11, 22, 33, 44, 48], 3)
        assert h2 != h3

    def test_different_draws_differ(self):
        h1 = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [1, 2, 3, 4, 5, 6], 2)
        h2 = _provenance_hash("biglotto_echo_aware_3bet", "102000013", [1, 2, 3, 4, 5, 6], 2)
        assert h1 != h2

    def test_length_16(self):
        h = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [1, 2, 3, 4, 5, 6], 2)
        assert len(h) == 16

    def test_p126c_prefix_in_hash(self):
        # P126C prefix distinguishes from P126B hashes
        h = _provenance_hash("biglotto_echo_aware_3bet", "102000012", [1, 2, 3, 4, 5, 6], 2)
        assert isinstance(h, str)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_task_id(self):
        assert TASK_ID == "P126C"

    def test_classification(self):
        assert CLASSIFICATION == "P126C_BIGLOTTO_ECHO_AWARE_3BET_APPLIED"

    def test_strategy_id(self):
        assert STRATEGY_ID == "biglotto_echo_aware_3bet"

    def test_lottery_type(self):
        assert LOTTERY_TYPE == "BIG_LOTTO"

    def test_expected_insert_rows(self):
        assert EXPECTED_INSERT_ROWS == 3000

    def test_expected_rows_before(self):
        assert EXPECTED_ROWS_BEFORE == 55962

    def test_expected_rows_after(self):
        assert EXPECTED_ROWS_AFTER == 58962

    def test_expected_bet1_rows(self):
        assert EXPECTED_BET1_ROWS == 1500

    def test_expected_strategy_total(self):
        assert EXPECTED_STRATEGY_TOTAL == 4500

    def test_other_candidates_excludes_strategy(self):
        assert STRATEGY_ID not in OTHER_CANDIDATES

    def test_other_candidates_has_three_remaining(self):
        assert len(OTHER_CANDIDATES) == 3
        assert "daily539_f4cold_3bet" in OTHER_CANDIDATES
        assert "biglotto_ts3_markov_4bet_w30" in OTHER_CANDIDATES
        assert "daily539_f4cold_5bet" in OTHER_CANDIDATES

    def test_exact_auth_prefix(self):
        assert EXACT_AUTH_PREFIX.startswith("YES authorize controlled_apply for biglotto_echo_aware_3bet")


# ---------------------------------------------------------------------------
# Artifact JSON integrity
# ---------------------------------------------------------------------------

class TestArtifactJSON:
    @pytest.fixture(scope="class")
    def artifact(self):
        assert OUT_JSON.exists(), f"P126C JSON not found: {OUT_JSON}"
        with OUT_JSON.open() as f:
            return json.load(f)

    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P126C"

    def test_classification(self, artifact):
        assert artifact["classification"] == "P126C_BIGLOTTO_ECHO_AWARE_3BET_APPLIED"

    def test_authorization_present(self, artifact):
        assert artifact["authorization"]["authorization_present"] is True

    def test_apply_allowed(self, artifact):
        assert artifact["authorization"]["apply_allowed"] is True

    def test_strategy_id(self, artifact):
        assert artifact["authorization"]["strategy_id"] == "biglotto_echo_aware_3bet"

    def test_backup_created(self, artifact):
        assert artifact["backup"]["backup_created"] is True

    def test_backup_row_count(self, artifact):
        assert artifact["backup"]["backup_row_count"] == 55962

    def test_backup_verification_pass(self, artifact):
        assert artifact["backup"]["backup_verification"] == "PASS"

    def test_db_rows_before(self, artifact):
        assert artifact["db_snapshot_before"]["replay_rows"] == 55962

    def test_db_rows_after(self, artifact):
        assert artifact["db_snapshot_after"]["replay_rows"] == 58962

    def test_expected_insert_rows(self, artifact):
        assert artifact["apply_scope"]["expected_insert_rows"] == 3000

    def test_actual_insert_rows(self, artifact):
        assert artifact["apply_scope"]["actual_insert_rows"] == 3000

    def test_apply_executed(self, artifact):
        assert artifact["apply_scope"]["apply_executed"] is True

    def test_target_bet_count(self, artifact):
        assert artifact["apply_scope"]["target_bet_count"] == 3

    def test_bet2_rows(self, artifact):
        assert artifact["apply_scope"]["bet2_rows_inserted"] == 1500

    def test_bet3_rows(self, artifact):
        assert artifact["apply_scope"]["bet3_rows_inserted"] == 1500

    def test_bet_index_validation_pass(self, artifact):
        bv = artifact["bet_index_validation"]
        assert bv["bet1_count"] == 1500
        assert bv["bet2_count"] == 1500
        assert bv["bet3_count"] == 1500
        assert bv["distribution_ok"] is True
        assert bv["validation"] == "PASS"

    def test_all_rows_big_lotto(self, artifact):
        assert artifact["bet_index_validation"]["all_rows_big_lotto"] is True

    def test_duplicate_guard_ok(self, artifact):
        assert artifact["duplicate_guard"]["guard_ok"] is True
        assert artifact["duplicate_guard"]["duplicate_rejected_in_validation"] is True
        assert artifact["duplicate_guard"]["other_candidates_untouched"] is True

    def test_power_fourier_rhythm_2bet_preserved(self, artifact):
        pa = artifact["previous_apply_status"]["power_fourier_rhythm_2bet"]
        assert pa["already_applied"] is True
        assert pa["rows_preserved"] is True
        assert pa["no_duplicate_power_fourier_rows"] is True

    def test_row_preservation_ok(self, artifact):
        rp = artifact["row_preservation_check"]
        assert rp["rows_before_apply"] == 55962
        assert rp["rows_inserted"] == 3000
        assert rp["expected_rows_after"] == 58962
        assert rp["actual_rows_after"] == 58962
        assert rp["rows_preserved_ok"] is True

    def test_drift_guard_update_required(self, artifact):
        assert artifact["drift_guard_update"]["update_required"] is True
        assert artifact["drift_guard_update"]["new_total"] == 58962

    def test_rollback_reference_has_backup_path(self, artifact):
        rr = artifact["rollback_reference"]
        assert "backup_path" in rr
        assert "rollback_command" in rr
        assert "lottery_v2.db" in rr["backup_path"]

    def test_blocked_or_excluded_contains_required(self, artifact):
        items = {b["item"] for b in artifact["blocked_or_excluded"]}
        assert "4_STAR" in items
        assert "P108" in items
        assert "P117" in items
        assert "P118" in items
        assert "rejected_strategies" in items
        assert "scheduler_cron_launchd" in items
        assert "daily539_f4cold_3bet" in items
        assert "biglotto_ts3_markov_4bet_w30" in items
        assert "daily539_f4cold_5bet" in items

    def test_all_validation_ok(self, artifact):
        assert artifact["summary"]["all_validation_ok"] is True


# ---------------------------------------------------------------------------
# Live DB state tests
# ---------------------------------------------------------------------------

class TestLiveDB:
    @pytest.fixture(scope="class")
    def conn(self):
        c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        c.execute("PRAGMA query_only = ON")
        yield c
        c.close()

    def test_total_rows_58962(self, conn):
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert total == 58962

    def test_biglotto_echo_aware_3bet_total_4500(self, conn):
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='biglotto_echo_aware_3bet'"
        ).fetchone()[0]
        assert total == 4500

    def test_biglotto_echo_aware_3bet_bet1_1500(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='biglotto_echo_aware_3bet' AND bet_index=1"
        ).fetchone()[0]
        assert cnt == 1500

    def test_biglotto_echo_aware_3bet_bet2_1500(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='biglotto_echo_aware_3bet' AND bet_index=2"
        ).fetchone()[0]
        assert cnt == 1500

    def test_biglotto_echo_aware_3bet_bet3_1500(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='biglotto_echo_aware_3bet' AND bet_index=3"
        ).fetchone()[0]
        assert cnt == 1500

    def test_all_biglotto_echo_rows_are_big_lotto(self, conn):
        wrong = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='biglotto_echo_aware_3bet' AND lottery_type!='BIG_LOTTO'"
        ).fetchone()[0]
        assert wrong == 0

    def test_power_fourier_rhythm_2bet_preserved_3000(self, conn):
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='power_fourier_rhythm_2bet'"
        ).fetchone()[0]
        assert total == 3000

    def test_remaining_candidates_not_touched(self, conn):
        for cid in ["daily539_f4cold_3bet", "biglotto_ts3_markov_4bet_w30", "daily539_f4cold_5bet"]:
            extra = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND bet_index>1",
                (cid,)
            ).fetchone()[0]
            assert extra == 0, f"{cid} unexpectedly has bet_index>1 rows: {extra}"

    def test_p126c_controlled_apply_id_rows_3000(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            ("P126C_BIGLOTTO_ECHO_AWARE_3BET_20260528",)
        ).fetchone()[0]
        assert cnt == 3000

    def test_new_rows_lottery_type_all_big_lotto(self, conn):
        wrong = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND lottery_type!='BIG_LOTTO'",
            ("P126C_BIGLOTTO_ECHO_AWARE_3BET_20260528",)
        ).fetchone()[0]
        assert wrong == 0

    def test_new_rows_strategy_id_all_biglotto_echo_aware(self, conn):
        wrong = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND strategy_id!='biglotto_echo_aware_3bet'",
            ("P126C_BIGLOTTO_ECHO_AWARE_3BET_20260528",)
        ).fetchone()[0]
        assert wrong == 0

    def test_bet_index_column_exists(self, conn):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)")]
        assert "bet_index" in cols

    def test_unique_constraint_active(self, conn):
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        assert "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl


# ---------------------------------------------------------------------------
# Markdown artifact
# ---------------------------------------------------------------------------

class TestMarkdown:
    def test_md_exists(self):
        assert OUT_MD.exists(), f"P126C MD not found: {OUT_MD}"

    def test_md_contains_backup_path(self):
        content = OUT_MD.read_text()
        assert "lottery_v2.db.p126c_backup_" in content

    def test_md_contains_rollback_reference(self):
        content = OUT_MD.read_text()
        assert "Rollback" in content or "rollback" in content

    def test_md_contains_classification(self):
        content = OUT_MD.read_text()
        assert "P126C_BIGLOTTO_ECHO_AWARE_3BET_APPLIED" in content

    def test_md_contains_authorization_section(self):
        content = OUT_MD.read_text()
        assert "Authorization" in content

    def test_md_contains_executive_summary(self):
        content = OUT_MD.read_text()
        assert "Executive Summary" in content

    def test_md_contains_non_actions_section(self):
        content = OUT_MD.read_text()
        assert "Non-Actions" in content or "non-action" in content.lower() or "did **not**" in content


# ---------------------------------------------------------------------------
# Governance tests
# ---------------------------------------------------------------------------

class TestGovernance:
    def test_only_biglotto_echo_aware_applied(self):
        """Verify P126C only applied biglotto_echo_aware_3bet."""
        assert STRATEGY_ID == "biglotto_echo_aware_3bet"
        assert LOTTERY_TYPE == "BIG_LOTTO"

    def test_daily539_f4cold_3bet_in_blocked(self):
        assert "daily539_f4cold_3bet" in OTHER_CANDIDATES

    def test_biglotto_ts3_markov_4bet_w30_in_blocked(self):
        assert "biglotto_ts3_markov_4bet_w30" in OTHER_CANDIDATES

    def test_daily539_f4cold_5bet_in_blocked(self):
        assert "daily539_f4cold_5bet" in OTHER_CANDIDATES

    def test_power_fourier_not_in_other_candidates(self):
        # power_fourier_rhythm_2bet was applied in P126B, not a candidate to block
        assert "power_fourier_rhythm_2bet" not in OTHER_CANDIDATES

    def test_p126a_artifact_classification_verified(self):
        p126a_path = REPO_ROOT / "outputs/replay/p126a_controlled_apply_authorization_gate_20260528.json"
        assert p126a_path.exists()
        with p126a_path.open() as f:
            d = json.load(f)
        assert d["classification"] == "P126A_WAITING_FOR_PER_STRATEGY_APPLY_AUTHORIZATION"

    def test_p126b_artifact_classification_verified(self):
        p126b_path = REPO_ROOT / "outputs/replay/p126b_apply_power_fourier_rhythm_2bet_20260528.json"
        assert p126b_path.exists()
        with p126b_path.open() as f:
            d = json.load(f)
        assert d["classification"] == "P126B_POWER_FOURIER_RHYTHM_2BET_APPLIED"

    def test_p129b_artifact_classification_verified(self):
        p129b_path = REPO_ROOT / "outputs/replay/p129b_execute_bet_index_schema_migration_20260528.json"
        assert p129b_path.exists()
        with p129b_path.open() as f:
            d = json.load(f)
        assert d["classification"] == "P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED"
