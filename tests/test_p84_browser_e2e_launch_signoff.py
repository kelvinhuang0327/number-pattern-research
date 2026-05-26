"""
P84 Browser E2E Launch-Signoff Validation Tests
================================================
Phase: P84 — Browser E2E Stabilization / Launch-Readiness Signoff
Classification: P84_BROWSER_E2E_STABILIZED_LAUNCH_SIGNOFF_READY

Rules:
- No DB writes asserted
- replay_rows must remain exactly 46962
- max_draw must remain 115000041
- Browser E2E result must be documented
- launch_ready must be consistent with browser_e2e_result
- No DB-write instructions in MD artifact
"""

import json
import re
import sqlite3
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs" / "replay" / "p84_browser_e2e_launch_signoff_20260526.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "replay" / "p84_browser_e2e_launch_signoff_20260526.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
SMOKE_TEST = REPO_ROOT / "tests" / "test_replay_browser_smoke.py"


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_JSON.exists(), f"P84 JSON artifact not found: {ARTIFACT_JSON}"
    return json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))


# ── test_01 ─────────────────────────────────────────────────────────────────

def test_01_json_artifact_exists():
    """P84 JSON output artifact must exist."""
    assert ARTIFACT_JSON.exists(), f"Missing: {ARTIFACT_JSON}"


# ── test_02 ─────────────────────────────────────────────────────────────────

def test_02_md_artifact_exists():
    """P84 Markdown artifact must exist."""
    assert ARTIFACT_MD.exists(), f"Missing: {ARTIFACT_MD}"


# ── test_03 ─────────────────────────────────────────────────────────────────

def test_03_classification_correct(artifact):
    """JSON classification must be P84_BROWSER_E2E_STABILIZED_LAUNCH_SIGNOFF_READY."""
    assert artifact["classification"] == "P84_BROWSER_E2E_STABILIZED_LAUNCH_SIGNOFF_READY", (
        f"Unexpected classification: {artifact['classification']}"
    )


# ── test_04 ─────────────────────────────────────────────────────────────────

def test_04_no_db_writes(artifact):
    """db_writes must be false and replay_rows_inserted must be 0."""
    assert artifact["db_writes"] is False, "db_writes must be false"
    assert artifact["replay_rows_inserted"] == 0, "replay_rows_inserted must be 0"


# ── test_05 ─────────────────────────────────────────────────────────────────

def test_05_replay_rows_baseline(artifact):
    """baseline_metrics.replay_rows must be exactly 46962."""
    rows = artifact["baseline_metrics"]["replay_rows"]
    assert rows == 46962, f"Expected 46962 replay rows, got {rows}"


# ── test_06 ─────────────────────────────────────────────────────────────────

def test_06_max_draw_baseline(artifact):
    """baseline_metrics.power_lotto_max_draw must be exactly 115000041."""
    max_draw = artifact["baseline_metrics"]["power_lotto_max_draw"]
    assert max_draw == 115000041, f"Expected max_draw=115000041, got {max_draw}"


# ── test_07 ─────────────────────────────────────────────────────────────────

def test_07_p79_sentinel_ids(artifact):
    """P79 sentinel rows must have id=46961 and id=46962 with dry_run=0."""
    sentinels = artifact["baseline_metrics"]["p79_sentinel_rows"]
    ids = {s["id"] for s in sentinels}
    assert 46961 in ids, f"Sentinel id=46961 missing. Got: {ids}"
    assert 46962 in ids, f"Sentinel id=46962 missing. Got: {ids}"
    for s in sentinels:
        assert s["dry_run"] == 0, f"Sentinel id={s['id']} dry_run must be 0, got {s['dry_run']}"
        assert s["truth_level"] == "POWERLOTTO_DRAW_EXT_VERIFIED", (
            f"Sentinel id={s['id']} truth_level must be POWERLOTTO_DRAW_EXT_VERIFIED"
        )


# ── test_08 ─────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not DB_PATH.exists(), reason="lottery_v2.db not present")
def test_08_db_live_replay_rows():
    """Live DB must have exactly 46962 rows in strategy_prediction_replays."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        rows = cur.fetchone()[0]
    finally:
        conn.close()
    assert rows == 46962, f"Live DB replay rows = {rows}, expected 46962"


# ── test_09 ─────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not DB_PATH.exists(), reason="lottery_v2.db not present")
def test_09_db_live_max_draw():
    """Live DB POWER_LOTTO max target_draw in replay table must be 115000041."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(CAST(target_draw AS INTEGER)) FROM strategy_prediction_replays "
            "WHERE lottery_type='POWER_LOTTO'"
        )
        max_draw = cur.fetchone()[0]
    finally:
        conn.close()
    assert max_draw == 115000041, f"Live DB max target_draw = {max_draw}, expected 115000041"


# ── test_10 ─────────────────────────────────────────────────────────────────

def test_10_browser_e2e_result_documented(artifact):
    """browser_e2e_result must be documented as PASS, FLAKY, or FAIL."""
    result = artifact.get("browser_e2e_result")
    assert result in ("PASS", "FLAKY", "FAIL"), (
        f"browser_e2e_result must be PASS/FLAKY/FAIL, got: {result!r}"
    )
    # P84 target: PASS
    assert result == "PASS", f"P84 must achieve PASS for browser_e2e_result, got: {result}"


# ── test_11 ─────────────────────────────────────────────────────────────────

def test_11_launch_ready_consistent(artifact):
    """launch_ready must be true iff browser_e2e_result is PASS."""
    e2e = artifact.get("browser_e2e_result")
    launch = artifact.get("launch_ready")
    if e2e == "PASS":
        assert launch is True, "launch_ready must be true when browser_e2e_result=PASS"
    else:
        assert launch is False, f"launch_ready must be false when browser_e2e_result={e2e}"


# ── test_12 ─────────────────────────────────────────────────────────────────

def test_12_no_db_write_instructions_in_md():
    """Markdown artifact must not instruct or imply DB writes."""
    assert ARTIFACT_MD.exists(), "MD artifact missing"
    text = ARTIFACT_MD.read_text(encoding="utf-8")
    forbidden_patterns = [
        r"INSERT INTO",
        r"UPDATE.*SET",
        r"DELETE FROM",
        r"db_writes.*true",
        r"replay_rows_inserted.*[1-9]",
    ]
    for pattern in forbidden_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        assert not matches, (
            f"Forbidden DB-write instruction found in MD: pattern={pattern!r}, matches={matches}"
        )


# ── test_13 ─────────────────────────────────────────────────────────────────

def test_13_browser_e2e_root_cause_documented(artifact):
    """browser_e2e_root_cause must be a non-empty string."""
    rc = artifact.get("browser_e2e_root_cause", "")
    assert isinstance(rc, str) and len(rc) > 20, (
        f"browser_e2e_root_cause must be a non-empty description, got: {rc!r}"
    )


# ── test_14 ─────────────────────────────────────────────────────────────────

def test_14_browser_e2e_fix_summary_documented(artifact):
    """browser_e2e_fix_summary must be a non-empty string."""
    fs = artifact.get("browser_e2e_fix_summary", "")
    assert isinstance(fs, str) and len(fs) > 20, (
        f"browser_e2e_fix_summary must be a non-empty description, got: {fs!r}"
    )


# ── test_15 ─────────────────────────────────────────────────────────────────

def test_15_timeout_fix_in_smoke_test():
    """test_replay_browser_smoke.py must use timeout=15000 (not 5000) in wait_for_function."""
    assert SMOKE_TEST.exists(), f"Smoke test file missing: {SMOKE_TEST}"
    text = SMOKE_TEST.read_text(encoding="utf-8")
    # Must not have 5000ms timeouts
    assert "timeout=5000" not in text, (
        "Old timeout=5000 found in test_replay_browser_smoke.py — fix not applied"
    )
    # Must have 15000ms timeouts
    count_15000 = text.count("timeout=15000")
    assert count_15000 >= 3, (
        f"Expected at least 3 occurrences of timeout=15000, found {count_15000}"
    )


# ── test_16 ─────────────────────────────────────────────────────────────────

def test_16_launch_readiness_all_pass(artifact):
    """All 7 launch readiness checklist items must be PASS."""
    checklist = artifact.get("launch_readiness_checklist", [])
    assert len(checklist) >= 7, f"Expected 7+ checklist items, got {len(checklist)}"
    failed = [item for item in checklist if item.get("status") != "PASS"]
    assert not failed, (
        f"Launch readiness items not PASS: {[i['item'] for i in failed]}"
    )


# ── test_17 ─────────────────────────────────────────────────────────────────

def test_17_r01_resolved(artifact):
    """Risk R01 (browser_e2e) must be RESOLVED in risk_register."""
    risks = artifact.get("risk_register", [])
    r01 = next((r for r in risks if r.get("id") == "R01"), None)
    assert r01 is not None, "R01 not found in risk_register"
    assert r01["status"] == "RESOLVED", (
        f"R01 must be RESOLVED in P84, got: {r01['status']!r}"
    )


# ── test_18 ─────────────────────────────────────────────────────────────────

def test_18_phase_evidence_chain_complete(artifact):
    """phase_evidence must include P77C through P84."""
    phases = {e["phase"] for e in artifact.get("phase_evidence", [])}
    required = {"P77C", "P78", "P79", "P80", "P81", "P82", "P83", "P84"}
    missing = required - phases
    assert not missing, f"Missing phase evidence entries: {missing}"


# ── test_19 ─────────────────────────────────────────────────────────────────

def test_19_batch_a_coverage_100(artifact):
    """batch_a_coverage_pct must be 100.0."""
    pct = artifact["baseline_metrics"].get("batch_a_coverage_pct")
    assert pct == 100.0, f"batch_a_coverage_pct must be 100.0, got {pct}"


# ── test_20 ─────────────────────────────────────────────────────────────────

def test_20_operator_walkthrough_pass(artifact):
    """operator_walkthrough_result must be PASS."""
    result = artifact.get("operator_walkthrough_result")
    assert result == "PASS", (
        f"operator_walkthrough_result must be PASS, got: {result!r}"
    )
