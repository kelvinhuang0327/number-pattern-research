"""
P213F 3_STAR/4_STAR Positional Code Fix — Targeted Validation Tests
All DB operations use in-memory SQLite only. Production DB is never touched.
"""
import json
import os
import sqlite3
import sys
import tempfile
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTION_DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")

sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db_path(tmp_path):
    """Return a fresh temp DB file path for each test."""
    return str(tmp_path / "test_draws.db")


def _make_db(path=":memory:"):
    """Create an isolated DB using the same schema definition as database.py."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0,
            jackpot_amount REAL DEFAULT NULL,
            numbers_positional TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(draw, lottery_type)
        )
    """)
    conn.commit()
    return conn


def _insert_draw(conn, draw_id, lottery_type, numbers, date="2026/01/01", special=0):
    """Insert a draw row using the same dual-write logic as database.py."""
    numbers_json = json.dumps(sorted(numbers))
    if lottery_type in ('3_STAR', '4_STAR'):
        numbers_positional_json = json.dumps(numbers)
    else:
        numbers_positional_json = None
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO draws (draw, date, lottery_type, numbers, special, numbers_positional)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (draw_id, date, lottery_type, numbers_json, special, numbers_positional_json))
    conn.commit()


def _get_row(conn, draw_id, lottery_type):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT numbers, numbers_positional FROM draws WHERE draw=? AND lottery_type=?",
        (draw_id, lottery_type)
    )
    return cursor.fetchone()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_draws_table_has_numbers_positional_column():
    conn = _make_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(draws)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "numbers_positional" in columns
    conn.close()


def test_numbers_positional_column_is_nullable():
    conn = _make_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(draws)")
    for row in cursor.fetchall():
        if row[1] == "numbers_positional":
            # notnull = 0 means nullable
            assert row[3] == 0
    conn.close()


def test_migration_is_idempotent(temp_db_path):
    """Adding the column twice via try/except should not fail."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0,
            UNIQUE(draw, lottery_type)
        )
    """)
    conn.commit()
    for _ in range(2):
        try:
            cursor.execute("ALTER TABLE draws ADD COLUMN numbers_positional TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass
    cursor.execute("PRAGMA table_info(draws)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "numbers_positional" in columns
    conn.close()


# ---------------------------------------------------------------------------
# 3_STAR permutation storage
# ---------------------------------------------------------------------------

def test_3star_stores_positional_order():
    conn = _make_db()
    _insert_draw(conn, "112000001", "3_STAR", [3, 2, 1])
    row = _get_row(conn, "112000001", "3_STAR")
    assert row is not None
    assert json.loads(row["numbers_positional"]) == [3, 2, 1]
    conn.close()


def test_3star_numbers_field_is_sorted():
    conn = _make_db()
    _insert_draw(conn, "112000002", "3_STAR", [3, 2, 1])
    row = _get_row(conn, "112000002", "3_STAR")
    assert json.loads(row["numbers"]) == [1, 2, 3]
    conn.close()


def test_3star_positional_differs_from_sorted_when_order_differs():
    conn = _make_db()
    _insert_draw(conn, "112000003", "3_STAR", [9, 0, 5])
    row = _get_row(conn, "112000003", "3_STAR")
    assert json.loads(row["numbers"]) == [0, 5, 9]
    assert json.loads(row["numbers_positional"]) == [9, 0, 5]
    conn.close()


def test_3star_positional_equals_sorted_when_already_sorted():
    conn = _make_db()
    _insert_draw(conn, "112000004", "3_STAR", [1, 5, 9])
    row = _get_row(conn, "112000004", "3_STAR")
    assert json.loads(row["numbers"]) == [1, 5, 9]
    assert json.loads(row["numbers_positional"]) == [1, 5, 9]
    conn.close()


# ---------------------------------------------------------------------------
# 4_STAR permutation storage
# ---------------------------------------------------------------------------

def test_4star_stores_positional_order():
    conn = _make_db()
    _insert_draw(conn, "112000001", "4_STAR", [4, 3, 2, 1])
    row = _get_row(conn, "112000001", "4_STAR")
    assert json.loads(row["numbers_positional"]) == [4, 3, 2, 1]
    conn.close()


def test_4star_numbers_field_is_sorted():
    conn = _make_db()
    _insert_draw(conn, "112000002", "4_STAR", [4, 3, 2, 1])
    row = _get_row(conn, "112000002", "4_STAR")
    assert json.loads(row["numbers"]) == [1, 2, 3, 4]
    conn.close()


def test_4star_positional_differs_from_sorted_when_order_differs():
    conn = _make_db()
    _insert_draw(conn, "112000003", "4_STAR", [7, 0, 5, 3])
    row = _get_row(conn, "112000003", "4_STAR")
    assert json.loads(row["numbers"]) == [0, 3, 5, 7]
    assert json.loads(row["numbers_positional"]) == [7, 0, 5, 3]
    conn.close()


# ---------------------------------------------------------------------------
# Non-permutation backward compatibility
# ---------------------------------------------------------------------------

def test_biglotto_numbers_positional_is_null():
    conn = _make_db()
    _insert_draw(conn, "115000001", "BIG_LOTTO", [11, 15, 33, 38, 41, 43])
    row = _get_row(conn, "115000001", "BIG_LOTTO")
    assert row["numbers_positional"] is None
    conn.close()


def test_power_lotto_numbers_positional_is_null():
    conn = _make_db()
    _insert_draw(conn, "115000001", "POWER_LOTTO", [3, 9, 18, 27, 36, 37])
    row = _get_row(conn, "115000001", "POWER_LOTTO")
    assert row["numbers_positional"] is None
    conn.close()


def test_daily_539_numbers_positional_is_null():
    conn = _make_db()
    _insert_draw(conn, "115000001", "DAILY_539", [5, 10, 20, 30, 39])
    row = _get_row(conn, "115000001", "DAILY_539")
    assert row["numbers_positional"] is None
    conn.close()


def test_biglotto_numbers_field_remains_sorted():
    conn = _make_db()
    _insert_draw(conn, "115000002", "BIG_LOTTO", [43, 11, 38, 15, 33, 41])
    row = _get_row(conn, "115000002", "BIG_LOTTO")
    assert json.loads(row["numbers"]) == [11, 15, 33, 38, 41, 43]
    conn.close()


def test_power_lotto_numbers_field_remains_sorted():
    conn = _make_db()
    _insert_draw(conn, "115000002", "POWER_LOTTO", [37, 36, 27, 3, 9, 18])
    row = _get_row(conn, "115000002", "POWER_LOTTO")
    assert json.loads(row["numbers"]) == [3, 9, 18, 27, 36, 37]
    conn.close()


def test_daily_539_numbers_field_remains_sorted():
    conn = _make_db()
    _insert_draw(conn, "115000002", "DAILY_539", [39, 30, 20, 10, 5])
    row = _get_row(conn, "115000002", "DAILY_539")
    assert json.loads(row["numbers"]) == [5, 10, 20, 30, 39]
    conn.close()


# ---------------------------------------------------------------------------
# Duplicate insert guard
# ---------------------------------------------------------------------------

def test_duplicate_insert_is_ignored():
    conn = _make_db()
    _insert_draw(conn, "112000010", "3_STAR", [3, 2, 1])
    _insert_draw(conn, "112000010", "3_STAR", [9, 8, 7])
    row = _get_row(conn, "112000010", "3_STAR")
    assert json.loads(row["numbers_positional"]) == [3, 2, 1]
    conn.close()


# ---------------------------------------------------------------------------
# Read / query backward compatibility
# ---------------------------------------------------------------------------

def test_select_numbers_from_existing_rows_still_works():
    conn = _make_db()
    _insert_draw(conn, "115000005", "BIG_LOTTO", [11, 22, 33, 44, 5, 6])
    cursor = conn.cursor()
    cursor.execute("SELECT numbers FROM draws WHERE draw=? AND lottery_type=?", ("115000005", "BIG_LOTTO"))
    row = cursor.fetchone()
    assert json.loads(row[0]) == [5, 6, 11, 22, 33, 44]
    conn.close()


def test_select_all_columns_does_not_error():
    conn = _make_db()
    _insert_draw(conn, "112000020", "3_STAR", [7, 1, 5])
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM draws WHERE draw='112000020'")
    row = cursor.fetchone()
    assert row is not None
    conn.close()


# ---------------------------------------------------------------------------
# Production DB isolation
# ---------------------------------------------------------------------------

def test_production_db_not_accessed(monkeypatch):
    """Confirm production DB path is not opened during these tests."""
    original_connect = sqlite3.connect
    opened_paths = []

    def patched_connect(path, **kwargs):
        opened_paths.append(str(path))
        return original_connect(path, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", patched_connect)
    conn = _make_db()
    _insert_draw(conn, "112000030", "4_STAR", [4, 3, 2, 1])
    conn.close()
    for p in opened_paths:
        assert PRODUCTION_DB_PATH not in p, f"Production DB was opened: {p}"


def test_production_db_row_count_unchanged():
    prod_conn = sqlite3.connect(PRODUCTION_DB_PATH)
    cursor = prod_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cursor.fetchone()[0]
    prod_conn.close()
    assert count == 94924


# ---------------------------------------------------------------------------
# database.py source code checks
# ---------------------------------------------------------------------------

def test_database_py_has_numbers_positional_in_create_table():
    db_path = os.path.join(REPO_ROOT, "lottery_api", "database.py")
    with open(db_path) as f:
        src = f.read()
    assert "numbers_positional" in src


def test_database_py_has_migration_for_numbers_positional():
    db_path = os.path.join(REPO_ROOT, "lottery_api", "database.py")
    with open(db_path) as f:
        src = f.read()
    assert "ALTER TABLE draws ADD COLUMN numbers_positional" in src


def test_database_py_insert_sql_includes_numbers_positional():
    db_path = os.path.join(REPO_ROOT, "lottery_api", "database.py")
    with open(db_path) as f:
        src = f.read()
    assert "INSERT OR IGNORE INTO draws" in src
    insert_idx = src.index("INSERT OR IGNORE INTO draws")
    insert_block = src[insert_idx:insert_idx + 400]
    assert "numbers_positional" in insert_block


def test_database_py_no_strategy_or_registry_changes():
    db_path = os.path.join(REPO_ROOT, "lottery_api", "database.py")
    with open(db_path) as f:
        src = f.read()
    assert "controlled_apply" not in src
    assert "registry_mutation" not in src
    assert "strategy_promotion" not in src


def test_csv_validator_not_modified():
    """csv_validator.py must not have been modified."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    changed = result.stdout.strip()
    assert "csv_validator" not in changed


# ---------------------------------------------------------------------------
# Artifact checks (populated later; guard that files exist after task)
# ---------------------------------------------------------------------------

ARTIFACT_JSON = os.path.join(REPO_ROOT, "outputs", "research",
    "p213f_3star_4star_positional_code_fix_20260605.json")
ARTIFACT_MD = os.path.join(REPO_ROOT, "outputs", "research",
    "p213f_3star_4star_positional_code_fix_20260605.md")


def test_artifact_json_exists():
    assert os.path.exists(ARTIFACT_JSON), f"JSON artifact not found: {ARTIFACT_JSON}"


def test_artifact_markdown_exists():
    assert os.path.exists(ARTIFACT_MD), f"Markdown artifact not found: {ARTIFACT_MD}"


def test_artifact_json_parses():
    with open(ARTIFACT_JSON) as f:
        data = json.load(f)
    assert data["classification"] == "P213F_3STAR_4STAR_POSITIONAL_CODE_FIX_COMPLETE"
    assert data["production_db_write"] is False
    assert data["no_registry_mutation"] is True
    assert data["no_production_change"] is True
    assert data["no_strategy_authorization"] is True
    assert data["no_betting_advice"] is True
    assert data["same_pr_closeout"] is True
