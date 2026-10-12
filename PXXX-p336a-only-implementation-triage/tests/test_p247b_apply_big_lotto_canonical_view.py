"""Tests for P247B — BIG_LOTTO canonical view apply."""

import json
import sqlite3
from pathlib import Path

import pytest

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs" / "research"
JSON_PATH = OUTPUTS_DIR / "p247b_apply_big_lotto_canonical_view_20260606.json"
DB_PATH = Path(__file__).parent.parent / "lottery_api" / "data" / "lottery_v2.db"
BACKUPS_DIR = Path(__file__).parent.parent / "backups"
VIEW_NAME = "draws_big_lotto_canonical_main"
EXPECTED_CANONICAL = 2_113
EXPECTED_RAW_BIG_LOTTO = 22_238
EXPECTED_ADD_ON = 19_100


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P247B JSON artifact not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text())


@pytest.fixture(scope="module")
def conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    c = sqlite3.connect(str(DB_PATH))
    yield c
    c.close()


class TestP247BJSONArtifact:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_task_id(self, report):
        assert report["task_id"] == "P247B"

    def test_classification(self, report):
        assert report["classification"] == "TYPE_D_CONTROLLED_APPLY"

    def test_p247a_merged_pr(self, report):
        assert report["p247a_merged_pr"] == 327

    def test_explicit_authorization_present(self, report):
        assert "YES apply P247B" in report["explicit_authorization_confirmed"]

    def test_view_name(self, report):
        assert report["view_name"] == VIEW_NAME

    def test_view_created_true(self, report):
        assert report["view_created"] is True

    def test_view_row_count_correct(self, report):
        assert report["post_apply_counts"]["view_rows"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_preserved(self, report):
        assert report["post_apply_counts"]["raw_big_lotto"] == EXPECTED_RAW_BIG_LOTTO

    def test_add_on_preserved(self, report):
        assert report["post_apply_counts"]["add_on"] == EXPECTED_ADD_ON

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_annotation_table_not_created(self, report):
        assert report["annotation_table_created"] is False

    def test_db_integrity_ok(self, report):
        assert report["db_integrity_result"] == "ok"

    def test_forbidden_actions_confirmed(self, report):
        fac = report["forbidden_actions_confirmed"]
        for action, status in fac.items():
            assert status == "NOT PERFORMED", f"Forbidden action '{action}' has unexpected status: {status}"

    def test_raw_rows_preserved(self, report):
        assert report["raw_rows_preserved"] is True

    def test_canonical_count_correct(self, report):
        assert report["canonical_count_correct"] is True


class TestP247BBackup:
    def test_backup_path_in_report(self, report):
        assert report["backup_path"] is not None

    def test_backup_file_exists(self, report):
        p = Path(report["backup_path"])
        assert p.exists(), f"Backup file not found: {p}"

    def test_sha256_file_exists(self, report):
        p = Path(report["backup_path"]).with_suffix(".db.sha256")
        assert p.exists(), f"SHA256 file not found: {p}"

    def test_sha256_value_present(self, report):
        assert report["backup_sha256"] is not None
        assert len(report["backup_sha256"]) == 64


class TestP247BLiveDB:
    def test_view_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name=?",
            (VIEW_NAME,)
        ).fetchone()
        assert row is not None, f"View {VIEW_NAME} does not exist in DB"

    def test_view_row_count(self, conn):
        cnt = conn.execute(f"SELECT COUNT(*) FROM {VIEW_NAME}").fetchone()[0]
        assert cnt == EXPECTED_CANONICAL, f"View row count {cnt} != expected {EXPECTED_CANONICAL}"

    def test_raw_big_lotto_count(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == EXPECTED_RAW_BIG_LOTTO

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

    def test_no_date_format_alien_in_view(self, conn):
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
            "SELECT name FROM sqlite_master WHERE type='table' AND name='draw_row_family_annotations'"
        ).fetchone()
        assert row is None, "Annotation table was created — forbidden!"

    def test_db_integrity(self, conn):
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert result == "ok"

    def test_view_lottery_type_all_big_lotto(self, conn):
        cnt = conn.execute(
            f"SELECT COUNT(*) FROM {VIEW_NAME} WHERE lottery_type != 'BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == 0
