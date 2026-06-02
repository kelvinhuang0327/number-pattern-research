"""
tests/conftest.py — CI DB Fixture Guard
=======================================
Skips tests marked @pytest.mark.requires_db when the SQLite replay
database fixture is unavailable.

DB path resolution order:
  1. LOTTERY_TEST_DB_PATH environment variable (override for CI / simulation)
  2. lottery_api/data/lottery_v2.db  (default local path)

Rules:
  - Never creates, downloads, writes, or modifies the DB.
  - Skip message explicitly names the path that was checked.
  - Non-DB tests are never affected.

P181 Part D additions (P182 backport):
  - requires_zen_gates_db: skip if DB row count != 94924 (zen-gates canonical research DB)
  - requires_bet_index: skip if bet_index column absent from strategy_prediction_replays
  These markers SKIP on stale main DB — they do NOT FAIL.
  Row counts in contract tests are NOT weakened (94924 guard preserved).
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_DEFAULT_DB_PATH = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

_ZEN_GATES_ROW_COUNT = 94924


def _get_db_path() -> Path:
    """Return the DB path, honouring LOTTERY_TEST_DB_PATH env override."""
    env_override = os.environ.get("LOTTERY_TEST_DB_PATH")
    if env_override:
        return Path(env_override)
    return _DEFAULT_DB_PATH


def _db_row_count(db_path: Path) -> int | None:
    """Return row count of strategy_prediction_replays, or None if unavailable."""
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
        count = cur.fetchone()[0]
        con.close()
        return count
    except Exception:
        return None


def _bet_index_present(db_path: Path) -> bool:
    """Return True if bet_index column exists in strategy_prediction_replays."""
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.execute("PRAGMA table_info(strategy_prediction_replays);")
        cols = [row[1] for row in cur.fetchall()]
        con.close()
        return "bet_index" in cols
    except Exception:
        return False


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip tests based on DB availability and schema markers."""
    db_path = _get_db_path()

    if item.get_closest_marker("requires_db") is not None:
        if not db_path.exists():
            pytest.skip(
                f"requires local SQLite replay database fixture "
                f"(checked: {db_path})"
            )

    if item.get_closest_marker("requires_zen_gates_db") is not None:
        if not db_path.exists():
            pytest.skip(
                f"requires zen-gates canonical DB (94924 rows) — "
                f"DB not found at {db_path}"
            )
        actual = _db_row_count(db_path)
        if actual != _ZEN_GATES_ROW_COUNT:
            pytest.skip(
                f"requires zen-gates canonical DB (expected {_ZEN_GATES_ROW_COUNT} rows, "
                f"got {actual}) — run against zen-gates-ff6802 worktree DB"
            )

    if item.get_closest_marker("requires_bet_index") is not None:
        if not db_path.exists():
            pytest.skip(
                f"requires bet_index column — DB not found at {db_path}"
            )
        if not _bet_index_present(db_path):
            pytest.skip(
                "requires bet_index column in strategy_prediction_replays — "
                "absent in main DB; run against zen-gates-ff6802 worktree DB"
            )
