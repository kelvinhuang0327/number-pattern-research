"""
P103 Special3 Source Acquisition Decision — Test Suite
Phase: P103
Classification expected: P103_SPECIAL3_SOURCE_ACQUISITION_DECISION_READY
Default recommendation: HOLD_AWAITING_USER_SOURCE
"""
import json
import os
import sqlite3
import pytest

ARTIFACT_JSON = "outputs/replay/special3_source_acquisition_decision_20260527.json"
ARTIFACT_MD   = "docs/replay/special3_source_acquisition_decision_20260527.md"
P102_ARTIFACT = "outputs/replay/special3_source_decision_audit_20260527.json"
DB_PATH       = "lottery_api/data/lottery_v2.db"

VALID_CLASSIFICATIONS = {
    "P103_SPECIAL3_SOURCE_ACQUISITION_DECISION_READY",
    "P103_SPECIAL3_SOURCE_ACQUISITION_DECISION_HOLD_AWAITING_USER_SOURCE",
}

REPLAY_ROWS_BASELINE   = 54462
POWER_LOTTO_MAX_DRAW   = 115000041
STAR3_MAX_DRAW         = 115000024


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# ── Test 01 ───────────────────────────────────────────────────────────────────
def test_01_json_artifact_exists_and_valid():
    """JSON artifact must exist and be valid JSON."""
    assert os.path.isfile(ARTIFACT_JSON), f"Missing: {ARTIFACT_JSON}"
    with open(ARTIFACT_JSON, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict), "Artifact must be a JSON object"
    assert data.get("phase") == "P103"


# ── Test 02 ───────────────────────────────────────────────────────────────────
def test_02_markdown_artifact_exists():
    """Markdown artifact must exist and be non-empty."""
    assert os.path.isfile(ARTIFACT_MD), f"Missing: {ARTIFACT_MD}"
    assert os.path.getsize(ARTIFACT_MD) > 500, "Markdown artifact too small"


# ── Test 03 ───────────────────────────────────────────────────────────────────
def test_03_classification_valid(artifact):
    """Classification must be a valid P103 classification string."""
    cls = artifact.get("classification", "")
    assert cls in VALID_CLASSIFICATIONS, (
        f"Invalid classification: {cls!r}. Must be one of {VALID_CLASSIFICATIONS}"
    )


# ── Test 04 ───────────────────────────────────────────────────────────────────
def test_04_p102_artifact_referenced(artifact):
    """P102 artifact must be referenced in the P103 JSON."""
    p102_ref = artifact.get("p102_artifact", "")
    assert p102_ref, "p102_artifact field must be present and non-empty"
    assert "special3_source_decision_audit" in p102_ref, (
        f"p102_artifact reference does not match expected pattern: {p102_ref!r}"
    )
    assert os.path.isfile(P102_ARTIFACT), f"P102 artifact file missing on disk: {P102_ARTIFACT}"


# ── Test 05 ───────────────────────────────────────────────────────────────────
def test_05_options_abc_exist(artifact):
    """Options A, B, and C must all appear in source_acquisition_options."""
    options = artifact.get("source_acquisition_options", [])
    assert len(options) >= 3, f"Expected >= 3 options, got {len(options)}"
    option_letters = [o.get("option") for o in options]
    for required in ["A", "B", "C"]:
        assert required in option_letters, (
            f"Option {required} missing from source_acquisition_options"
        )


# ── Test 06 ───────────────────────────────────────────────────────────────────
def test_06_default_recommendation_is_hold_without_source(artifact):
    """Default recommendation must be HOLD (Option C) without explicit source/authorization."""
    rec = artifact.get("default_recommendation", "")
    assert "HOLD" in rec.upper() or rec == "C", (
        f"Default recommendation must be HOLD-based without explicit source. Got: {rec!r}"
    )
    matrix = artifact.get("decision_matrix_summary", {})
    assert matrix.get("default_recommendation") in {"C", "HOLD", "HOLD_AWAITING_USER_SOURCE"}, (
        "decision_matrix_summary.default_recommendation must be C/HOLD"
    )


# ── Test 07 ───────────────────────────────────────────────────────────────────
def test_07_leading_zero_preservation_requirement(artifact):
    """Option A must explicitly state leading-zero preservation requirement."""
    options = artifact.get("source_acquisition_options", [])
    option_a = next((o for o in options if o.get("option") == "A"), None)
    assert option_a is not None, "Option A not found"
    a_str = json.dumps(option_a).lower()
    assert "leading" in a_str or "zero" in a_str, (
        "Option A must document leading-zero preservation requirement"
    )
    assert option_a.get("leading_zero_preservation") or "leading_zero" in a_str, (
        "leading_zero_preservation field must be present in Option A"
    )


# ── Test 08 ───────────────────────────────────────────────────────────────────
def test_08_no_db_writes(artifact):
    """governance_statements must declare no DB writes, no ingestion, no replay row inserts."""
    gov = artifact.get("governance_statements", {})
    assert gov.get("db_writes") is False, "db_writes must be false"
    assert gov.get("db_ingestion") is False, "db_ingestion must be false"
    assert gov.get("replay_row_inserts") is False, "replay_row_inserts must be false"


# ── Test 09 ───────────────────────────────────────────────────────────────────
def test_09_no_ingestion_flag(artifact):
    """All three options must declare ingestion=false at the option level."""
    options = artifact.get("source_acquisition_options", [])
    for opt in options:
        letter = opt.get("option")
        assert opt.get("ingestion_in_this_option") is False, (
            f"Option {letter} must declare ingestion_in_this_option=false"
        )


# ── Test 10 ───────────────────────────────────────────────────────────────────
def test_10_replay_rows_unchanged(db_conn):
    """Live DB replay rows must remain at governance baseline 54462."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == REPLAY_ROWS_BASELINE, (
        f"replay_rows changed: expected {REPLAY_ROWS_BASELINE}, got {count}"
    )


# ── Test 11 ───────────────────────────────────────────────────────────────────
def test_11_star4_remains_data_gap_blocking(artifact, db_conn):
    """4_STAR must remain DATA_GAP_BLOCKING — 0 draws in DB, artifact declares same."""
    star4_count = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert star4_count == 0, f"4_STAR draws != 0: got {star4_count}"
    assert artifact.get("special4_status") == "DATA_GAP_BLOCKING", (
        "special4_status must be DATA_GAP_BLOCKING"
    )
    assert artifact.get("governance_statements", {}).get("star4_backtest") is False, (
        "star4_backtest must be false"
    )


# ── Test 12 ───────────────────────────────────────────────────────────────────
def test_12_no_special3_production_promotion(artifact):
    """special3_production_promotion and strategy_promotion must both be false."""
    gov = artifact.get("governance_statements", {})
    assert gov.get("special3_production_promotion") is False, (
        "special3_production_promotion must be false"
    )
    assert gov.get("strategy_promotion") is False, (
        "strategy_promotion must be false"
    )


# ── Test 13 ───────────────────────────────────────────────────────────────────
def test_13_p104_recommendation_exists(artifact):
    """p104_recommendation must exist and reference all three options."""
    p104 = artifact.get("p104_recommendation", {})
    assert p104, "p104_recommendation must be present and non-empty"
    p104_str = json.dumps(p104).lower()
    assert "option" in p104_str or "p104" in p104_str, (
        "p104_recommendation must reference P104 paths"
    )
    # All three option references should be present
    assert "a" in p104 or "if_option_a" in p104, "p104_recommendation must cover Option A"
    assert "b" in p104 or "if_option_b" in p104, "p104_recommendation must cover Option B"
    assert "c" in p104 or "if_option_c" in p104, "p104_recommendation must cover Option C"


# ── Test 14 ───────────────────────────────────────────────────────────────────
def test_14_live_db_star3_max_draw_unchanged(db_conn):
    """Live DB 3_STAR max draw must remain 115000024."""
    row = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)), COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()
    max_draw, count = row
    assert max_draw == STAR3_MAX_DRAW, (
        f"3_STAR max_draw changed: expected {STAR3_MAX_DRAW}, got {max_draw}"
    )
    assert count == 4115, f"3_STAR draw count changed: expected 4115, got {count}"


# ── Test 15 ───────────────────────────────────────────────────────────────────
def test_15_power_lotto_max_draw_unchanged(db_conn):
    """Live DB POWER_LOTTO max draw must remain 115000041."""
    max_draw = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    assert max_draw == POWER_LOTTO_MAX_DRAW, (
        f"POWER_LOTTO max_draw changed: expected {POWER_LOTTO_MAX_DRAW}, got {max_draw}"
    )
