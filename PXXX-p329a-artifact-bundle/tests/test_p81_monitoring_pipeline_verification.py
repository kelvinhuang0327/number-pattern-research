"""
P81: Monitoring / Scoring Pipeline Verification — POWER_LOTTO draw 115000041.

Read-only verification that P79 draw-ext rows are reflected in the monitoring
pipeline. No DB writes. Backend must be running on port 8002.
"""
import json
import sqlite3
import urllib.request
from pathlib import Path

import pytest

DB_PATH = "lottery_api/data/lottery_v2.db"
ARTIFACT_PATH = "outputs/replay/p81_monitoring_pipeline_verification_20260526.json"
API_BASE = "http://localhost:8002"
TARGET_DRAW = "115000041"
TARGET_LOTTERY = "POWER_LOTTO"
TARGET_DATE_SLASH = "2026/05/21"
EXPECTED_TOTAL_REPLAY_ROWS = 46962
EXPECTED_STRATEGY_ROWS = 1501  # 1500 historical + 1 P79 draw-ext


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# ── Artifact ──────────────────────────────────────────────────────────────────

class TestP81Artifact:
    def test_artifact_exists(self, artifact):
        assert artifact is not None

    def test_final_classification(self, artifact):
        assert artifact["final_classification"] == "P81_MONITORING_PIPELINE_VERIFICATION_PASS"

    def test_all_checks_passed(self, artifact):
        assert artifact["all_checks_passed"] is True

    def test_no_db_writes(self, artifact):
        assert artifact["db_state"]["no_writes_performed"] is True

    def test_replay_rows_unchanged(self, artifact):
        assert artifact["db_state"]["replay_rows_before"] == EXPECTED_TOTAL_REPLAY_ROWS
        assert artifact["db_state"]["replay_rows_after"] == EXPECTED_TOTAL_REPLAY_ROWS


# ── DB state ─────────────────────────────────────────────────────────────────

class TestP81DBState:
    def test_replay_rows_unchanged(self, db):
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert c.fetchone()[0] == EXPECTED_TOTAL_REPLAY_ROWS

    def test_draw_115000041_in_draws_table(self, db):
        c = db.cursor()
        c.execute(
            "SELECT date, numbers, special FROM draws WHERE lottery_type=? AND draw=?",
            (TARGET_LOTTERY, TARGET_DRAW),
        )
        row = c.fetchone()
        assert row is not None, "draw 115000041 not found in draws table"
        assert row[0] == TARGET_DATE_SLASH
        assert "[6, 14, 22, 28, 35, 38]" in row[1]
        assert row[2] == 1

    def test_draw_115000041_is_max_power_lotto(self, db):
        c = db.cursor()
        c.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type=?",
            (TARGET_LOTTERY,),
        )
        assert c.fetchone()[0] == 115000041

    def test_p79_rows_still_present(self, db):
        c = db.cursor()
        c.execute(
            """SELECT id, strategy_id, hit_count, dry_run FROM strategy_prediction_replays
               WHERE id IN (46961, 46962) ORDER BY id""",
        )
        rows = c.fetchall()
        assert len(rows) == 2
        assert rows[0] == (46961, "fourier_rhythm_3bet", 1, 0)
        assert rows[1] == (46962, "fourier30_markov30_2bet", 2, 0)

    def test_no_pending_prediction_items(self, db):
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM prediction_items WHERE status='PENDING'")
        assert c.fetchone()[0] == 0, "Unexpected PENDING prediction_items"


# ── RSM data feed ─────────────────────────────────────────────────────────────

class TestP81RSMFeed:
    def test_artifact_rsm_draw_in_feed(self, artifact):
        assert artifact["phase1_rsm"]["draw_115000041_in_feed"] is True

    def test_artifact_rsm_pass(self, artifact):
        assert "PASS" in artifact["phase1_rsm"]["result"]

    def test_artifact_rsm_data_path_is_draws_table(self, artifact):
        assert "draws table" in artifact["phase1_rsm"]["data_path"]


# ── Replay API ────────────────────────────────────────────────────────────────

class TestP81ReplayAPI:
    def test_api_health(self):
        d = _get(f"{API_BASE}/health")
        assert d.get("status") in ("healthy", "ok")

    def test_fourier_rhythm_total_rows(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&strategy_id=fourier_rhythm_3bet"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        assert d["total"] == 1
        r = d["records"][0]
        assert r["id"] == 46961
        assert r["hit_count"] == 1

    def test_fourier30_markov30_total_rows(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&strategy_id=fourier30_markov30_2bet"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        assert d["total"] == 1
        r = d["records"][0]
        assert r["id"] == 46962
        assert r["hit_count"] == 2

    def test_summary_fourier_rhythm_total_rows(self):
        d = _get(f"{API_BASE}/api/replay/summary?lottery_type={TARGET_LOTTERY}")
        s = next((x for x in d["summaries"] if x["strategy_id"] == "fourier_rhythm_3bet"), None)
        assert s is not None
        assert s["total_rows"] == EXPECTED_STRATEGY_ROWS

    def test_summary_fourier30_markov30_total_rows(self):
        d = _get(f"{API_BASE}/api/replay/summary?lottery_type={TARGET_LOTTERY}")
        s = next((x for x in d["summaries"] if x["strategy_id"] == "fourier30_markov30_2bet"), None)
        assert s is not None
        assert s["total_rows"] == EXPECTED_STRATEGY_ROWS

    def test_summary_no_errors(self):
        d = _get(f"{API_BASE}/api/replay/summary?lottery_type={TARGET_LOTTERY}")
        for s in d["summaries"]:
            if s["strategy_id"] in ("fourier_rhythm_3bet", "fourier30_markov30_2bet"):
                assert s["error_count"] == 0
                assert s["rejected_count"] == 0


# ── MicroFish / prediction_logger ─────────────────────────────────────────────

class TestP81MicroFish:
    def test_artifact_microfish_not_applicable(self, artifact):
        assert "NOT APPLICABLE" in artifact["phase3_microfish_prediction_logger"]["result"]

    def test_no_pending_prediction_items_artifact(self, artifact):
        assert artifact["phase3_microfish_prediction_logger"]["prediction_items_pending_count"] == 0

    def test_stale_pending_not_blocking(self, artifact):
        assert artifact["phase3_microfish_prediction_logger"]["stale_pending_blocking_pipeline"] is False

    def test_prediction_logger_source_absent(self, artifact):
        assert artifact["phase3_microfish_prediction_logger"]["prediction_logger_py_exists"] is False
