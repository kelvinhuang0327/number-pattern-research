"""P354A - replay API lottery_type query normalization.

Validates lowercase/whitespace lottery_type query values on read-only replay
endpoints without changing DB state.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_ID = "biglotto_case_2bet"


class _SyncASGIClient:
    """Synchronous facade over httpx's ASGI transport.

    starlette.testclient.TestClient (0.27.0) constructs its underlying
    httpx.Client with the removed `app=` kwarg, raising TypeError under
    httpx>=0.28. This bridges httpx.AsyncClient + ASGITransport through
    asyncio.run so existing `client.get(...)` call sites are unchanged.
    """

    def __init__(self, app, base_url="http://testserver"):
        import httpx

        self._transport = httpx.ASGITransport(app=app)
        self._base_url = base_url

    def get(self, url, params=None):
        import httpx

        async def _get():
            async with httpx.AsyncClient(transport=self._transport, base_url=self._base_url) as ac:
                return await ac.get(url, params=params)

        return asyncio.run(_get())


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0]


class _FakeReplayConn:
    def execute(self, sql, params=None):
        compact_sql = " ".join(sql.split())
        if "GROUP_CONCAT(DISTINCT bet_index)" in compact_sql:
            return _Rows([{
                "lottery_type": "BIG_LOTTO",
                "strategy_id": STRATEGY_ID,
                "db_strategy_name": "Case Strategy",
                "total_rows": 2,
                "distinct_draw_count": 1,
                "max_bet_index": 2,
                "bet_indices_csv": "1,2",
                "min_draw_int": 115000001,
                "max_draw_int": 115000001,
                "predicted_cnt": 2,
                "rejected_cnt": 0,
                "insuf_cnt": 0,
                "error_cnt": 0,
                "unavail_cnt": 0,
            }])
        if "COUNT(*) FROM strategy_prediction_replays WHERE" in compact_sql and "GROUP BY" not in compact_sql:
            return _Rows([[2]])
        if "SELECT lottery_type, strategy_id, strategy_name" in compact_sql:
            return _Rows([
                {
                    "lottery_type": "BIG_LOTTO",
                    "strategy_id": STRATEGY_ID,
                    "strategy_name": "Case Strategy",
                    "target_draw": "115000001",
                    "target_date": "2026-01-01",
                    "predicted_numbers": "[1, 2, 3, 4, 5, 6]",
                    "predicted_special": None,
                    "actual_numbers": "[1, 2, 7, 8, 9, 10]",
                    "actual_special": None,
                    "hit_count": 2,
                    "hit_numbers": "[1, 2]",
                    "special_hit": 0,
                    "generated_at": "2026-01-01T00:00:00Z",
                    "truth_level": "LIVE",
                    "controlled_apply_id": None,
                    "source": "fixture",
                    "provenance_hash": "hash-1",
                    "provenance_source": "fixture",
                },
                {
                    "lottery_type": "BIG_LOTTO",
                    "strategy_id": STRATEGY_ID,
                    "strategy_name": "Case Strategy",
                    "target_draw": "115000001",
                    "target_date": "2026-01-01",
                    "predicted_numbers": "[11, 12, 13, 14, 15, 16]",
                    "predicted_special": None,
                    "actual_numbers": "[1, 2, 7, 8, 9, 10]",
                    "actual_special": None,
                    "hit_count": 0,
                    "hit_numbers": "[]",
                    "special_hit": 0,
                    "generated_at": "2026-01-01T00:00:00Z",
                    "truth_level": "LIVE",
                    "controlled_apply_id": None,
                    "source": "fixture",
                    "provenance_hash": "hash-2",
                    "provenance_source": "fixture",
                },
            ])
        if "COUNT(*) AS total_rows" in compact_sql and "COUNT(DISTINCT target_draw)" not in compact_sql:
            return _Rows([{
                "total_rows": 2,
                "hit_rows": 1,
                "first_draw": 115000001,
                "last_draw": 115000001,
            }])
        if "COUNT(DISTINCT target_draw)" in compact_sql:
            return _Rows([{
                "total_rows": 2,
                "total_draws": 1,
                "hit_rows": 1,
                "first_draw": 115000001,
                "last_draw": 115000001,
            }])
        if "SELECT COUNT(*) FROM (" in compact_sql:
            return _Rows([[1]])
        if "SELECT target_draw, MAX(target_date)" in compact_sql:
            return _Rows([{
                "target_draw": "115000001",
                "draw_date": "2026-01-01",
                "n_bets": 2,
                "hit_bets": 1,
                "max_hit_count": 2,
                "total_hit_count": 2,
            }])
        if "SELECT target_draw, bet_index" in compact_sql:
            return _Rows([
                {
                    "target_draw": "115000001",
                    "bet_index": 1,
                    "strategy_name": "Case Strategy",
                    "target_date": "2026-01-01",
                    "predicted_numbers": "[1, 2, 3, 4, 5, 6]",
                    "predicted_special": None,
                    "actual_numbers": "[1, 2, 7, 8, 9, 10]",
                    "actual_special": None,
                    "hit_numbers": "[1, 2]",
                    "hit_count": 2,
                    "special_hit": 0,
                    "replay_status": "PREDICTED",
                    "truth_level": "LIVE",
                    "controlled_apply_id": None,
                    "source": "fixture",
                    "provenance_hash": "hash-1",
                    "provenance_source": "fixture",
                },
                {
                    "target_draw": "115000001",
                    "bet_index": 2,
                    "strategy_name": "Case Strategy",
                    "target_date": "2026-01-01",
                    "predicted_numbers": "[11, 12, 13, 14, 15, 16]",
                    "predicted_special": None,
                    "actual_numbers": "[1, 2, 7, 8, 9, 10]",
                    "actual_special": None,
                    "hit_numbers": "[]",
                    "hit_count": 0,
                    "special_hit": 0,
                    "replay_status": "PREDICTED",
                    "truth_level": "LIVE",
                    "controlled_apply_id": None,
                    "source": "fixture",
                    "provenance_hash": "hash-2",
                    "provenance_source": "fixture",
                },
            ])
        raise AssertionError(f"unexpected SQL: {compact_sql}")

    def close(self):
        pass


@pytest.fixture()
def replay_mod(monkeypatch):
    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")

    monkeypatch.setattr(replay_mod, "_open_conn", lambda: _FakeReplayConn())
    monkeypatch.setattr(replay_mod, "list_executable_strategy_ids", lambda: [STRATEGY_ID])
    monkeypatch.setattr(
        replay_mod,
        "list_strategy_lifecycle_metadata",
        lambda: [{
            "strategy_id": STRATEGY_ID,
            "strategy_name": "Case Strategy",
            "strategy_version": "v1",
            "lifecycle_status": "ONLINE",
            "supported_lottery_types": ["BIG_LOTTO"],
        }],
    )
    monkeypatch.setattr(replay_mod, "get_strategy_lifecycle_status", lambda strategy_id: "ONLINE")
    return replay_mod


@pytest.fixture()
def client(replay_mod):
    try:
        from fastapi import FastAPI
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return _SyncASGIClient(app)
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")


@pytest.fixture()
def big_lotto_sample():
    return {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": STRATEGY_ID,
        "bet_index": 2,
    }


def test_overview_lottery_type_query_is_case_and_whitespace_insensitive(client):
    upper = client.get(
        "/api/replay/history-overview",
        params={"bet_index": 0, "lottery_type": "BIG_LOTTO"},
    ).json()
    lower = client.get(
        "/api/replay/history-overview",
        params={"bet_index": 0, "lottery_type": " big_lotto "},
    ).json()

    assert lower["lottery_type_filter"] == "BIG_LOTTO"
    assert lower["total_rows"] == upper["total_rows"]
    assert {row["lottery_type"] for row in lower["rows"]} == {"BIG_LOTTO"}


def test_detail_lottery_type_query_is_case_and_whitespace_insensitive(client, big_lotto_sample):
    upper = client.get(
        "/api/replay/history-detail",
        params={
            "lottery_type": "BIG_LOTTO",
            "strategy_id": big_lotto_sample["strategy_id"],
            "bet_index": big_lotto_sample["bet_index"],
            "page_size": 5,
        },
    )
    lower = client.get(
        "/api/replay/history-detail",
        params={
            "lottery_type": " big_lotto ",
            "strategy_id": big_lotto_sample["strategy_id"],
            "bet_index": big_lotto_sample["bet_index"],
            "page_size": 5,
        },
    )

    assert lower.status_code == 200
    assert lower.json()["lottery_type"] == "BIG_LOTTO"
    assert lower.json()["summary"]["current_filters"]["lottery_type"] == "BIG_LOTTO"
    assert lower.json()["total_count"] == upper.json()["total_count"]
    assert lower.json()["rows"]


def test_grouped_detail_lottery_type_query_is_case_and_whitespace_insensitive(client, big_lotto_sample):
    upper = client.get(
        "/api/replay/history-detail-grouped",
        params={
            "lottery_type": "BIG_LOTTO",
            "strategy_id": big_lotto_sample["strategy_id"],
            "bet_index": big_lotto_sample["bet_index"],
            "page_size": 5,
        },
    )
    lower = client.get(
        "/api/replay/history-detail-grouped",
        params={
            "lottery_type": " big_lotto ",
            "strategy_id": big_lotto_sample["strategy_id"],
            "bet_index": big_lotto_sample["bet_index"],
            "page_size": 5,
        },
    )

    assert lower.status_code == 200
    assert lower.json()["lottery_type"] == "BIG_LOTTO"
    assert lower.json()["summary"]["current_filters"]["lottery_type"] == "BIG_LOTTO"
    assert lower.json()["total_count"] == upper.json()["total_count"]
    assert lower.json()["rows"]
