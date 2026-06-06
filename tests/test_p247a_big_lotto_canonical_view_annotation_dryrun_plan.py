"""P247A — BIG_LOTTO Canonical DB Separation Dry-run Plan Tests"""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "research"
P247A_JSON = OUTPUTS / "p247a_big_lotto_canonical_view_annotation_dryrun_plan_20260606.json"
P247A_MD = OUTPUTS / "p247a_big_lotto_canonical_view_annotation_dryrun_plan_20260606.md"


@pytest.fixture(scope="session")
def p247a_data():
    assert P247A_JSON.exists(), f"P247A JSON not found: {P247A_JSON}"
    return json.loads(P247A_JSON.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def p247a_md():
    assert P247A_MD.exists(), f"P247A MD not found: {P247A_MD}"
    return P247A_MD.read_text(encoding="utf-8")


# Structure
def test_p247a_json_parses(p247a_data): assert isinstance(p247a_data, dict)
def test_p247a_task_id(p247a_data): assert p247a_data.get("task_id") == "P247A"
def test_p247a_classification(p247a_data): assert "P247A" in p247a_data.get("classification", "")
def test_p247a_p246k_pr_mentioned(p247a_data): assert "326" in str(p247a_data.get("p246k_merged_pr", ""))


# Read-only confirmed
def test_p247a_read_only_confirmed(p247a_data): assert p247a_data.get("read_only_confirmed") is True
def test_p247a_db_write_not_performed(p247a_data): assert p247a_data.get("db_write_performed") is False
def test_p247a_sql_not_applied(p247a_data): assert p247a_data.get("sql_applied") is False
def test_p247a_sql_dry_run_only(p247a_data): assert p247a_data.get("sql_dry_run_only") is True


# Raw and canonical counts distinct
def test_p247a_raw_count_22238(p247a_data):
    assert p247a_data.get("raw_population_count") == 22238

def test_p247a_canonical_count_2113(p247a_data):
    canonical = p247a_data.get("canonical_population_count")
    assert 2100 <= canonical <= 2200, f"expected ~2113, got {canonical}"

def test_p247a_counts_distinct(p247a_data):
    assert p247a_data.get("raw_population_count") != p247a_data.get("canonical_population_count")


# Dry-run validation
def test_p247a_dry_run_matches_expected(p247a_data):
    v = p247a_data.get("dry_run_validation", {})
    assert v.get("dry_run_matches_expected") is True

def test_p247a_dry_run_canonical_count(p247a_data):
    v = p247a_data.get("dry_run_validation", {})
    assert v.get("canonical_view_dry_run_count") == 2113

def test_p247a_row_family_counts_sum(p247a_data):
    rfc = p247a_data.get("row_family_counts", {})
    total = rfc.get("BIG_LOTTO_total", 0)
    addon = rfc.get("ADD_ON_PRIZE_EXCLUDED", 0)
    date_fmt = rfc.get("DATE_FORMAT_ALIEN", 0)
    sp = rfc.get("SMALL_POOL_ALIEN", 0)
    canon = rfc.get("CANONICAL_MAIN_DRAW_dry_run", 0)
    assert addon + date_fmt + sp + canon == total, "Row family counts must sum to total"


# Proposed SQL strings exist but not applied
def test_p247a_proposed_view_sql_exists(p247a_data):
    sql = p247a_data.get("proposed_view_sql", "")
    assert "CREATE VIEW" in sql
    assert "draws_big_lotto_canonical_main" in sql

def test_p247a_proposed_annotation_table_sql_exists(p247a_data):
    sql = p247a_data.get("proposed_annotation_table_sql", "")
    assert "CREATE TABLE" in sql
    assert "draw_row_family_annotations" in sql

def test_p247a_canonical_view_not_in_db():
    """Verify the view was not actually created in the DB."""
    db_path = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.exists():
        pytest.skip("DB not available")
    import sqlite3
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    views = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()]
    conn.close()
    assert "draws_big_lotto_canonical_main" not in views, \
        "Canonical view must NOT exist in DB (dry-run only)"

def test_p247a_annotation_table_not_in_db():
    """Verify the annotation table was not actually created."""
    db_path = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.exists():
        pytest.skip("DB not available")
    import sqlite3
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()
    assert "draw_row_family_annotations" not in tables, \
        "Annotation table must NOT exist in DB (dry-run only)"


# Forbidden actions
def test_p247a_forbidden_actions_present(p247a_data):
    fa = p247a_data.get("forbidden_actions_confirmed", [])
    fa_str = " ".join(fa).lower()
    assert "db_write" in fa_str or "create_view" in fa_str
    assert "delet" in fa_str
    assert "registry" in fa_str
    assert "strategy" in fa_str
    assert "betting" in fa_str or "bet" in fa_str


# Required Type D authorization phrase
def test_p247a_type_d_authorization_phrase_present(p247a_data):
    phrase = str(p247a_data.get("required_type_d_authorization_phrase", "")).lower()
    assert len(phrase) > 10
    assert "type d" in phrase or "explicit" in phrase


# Add-on records preserved
def test_p247a_addon_records_preserved(p247a_data):
    addon_status = p247a_data.get("add_on_records_status", {})
    assert addon_status.get("preserved") is True
    assert addon_status.get("is_fake") is False

def test_p247a_md_no_db_write(p247a_md): assert "no db write" in p247a_md.lower()
def test_p247a_md_no_create_view_executed(p247a_md):
    text = p247a_md.lower()
    assert "no create view" in text or "not executed" in text or "dry-run only" in text
def test_p247a_md_addon_preserved(p247a_md): assert "preserved" in p247a_md.lower()
def test_p247a_md_no_deletion(p247a_md): assert "no deletion" in p247a_md.lower() or "no row deletion" in p247a_md.lower()


# Script
def test_p247a_script_importable():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p247a", REPO_ROOT / "analysis" / "p247a_big_lotto_canonical_view_annotation_dryrun_plan.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "run_dryrun_plan")
    assert hasattr(mod, "PROPOSED_VIEW_SQL")
    assert hasattr(mod, "PROPOSED_ANNOTATION_TABLE_SQL")

def test_p247a_run_dryrun_no_write():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p247a", REPO_ROOT / "analysis" / "p247a_big_lotto_canonical_view_annotation_dryrun_plan.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.run_dryrun_plan()
    assert result["db_write_performed"] is False
    assert result["sql_applied"] is False
    v = result.get("dry_run_validation", {})
    assert v.get("dry_run_matches_expected") is True
    assert v.get("canonical_view_dry_run_count") == 2113

def test_p247a_final_decision_present(p247a_data):
    fd = p247a_data.get("final_decision", "")
    assert len(fd) > 50
    assert "no db write" in fd.lower() or "no create" in fd.lower()
