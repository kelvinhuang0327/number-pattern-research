"""
Tests for P124: Multi-Bet Replay Truth Model + Coverage Matrix
==============================================================
All tests are read-only. No DB writes, no staging checks beyond git status.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_JSON = (
    PROJECT_ROOT
    / "outputs"
    / "replay"
    / "p124_multi_bet_truth_and_coverage_matrix_20260528.json"
)
ARTIFACT_MD = (
    PROJECT_ROOT
    / "docs"
    / "replay"
    / "p124_multi_bet_truth_and_coverage_matrix_20260528.md"
)
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_3STAR_COUNT = 4179
EXPECTED_3STAR_MAX = "115000106"
EXPECTED_4STAR_COUNT = 2922
EXPECTED_4STAR_MAX = "115000103"
EXPECTED_POWER_LOTTO_COUNT = 1913
EXPECTED_POWER_LOTTO_MAX = "115000041"

REQUIRED_TOP_LEVEL_KEYS = {
    "task_id",
    "generated_at",
    "classification",
    "db_snapshot",
    "truth_model",
    "coverage_matrix",
    "excluded_listings",
    "summary",
    "governance",
    "next_task",
}

REQUIRED_TRUTH_MODEL_LABELS = {
    "native_multi_bet",
    "first_bet_only_fallback",
    "adapter_missing",
    "already_covered",
    "unsupported",
    "rejected",
    "retired",
    "source_unknown",
    "fabrication_prohibited",
}

REQUIRED_MATRIX_COLUMNS = {
    "strategy_id",
    "lottery_type",
    "native_bet_count",
    "adapter_status",
    "bet_1_label",
    "bet_2_label",
    "bet_3_label",
    "bet_4_label",
    "bet_5_label",
    "replay_rows_total",
    "replay_rows_per_bet",
    "quality_label",
    "blocker",
    "proposed_next_action_type",
}


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_JSON.exists(), f"Artifact not found: {ARTIFACT_JSON}"
    return json.loads(ARTIFACT_JSON.read_text())


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ── Schema checks ─────────────────────────────────────────────────────────────


def test_artifact_exists():
    assert ARTIFACT_JSON.exists(), f"JSON artifact missing: {ARTIFACT_JSON}"
    assert ARTIFACT_MD.exists(), f"MD report missing: {ARTIFACT_MD}"


def test_required_top_level_keys(artifact):
    missing = REQUIRED_TOP_LEVEL_KEYS - set(artifact.keys())
    assert not missing, f"Missing top-level keys: {missing}"


def test_task_id(artifact):
    assert artifact["task_id"] == "P124"


def test_classification_ready(artifact):
    assert artifact["classification"] == "P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY"


def test_next_task(artifact):
    assert artifact["next_task"] == "P125_ADAPTER_GAP_PLAN"


# ── DB invariant checks (read-only) ───────────────────────────────────────────


def test_db_snapshot_replay_rows(artifact):
    assert artifact["db_snapshot"]["replay_rows"] == EXPECTED_REPLAY_ROWS, (
        f"Expected replay_rows={EXPECTED_REPLAY_ROWS}, "
        f"got {artifact['db_snapshot']['replay_rows']}"
    )


def test_db_snapshot_3star(artifact):
    s = artifact["db_snapshot"]["3_STAR"]
    assert s["count"] == EXPECTED_3STAR_COUNT
    assert s["max_draw"] == EXPECTED_3STAR_MAX


def test_db_snapshot_4star(artifact):
    s = artifact["db_snapshot"]["4_STAR"]
    assert s["count"] == EXPECTED_4STAR_COUNT
    assert s["max_draw"] == EXPECTED_4STAR_MAX


def test_db_snapshot_power_lotto(artifact):
    s = artifact["db_snapshot"]["POWER_LOTTO"]
    assert s["count"] == EXPECTED_POWER_LOTTO_COUNT
    assert s["max_draw"] == EXPECTED_POWER_LOTTO_MAX


def test_db_replay_row_count_unchanged(db_conn):
    """Confirm no DB write occurred — row count must still be EXPECTED_REPLAY_ROWS."""
    c = db_conn.cursor()
    c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    actual = c.fetchone()[0]
    assert actual == EXPECTED_REPLAY_ROWS, (
        f"DB row count changed! Expected {EXPECTED_REPLAY_ROWS}, got {actual}. "
        "Possible unauthorized DB write."
    )


# ── Truth model checks ────────────────────────────────────────────────────────


def test_all_9_truth_model_labels_present(artifact):
    labels = set(artifact["truth_model"]["labels"].keys())
    missing = REQUIRED_TRUTH_MODEL_LABELS - labels
    assert not missing, f"Missing truth model labels: {missing}"


def test_truth_model_has_conventions(artifact):
    assert "conventions" in artifact["truth_model"]
    conventions = artifact["truth_model"]["conventions"]
    assert conventions.get("one_row_per_strategy_draw") is True
    assert conventions.get("predicted_numbers_stores_single_bet") is True


# ── Coverage matrix checks ────────────────────────────────────────────────────


def test_coverage_matrix_non_empty(artifact):
    assert isinstance(artifact["coverage_matrix"], list)
    assert len(artifact["coverage_matrix"]) > 0


def test_coverage_matrix_row_columns(artifact):
    for row in artifact["coverage_matrix"]:
        missing = REQUIRED_MATRIX_COLUMNS - set(row.keys())
        assert not missing, (
            f"Row {row.get('strategy_id')} / {row.get('lottery_type')} missing columns: {missing}"
        )


def test_no_4star_in_coverage_matrix(artifact):
    """No coverage_matrix row should claim lottery_type=4_STAR."""
    for row in artifact["coverage_matrix"]:
        assert row["lottery_type"] != "4_STAR", (
            f"Forbidden: 4_STAR found in coverage_matrix for strategy {row['strategy_id']}"
        )


def test_no_native_multi_bet_for_4star(artifact):
    """No row should claim native_multi_bet for 4_STAR lottery."""
    for row in artifact["coverage_matrix"]:
        if row["lottery_type"] == "4_STAR":
            for b in range(1, 6):
                lbl = row.get(f"bet_{b}_label", "")
                assert lbl != "native_multi_bet", (
                    f"native_multi_bet label on 4_STAR strategy {row['strategy_id']} bet_{b}"
                )


def test_rejected_rows_have_no_native_multi_bet(artifact):
    """No bet_N_label can be native_multi_bet when the row is rejected."""
    for row in artifact["coverage_matrix"]:
        if row["adapter_status"] == "rejected":
            for b in range(1, 6):
                lbl = row.get(f"bet_{b}_label", "")
                assert lbl != "native_multi_bet", (
                    f"rejected strategy {row['strategy_id']} has native_multi_bet at bet_{b}"
                )


def test_native_multi_bet_count_is_zero(artifact):
    """Per the current storage convention, no strategy achieves native_multi_bet."""
    for row in artifact["coverage_matrix"]:
        for b in range(1, 6):
            lbl = row.get(f"bet_{b}_label", "")
            assert lbl != "native_multi_bet", (
                f"Unexpected native_multi_bet: {row['strategy_id']} / "
                f"{row['lottery_type']} / bet_{b}"
            )


def test_unsupported_labels_above_native(artifact):
    """bet_N_label must be 'unsupported' when N > native_bet_count (unless rejected)."""
    for row in artifact["coverage_matrix"]:
        if row["adapter_status"] == "rejected":
            continue
        native = row["native_bet_count"]
        for b in range(1, 6):
            lbl = row.get(f"bet_{b}_label", "")
            if b > native:
                assert lbl == "unsupported", (
                    f"{row['strategy_id']} bet_{b} (native={native}): "
                    f"expected 'unsupported', got '{lbl}'"
                )


# ── Excluded listings ─────────────────────────────────────────────────────────


def test_excluded_listings_has_source_unknown_4star(artifact):
    excl = artifact["excluded_listings"]
    assert "4_STAR" in excl.get("source_unknown", []), (
        "4_STAR must appear in excluded_listings.source_unknown"
    )


def test_excluded_listings_rejected_non_empty(artifact):
    rejected = artifact["excluded_listings"].get("rejected", [])
    assert len(rejected) > 0, "excluded_listings.rejected must list at least one strategy"


# ── Governance checks ─────────────────────────────────────────────────────────


def test_governance_no_db_writes(artifact):
    assert artifact["governance"]["db_writes"] == 0


def test_governance_replay_rows_unchanged(artifact):
    before = artifact["governance"]["replay_rows_before"]
    after = artifact["governance"]["replay_rows_after"]
    assert before == after == EXPECTED_REPLAY_ROWS


def test_governance_no_promotions(artifact):
    gov = artifact["governance"]
    assert gov["no_strategy_promotion"] is True
    assert gov["no_lifecycle_mutation"] is True
    assert gov["no_registry_mutation"] is True
    assert gov["no_4star_backtest"] is True
    assert gov["no_special3_p108_rerun"] is True
    assert gov["no_scheduler_install"] is True


# ── Forbidden staging scan ────────────────────────────────────────────────────


def test_no_forbidden_files_staged():
    """DB, history, pid, runtime files must NOT appear in git staged area."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--name-only"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    staged = result.stdout.strip().splitlines()
    forbidden_patterns = [
        "lottery_v2.db",
        "lottery_history.json",
        ".pid",
        "runtime/",
    ]
    for path in staged:
        for pattern in forbidden_patterns:
            assert pattern not in path, (
                f"Forbidden file staged: {path} (matches pattern '{pattern}')"
            )


# ── Summary checks ────────────────────────────────────────────────────────────


def test_summary_native_multi_bet_zero(artifact):
    assert artifact["summary"]["native_multi_bet_count"] == 0


def test_summary_fields_present(artifact):
    summary = artifact["summary"]
    required = {
        "total_strategy_lottery_pairs",
        "rejected_count",
        "native_multi_bet_count",
        "adapter_build_needed",
        "controlled_apply_ready",
        "key_finding",
    }
    missing = required - set(summary.keys())
    assert not missing, f"Summary missing fields: {missing}"
