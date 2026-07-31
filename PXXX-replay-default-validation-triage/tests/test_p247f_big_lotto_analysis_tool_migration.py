"""Tests for P247F — BIG_LOTTO analysis tool migration to canonical helper."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p247f_big_lotto_analysis_tool_migration_20260606.json"
MD_PATH = OUTPUTS / "p247f_big_lotto_analysis_tool_migration_20260606.md"
CANONICAL_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
EXPECTED_CANONICAL = 2_113
EXPECTED_RAW = 22_238
EXPECTED_ADD_ON = 19_100

VALID_CLASSIFICATIONS = {
    "UPDATED_TO_CANONICAL",
    "ALREADY_CANONICAL",
    "RAW_HISTORY_ALLOWED",
    "DEFERRED_ARCHIVED_OR_EXPLORATORY",
    "DEFERRED_REQUIRES_DEDICATED_SCOPE",
    "NOT_AFFECTED",
    "UNKNOWN_NEEDS_REVIEW",
}

UPDATED_TOOL_PATHS = [
    "tools/analyze_banker_accuracy.py",
    "tools/analyze_banker_plus_kill.py",
    "tools/analyze_biglotto_special.py",
    "tools/analyze_market_temperature.py",
    "tools/analyze_top_n_for_2.py",
    "tools/audit_big_lotto_3bet.py",
    "tools/audit_big_lotto_baseline.py",
    "tools/audit_big_lotto_hyper.py",
    "tools/audit_big_lotto_rigorous.py",
]


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P247F JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists()
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def db_conn():
    if not CANONICAL_DB.exists():
        pytest.skip("Canonical DB not available")
    c = sqlite3.connect(f"file:{CANONICAL_DB.resolve()}?mode=ro", uri=True)
    yield c
    c.close()


# ── JSON artifact ─────────────────────────────────────────────────────────────

class TestP247FJSONArtifact:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_task_id(self, report):
        assert report["task_id"] == "P247F"

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_p247e_merged_verified(self, report):
        assert report["p247e_merged_state_verified"] is True

    def test_view_row_count(self, report):
        assert report["view_row_count"] == EXPECTED_CANONICAL

    def test_helper_row_count(self, report):
        assert report["helper_row_count"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_count(self, report):
        assert report["raw_big_lotto_count"] == EXPECTED_RAW

    def test_db_write_performed_false(self, report):
        assert report["db_write_performed"] is False

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_raw_access_preserved(self, report):
        assert report["raw_access_preserved"] is True

    def test_add_on_records_raw_accessible(self, report):
        assert report["add_on_records_raw_accessible"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        for action, status in report["forbidden_actions_confirmed"].items():
            assert status == "NOT PERFORMED", f"Forbidden: {action} -> {status}"

    def test_final_decision_no_db_write(self, report):
        assert "no db write" in report["final_decision"].lower()

    def test_final_decision_mentions_add_on(self, report):
        fd = report["final_decision"].lower()
        assert "add-on" in fd or "raw-accessible" in fd

    def test_read_only_precheck_passed(self, report):
        assert report["read_only_precheck"]["all_correct"] is True


class TestP247FToolsUpdated:
    def test_updated_tools_count(self, report):
        assert len(report["updated_tools"]) == 9

    def test_all_updated_tools_are_updated_to_canonical(self, report):
        for t in report["updated_tools"]:
            assert t["classification"] == "UPDATED_TO_CANONICAL", (
                f"{t['path']} is not UPDATED_TO_CANONICAL: {t['classification']}"
            )

    def test_deferred_tools_have_reasons(self, report):
        for t in report["deferred_tools"]:
            assert "reason" in t and len(t["reason"]) > 10

    def test_all_classifications_valid(self, report):
        for t in report["updated_tools"] + report["deferred_tools"]:
            assert t["classification"] in VALID_CLASSIFICATIONS

    def test_candidate_tools_scanned_count(self, report):
        assert report["candidate_tools_scanned"] >= 9

    def test_migration_scan_all_ok(self, report):
        assert report["migration_scan_results"]["all_ok"] is True

    def test_each_tool_scan_ok(self, report):
        for r in report["migration_scan_results"]["tool_results"]:
            assert r["status"] == "OK", f"{r['path']} scan status: {r['status']}"


class TestP247FSourceFiles:
    """Verify all 9 tools now use get_canonical_draws in their source."""

    @pytest.mark.parametrize("tool_path", UPDATED_TOOL_PATHS)
    def test_tool_uses_canonical(self, tool_path):
        path = REPO_ROOT / tool_path
        assert path.exists(), f"Tool not found: {path}"
        content = path.read_text()
        assert "get_canonical_draws" in content, (
            f"{tool_path} does not contain get_canonical_draws"
        )

    @pytest.mark.parametrize("tool_path", UPDATED_TOOL_PATHS)
    def test_tool_has_no_raw_big_lotto_call(self, tool_path):
        path = REPO_ROOT / tool_path
        content = path.read_text()
        raw_calls = [
            "get_all_draws(lottery_type='BIG_LOTTO')",
            "get_all_draws('BIG_LOTTO')",
        ]
        for rc in raw_calls:
            assert rc not in content, (
                f"{tool_path} still contains raw call: {rc}"
            )


class TestP247FMarkdown:
    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_add_on_raw_accessible(self, md):
        assert "raw-accessible" in md.lower()

    def test_md_mentions_9_tools(self, md):
        assert "9" in md

    def test_md_mentions_deferred(self, md):
        assert "deferred" in md.lower()

    def test_md_no_row_mutation(self, md):
        assert "no rows deleted" in md.lower() or "no row" in md.lower()


class TestP247FLiveDB:
    def test_view_still_correct(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws_big_lotto_canonical_main"
        ).fetchone()[0]
        assert cnt == EXPECTED_CANONICAL

    def test_raw_count_still_correct(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == EXPECTED_RAW

    def test_add_on_still_preserved(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
        ).fetchone()[0]
        assert cnt == EXPECTED_ADD_ON

    def test_annotation_table_absent(self, db_conn):
        row = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name='draw_row_family_annotations'"
        ).fetchone()
        assert row is None
