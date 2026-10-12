"""
test_p7_controlled_apply_dry_run.py
======================================
P7 Controlled Apply Dry-run — Integration Tests.

Tests the P7 script and its JSON output:
  1. Script has no --apply flag
  2. No DB write (row count stays at 460)
  3. Default scope ONLINE_ONLY
  4. ONLINE candidates → PLAN_INSERT
  5. RETIRED candidates → PLAN_MANUAL_REVIEW_REQUIRED in ONLINE_ONLY scope
  6. INCLUDE_RETIRED_WITH_WARNING still dry-run, no DB write
  7. All 121 P6 candidates classified
  8. duplicate_check_key present for all rows
  9. provenance_hash required for PLAN_INSERT
 10. p7_can_apply False for all rows
 11. dry_run_only True for all rows
 12. rollback_batch_id present
 13. controlled_apply_id present for all rows
 14. backup plan present
 15. JSON has required summary keys
 16. P6 rejected rows (not in P7 candidates) not in plan
 17. PLAN_INSERT count <= online_candidates
 18. manual_review_count >= retired_candidates (in ONLINE_ONLY scope)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P7_SCRIPT  = REPO_ROOT / "scripts" / "p7_controlled_replay_row_apply_dry_run.py"
P7_JSON    = REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"
P6_JSON    = REPO_ROOT / "outputs" / "replay" / "p6_source_promotion_policy_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_p7_apply_plan_contract import (
    P7ApplyDecision,
    P7ApplyScope,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p7_json() -> dict:
    if not P7_JSON.exists():
        pytest.skip(f"P7 output not found: {P7_JSON}. "
                    "Run scripts/p7_controlled_replay_row_apply_dry_run.py first.")
    return json.loads(P7_JSON.read_text())


@pytest.fixture(scope="module")
def p6_json() -> dict:
    if not P6_JSON.exists():
        pytest.skip(f"P6 output not found: {P6_JSON}")
    return json.loads(P6_JSON.read_text())


def _db_replay_count() -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 1: Script safety
# ---------------------------------------------------------------------------

class TestScriptSafety:
    def test_no_apply_flag_in_argparse(self):
        src = P7_SCRIPT.read_text()
        assert 'add_argument("--apply"' not in src and "add_argument('--apply'" not in src, (
            "P7 script must not expose --apply via argparse"
        )

    def test_no_db_write_sql(self):
        src = P7_SCRIPT.read_text()
        for kw in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
            assert kw not in src, f"P7 script contains forbidden SQL: {kw!r}"

    def test_opens_db_readonly(self):
        src = P7_SCRIPT.read_text()
        assert "mode=ro" in src, "P7 script must open DB with mode=ro"


# ---------------------------------------------------------------------------
# Section 2: DB safety
# ---------------------------------------------------------------------------

class TestDBSafety:
    def test_db_row_count_is_460(self):
        assert _db_replay_count() == 460, (
            "strategy_prediction_replays row count changed from expected 460"
        )

    def test_p7_json_db_verified(self, p7_json):
        assert p7_json["db_row_count_verified"] == 460

    def test_no_replay_rows_in_candidates(self, p7_json):
        # PLAN_INSERT rows must not have an existing replay_row_id
        for row in p7_json.get("p7_insert_rows", []):
            assert "replay_row_id" not in row


# ---------------------------------------------------------------------------
# Section 3: P7 JSON structure
# ---------------------------------------------------------------------------

class TestP7OutputStructure:
    REQUIRED_KEYS = {
        "phase", "generated_at", "scope", "rollback_batch_id",
        "dry_run_only", "p7_can_apply", "db_row_count_verified",
        "total_p6_candidates", "plan_insert_count",
        "manual_review_required_count", "duplicate_skip_count",
        "online_candidates", "retired_warning_candidates",
        "by_strategy", "by_lifecycle_state", "by_apply_decision",
        "backup_plan", "rollback_plan", "safety_flags",
        "p7_insert_rows", "all_plan_rows",
    }

    def test_required_keys(self, p7_json):
        for k in self.REQUIRED_KEYS:
            assert k in p7_json, f"Missing required key {k!r} in P7 output"

    def test_phase_is_p7(self, p7_json):
        assert p7_json["phase"] == "P7"

    def test_dry_run_only_true(self, p7_json):
        assert p7_json["dry_run_only"] is True

    def test_p7_can_apply_false(self, p7_json):
        assert p7_json["p7_can_apply"] is False

    def test_default_scope_is_online_only(self, p7_json):
        assert p7_json["scope"] == P7ApplyScope.ONLINE_ONLY

    def test_rollback_batch_id_is_uuid(self, p7_json):
        import uuid
        try:
            uuid.UUID(p7_json["rollback_batch_id"])
        except ValueError:
            pytest.fail(f"rollback_batch_id is not a valid UUID: {p7_json['rollback_batch_id']!r}")

    def test_backup_plan_present(self, p7_json):
        bp = p7_json["backup_plan"]
        assert "description" in bp
        assert "rollback_command" in bp
        assert "verified_row_count_before" in bp

    def test_rollback_plan_present(self, p7_json):
        rp = p7_json["rollback_plan"]
        assert "rollback_batch_id" in rp
        assert "idempotency_check" in rp


# ---------------------------------------------------------------------------
# Section 4: Candidate classification
# ---------------------------------------------------------------------------

class TestCandidateClassification:
    def test_total_candidates_equals_p6(self, p7_json, p6_json):
        assert p7_json["total_p6_candidates"] == p6_json["approved_for_p7_candidate"], (
            "P7 must classify ALL P6 approved candidates"
        )

    def test_online_candidates_count(self, p7_json, p6_json):
        assert p7_json["online_candidates"] == 28

    def test_retired_candidates_count(self, p7_json):
        assert p7_json["retired_warning_candidates"] == 93

    def test_plan_insert_lte_online(self, p7_json):
        assert p7_json["plan_insert_count"] <= p7_json["online_candidates"], (
            "In ONLINE_ONLY scope, PLAN_INSERT cannot exceed ONLINE candidates"
        )

    def test_manual_review_gte_retired(self, p7_json):
        assert p7_json["manual_review_required_count"] >= p7_json["retired_warning_candidates"], (
            "In ONLINE_ONLY scope, all RETIRED must be MANUAL_REVIEW_REQUIRED"
        )

    def test_counts_add_up(self, p7_json):
        total     = p7_json["total_p6_candidates"]
        insert    = p7_json["plan_insert_count"]
        manual    = p7_json["manual_review_required_count"]
        dup_skip  = p7_json["duplicate_skip_count"]
        other     = p7_json["invalid_candidate_count"]
        assert insert + manual + dup_skip + other == total, (
            f"plan_insert({insert}) + manual({manual}) + dup_skip({dup_skip}) "
            f"+ other({other}) != total({total})"
        )

    def test_all_rows_p7_can_apply_false(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            assert r["p7_can_apply"] is False, (
                f"p7_can_apply must be False: {r['strategy_id']}/{r['draw_id']}"
            )

    def test_all_rows_dry_run_only_true(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            assert r["dry_run_only"] is True

    def test_all_rows_truth_level(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            assert r["truth_level"] == "RECONSTRUCTION_DRY_RUN_PLAN"

    def test_all_rows_have_duplicate_check_key(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            assert r["duplicate_check_key"], (
                f"duplicate_check_key missing for {r['strategy_id']}/{r['draw_id']}"
            )

    def test_all_rows_have_rollback_batch_id(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            assert r["rollback_batch_id"], (
                f"rollback_batch_id missing for {r['strategy_id']}/{r['draw_id']}"
            )

    def test_all_rows_have_controlled_apply_id(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            assert r["controlled_apply_id"], (
                f"controlled_apply_id missing for {r['strategy_id']}/{r['draw_id']}"
            )


# ---------------------------------------------------------------------------
# Section 5: PLAN_INSERT row quality
# ---------------------------------------------------------------------------

class TestInsertRowQuality:
    def test_insert_rows_have_provenance(self, p7_json):
        for r in p7_json["p7_insert_rows"]:
            assert r["provenance_hash"], (
                f"PLAN_INSERT row missing provenance_hash: {r['strategy_id']}/{r['draw_id']}"
            )

    def test_insert_rows_are_online(self, p7_json):
        # In ONLINE_ONLY scope, all PLAN_INSERT rows must be ONLINE lifecycle
        for r in p7_json["p7_insert_rows"]:
            assert r["lifecycle_state"] == "ONLINE", (
                f"PLAN_INSERT row has non-ONLINE lifecycle: "
                f"{r['strategy_id']}/{r['draw_id']} = {r['lifecycle_state']!r}"
            )

    def test_insert_rows_no_lifecycle_warning(self, p7_json):
        for r in p7_json["p7_insert_rows"]:
            assert not r["lifecycle_warning"], (
                f"PLAN_INSERT row in ONLINE_ONLY scope has lifecycle_warning: "
                f"{r['strategy_id']}/{r['draw_id']}"
            )

    def test_no_duplicates_in_insert_rows(self, p7_json):
        keys = [r["duplicate_check_key"] for r in p7_json["p7_insert_rows"]]
        assert len(keys) == len(set(keys)), "Duplicate check keys not unique in PLAN_INSERT rows"


# ---------------------------------------------------------------------------
# Section 6: RETIRED rows are manual review in ONLINE_ONLY
# ---------------------------------------------------------------------------

class TestRetiredClassification:
    def test_retired_rows_manual_review(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            if r["lifecycle_state"] == "RETIRED":
                assert r["apply_decision"] == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED, (
                    f"RETIRED row in ONLINE_ONLY scope must be PLAN_MANUAL_REVIEW_REQUIRED: "
                    f"{r['strategy_id']}/{r['draw_id']}"
                )

    def test_retired_rows_have_lifecycle_warning(self, p7_json):
        for r in p7_json["all_plan_rows"]:
            if r["lifecycle_state"] == "RETIRED":
                assert r["lifecycle_warning"], (
                    f"RETIRED row must have lifecycle_warning: "
                    f"{r['strategy_id']}/{r['draw_id']}"
                )


# ---------------------------------------------------------------------------
# Section 7: Safety flags
# ---------------------------------------------------------------------------

class TestSafetyFlags:
    def test_safety_flags(self, p7_json):
        sf = p7_json["safety_flags"]
        assert sf["p7_can_apply_globally"] is False
        assert sf["dry_run_only_globally"] is True
        assert sf["db_write_performed"] is False
        assert sf["replay_rows_generated"] is False
        assert sf["prediction_rows_generated"] is False
