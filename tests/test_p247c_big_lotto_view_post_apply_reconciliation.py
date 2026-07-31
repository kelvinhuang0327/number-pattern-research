"""Tests for P247C — BIG_LOTTO canonical view post-apply reconciliation."""

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p247c_big_lotto_view_post_apply_reconciliation_20260606.json"
MD_PATH = OUTPUTS / "p247c_big_lotto_view_post_apply_reconciliation_20260606.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
VIEW_NAME = "draws_big_lotto_canonical_main"
EXPECTED_CANONICAL = 2_113
EXPECTED_RAW = 22_238
EXPECTED_ADD_ON = 19_100


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P247C JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists(), f"P247C MD not found: {MD_PATH}"
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def conn():
    if not DB_PATH.exists():
        pytest.skip("DB not available")
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield c
    c.close()


class TestP247CJSONArtifact:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_task_id(self, report):
        assert report["task_id"] == "P247C"

    def test_classification(self, report):
        assert "READ_ONLY" in report["classification"]

    def test_read_only_confirmed(self, report):
        assert report["read_only_confirmed"] is True

    def test_p247b_merged_state_verified(self, report):
        assert report["p247b_merged_state_verified"] is True

    def test_view_exists(self, report):
        assert report["view_exists"] is True

    def test_view_row_count(self, report):
        assert report["view_row_count"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_count(self, report):
        assert report["raw_big_lotto_count"] == EXPECTED_RAW

    def test_add_on_count(self, report):
        assert report["add_on_count"] == EXPECTED_ADD_ON

    def test_annotation_table_exists_false(self, report):
        assert report["annotation_table_exists"] is False

    def test_db_write_performed_false(self, report):
        assert report["db_write_performed"] is False

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_add_on_records_preserved(self, report):
        assert report["add_on_records_preserved"] is True

    def test_add_on_raw_accessible(self, report):
        assert report["add_on_raw_accessible"] is True

    def test_db_integrity_ok(self, report):
        assert report["db_integrity_result"] == "ok"

    def test_obsolete_assertions_updated_listed(self, report):
        updated = report.get("obsolete_assertions_updated", [])
        assert len(updated) > 0
        assert any("test_p247a_canonical_view_not_in_db" in entry or
                   "p247a" in entry.lower() for entry in updated)

    def test_forbidden_actions_all_not_performed(self, report):
        fac = report["forbidden_actions_confirmed"]
        for action, status in fac.items():
            assert status == "NOT PERFORMED", (
                f"Forbidden action '{action}' has unexpected status: {status}"
            )

    def test_final_decision_no_db_write(self, report):
        fd = report["final_decision"].lower()
        assert "no db write" in fd or "read-only" in fd

    def test_final_decision_add_on_raw(self, report):
        fd = report["final_decision"].lower()
        assert "raw-accessible" in fd or "add_on" in fd or "add-on" in fd


class TestP247CMarkdown:
    def test_md_exists(self, md):
        assert len(md) > 100

    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_add_on_raw_accessible(self, md):
        assert "raw-accessible" in md.lower()

    def test_md_no_rows_deleted(self, md):
        text = md.lower()
        assert "no rows deleted" in text or "no row" in text

    def test_md_annotation_table_not_created(self, md):
        assert "annotation" in md.lower()
        assert "no annotation table" in md.lower()


class TestP247CLiveDB:
    def test_view_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name=?", (VIEW_NAME,)
        ).fetchone()
        assert row is not None

    def test_view_row_count(self, conn):
        cnt = conn.execute(f"SELECT COUNT(*) FROM {VIEW_NAME}").fetchone()[0]
        assert cnt == EXPECTED_CANONICAL

    def test_raw_big_lotto_count(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == EXPECTED_RAW

    def test_add_on_raw_count(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
        ).fetchone()[0]
        assert cnt == EXPECTED_ADD_ON

    def test_no_hyphen_in_view(self, conn):
        cnt = conn.execute(
            f"SELECT COUNT(*) FROM {VIEW_NAME} WHERE draw LIKE '%-%'"
        ).fetchone()[0]
        assert cnt == 0

    def test_no_date_format_in_view(self, conn):
        cnt = conn.execute(
            f"SELECT COUNT(*) FROM {VIEW_NAME} WHERE LENGTH(draw)=8 AND draw LIKE '20%'"
        ).fetchone()[0]
        assert cnt == 0

    def test_all_max_numbers_gt25(self, conn):
        cnt = conn.execute(f"""
            SELECT COUNT(*) FROM {VIEW_NAME} v
            WHERE (
                SELECT MAX(CAST(j.value AS INTEGER))
                FROM json_each(v.numbers) j
            ) <= 25
        """).fetchone()[0]
        assert cnt == 0

    def test_annotation_table_not_created(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name='draw_row_family_annotations'"
        ).fetchone()
        assert row is None

    def test_db_integrity(self, conn):
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert result == "ok"

    def test_row_family_sum(self, conn):
        raw = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        add_on = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
        ).fetchone()[0]
        date_fmt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
            " AND draw NOT LIKE '%-%' AND LENGTH(draw)=8 AND draw LIKE '20%'"
        ).fetchone()[0]
        small_pool = conn.execute("""
            SELECT COUNT(*) FROM draws d
            WHERE d.lottery_type='BIG_LOTTO'
              AND d.draw NOT LIKE '%-%'
              AND NOT (LENGTH(d.draw)=8 AND d.draw LIKE '20%')
              AND (SELECT MAX(CAST(j.value AS INTEGER)) FROM json_each(d.numbers) j) <= 25
        """).fetchone()[0]
        canonical = conn.execute(f"SELECT COUNT(*) FROM {VIEW_NAME}").fetchone()[0]
        assert add_on + date_fmt + small_pool + canonical == raw


class TestP247ATestUpdated:
    """Verify the updated P247A test no longer fails due to view existence."""

    def test_p247a_artifact_still_records_sql_not_applied(self):
        p247a_json = REPO_ROOT / "outputs" / "research" / \
            "p247a_big_lotto_canonical_view_annotation_dryrun_plan_20260606.json"
        assert p247a_json.exists()
        data = json.loads(p247a_json.read_text())
        assert data["sql_applied"] is False
        assert data["db_write_performed"] is False

    def test_p247a_artifact_records_view_was_absent_at_dryrun_time(self):
        p247a_json = REPO_ROOT / "outputs" / "research" / \
            "p247a_big_lotto_canonical_view_annotation_dryrun_plan_20260606.json"
        data = json.loads(p247a_json.read_text())
        v = data.get("dry_run_validation", {})
        assert v.get("canonical_view_already_exists") is False

    def test_p247a_test_does_not_require_view_absence(self):
        """Verify the updated P247A test file no longer asserts live DB view absence."""
        test_path = REPO_ROOT / "tests" / \
            "test_p247a_big_lotto_canonical_view_annotation_dryrun_plan.py"
        content = test_path.read_text()
        # The old failing assertion text must not appear in the file
        assert '"draws_big_lotto_canonical_main" not in views' not in content, (
            "Old live-DB view-absence assertion still present in P247A test file"
        )
