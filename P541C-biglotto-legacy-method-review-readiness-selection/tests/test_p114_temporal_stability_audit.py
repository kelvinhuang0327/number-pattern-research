"""
tests/test_p114_temporal_stability_audit.py

Test suite for P114: Temporal Stability Audit.
All tests are read-only. No DB writes. No strategy promotion.
"""

import json
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "replay" / "p114_temporal_stability_audit_20260527.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p114_temporal_stability_audit_20260527.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "p114_temporal_stability_audit.py"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_TASK_ID = "P114_TEMPORAL_STABILITY_AUDIT"

VALID_CLASSIFICATIONS = {
    "P114_TEMPORAL_STABILITY_AUDIT_READY",
    "P114_TEMPORAL_STABILITY_AUDIT_PARTIAL",
    "P114_TEMPORAL_STABILITY_AUDIT_INCONCLUSIVE",
    "P114_BLOCKED_BY_PREFLIGHT",
    "P114_BLOCKED_BY_DB_DRIFT",
    "P114_BLOCKED_BY_GUARD_FAILURE",
    "P114_BLOCKED_BY_TEST_FAILURE",
    "P114_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P114_BLOCKED_BY_SCOPE_VIOLATION",
    "P114_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

ALLOWED_STABILITY_LABELS = {
    "STABLE_POSITIVE",
    "MOSTLY_POSITIVE",
    "MIXED",
    "UNSTABLE",
    "STABLE_NEGATIVE",
    "INSUFFICIENT_WINDOW_DATA",
}

ALLOWED_P114_DECISIONS = {
    "READY_FOR_OOS_MONITORING_DESIGN",
    "READY_FOR_CONTROLLED_OBSERVATION_PLAN",
    "HOLD_FOR_ADDITIONAL_STABILITY_EVIDENCE",
    "KEEP_IN_OBSERVATION_AND_RETEST",
    "READY_FOR_QUARANTINE_GOVERNANCE",
    "HOLD_FOR_MORE_DATA",
    "NO_ACTION",
}

SQL_WRITE_VERBS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE|VACUUM|PRAGMA\s+writable_schema)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Fixture: load the JSON artifact once per session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def artifact():
    assert JSON_PATH.exists(), f"JSON artifact not found: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def md_content():
    assert MD_PATH.exists(), f"MD artifact not found: {MD_PATH}"
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def script_content():
    assert SCRIPT_PATH.exists(), f"Script not found: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------


def test_json_artifact_exists():
    assert JSON_PATH.exists()


def test_md_artifact_exists():
    assert MD_PATH.exists()


def test_script_exists():
    assert SCRIPT_PATH.exists()


# ---------------------------------------------------------------------------
# 2. JSON parse validity
# ---------------------------------------------------------------------------


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


# ---------------------------------------------------------------------------
# 3. Top-level required fields
# ---------------------------------------------------------------------------


def test_task_id(artifact):
    assert artifact["task_id"] == EXPECTED_TASK_ID


def test_classification_valid(artifact):
    assert artifact["classification"] in VALID_CLASSIFICATIONS


def test_final_classification_valid(artifact):
    assert artifact["final_classification"] in VALID_CLASSIFICATIONS


def test_p112_reference_exists(artifact):
    assert "p112_reference" in artifact
    assert isinstance(artifact["p112_reference"], dict)
    assert "classification" in artifact["p112_reference"]
    assert "artifact_path" in artifact["p112_reference"]


def test_p113_reference_exists(artifact):
    assert "p113_reference" in artifact
    assert isinstance(artifact["p113_reference"], dict)
    assert "classification" in artifact["p113_reference"]
    assert "artifact_path" in artifact["p113_reference"]


# ---------------------------------------------------------------------------
# 4. Governance flags
# ---------------------------------------------------------------------------


def test_db_writes_false(artifact):
    assert artifact["db_writes"] is False


def test_replay_rows_before(artifact):
    assert artifact["replay_rows_before"] == EXPECTED_REPLAY_ROWS


def test_replay_rows_after(artifact):
    assert artifact["replay_rows_after"] == EXPECTED_REPLAY_ROWS


def test_replay_rows_unchanged(artifact):
    assert artifact["replay_rows_before"] == artifact["replay_rows_after"]


def test_no_strategy_promotion(artifact):
    assert artifact["no_strategy_promotion"] is True


def test_no_lifecycle_mutation(artifact):
    assert artifact["no_lifecycle_mutation"] is True


def test_no_registry_mutation(artifact):
    assert artifact["no_registry_mutation"] is True


def test_no_4star_backtest(artifact):
    assert artifact["no_4star_backtest"] is True


def test_no_special3_p108_rerun(artifact):
    assert artifact["no_special3_p108_rerun"] is True


def test_source_unknown_caveat_preserved(artifact):
    assert artifact["source_unknown_caveat_preserved"] is True


# ---------------------------------------------------------------------------
# 5. Audit scope
# ---------------------------------------------------------------------------


def test_audited_lottery_types_includes_power_lotto(artifact):
    assert "POWER_LOTTO" in artifact["audited_lottery_types"]


def test_audited_lottery_types_includes_daily_539(artifact):
    assert "DAILY_539" in artifact["audited_lottery_types"]


def test_audited_lottery_types_includes_big_lotto(artifact):
    assert "BIG_LOTTO" in artifact["audited_lottery_types"]


def test_audited_strategy_count_positive(artifact):
    assert artifact["audited_strategy_count"] >= 1


def test_audited_strategy_count_matches_p113(artifact):
    # P113 has 36 strategies
    assert artifact["audited_strategy_count"] == 36


# ---------------------------------------------------------------------------
# 6. Temporal window definitions
# ---------------------------------------------------------------------------


def test_temporal_window_definitions_exists(artifact):
    assert "temporal_window_definitions" in artifact
    assert isinstance(artifact["temporal_window_definitions"], dict)
    assert len(artifact["temporal_window_definitions"]) > 0


def test_temporal_window_definitions_has_thirds(artifact):
    wd = artifact["temporal_window_definitions"]
    assert "first_third" in wd
    assert "middle_third" in wd
    assert "last_third" in wd


# ---------------------------------------------------------------------------
# 7. per_strategy_temporal_results
# ---------------------------------------------------------------------------


def test_per_strategy_temporal_results_exists(artifact):
    assert "per_strategy_temporal_results" in artifact
    assert isinstance(artifact["per_strategy_temporal_results"], list)
    assert len(artifact["per_strategy_temporal_results"]) > 0


def test_every_result_has_strategy_id(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "strategy_id" in r, f"Missing strategy_id in {r}"
        assert r["strategy_id"]


def test_every_result_has_lottery_type(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "lottery_type" in r, f"Missing lottery_type in {r}"
        assert r["lottery_type"] in {"POWER_LOTTO", "DAILY_539", "BIG_LOTTO"}


def test_every_result_has_stability_label(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "stability_label" in r, f"Missing stability_label in {r}"


def test_every_stability_label_is_allowed(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert r["stability_label"] in ALLOWED_STABILITY_LABELS, (
            f"Invalid stability_label '{r['stability_label']}' for {r['strategy_id']}"
        )


def test_every_result_has_p114_decision(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "p114_decision" in r, f"Missing p114_decision in {r}"


def test_every_p114_decision_is_allowed(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert r["p114_decision"] in ALLOWED_P114_DECISIONS, (
            f"Invalid p114_decision '{r['p114_decision']}' for {r['strategy_id']}"
        )


def test_every_result_has_promotion_authorized_false(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "promotion_authorized" in r, f"Missing promotion_authorized in {r}"
        assert r["promotion_authorized"] is False, (
            f"promotion_authorized is True for {r['strategy_id']} — unauthorized!"
        )


def test_every_result_has_windows(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "windows" in r, f"Missing windows in {r}"
        assert isinstance(r["windows"], dict)


def test_every_result_has_rationale(artifact):
    for r in artifact["per_strategy_temporal_results"]:
        assert "rationale" in r
        assert r["rationale"]


# ---------------------------------------------------------------------------
# 8. Decision category lists
# ---------------------------------------------------------------------------


def test_oos_monitoring_candidates_exists(artifact):
    assert "oos_monitoring_candidates" in artifact
    assert isinstance(artifact["oos_monitoring_candidates"], list)


def test_controlled_observation_candidates_exists(artifact):
    assert "controlled_observation_candidates" in artifact
    assert isinstance(artifact["controlled_observation_candidates"], list)


def test_quarantine_governance_candidates_exists(artifact):
    assert "quarantine_governance_candidates" in artifact
    assert isinstance(artifact["quarantine_governance_candidates"], list)


def test_hold_for_more_data_candidates_exists(artifact):
    assert "hold_for_more_data_candidates" in artifact
    assert isinstance(artifact["hold_for_more_data_candidates"], list)


def test_limitations_exists(artifact):
    assert "limitations" in artifact
    assert isinstance(artifact["limitations"], list)
    assert len(artifact["limitations"]) > 0


# ---------------------------------------------------------------------------
# 9. Live DB invariant
# ---------------------------------------------------------------------------


def test_live_db_replay_rows_unchanged():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert rows == EXPECTED_REPLAY_ROWS, (
        f"Live DB replay rows={rows}, expected={EXPECTED_REPLAY_ROWS}"
    )


# ---------------------------------------------------------------------------
# 10. Script safety — no SQL write verbs
# ---------------------------------------------------------------------------


def test_script_no_sql_write_verbs(script_content):
    matches = SQL_WRITE_VERBS.findall(script_content)
    assert not matches, f"SQL write verbs found in script: {matches}"


def test_script_has_json_out_argument(script_content):
    assert "--json-out" in script_content


def test_script_uses_mode_ro(script_content):
    assert "mode=ro" in script_content


# ---------------------------------------------------------------------------
# 11. Markdown content checks
# ---------------------------------------------------------------------------


def test_md_no_promotion_authorization(md_content):
    # The MD must not claim promotion is authorized
    # It may say "NOT authorized" or "no_strategy_promotion" but must not say "promotion_authorized: true"
    assert "promotion_authorized: true" not in md_content.lower()
    assert "PROMOTION_AUTHORIZED: TRUE" not in md_content.upper()


def test_md_contains_p108_blocked(md_content):
    assert "P108" in md_content
    assert "BLOCKED" in md_content.upper() or "blocked" in md_content


def test_md_contains_4star_backtest_unauthorized(md_content):
    content_upper = md_content.upper()
    assert "4_STAR" in content_upper or "4STAR" in content_upper.replace("_", "")
    assert "NOT AUTHORIZED" in content_upper or "UNAUTHORIZED" in content_upper


def test_md_contains_final_classification(md_content):
    assert "P114_TEMPORAL_STABILITY_AUDIT_READY" in md_content or \
           "P114_TEMPORAL_STABILITY_AUDIT_PARTIAL" in md_content


def test_md_contains_project_context_lock(md_content):
    assert "PROJECT_CONTEXT_LOCK" in md_content


# ---------------------------------------------------------------------------
# 12. No DB files staged
# ---------------------------------------------------------------------------


def test_no_db_files_staged_in_current_commit():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip()
    forbidden_patterns = [".db", ".db-", ".wal", ".shm", "lottery_history"]
    for line in staged.splitlines():
        for pat in forbidden_patterns:
            assert pat not in line, f"Forbidden file staged: {line}"
