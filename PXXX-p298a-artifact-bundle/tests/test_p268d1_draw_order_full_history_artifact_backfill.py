"""Tests for P268D-1 registry-freeze artifact + bounded-rate full-history backfill.

These tests check the produced artifacts (read-only). They do not re-fetch
external data, do not write to the production DB, and do not write to the
production Hypothesis Registry.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "outputs" / "research"

REGISTRY_FREEZE_JSON = OUT_DIR / "p268d1_draw_order_registry_freeze_20260610.json"
JSONL_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl"
LEDGER_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.ledger.json"
SUMMARY_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.summary.json"
MD_PATH = OUT_DIR / "p268d1_draw_order_full_history_artifact_backfill_20260610.md"
SCRIPT_PATH = REPO_ROOT / "analysis" / "p268d1_draw_order_full_history_artifact_backfill.py"
HYPOTHESIS_REGISTRY_PATH = REPO_ROOT / "lottery_api" / "data" / "hypothesis_registry.jsonl"
DB_PATH = REPO_ROOT / "data" / "lottery_v2.db"

ALLOWED_FINAL_CLASSIFICATIONS = {
    "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_COMPLETE",
    "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_PARTIAL_API_LIMIT",
    "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_BLOCKED_STATE_MISMATCH",
    "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_BLOCKED_EXTERNAL_API_UNAVAILABLE",
    "P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_BLOCKED_SCOPE_CONFLICT",
}

BANNED_CLAIMS = [
    "hit-rate improved",
    "hit rate improved",
    "success rate improved",
    "validated edge",
    "proven edge",
]

# Phrases that would indicate a confirmatory test was actually RUN (as
# opposed to merely being mentioned as out-of-scope / reserved-for-later).
BANNED_TEST_EXECUTION_CLAIMS = [
    "p-value computed",
    "p value computed",
    "permutation test result",
    "confirmatory result",
]


@pytest.fixture(scope="module")
def registry_freeze():
    assert REGISTRY_FREEZE_JSON.exists(), f"Registry-freeze artifact not found: {REGISTRY_FREEZE_JSON}"
    with open(REGISTRY_FREEZE_JSON, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def summary():
    assert SUMMARY_PATH.exists(), f"Summary artifact not found: {SUMMARY_PATH}"
    with open(SUMMARY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def ledger():
    assert LEDGER_PATH.exists(), f"Ledger artifact not found: {LEDGER_PATH}"
    with open(LEDGER_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_registry_freeze_artifact_exists_and_valid(registry_freeze):
    assert isinstance(registry_freeze, dict)
    assert registry_freeze.get("task_id") == "P268D1_DRAW_ORDER_REGISTRY_FREEZE_ARTIFACT"
    assert registry_freeze.get("type") == "REGISTRY_FREEZE_SNAPSHOT_ONLY"


def test_h1_h2_h3_present_in_freeze(registry_freeze):
    hypotheses = registry_freeze.get("hypotheses", [])
    ids = {h["id"] for h in hypotheses}
    assert "H1" in ids
    assert "H1_holdout" in ids
    assert "H2" in ids
    assert "H3" in ids
    for h in hypotheses:
        assert h.get("status") == "FROZEN_NOT_TESTED"


def test_production_hypothesis_registry_not_written(registry_freeze):
    note = registry_freeze.get("note", "").lower()
    assert "not written to" in note or "not a write to the production hypothesis registry" in note
    assert registry_freeze.get("no_hypothesis_registry_write") is True

    if HYPOTHESIS_REGISTRY_PATH.exists():
        text = HYPOTHESIS_REGISTRY_PATH.read_text(encoding="utf-8")
        assert "P268D1_DRAW_ORDER_REGISTRY_FREEZE_ARTIFACT" not in text
        for h in registry_freeze.get("hypotheses", []):
            assert f'"id": "{h["id"]}"' not in text


def test_production_db_not_written(registry_freeze, summary):
    assert registry_freeze.get("no_db_write") is True
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden = ["INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE", "ALTER TABLE", "sqlite3.connect", "sqlite3.Connection"]
    for token in forbidden:
        assert token not in source, f"Forbidden DB-write token found in script: {token!r}"


def test_jsonl_artifact_exists_and_records_valid():
    assert JSONL_PATH.exists(), f"JSONL artifact not found: {JSONL_PATH}"
    lines = JSONL_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 0
    for line in lines[:50]:
        rec = json.loads(line)
        assert "lottery_type" in rec
        assert "drawNumberAppear" in rec
        assert "validation" in rec
        assert "drawNumberAppear_present" in rec["validation"]


def test_ledger_exists_and_structured(ledger):
    assert "ledger" in ledger
    cells = ledger["ledger"]
    assert len(cells) > 0
    statuses = {c["status"] for c in cells}
    assert statuses <= {"PENDING", "DONE", "EMPTY", "ERROR"}
    assert ledger.get("start_month") == "2007-01"
    assert "max_calls_per_run" in ledger


def test_bounded_rate_represented(ledger, summary):
    max_calls = ledger.get("max_calls_per_run")
    assert isinstance(max_calls, int) and max_calls > 0
    this_run = summary.get("this_run", {})
    assert this_run.get("calls_made_this_run") <= max_calls
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "MAX_CALLS_PER_RUN" in source
    assert "TIMEOUT_SECONDS" in source


def test_no_h1_h2_h3_test_run_this_task(registry_freeze, summary):
    assert registry_freeze.get("no_h1_h2_h3_test_run_in_this_task") is True

    text_blob = json.dumps(summary, ensure_ascii=False).lower()
    for claim in BANNED_TEST_EXECUTION_CLAIMS:
        assert claim not in text_blob, f"Banned statistical-test claim found in summary: {claim!r}"

    md_text = MD_PATH.read_text(encoding="utf-8").lower()
    for claim in BANNED_TEST_EXECUTION_CLAIMS:
        assert claim not in md_text, f"Banned statistical-test claim found in markdown: {claim!r}"


def test_no_hit_rate_improvement_claim(registry_freeze, summary):
    for blob in (registry_freeze, summary):
        text_blob = json.dumps(blob, ensure_ascii=False).lower()
        for claim in ["hit-rate improved", "hit rate improved", "success rate improved", "validated edge", "proven edge"]:
            assert claim not in text_blob, f"Banned hit-rate claim found: {claim!r}"

    non_claims = registry_freeze.get("explicit_non_claims", [])
    assert any("hit-rate" in c.lower() or "success-rate" in c.lower() for c in non_claims)


def test_summary_required_fields_present(summary):
    assert "coverage" in summary
    coverage = summary["coverage"]
    for key in ["games", "start_month", "end_month", "total_ledger_cells", "done_cells", "pending_cells", "error_cells"]:
        assert key in coverage

    assert "missing_months_by_game" in summary
    assert "limitations" in summary and len(summary["limitations"]) > 0
    assert "next_step_recommendation" in summary
    assert "is_complete" in summary
    assert "overall_status" in summary


def test_final_classification_is_allowed(summary, registry_freeze):
    assert summary.get("final_classification") in ALLOWED_FINAL_CLASSIFICATIONS
    assert registry_freeze.get("final_classification") == "P268D1_DRAW_ORDER_REGISTRY_FREEZE_ARTIFACT_COMPLETE"
