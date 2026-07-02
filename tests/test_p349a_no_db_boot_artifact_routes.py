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


@pytest.fixture(autouse=True)
def _reset_db_manager_singleton():
    """Guard against cross-test state leakage on the module-level db_manager singleton.

    Several tests below rely on database_module.db_manager being uninitialized
    (so the no-DB / fail-closed paths are actually exercised). Resetting before
    and after every test makes this file's outcome independent of run order.
    """
    database_module.db_manager._initialized = False
    database_module.db_manager.db_path = None
    yield
    database_module.db_manager._initialized = False
    database_module.db_manager.db_path = None


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


# ─── P350B: lazy-init recursion regression tests ───────────────────────────
#
# Prior to the P350B fix, _get_connection() -> _ensure_ready() -> _init_database()
# -> _get_connection() formed an unconditional cycle, because _init_database()
# opened its own connection via _get_connection() while _initialized was still
# False. On any machine where the DB actually exists, the very first DB-backed
# call hit RecursionError. The existing tests above never caught this because
# they only exercise the *missing*-DB path (which raises before recursion
# starts). These tests exercise the DB-*present* happy path instead.


def test_get_connection_succeeds_against_real_temp_db_no_recursion(tmp_path):
    """DB-present happy path: _get_connection() must not recurse and must
    leave the manager correctly marked initialized."""
    tmp_db = tmp_path / "p350b_happy_path.db"
    tmp_db.touch()

    mgr = database_module.DatabaseManager(str(tmp_db))
    assert mgr._initialized is False

    try:
        conn = mgr._get_connection()
    except RecursionError:  # pragma: no cover - documents the pre-fix failure mode
        pytest.fail("_get_connection() recursed infinitely on a present DB")

    try:
        row = conn.execute("SELECT 1").fetchone()
        assert row[0] == 1
    finally:
        conn.close()

    assert mgr._initialized is True
    assert mgr.db_path == str(tmp_db)


def test_init_database_runs_exactly_once_across_repeated_get_connection(tmp_path):
    """Init idempotence: repeated _get_connection() calls must not re-run
    schema initialization once the manager is initialized."""
    tmp_db = tmp_path / "p350b_idempotence.db"
    tmp_db.touch()

    mgr = database_module.DatabaseManager(str(tmp_db))

    call_count = {"n": 0}
    original_init_database = mgr._init_database

    def _counting_init_database():
        call_count["n"] += 1
        return original_init_database()

    mgr._init_database = _counting_init_database

    for _ in range(3):
        conn = mgr._get_connection()
        conn.execute("SELECT 1")
        conn.close()

    assert call_count["n"] == 1
    assert mgr._initialized is True


def test_real_resolver_raises_for_absent_db_and_creates_no_file(tmp_path):
    """Real resolver absent path (no monkeypatch): a genuinely-missing custom
    DB path must fail closed via the real resolve_db_path(), and must never
    create the file it failed to find."""
    absent_db = tmp_path / "does_not_exist_dir" / "missing.db"
    assert not absent_db.exists()

    mgr = database_module.DatabaseManager(str(absent_db))
    with pytest.raises(FileNotFoundError):
        mgr._get_connection()

    assert not absent_db.exists()
    assert mgr._initialized is False


def test_p333_route_serves_without_creating_canonical_db_or_sidecars(monkeypatch):
    """P333 artifact route must serve its full contract without ever creating
    the canonical DB file or any -wal/-shm journal sidecars, before or after
    the request."""
    _simulate_missing_db(monkeypatch)

    canonical_db = LOTTERY_API / "data" / "lottery_v2.db"
    cwd_db = REPO_ROOT / "data" / "lottery_v2.db"
    sidecar_paths = [
        Path(str(canonical_db) + "-wal"),
        Path(str(canonical_db) + "-shm"),
        Path(str(cwd_db) + "-wal"),
        Path(str(cwd_db) + "-shm"),
    ]

    assert not canonical_db.exists()
    for sidecar in sidecar_paths:
        assert not sidecar.exists()

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

    assert not canonical_db.exists()
    for sidecar in sidecar_paths:
        assert not sidecar.exists()


def test_db_manager_singleton_starts_uninitialized():
    """Singleton hygiene: the module-level db_manager must be uninitialized
    at the start of a no-DB test, independent of what ran before it."""
    assert database_module.db_manager._initialized is False
    assert database_module.db_manager.db_path is None
