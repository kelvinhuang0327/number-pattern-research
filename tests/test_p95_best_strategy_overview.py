"""
P95 Best Strategy Overview — API and contract tests.

Tests call route functions directly (no live HTTP server required).
FastAPI Query() defaults are NOT unwrapped when calling routes directly,
so all async route calls must pass explicit values for every Query param.

Covers: schema, filters, POWER_LOTTO special, BIG_LOTTO/DAILY_539 no-special,
rejected/offline caveat, unsupported bet count, no DB writes, replay row invariance.
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT   = Path(__file__).resolve().parents[1]
_LOTTERY_API = _REPO_ROOT / "lottery_api"
_PROD_DB     = _LOTTERY_API / "data" / "lottery_v2.db"

sys.path.insert(0, str(_LOTTERY_API))

from routes.best_strategy_overview import (
    _get_biglotto_ranking,
    _get_powerlotto_ranking,
    _get_daily539_ranking,
    _attach_stability_biglotto,
    _artifact_available,
    _DISCLAIMER,
    _normalise_biglotto_entry,
    _normalise_powerlotto_entry,
    _normalise_daily539_entry,
    get_best_strategy_overview,
    get_next_prediction,
    get_available_artifacts,
)

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_MAX_DRAW    = 115000041

# ── Helpers ────────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _bso(lottery_type, bet_count, observation_window=1500, ranking_metric="m3plus_rate"):
    """Wrapper that always passes explicit values — avoids FastAPI Query() default issue."""
    return run(get_best_strategy_overview(
        lottery_type=lottery_type,
        bet_count=bet_count,
        observation_window=observation_window,
        ranking_metric=ranking_metric,
    ))


def _pred(strategy_id, lottery_type):
    return run(get_next_prediction(strategy_id=strategy_id, lottery_type=lottery_type))


def db_replay_rows() -> int:
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()


def db_max_draw() -> int:
    conn = sqlite3.connect(str(_PROD_DB))
    try:
        return conn.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
    finally:
        conn.close()


# ── 1. API returns 200-equiv for BIG_LOTTO ────────────────────────────────────

def test_api_returns_ok_biglotto():
    resp = _bso("BIG_LOTTO", 3)
    assert isinstance(resp, dict)
    assert resp.get("lottery_type") == "BIG_LOTTO"
    assert resp.get("generation_status") in ("READY", "SOURCE_UNAVAILABLE")


# ── 2. API returns 200-equiv for POWER_LOTTO ──────────────────────────────────

def test_api_returns_ok_powerlotto():
    resp = _bso("POWER_LOTTO", 3)
    assert isinstance(resp, dict)
    assert resp.get("lottery_type") == "POWER_LOTTO"
    assert resp.get("generation_status") in ("READY", "SOURCE_UNAVAILABLE")


# ── 3. API returns 200-equiv for DAILY_539 ────────────────────────────────────

def test_api_returns_ok_daily539():
    resp = _bso("DAILY_539", 3)
    assert isinstance(resp, dict)
    assert resp.get("lottery_type") == "DAILY_539"
    assert resp.get("generation_status") in ("READY", "SOURCE_UNAVAILABLE")


# ── 4. API returns RankingCard schema ─────────────────────────────────────────

def test_api_returns_ranking_card_schema():
    resp = _bso("BIG_LOTTO", 3)
    cards = resp.get("cards", [])
    assert isinstance(cards, list)
    if cards:
        c = cards[0]
        required = [
            "rank", "strategy_id", "display_name", "lottery_type", "bet_count",
            "observation_window", "lifecycle_status", "source_category",
            "row_backed", "benchmark_only", "adapter_generated",
            "rejected_or_offline_caveat", "sample_size", "m3plus_rate",
            "avg_hit_count", "m4plus_rate", "zero_hit_rate", "special_hit_rate",
            "stability_across_windows", "warning_flags",
        ]
        for field in required:
            assert field in c, f"RankingCard missing field: {field}"


# ── 5. Filter by bet_count works ──────────────────────────────────────────────

def test_filter_by_bet_count():
    for bc in [1, 2, 3, 5]:
        resp = _bso("BIG_LOTTO", bc)
        assert resp.get("bet_count") == bc
        for card in resp.get("cards", []):
            assert card.get("bet_count") == bc


# ── 6. Filter by observation_window works ─────────────────────────────────────

def test_filter_by_observation_window():
    for w in [30, 100, 500, 1500]:
        resp = _bso("POWER_LOTTO", 3, observation_window=w)
        assert resp.get("observation_window") == w
        for card in resp.get("cards", []):
            assert card.get("observation_window") == w


# ── 7. Default ranking_metric echo'd in response ──────────────────────────────

def test_ranking_metric_m3plus_rate_in_response():
    resp = _bso("BIG_LOTTO", 3, ranking_metric="m3plus_rate")
    assert resp.get("ranking_metric") == "m3plus_rate"


# ── 8. POWER_LOTTO cards expose special_hit_rate field ────────────────────────

def test_power_lotto_cards_have_special_hit_rate_field():
    cards = _get_powerlotto_ranking(1500, 3)
    for c in cards:
        assert "special_hit_rate" in c, "POWER_LOTTO card must have special_hit_rate field"


# ── 9. BIG_LOTTO cards have special_hit_rate = null ──────────────────────────

def test_biglotto_cards_special_hit_rate_is_null():
    cards = _get_biglotto_ranking(1500, 3)
    for c in cards:
        assert c.get("special_hit_rate") is None, "BIG_LOTTO must have special_hit_rate=null"


# ── 10. DAILY_539 cards have special_hit_rate = null ─────────────────────────

def test_daily539_cards_special_hit_rate_is_null():
    cards = _get_daily539_ranking(1500, 3)
    for c in cards:
        assert c.get("special_hit_rate") is None, "DAILY_539 must have special_hit_rate=null"


# ── 11. Rejected/offline cards include caveat ─────────────────────────────────

def test_rejected_cards_include_caveat():
    raw = {
        "strategy_id": "test_rejected",
        "lifecycle": "REJECTED",
        "sample_size": 30,
        "m3_rate": 0.1,
        "source": "DB_ROW",
    }
    card = _normalise_daily539_entry(raw, 30, 1)
    assert card["rejected_or_offline_caveat"] is not None
    assert "REJECTED" in card["rejected_or_offline_caveat"]
    assert "REJECTED_STRATEGY" in card["warning_flags"]


def test_offline_cards_include_caveat():
    raw = {"strategy_id": "test_offline", "lifecycle": "OFFLINE", "sample_size": 200, "source": "DB_ROW"}
    card = _normalise_biglotto_entry(raw, 1500, 2)
    assert card["rejected_or_offline_caveat"] is not None
    assert "OFFLINE" in card["rejected_or_offline_caveat"]


# ── 12. Rejected next-prediction returns REJECTED_REPLAY_ONLY ─────────────────

@pytest.mark.parametrize("strategy_id", ["biglotto_ts3_acb_4bet"])  # known REJECTED stub
def test_rejected_next_prediction_status(strategy_id):
    resp = _pred(strategy_id, "BIG_LOTTO")
    assert isinstance(resp, dict)
    assert resp.get("generation_status") == "REJECTED_REPLAY_ONLY"
    assert resp.get("predicted_bets") is None
    assert _DISCLAIMER in resp.get("disclaimer", "")


# ── 13. Next-prediction endpoint returns NextPrediction schema ────────────────

def test_next_prediction_returns_schema():
    resp = _pred("ts3_regime_3bet", "BIG_LOTTO")
    required = [
        "next_draw_lottery_type", "strategy_id", "bet_count",
        "predicted_bets", "predicted_special", "adapter_name",
        "generation_status", "disclaimer", "prediction_generated_at",
    ]
    for field in required:
        assert field in resp, f"NextPrediction missing field: {field}"
    assert resp["next_draw_lottery_type"] == "BIG_LOTTO"
    assert resp["strategy_id"] == "ts3_regime_3bet"


# ── 14. POWER_LOTTO next-prediction handles predicted_special separately ───────

def test_power_lotto_next_prediction_special_field():
    resp = _pred("fourier_rhythm_3bet", "POWER_LOTTO")
    assert "predicted_special" in resp
    if resp.get("generation_status") == "READY":
        bets = resp.get("predicted_bets", [])
        for bet in bets:
            # POWER_LOTTO main: 6 numbers from [1,38]
            assert len(bet) <= 6
            for n in bet:
                assert 1 <= n <= 38, f"Main number {n} out of POWER_LOTTO range [1,38]"


# ── 15. BIG_LOTTO next-prediction has predicted_special = null ────────────────

def test_biglotto_next_prediction_special_is_null():
    resp = _pred("ts3_regime_3bet", "BIG_LOTTO")
    assert resp.get("predicted_special") is None, "BIG_LOTTO must have predicted_special=null"


# ── 16. Unsupported lottery for strategy → UNSUPPORTED_BET_COUNT ──────────────

def test_unsupported_lottery_type_for_strategy():
    # ts3_regime_3bet only supports BIG_LOTTO
    resp = _pred("ts3_regime_3bet", "POWER_LOTTO")
    assert resp.get("generation_status") == "UNSUPPORTED_BET_COUNT"
    assert resp.get("predicted_bets") is None


# ── 17. No DB writes — BIG_LOTTO ─────────────────────────────────────────────

def test_no_db_writes_biglotto():
    rows_before = db_replay_rows()
    _bso("BIG_LOTTO", 3)
    assert db_replay_rows() == rows_before


# ── 18. No DB writes — POWER_LOTTO ────────────────────────────────────────────

def test_no_db_writes_powerlotto():
    rows_before = db_replay_rows()
    _bso("POWER_LOTTO", 3, observation_window=500)
    assert db_replay_rows() == rows_before


# ── 19. No DB writes — DAILY_539 ─────────────────────────────────────────────

def test_no_db_writes_daily539():
    rows_before = db_replay_rows()
    _bso("DAILY_539", 1, observation_window=100)
    assert db_replay_rows() == rows_before


# ── 20. replay_rows remains 54462 after all API calls ─────────────────────────

def test_replay_rows_invariant():
    for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
        for w in [30, 1500]:
            _bso(lt, 3, observation_window=w)
    assert db_replay_rows() == EXPECTED_REPLAY_ROWS


# ── 21. POWER_LOTTO max draw unchanged ───────────────────────────────────────

def test_power_lotto_max_draw_invariant():
    _bso("POWER_LOTTO", 3)
    assert db_max_draw() == EXPECTED_MAX_DRAW


# ── 22. Available artifacts endpoint correct ──────────────────────────────────

def test_available_artifacts_endpoint():
    resp = run(get_available_artifacts())
    assert isinstance(resp, dict)
    for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
        assert lt in resp
        assert isinstance(resp[lt], bool)
    # All three must be True since we verified artifacts exist in pre-flight
    assert resp["BIG_LOTTO"] is True
    assert resp["POWER_LOTTO"] is True
    assert resp["DAILY_539"] is True


# ── 23. Disclaimer always present in ranking response ─────────────────────────

def test_disclaimer_always_present_in_ranking():
    resp = _bso("BIG_LOTTO", 3)
    assert _DISCLAIMER in resp.get("disclaimer", "")


# ── 24. Disclaimer always present in prediction response ──────────────────────

def test_disclaimer_always_present_in_prediction():
    resp = _pred("ts3_regime_3bet", "BIG_LOTTO")
    assert _DISCLAIMER in resp.get("disclaimer", "")


# ── 25. BIG_LOTTO cards have m6_rate field ────────────────────────────────────

def test_biglotto_has_m6_rate_field():
    cards = _get_biglotto_ranking(1500, 3)
    for c in cards:
        assert "m6_rate" in c, "BIG_LOTTO card must have m6_rate field"


# ── 26. DAILY_539 next-prediction predicted_special is null ───────────────────

def test_daily539_next_prediction_special_is_null():
    resp = _pred("daily539_f4cold", "DAILY_539")
    assert resp.get("predicted_special") is None, "DAILY_539 must have predicted_special=null"


# ── 27. Stability score attached when window data available ───────────────────

def test_stability_score_attached_when_data_available():
    cards = _get_biglotto_ranking(1500, 3)
    _attach_stability_biglotto(cards)
    for c in cards:
        assert isinstance(c.get("stability_across_windows"), dict)


# ── 28. Ranking is sorted by rank ascending ───────────────────────────────────

def test_ranking_sorted_ascending():
    resp = _bso("BIG_LOTTO", 3, ranking_metric="m3plus_rate")
    cards = resp.get("cards", [])
    ranks = [c.get("rank") for c in cards]
    assert ranks == sorted(ranks), f"Cards not sorted: {ranks}"


# ── 29. Unknown strategy returns ADAPTER_MISSING ──────────────────────────────

def test_unknown_strategy_returns_adapter_missing():
    resp = _pred("nonexistent_xyz_p95_test_999", "BIG_LOTTO")
    assert resp.get("generation_status") == "ADAPTER_MISSING"
    assert resp.get("predicted_bets") is None
