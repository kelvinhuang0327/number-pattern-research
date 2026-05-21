"""
P17 — Big Lotto Replay Timestamp API Tests.

Verifies that:
- schema has prediction_cutoff_date / prediction_generated_at columns
- P16 rows (3000) have timestamps populated
- P14D rows (1500) have NULL timestamps — documented legacy gap, not fabricated
- All 3 ONLINE BIG_LOTTO strategies are queryable via GET /api/replay/history
- API now returns prediction_cutoff_date and prediction_generated_at (P17 patch)
- hit_count == len(hit_numbers) for all records checked
- pagination works
- no DB writes occur
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT   = Path(__file__).resolve().parents[1]
_LOTTERY_API = _REPO_ROOT / "lottery_api"
_PROD_DB     = _LOTTERY_API / "data" / "lottery_v2.db"
_P17_OUTPUT  = _REPO_ROOT / "outputs" / "replay" / "p17_biglotto_replay_timestamp_api_20260520.json"

sys.path.insert(0, str(_LOTTERY_API))
from routes.replay import get_replay_history  # noqa: E402

PROD_ROWS     = 9460  # updated post-P20 apply
P16_APPLY_ID     = "P16_BIGLOTTO_REMAINING_1500_PROD_20260520"
P14D_APPLY_ID    = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
P16_TIMESTAMP_ROWS  = 3000
P14D_TIMESTAMP_ROWS = 1500  # updated post-P17B: timestamps now backfilled for all P14D rows

STRATEGIES = ["ts3_regime_3bet", "biglotto_triple_strike", "biglotto_deviation_2bet"]
# ts3_regime_3bet has only P14D rows (1500); others have 70 legacy + 1500 P16 = 1570
STRATEGY_MIN_ROWS = {
    "ts3_regime_3bet":     1500,
    "biglotto_triple_strike": 1500,
    "biglotto_deviation_2bet": 1500,
}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _history(strategy_id, page=1, page_size=50):
    return _run(get_replay_history(
        lottery_type="BIG_LOTTO",
        strategy_id=strategy_id,
        replay_status=None, lifecycle_status=None,
        fixture_mode=False, date_from=None, date_to=None,
        page=page, page_size=page_size,
    ))


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def output() -> dict:
    assert _P17_OUTPUT.exists()
    return json.loads(_P17_OUTPUT.read_text())


@pytest.fixture(scope="module")
def ts3_page() -> dict:
    return _history("ts3_regime_3bet", page_size=5)


@pytest.fixture(scope="module")
def triple_page() -> dict:
    return _history("biglotto_triple_strike", page_size=5)


@pytest.fixture(scope="module")
def deviation_page() -> dict:
    return _history("biglotto_deviation_2bet", page_size=5)


# ── output JSON tests ─────────────────────────────────────────────────────────

def test_output_exists():
    assert _P17_OUTPUT.exists()


def test_output_phase(output: dict):
    assert output["phase"] == "P17_BIGLOTTO_REPLAY_TIMESTAMP_API"


def test_output_production_rows(output: dict):
    # P17 output snapshot captured pre-P19B; value may be lower than current live count
    assert output["production_rows"] >= 4960


def test_output_p16_timestamp_rows(output: dict):
    assert output["p16_timestamp_rows"] == P16_TIMESTAMP_ROWS


def test_output_p14d_timestamp_rows(output: dict):
    # P17 output JSON is a frozen snapshot captured before P17B backfill.
    # The snapshot value is 0 (pre-backfill); post-P17B the live count is 1500.
    # Accept either value: snapshot is immutable, live state verified in P17B tests.
    assert output["p14d_timestamp_rows"] in (0, P14D_TIMESTAMP_ROWS)


def test_output_p14d_timestamp_gap_documented(output: dict):
    assert output["p14d_timestamp_gap"] is True


def test_output_api_timestamp_fields_present(output: dict):
    assert output["api_timestamp_fields_present"] is True


def test_output_no_missing_fields(output: dict):
    assert output["missing_fields"] == []


def test_output_no_db_write(output: dict):
    assert output["no_db_write"] is True


def test_output_fake_success_zero(output: dict):
    assert output["fake_success_count"] == 0


def test_output_classification(output: dict):
    assert output["final_classification"] == "P17_BIGLOTTO_REPLAY_TIMESTAMP_API_READY"


# ── DB schema tests ───────────────────────────────────────────────────────────

def test_db_schema_has_prediction_cutoff_date():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        cols = [row[1] for row in conn.execute(
            "PRAGMA table_info(strategy_prediction_replays)"
        ).fetchall()]
    finally:
        conn.close()
    assert "prediction_cutoff_date" in cols


def test_db_schema_has_prediction_generated_at():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        cols = [row[1] for row in conn.execute(
            "PRAGMA table_info(strategy_prediction_replays)"
        ).fetchall()]
    finally:
        conn.close()
    assert "prediction_generated_at" in cols


# ── DB data tests ─────────────────────────────────────────────────────────────

def test_p16_timestamp_rows_in_db():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND prediction_cutoff_date IS NOT NULL
               AND prediction_generated_at IS NOT NULL""",
            (P16_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == P16_TIMESTAMP_ROWS


def test_p14d_timestamp_rows_in_db():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND prediction_cutoff_date IS NOT NULL""",
            (P14D_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == P14D_TIMESTAMP_ROWS  # known legacy gap, not fabricated


def test_p16_cutoff_no_future_violations():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        bad = conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id=?
               AND prediction_cutoff_date > target_date""",
            (P16_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert bad == 0


def test_production_rows_4960():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS


# ── per-strategy API tests ────────────────────────────────────────────────────

@pytest.mark.parametrize("strategy_id,min_rows", [
    ("ts3_regime_3bet",     1500),
    ("biglotto_triple_strike", 1500),
    ("biglotto_deviation_2bet", 1500),
])
def test_api_strategy_row_count(strategy_id, min_rows):
    r = _history(strategy_id, page_size=1)
    assert r["total"] >= min_rows, \
        f"{strategy_id}: expected >= {min_rows} rows, got {r['total']}"


def test_api_ts3_returns_timestamp_fields(ts3_page: dict):
    rec = ts3_page["records"][0]
    assert "prediction_cutoff_date" in rec
    assert "prediction_generated_at" in rec
    # Post-P17B: P14D timestamps have been backfilled — no longer NULL
    assert rec["prediction_cutoff_date"] is not None, \
        "P14D timestamps should be populated after P17B backfill"
    assert rec["prediction_generated_at"] is not None, \
        "P14D timestamps should be populated after P17B backfill"


def test_api_triple_strike_has_timestamps(triple_page: dict):
    # P16 rows should have timestamps
    p16_recs = [r for r in triple_page["records"]
                if r.get("controlled_apply_id") == P16_APPLY_ID]
    for rec in p16_recs:
        assert rec["prediction_cutoff_date"] is not None, \
            f"draw={rec['target_draw']}: expected non-NULL prediction_cutoff_date"
        assert rec["prediction_generated_at"] is not None, \
            f"draw={rec['target_draw']}: expected non-NULL prediction_generated_at"


def test_api_deviation_has_timestamps(deviation_page: dict):
    p16_recs = [r for r in deviation_page["records"]
                if r.get("controlled_apply_id") == P16_APPLY_ID]
    for rec in p16_recs:
        assert rec["prediction_cutoff_date"] is not None
        assert rec["prediction_generated_at"] is not None


# ── general API field / quality tests ────────────────────────────────────────

def test_api_hit_count_consistent_first_pages():
    for sid in STRATEGIES:
        r = _history(sid, page_size=50)
        for rec in r["records"]:
            hn = rec.get("hit_numbers") or []
            hc = rec.get("hit_count") or 0
            assert len(hn) == hc, \
                f"{sid} draw={rec['target_draw']}: hit_count={hc} len_hit_numbers={len(hn)}"


def test_api_pagination_supported():
    r1 = _history("biglotto_triple_strike", page=1, page_size=10)
    r2 = _history("biglotto_triple_strike", page=2, page_size=10)
    assert r1["total"] >= 1500
    assert len(r1["records"]) == 10
    d1 = {rec["target_draw"] for rec in r1["records"]}
    d2 = {rec["target_draw"] for rec in r2["records"]}
    assert d1.isdisjoint(d2), "Pages 1 and 2 must not overlap"


def test_api_display_status_present():
    r = _history("biglotto_triple_strike", page_size=5)
    for rec in r["records"]:
        assert rec.get("display_status") == "SHOW_REPLAY_RESULT"


def test_api_visibility_state_present():
    r = _history("biglotto_triple_strike", page_size=5)
    for rec in r["records"]:
        assert rec.get("visibility_state") == "ROW_BACKED"


def test_no_db_writes():
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == PROD_ROWS
