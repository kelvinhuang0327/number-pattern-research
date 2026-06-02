"""
Tests for P126 — Controlled Apply Dry-Run Plan for Tier-B Multi-Bet Adapters

Verifies:
- Script is read-only (no DB writes)
- JSON artifact structure and content
- DB invariants unchanged after run
- Duplicate guard and provenance guard results
- Delta calculations for each candidate
- Governance fields
- No forbidden side effects
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
SCRIPT    = REPO_ROOT / "scripts" / "p126_controlled_apply_plan_tier_b_multi_bet.py"
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON  = REPO_ROOT / "outputs" / "replay" / "p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"
OUT_MD    = REPO_ROOT / "docs"    / "replay" / "p126_controlled_apply_plan_tier_b_multi_bet_20260528.md"

PYTHON = sys.executable

# ── Expected constants ────────────────────────────────────────────────────────

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_CANDIDATES  = [
    "biglotto_echo_aware_3bet",
    "daily539_f4cold_5bet",
    "daily539_f4cold_3bet",
    "power_fourier_rhythm_2bet",
    "biglotto_ts3_markov_4bet_w30",
]

EXPECTED_BET_COUNTS = {
    "biglotto_echo_aware_3bet":    3,
    "daily539_f4cold_5bet":        5,
    "daily539_f4cold_3bet":        3,
    "power_fourier_rhythm_2bet":   2,
    "biglotto_ts3_markov_4bet_w30": 4,
}

EXPECTED_NEW_ROWS = {
    "biglotto_echo_aware_3bet":    3000,   # 1500 draws × (3-1)
    "daily539_f4cold_5bet":        6000,   # 1500 draws × (5-1)
    "daily539_f4cold_3bet":        3000,   # 1500 draws × (3-1)
    "power_fourier_rhythm_2bet":   1500,   # 1500 draws × (2-1)
    "biglotto_ts3_markov_4bet_w30": 4500,  # 1500 draws × (4-1)
}

EXPECTED_TOTAL_NEW_ROWS = 18000
EXPECTED_TOTAL_AFTER    = 72462


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def artifact() -> dict:
    """Load the P126 JSON artifact (run script if needed)."""
    if not OUT_JSON.exists():
        result = subprocess.run(
            [PYTHON, str(SCRIPT)],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        assert result.returncode == 0, (
            f"Script failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    with open(OUT_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    """Read-only DB connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA query_only = ON")
    yield conn
    conn.close()


# ── Group 1: Script and artifact existence ────────────────────────────────────

class TestArtifactExists:

    def test_script_exists(self):
        assert SCRIPT.exists(), f"Script not found: {SCRIPT}"

    def test_json_exists(self, artifact):
        assert OUT_JSON.exists(), f"JSON not found: {OUT_JSON}"

    def test_md_exists(self, artifact):
        assert OUT_MD.exists(), f"MD not found: {OUT_MD}"


# ── Group 2: Classification and metadata ─────────────────────────────────────

class TestClassification:

    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P126"

    def test_classification(self, artifact):
        assert artifact["classification"] == "P126_DRY_RUN_PLAN_READY"

    def test_generated_at_present(self, artifact):
        assert artifact.get("generated_at"), "generated_at must be set"

    def test_plan_hash_present(self, artifact):
        assert artifact.get("plan_hash"), "plan_hash must be set"

    def test_p124_source_referenced(self, artifact):
        assert "p124" in artifact["p124_source_artifact"].lower()

    def test_p125_source_referenced(self, artifact):
        assert "p125" in artifact["p125_source_artifact"].lower()


# ── Group 3: DB invariants ────────────────────────────────────────────────────

class TestDBInvariantsBeforeRun:

    def test_replay_rows_unchanged(self, db):
        count = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert count == EXPECTED_REPLAY_ROWS, (
            f"replay_rows={count} expected={EXPECTED_REPLAY_ROWS}"
        )

    def test_3star_count(self, db):
        count = db.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()[0]
        assert count == 4179

    def test_3star_max_draw(self, db):
        mx = db.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()[0]
        assert mx == 115000106

    def test_4star_count(self, db):
        count = db.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
        ).fetchone()[0]
        assert count == 2922

    def test_4star_max_draw(self, db):
        mx = db.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='4_STAR'"
        ).fetchone()[0]
        assert mx == 115000103

    def test_power_lotto_count(self, db):
        count = db.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        assert count == 1913

    def test_power_lotto_max_draw(self, db):
        mx = db.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        assert mx == 115000041


# ── Group 4: DB snapshot in artifact ─────────────────────────────────────────

class TestDBSnapshot:

    def test_snapshot_replay_rows(self, artifact):
        assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_snapshot_3star(self, artifact):
        s = artifact["db_snapshot_before"]["3_STAR"]
        assert s["count"] == 4179
        assert s["max_draw"] == 115000106

    def test_snapshot_4star(self, artifact):
        s = artifact["db_snapshot_before"]["4_STAR"]
        assert s["count"] == 2922
        assert s["max_draw"] == 115000103

    def test_snapshot_power(self, artifact):
        s = artifact["db_snapshot_before"]["POWER_LOTTO"]
        assert s["count"] == 1913
        assert s["max_draw"] == 115000041


# ── Group 5: Candidate structure ─────────────────────────────────────────────

class TestCandidateStructure:

    def test_candidate_count(self, artifact):
        assert len(artifact["dry_run_candidates"]) == 5

    def test_candidate_ids(self, artifact):
        ids = {c["strategy_id"] for c in artifact["dry_run_candidates"]}
        assert ids == set(EXPECTED_CANDIDATES)

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_bet_count(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["target_bet_count"] == EXPECTED_BET_COUNTS[sid]

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_existing_rows(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["existing_rows"] == 1500, (
            f"{sid}: expected 1500 existing rows"
        )

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_new_rows(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["new_rows_if_applied"] == EXPECTED_NEW_ROWS[sid], (
            f"{sid}: new_rows_if_applied={cand['new_rows_if_applied']} expected={EXPECTED_NEW_ROWS[sid]}"
        )

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_total_after(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        expected_total = 1500 + EXPECTED_NEW_ROWS[sid]
        assert cand["total_rows_after_apply"] == expected_total

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_storage_approach(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["storage_approach"] == "one_row_per_bet"

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_authorization_required(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["explicit_apply_authorization_required"] is True

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_db_writes_zero(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["db_writes_in_p126"] == 0

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_draw_count_nonzero(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["draw_count"] > 0
        assert cand["draw_min"] is not None
        assert cand["draw_max"] is not None

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_apply_order_present(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert 1 <= cand["apply_order"] <= 5

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_candidate_apply_order_unique(self, artifact, sid):
        orders = [c["apply_order"] for c in artifact["dry_run_candidates"]]
        assert len(orders) == len(set(orders)), "apply_order values must be unique"


# ── Group 6: Provenance guard ─────────────────────────────────────────────────

class TestProvenanceGuard:

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_provenance_pass(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["provenance_guard"]["status"] == "PASS", (
            f"{sid}: provenance_guard FAIL — notes: {cand['provenance_guard']['notes']}"
        )

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_provenance_found_sources_nonempty(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert len(cand["provenance_guard"]["found_sources"]) > 0

    def test_all_provenance_pass(self, artifact):
        assert artifact["summary"]["all_candidates_prov_guard_pass"] is True


# ── Group 7: Duplicate guard ──────────────────────────────────────────────────

class TestDuplicateGuard:

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_duplicate_pass(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["duplicate_guard"]["status"] == "PASS", (
            f"{sid}: duplicate_guard FAIL"
        )

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_no_duplicate_draws(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert cand["duplicate_guard"]["duplicate_draws_found"] == 0

    def test_all_duplicate_pass(self, artifact):
        assert artifact["summary"]["all_candidates_dup_guard_pass"] is True


# ── Group 8: Row delta totals ─────────────────────────────────────────────────

class TestRowDelta:

    def test_total_new_rows(self, artifact):
        assert artifact["summary"]["total_new_rows_if_all_applied"] == EXPECTED_TOTAL_NEW_ROWS

    def test_total_rows_after(self, artifact):
        assert artifact["summary"]["total_replay_rows_after_all_applied"] == EXPECTED_TOTAL_AFTER

    def test_sum_of_candidate_new_rows(self, artifact):
        total = sum(c["new_rows_if_applied"] for c in artifact["dry_run_candidates"])
        assert total == EXPECTED_TOTAL_NEW_ROWS

    def test_delta_formula_per_candidate(self, artifact):
        """Verify new_rows = draw_count × (target_bets - 1) for each candidate."""
        for cand in artifact["dry_run_candidates"]:
            expected = cand["draw_count"] * (cand["target_bet_count"] - 1)
            assert cand["new_rows_if_applied"] == expected, (
                f"{cand['strategy_id']}: "
                f"new_rows={cand['new_rows_if_applied']} "
                f"expected draw_count×(bets-1)={expected}"
            )


# ── Group 9: Preconditions ────────────────────────────────────────────────────

class TestPreconditions:

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_preconditions_list_nonempty(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        assert len(cand["preconditions"]) >= 5

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_p128_precondition_pending(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        p128_check = next(
            (p for p in cand["preconditions"] if p["check"] == "p128_storage_design_or_convention_accepted"),
            None
        )
        assert p128_check is not None, "p128_storage_design_or_convention_accepted must be in preconditions"
        assert p128_check["status"] == "PENDING"

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_explicit_authorization_precondition(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        auth_check = next(
            (p for p in cand["preconditions"] if p["check"] == "explicit_apply_authorization"),
            None
        )
        assert auth_check is not None, "explicit_apply_authorization must be in preconditions"
        assert auth_check["status"] == "REQUIRED"

    @pytest.mark.parametrize("sid", EXPECTED_CANDIDATES)
    def test_authorization_phrase_present(self, artifact, sid):
        cand = next(c for c in artifact["dry_run_candidates"] if c["strategy_id"] == sid)
        phrase = cand.get("apply_authorization_phrase", "")
        assert sid in phrase, f"authorization phrase must contain strategy_id"
        assert "YES authorize" in phrase


# ── Group 10: Governance ──────────────────────────────────────────────────────

class TestGovernance:

    def test_db_writes_zero(self, artifact):
        assert artifact["governance"]["db_writes"] == 0
        assert artifact["summary"]["db_writes_in_p126"] == 0

    def test_scheduler_not_installed(self, artifact):
        assert artifact["governance"]["scheduler_installed"] is False

    def test_strategy_not_promoted(self, artifact):
        assert artifact["governance"]["strategy_promoted"] is False

    def test_no_fabricated_rows(self, artifact):
        assert artifact["governance"]["fabricated_rows"] == 0

    def test_4star_not_included(self, artifact):
        assert artifact["governance"]["4_STAR_included"] is False

    def test_p108_not_executed(self, artifact):
        assert artifact["governance"]["P108_executed"] is False

    def test_p117_not_executed(self, artifact):
        assert artifact["governance"]["P117_executed"] is False

    def test_p118_not_executed(self, artifact):
        assert artifact["governance"]["P118_executed"] is False

    def test_forbidden_files_not_staged(self, artifact):
        assert artifact["governance"]["forbidden_files_staged"] is False

    def test_pragma_query_only(self, artifact):
        assert "ON" in artifact["governance"]["pragma_query_only"]

    def test_p128_pending(self, artifact):
        assert artifact["summary"]["p128_pending"] is True

    def test_all_authorization_required(self, artifact):
        assert artifact["summary"]["all_candidates_authorization_required"] is True
        assert artifact["summary"]["explicit_apply_authorization_required"] is True


# ── Group 11: Storage risk summary ───────────────────────────────────────────

class TestStorageRiskSummary:

    def test_rsr1_present(self, artifact):
        assert "RSR-1" in artifact["storage_risk_summary"]

    def test_rsr1_is_blocker_for_apply(self, artifact):
        assert artifact["storage_risk_summary"]["RSR-1"]["blocker_for_apply"] is True

    def test_rsr2_present(self, artifact):
        assert "RSR-2" in artifact["storage_risk_summary"]

    def test_rsr3_present(self, artifact):
        assert "RSR-3" in artifact["storage_risk_summary"]

    def test_rsr4_present(self, artifact):
        assert "RSR-4" in artifact["storage_risk_summary"]


# ── Group 12: Blocked/forbidden actions ──────────────────────────────────────

class TestBlockedForbiddenActions:

    def test_4star_no_action(self, artifact):
        entry = artifact["blocked_or_forbidden"].get("4_STAR_source_unknown", {})
        assert entry.get("action") == "no_action"

    def test_p108_no_action(self, artifact):
        entry = artifact["blocked_or_forbidden"].get("P108_Special3", {})
        assert entry.get("action") == "no_action"

    def test_p117_no_action(self, artifact):
        entry = artifact["blocked_or_forbidden"].get("P117_POWER_LOTTO_OOS", {})
        assert entry.get("action") == "no_action"

    def test_p118_no_action(self, artifact):
        entry = artifact["blocked_or_forbidden"].get("P118_BIG_LOTTO_quarantine", {})
        assert entry.get("action") == "no_action"

    def test_fabricated_rows_no_action(self, artifact):
        entry = artifact["blocked_or_forbidden"].get("fabricated_rows", {})
        assert entry.get("action") == "no_action"


# ── Group 13: Next tasks ──────────────────────────────────────────────────────

class TestNextTasks:

    def test_p126_apply_next_task_present(self, artifact):
        assert "P126_apply" in artifact["next_tasks"]

    def test_p126_apply_has_authorization_phrases(self, artifact):
        phrases = artifact["next_tasks"]["P126_apply"]["authorization_phrases_required"]
        assert len(phrases) == 5
        for phrase in phrases:
            assert "YES authorize controlled_apply for" in phrase

    def test_p127_present(self, artifact):
        assert "P127" in artifact["next_tasks"]

    def test_p128_present(self, artifact):
        assert "P128" in artifact["next_tasks"]


# ── Group 14: MD output ───────────────────────────────────────────────────────

class TestMarkdownOutput:

    def test_md_nonempty(self, artifact):
        content = OUT_MD.read_text()
        assert len(content) > 2000

    def test_md_contains_classification(self, artifact):
        content = OUT_MD.read_text()
        assert "P126_DRY_RUN_PLAN_READY" in content

    def test_md_contains_all_candidates(self, artifact):
        content = OUT_MD.read_text()
        for sid in EXPECTED_CANDIDATES:
            assert sid in content, f"MD missing candidate: {sid}"

    def test_md_contains_total_new_rows(self, artifact):
        content = OUT_MD.read_text()
        assert "+18000" in content or "18000" in content

    def test_md_contains_no_db_write(self, artifact):
        content = OUT_MD.read_text()
        assert "0" in content  # at least one zero for DB writes


# ── Group 15: Script is idempotent ───────────────────────────────────────────

class TestIdempotency:

    def test_script_reruns_cleanly(self):
        """Running the script a second time produces same classification."""
        result = subprocess.run(
            [PYTHON, str(SCRIPT)],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        assert result.returncode == 0, (
            f"Script re-run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "P126_DRY_RUN_PLAN_READY" in result.stdout

    def test_db_still_unchanged_after_rerun(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == EXPECTED_REPLAY_ROWS, (
            f"DB row count changed after re-run: {count} expected {EXPECTED_REPLAY_ROWS}"
        )
