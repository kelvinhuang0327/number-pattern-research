"""
P107B: Stale Baseline Guard Repair — Test Suite

≥30 governance tests covering:
  - JSON artifact fields and governance confirmations
  - Live DB invariants (accepted post-P104 baseline)
  - MD content checks
  - Script read-only safety (no write SQL verbs)
  - Historical artifacts untouched
  - Repaired-test correctness
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_PATH = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p107b_stale_baseline_guard_repair_20260527.json"
)
MD_PATH = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "p107b_stale_baseline_guard_repair_20260527.md"
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "p107b_stale_baseline_guard_repair.py"

# Historical artifacts — must remain unchanged
P98_JSON = REPO_ROOT / "outputs" / "replay" / "special3_oos_permutation_review_20260527.json"
P99_JSON = REPO_ROOT / "outputs" / "replay" / "special3_prospective_dryrun_plan_20260527.json"

# Accepted post-P104 baseline
EXPECTED_REPLAY_ROWS = 54462
EXPECTED_3STAR_COUNT = 4179
EXPECTED_3STAR_MAX = "115000106"
EXPECTED_4STAR_COUNT = 2922
EXPECTED_4STAR_MAX = "115000103"
EXPECTED_PL_COUNT = 1913
EXPECTED_PL_MAX = "115000041"

# Stale historical facts
STALE_3STAR_COUNT = 4115
STALE_3STAR_MAX = "115000024"
STALE_4STAR_COUNT = 0


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def artifact():
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text())


@pytest.fixture(scope="session")
def md_text():
    assert MD_PATH.exists(), f"MD report missing: {MD_PATH}"
    return MD_PATH.read_text()


@pytest.fixture(scope="session")
def script_text():
    assert SCRIPT_PATH.exists(), f"Script missing: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text()


@pytest.fixture(scope="session")
def db_conn():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield conn
    conn.close()


# ── § 1: JSON Artifact Basics ─────────────────────────────────────────────────

def test_01_json_artifact_exists():
    assert JSON_PATH.exists(), f"Missing: {JSON_PATH}"


def test_02_json_is_valid(artifact):
    assert isinstance(artifact, dict), "Artifact must be a JSON object"


def test_03_classification(artifact):
    assert artifact["classification"] == "P107B_STALE_BASELINE_GUARD_REPAIR_READY"


def test_04_final_classification_matches(artifact):
    assert artifact["final_classification"] == artifact["classification"]


def test_05_task_field(artifact):
    assert artifact["task"] == "P107B"


def test_06_repair_scope_active_tests_only(artifact):
    assert artifact["repair_scope"] == "active_tests_only"


# ── § 2: Governance Flags ─────────────────────────────────────────────────────

def test_07_historical_artifacts_rewritten_false(artifact):
    assert artifact["historical_artifacts_rewritten"] is False


def test_08_db_writes_false(artifact):
    assert artifact["db_writes"] is False


def test_09_governance_four_star_backtest_authorized_false(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["four_star_backtest_authorized"] is False


def test_10_governance_special3_promotion_authorized_false(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["special3_promotion_authorized"] is False


def test_11_governance_lifecycle_mutation_false(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["lifecycle_mutation"] is False


def test_12_governance_source_unknown_caveat_preserved(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["source_unknown_caveat_preserved"] is True


def test_13_governance_p108_100draw_rerun_not_performed(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["p108_100draw_rerun_performed"] is False


def test_14_governance_historical_artifacts_rewritten_in_gc(artifact):
    gc = artifact["governance_confirmations"]
    assert gc["historical_artifacts_rewritten"] is False


# ── § 3: Accepted Baseline in Artifact ───────────────────────────────────────

def test_15_replay_rows_before_matches_expected(artifact):
    assert artifact["replay_rows_before"] == EXPECTED_REPLAY_ROWS


def test_16_replay_rows_after_matches_expected(artifact):
    assert artifact["replay_rows_after"] == EXPECTED_REPLAY_ROWS


def test_17_accepted_baseline_three_star_count(artifact):
    ab = artifact["accepted_current_baseline"]
    assert ab["three_star_count"] == EXPECTED_3STAR_COUNT


def test_18_accepted_baseline_three_star_max(artifact):
    ab = artifact["accepted_current_baseline"]
    assert ab["three_star_max_draw"] == EXPECTED_3STAR_MAX


def test_19_accepted_baseline_four_star_count(artifact):
    ab = artifact["accepted_current_baseline"]
    assert ab["four_star_count"] == EXPECTED_4STAR_COUNT


def test_20_accepted_baseline_four_star_max(artifact):
    ab = artifact["accepted_current_baseline"]
    assert ab["four_star_max_draw"] == EXPECTED_4STAR_MAX


def test_21_accepted_baseline_power_lotto_count(artifact):
    ab = artifact["accepted_current_baseline"]
    assert ab["power_lotto_count"] == EXPECTED_PL_COUNT


def test_22_accepted_baseline_power_lotto_max(artifact):
    ab = artifact["accepted_current_baseline"]
    assert ab["power_lotto_max_draw"] == EXPECTED_PL_MAX


# ── § 4: Stale Baseline Record ────────────────────────────────────────────────

def test_23_stale_baseline_old_three_star_count(artifact):
    sb = artifact["stale_baselines_repaired"]
    assert sb["old_three_star_count"] == STALE_3STAR_COUNT


def test_24_stale_baseline_old_three_star_max(artifact):
    sb = artifact["stale_baselines_repaired"]
    assert sb["old_three_star_max_draw"] == STALE_3STAR_MAX


def test_25_stale_baseline_old_four_star_count(artifact):
    sb = artifact["stale_baselines_repaired"]
    assert sb["old_four_star_count"] == STALE_4STAR_COUNT


# ── § 5: Repaired Tests List ──────────────────────────────────────────────────

def test_26_repaired_tests_count(artifact):
    assert len(artifact["repaired_tests"]) == 2


def test_27_repaired_tests_include_p98_test11(artifact):
    names = [t["test"] for t in artifact["repaired_tests"]]
    assert "test_11_no_4star_backtest_metrics" in names


def test_28_repaired_tests_include_p99_test14(artifact):
    names = [t["test"] for t in artifact["repaired_tests"]]
    assert "test_14_special4_data_gap_blocking" in names


# ── § 6: Live DB Invariants ───────────────────────────────────────────────────

def test_29_live_db_replay_rows(db_conn):
    rows = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert rows == EXPECTED_REPLAY_ROWS, f"Expected {EXPECTED_REPLAY_ROWS}, got {rows}"


def test_30_live_db_three_star_count(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()[0]
    assert cnt == EXPECTED_3STAR_COUNT


def test_31_live_db_three_star_max_draw(db_conn):
    max_draw = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='3_STAR'"
    ).fetchone()[0]
    assert str(max_draw) == EXPECTED_3STAR_MAX


def test_32_live_db_four_star_count(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert cnt == EXPECTED_4STAR_COUNT


def test_33_live_db_four_star_max_draw(db_conn):
    max_draw = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert str(max_draw) == EXPECTED_4STAR_MAX


def test_34_live_db_power_lotto_count(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    assert cnt == EXPECTED_PL_COUNT


def test_35_live_db_power_lotto_max_draw(db_conn):
    max_draw = db_conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    assert str(max_draw) == EXPECTED_PL_MAX


# ── § 7: Script Safety ────────────────────────────────────────────────────────

_FORBIDDEN_WRITE_PATTERN = re.compile(
    r"""\.execute\(\s*["'f](?:f"[^"]*"|'[^']*'|"[^"]*")""",
    re.IGNORECASE,
)
_WRITE_VERBS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|REPLACE|VACUUM)\b",
    re.IGNORECASE,
)


def test_36_script_no_write_sql(script_text):
    """No SQL write verbs on any .execute() call line."""
    for line in script_text.splitlines():
        if ".execute(" in line.lower():
            assert not _WRITE_VERBS.search(line), (
                f"Write SQL verb found in .execute() line: {line!r}"
            )


def test_37_script_no_insert(script_text):
    for line in script_text.splitlines():
        if ".execute(" in line.lower():
            assert "insert" not in line.lower(), f"INSERT found in: {line!r}"


def test_38_script_no_update(script_text):
    for line in script_text.splitlines():
        if ".execute(" in line.lower():
            assert "update" not in line.lower(), f"UPDATE found in: {line!r}"


def test_39_script_no_delete(script_text):
    for line in script_text.splitlines():
        if ".execute(" in line.lower():
            assert "delete" not in line.lower(), f"DELETE found in: {line!r}"


# ── § 8: MD Report Content ───────────────────────────────────────────────────

def test_40_md_exists():
    assert MD_PATH.exists(), f"Missing MD: {MD_PATH}"


def test_41_md_has_classification(md_text):
    assert "P107B_STALE_BASELINE_GUARD_REPAIR_READY" in md_text


def test_42_md_mentions_historical_artifacts_not_rewritten(md_text):
    assert "NOT rewrite" in md_text or "not rewritten" in md_text.lower()


def test_43_md_four_star_backtest_unauthorized_statement(md_text):
    assert "NOT AUTHORIZED" in md_text


def test_44_md_mentions_replay_rows(md_text):
    assert "54462" in md_text


def test_45_md_mentions_four_star_count(md_text):
    assert "2922" in md_text


def test_46_md_mentions_source_unknown(md_text):
    assert "source_unknown" in md_text


def test_47_md_next_task_p108(md_text):
    assert "P108" in md_text


# ── § 9: Historical Artifacts Untouched ──────────────────────────────────────

def test_48_p98_historical_artifact_draws_loaded_unchanged():
    if not P98_JSON.exists():
        pytest.skip("P98 artifact not present")
    data = json.loads(P98_JSON.read_text())
    assert data.get("draws_loaded") == STALE_3STAR_COUNT, (
        "P98 historical artifact draws_loaded must remain 4115 — do not rewrite"
    )


def test_49_p99_historical_artifact_draws_loaded_unchanged():
    if not P99_JSON.exists():
        pytest.skip("P99 artifact not present")
    data = json.loads(P99_JSON.read_text())
    assert data.get("draws_loaded") == STALE_3STAR_COUNT, (
        "P99 historical artifact draws_loaded must remain 4115 — do not rewrite"
    )


def test_50_p99_historical_special4_status_unchanged():
    if not P99_JSON.exists():
        pytest.skip("P99 artifact not present")
    data = json.loads(P99_JSON.read_text())
    assert data.get("special4_status") == "DATA_GAP_BLOCKING", (
        "P99 historical special4_status must remain DATA_GAP_BLOCKING"
    )
