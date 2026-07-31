"""
P213G 3_STAR/4_STAR Dry-run Source Parser — Targeted Validation Tests
No production DB write. Parser is validated against format fixtures only.
"""
import json
import os
import sys
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

PRODUCTION_DB = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")
PARSER_SCRIPT = os.path.join(REPO_ROOT, "scripts", "p213g_3star_4star_dry_run_source_parser.py")
JSON_SUMMARY = os.path.join(REPO_ROOT, "outputs", "research",
    "p213g_3star_4star_dry_run_source_parser_validation_20260605.json")
MD_SUMMARY = os.path.join(REPO_ROOT, "outputs", "research",
    "p213g_3star_4star_dry_run_source_parser_validation_20260605.md")
ROWS_JSON = os.path.join(REPO_ROOT, "outputs", "research",
    "p213g_3star_4star_dry_run_source_parser_rows_20260605.json")

from scripts.p213g_3star_4star_dry_run_source_parser import (
    parse_source_content,
    run_dry_run,
    FIXTURE_3STAR,
    FIXTURE_4STAR,
    SOURCE_STATUS,
)

FORBIDDEN_PHRASES = [
    "prediction edge",
    "improved win rate",
    "production-ready",
    "strategy-ready",
    "recommended numbers",
    "recommended bet",
]


# ---------------------------------------------------------------------------
# Parser import
# ---------------------------------------------------------------------------

def test_parser_imports():
    assert callable(parse_source_content)
    assert callable(run_dry_run)


# ---------------------------------------------------------------------------
# 3_STAR parsing
# ---------------------------------------------------------------------------

def test_3star_fixture_parses_draw_order():
    f = FIXTURE_3STAR[0]
    r = parse_source_content(f["content"], "3_STAR")
    assert r["positional"] == [3, 2, 1]
    assert r["source_has_draw_order"] is True
    assert r["errors"] == []


def test_3star_fixture_sorted_canonical():
    f = FIXTURE_3STAR[0]
    r = parse_source_content(f["content"], "3_STAR")
    assert r["sorted_numbers"] == [1, 2, 3]


def test_3star_positional_preserved_when_different_from_sorted():
    f = FIXTURE_3STAR[2]
    r = parse_source_content(f["content"], "3_STAR")
    assert r["positional"] == [7, 1, 4]
    assert r["sorted_numbers"] == [1, 4, 7]
    assert r["positional"] != r["sorted_numbers"]


def test_3star_draw_id_extracted():
    f = FIXTURE_3STAR[0]
    r = parse_source_content(f["content"], "3_STAR")
    assert r["draw_id"] == "112000001"


def test_3star_date_extracted():
    f = FIXTURE_3STAR[0]
    r = parse_source_content(f["content"], "3_STAR")
    assert r["date"] == "112/01/01"


# ---------------------------------------------------------------------------
# 4_STAR parsing
# ---------------------------------------------------------------------------

def test_4star_fixture_parses_joined_draw_order():
    f = FIXTURE_4STAR[0]
    r = parse_source_content(f["content"], "4_STAR")
    assert r["positional"] == [4, 3, 2, 1]
    assert r["source_has_draw_order"] is True
    assert r["errors"] == []


def test_4star_fixture_sorted_canonical():
    f = FIXTURE_4STAR[0]
    r = parse_source_content(f["content"], "4_STAR")
    assert r["sorted_numbers"] == [1, 2, 3, 4]


def test_4star_draw_id_extracted():
    f = FIXTURE_4STAR[0]
    r = parse_source_content(f["content"], "4_STAR")
    assert r["draw_id"] == "112000001"


# ---------------------------------------------------------------------------
# Source provenance and draw order field
# ---------------------------------------------------------------------------

def test_source_has_draw_order_field():
    for f in FIXTURE_3STAR + FIXTURE_4STAR:
        r = parse_source_content(f["content"], f["lottery_type"])
        assert r["source_has_draw_order"] is True, f"Expected draw order for {f['source']}"


def test_all_fixtures_parse_without_errors():
    for f in FIXTURE_3STAR + FIXTURE_4STAR:
        r = parse_source_content(f["content"], f["lottery_type"])
        assert r["errors"] == [], f"Unexpected error in {f['source']}: {r['errors']}"


# ---------------------------------------------------------------------------
# Missing 開出順序
# ---------------------------------------------------------------------------

def test_missing_draw_order_field_reports_error():
    content = "112000001期\n開獎日期:112/01/01\n大小順序:1 2 3\n1 2 3"
    r = parse_source_content(content, "3_STAR")
    assert r["positional"] is None
    assert r["source_has_draw_order"] is False
    assert len(r["errors"]) > 0


# ---------------------------------------------------------------------------
# run_dry_run summary
# ---------------------------------------------------------------------------

def test_run_dry_run_all_fixtures_valid():
    result = run_dry_run(FIXTURE_3STAR + FIXTURE_4STAR)
    assert result["total"] == 5
    assert result["valid"] == 5
    assert result["invalid"] == 0


def test_run_dry_run_positional_matches():
    result = run_dry_run(FIXTURE_3STAR + FIXTURE_4STAR)
    for r in result["rows"]:
        assert r["positional_match"] is True, f"Positional mismatch: {r['source']}"


def test_run_dry_run_sorted_matches():
    result = run_dry_run(FIXTURE_3STAR + FIXTURE_4STAR)
    for r in result["rows"]:
        assert r["sorted_match"] is True, f"Sorted mismatch: {r['source']}"


# ---------------------------------------------------------------------------
# Source status
# ---------------------------------------------------------------------------

def test_source_status_is_mock_only():
    assert SOURCE_STATUS == "P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY"


# ---------------------------------------------------------------------------
# Parser script — no production DB writes
# ---------------------------------------------------------------------------

def test_parser_script_no_insert_or_update():
    with open(PARSER_SCRIPT) as f:
        src = f.read()
    lower = src.lower()
    for forbidden in ["insert into draws", "update draws", "alter table draws", "drop table draws"]:
        assert forbidden not in lower, f"Forbidden SQL found: {forbidden}"


def test_parser_script_no_registry_mutation():
    with open(PARSER_SCRIPT) as f:
        src = f.read()
    assert "controlled_apply" not in src
    assert "strategy_promotion" not in src
    assert "registry_mutation" not in src


def test_parser_script_no_strategy_output():
    with open(PARSER_SCRIPT) as f:
        src = f.read()
    assert "recommended_numbers" not in src
    assert "betting_advice" not in src


# ---------------------------------------------------------------------------
# Artifact checks
# ---------------------------------------------------------------------------

def test_json_summary_exists():
    assert os.path.exists(JSON_SUMMARY)


def test_markdown_summary_exists():
    assert os.path.exists(MD_SUMMARY)


def test_rows_json_exists():
    assert os.path.exists(ROWS_JSON)


def test_json_summary_parses():
    with open(JSON_SUMMARY) as f:
        data = json.load(f)
    assert data["classification"] in (
        "P213G_DRY_RUN_SOURCE_VALIDATION_COMPLETE",
        "P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY",
        "P213G_SOURCE_NOT_FOUND",
        "P213G_SOURCE_AMBIGUOUS_STOPPED",
        "P213G_BLOCKED_BY_SOURCE_ACCESS",
    )
    assert data["production_db_write"] is False
    assert data["no_registry_mutation"] is True
    assert data["no_production_change"] is True
    assert data["no_strategy_authorization"] is True
    assert data["no_betting_advice"] is True
    assert data["same_pr_closeout"] is True


def test_rows_json_parses():
    with open(ROWS_JSON) as f:
        data = json.load(f)
    assert data["dry_run_only"] is True
    assert data["production_db_write"] is False
    rows = data.get("parsed_rows", [])
    assert len(rows) > 0
    for r in rows:
        assert "positional" in r
        assert "sorted_numbers" in r
        assert "source_has_draw_order" in r


def test_markdown_no_forbidden_phrases():
    with open(MD_SUMMARY) as f:
        content = f.read().lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in content, f"Forbidden phrase in MD: '{phrase}'"


def test_json_summary_source_status_is_mock_only():
    with open(JSON_SUMMARY) as f:
        data = json.load(f)
    assert data.get("source_status") == "P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY"


def test_production_db_row_count_unchanged():
    import sqlite3
    conn = sqlite3.connect(PRODUCTION_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 94924
