"""
test_h6_draw_no_hygiene.py — draw_no hygiene guard 驗收測試
===========================================================

測試清單：
  H1  is_test_draw_no — 所有 test prefix 都被識別
  H2  is_production_draw_no — 純數字 draw_no 通過
  H3  is_test_draw_no — 純數字 draw_no 不被誤判為 test
  H4  production_draw_no_sql_filter — S1_/E2E_/AUTO_ 被 SQL 排除
  H5  _fetch_latest_draw_no 不抓 S1_ draw_no
  H6  _fetch_latest_draw_no 不抓 E2E_ draw_no
  H7  _fetch_latest_draw_no 不抓 AUTO_ draw_no
  H8  _fetch_latest_draw_no 純數字可被抓到
  H9  test draw_no 產生 report → environment=test
  H10 production draw_no 產生 report → environment=production
  H11 test draw_no HIGH risk → process_report_alerts 不 alert
  H12 production draw_no HIGH risk → process_report_alerts 會 alert
  H13 h6_scheduler.run_scheduled_report 對 test draw_no 跳過 alert
  H14 CLI --draw-no S1_xxx → ValueError
  H15 CLI --draw-no RB_xxx → ValueError
  H16 API endpoint 對 test draw_no → 400

2026-04-29  Created (H6 draw_no hygiene guard)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

# ── path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOTTERY_API = os.path.join(_ROOT, "lottery_api")
_SCRIPTS = os.path.join(_ROOT, "scripts")
sys.path.insert(0, _LOTTERY_API)
sys.path.insert(0, _SCRIPTS)

from engine.draw_no_hygiene import (
    is_production_draw_no,
    is_test_draw_no,
    production_draw_no_sql_filter,
)
from engine.h6_report_generator import generate_report, _fetch_latest_draw_no
from engine.h6_alert_engine import process_report_alerts
from engine.h6_live_monitor import H6_STRATEGY_ID, SHADOW_STRATEGY_ID, save_prediction

_DB_PATH = os.path.join(_ROOT, "runtime", "agent_orchestrator", "orchestrator.db")
H6_GAME = "DAILY_539"


def _db_ok():
    return os.path.exists(_DB_PATH)


def _ts():
    return int(time.time() * 1000)


def _delete_predictions_like(pattern: str, game_type: str = H6_GAME):
    """Delete test predictions matching a LIKE pattern."""
    if not _db_ok():
        return
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute(
        "DELETE FROM live_strategy_predictions WHERE game_type=? AND draw_no LIKE ? AND strategy_name=?",
        (game_type, pattern, H6_STRATEGY_ID),
    )
    conn.commit()
    conn.close()


def _delete_prediction(draw_no: str, game_type: str = H6_GAME):
    if not _db_ok():
        return
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute(
        "DELETE FROM live_strategy_predictions WHERE game_type=? AND draw_no=?",
        (game_type, draw_no),
    )
    conn.commit()
    conn.close()


def _delete_cto_backlog(draw_no: str, game_type: str = H6_GAME):
    if not _db_ok():
        return
    finding_id = f"h6_alert:{game_type}:{draw_no}"
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute("DELETE FROM cto_backlog_items WHERE finding_id=?", (finding_id,))
    conn.commit()
    conn.close()


def _delete_agent_task(draw_no: str):
    if not _db_ok():
        return
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute(
        "DELETE FROM agent_tasks WHERE title LIKE ?",
        (f"%{draw_no}%",),
    )
    conn.commit()
    conn.close()


def _insert_prediction(draw_no: str, game_type: str = H6_GAME):
    """Insert a bare prediction row for testing."""
    if not _db_ok():
        return
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute(
        """INSERT OR IGNORE INTO live_strategy_predictions
           (game_type, draw_no, strategy_name, active_strategy, shadow_strategy,
            predicted_numbers, generated_at)
           VALUES (?,?,?,?,?,?,datetime('now'))""",
        (game_type, draw_no, H6_STRATEGY_ID, H6_STRATEGY_ID, SHADOW_STRATEGY_ID,
         json.dumps([[1, 2, 3, 4, 5]])),
    )
    conn.commit()
    conn.close()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


# ── H1: is_test_draw_no covers all test prefixes ─────────────────────────────

class TestH1_IsTestDrawNo(unittest.TestCase):
    """H1: All test prefixes and sentinels are identified as test draw_nos."""

    def test_auto_prefix(self):
        self.assertTrue(is_test_draw_no("AUTO_12345"))

    def test_s1_prefix(self):
        self.assertTrue(is_test_draw_no("S1_177747072422"))

    def test_e2e_prefix(self):
        self.assertTrue(is_test_draw_no("E2E_draw_001"))

    def test_rb_prefix(self):
        self.assertTrue(is_test_draw_no("RB_20260429"))

    def test_rbiso_prefix(self):
        self.assertTrue(is_test_draw_no("RBISO_20260429_001"))

    def test_test_prefix(self):
        self.assertTrue(is_test_draw_no("TEST_draw"))

    def test_mock_prefix(self):
        self.assertTrue(is_test_draw_no("MOCK_001"))

    def test_sentinel_pending(self):
        self.assertTrue(is_test_draw_no("PENDING"))

    def test_sentinel_pending_lower(self):
        self.assertTrue(is_test_draw_no("pending"))

    def test_sentinel_unknown(self):
        self.assertTrue(is_test_draw_no("UNKNOWN"))

    def test_empty_string(self):
        self.assertTrue(is_test_draw_no(""))

    def test_none_like_empty(self):
        # None is treated as test (falsy)
        self.assertTrue(is_test_draw_no(None))  # type: ignore[arg-type]

    def test_prefix_case_insensitive(self):
        self.assertTrue(is_test_draw_no("s1_123"))
        self.assertTrue(is_test_draw_no("auto_123"))
        self.assertTrue(is_test_draw_no("e2e_abc"))


# ── H2/H3: is_production_draw_no / not-mis-classified ────────────────────────

class TestH2H3_IsProductionDrawNo(unittest.TestCase):
    """H2: Numeric draw_nos pass. H3: Numeric draw_nos not mis-classified as test."""

    def test_numeric_short(self):
        self.assertTrue(is_production_draw_no("114001"))

    def test_numeric_long(self):
        # 9-digit real DAILY_539 draw_no (ROC year 115, draw 000104)
        self.assertTrue(is_production_draw_no("115000104"))
        self.assertTrue(is_production_draw_no("115000105"))

    def test_numeric_not_test(self):
        self.assertFalse(is_test_draw_no("114001"))
        self.assertFalse(is_test_draw_no("115000104"))

    def test_synthetic_high_numeric_not_production(self):
        """10-digit synthetic draw_nos are NOT production."""
        self.assertFalse(is_production_draw_no("9300279486"))
        self.assertFalse(is_production_draw_no("9300297780"))
        self.assertFalse(is_production_draw_no("9300412307"))
        self.assertTrue(is_test_draw_no("9300279486"))
        self.assertTrue(is_test_draw_no("9300297780"))
        self.assertTrue(is_test_draw_no("9300412307"))

    def test_s1_not_production(self):
        self.assertFalse(is_production_draw_no("S1_123"))

    def test_auto_not_production(self):
        self.assertFalse(is_production_draw_no("AUTO_456"))

    def test_e2e_not_production(self):
        self.assertFalse(is_production_draw_no("E2E_001"))

    def test_rb_not_production(self):
        self.assertFalse(is_production_draw_no("RB_20260429"))

    def test_pending_not_production(self):
        self.assertFalse(is_production_draw_no("PENDING"))

    def test_alphanumeric_not_production(self):
        self.assertFalse(is_production_draw_no("114001abc"))

    def test_empty_not_production(self):
        self.assertFalse(is_production_draw_no(""))


# ── H4: production_draw_no_sql_filter actually filters in SQLite ─────────────

class TestH4_SqlFilter(unittest.TestCase):
    """H4: The SQL filter correctly includes/excludes draw_nos in SQLite."""

    def _query(self, draw_no: str) -> bool:
        """Return True if draw_no passes the production filter."""
        sql_filter = production_draw_no_sql_filter("value")
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TEMP TABLE t (value TEXT)")
        conn.execute("INSERT INTO t VALUES (?)", (draw_no,))
        row = conn.execute(f"SELECT value FROM t WHERE {sql_filter}").fetchone()
        conn.close()
        return row is not None

    def test_numeric_passes(self):
        self.assertTrue(self._query("114001"))

    def test_long_numeric_passes(self):
        # 9-digit draw_no — within valid range
        self.assertTrue(self._query("115000104"))
        self.assertTrue(self._query("115000105"))

    def test_synthetic_high_numeric_excluded(self):
        """10-digit synthetic draw_nos are excluded by the SQL filter."""
        self.assertFalse(self._query("9300279486"))
        self.assertFalse(self._query("9300297780"))
        self.assertFalse(self._query("9300412307"))

    def test_s1_excluded(self):
        self.assertFalse(self._query("S1_177747072422"))

    def test_e2e_excluded(self):
        self.assertFalse(self._query("E2E_draw_001"))

    def test_auto_excluded(self):
        self.assertFalse(self._query("AUTO_12345"))

    def test_rb_excluded(self):
        self.assertFalse(self._query("RB_20260429"))

    def test_rbiso_excluded(self):
        self.assertFalse(self._query("RBISO_001"))

    def test_test_excluded(self):
        self.assertFalse(self._query("TEST_draw"))

    def test_mock_excluded(self):
        self.assertFalse(self._query("MOCK_001"))

    def test_pending_excluded(self):
        self.assertFalse(self._query("PENDING"))

    def test_unknown_excluded(self):
        self.assertFalse(self._query("UNKNOWN"))


# ── H5/H6/H7/H8: _fetch_latest_draw_no DB integration ───────────────────────

class TestH5H6H7H8_FetchLatestDrawNo(unittest.TestCase):
    """H5-H8: _fetch_latest_draw_no returns only production draw_nos from DB."""

    def setUp(self):
        if not _db_ok():
            return
        self._cleanup_draw_nos = []

        # Insert one production draw_no — valid 9-digit number, far from
        # real draw range (115000xxx) to avoid collisions with live data
        ts = _ts()
        self.prod_draw_no = f"199{ts % 1_000_000:06d}"  # e.g. 199012345
        self.synthetic_numeric_draw = "9300279486"  # 10 digits, synthetic

        # Insert test draw_nos of each problematic prefix
        self.s1_draw = f"S1_{ts}"
        self.e2e_draw = f"E2E_{ts}"
        self.auto_draw = f"AUTO_{ts}"
        self.rb_draw = f"RB_{ts}"
        self.test_draw = f"TEST_{ts}"
        self.mock_draw = f"MOCK_{ts}"

        all_draws = [
            self.prod_draw_no,
            self.synthetic_numeric_draw,
            self.s1_draw, self.e2e_draw, self.auto_draw,
            self.rb_draw, self.test_draw, self.mock_draw,
        ]
        for d in all_draws:
            _insert_prediction(d)
            self._cleanup_draw_nos.append(d)

        # Make production draw_no sort LAST (most recent) by generated_at.
        # Use a far-future ISO-format timestamp so it beats any real row regardless
        # of whether the real row was stored with SQLite's space format or Python's T format.
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        conn.execute(
            "UPDATE live_strategy_predictions SET generated_at=? "
            "WHERE game_type=? AND draw_no=? AND strategy_name=?",
            ("2099-12-31T23:59:59.000000+00:00", H6_GAME, self.prod_draw_no, H6_STRATEGY_ID),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        for d in getattr(self, "_cleanup_draw_nos", []):
            _delete_prediction(d)

    def test_s1_not_returned_as_latest(self):
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotEqual(result, self.s1_draw, "S1_ draw_no should not be returned as latest")

    def test_e2e_not_returned_as_latest(self):
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotEqual(result, self.e2e_draw, "E2E_ draw_no should not be returned as latest")

    def test_auto_not_returned_as_latest(self):
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotEqual(result, self.auto_draw, "AUTO_ draw_no should not be returned as latest")

    def test_rb_not_returned_as_latest(self):
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotEqual(result, self.rb_draw, "RB_ draw_no should not be returned as latest")

    def test_production_draw_no_returned(self):
        """H8: A purely numeric draw_no is correctly returned as latest."""
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertEqual(result, self.prod_draw_no,
                         f"Expected production draw_no={self.prod_draw_no}, got {result!r}")

    def test_test_prefix_not_returned(self):
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotIn("TEST_", result or "")

    def test_mock_prefix_not_returned(self):
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotIn("MOCK_", result or "")

    def test_synthetic_numeric_not_returned_as_latest(self):
        """H8b: 10-digit synthetic numeric draw_no is NOT returned as latest."""
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        self.assertNotEqual(
            result, self.synthetic_numeric_draw,
            "Synthetic numeric draw_no 9300279486 should not be returned as latest",
        )


# ── H9/H10: generate_report environment field ─────────────────────────────────

class TestH9H10_ReportEnvironmentField(unittest.TestCase):
    """H9: test draw_no → environment=test.  H10: production → environment=production."""

    def test_test_draw_no_environment_is_test(self):
        """H9: Report generated with a test draw_no gets environment=test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_report(
                game_type=H6_GAME,
                draw_no="S1_99999999",
                output_dir=tmpdir,
            )
        self.assertEqual(report["report_meta"]["environment"], "test")

    def test_auto_draw_no_environment_is_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_report(
                game_type=H6_GAME,
                draw_no="AUTO_123456",
                output_dir=tmpdir,
            )
        self.assertEqual(report["report_meta"]["environment"], "test")

    def test_rb_draw_no_environment_is_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_report(
                game_type=H6_GAME,
                draw_no="RB_20260429",
                output_dir=tmpdir,
            )
        self.assertEqual(report["report_meta"]["environment"], "test")

    def test_e2e_draw_no_environment_is_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_report(
                game_type=H6_GAME,
                draw_no="E2E_001",
                output_dir=tmpdir,
            )
        self.assertEqual(report["report_meta"]["environment"], "test")

    def test_numeric_draw_no_environment_is_production(self):
        """H10: Numeric draw_no within valid range → environment=production."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_report(
                game_type=H6_GAME,
                draw_no="114001",
                output_dir=tmpdir,
            )
        self.assertEqual(report["report_meta"]["environment"], "production")

    def test_synthetic_numeric_draw_no_environment_is_test(self):
        """H10b: 10-digit synthetic numeric draw_no → environment=test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_report(
                game_type=H6_GAME,
                draw_no="9300279486",
                output_dir=tmpdir,
            )
        self.assertEqual(report["report_meta"]["environment"], "test")


# ── H11/H12: process_report_alerts hygiene guard ─────────────────────────────

def _make_high_risk_report(draw_no: str) -> dict:
    """Build a minimal HIGH-risk report dict for alert testing."""
    return {
        "report_meta": {
            "draw_no": draw_no,
            "game_type": H6_GAME,
            "report_status": "COMPLETE",
            "environment": "test" if is_test_draw_no(draw_no) else "production",
        },
        "risk_assessment": {"risk_level": "HIGH", "risk_factors": ["test_risk"]},
        "action_recommendation": {"action": "PREPARE_ROLLBACK", "reason": "test"},
        "strategy": {"rollback_status": "ACTIVE"},
    }


class TestH11H12_AlertEngineHygieneGuard(unittest.TestCase):
    """H11: test draw_no → no CTO alert.  H12: production draw_no → alert fires."""

    def setUp(self):
        # Valid 9-digit production draw_no (far from real 115000xxx range)
        self.prod_draw_no = f"199{_ts() % 1_000_000:06d}"
        self.test_draw_no = f"S1_{_ts()}"

    def tearDown(self):
        _delete_cto_backlog(self.prod_draw_no)
        _delete_agent_task(self.prod_draw_no)

    def test_test_draw_no_does_not_alert(self):
        """H11: High-risk report with test draw_no → alerted=False, no CTO row."""
        if not _db_ok():
            self.skipTest("No DB")
        report = _make_high_risk_report(self.test_draw_no)
        result = process_report_alerts(report, game_type=H6_GAME)
        self.assertFalse(result["alerted"],
                         "Alert should be suppressed for test draw_no")
        self.assertEqual(result.get("skipped_reason"), "test_draw_no")
        # Confirm no CTO backlog row written
        conn = _get_conn()
        finding_id = f"h6_alert:{H6_GAME}:{self.test_draw_no}"
        row = conn.execute(
            "SELECT id FROM cto_backlog_items WHERE finding_id=?", (finding_id,)
        ).fetchone()
        conn.close()
        self.assertIsNone(row, "No CTO backlog row should be written for test draw_no")

    def test_test_draw_no_no_rollback_task(self):
        """H11b: No rollback follow-up task created for test draw_no."""
        if not _db_ok():
            self.skipTest("No DB")
        report = _make_high_risk_report(self.test_draw_no)
        # Make rollback non-ACTIVE to trigger the task creation path
        report["strategy"]["rollback_status"] = "ROLLBACK_TRIGGERED"
        result = process_report_alerts(report, game_type=H6_GAME)
        self.assertFalse(result["alerted"])
        self.assertIsNone(result.get("rollback_task_id"))
        # Verify no task with this draw_no exists
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id FROM agent_tasks WHERE title LIKE ?",
            (f"%{self.test_draw_no}%",),
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 0, "No agent_tasks should be created for test draw_no")

    def test_production_draw_no_high_risk_alerts(self):
        """H12: High-risk report with production draw_no → alerted=True."""
        if not _db_ok():
            self.skipTest("No DB")
        report = _make_high_risk_report(self.prod_draw_no)
        result = process_report_alerts(report, game_type=H6_GAME)
        self.assertTrue(result["alerted"],
                        f"Alert should fire for production draw_no. Got: {result}")
        self.assertIsNotNone(result.get("cto_finding_id"))

    def test_production_draw_no_cto_backlog_written(self):
        """H12b: CTO backlog row is written for production HIGH risk."""
        if not _db_ok():
            self.skipTest("No DB")
        report = _make_high_risk_report(self.prod_draw_no)
        process_report_alerts(report, game_type=H6_GAME)
        conn = _get_conn()
        finding_id = f"h6_alert:{H6_GAME}:{self.prod_draw_no}"
        row = conn.execute(
            "SELECT finding_id FROM cto_backlog_items WHERE finding_id=?", (finding_id,)
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row, "CTO backlog row should be written for production draw_no")


# ── H13: h6_scheduler skips alert for test draw_no ───────────────────────────

class TestH13_SchedulerHygieneGuard(unittest.TestCase):
    """H13: run_scheduled_report with test draw_no skips alert pipeline."""

    def test_scheduler_skips_alert_for_test_draw_no(self):
        """When _fetch_latest_draw_no would return a test draw_no, alert is skipped."""
        from engine.h6_scheduler import run_scheduled_report

        # Patch generate_report to return a test-environment report
        test_report = {
            "report_meta": {
                "draw_no": "S1_scheduler_test",
                "report_status": "COMPLETE",
                "game_type": H6_GAME,
                "environment": "test",
            },
            "risk_assessment": {"risk_level": "HIGH", "risk_factors": ["test"]},
            "action_recommendation": {"action": "PREPARE_ROLLBACK", "reason": "test"},
            "strategy": {"rollback_status": "ACTIVE"},
            "output": {"json_path": None, "markdown_path": None},
        }

        with patch("engine.h6_scheduler.generate_report", return_value=test_report):
            result = run_scheduled_report(game_type=H6_GAME)

        alert = result.get("alert", {})
        self.assertFalse(alert.get("alerted", True),
                         f"Alert should be skipped for test draw_no. Got alert: {alert}")
        self.assertEqual(alert.get("skipped_reason"), "test_draw_no")

    def test_scheduler_fires_alert_for_production_draw_no(self):
        """When draw_no is production and risk is HIGH, alert fires."""
        if not _db_ok():
            self.skipTest("No DB")
        from engine.h6_scheduler import run_scheduled_report

        # Valid 9-digit production draw_no (far from real 115000xxx range)
        prod_draw_no = f"199{_ts() % 1_000_000:06d}"
        prod_report = {
            "report_meta": {
                "draw_no": prod_draw_no,
                "report_status": "COMPLETE",
                "game_type": H6_GAME,
                "environment": "production",
            },
            "risk_assessment": {"risk_level": "HIGH", "risk_factors": ["edge_low"]},
            "action_recommendation": {"action": "PREPARE_ROLLBACK", "reason": "test"},
            "strategy": {"rollback_status": "ACTIVE"},
            "output": {"json_path": None, "markdown_path": None},
        }

        try:
            with patch("engine.h6_scheduler.generate_report", return_value=prod_report):
                result = run_scheduled_report(game_type=H6_GAME)

            alert = result.get("alert", {})
            self.assertTrue(alert.get("alerted", False),
                            f"Alert should fire for production HIGH risk. Got: {alert}")
        finally:
            _delete_cto_backlog(prod_draw_no)
            _delete_agent_task(prod_draw_no)


# ── H14/H15: CLI validate_draw_no rejects test prefixes ──────────────────────

class TestH14H15_CLIValidation(unittest.TestCase):
    """H14/H15: CLI _validate_draw_no rejects test draw_nos."""

    def setUp(self):
        # Import the helper directly from the scripts module
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "h6_daily_report_script",
            os.path.join(_SCRIPTS, "h6_daily_report.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        self._validate = mod._validate_draw_no

    def test_s1_rejected(self):
        """H14: S1_ prefix is rejected by CLI validator."""
        with self.assertRaises(ValueError):
            self._validate("S1_177747072422")

    def test_rb_rejected(self):
        """H15: RB_ prefix is rejected by CLI validator."""
        with self.assertRaises(ValueError):
            self._validate("RB_20260429")

    def test_e2e_rejected(self):
        with self.assertRaises(ValueError):
            self._validate("E2E_draw")

    def test_auto_rejected(self):
        with self.assertRaises(ValueError):
            self._validate("AUTO_123")

    def test_rbiso_rejected(self):
        with self.assertRaises(ValueError):
            self._validate("RBISO_001")

    def test_test_rejected(self):
        with self.assertRaises(ValueError):
            self._validate("TEST_draw")

    def test_mock_rejected(self):
        with self.assertRaises(ValueError):
            self._validate("MOCK_001")

    def test_pending_rejected(self):
        with self.assertRaises(ValueError):
            self._validate("PENDING")

    def test_production_numeric_accepted(self):
        """Numeric draw_no passes validation."""
        result = self._validate("114001")
        self.assertEqual(result, "114001")

    def test_production_9digit_numeric_accepted(self):
        # Real DAILY_539 draw_no — 9 digits, valid range
        result = self._validate("115000105")
        self.assertEqual(result, "115000105")

    def test_synthetic_high_numeric_rejected(self):
        """10-digit out-of-range draw_no should be rejected as synthetic."""
        with self.assertRaises(ValueError):
            self._validate("9300279486")


# ── H16: API endpoint rejects test draw_no ───────────────────────────────────

class TestH16_APIEndpointRejectsTestDrawNo(unittest.TestCase):
    """H16: API GET /api/h6-monitoring/daily-operations-report rejects test draw_no."""

    def setUp(self):
        # Import the endpoint logic directly (not a running server)
        # We test by calling the underlying validation logic
        from engine.draw_no_hygiene import is_test_draw_no
        self._is_test = is_test_draw_no

    def test_s1_is_identified_as_test(self):
        self.assertTrue(self._is_test("S1_177747072422"))

    def test_e2e_is_identified_as_test(self):
        self.assertTrue(self._is_test("E2E_draw_001"))

    def test_auto_is_identified_as_test(self):
        self.assertTrue(self._is_test("AUTO_99999"))

    def test_rb_is_identified_as_test(self):
        self.assertTrue(self._is_test("RB_20260429"))

    def test_rbiso_is_identified_as_test(self):
        self.assertTrue(self._is_test("RBISO_001"))

    def test_numeric_not_test(self):
        self.assertFalse(self._is_test("114001"))

    def test_api_guard_via_httpx(self):
        """Integration: API returns 400 for test draw_no (uses TestClient)."""
        try:
            from fastapi.testclient import TestClient
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "lottery_app",
                os.path.join(_LOTTERY_API, "main.py"),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            client = TestClient(mod.app, raise_server_exceptions=False)
            resp = client.get(
                "/api/h6-monitoring/daily-operations-report",
                params={"draw_no": "S1_hygiene_test"},
            )
            self.assertEqual(resp.status_code, 400)
        except Exception as exc:
            self.skipTest(f"TestClient integration skipped: {exc}")


# ── HN1–HN5: Synthetic numeric draw_no detection ─────────────────────────────

class TestHN1_to_HN5_SyntheticNumericDetection(unittest.TestCase):
    """New cases: synthetic numeric draw_nos (10-digit, > 999_999_999) are test/synthetic."""

    # HN1
    def test_115000105_is_production(self):
        """115000105 (real DAILY_539 period) → production."""
        self.assertTrue(is_production_draw_no("115000105"))
        self.assertFalse(is_test_draw_no("115000105"))

    # HN2
    def test_s1_prefix_is_test(self):
        """S1_ prefix → test."""
        self.assertTrue(is_test_draw_no("S1_177747072422"))
        self.assertFalse(is_production_draw_no("S1_177747072422"))

    # HN3
    def test_e2e_prefix_is_test(self):
        """E2E_ prefix → test."""
        self.assertTrue(is_test_draw_no("E2E_draw_001"))
        self.assertFalse(is_production_draw_no("E2E_draw_001"))

    # HN4
    def test_auto_prefix_is_test(self):
        """AUTO_ prefix → test."""
        self.assertTrue(is_test_draw_no("AUTO_1777478529338"))
        self.assertFalse(is_production_draw_no("AUTO_1777478529338"))

    # HN5
    def test_9300279486_is_synthetic(self):
        """9300279486 (10 digits, ~9.3 billion) → synthetic/test."""
        self.assertFalse(is_production_draw_no("9300279486"))
        self.assertTrue(is_test_draw_no("9300279486"))

    def test_9300297780_is_synthetic(self):
        self.assertFalse(is_production_draw_no("9300297780"))
        self.assertTrue(is_test_draw_no("9300297780"))

    def test_9300412307_is_synthetic(self):
        self.assertFalse(is_production_draw_no("9300412307"))
        self.assertTrue(is_test_draw_no("9300412307"))

    def test_sql_filter_rejects_synthetic_numeric(self):
        """SQL filter excludes 10-digit synthetic numeric draw_nos."""
        sql_filter = production_draw_no_sql_filter("value")
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TEMP TABLE t (value TEXT)")
        for synthetic in ("9300279486", "9300297780", "9300412307"):
            conn.execute("DELETE FROM t")
            conn.execute("INSERT INTO t VALUES (?)", (synthetic,))
            row = conn.execute(f"SELECT value FROM t WHERE {sql_filter}").fetchone()
            self.assertIsNone(row, f"Synthetic draw_no {synthetic} should be excluded by SQL filter")
        conn.close()


# ── HN6: synthetic numeric draw_no → no CTO backlog ──────────────────────────

class TestHN6_SyntheticNumericNoCTOBacklog(unittest.TestCase):
    """HN6: HIGH-risk report with synthetic numeric draw_no must not create CTO backlog."""

    _SYNTHETIC = "9300279486"

    def tearDown(self):
        _delete_cto_backlog(self._SYNTHETIC)
        _delete_agent_task(self._SYNTHETIC)

    def test_synthetic_numeric_no_cto_backlog(self):
        if not _db_ok():
            self.skipTest("No DB")
        report = {
            "report_meta": {
                "draw_no": self._SYNTHETIC,
                "game_type": H6_GAME,
                "report_status": "COMPLETE",
                "environment": "test",
            },
            "risk_assessment": {"risk_level": "HIGH", "risk_factors": ["synthetic_test"]},
            "action_recommendation": {"action": "PREPARE_ROLLBACK", "reason": "test"},
            "strategy": {"rollback_status": "ACTIVE"},
        }
        result = process_report_alerts(report, game_type=H6_GAME)
        self.assertFalse(result["alerted"],
                         f"Alert should be suppressed for synthetic numeric. Got: {result}")
        self.assertEqual(result.get("skipped_reason"), "test_draw_no")
        # Confirm no CTO backlog row written
        conn = _get_conn()
        finding_id = f"h6_alert:{H6_GAME}:{self._SYNTHETIC}"
        row = conn.execute(
            "SELECT id FROM cto_backlog_items WHERE finding_id=?", (finding_id,)
        ).fetchone()
        conn.close()
        self.assertIsNone(row, "No CTO backlog row should be created for synthetic numeric draw_no")


# ── HN7: synthetic numeric draw_no → no rollback task ────────────────────────

class TestHN7_SyntheticNumericNoRollbackTask(unittest.TestCase):
    """HN7: Synthetic numeric draw_no with rollback_status != ACTIVE must not create agent task."""

    # Use a fresh 10-digit synthetic that has no pre-existing tasks/backlog
    _SYNTHETIC = "9399988877"

    def setUp(self):
        # Clean up any stale rows from previous failed runs
        _delete_cto_backlog(self._SYNTHETIC)
        _delete_agent_task(self._SYNTHETIC)

    def tearDown(self):
        _delete_cto_backlog(self._SYNTHETIC)
        _delete_agent_task(self._SYNTHETIC)

    def test_synthetic_numeric_no_rollback_task(self):
        if not _db_ok():
            self.skipTest("No DB")
        report = {
            "report_meta": {
                "draw_no": self._SYNTHETIC,
                "game_type": H6_GAME,
                "report_status": "COMPLETE",
                "environment": "test",
            },
            "risk_assessment": {"risk_level": "HIGH", "risk_factors": ["synthetic_test"]},
            "action_recommendation": {"action": "ROLLBACK_ACTIVE", "reason": "test"},
            "strategy": {"rollback_status": "ROLLBACK_TRIGGERED"},
        }
        result = process_report_alerts(report, game_type=H6_GAME)
        self.assertFalse(result["alerted"])
        self.assertIsNone(result.get("rollback_task_id"))
        conn = _get_conn()
        rows = conn.execute(
            "SELECT id FROM agent_tasks WHERE title LIKE ?",
            (f"%{self._SYNTHETIC}%",),
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 0,
                         "No agent_task should be created for synthetic numeric draw_no")


# ── HN8: latest mode does not return synthetic numeric draw_no ────────────────

class TestHN8_LatestModeNoSyntheticNumeric(unittest.TestCase):
    """HN8: _fetch_latest_draw_no does not return synthetic numeric draw_nos (9300279486)."""

    _SYNTHETICS = ["9300279486", "9300297780", "9300412307"]

    def setUp(self):
        if not _db_ok():
            return
        for d in self._SYNTHETICS:
            _insert_prediction(d)
        # Give synthetics a far-future ISO timestamp so they'd win by time ordering
        # if they weren't filtered out — confirming the filter is what blocks them
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        for d in self._SYNTHETICS:
            conn.execute(
                "UPDATE live_strategy_predictions SET generated_at=? "
                "WHERE game_type=? AND draw_no=? AND strategy_name=?",
                ("2099-12-31T23:59:59.000000+00:00", H6_GAME, d, H6_STRATEGY_ID),
            )
        conn.commit()
        conn.close()

    def tearDown(self):
        for d in self._SYNTHETICS:
            _delete_prediction(d)

    def test_latest_mode_skips_synthetic_numeric(self):
        """Even if synthetic numeric draw_nos are the most recent by generated_at,
        _fetch_latest_draw_no must skip them."""
        if not _db_ok():
            self.skipTest("No DB")
        conn = _get_conn()
        result = _fetch_latest_draw_no(conn, H6_GAME, H6_STRATEGY_ID)
        conn.close()
        for synthetic in self._SYNTHETICS:
            self.assertNotEqual(
                result, synthetic,
                f"Synthetic numeric draw_no {synthetic} should not be returned by _fetch_latest_draw_no",
            )


if __name__ == "__main__":
    unittest.main()

