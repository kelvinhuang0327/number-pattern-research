"""Tests for P268D-2 structure-validation aggregate + read-only DB alignment.

These tests check the produced artifact (read-only). They do not re-run the
P268D-2 script's DB inspection themselves, do not write to the production DB,
and do not write to the production Hypothesis Registry.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "outputs" / "research"

OUTPUT_JSON = OUT_DIR / "p268d2_draw_order_structure_validation_db_alignment_20260610.json"
OUTPUT_MD = OUT_DIR / "p268d2_draw_order_structure_validation_db_alignment_20260610.md"
SCRIPT_PATH = REPO_ROOT / "analysis" / "p268d2_draw_order_structure_validation_db_alignment.py"
HYPOTHESIS_REGISTRY_PATH = REPO_ROOT / "lottery_api" / "data" / "hypothesis_registry.jsonl"

ALLOWED_FINAL_CLASSIFICATIONS = {
    "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_COMPLETE_READY_FOR_H1_DESIGN",
    "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_COMPLETE_DB_ALIGNMENT_PARTIAL",
    "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_BLOCKED_STATE_MISMATCH",
    "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_BLOCKED_ARTIFACT_MISSING",
    "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_BLOCKED_DB_SCHEMA_MISMATCH",
    "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_BLOCKED_SCOPE_CONFLICT",
}

ALLOWED_DB_ALIGNMENT_VERDICTS = {
    "PASS",
    "PARTIAL_ENV_LIMITATION",
    "FAIL_SCHEMA_MISMATCH",
    "FAIL_DATA_MISMATCH",
}

BANNED_TEST_EXECUTION_CLAIMS = [
    "p-value computed",
    "p value computed",
    "permutation test result",
    "confirmatory result",
]

BANNED_HIT_RATE_CLAIMS = [
    "hit-rate improved",
    "hit rate improved",
    "success rate improved",
    "validated edge",
    "proven edge",
]


@pytest.fixture(scope="module")
def artifact():
    assert OUTPUT_JSON.exists(), f"P268D2 artifact not found: {OUTPUT_JSON}"
    with open(OUTPUT_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def test_json_artifact_exists_and_valid(artifact):
    assert isinstance(artifact, dict)
    assert artifact.get("task_id") == "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_AND_READ_ONLY_DB_ALIGNMENT"


def test_markdown_artifact_exists():
    assert OUTPUT_MD.exists(), f"P268D2 markdown artifact not found: {OUTPUT_MD}"
    text = OUTPUT_MD.read_text(encoding="utf-8")
    assert "Structure Validation Summary" in text
    assert "Read-Only DB Alignment Summary" in text


def test_structure_validation_section_present(artifact):
    sv = artifact.get("structure_validation")
    assert isinstance(sv, dict)
    for key in [
        "records_checked",
        "expected_record_count",
        "record_count_matches_expected",
        "duplicate_key_count",
        "schema_drift_count",
        "ledger_pending_cells",
        "ledger_error_cells",
        "ledger_empty_cells",
        "ledger_done_cells",
        "parse_success_rate",
        "correct_length_rate",
    ]:
        assert key in sv, f"missing structure_validation key: {key}"
    assert sv["records_checked"] > 0


def test_db_alignment_section_present(artifact):
    db = artifact.get("db_alignment")
    assert isinstance(db, dict)
    for key in [
        "db_path",
        "opened_read_only",
        "tables_inspected",
        "rows_available_per_lottery",
        "matched_records_per_lottery",
        "unmatched_artifact_records",
        "unmatched_db_records",
        "date_range_overlap",
        "verdict",
    ]:
        assert key in db, f"missing db_alignment key: {key}"
    assert db["verdict"] in ALLOWED_DB_ALIGNMENT_VERDICTS


def test_read_only_db_mode_represented(artifact):
    db = artifact["db_alignment"]
    assert db.get("opened_read_only") is True
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "mode=ro" in source
    forbidden = ["INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE", "ALTER TABLE"]
    for token in forbidden:
        assert token not in source, f"Forbidden DB-write token found in script: {token!r}"


def test_no_db_write_claim(artifact):
    assert artifact.get("no_db_write") is True


def test_no_hypothesis_registry_write_claim(artifact):
    assert artifact.get("no_hypothesis_registry_write") is True
    if HYPOTHESIS_REGISTRY_PATH.exists():
        text = HYPOTHESIS_REGISTRY_PATH.read_text(encoding="utf-8")
        assert "P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_AND_READ_ONLY_DB_ALIGNMENT" not in text


def test_no_h1_h2_h3_test_run_this_task(artifact):
    assert artifact.get("no_h1_h2_h3_test_run_in_this_task") is True

    text_blob = json.dumps(artifact, ensure_ascii=False).lower()
    md_text = OUTPUT_MD.read_text(encoding="utf-8").lower()
    for claim in BANNED_TEST_EXECUTION_CLAIMS:
        assert claim not in text_blob, f"Banned statistical-test claim found in JSON: {claim!r}"
        assert claim not in md_text, f"Banned statistical-test claim found in markdown: {claim!r}"


def test_no_hit_rate_improvement_claim(artifact):
    assert artifact.get("no_hit_rate_claim") is True
    text_blob = json.dumps(artifact, ensure_ascii=False).lower()
    for claim in BANNED_HIT_RATE_CLAIMS:
        assert claim not in text_blob, f"Banned hit-rate claim found: {claim!r}"

    non_claims = artifact.get("explicit_non_claims", [])
    assert any("hit-rate" in c.lower() or "success-rate" in c.lower() for c in non_claims)


def test_data_quality_gate_verdict_allowed(artifact):
    gate = artifact.get("data_quality_gate")
    assert isinstance(gate, dict)
    assert "verdict" in gate
    assert "can_p268d3_proceed" in gate
    if gate["can_p268d3_proceed"]:
        assert gate.get("p268d3_allowed_next_scope")
    else:
        assert gate.get("blocker")


def test_final_classification_is_allowed(artifact):
    assert artifact.get("final_classification") in ALLOWED_FINAL_CLASSIFICATIONS
