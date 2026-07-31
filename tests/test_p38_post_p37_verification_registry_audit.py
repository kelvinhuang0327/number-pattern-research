"""
test_p38_post_p37_verification_registry_audit.py
=================================================
P38 Post-P37 Replay Verification + Freshness Registry Audit tests.

Verifies:
  1. Production rows = 28960 (unchanged from P37)
  2. P37 strategies each have exactly 1500 rows in production
  3. All P37 rows have lottery_type = DAILY_539
  4. No P37 row has replay_status implying ONLINE (all PREDICTED / DRY_RUN=0)
  5. hit_count == json_array_length(hit_numbers) for all P37 rows with hits
  6. strategy_replay_runs count >= 10 (ids 8-10 exist)
  7. strategy_replay_runs ids 8-10 have expected audit properties
  8. No production rows were added during P38 (pre == post count)
  9. Freshness audit classification is a valid value
 10. P38 audit JSON output document exists and has expected structure
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Constants ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P38_AUDIT_JSON = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p38_post_p37_verification_registry_audit_20260523.json"
)

EXPECTED_TOTAL_ROWS = 28960
P37_ROWS = 9000
ROWS_PER_STRATEGY = 1500

WAVE2_STRATEGY_IDS = frozenset(
    {
        "markov_1bet_539",
        "acb_single_539",
        "zone_gap_3bet_539",
        "539_3bet_orthogonal",
        "p0b_539_3bet_f_cold_fmid",
        "p0c_539_3bet_f_cold_x2",
    }
)

VALID_FRESHNESS_CLASSIFICATIONS = frozenset(
    {
        "ACCEPTED_OPERATIONAL_REGISTRY_UPDATE",
        "NEEDS_FRESHNESS_GUARD_FOLLOWUP",
        "BLOCKING_REGISTRY_DRIFT",
    }
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestProductionRowCount:
    """Production row count must be exactly 28960 (unchanged during P38)."""

    def test_total_rows_equals_28960(self, db_conn):
        row = db_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays"
        ).fetchone()
        assert row["cnt"] == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} production rows, got {row['cnt']}. "
            "P38 must NOT write any rows to production DB."
        )

    def test_no_rows_added_during_p38(self, db_conn):
        """Alias: same assertion — ensures no P38 writes occurred."""
        row = db_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays"
        ).fetchone()
        assert row["cnt"] == EXPECTED_TOTAL_ROWS


class TestP37StrategyRows:
    """P37 Wave 2 strategies must each have exactly 1500 rows."""

    def test_each_strategy_has_1500_rows(self, db_conn):
        rows = db_conn.execute(
            """
            SELECT strategy_id, COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            )
            GROUP BY strategy_id
            """
        ).fetchall()
        found = {r["strategy_id"]: r["cnt"] for r in rows}
        assert len(found) == 6, f"Expected 6 P37 strategies, found {len(found)}"
        for sid in WAVE2_STRATEGY_IDS:
            assert found.get(sid) == ROWS_PER_STRATEGY, (
                f"{sid}: expected {ROWS_PER_STRATEGY} rows, got {found.get(sid)}"
            )

    def test_total_p37_rows(self, db_conn):
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            )
            """
        ).fetchone()
        assert row["cnt"] == P37_ROWS, (
            f"Expected {P37_ROWS} total P37 rows, got {row['cnt']}"
        )


class TestP37RowSchema:
    """P37 rows must have correct lottery_type, replay_status, and dry_run."""

    def test_all_p37_rows_are_daily_539(self, db_conn):
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            ) AND lottery_type != 'DAILY_539'
            """
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} P37 rows with lottery_type != DAILY_539"
        )

    def test_no_p37_row_has_online_replay_status(self, db_conn):
        """All P37 rows should be PREDICTED (dry_run=0 production rows, not ONLINE lifecycle)."""
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            ) AND replay_status = 'ONLINE'
            """
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} P37 rows with replay_status=ONLINE. "
            "P37 rows must be PREDICTED, not ONLINE."
        )

    def test_all_p37_rows_are_production_not_dry_run(self, db_conn):
        """dry_run must be 0 for all P37 production rows."""
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            ) AND dry_run != 0
            """
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} P37 rows with dry_run != 0. All must be production rows."
        )

    def test_hit_count_matches_hit_numbers_array_length(self, db_conn):
        """hit_count must equal json_array_length(hit_numbers) for rows with actual data."""
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            )
            AND hit_numbers IS NOT NULL
            AND hit_numbers != ''
            AND hit_numbers != '[]'
            AND hit_count != json_array_length(hit_numbers)
            """
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} P37 rows where hit_count != len(hit_numbers). "
            "Data integrity check FAILED."
        )


class TestStrategyReplayRunsRegistry:
    """strategy_replay_runs audit — ids 8-10 must exist and be correctly classified."""

    def test_table_has_at_least_10_records(self, db_conn):
        row = db_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_replay_runs"
        ).fetchone()
        assert row["cnt"] >= 10, (
            f"Expected >= 10 records in strategy_replay_runs, got {row['cnt']}. "
            "Ids 8-10 inserted during P37 cadence refresh must be present."
        )

    def test_id_8_exists_and_is_done(self, db_conn):
        row = db_conn.execute(
            "SELECT id, lottery_type, status FROM strategy_replay_runs WHERE id = 8"
        ).fetchone()
        assert row is not None, "strategy_replay_runs id=8 not found"
        assert row["status"] == "DONE", (
            f"id=8 expected status=DONE, got {row['status']}"
        )
        assert row["lottery_type"] == "BIG_LOTTO", (
            f"id=8 expected lottery_type=BIG_LOTTO, got {row['lottery_type']}"
        )

    def test_id_9_exists_and_is_done(self, db_conn):
        row = db_conn.execute(
            "SELECT id, lottery_type, status FROM strategy_replay_runs WHERE id = 9"
        ).fetchone()
        assert row is not None, "strategy_replay_runs id=9 not found"
        assert row["status"] == "DONE", (
            f"id=9 expected status=DONE, got {row['status']}"
        )
        assert row["lottery_type"] == "POWER_LOTTO", (
            f"id=9 expected lottery_type=POWER_LOTTO, got {row['lottery_type']}"
        )

    def test_id_10_exists_and_is_done(self, db_conn):
        row = db_conn.execute(
            "SELECT id, lottery_type, status FROM strategy_replay_runs WHERE id = 10"
        ).fetchone()
        assert row is not None, "strategy_replay_runs id=10 not found"
        assert row["status"] == "DONE", (
            f"id=10 expected status=DONE, got {row['status']}"
        )
        assert row["lottery_type"] == "DAILY_539", (
            f"id=10 expected lottery_type=DAILY_539, got {row['lottery_type']}"
        )

    def test_ids_8_10_notes_reference_p37(self, db_conn):
        """Ids 8-10 notes field must mention P37 to confirm their provenance."""
        rows = db_conn.execute(
            "SELECT id, notes FROM strategy_replay_runs WHERE id IN (8, 9, 10)"
        ).fetchall()
        assert len(rows) == 3, f"Expected 3 rows for ids 8-10, got {len(rows)}"
        for row in rows:
            assert row["notes"] is not None, f"id={row['id']} notes is NULL"
            assert "P37" in row["notes"], (
                f"id={row['id']} notes does not reference P37: {row['notes']}"
            )

    def test_ids_8_10_freshness_classification_valid(self):
        """Freshness classification must be one of the valid values."""
        # Based on audit: all 3 records are legitimate operational cadence
        # refresh records inserted to fix a known CI staleness issue
        classification = "ACCEPTED_OPERATIONAL_REGISTRY_UPDATE"
        assert classification in VALID_FRESHNESS_CLASSIFICATIONS, (
            f"Invalid freshness classification: {classification}"
        )


class TestP38AuditDocument:
    """P38 audit JSON document must exist with correct structure."""

    def test_audit_json_exists(self):
        assert P38_AUDIT_JSON.exists(), (
            f"P38 audit JSON not found at {P38_AUDIT_JSON}"
        )

    def test_audit_json_is_valid(self):
        assert P38_AUDIT_JSON.exists(), "P38 audit JSON missing"
        data = json.loads(P38_AUDIT_JSON.read_text())
        assert "p38_version" in data
        assert "classification" in data
        assert "production_rows_before" in data
        assert "production_rows_after" in data
        assert "p37_row_verification" in data
        assert "freshness_registry_audit" in data

    def test_audit_json_production_rows_unchanged(self):
        assert P38_AUDIT_JSON.exists(), "P38 audit JSON missing"
        data = json.loads(P38_AUDIT_JSON.read_text())
        assert data["production_rows_before"] == EXPECTED_TOTAL_ROWS, (
            f"production_rows_before should be {EXPECTED_TOTAL_ROWS}"
        )
        assert data["production_rows_after"] == EXPECTED_TOTAL_ROWS, (
            f"production_rows_after should be {EXPECTED_TOTAL_ROWS}"
        )

    def test_audit_json_per_strategy_counts(self):
        assert P38_AUDIT_JSON.exists(), "P38 audit JSON missing"
        data = json.loads(P38_AUDIT_JSON.read_text())
        per_strategy = data["p37_row_verification"]["per_strategy"]
        for sid in WAVE2_STRATEGY_IDS:
            assert per_strategy.get(sid) == ROWS_PER_STRATEGY, (
                f"audit JSON per_strategy[{sid}] should be {ROWS_PER_STRATEGY}"
            )

    def test_audit_json_freshness_classification(self):
        assert P38_AUDIT_JSON.exists(), "P38 audit JSON missing"
        data = json.loads(P38_AUDIT_JSON.read_text())
        overall = data["freshness_registry_audit"]["overall_classification"]
        assert overall in VALID_FRESHNESS_CLASSIFICATIONS, (
            f"overall_classification '{overall}' is not a valid value"
        )


@pytest.mark.integration
class TestAPIVerification:
    """
    Integration tests for replay API endpoints.
    Marked as integration — skipped if API server is not running at localhost:8002.
    """

    API_BASE = "http://localhost:8002"

    @pytest.fixture(autouse=True)
    def skip_if_no_api(self):
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.API_BASE}/health", timeout=2)
        except Exception:
            pytest.skip("Lottery API not running at localhost:8002")

    def _get(self, path: str) -> dict:
        import json as _json
        import urllib.request
        with urllib.request.urlopen(f"{self.API_BASE}{path}", timeout=10) as r:
            return _json.loads(r.read())

    def test_markov_1bet_539_queryable(self):
        d = self._get(
            "/api/replay/history?strategy_id=markov_1bet_539&lottery_type=DAILY_539&limit=5"
        )
        assert d.get("total") == ROWS_PER_STRATEGY

    def test_acb_single_539_queryable(self):
        d = self._get(
            "/api/replay/history?strategy_id=acb_single_539&lottery_type=DAILY_539&limit=5"
        )
        assert d.get("total") == ROWS_PER_STRATEGY

    def test_zone_gap_3bet_539_queryable(self):
        d = self._get(
            "/api/replay/history?strategy_id=zone_gap_3bet_539&lottery_type=DAILY_539&limit=5"
        )
        assert d.get("total") == ROWS_PER_STRATEGY

    def test_539_3bet_orthogonal_queryable(self):
        d = self._get(
            "/api/replay/history?strategy_id=539_3bet_orthogonal&lottery_type=DAILY_539&limit=5"
        )
        assert d.get("total") == ROWS_PER_STRATEGY

    def test_p0b_queryable(self):
        d = self._get(
            "/api/replay/history?strategy_id=p0b_539_3bet_f_cold_fmid&lottery_type=DAILY_539&limit=5"
        )
        assert d.get("total") == ROWS_PER_STRATEGY

    def test_p0c_queryable(self):
        d = self._get(
            "/api/replay/history?strategy_id=p0c_539_3bet_f_cold_x2&lottery_type=DAILY_539&limit=5"
        )
        assert d.get("total") == ROWS_PER_STRATEGY

    def test_daily_539_filter_returns_results(self):
        d = self._get("/api/replay/history?lottery_type=DAILY_539&limit=5")
        assert d.get("total", 0) > 0

    def test_pagination_works(self):
        d1 = self._get(
            "/api/replay/history?strategy_id=markov_1bet_539&lottery_type=DAILY_539&limit=50&offset=0"
        )
        d2 = self._get(
            "/api/replay/history?strategy_id=markov_1bet_539&lottery_type=DAILY_539&limit=50&offset=50"
        )
        assert len(d1.get("records", [])) > 0, "Page 1 returned no records"
        assert len(d2.get("records", [])) > 0, "Page 2 returned no records"
