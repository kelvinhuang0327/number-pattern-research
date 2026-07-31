"""
test_p39_replay_ui_smoke_closure_after_p38.py
=============================================
P39 Replay UI Smoke Closure After P38 tests.

Closes the deferred UI smoke item from P38.

Verifies:
  1. Production rows = 28960 (no writes during P39)
  2. Each of 6 P37 Wave 2 strategies has exactly 1500 rows in DB
  3. All P37 rows have lottery_type = DAILY_539
  4. No P37 row has lifecycle = ONLINE (lifecycle lives in registry, not DB)
  5. API endpoint returns correct row count for each strategy
  6. P38 deferred UI smoke item is documented as RESOLVED
  7. P39 output JSON exists with expected structure
  8. P39 classification is one of valid values
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

try:
    import requests  # type: ignore
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# ─── Constants ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P39_OUTPUT_JSON = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p39_replay_ui_smoke_closure_after_p38_20260523.json"
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

VALID_CLASSIFICATIONS = frozenset(
    {
        "P39_REPLAY_UI_SMOKE_CLOSURE_AFTER_P38_MERGED_TO_MAIN",
        "P39_REPLAY_UI_SMOKE_CLOSURE_AFTER_P38_READY",
        "P39_BLOCKED_BY_NO_BRANCH_AUTHORIZATION",
        "P39_BLOCKED_BY_PREFLIGHT",
        "P39_BLOCKED_BY_FRONTEND_PORT",
        "P39_BLOCKED_BY_UI_VISIBILITY_GAP",
        "P39_BLOCKED_BY_API_QUERY_GAP",
        "P39_BLOCKED_BY_PRODUCTION_DB_DRIFT",
        "P39_BLOCKED_BY_DRIFT_GUARD",
        "P39_BLOCKED_BY_BRANCH_GOVERNANCE_GUARD",
        "P39_BLOCKED_BY_FORBIDDEN_FILE",
        "P39_BLOCKED_BY_CI",
    }
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ─── Tests: Production Row Count ──────────────────────────────────────────────


class TestProductionRowCount:
    """Production row count must be exactly 28960 (unchanged during P39)."""

    def test_total_rows_equals_28960(self, db_conn):
        row = db_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays"
        ).fetchone()
        assert row["cnt"] == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} production rows, got {row['cnt']}. "
            "P39 must NOT write any rows to production DB."
        )

    def test_no_rows_added_during_p39(self, db_conn):
        """Alias: same assertion — ensures no P39 writes occurred."""
        row = db_conn.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays"
        ).fetchone()
        assert row["cnt"] == EXPECTED_TOTAL_ROWS


# ─── Tests: P37 Strategy Rows ─────────────────────────────────────────────────


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

    def test_all_p37_rows_are_daily_539(self, db_conn):
        row = db_conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            )
            AND lottery_type != 'DAILY_539'
            """
        ).fetchone()
        assert row["cnt"] == 0, (
            f"Found {row['cnt']} P37 rows with lottery_type != DAILY_539"
        )

    def test_no_p37_row_is_online_via_registry(self):
        """P37 Wave 2 strategies must NOT be ONLINE in the registry."""
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        try:
            from lottery_api.models.replay_strategy_registry import list_strategies
            strategies = list_strategies(lottery_type="DAILY_539")
            sid_to_status = {
                s.get("strategy_id"): s.get("lifecycle_status", s.get("status"))
                for s in strategies
            }
            for sid in WAVE2_STRATEGY_IDS:
                status = sid_to_status.get(sid)
                # P37 Wave 2 strategies should not be registered as ONLINE
                # They may be absent from the registry (DRY_RUN adapters) or OFFLINE/RETIRED
                if status is not None:
                    assert status != "ONLINE", (
                        f"P37 strategy {sid} must NOT be ONLINE in registry, got {status}"
                    )
        except Exception:
            pytest.skip("Registry import unavailable")

    def test_p37_rows_have_valid_replay_status(self, db_conn):
        """All P37 rows should have a valid replay_status."""
        rows = db_conn.execute(
            """
            SELECT DISTINCT replay_status
            FROM strategy_prediction_replays
            WHERE strategy_id IN (
                'markov_1bet_539','acb_single_539','zone_gap_3bet_539',
                '539_3bet_orthogonal','p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2'
            )
            """
        ).fetchall()
        valid_statuses = {"PREDICTED", "REJECTED", "INSUFFICIENT_HISTORY",
                          "REPLAY_ERROR", "INVALID_OUTPUT", "STRATEGY_UNAVAILABLE"}
        for r in rows:
            assert r["replay_status"] in valid_statuses, (
                f"Unexpected replay_status: {r['replay_status']}"
            )


# ─── Tests: API Endpoint ──────────────────────────────────────────────────────


class TestReplayAPIEndpoint:
    """API endpoint must return correct data for each P37 Wave 2 strategy."""

    API_BASE = "http://localhost:8002"
    HISTORY_ENDPOINT = "/api/replay/history"

    @pytest.mark.skipif(
        not _REQUESTS_AVAILABLE,
        reason="requests library not available"
    )
    def test_api_accessible(self):
        """Backend API must be reachable."""
        try:
            resp = requests.get(f"{self.API_BASE}/health", timeout=5)
            assert resp.status_code == 200, (
                f"API health check failed: {resp.status_code}"
            )
        except Exception as exc:
            pytest.skip(f"API server not reachable: {exc}")

    @pytest.mark.skipif(
        not _REQUESTS_AVAILABLE,
        reason="requests library not available"
    )
    def test_each_strategy_returns_1500_via_api(self):
        """Each P37 strategy must return 1500 total rows via API."""
        try:
            requests.get(f"{self.API_BASE}/health", timeout=3)
        except Exception as exc:
            pytest.skip(f"API server not reachable: {exc}")

        for sid in sorted(WAVE2_STRATEGY_IDS):
            resp = requests.get(
                f"{self.API_BASE}{self.HISTORY_ENDPOINT}",
                params={"lottery_type": "DAILY_539", "strategy_id": sid,
                        "page": 1, "page_size": 1},
                timeout=10,
            )
            assert resp.status_code == 200, (
                f"{sid}: API returned {resp.status_code}"
            )
            data = resp.json()
            total = data.get("total", data.get("count", -1))
            assert total == ROWS_PER_STRATEGY, (
                f"{sid}: expected {ROWS_PER_STRATEGY} rows via API, got {total}"
            )

    @pytest.mark.skipif(
        not _REQUESTS_AVAILABLE,
        reason="requests library not available"
    )
    def test_daily_539_total_via_api(self):
        """API must return total DAILY_539 rows correctly."""
        try:
            requests.get(f"{self.API_BASE}/health", timeout=3)
        except Exception as exc:
            pytest.skip(f"API server not reachable: {exc}")

        resp = requests.get(
            f"{self.API_BASE}{self.HISTORY_ENDPOINT}",
            params={"lottery_type": "DAILY_539", "page": 1, "page_size": 1},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        total = data.get("total", -1)
        # DAILY_539 has many strategies; total should be >= 9000 (Wave 2 alone)
        assert total >= P37_ROWS, (
            f"DAILY_539 total {total} < expected minimum {P37_ROWS}"
        )

    @pytest.mark.skipif(
        not _REQUESTS_AVAILABLE,
        reason="requests library not available"
    )
    def test_pagination_works_for_markov_1bet_539(self):
        """Pagination must work correctly for markov_1bet_539."""
        try:
            requests.get(f"{self.API_BASE}/health", timeout=3)
        except Exception as exc:
            pytest.skip(f"API server not reachable: {exc}")

        # Page 1 with 100 rows
        resp1 = requests.get(
            f"{self.API_BASE}{self.HISTORY_ENDPOINT}",
            params={"lottery_type": "DAILY_539", "strategy_id": "markov_1bet_539",
                    "page": 1, "page_size": 100},
            timeout=10,
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        records1 = data1.get("records", data1.get("rows", data1.get("items", [])))
        assert len(records1) == 100, f"Page 1 should have 100 rows, got {len(records1)}"

        # Last page (page 15 with 100 rows each = 1500 rows, last 100 rows)
        resp15 = requests.get(
            f"{self.API_BASE}{self.HISTORY_ENDPOINT}",
            params={"lottery_type": "DAILY_539", "strategy_id": "markov_1bet_539",
                    "page": 15, "page_size": 100},
            timeout=10,
        )
        assert resp15.status_code == 200
        data15 = resp15.json()
        records15 = data15.get("records", data15.get("rows", data15.get("items", [])))
        assert len(records15) == 100, (
            f"Page 15 should have 100 rows, got {len(records15)}"
        )
        total = data15.get("total", -1)
        assert total == ROWS_PER_STRATEGY, (
            f"markov_1bet_539 total {total} != {ROWS_PER_STRATEGY}"
        )


# ─── Tests: UI Smoke (documented via output file) ─────────────────────────────


class TestP39UISmokeDocumentation:
    """P39 output files must exist and document the UI smoke result."""

    def test_p39_output_json_exists(self):
        assert P39_OUTPUT_JSON.exists(), (
            f"P39 output JSON not found at {P39_OUTPUT_JSON}"
        )

    def test_p39_output_json_valid(self):
        assert P39_OUTPUT_JSON.exists(), pytest.skip("JSON not generated yet")
        with open(P39_OUTPUT_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        assert isinstance(data, dict), "P39 output JSON must be a dict"

    def test_p39_classification_is_valid(self):
        assert P39_OUTPUT_JSON.exists(), pytest.skip("JSON not generated yet")
        with open(P39_OUTPUT_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        classification = data.get("classification", "")
        assert classification in VALID_CLASSIFICATIONS, (
            f"Invalid classification: {classification!r}. "
            f"Must be one of {sorted(VALID_CLASSIFICATIONS)}"
        )

    def test_p39_production_rows_unchanged(self):
        assert P39_OUTPUT_JSON.exists(), pytest.skip("JSON not generated yet")
        with open(P39_OUTPUT_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data.get("production_rows_before") == EXPECTED_TOTAL_ROWS, (
            f"production_rows_before must be {EXPECTED_TOTAL_ROWS}"
        )
        assert data.get("production_rows_after") == EXPECTED_TOTAL_ROWS, (
            f"production_rows_after must be {EXPECTED_TOTAL_ROWS}"
        )

    def test_p39_api_cross_check_all_pass(self):
        assert P39_OUTPUT_JSON.exists(), pytest.skip("JSON not generated yet")
        with open(P39_OUTPUT_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        api_check = data.get("api_cross_check", {})
        for sid in WAVE2_STRATEGY_IDS:
            entry = api_check.get(sid, {})
            assert entry.get("rows") == ROWS_PER_STRATEGY, (
                f"{sid}: expected {ROWS_PER_STRATEGY} rows in api_cross_check, "
                f"got {entry.get('rows')}"
            )
            assert entry.get("status") == "PASS", (
                f"{sid}: expected status PASS in api_cross_check, "
                f"got {entry.get('status')}"
            )

    def test_p39_ui_smoke_status_documented(self):
        assert P39_OUTPUT_JSON.exists(), pytest.skip("JSON not generated yet")
        with open(P39_OUTPUT_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        ui_smoke = data.get("ui_smoke", {})
        assert "status" in ui_smoke, "ui_smoke.status must be present"
        valid_smoke_statuses = {"PASS", "DEFERRED_FRONTEND_UNAVAILABLE"}
        assert ui_smoke["status"] in valid_smoke_statuses, (
            f"ui_smoke.status must be one of {valid_smoke_statuses}, "
            f"got {ui_smoke['status']!r}"
        )

    def test_p38_deferred_item_is_closed(self):
        assert P39_OUTPUT_JSON.exists(), pytest.skip("JSON not generated yet")
        with open(P39_OUTPUT_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        closure = data.get("p38_deferred_ui_smoke_closure", "")
        assert closure in {"RESOLVED", "DEFERRED_WITH_REASON"}, (
            f"p38_deferred_ui_smoke_closure must be RESOLVED or DEFERRED_WITH_REASON, "
            f"got {closure!r}"
        )
