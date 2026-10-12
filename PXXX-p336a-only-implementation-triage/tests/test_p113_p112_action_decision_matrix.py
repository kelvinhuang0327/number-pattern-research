"""
Tests for P113: P112 Action Decision Matrix
Read-only governance decision matrix. No DB writes, no promotion.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

BASE = Path(__file__).parent.parent
JSON_PATH = BASE / "outputs/replay/p113_p112_action_decision_matrix_20260527.json"
MD_PATH = BASE / "docs/replay/p113_p112_action_decision_matrix_20260527.md"
SCRIPT_PATH = BASE / "scripts/p113_p112_action_decision_matrix.py"
DB_PATH = BASE / "lottery_api/data/lottery_v2.db"

VALID_CLASSIFICATIONS = {
    "P113_P112_ACTION_DECISION_MATRIX_READY",
    "P113_P112_ACTION_DECISION_MATRIX_PARTIAL",
    "P113_P112_ACTION_DECISION_MATRIX_INCONCLUSIVE",
    "P113_BLOCKED_BY_PREFLIGHT",
    "P113_BLOCKED_BY_DB_DRIFT",
    "P113_BLOCKED_BY_GUARD_FAILURE",
    "P113_BLOCKED_BY_TEST_FAILURE",
    "P113_BLOCKED_BY_FORBIDDEN_FILES_STAGED",
    "P113_BLOCKED_BY_SCOPE_VIOLATION",
    "P113_BLOCKED_BY_CONTEXT_CONTAMINATION",
}

FORBIDDEN_SQL_VERBS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bCREATE\b",
    r"\bDROP\b", r"\bALTER\b", r"\bREPLACE\b", r"\bVACUUM\b",
    r"\bPRAGMA\s+writable_schema\b",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    return MD_PATH.read_text()


@pytest.fixture(scope="module")
def script_content():
    return SCRIPT_PATH.read_text()


# ── File existence ─────────────────────────────────────────────────────────────

def test_json_artifact_exists():
    assert JSON_PATH.exists(), f"Missing: {JSON_PATH}"


def test_md_artifact_exists():
    assert MD_PATH.exists(), f"Missing: {MD_PATH}"


def test_script_exists():
    assert SCRIPT_PATH.exists(), f"Missing: {SCRIPT_PATH}"


# ── JSON top-level fields ──────────────────────────────────────────────────────

def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_classification_valid(artifact):
    cls = artifact.get("classification")
    assert cls in VALID_CLASSIFICATIONS, f"Invalid classification: {cls}"


def test_classification_is_ready(artifact):
    assert artifact["classification"] == "P113_P112_ACTION_DECISION_MATRIX_READY"


def test_task_id(artifact):
    assert artifact["task_id"] == "P113_P112_ACTION_DECISION_MATRIX"


def test_final_classification_matches(artifact):
    assert artifact["final_classification"] == artifact["classification"]


# ── p112_reference ─────────────────────────────────────────────────────────────

def test_p112_reference_exists(artifact):
    assert "p112_reference" in artifact


def test_p112_classification(artifact):
    ref = artifact["p112_reference"]
    assert ref["classification"] == "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY"


def test_p112_audited_strategy_count(artifact):
    ref = artifact["p112_reference"]
    assert ref["audited_strategy_count"] >= 1


def test_p112_audited_lotteries_power_lotto(artifact):
    assert "POWER_LOTTO" in artifact["p112_reference"]["audited_lotteries"]


def test_p112_audited_lotteries_daily_539(artifact):
    assert "DAILY_539" in artifact["p112_reference"]["audited_lotteries"]


def test_p112_audited_lotteries_big_lotto(artifact):
    assert "BIG_LOTTO" in artifact["p112_reference"]["audited_lotteries"]


# ── Governance flags ───────────────────────────────────────────────────────────

def test_db_writes_false(artifact):
    assert artifact["db_writes"] is False


def test_replay_rows_before(artifact):
    assert artifact["replay_rows_before"] == 54462


def test_replay_rows_after(artifact):
    assert artifact["replay_rows_after"] == 54462


def test_replay_rows_before_equals_after(artifact):
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


# ── action_definitions ─────────────────────────────────────────────────────────

def test_action_definitions_exist(artifact):
    assert "action_definitions" in artifact


def test_action_definitions_watchlist_queue(artifact):
    assert "WATCHLIST_QUEUE" in artifact["action_definitions"]


def test_action_definitions_observation_queue(artifact):
    assert "OBSERVATION_QUEUE" in artifact["action_definitions"]


def test_action_definitions_demote_quarantine(artifact):
    assert "DEMOTE_OR_QUARANTINE_CANDIDATE" in artifact["action_definitions"]


def test_action_definitions_fallback_disclosure(artifact):
    assert "FALLBACK_DISCLOSURE_CANDIDATE" in artifact["action_definitions"]


# ── per_lottery_decision_matrix ────────────────────────────────────────────────

def test_per_lottery_decision_matrix_exists(artifact):
    assert "per_lottery_decision_matrix" in artifact


def test_per_lottery_power_lotto_present(artifact):
    assert "POWER_LOTTO" in artifact["per_lottery_decision_matrix"]


def test_per_lottery_daily_539_present(artifact):
    assert "DAILY_539" in artifact["per_lottery_decision_matrix"]


def test_per_lottery_big_lotto_present(artifact):
    assert "BIG_LOTTO" in artifact["per_lottery_decision_matrix"]


# ── per_strategy_action_matrix ─────────────────────────────────────────────────

def test_per_strategy_action_matrix_exists(artifact):
    assert "per_strategy_action_matrix" in artifact


def test_per_strategy_action_matrix_non_empty(artifact):
    assert len(artifact["per_strategy_action_matrix"]) > 0


def test_all_strategies_promotion_authorized_false(artifact):
    for s in artifact["per_strategy_action_matrix"]:
        assert s["promotion_authorized"] is False, (
            f"Strategy {s['strategy_id']} has promotion_authorized={s['promotion_authorized']}"
        )


def test_all_strategies_have_rationale(artifact):
    for s in artifact["per_strategy_action_matrix"]:
        assert s.get("rationale"), f"Missing rationale for {s['strategy_id']}"


def test_all_strategies_have_next_task_candidate(artifact):
    for s in artifact["per_strategy_action_matrix"]:
        assert s.get("next_task_candidate"), (
            f"Missing next_task_candidate for {s['strategy_id']}"
        )


def test_strategy_count_matches_p112(artifact):
    expected = artifact["p112_reference"]["audited_strategy_count"]
    actual = len(artifact["per_strategy_action_matrix"])
    assert actual == expected, f"Strategy count mismatch: {actual} != {expected}"


# ── wave_n_backlog ─────────────────────────────────────────────────────────────

def test_wave_n_backlog_exists(artifact):
    assert "wave_n_backlog" in artifact


def test_wave_n_backlog_non_empty(artifact):
    assert len(artifact["wave_n_backlog"]) > 0


# ── explicit_holds ─────────────────────────────────────────────────────────────

def test_explicit_holds_exist(artifact):
    assert "explicit_holds" in artifact


def test_explicit_holds_special3_p108(artifact):
    hold_ids = [h["hold_id"] for h in artifact["explicit_holds"]]
    assert "SPECIAL3_P108_HOLD" in hold_ids


def test_explicit_holds_four_star_backtest(artifact):
    hold_ids = [h["hold_id"] for h in artifact["explicit_holds"]]
    assert "FOUR_STAR_BACKTEST_HOLD" in hold_ids


def test_explicit_holds_no_production_promotion(artifact):
    hold_ids = [h["hold_id"] for h in artifact["explicit_holds"]]
    assert "NO_PRODUCTION_PROMOTION_FROM_P112_P113" in hold_ids


# ── Live DB invariant ──────────────────────────────────────────────────────────

def test_live_db_replay_rows():
    uri = DB_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert rows == 54462, f"replay_rows={rows} != 54462"


# ── Script safety ──────────────────────────────────────────────────────────────

def test_script_no_sql_write_verbs(script_content):
    # Exclude comment lines and docstrings when checking for write verbs
    non_comment_lines = [
        line for line in script_content.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith('"""')
        and not line.strip().startswith("'\"'\"'")
    ]
    code_text = "\n".join(non_comment_lines)
    for verb_pattern in FORBIDDEN_SQL_VERBS:
        # Look for verb in string literals (SQL context)
        # Only flag if it appears inside a quoted string or as a standalone string
        matches = re.findall(
            r'["\']([^"\']*' + verb_pattern[2:-2] + r'[^"\']*)["\']',
            code_text, re.IGNORECASE
        )
        # Filter to only actual SQL-like strings (not Python code like "INSERT" in docstrings)
        for m in matches:
            # If the matched string looks like SQL (not a comment or explanation)
            if re.search(r'\b(INTO|FROM|TABLE|WHERE|SET)\b', m, re.IGNORECASE):
                pytest.fail(f"Found SQL write verb in script string: {m!r}")


def test_script_has_json_out_argument(script_content):
    assert "--json-out" in script_content


def test_script_uses_read_only_db(script_content):
    assert "mode=ro" in script_content


# ── MD content checks ──────────────────────────────────────────────────────────

def test_md_no_promotion_authorization(md_content):
    # Should explicitly say promotion is NOT authorized
    assert "NOT authorized" in md_content or "not authorized" in md_content.lower()


def test_md_p108_blocked(md_content):
    assert "P108" in md_content
    # Should mention blocked or not executable
    assert "NOT EXECUTABLE" in md_content or "BLOCKED" in md_content


def test_md_4star_backtest_unauthorized(md_content):
    assert "4_STAR" in md_content
    assert "NOT AUTHORIZED" in md_content or "not authorized" in md_content.lower()


def test_md_contains_final_classification(md_content):
    assert "P113_P112_ACTION_DECISION_MATRIX_READY" in md_content


def test_md_contains_project_context_lock(md_content):
    assert "PROJECT_CONTEXT_LOCK" in md_content


# ── No DB files staged ─────────────────────────────────────────────────────────

def test_no_db_files_in_p113_output_dir():
    """Verify no DB/WAL/SHM files were created in the outputs directory."""
    outputs = BASE / "outputs" / "replay"
    if outputs.exists():
        for f in outputs.iterdir():
            assert not f.name.endswith(".db"), f"DB file found in outputs: {f}"
            assert not f.name.endswith(".wal"), f"WAL file found in outputs: {f}"
            assert not f.name.endswith(".shm"), f"SHM file found in outputs: {f}"
