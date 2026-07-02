"""Tests for P349A: lazy/no-DB boot path so artifact-only routes can be served
from a clean checkout without the canonical SQLite DB, while DB-backed routes
still fail closed (explicit error, never silent fake data) when the DB is
absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(LOTTERY_API))

import app as app_module  # noqa: E402
import database as database_module  # noqa: E402


def _simulate_missing_db(monkeypatch):
    """Force database.py's lazy resolver to behave as if the canonical DB is absent."""

    def _raise_missing(_db_path=None):
        raise FileNotFoundError("Lottery DB path does not exist: <simulated missing DB>")

    monkeypatch.setattr(database_module, "resolve_db_path", _raise_missing)


def test_database_manager_construction_performs_no_io(monkeypatch):
    """Constructing DatabaseManager must not resolve a DB path or touch the filesystem."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("resolve_db_path must not run during construction")

    monkeypatch.setattr(database_module, "resolve_db_path", _boom)
    mgr = database_module.DatabaseManager()
    assert mgr.db_path is None
    assert mgr._initialized is False


def test_database_manager_fails_closed_when_db_absent(monkeypatch):
    """First real DB operation must raise a clear error, never silently succeed."""
    _simulate_missing_db(monkeypatch)
    mgr = database_module.DatabaseManager()
    with pytest.raises(FileNotFoundError):
        mgr.get_all_draws()
    assert mgr._initialized is False


def test_app_and_database_modules_imported_successfully():
    """Collecting this file already proves app.py's full router chain (including
    routes/data.py, routes/prediction.py, routes/optimization.py — each of which
    does `from database import db_manager` at module level) imports cleanly in
    this environment, which has no lottery_api/data/lottery_v2.db present.
    """
    assert app_module.app is not None
    assert hasattr(database_module, "db_manager")


def test_p333_scoreboard_serves_200_without_db(monkeypatch):
    """P333 artifact-only route must serve correctly even when canonical DB is absent."""
    _simulate_missing_db(monkeypatch)

    client = TestClient(app_module.app)
    response = client.get("/api/replay/strategy-pick-scoreboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["strategy_pick_records"] == 603
    assert payload["summary"]["combination_leaderboard_records"] == 510
    counts = payload["summary"]["strategy_window_decision_counts"]
    assert counts["HISTORICAL_WINDOW_PASS"] == 13
    assert counts["HISTORICAL_WINDOW_FAIL"] == 23
    assert payload["no_betting_advice"] is True
    assert payload["no_strategy_promotion"] is True
    assert payload["historical_replay_only"] is True


def test_db_backed_route_fails_clearly_without_db(monkeypatch):
    """A DB-backed route must return an explicit error, never fabricate empty/fake data."""
    _simulate_missing_db(monkeypatch)

    client = TestClient(app_module.app, raise_server_exceptions=False)
    response = client.get("/api/history", params={"lotteryType": "BIG_LOTTO"})

    assert response.status_code == 500
    assert "does not exist" in response.json()["detail"]
