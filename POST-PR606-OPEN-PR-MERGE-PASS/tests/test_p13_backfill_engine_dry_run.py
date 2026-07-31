"""
tests/test_p13_backfill_engine_dry_run.py
==========================================
20 tests verifying the P13 backfill engine dry-run output.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
P13_JSON = PROJECT_ROOT / "outputs" / "replay" / "p13_backfill_engine_dry_run_20260520.json"
DB_PATH  = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

ALLOWED_STATUSES = frozenset({
    "READY",
    "BLOCKED_NO_STRATEGY_RUNNER",
    "BLOCKED_INSUFFICIENT_HISTORY",
    "BLOCKED_NO_PREDICTION_PAYLOAD",
    "BLOCKED_DUPLICATE_REPLAY_ROW",
    "BLOCKED_UNSUPPORTED_LOTTERY_TYPE",
    "BLOCKED_INVALID_OUTPUT",
    "BLOCKED_REPLAY_ERROR",
})


@pytest.fixture(scope="module")
def p13() -> dict:
    assert P13_JSON.exists(), f"P13 JSON not found: {P13_JSON}"
    with open(P13_JSON) as f:
        return json.load(f)


# 1. P13 JSON exists
def test_p13_json_exists():
    assert P13_JSON.exists(), "P13 JSON output does not exist"


# 2. dry_run_only = true
def test_dry_run_only_flag(p13):
    assert p13["dry_run_only"] is True


# 3. production_rows_before = 460
def test_production_rows_before(p13):
    assert p13["production_rows_before"] == 460


# 4. production_rows_after = 460
def test_production_rows_after(p13):
    assert p13["production_rows_after"] == 460


# 5. target_draw_window = 1500
def test_target_draw_window(p13):
    assert p13["target_draw_window"] == 1500


# 6. target_strategy_count = 2
def test_target_strategy_count(p13):
    assert p13["target_strategy_count"] == 2


# 7. estimated_target_candidates = 3000
def test_estimated_target_candidates(p13):
    assert p13["estimated_target_candidates"] == 3000


# 8. fake_success_count = 0
def test_fake_success_count_zero(p13):
    assert p13["fake_success_count"] == 0


# 9. no_db_write = true
def test_no_db_write(p13):
    assert p13["no_db_write"] is True


# 10. All candidates have allowed prediction_status values
def test_candidates_sample_allowed_statuses(p13):
    for c in p13["candidates_sample"]:
        assert c["prediction_status"] in ALLOWED_STATUSES, (
            f"Unexpected status: {c['prediction_status']}"
        )


# 11. READY candidates have predicted_numbers and actual_numbers
def test_ready_candidates_have_numbers(p13):
    for c in p13["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["predicted_numbers"] is not None, "READY candidate missing predicted_numbers"
            assert len(c["predicted_numbers"]) > 0, "READY candidate has empty predicted_numbers"
            assert c["actual_numbers"] is not None, "READY candidate missing actual_numbers"
            assert len(c["actual_numbers"]) > 0, "READY candidate has empty actual_numbers"


# 12. BLOCKED candidates do not count as success (counts_as_success = False)
def test_blocked_candidates_not_success(p13):
    for c in p13["candidates_sample"]:
        if c["prediction_status"] != "READY":
            assert c["counts_as_success"] is False, (
                f"BLOCKED candidate {c['draw_number']} has counts_as_success=True"
            )


# 13. would_insert = false for all candidates
def test_would_insert_false_all(p13):
    for c in p13["candidates_sample"]:
        assert c["would_insert"] is False


# 14. counts_as_success = false for all dry-run candidates
def test_counts_as_success_false_all(p13):
    for c in p13["candidates_sample"]:
        assert c["counts_as_success"] is False


# 15. hit_count equals len(hit_numbers) for READY candidates
def test_hit_count_matches_hit_numbers(p13):
    for c in p13["candidates_sample"]:
        if c["prediction_status"] == "READY":
            assert c["hit_count"] == len(c["hit_numbers"]), (
                f"hit_count={c['hit_count']} != len(hit_numbers)={len(c['hit_numbers'])} "
                f"for draw {c['draw_number']}"
            )


# 16. Production DB rows remain 460 after script execution
def test_production_db_rows_after_execution():
    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert count == 460, f"DB row count changed: expected 460, got {count}"


# 17. No candidate from ARTIFACT_ONLY strategy
def test_no_artifact_only_strategy(p13):
    artifact_only_ids = {"p7_oos_gate", "controlled_apply_v1"}
    for c in p13["candidates_sample"]:
        assert c["strategy_id"] not in artifact_only_ids, (
            f"Candidate uses ARTIFACT_ONLY strategy: {c['strategy_id']}"
        )


# 18. No candidate from NO_DATA strategy
def test_no_no_data_strategy(p13):
    no_data_ids = {"big_lotto_v1_historical", "power_lotto_v1_historical"}
    for c in p13["candidates_sample"]:
        assert c["strategy_id"] not in no_data_ids, (
            f"Candidate uses NO_DATA strategy: {c['strategy_id']}"
        )


# 19. selected_strategies count = 2
def test_selected_strategies_count(p13):
    assert len(p13["selected_strategies"]) == 2


# 20. candidates_sample exists and is non-empty
def test_candidates_sample_exists(p13):
    assert "candidates_sample" in p13
    assert isinstance(p13["candidates_sample"], list)
    assert len(p13["candidates_sample"]) > 0, "candidates_sample is empty"
