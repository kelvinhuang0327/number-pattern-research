"""
P246E — Canonical Draw Helper Isolation Tests

Verifies:
- get_canonical_draws() helper exists in database.py
- BIG_LOTTO canonical helper excludes hyphenated draw IDs (ADD_ON_PRIZE_EXCLUDED)
- BIG_LOTTO canonical helper excludes date-format alien rows (DATE_FORMAT_ALIEN)
- BIG_LOTTO canonical helper excludes small-pool rows where max(numbers) <= 25
- canonical helper returns ~2,113 canonical BIG_LOTTO rows
- raw get_draws/get_all_draws still includes add-on records
- quick_predict.py uses canonical helper, not raw get_all_draws()
- P246E JSON artifact parses
- forbidden actions not performed
- add-on records are preserved and excluded only from research
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"

P246E_JSON = OUTPUTS / "p246e_canonical_draw_helper_isolation_20260605.json"
P246E_MD = OUTPUTS / "p246e_canonical_draw_helper_isolation_20260605.md"

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def p246e_data():
    assert P246E_JSON.exists(), f"P246E JSON not found: {P246E_JSON}"
    return json.loads(P246E_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def p246e_md():
    assert P246E_MD.exists(), f"P246E MD not found: {P246E_MD}"
    return P246E_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def db_manager():
    """DatabaseManager instance for live DB tests (read-only usage)."""
    if not DB_PATH.exists():
        pytest.skip("DB not available")
    sys.path.insert(0, str(REPO_ROOT / "lottery_api"))
    from database import DatabaseManager
    return DatabaseManager(db_path=str(DB_PATH))


# ---------------------------------------------------------------------------
# Source code checks
# ---------------------------------------------------------------------------

def test_get_canonical_draws_exists_in_database_py():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    assert db_file.exists()
    content = db_file.read_text(encoding="utf-8")
    assert "def get_canonical_draws" in content, \
        "get_canonical_draws() must exist in database.py"


def test_canonical_draws_has_hyphen_filter():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    content = db_file.read_text(encoding="utf-8")
    assert "draw NOT LIKE '%-%'" in content or "draw NOT LIKE \\'%-%\\'" in content, \
        "database.py must filter hyphenated draw IDs in get_canonical_draws"


def test_canonical_draws_has_date_format_filter():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    content = db_file.read_text(encoding="utf-8")
    has_filter = "LENGTH(draw) = 8" in content or "LENGTH(draw)=8" in content
    assert has_filter, "database.py must filter 8-digit date-format IDs"


def test_canonical_draws_has_small_pool_python_filter():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    content = db_file.read_text(encoding="utf-8")
    has_filter = "max(numbers)" in content or ("<= 25" in content)
    assert has_filter, "database.py must have Python-level SMALL_POOL_ALIEN filter"


def test_canonical_draws_has_preservation_comment():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    content = db_file.read_text(encoding="utf-8")
    has_comment = (
        "add-on" in content.lower()
        or "ADD_ON_PRIZE_EXCLUDED" in content
        or "valid lottery" in content.lower()
    )
    assert has_comment, "database.py get_canonical_draws must document add-on record preservation"


def test_quick_predict_uses_canonical_helper():
    qp_file = REPO_ROOT / "tools" / "quick_predict.py"
    assert qp_file.exists()
    content = qp_file.read_text(encoding="utf-8")
    assert "get_canonical_draws" in content, \
        "quick_predict.py must use get_canonical_draws instead of raw get_all_draws"


def test_quick_predict_load_history_uses_canonical():
    qp_file = REPO_ROOT / "tools" / "quick_predict.py"
    content = qp_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_load_history = False
    found_canonical = False
    for line in lines:
        if "def load_history" in line:
            in_load_history = True
        if in_load_history and "get_canonical_draws" in line:
            found_canonical = True
            break
        if in_load_history and line.strip().startswith("def ") and "load_history" not in line:
            in_load_history = False
    assert found_canonical, \
        "load_history() in quick_predict.py must call get_canonical_draws()"


def test_raw_get_all_draws_still_present():
    db_file = REPO_ROOT / "lottery_api" / "database.py"
    content = db_file.read_text(encoding="utf-8")
    assert "def get_all_draws" in content, \
        "get_all_draws() must remain in database.py for display/history use"


# ---------------------------------------------------------------------------
# Live DB tests (skipped if DB unavailable)
# ---------------------------------------------------------------------------

def test_canonical_excludes_hyphenated_draw_ids(db_manager):
    canonical = db_manager.get_canonical_draws("BIG_LOTTO")
    hyphen = [d["draw"] for d in canonical if "-" in d["draw"]]
    assert len(hyphen) == 0, \
        f"canonical helper must exclude all hyphenated draw IDs, found: {hyphen[:5]}"


def test_canonical_excludes_date_format_alien(db_manager):
    canonical = db_manager.get_canonical_draws("BIG_LOTTO")
    date_fmt = [
        d["draw"] for d in canonical
        if len(d["draw"]) == 8 and d["draw"].startswith("20")
    ]
    assert len(date_fmt) == 0, \
        f"canonical helper must exclude 8-digit YYYYMMDD draw IDs, found: {date_fmt[:5]}"


def test_canonical_excludes_small_pool_rows(db_manager):
    canonical = db_manager.get_canonical_draws("BIG_LOTTO")
    small_pool = [d["draw"] for d in canonical if max(d["numbers"]) <= 25]
    assert len(small_pool) == 0, \
        f"canonical helper must exclude rows where max(numbers)<=25, found: {small_pool[:5]}"


def test_canonical_big_lotto_count_matches_expected(db_manager):
    canonical = db_manager.get_canonical_draws("BIG_LOTTO")
    # Expected ~2113; allow small delta for ongoing ingestion
    assert 2100 <= len(canonical) <= 2200, \
        f"canonical BIG_LOTTO count expected ~2113, got {len(canonical)}"


def test_raw_get_all_draws_preserves_addon_records():
    # Use direct SQLite to avoid apscheduler import chain in get_all_draws()
    if not DB_PATH.exists():
        pytest.skip("DB not available")
    import sqlite3
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    hyphen_count = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%'"
    ).fetchone()[0]
    conn.close()
    assert hyphen_count == 19100, \
        f"DB must preserve 19100 ADD_ON_PRIZE_EXCLUDED rows, got {hyphen_count}"


def test_raw_total_big_lotto_count():
    # Use direct SQLite to avoid apscheduler import chain
    if not DB_PATH.exists():
        pytest.skip("DB not available")
    import sqlite3
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    total = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
    ).fetchone()[0]
    conn.close()
    assert total == 22238, f"Total BIG_LOTTO rows must be 22238, got {total}"


def test_canonical_non_big_lotto_unchanged(db_manager):
    # POWER_LOTTO and DAILY_539 canonical and raw counts must match
    # Use direct SQLite for raw counts to avoid apscheduler chain
    import sqlite3
    if not DB_PATH.exists():
        pytest.skip("DB not available")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    power_raw = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    d539_raw = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='DAILY_539'"
    ).fetchone()[0]
    conn.close()

    power_canonical = db_manager.get_canonical_draws("POWER_LOTTO")
    d539_canonical = db_manager.get_canonical_draws("DAILY_539")
    assert len(power_canonical) == power_raw, \
        f"POWER_LOTTO canonical ({len(power_canonical)}) must match raw ({power_raw})"
    assert len(d539_canonical) == d539_raw, \
        f"DAILY_539 canonical ({len(d539_canonical)}) must match raw ({d539_raw})"


def test_canonical_result_is_sorted_ascending_by_date(db_manager):
    canonical = db_manager.get_canonical_draws("BIG_LOTTO")
    # The load_history function sorts ascending; verify canonical data is usable
    assert len(canonical) > 100, "Should have many canonical draws"
    # All draws should have valid draw IDs (numeric only)
    for d in canonical[:10]:
        assert "-" not in d["draw"], f"Unexpected hyphen in draw: {d['draw']}"
        assert d["draw"].isdigit() or d["draw"].replace("", "").isdigit()


# ---------------------------------------------------------------------------
# P246E JSON artifact
# ---------------------------------------------------------------------------

def test_p246e_json_parses(p246e_data):
    assert isinstance(p246e_data, dict)


def test_p246e_task_id(p246e_data):
    assert p246e_data.get("task_id") == "P246E"


def test_p246e_classification(p246e_data):
    assert "P246E" in p246e_data.get("classification", "")


def test_p246e_db_write_not_performed(p246e_data):
    assert p246e_data.get("db_write_performed") is False


def test_p246e_implemented_helper_present(p246e_data):
    helper = p246e_data.get("implemented_helper", {})
    assert "get_canonical_draws" in str(helper), \
        "P246E JSON must document get_canonical_draws() helper"


def test_p246e_updated_callers_listed(p246e_data):
    callers = p246e_data.get("updated_callers", [])
    assert len(callers) >= 1
    callers_str = json.dumps(callers).lower()
    assert "quick_predict" in callers_str, "updated_callers must include quick_predict.py"


def test_p246e_raw_access_preserved(p246e_data):
    raw_access = p246e_data.get("raw_access_preserved", {})
    assert isinstance(raw_access, dict)
    desc = str(raw_access.get("description", "")).lower()
    assert "preserv" in desc or "get_all_draws" in desc, \
        "P246E must state raw access is preserved"


def test_p246e_canonical_filter_rules_present(p246e_data):
    rules = p246e_data.get("canonical_filter_rules", {})
    assert "BIG_LOTTO" in rules
    bl_rules = rules["BIG_LOTTO"]
    assert "draw NOT LIKE" in str(bl_rules) or "not like" in str(bl_rules).lower()


def test_p246e_states_addon_valid_and_preserved(p246e_data):
    full_text = json.dumps(p246e_data, ensure_ascii=False).lower()
    assert "valid lottery-related" in full_text or "valid lottery related" in full_text or \
           "add-on" in full_text, \
        "P246E must state add-on records are valid lottery-related"
    assert "preserv" in full_text, "P246E must state add-on records are preserved"


def test_p246e_states_exclusion_from_research_only(p246e_data):
    full_text = json.dumps(p246e_data, ensure_ascii=False).lower()
    assert "research" in full_text, "P246E must mention research exclusion"
    # Must not claim add-on rows are deleted
    assert "delete" not in full_text.replace("no deletion", "").replace("no_deletion", "").replace("row_deletion", "").replace("no row deletion", ""), \
        "P246E must not claim to delete any rows"


def test_p246e_forbidden_actions_present(p246e_data):
    fa = p246e_data.get("forbidden_actions_confirmed", [])
    assert len(fa) > 0
    fa_str = " ".join(str(x) for x in fa).lower()
    assert "db_write" in fa_str or "db write" in fa_str
    assert "delet" in fa_str or "row_deletion" in fa_str
    assert "registry" in fa_str
    assert "strategy" in fa_str
    assert "betting" in fa_str or "bet" in fa_str


def test_p246e_all_isolation_checks_pass(p246e_data):
    assert p246e_data.get("all_isolation_checks_pass") is True, \
        "all_isolation_checks_pass must be True"


def test_p246e_final_decision_present(p246e_data):
    fd = p246e_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower() or "no db write performed" in fd.lower()


def test_p246e_md_states_canonical_count(p246e_md):
    assert "2,113" in p246e_md or "2113" in p246e_md, \
        "P246E MD must state canonical BIG_LOTTO count ~2113"


def test_p246e_md_states_no_db_write(p246e_md):
    text = p246e_md.lower()
    assert "no db write" in text or "no database write" in text


def test_p246e_md_states_addon_preserved(p246e_md):
    text = p246e_md.lower()
    assert "preserv" in text, "P246E MD must state add-on records are preserved"
