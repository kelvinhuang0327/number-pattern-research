from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "lottery_api"))

from lottery_api.database import DatabaseManager  # noqa: E402

REAL_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _make_isolated_db(path: Path, with_canonical_view: bool, rows):
    """Build a small, task-owned SQLite fixture (default rollback-journal
    mode, not WAL) with the `draws` schema plus optionally the canonical
    view. Deliberately not WAL so a fresh read-only open never needs
    pre-existing -shm/-wal sidecars, matching how a cold checkout behaves.
    """
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            jackpot_amount REAL DEFAULT NULL,
            sell_amount REAL DEFAULT NULL,
            total_amount REAL DEFAULT NULL,
            numbers_positional TEXT DEFAULT NULL,
            UNIQUE(draw, lottery_type)
        )
        """
    )
    for row in rows:
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) VALUES (?, ?, ?, ?, ?)",
            (row["draw"], row["date"], row["lottery_type"], json.dumps(row["numbers"]), row.get("special", 0)),
        )
    if with_canonical_view:
        # Mirrors the production view's exact definition (verified via
        # `sqlite_master.sql` against the real canonical DB).
        conn.execute(
            """
            CREATE VIEW draws_big_lotto_canonical_main AS
            SELECT d.*
            FROM draws d
            WHERE d.lottery_type = 'BIG_LOTTO'
              AND d.draw NOT LIKE '%-%'
              AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
              AND (
                SELECT MAX(CAST(j.value AS INTEGER))
                FROM json_each(d.numbers) j
              ) > 25
            """
        )
    conn.commit()
    conn.close()


CANONICAL_ROWS = [
    {"draw": "115000001", "date": "2026/01/01", "lottery_type": "BIG_LOTTO", "numbers": [1, 2, 3, 4, 5, 44]},
    {"draw": "115000002", "date": "2026/01/08", "lottery_type": "BIG_LOTTO", "numbers": [7, 8, 9, 10, 11, 49]},
]
ALIEN_ROWS = [
    {"draw": "103000009-01", "date": "2026/01/03", "lottery_type": "BIG_LOTTO", "numbers": [1, 2, 3, 4, 5, 6]},
    {"draw": "20090727", "date": "2009-07-27", "lottery_type": "BIG_LOTTO", "numbers": [1, 2, 3, 4, 5, 6]},
    {"draw": "115000003", "date": "2026/01/15", "lottery_type": "BIG_LOTTO", "numbers": [1, 2, 3, 4, 5, 20]},
]


# ---------------------------------------------------------------------------
# Construction / fail-closed
# ---------------------------------------------------------------------------

def test_read_only_construction_performs_no_io(tmp_path):
    missing = tmp_path / "does_not_exist.db"
    manager = DatabaseManager(db_path=str(missing), read_only=True)
    assert manager.db_path is None
    assert manager._initialized is False
    assert not missing.exists()


def test_read_only_missing_db_fails_closed_without_creating_file(tmp_path):
    missing = tmp_path / "does_not_exist.db"
    manager = DatabaseManager(db_path=str(missing), read_only=True)
    with pytest.raises(FileNotFoundError):
        manager.get_canonical_draws(lottery_type="BIG_LOTTO")
    assert not missing.exists(), "read-only manager must never create the DB file"


def test_read_only_first_query_never_calls_schema_initialization(tmp_path):
    db_path = tmp_path / "isolated.db"
    _make_isolated_db(db_path, with_canonical_view=True, rows=CANONICAL_ROWS)
    manager = DatabaseManager(db_path=str(db_path), read_only=True)
    with patch.object(DatabaseManager, "_init_database") as mocked_init:
        rows = manager.get_canonical_draws(lottery_type="BIG_LOTTO")
        mocked_init.assert_not_called()
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Write methods fail closed before any SQL
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "call",
    [
        lambda m: m.insert_draws([{"draw": "1", "lotteryType": "BIG_LOTTO", "numbers": [1, 2, 3, 4, 5, 6]}]),
        lambda m: m.delete_draw(1),
        lambda m: m.clear_all_data(),
        lambda m: m.vacuum(),
    ],
    ids=["insert_draws", "delete_draw", "clear_all_data", "vacuum"],
)
def test_write_methods_reject_read_only_before_sql(tmp_path, call):
    db_path = tmp_path / "isolated.db"
    _make_isolated_db(db_path, with_canonical_view=False, rows=CANONICAL_ROWS)
    manager = DatabaseManager(db_path=str(db_path), read_only=True)
    with patch.object(DatabaseManager, "_get_connection") as mocked_conn:
        with pytest.raises(PermissionError):
            call(manager)
        mocked_conn.assert_not_called()


# ---------------------------------------------------------------------------
# get_canonical_draws behaves correctly (view path + fallback path) read-only
# ---------------------------------------------------------------------------

def test_get_canonical_draws_view_path_read_only(tmp_path):
    db_path = tmp_path / "isolated_view.db"
    _make_isolated_db(db_path, with_canonical_view=True, rows=CANONICAL_ROWS + ALIEN_ROWS)
    manager = DatabaseManager(db_path=str(db_path), read_only=True)
    draws = manager.get_canonical_draws(lottery_type="BIG_LOTTO")
    got = {d["draw"] for d in draws}
    assert got == {"115000001", "115000002"}, "canonical view must exclude all three alien families"


def test_get_canonical_draws_fallback_filter_read_only(tmp_path):
    db_path = tmp_path / "isolated_fallback.db"
    _make_isolated_db(db_path, with_canonical_view=False, rows=CANONICAL_ROWS + ALIEN_ROWS)
    manager = DatabaseManager(db_path=str(db_path), read_only=True)
    draws = manager.get_canonical_draws(lottery_type="BIG_LOTTO")
    got = {d["draw"] for d in draws}
    assert got == {"115000001", "115000002"}, (
        "fallback filter (view absent) must exclude hyphenated, date-format, "
        "and small-pool-alien rows identically to the view path"
    )


# ---------------------------------------------------------------------------
# No filesystem side effects from read-only access
# ---------------------------------------------------------------------------

def test_read_only_mode_creates_no_wal_shm_journal_sidecars(tmp_path):
    db_path = tmp_path / "isolated_sidecars.db"
    _make_isolated_db(db_path, with_canonical_view=True, rows=CANONICAL_ROWS)
    before = set(os.listdir(tmp_path))

    manager = DatabaseManager(db_path=str(db_path), read_only=True)
    manager.get_canonical_draws(lottery_type="BIG_LOTTO")

    after = set(os.listdir(tmp_path))
    new_files = after - before
    assert new_files == set(), f"read-only access must create no new files, found: {new_files}"


@pytest.mark.skipif(not REAL_DB_PATH.exists(), reason="canonical DB fixture not present in this checkout")
def test_real_canonical_db_sha256_unchanged_after_read_only_bounded_read():
    import hashlib

    def _sha256(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    before = _sha256(REAL_DB_PATH)
    manager = DatabaseManager(db_path=str(REAL_DB_PATH), read_only=True)
    draws = manager.get_canonical_draws(lottery_type="BIG_LOTTO", limit=5)
    after = _sha256(REAL_DB_PATH)

    assert draws, "expected at least one canonical BIG_LOTTO draw"
    assert before == after, "bounded read-only read must not change the canonical DB file"


# ---------------------------------------------------------------------------
# Backward compatibility: default (read_only=False) behavior is unchanged
# ---------------------------------------------------------------------------

def test_default_manager_is_not_read_only_and_still_initializes_schema(tmp_path):
    db_path = tmp_path / "writable.db"
    db_path.touch()  # resolve_db_path requires the path to already exist as a regular file
    manager = DatabaseManager(db_path=str(db_path))
    assert manager._read_only is False
    manager._ensure_ready()
    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "draws" in tables
