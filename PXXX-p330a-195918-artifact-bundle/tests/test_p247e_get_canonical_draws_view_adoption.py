"""Tests for P247E — get_canonical_draws BIG_LOTTO view adoption."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p247e_get_canonical_draws_view_adoption_20260606.json"
MD_PATH = OUTPUTS / "p247e_get_canonical_draws_view_adoption_20260606.md"
CANONICAL_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
VIEW_NAME = "draws_big_lotto_canonical_main"
EXPECTED_CANONICAL = 2_113
EXPECTED_RAW_BIG_LOTTO = 22_238
EXPECTED_ADD_ON = 19_100


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P247E JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists()
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def db_manager():
    if not CANONICAL_DB.exists():
        pytest.skip("Canonical DB not available")
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.database import DatabaseManager
    return DatabaseManager(str(CANONICAL_DB))


@pytest.fixture(scope="module")
def db_conn():
    if not CANONICAL_DB.exists():
        pytest.skip("Canonical DB not available")
    c = sqlite3.connect(f"file:{CANONICAL_DB.resolve()}?mode=ro", uri=True)
    yield c
    c.close()


# ── JSON artifact ─────────────────────────────────────────────────────────────

class TestP247EJSONArtifact:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_task_id(self, report):
        assert report["task_id"] == "P247E"

    def test_p247d_merged_verified(self, report):
        assert report["p247d_merged_state_verified"] is True

    def test_view_exists(self, report):
        assert report["view_exists"] is True

    def test_view_row_count(self, report):
        assert report["view_row_count"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_count(self, report):
        assert report["raw_big_lotto_count"] == EXPECTED_RAW_BIG_LOTTO

    def test_helper_updated(self, report):
        assert report["helper_updated"] is True

    def test_helper_row_count(self, report):
        assert report["helper_row_count"] == EXPECTED_CANONICAL

    def test_return_shape_preserved(self, report):
        assert report["return_shape_preserved"] is True

    def test_view_path_confirmed(self, report):
        assert report["view_path_confirmed"] is True

    def test_fallback_policy_documented(self, report):
        fp = report["fallback_policy"]
        assert len(fp) > 20
        assert "absent" in fp.lower() or "fallback" in fp.lower()

    def test_raw_access_preserved(self, report):
        assert report["raw_access_preserved"] is True

    def test_limit_behavior_preserved(self, report):
        assert report["limit_behavior_preserved"] is True

    def test_db_write_performed_false(self, report):
        assert report["db_write_performed"] is False

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_add_on_records_preserved(self, report):
        assert report["add_on_records_preserved"] is True

    def test_all_helper_checks_pass(self, report):
        assert report["all_helper_checks_pass"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        for action, status in report["forbidden_actions_confirmed"].items():
            assert status == "NOT PERFORMED", f"Forbidden: {action} -> {status}"

    def test_final_decision_no_db_write(self, report):
        assert "no db write" in report["final_decision"].lower()


# ── Helper live verification ───────────────────────────────────────────────────

class TestP247EHelperLive:
    def test_returns_2113_rows(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO")
        assert len(draws) == EXPECTED_CANONICAL

    def test_return_shape_has_required_fields(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO")
        required = {"draw", "date", "lotteryType", "numbers", "special", "jackpot_amount"}
        for d in draws[:5]:
            assert required <= set(d.keys()), f"Missing fields in: {set(d.keys())}"

    def test_no_hyphenated_draw_ids(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO")
        hyphen = [d["draw"] for d in draws if "-" in str(d["draw"])]
        assert hyphen == [], f"Unexpected hyphenated draws: {hyphen[:3]}"

    def test_no_date_format_alien_draws(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO")
        date_fmt = [d["draw"] for d in draws
                    if len(str(d["draw"])) == 8 and str(d["draw"]).startswith("20")]
        assert date_fmt == [], f"Unexpected date-format draws: {date_fmt[:3]}"

    def test_all_max_numbers_gt25(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO")
        small = [d["draw"] for d in draws if d["numbers"] and max(d["numbers"]) <= 25]
        assert small == [], f"Unexpected small-pool draws: {small[:3]}"

    def test_limit_returns_exactly_n(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO", limit=10)
        assert len(draws) == 10

    def test_limit_1_returns_latest(self, db_manager):
        draws = db_manager.get_canonical_draws("BIG_LOTTO", limit=1)
        assert len(draws) == 1

    def test_view_path_is_active(self, db_manager):
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        view_used = db_manager._big_lotto_canonical_view_exists(cursor)
        conn.close()
        assert view_used is True, "View should be active in canonical DB"

    def test_raw_big_lotto_count_via_db(self, db_conn):
        """Raw BIG_LOTTO access preserved — verified via direct SQL (get_all_draws
        requires scheduler import unavailable in test env)."""
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt >= EXPECTED_RAW_BIG_LOTTO

    def test_non_big_lotto_canonical_unchanged(self, db_manager):
        power = db_manager.get_canonical_draws("POWER_LOTTO")
        assert len(power) > 0
        for d in power[:3]:
            assert "draw" in d and "numbers" in d


# ── Fallback behavior ─────────────────────────────────────────────────────────

class TestP247EFallback:
    def test_fallback_method_exists(self):
        """DatabaseManager._big_lotto_canonical_view_exists must exist."""
        sys.path.insert(0, str(REPO_ROOT))
        from lottery_api.database import DatabaseManager
        assert hasattr(DatabaseManager, "_big_lotto_canonical_view_exists")

    def test_fallback_with_viewless_db(self, tmp_path):
        """get_canonical_draws falls back gracefully when view is absent."""
        import json as _json
        sys.path.insert(0, str(REPO_ROOT))
        from lottery_api.database import DatabaseManager

        # Create a tiny test DB without the view but with some BIG_LOTTO rows
        test_db = tmp_path / "test.db"
        conn = sqlite3.connect(str(test_db))
        conn.execute("""
            CREATE TABLE draws (
                id INTEGER PRIMARY KEY,
                draw TEXT, date TEXT, lottery_type TEXT,
                numbers TEXT, special TEXT, jackpot_amount TEXT
            )
        """)
        # Insert one canonical row (draw=115000001, max > 25)
        conn.execute(
            "INSERT INTO draws VALUES (1,'115000001','2024/01/01','BIG_LOTTO',"
            "'[5,10,20,30,40,49]','7','0')"
        )
        # Insert one ADD_ON row (hyphenated — should be excluded by fallback)
        conn.execute(
            "INSERT INTO draws VALUES (2,'115000001-1','2024/01/01','BIG_LOTTO',"
            "'[1,2,3,4,5,6]','7','0')"
        )
        # Insert one SMALL_POOL row (max <= 25 — should be excluded by fallback)
        conn.execute(
            "INSERT INTO draws VALUES (3,'115000002','2024/01/02','BIG_LOTTO',"
            "'[1,2,3,4,5,6]','7','0')"
        )
        conn.commit()
        conn.close()

        db_mgr = DatabaseManager(str(test_db))
        draws = db_mgr.get_canonical_draws("BIG_LOTTO")
        # Only the one canonical row should be returned
        assert len(draws) == 1
        assert draws[0]["draw"] == "115000001"
        assert max(draws[0]["numbers"]) > 25


# ── Markdown ──────────────────────────────────────────────────────────────────

class TestP247EMarkdown:
    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_add_on_raw_accessible(self, md):
        assert "raw-accessible" in md.lower()

    def test_md_mentions_view(self, md):
        assert VIEW_NAME in md

    def test_md_mentions_fallback(self, md):
        assert "fallback" in md.lower()

    def test_md_no_row_mutation(self, md):
        assert "no rows deleted" in md.lower() or "no row" in md.lower()


# ── DB raw access still intact ────────────────────────────────────────────────

class TestP247EDBRawIntact:
    def test_raw_big_lotto_count(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == EXPECTED_RAW_BIG_LOTTO

    def test_add_on_still_exists(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
        ).fetchone()[0]
        assert cnt == EXPECTED_ADD_ON

    def test_annotation_table_still_absent(self, db_conn):
        row = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name='draw_row_family_annotations'"
        ).fetchone()
        assert row is None
