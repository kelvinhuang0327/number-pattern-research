"""P247G — BIG_LOTTO canonical isolation final guard tests.

Regression guard: fails if active BIG_LOTTO research paths use raw get_all_draws.
Verifies DB view, helper, and raw access preservation.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
JSON_PATH = OUTPUTS / "p247g_big_lotto_canonical_isolation_final_guard_20260606.json"
MD_PATH = OUTPUTS / "p247g_big_lotto_canonical_isolation_final_guard_20260606.md"
CANONICAL_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CANONICAL = 2_114   # updated: +1 draw 115000059 accepted 2026-06-08
EXPECTED_RAW = 22_239        # updated: +1 draw 115000059 accepted 2026-06-08
EXPECTED_ADD_ON = 19_100

# ── Active research/analysis paths: must NOT use raw get_all_draws('BIG_LOTTO') ─
ACTIVE_CANONICAL_PATHS = [
    # Production pipeline
    "tools/quick_predict.py",
    "tools/rsm_bootstrap.py",
    "lottery_api/backtest_framework.py",
    "lottery_api/engine/core_satellite.py",
    "lottery_api/engine/drift_detector.py",
    "lottery_api/utils/scheduler.py",
    # P247F-migrated analysis tools
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

# Expected canonical pattern per path (what they should contain)
CANONICAL_PATTERNS = {
    "tools/quick_predict.py": "get_canonical_draws",
    "tools/rsm_bootstrap.py": "get_canonical_draws",
    "lottery_api/backtest_framework.py": "get_canonical_draws",
    "lottery_api/engine/core_satellite.py": "get_canonical_draws",
    "lottery_api/engine/drift_detector.py": "canonical",
    "lottery_api/utils/scheduler.py": "canonical",
    "tools/analyze_banker_accuracy.py": "get_canonical_draws",
    "tools/analyze_banker_plus_kill.py": "get_canonical_draws",
    "tools/analyze_biglotto_special.py": "get_canonical_draws",
    "tools/analyze_market_temperature.py": "get_canonical_draws",
    "tools/analyze_top_n_for_2.py": "get_canonical_draws",
    "tools/audit_big_lotto_3bet.py": "get_canonical_draws",
    "tools/audit_big_lotto_baseline.py": "get_canonical_draws",
    "tools/audit_big_lotto_hyper.py": "get_canonical_draws",
    "tools/audit_big_lotto_rigorous.py": "get_canonical_draws",
}

RAW_BIG_LOTTO_PATTERNS = [
    "get_all_draws(lottery_type='BIG_LOTTO')",
    "get_all_draws('BIG_LOTTO')",
]


@pytest.fixture(scope="module")
def report():
    assert JSON_PATH.exists(), f"P247G JSON not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    assert MD_PATH.exists()
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def db_conn():
    if not CANONICAL_DB.exists():
        pytest.skip("Canonical DB not available")
    c = sqlite3.connect(str(CANONICAL_DB))
    yield c
    c.close()


# ── JSON artifact ─────────────────────────────────────────────────────────────

class TestP247GJSONArtifact:
    def test_json_parses(self, report):
        assert isinstance(report, dict)

    def test_task_id(self, report):
        assert report["task_id"] == "P247G"

    def test_schema_version(self, report):
        assert report["schema_version"] == "1.0"

    def test_p247f_merged_verified(self, report):
        assert report["p247f_merged_state_verified"] is True

    def test_read_only_confirmed(self, report):
        assert report["read_only_confirmed"] is True

    def test_view_row_count(self, report):
        assert report["view_row_count"] == EXPECTED_CANONICAL

    def test_helper_row_count(self, report):
        assert report["helper_row_count"] == EXPECTED_CANONICAL

    def test_raw_big_lotto_count(self, report):
        assert report["raw_big_lotto_count"] == EXPECTED_RAW

    def test_add_on_count(self, report):
        assert report["add_on_count"] == EXPECTED_ADD_ON

    def test_db_integrity_ok(self, report):
        assert report["db_integrity"] == "ok"

    def test_annotation_table_absent(self, report):
        assert report["annotation_table_exists"] is False

    def test_db_precheck_correct(self, report):
        assert report["db_precheck_all_correct"] is True

    def test_active_paths_all_ok(self, report):
        assert report["active_paths_verified"]["all_ok"] is True

    def test_active_paths_count(self, report):
        assert report["active_paths_verified"]["path_count"] == 15

    def test_raw_paths_preserved(self, report):
        assert report["raw_paths_preserved"]["raw_access_preserved"] is True

    def test_regression_guard_added(self, report):
        assert report["regression_guard_added"] is True

    def test_db_write_performed_false(self, report):
        assert report["db_write_performed"] is False

    def test_no_row_insert_update_delete(self, report):
        assert report["no_row_insert_update_delete"] is True

    def test_add_on_records_preserved(self, report):
        assert report["add_on_records_preserved"] is True

    def test_forbidden_actions_all_not_performed(self, report):
        for action, status in report["forbidden_actions_confirmed"].items():
            assert status == "NOT PERFORMED", f"Forbidden: {action} -> {status}"

    def test_p247_arc_summary_complete(self, report):
        arc = report["p247_arc_summary"]
        for task in ["P247A", "P247B", "P247C", "P247D", "P247E", "P247F", "P247G"]:
            assert task in arc

    def test_deferred_archived_paths_documented(self, report):
        deferred = report["deferred_archived_paths"]
        assert isinstance(deferred, list) and len(deferred) >= 3

    def test_final_decision_no_db_write(self, report):
        assert "no db write" in report["final_decision"].lower()


# ── Regression guard: active paths must NOT have raw BIG_LOTTO calls ──────────

class TestP247GRegressionGuard:
    @pytest.mark.parametrize("tool_path", ACTIVE_CANONICAL_PATHS)
    def test_active_path_no_raw_big_lotto(self, tool_path):
        """REGRESSION GUARD: active BIG_LOTTO research paths must not use raw get_all_draws."""
        path = REPO_ROOT / tool_path
        assert path.exists(), f"Active path not found: {path}"
        content = path.read_text(errors="replace")
        for pattern in RAW_BIG_LOTTO_PATTERNS:
            assert pattern not in content, (
                f"REGRESSION in {tool_path}: raw BIG_LOTTO call found: '{pattern}'. "
                f"Use get_canonical_draws('BIG_LOTTO') instead."
            )

    @pytest.mark.parametrize("tool_path", ACTIVE_CANONICAL_PATHS)
    def test_active_path_has_canonical_pattern(self, tool_path):
        """Each active path must contain its expected canonical pattern."""
        path = REPO_ROOT / tool_path
        content = path.read_text(errors="replace")
        expected = CANONICAL_PATTERNS[tool_path]
        assert expected in content, (
            f"{tool_path} does not contain expected canonical pattern: '{expected}'"
        )

    def test_database_py_has_canonical_view_constant(self):
        """database.py must define the canonical view name constant (P247E)."""
        db_py = (REPO_ROOT / "lottery_api" / "database.py").read_text()
        assert "draws_big_lotto_canonical_main" in db_py
        assert "_big_lotto_canonical_view_exists" in db_py

    def test_database_py_raw_access_preserved(self):
        """Raw access methods must still exist in database.py."""
        db_py = (REPO_ROOT / "lottery_api" / "database.py").read_text()
        assert "def get_all_draws" in db_py
        assert "def get_draws" in db_py

    def test_database_py_canonical_view_preferred(self):
        """get_canonical_draws must prefer the view path (P247E)."""
        db_py = (REPO_ROOT / "lottery_api" / "database.py").read_text()
        assert "draws_big_lotto_canonical_main" in db_py
        assert "view absent" in db_py or "fallback" in db_py.lower()


# ── Live DB verification ───────────────────────────────────────────────────────

class TestP247GLiveDB:
    def test_view_still_canonical(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws_big_lotto_canonical_main"
        ).fetchone()[0]
        assert cnt == EXPECTED_CANONICAL

    def test_raw_still_22239(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
        ).fetchone()[0]
        assert cnt == EXPECTED_RAW

    def test_add_on_still_19100(self, db_conn):
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

    def test_view_no_hyphen_draws(self, db_conn):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM draws_big_lotto_canonical_main WHERE draw LIKE '%-%'"
        ).fetchone()[0]
        assert cnt == 0

    def test_view_integrity(self, db_conn):
        result = db_conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert result == "ok"


# ── Markdown ──────────────────────────────────────────────────────────────────

class TestP247GMarkdown:
    def test_md_no_db_write(self, md):
        assert "no db write" in md.lower()

    def test_md_add_on_raw_accessible(self, md):
        assert "raw-accessible" in md.lower()

    def test_md_mentions_arc_complete(self, md):
        assert "P247G" in md and "P247A" in md

    def test_md_mentions_regression_guard(self, md):
        assert "regression" in md.lower() or "guard" in md.lower()

    def test_md_mentions_deferred(self, md):
        assert "deferred" in md.lower()
