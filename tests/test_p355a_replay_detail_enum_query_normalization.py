"""P355A - replay detail enum query normalization.

Validates case/whitespace-insensitive sort and hit_filter query values on the
read-only replay detail endpoints without opening the production DB.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_ID = "biglotto_case_2bet"


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
            ])
        if "COUNT(*) AS total_rows" in compact_sql and "COUNT(DISTINCT target_draw)" not in compact_sql:
            return _Rows([{
                "total_rows": 2,
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
            ])
        if "COUNT(DISTINCT target_draw)" in compact_sql:
            return _Rows([{
                "total_rows": 2,
                "total_draws": 1,
                "hit_rows": 1,
                "first_draw": 115000001,
                "last_draw": 115000001,
            }])
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
    monkeypatch.setattr(replay_mod, "get_strategy_lifecycle_status", lambda strategy_id: "ONLINE")
    return replay_mod


@pytest.fixture()
def client(replay_mod):
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility")


def _detail_params(**overrides):
    params = {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": STRATEGY_ID,
        "bet_index": 2,
        "page_size": 5,
    }
    params.update(overrides)
    return params


def test_detail_sort_and_hit_filter_queries_are_case_and_whitespace_insensitive(client):
    response = client.get(
        "/api/replay/history-detail",
        params=_detail_params(sort=" TARGET_DRAW_ASC ", hit_filter=" HIT "),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sort"] == "target_draw_asc"
    assert payload["hit_filter"] == "hit"
    assert payload["summary"]["current_filters"]["sort"] == "target_draw_asc"
    assert payload["summary"]["current_filters"]["hit_filter"] == "hit"


def test_grouped_detail_sort_and_hit_filter_queries_are_case_and_whitespace_insensitive(client):
    response = client.get(
        "/api/replay/history-detail-grouped",
        params=_detail_params(sort=" TARGET_DRAW_ASC ", hit_filter=" MISS "),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sort"] == "target_draw_asc"
    assert payload["hit_filter"] == "miss"
    assert payload["summary"]["current_filters"]["sort"] == "target_draw_asc"
    assert payload["summary"]["current_filters"]["hit_filter"] == "miss"


def test_invalid_detail_enum_still_returns_400(client):
    response = client.get(
        "/api/replay/history-detail",
        params=_detail_params(sort="target_draw_latest"),
    )

    assert response.status_code == 400
    assert "invalid sort" in response.json()["detail"]
