"""
P80: Replay UI/API Verification — POWER_LOTTO draw 115000041.

Verifies that the 2 P79 Batch A draw-ext rows are correctly queryable
via the replay history API. Backend must be running on port 8002.
All tests are read-only (no DB writes).
"""
import json
import sqlite3
import urllib.request
import urllib.error

import pytest

DB_PATH = "lottery_api/data/lottery_v2.db"
ARTIFACT_PATH = "outputs/replay/p80_replay_ui_api_verification_20260526.json"
API_BASE = "http://localhost:8002"
TARGET_DRAW = "115000041"
TARGET_LOTTERY = "POWER_LOTTO"
TARGET_DATE_SLASH = "2026/05/21"
EXPECTED_TOTAL_ROWS = 46962
EXPECTED_P79_IDS = {46961, 46962}


def _get(url: str) -> dict:
    """GET url, return parsed JSON or raise."""
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


# ── 1. Artifact ──────────────────────────────────────────────────────────────

class TestP80Artifact:
    def test_artifact_exists(self, artifact):
        assert artifact is not None

    def test_final_classification(self, artifact):
        assert artifact["final_classification"] == "P80_REPLAY_UI_API_VERIFICATION_PASS"

    def test_all_checks_passed(self, artifact):
        assert artifact["all_checks_passed"] is True

    def test_preconditions_met(self, artifact):
        pre = artifact["preconditions"]
        assert pre["pr_203_merged"] is True
        assert pre["pr_204_merged"] is True
        assert pre["replay_rows"] == EXPECTED_TOTAL_ROWS
        assert pre["p79_rows_present"] is True
        assert pre["p79_fourier_rhythm_dry_run"] == 0
        assert pre["p79_fourier30_markov30_dry_run"] == 0


# ── 2. DB state ───────────────────────────────────────────────────────────────

class TestP80DBState:
    def test_total_replay_rows(self, db):
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        assert c.fetchone()[0] == EXPECTED_TOTAL_ROWS

    def test_p79_rows_present(self, db):
        c = db.cursor()
        c.execute(
            """SELECT id FROM strategy_prediction_replays
               WHERE lottery_type=? AND target_draw=?
                 AND strategy_id IN ('fourier_rhythm_3bet','fourier30_markov30_2bet')
               ORDER BY id""",
            (TARGET_LOTTERY, TARGET_DRAW),
        )
        ids = {r[0] for r in c.fetchall()}
        assert ids == EXPECTED_P79_IDS

    def test_p79_rows_not_dry_run(self, db):
        c = db.cursor()
        c.execute(
            """SELECT SUM(dry_run) FROM strategy_prediction_replays
               WHERE id IN (46961, 46962)""",
        )
        assert c.fetchone()[0] == 0


# ── 3. API verification ───────────────────────────────────────────────────────

pytestmark_api = pytest.mark.skipif(
    False, reason="requires backend on port 8002"
)


class TestP80API:
    def test_api_health(self):
        d = _get(f"{API_BASE}/health")
        assert d.get("status") in ("healthy", "ok")

    def test_replay_history_date_filter_returns_two_rows(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        assert d["total"] == 2, f"Expected 2 records, got {d['total']}"

    def test_replay_history_ids_correct(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        ids = {r["id"] for r in d["records"]}
        assert ids == EXPECTED_P79_IDS

    def test_replay_history_truth_levels(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        for r in d["records"]:
            assert r["truth_level"] == "POWERLOTTO_DRAW_EXT_VERIFIED", (
                f"Row {r['id']} has wrong truth_level: {r['truth_level']}"
            )

    def test_replay_history_fourier_rhythm_filter(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&strategy_id=fourier_rhythm_3bet"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        assert d["total"] == 1
        r = d["records"][0]
        assert r["strategy_id"] == "fourier_rhythm_3bet"
        assert r["hit_count"] == 1

    def test_replay_history_fourier30_markov30_filter(self):
        url = (
            f"{API_BASE}/api/replay/history"
            f"?lottery_type={TARGET_LOTTERY}"
            f"&strategy_id=fourier30_markov30_2bet"
            f"&date_from={TARGET_DATE_SLASH}&date_to={TARGET_DATE_SLASH}"
        )
        d = _get(url)
        assert d["total"] == 1
        r = d["records"][0]
        assert r["strategy_id"] == "fourier30_markov30_2bet"
        assert r["hit_count"] == 2

    def test_replay_summary_fourier_rhythm_row_count(self):
        url = f"{API_BASE}/api/replay/summary?lottery_type={TARGET_LOTTERY}"
        d = _get(url)
        strat = next(
            (s for s in d["summaries"] if s["strategy_id"] == "fourier_rhythm_3bet"),
            None,
        )
        assert strat is not None, "fourier_rhythm_3bet not found in summary"
        assert strat["total_rows"] == 1501, (
            f"Expected 1501, got {strat['total_rows']}"
        )

    def test_replay_summary_fourier30_markov30_row_count(self):
        url = f"{API_BASE}/api/replay/summary?lottery_type={TARGET_LOTTERY}"
        d = _get(url)
        strat = next(
            (s for s in d["summaries"] if s["strategy_id"] == "fourier30_markov30_2bet"),
            None,
        )
        assert strat is not None, "fourier30_markov30_2bet not found in summary"
        assert strat["total_rows"] == 1501, (
            f"Expected 1501, got {strat['total_rows']}"
        )
