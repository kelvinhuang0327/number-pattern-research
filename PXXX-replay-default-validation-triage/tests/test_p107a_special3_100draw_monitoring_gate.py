"""
tests/test_p107a_special3_100draw_monitoring_gate.py

Test suite for P107A: Special3 100-Draw Monitoring Gate.
All tests are read-only. No DB writes.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

JSON_PATH = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p107a_special3_100draw_monitoring_gate_20260527.json"
)
MD_PATH = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "p107a_special3_100draw_monitoring_gate_20260527.md"
)
SCRIPT_PATH = (
    REPO_ROOT / "scripts" / "p107a_special3_100draw_monitoring_gate.py"
)

VALID_CLASSIFICATIONS = {
    "P107A_SPECIAL3_100DRAW_READY",
    "P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS",
    "P107A_SPECIAL3_100DRAW_BLOCKED_BY_DB_DRIFT",
    "P107A_SPECIAL3_100DRAW_BLOCKED_BY_GUARD_FAILURE",
    "P107A_SPECIAL3_100DRAW_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P107A_SPECIAL3_100DRAW_BLOCKED_BY_CONTEXT_CONTAMINATION",
    "P107A_SPECIAL3_100DRAW_BLOCKED_BY_SCOPE_VIOLATION",
    "P107A_SPECIAL3_100DRAW_BLOCKED_BY_TEST_FAILURE",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text())


@pytest.fixture(scope="module")
def md_text():
    assert MD_PATH.exists(), f"MD report missing: {MD_PATH}"
    return MD_PATH.read_text()


@pytest.fixture(scope="module")
def script_text():
    assert SCRIPT_PATH.exists(), f"Script missing: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text()


@pytest.fixture(scope="module")
def live_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------
class TestFileExistence:
    def test_json_artifact_exists(self):
        assert JSON_PATH.exists(), f"Missing: {JSON_PATH}"

    def test_md_report_exists(self):
        assert MD_PATH.exists(), f"Missing: {MD_PATH}"

    def test_script_exists(self):
        assert SCRIPT_PATH.exists(), f"Missing: {SCRIPT_PATH}"

    def test_json_parses_cleanly(self, artifact):
        assert isinstance(artifact, dict), "JSON must be a dict"

    def test_md_not_empty(self, md_text):
        assert len(md_text.strip()) > 100, "MD report is too short"


# ---------------------------------------------------------------------------
# 2. Classification
# ---------------------------------------------------------------------------
class TestClassification:
    def test_classification_field_exists(self, artifact):
        assert "classification" in artifact

    def test_classification_is_valid(self, artifact):
        assert artifact["classification"] in VALID_CLASSIFICATIONS, (
            f"Unknown classification: {artifact['classification']}"
        )

    def test_classification_not_blocked(self, artifact):
        cls = artifact["classification"]
        assert "BLOCKED" not in cls, f"Classification is BLOCKED: {cls}"

    def test_classification_ready_or_wait(self, artifact):
        cls = artifact["classification"]
        assert cls in (
            "P107A_SPECIAL3_100DRAW_READY",
            "P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS",
        ), f"Expected READY or WAIT_MORE_DRAWS, got: {cls}"

    def test_classification_matches_count_logic(self, artifact):
        total = artifact["prospective_draw_counts"]["total_after_p99_cutoff"]
        cls = artifact["classification"]
        if total >= 100:
            assert cls == "P107A_SPECIAL3_100DRAW_READY"
        else:
            assert cls == "P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS"


# ---------------------------------------------------------------------------
# 3. Governance fields
# ---------------------------------------------------------------------------
class TestGovernanceFields:
    def test_source_unknown_caveat_true(self, artifact):
        assert artifact.get("source_unknown_caveat") is True

    def test_db_writes_false(self, artifact):
        assert artifact.get("db_writes") is False

    def test_no_strategy_promotion(self, artifact):
        assert artifact.get("no_strategy_promotion") is True

    def test_no_4star_backtest(self, artifact):
        assert artifact.get("no_4star_backtest") is True

    def test_no_lifecycle_mutation(self, artifact):
        assert artifact.get("no_lifecycle_mutation") is True

    def test_replay_rows_before_54462(self, artifact):
        assert artifact.get("replay_rows_before") == 54462

    def test_replay_rows_after_54462(self, artifact):
        assert artifact.get("replay_rows_after") == 54462

    def test_replay_rows_before_equals_after(self, artifact):
        assert artifact["replay_rows_before"] == artifact["replay_rows_after"]


# ---------------------------------------------------------------------------
# 4. P106 reference
# ---------------------------------------------------------------------------
class TestP106Reference:
    def test_p106_reference_exists(self, artifact):
        assert "p106_reference" in artifact

    def test_p106_classification(self, artifact):
        ref = artifact["p106_reference"]
        assert ref["classification"] == "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL"

    def test_p100_criteria_passed(self, artifact):
        assert artifact["p106_reference"]["p100_criteria_passed"] == 5

    def test_p100_criteria_total(self, artifact):
        assert artifact["p106_reference"]["p100_criteria_total"] == 6

    def test_best_individual_strategy(self, artifact):
        assert artifact["p106_reference"]["best_individual_strategy"] == "sum_band_frequency"

    def test_p106_pr_number(self, artifact):
        assert artifact["p106_reference"]["pr_number"] == 235

    def test_ensemble_v2_hit_rate(self, artifact):
        rate = artifact["p106_reference"]["ensemble_v2_top20_hit_rate"]
        assert abs(rate - 0.1429) < 0.001

    def test_ensemble_v2_threshold(self, artifact):
        threshold = artifact["p106_reference"]["ensemble_v2_top20_threshold"]
        assert abs(threshold - 0.15) < 0.001

    def test_best_strategy_hit_rate(self, artifact):
        rate = artifact["p106_reference"]["best_individual_strategy_top20_hit_rate"]
        assert abs(rate - 0.1905) < 0.001


# ---------------------------------------------------------------------------
# 5. History / evaluated range
# ---------------------------------------------------------------------------
class TestHistoryRange:
    def test_history_end_draw(self, artifact):
        assert artifact.get("history_end_draw") == "115000024"

    def test_p106_evaluated_range_min(self, artifact):
        assert artifact["p106_evaluated_range"]["min"] == "115000028"

    def test_p106_evaluated_range_max(self, artifact):
        assert artifact["p106_evaluated_range"]["max"] == "115000106"

    def test_p106_evaluated_draws(self, artifact):
        assert artifact["p106_evaluated_range"]["evaluated_draws"] == 63


# ---------------------------------------------------------------------------
# 6. Prospective draw counts
# ---------------------------------------------------------------------------
class TestProspectiveDrawCounts:
    def test_prospective_counts_section_exists(self, artifact):
        assert "prospective_draw_counts" in artifact

    def test_total_after_p99_cutoff_positive(self, artifact):
        total = artifact["prospective_draw_counts"]["total_after_p99_cutoff"]
        assert total > 0

    def test_remaining_needed_non_negative(self, artifact):
        remaining = artifact["prospective_draw_counts"]["remaining_needed_for_100"]
        assert remaining >= 0

    def test_remaining_consistent_with_total(self, artifact):
        total = artifact["prospective_draw_counts"]["total_after_p99_cutoff"]
        remaining = artifact["prospective_draw_counts"]["remaining_needed_for_100"]
        expected_remaining = max(0, 100 - total)
        assert remaining == expected_remaining


# ---------------------------------------------------------------------------
# 7. Current DB snapshot in artifact
# ---------------------------------------------------------------------------
class TestCurrentDbSnapshot:
    def test_db_snapshot_exists(self, artifact):
        assert "current_db_snapshot" in artifact

    def test_snapshot_replay_rows(self, artifact):
        assert artifact["current_db_snapshot"]["replay_rows"] == 54462

    def test_snapshot_three_star_count(self, artifact):
        assert artifact["current_db_snapshot"]["three_star_count"] == 4179

    def test_snapshot_three_star_max_draw(self, artifact):
        assert artifact["current_db_snapshot"]["three_star_max_draw"] == "115000106"

    def test_snapshot_four_star_count(self, artifact):
        assert artifact["current_db_snapshot"]["four_star_count"] == 2922

    def test_snapshot_four_star_max_draw(self, artifact):
        assert artifact["current_db_snapshot"]["four_star_max_draw"] == "115000103"

    def test_snapshot_power_lotto_count(self, artifact):
        assert artifact["current_db_snapshot"]["power_lotto_count"] == 1913

    def test_snapshot_power_lotto_max_draw(self, artifact):
        assert artifact["current_db_snapshot"]["power_lotto_max_draw"] == "115000041"


# ---------------------------------------------------------------------------
# 8. Live DB invariants
# ---------------------------------------------------------------------------
class TestLiveDbInvariants:
    def test_live_replay_rows_54462(self, live_db):
        count = live_db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert count == 54462

    def test_live_3star_max_draw_gte_p106_max(self, live_db):
        max_draw = live_db.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()[0]
        assert max_draw >= 115000106

    def test_live_4star_max_draw(self, live_db):
        max_draw = live_db.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='4_STAR'"
        ).fetchone()[0]
        assert max_draw == 115000103, (
            f"4_STAR max draw changed unexpectedly: {max_draw}"
        )

    def test_live_power_lotto_max_draw(self, live_db):
        max_draw = live_db.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        assert max_draw == 115000041, (
            f"POWER_LOTTO max draw changed unexpectedly: {max_draw}"
        )

    def test_live_prospective_after_p99_consistent_with_artifact(self, artifact, live_db):
        live_count = live_db.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR' "
            "AND CAST(draw AS INTEGER) > 115000024"
        ).fetchone()[0]
        artifact_count = artifact["prospective_draw_counts"]["total_after_p99_cutoff"]
        assert live_count == artifact_count


# ---------------------------------------------------------------------------
# 9. Markdown spot-checks
# ---------------------------------------------------------------------------
class TestMarkdownContent:
    def test_md_contains_source_unknown(self, md_text):
        assert "source_unknown" in md_text.lower() or "SOURCE_UNKNOWN" in md_text

    def test_md_contains_no_4star_backtest_note(self, md_text):
        assert "4_STAR backtest" in md_text or "4_star backtest" in md_text.lower()

    def test_md_contains_no_strategy_promotion_note(self, md_text):
        assert "promot" in md_text.lower()

    def test_md_contains_project_context_lock(self, md_text):
        assert "PROJECT_CONTEXT_LOCK" in md_text

    def test_md_contains_p107b_separation_note(self, md_text):
        assert "P107B" in md_text

    def test_md_contains_classification(self, md_text):
        assert "P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS" in md_text or \
               "P107A_SPECIAL3_100DRAW_READY" in md_text

    def test_md_contains_wait_more_draws_or_ready(self, md_text):
        assert "WAIT_MORE_DRAWS" in md_text or "READY" in md_text


# ---------------------------------------------------------------------------
# 10. Script safety — no write SQL verbs in execute() calls
# ---------------------------------------------------------------------------
def _extract_execute_calls(script_text: str) -> str:
    """Extract only lines containing .execute( to check for write verbs."""
    return "\n".join(
        line for line in script_text.splitlines()
        if ".execute(" in line
    )


class TestScriptSafety:
    def test_script_no_insert_in_execute(self, script_text):
        calls = _extract_execute_calls(script_text)
        assert not re.search(r"\bINSERT\b", calls, re.IGNORECASE), \
            "Script has INSERT in an execute() call"

    def test_script_no_update_in_execute(self, script_text):
        calls = _extract_execute_calls(script_text)
        assert not re.search(r"\bUPDATE\b", calls, re.IGNORECASE), \
            "Script has UPDATE in an execute() call"

    def test_script_no_delete_in_execute(self, script_text):
        calls = _extract_execute_calls(script_text)
        assert not re.search(r"\bDELETE\b", calls, re.IGNORECASE), \
            "Script has DELETE in an execute() call"

    def test_script_no_drop_in_execute(self, script_text):
        calls = _extract_execute_calls(script_text)
        assert not re.search(r"\bDROP\b", calls, re.IGNORECASE), \
            "Script has DROP in an execute() call"

    def test_script_no_alter_in_execute(self, script_text):
        calls = _extract_execute_calls(script_text)
        assert not re.search(r"\bALTER\b", calls, re.IGNORECASE), \
            "Script has ALTER in an execute() call"

    def test_script_opens_db_readonly(self, script_text):
        assert "mode=ro" in script_text, "Script must open DB in read-only mode"
