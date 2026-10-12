"""Tests for P247D — BIG_LOTTO canonical view consumer adoption audit."""

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p247d_big_lotto_canonical_view_consumer_adoption_audit_20260606.json"
MD_PATH = OUTPUTS / "p247d_big_lotto_canonical_view_consumer_adoption_audit_20260606.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
VIEW_NAME = "draws_big_lotto_canonical_main"
EXPECTED_CANONICAL = 2_113
EXPECTED_RAW = 22_238
EXPECTED_ADD_ON = 19_100

VALID_CLASSIFICATIONS = {
    "ALREADY_VIEW_BACKED",
    "ALREADY_HELPER_CANONICAL",
    "RAW_HISTORY_ALLOWED",
    "SHOULD_ADOPT_VIEW",
    "SHOULD_KEEP_HELPER",
    "FUTURE_SCOPE_REQUIRES_AUTHORIZATION",
    "NOT_AFFECTED",
    "UNKNOWN_NEEDS_REVIEW",
}


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P247D JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists(), f"P247D MD not found: {MD_PATH}"
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def conn():
    if not DB_PATH.exists():
        pytest.skip("DB not available")
    c = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
    yield c
    c.close()


class TestP247DJSONStructure:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_task_id(self, report):
        assert report["task_id"] == "P247D"

    def test_classification_contains_audit(self, report):
        assert "AUDIT" in report["classification"].upper()

    def test_read_only_confirmed(self, report):
        assert report["read_only_confirmed"] is True

    def test_p247c_merged_state_verified(self, report):
        assert report["p247c_merged_state_verified"] is True


class TestP247DViewCounts:
    def test_view_exists(self, report):
        assert report["view_exists"] is True

    def test_view_row_count(self, report):
        assert report["view_row_count"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_count(self, report):
        assert report["raw_big_lotto_count"] == EXPECTED_RAW

    def test_add_on_count(self, report):
        assert report["add_on_count"] == EXPECTED_ADD_ON

    def test_db_integrity_ok(self, report):
        assert report["db_integrity_result"] == "ok"

    def test_annotation_table_still_not_created(self, report):
        assert report["annotation_table_exists"] is False


class TestP247DCompliance:
    def test_db_write_performed_false(self, report):
        assert report["db_write_performed"] is False

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_add_on_records_preserved(self, report):
        assert report["add_on_records_preserved"] is True

    def test_annotation_table_deferred(self, report):
        assert report["annotation_table_deferred"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        fac = report["forbidden_actions_confirmed"]
        for action, status in fac.items():
            assert status == "NOT PERFORMED", (
                f"Forbidden action '{action}' has unexpected status: {status}"
            )

    def test_final_decision_no_db_write(self, report):
        fd = report["final_decision"].lower()
        assert "no db write" in fd

    def test_final_decision_add_on_preserved(self, report):
        fd = report["final_decision"].lower()
        assert "add-on" in fd or "add_on" in fd or "19100" in fd


class TestP247DConsumerClassifications:
    def test_consumer_classifications_present(self, report):
        cc = report["consumer_classifications"]
        assert isinstance(cc, list)
        assert len(cc) >= 10

    def test_all_classifications_valid(self, report):
        for c in report["consumer_classifications"]:
            assert c["classification"] in VALID_CLASSIFICATIONS, (
                f"Invalid classification: {c['classification']} for path {c['path']}"
            )

    def test_has_already_view_backed(self, report):
        classes = [c["classification"] for c in report["consumer_classifications"]]
        assert "ALREADY_VIEW_BACKED" in classes

    def test_has_already_helper_canonical(self, report):
        classes = [c["classification"] for c in report["consumer_classifications"]]
        assert "ALREADY_HELPER_CANONICAL" in classes

    def test_has_raw_history_allowed(self, report):
        classes = [c["classification"] for c in report["consumer_classifications"]]
        assert "RAW_HISTORY_ALLOWED" in classes

    def test_has_future_scope(self, report):
        classes = [c["classification"] for c in report["consumer_classifications"]]
        assert "FUTURE_SCOPE_REQUIRES_AUTHORIZATION" in classes

    def test_backtest_framework_is_helper_canonical(self, report):
        paths = {c["path"]: c["classification"] for c in report["consumer_classifications"]}
        bf = next((v for k, v in paths.items() if "backtest_framework" in k), None)
        assert bf == "ALREADY_HELPER_CANONICAL", (
            f"backtest_framework.py should be ALREADY_HELPER_CANONICAL, got {bf}"
        )

    def test_quick_predict_is_helper_canonical(self, report):
        paths = {c["path"]: c["classification"] for c in report["consumer_classifications"]}
        qp = next((v for k, v in paths.items() if "quick_predict" in k), None)
        assert qp == "ALREADY_HELPER_CANONICAL"

    def test_raw_history_routes_not_changed(self, report):
        raw = [c for c in report["consumer_classifications"]
               if c["classification"] == "RAW_HISTORY_ALLOWED"]
        for r in raw:
            assert r["action"] == "DO_NOT_CHANGE"

    def test_scan_hits_counts_present(self, report):
        sh = report["consumer_scan_hits"]
        assert "total_consumers_classified" in sh
        assert sh["total_consumers_classified"] >= 10
        assert sh.get("already_view_backed", 0) >= 1
        assert sh.get("already_helper_canonical", 0) >= 1


class TestP247DAdoptionPlan:
    def test_recommended_adoption_plan_present(self, report):
        plan = report["recommended_adoption_plan"]
        assert isinstance(plan, dict)
        assert len(plan) >= 3

    def test_future_scope_items_present(self, report):
        fi = report["future_scope_items"]
        assert isinstance(fi, list)
        assert len(fi) >= 2

    def test_annotation_table_explicitly_deferred(self, report):
        fi_str = " ".join(report["future_scope_items"]).lower()
        assert "annotation" in fi_str
        assert "deferred" in fi_str or "future" in fi_str


class TestP247DMarkdown:
    def test_md_exists(self, md):
        assert len(md) > 200

    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_add_on_raw_accessible(self, md):
        assert "raw-accessible" in md.lower()

    def test_md_annotation_deferred(self, md):
        assert "annotation" in md.lower() and "deferred" in md.lower()

    def test_md_no_row_mutation(self, md):
        assert "no rows deleted" in md.lower() or "no row" in md.lower()


class TestP247DLiveDB:
    def test_view_still_correct(self, conn):
        cnt = conn.execute(f"SELECT COUNT(*) FROM {VIEW_NAME}").fetchone()[0]
        assert cnt == EXPECTED_CANONICAL

    def test_raw_count_still_correct(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == EXPECTED_RAW

    def test_add_on_still_preserved(self, conn):
        cnt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
        ).fetchone()[0]
        assert cnt == EXPECTED_ADD_ON

    def test_annotation_table_still_not_created(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name='draw_row_family_annotations'"
        ).fetchone()
        assert row is None
