"""Tests for the P536E read-only strategy lift-extension artifact route."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottery_api.routes import replay

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "outputs/research/p536c_success_matrix_lift_extension_20260708.json"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(replay.router)
    return TestClient(app)


def test_route_serves_200_and_reuses_committed_artifact():
    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    response = _client().get("/api/replay/strategy-lift-extension")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_version"] == data["schema_version"]
    assert payload["generated_at"] == data["generated_at"]
    assert payload["source_artifact"] == ARTIFACT.name


def test_route_exposes_provenance_and_disclaimer():
    response = _client().get("/api/replay/strategy-lift-extension")
    payload = response.json()

    assert payload["source"]["data_hash_sha256"]
    assert payload["source"]["db_open_mode"] == "sqlite3 URI mode=ro + PRAGMA query_only=ON"
    assert payload["disclaimer"] == (
        "Retrospective historical replay evidence only; no prediction, "
        "betting, edge, future-winning, or production-readiness claim."
    )
    assert payload["historical_replay_only"] is True
    assert payload["no_future_guarantee"] is True
    assert payload["no_betting_advice"] is True
    assert payload["no_strategy_promotion"] is True


def test_top_lift_cells_grouped_by_lottery_and_window_ranked_desc():
    response = _client().get("/api/replay/strategy-lift-extension")
    cells = response.json()["top_lift_cells"]

    assert len(cells) > 0
    seen_groups = {}
    for cell in cells:
        key = (cell["lottery_type"], cell["window"])
        seen_groups.setdefault(key, []).append(cell["any_main_hit_lift"])
        assert cell["lottery_type"] in {"BIG_LOTTO", "DAILY_539", "POWER_LOTTO"}
        assert cell["window"] in {50, 300, 750}

    for key, lifts in seen_groups.items():
        assert len(lifts) <= 3, f"expected at most 3 rows per group, got {len(lifts)} for {key}"
        assert lifts == sorted(lifts, reverse=True), f"group {key} not sorted descending"


def test_cross_lottery_normalized_lift_summary_has_lotteries_breakdown():
    response = _client().get("/api/replay/strategy-lift-extension")
    rows = response.json()["cross_lottery_normalized_lift_summary"]

    assert 0 < len(rows) <= 10
    for row in rows:
        assert "feature_family" in row
        assert "lotteries" in row
        assert isinstance(row["lotteries"], dict)
        assert len(row["lotteries"]) > 0


def test_combination_stability_rank_summary_sorted_ascending():
    response = _client().get("/api/replay/strategy-lift-extension")
    rows = response.json()["combination_stability_rank_summary"]

    assert 0 < len(rows) <= 15
    ranks = [row["stability_rank"] for row in rows]
    assert ranks == sorted(ranks)


def test_route_does_not_open_sqlite_or_recompute(monkeypatch):
    """The route must only read the committed JSON artifact — no DB, no recompute."""
    import sqlite3

    def _fail_connect(*args, **kwargs):
        raise AssertionError("route must not open a sqlite3 connection")

    monkeypatch.setattr(sqlite3, "connect", _fail_connect)

    response = _client().get("/api/replay/strategy-lift-extension")
    assert response.status_code == 200


def test_missing_artifact_returns_clear_error(monkeypatch):
    monkeypatch.setattr(replay, "_LIFT_EXTENSION_PATH", REPO_ROOT / "outputs/research/does-not-exist.json")

    response = _client().get("/api/replay/strategy-lift-extension")
    assert response.status_code == 500
    assert "not found" in response.json()["detail"]
