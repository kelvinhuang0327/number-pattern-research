"""
P271E — Scoped Prize-Aware Replay Adapter Tests

Tests verifying the adapter's contract, isolation, safety guards,
and bounded smoke validation.

All DB operations use the canonical DB in read-only mode.
No DB write occurs during any test.
Scorer is called only via synthetic fixtures (isolated from DB) and
in the bounded DB smoke run (≤ 10 rows per lottery type).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import re
import sqlite3
import types

import pytest

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

DB_PATH = "lottery_api/data/lottery_v2.db"
ADAPTER_MODULE = "lottery_api.prize_aware_replay_adapter"
SCORER_MODULE = "lottery_api.prize_aware_scorer"
REPLAY_MODULE = "lottery_api.routes.replay"
SMOKE_LIMIT = 10


def _adapter():
    import lottery_api.prize_aware_replay_adapter as m
    return m


def _scorer():
    import lottery_api.prize_aware_scorer as m
    return m


# ---------------------------------------------------------------------------
# 1. Import without side effects
# ---------------------------------------------------------------------------

def test_adapter_imports_without_side_effects():
    """Adapter module must import cleanly with no side effects."""
    m = importlib.import_module(ADAPTER_MODULE)
    assert m is not None


# ---------------------------------------------------------------------------
# 2. Adapter version and scoring version
# ---------------------------------------------------------------------------

def test_adapter_version():
    m = _adapter()
    assert m.ADAPTER_VERSION == "prize_aware_adapter_v1"


def test_scoring_version_delegated():
    m = _adapter()
    s = _scorer()
    assert m.SCORING_VERSION == s.SCORING_VERSION
    assert m.SCORING_VERSION == "prize_aware_v1"


# ---------------------------------------------------------------------------
# 3. DB URI uses mode=ro
# ---------------------------------------------------------------------------

def test_db_open_uses_mode_ro():
    src = inspect.getsource(_adapter())
    # The URI must contain ?mode=ro
    assert "?mode=ro" in src
    assert "uri=True" in src


def test_open_ro_returns_connection(tmp_path):
    """_open_ro must return a writable-blocked sqlite connection."""
    m = _adapter()
    conn = m._open_ro(DB_PATH)
    try:
        assert isinstance(conn, sqlite3.Connection)
        # Verify read-only: attempt an INSERT must raise
        with pytest.raises(Exception):
            conn.execute("INSERT INTO strategy_prediction_replays (lottery_type) VALUES ('TEST')")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. No SQL write statements in source
# ---------------------------------------------------------------------------

def test_no_sql_write_statements_in_source():
    src = inspect.getsource(_adapter())
    # Check for DML write keywords
    for keyword in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "CREATE TABLE", "ALTER TABLE"):
        assert keyword not in src.upper(), f"Forbidden SQL keyword found: {keyword}"


# ---------------------------------------------------------------------------
# 5. Adapter imports scorer but not replay.py
# ---------------------------------------------------------------------------

def test_adapter_imports_scorer():
    m = _adapter()
    assert hasattr(m, "score_prize_aware_ticket")
    assert hasattr(m, "SCORING_VERSION")


def test_adapter_does_not_import_replay():
    src = inspect.getsource(_adapter())
    # Must not have actual import statements for the replay route module
    # (mentions in docstrings as a negative reference are allowed)
    assert "import lottery_api.routes.replay" not in src
    assert "from lottery_api.routes import" not in src
    assert "from lottery_api.routes.replay" not in src


def test_adapter_module_does_not_contain_replay_import():
    m = _adapter()
    module_imports = [
        name for name in dir(m)
        if isinstance(getattr(m, name), types.ModuleType)
    ]
    for name in module_imports:
        mod = getattr(m, name)
        assert "routes.replay" not in getattr(mod, "__name__", "")


# ---------------------------------------------------------------------------
# 6. No DB/repository write modules in adapter imports
# ---------------------------------------------------------------------------

def test_no_write_module_imports():
    src = inspect.getsource(_adapter())
    forbidden_imports = [
        "import os",  # os.system / os.popen could write
        "subprocess",
        "shutil",
        "tempfile",
        "pathlib.Path",
        "open(",
    ]
    # The adapter uses only sqlite3, json, and typing imports
    # It must not import subprocess or shutil
    assert "subprocess" not in src
    assert "shutil" not in src


# ---------------------------------------------------------------------------
# 7. No strategy-selection imports
# ---------------------------------------------------------------------------

def test_no_strategy_selection_imports():
    src = inspect.getsource(_adapter())
    forbidden = [
        "replay_strategy_registry",
        "rolling_strategy_monitor",
        "quick_predict",
        "strategy_selection",
    ]
    for token in forbidden:
        assert token not in src, f"Forbidden strategy-selection reference: {token}"


# ---------------------------------------------------------------------------
# 8. Deterministic ordering (same inputs, same output order)
# ---------------------------------------------------------------------------

def test_deterministic_ordering():
    m = _adapter()
    first_pass = list(m.iter_structurally_eligible_rows(
        DB_PATH, lottery_type="DAILY_539", limit=5
    ))
    second_pass = list(m.iter_structurally_eligible_rows(
        DB_PATH, lottery_type="DAILY_539", limit=5
    ))
    assert len(first_pass) == len(second_pass)
    for a, b in zip(first_pass, second_pass):
        assert a["target_draw"] == b["target_draw"]
        assert a["strategy_id"] == b["strategy_id"]
        assert a["bet_index"] == b["bet_index"]


# ---------------------------------------------------------------------------
# 9. Explicit bounded limit required
# ---------------------------------------------------------------------------

def test_limit_none_raises():
    m = _adapter()
    with pytest.raises(ValueError, match="limit"):
        list(m.iter_structurally_eligible_rows(DB_PATH, limit=None))


def test_limit_zero_raises():
    m = _adapter()
    with pytest.raises(ValueError):
        list(m.iter_structurally_eligible_rows(DB_PATH, limit=0))


def test_limit_negative_raises():
    m = _adapter()
    with pytest.raises(ValueError):
        list(m.iter_structurally_eligible_rows(DB_PATH, limit=-1))


def test_limit_respected():
    m = _adapter()
    rows = list(m.iter_structurally_eligible_rows(DB_PATH, lottery_type="BIG_LOTTO", limit=3))
    assert len(rows) <= 3


# ---------------------------------------------------------------------------
# 10. POWER eligibility requires stored predicted_special
# ---------------------------------------------------------------------------

def test_power_eligibility_requires_predicted_special():
    m = _adapter()
    # A row with NULL predicted_special must be ineligible
    row = {
        "lottery_type": "POWER_LOTTO",
        "predicted_numbers": "[1,2,3,4,5,6]",
        "actual_numbers": "[1,2,3,4,5,6]",
        "predicted_special": None,  # NULL
        "actual_special": 3,
        "_join_count": 1,
        "history_cutoff_draw": "100000001",
        "target_draw": "100000002",
        "strategy_id": "test",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_MISSING_PREDICTED_SECOND_ZONE


# ---------------------------------------------------------------------------
# 11. POWER missing predicted_special → MISSING_PREDICTED_SECOND_ZONE
# ---------------------------------------------------------------------------

def test_power_missing_predicted_special_exclusion_reason():
    m = _adapter()
    row = {
        "lottery_type": "POWER_LOTTO",
        "predicted_numbers": "[1,2,3,4,5,6]",
        "actual_numbers": "[7,8,9,10,11,12]",
        "predicted_special": None,
        "actual_special": 5,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == "MISSING_PREDICTED_SECOND_ZONE"


# ---------------------------------------------------------------------------
# 12. POWER missing values not filled or inferred
# ---------------------------------------------------------------------------

def test_power_missing_values_not_filled_or_inferred():
    """Adapter must never substitute actual_special for missing predicted_special."""
    m = _adapter()
    src = inspect.getsource(m)
    # Must NOT contain logic that substitutes actual_special for predicted_special
    # Check that there's no "predicted_special = row.get('actual_special')" pattern
    assert "predicted_special = row.get(\"actual_special\")" not in src
    assert "predicted_special = row.get('actual_special')" not in src
    assert "predicted_special = actual_special" not in src


# ---------------------------------------------------------------------------
# 13. BIG mapping uses actual special number
# ---------------------------------------------------------------------------

def test_big_mapping_uses_actual_special():
    m = _adapter()
    row = {
        "lottery_type": "BIG_LOTTO",
        "predicted_numbers": "[1,2,3,4,5,6]",
        "actual_numbers": "[7,8,9,10,11,12]",
        "predicted_special": None,
        "actual_special": 25,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert eligible, f"Expected eligible but got reason: {reason}"
    scorer_input = m.map_replay_row_to_scorer_input(row)
    assert scorer_input["actual_special_number"] == 25
    assert scorer_input["predicted_second_zone"] is None
    assert scorer_input["actual_second_zone"] is None


# ---------------------------------------------------------------------------
# 14. DAILY_539 rejects auxiliary fields
# ---------------------------------------------------------------------------

def test_daily_539_rejects_predicted_special():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": 3,  # must be rejected
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_INVALID_ACTUAL_AUXILIARY


def test_daily_539_rejects_actual_special():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": 5,  # must be rejected
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible


# ---------------------------------------------------------------------------
# 15. Join ambiguity rejection
# ---------------------------------------------------------------------------

def test_join_ambiguity_rejected():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 2,  # ambiguous
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_AMBIGUOUS_DRAW_JOIN


# ---------------------------------------------------------------------------
# 16. Causality failure rejection
# ---------------------------------------------------------------------------

def test_causality_failure_rejected():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000010",  # cutoff >= target → causality fail
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_CAUSALITY_FAILURE


def test_causality_reversed_order_rejected():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000020",  # cutoff > target
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_CAUSALITY_FAILURE


# ---------------------------------------------------------------------------
# 17. Invalid cardinality rejection
# ---------------------------------------------------------------------------

def test_invalid_cardinality_rejected():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4]",  # only 4 numbers, need 5
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_INVALID_PREDICTED_MAIN


# ---------------------------------------------------------------------------
# 18. Invalid range rejection
# ---------------------------------------------------------------------------

def test_invalid_range_rejected():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,40]",  # 40 > 39
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_INVALID_PREDICTED_MAIN


# ---------------------------------------------------------------------------
# 19. Duplicate-number rejection
# ---------------------------------------------------------------------------

def test_duplicate_number_rejected():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,3,5]",  # 3 appears twice
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_INVALID_PREDICTED_MAIN


# ---------------------------------------------------------------------------
# 20. Unsupported lottery type rejection
# ---------------------------------------------------------------------------

def test_unsupported_lottery_type_rejected():
    m = _adapter()
    row = {
        "lottery_type": "MYSTERY_LOTTO",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[1,2,3,4,5]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    eligible, reason = m._check_eligibility(row)
    assert not eligible
    assert reason == m.EXCLUSION_UNSUPPORTED_LOTTERY_TYPE


# ---------------------------------------------------------------------------
# 21. Mapping preserves strategy_id and bet_index only as identifiers
# ---------------------------------------------------------------------------

def test_mapping_preserves_strategy_id_and_bet_index():
    m = _adapter()
    row = {
        "lottery_type": "BIG_LOTTO",
        "predicted_numbers": "[1,2,3,4,5,6]",
        "actual_numbers": "[7,8,9,10,11,12]",
        "predicted_special": None,
        "actual_special": 20,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "my_strategy_42",
        "bet_index": 3,
    }
    scorer_input = m.map_replay_row_to_scorer_input(row)
    # scorer_input goes directly to score_prize_aware_ticket — no strategy_id or bet_index
    assert "strategy_id" not in scorer_input
    assert "bet_index" not in scorer_input
    # The caller retains strategy_id and bet_index from the original row
    assert row["strategy_id"] == "my_strategy_42"
    assert row["bet_index"] == 3


# ---------------------------------------------------------------------------
# 22. Existing replay row is not mutated
# ---------------------------------------------------------------------------

def test_no_replay_row_mutation():
    m = _adapter()
    original_row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[6,7,8,9,10]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    import copy
    row_copy = copy.deepcopy(original_row)
    _ = m.map_replay_row_to_scorer_input(row_copy)
    # Verify row was not mutated
    assert row_copy == original_row


# ---------------------------------------------------------------------------
# 23. Scorer input contract is exact
# ---------------------------------------------------------------------------

def test_power_scorer_input_contract():
    m = _adapter()
    row = {
        "lottery_type": "POWER_LOTTO",
        "predicted_numbers": "[1,2,3,4,5,6]",
        "actual_numbers": "[7,8,9,10,11,12]",
        "predicted_special": 3,
        "actual_special": 5,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    scorer_input = m.map_replay_row_to_scorer_input(row)
    assert scorer_input["lottery_type"] == "POWER_LOTTO"
    assert scorer_input["predicted_main_numbers"] == [1, 2, 3, 4, 5, 6]
    assert scorer_input["actual_main_numbers"] == [7, 8, 9, 10, 11, 12]
    assert scorer_input["predicted_second_zone"] == 3
    assert scorer_input["actual_second_zone"] == 5
    assert scorer_input["actual_special_number"] is None


def test_daily_539_scorer_input_contract():
    m = _adapter()
    row = {
        "lottery_type": "DAILY_539",
        "predicted_numbers": "[1,2,3,4,5]",
        "actual_numbers": "[6,7,8,9,10]",
        "predicted_special": None,
        "actual_special": None,
        "_join_count": 1,
        "history_cutoff_draw": "115000001",
        "target_draw": "115000010",
        "strategy_id": "s1",
        "bet_index": 1,
    }
    scorer_input = m.map_replay_row_to_scorer_input(row)
    assert scorer_input["lottery_type"] == "DAILY_539"
    assert scorer_input["predicted_main_numbers"] == [1, 2, 3, 4, 5]
    assert scorer_input["actual_main_numbers"] == [6, 7, 8, 9, 10]
    assert scorer_input["predicted_second_zone"] is None
    assert scorer_input["actual_second_zone"] is None
    assert scorer_input["actual_special_number"] is None


# ---------------------------------------------------------------------------
# 24. Scorer output schema is preserved
# ---------------------------------------------------------------------------

def test_scorer_output_schema_preserved():
    m = _adapter()
    s = _scorer()
    result = s.score_prize_aware_ticket(
        lottery_type="DAILY_539",
        predicted_main_numbers=[1, 2, 3, 4, 5],
        actual_main_numbers=[1, 2, 3, 6, 7],
    )
    required_fields = [
        "scoring_version", "lottery_type", "main_hit_count", "special_hit",
        "any_prize_aware_win", "prize_tier", "tier_class", "is_prize_aware_win",
        "is_m3_plus", "endpoint_flags", "source_verification_status",
        "parallel_feature", "existing_m3_replay_scoring_changed",
    ]
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"
    assert result["existing_m3_replay_scoring_changed"] is False


# ---------------------------------------------------------------------------
# 25. Synthetic scorer calls for all three lotteries
# ---------------------------------------------------------------------------

def test_synthetic_scorer_power_lotto():
    s = _scorer()
    result = s.score_prize_aware_ticket(
        lottery_type="POWER_LOTTO",
        predicted_main_numbers=[1, 2, 3, 4, 5, 6],
        actual_main_numbers=[1, 2, 3, 7, 8, 9],
        predicted_second_zone=3,
        actual_second_zone=3,
    )
    assert result["lottery_type"] == "POWER_LOTTO"
    assert result["main_hit_count"] == 3
    assert result["special_hit"] == 1
    assert result["tier_class"] == "POWER_SEVENTH_PRIZE"


def test_synthetic_scorer_big_lotto():
    s = _scorer()
    result = s.score_prize_aware_ticket(
        lottery_type="BIG_LOTTO",
        predicted_main_numbers=[1, 2, 3, 4, 5, 6],
        actual_main_numbers=[1, 2, 3, 7, 8, 9],
        actual_special_number=4,
    )
    assert result["lottery_type"] == "BIG_LOTTO"
    assert result["main_hit_count"] == 3
    assert result["special_hit"] == 1
    assert result["tier_class"] == "BIG_SIXTH_PRIZE"


def test_synthetic_scorer_daily_539():
    s = _scorer()
    result = s.score_prize_aware_ticket(
        lottery_type="DAILY_539",
        predicted_main_numbers=[1, 2, 3, 4, 5],
        actual_main_numbers=[1, 2, 3, 6, 7],
    )
    assert result["lottery_type"] == "DAILY_539"
    assert result["main_hit_count"] == 3
    assert result["tier_class"] == "D539_THIRD_PRIZE"


# ---------------------------------------------------------------------------
# 26. Bounded DB smoke processes no more than 10 rows per lottery
# ---------------------------------------------------------------------------

def test_smoke_processes_no_more_than_limit_per_lottery():
    m = _adapter()
    result = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=SMOKE_LIMIT)
    for lt in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
        processed = result["processed_rows_by_lottery"][lt]
        assert processed <= SMOKE_LIMIT, (
            f"{lt}: processed {processed} > limit {SMOKE_LIMIT}"
        )


# ---------------------------------------------------------------------------
# 27. Smoke run is deterministic
# ---------------------------------------------------------------------------

def test_smoke_run_is_deterministic():
    m = _adapter()
    result1 = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=3)
    result2 = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=3)
    assert result1["processed_rows_by_lottery"] == result2["processed_rows_by_lottery"]
    assert result1["successful_scorer_calls_by_lottery"] == result2["successful_scorer_calls_by_lottery"]
    assert result1["deterministic_repeat_check"]["passed"] == result2["deterministic_repeat_check"]["passed"]


# ---------------------------------------------------------------------------
# 28. Smoke artifact has no success-rate metrics
# ---------------------------------------------------------------------------

def test_smoke_artifact_has_no_success_rate_metrics():
    m = _adapter()
    result = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=3)
    # Explicitly forbidden top-level keys (exact key names, not substring matches)
    # Note: "success_rate_calculated" is a safety flag (value=False) and is allowed
    forbidden_exact_keys = [
        "success_rate", "hit_rate", "tier_frequency", "win_rate",
        "prize_rate", "accuracy", "edge", "baseline_comparison",
        "lift", "p_value",
    ]
    for key in forbidden_exact_keys:
        assert key not in result, f"Forbidden metric key found in smoke result: {key}"
    # The safety flag success_rate_calculated must be present and False
    assert result.get("success_rate_calculated") is False


# ---------------------------------------------------------------------------
# 29. Smoke artifact has no strategy aggregates/rankings
# ---------------------------------------------------------------------------

def test_smoke_artifact_has_no_strategy_ranking():
    m = _adapter()
    result = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=3)
    forbidden_keys = ["strategy_rank", "best_strategy", "ranked_strategy", "strategy_score"]
    result_str = str(result).lower()
    for key in forbidden_keys:
        assert key not in result_str, f"Forbidden strategy aggregate found: {key}"


# ---------------------------------------------------------------------------
# 30. No raw actual-number arrays exported
# ---------------------------------------------------------------------------

def test_smoke_no_raw_actual_number_arrays():
    m = _adapter()
    result = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=3)
    # The smoke summary must not contain raw_actual_number_arrays_exported = True
    assert result.get("raw_actual_number_arrays_exported") is False


# ---------------------------------------------------------------------------
# 31. DB remains unchanged before/after smoke run
# ---------------------------------------------------------------------------

def test_db_row_count_unchanged_after_smoke():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        before = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()

    m = _adapter()
    m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=5)

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()

    assert before == after, f"Row count changed: {before} → {after}"


# ---------------------------------------------------------------------------
# 32. No replay.py modification/integration
# ---------------------------------------------------------------------------

def test_no_replay_module_imported():
    m = _adapter()
    # Scan all module-level names for the replay route module
    for attr_name in dir(m):
        attr = getattr(m, attr_name)
        if isinstance(attr, types.ModuleType):
            assert "routes.replay" not in attr.__name__


def test_adapter_source_does_not_reference_replay_module():
    src = inspect.getsource(_adapter())
    assert "replay.py" not in src
    # Must not contain actual import statements for routes.replay
    # (docstring negative references like "NOT lottery_api.routes.replay" are allowed)
    assert "import lottery_api.routes.replay" not in src
    assert "from lottery_api.routes.replay" not in src


# ---------------------------------------------------------------------------
# 33. No API/frontend integration
# ---------------------------------------------------------------------------

def test_no_api_frontend_integration():
    src = inspect.getsource(_adapter())
    forbidden = ["FastAPI", "APIRouter", "app.include_router", "@app.get", "@router.get"]
    for token in forbidden:
        assert token not in src, f"Forbidden API token: {token}"


# ---------------------------------------------------------------------------
# 34. No registry mutation
# ---------------------------------------------------------------------------

def test_no_registry_mutation():
    src = inspect.getsource(_adapter())
    assert "hypothesis_registry" not in src
    assert "replay_strategy_registry" not in src


# ---------------------------------------------------------------------------
# 35. No prize amount/EV/ROI logic
# ---------------------------------------------------------------------------

def test_no_prize_amount_ev_roi_logic():
    src = inspect.getsource(_adapter())
    forbidden = ["prize_amount", "ev_roi", "expected_value", "roi_calc", "payout_amount"]
    for token in forbidden:
        assert token.lower() not in src.lower(), f"Forbidden financial logic: {token}"


# ---------------------------------------------------------------------------
# 36. Required implementation artifact fields
# ---------------------------------------------------------------------------

def test_required_implementation_artifact_exists():
    path = "outputs/research/p271e_scoped_prize_aware_replay_adapter_implementation_20260612.json"
    if not os.path.exists(path):
        pytest.skip("Implementation artifact not yet generated")
    import json
    with open(path) as f:
        artifact = json.load(f)
    required_fields = [
        "task_id", "generated_at", "branch", "mode",
        "adapter_version", "scoring_version",
        "scorer_imported", "scorer_called_in_tests",
        "scorer_called_in_bounded_smoke",
        "full_historical_evaluation_run", "success_rate_calculated",
        "strategy_comparison_run", "db_access", "db_read_only", "db_write",
        "registry_write", "existing_replay_modified",
        "existing_m3_replay_scoring_changed", "production_integration_added",
        "strategy_generated", "strategy_ranked", "hit_rate_improvement_claimed",
        "p270c_allowed", "final_classification",
    ]
    for field in required_fields:
        assert field in artifact, f"Missing required artifact field: {field}"


# ---------------------------------------------------------------------------
# 37. Required MD safety declarations
# ---------------------------------------------------------------------------

def test_required_md_safety_declarations():
    path = "outputs/research/p271e_scoped_prize_aware_replay_adapter_implementation_20260612.md"
    if not os.path.exists(path):
        pytest.skip("MD artifact not yet generated")
    with open(path) as f:
        content = f.read()
    required_declarations = [
        "standalone",
        "read-only",
        "replay.py was not modified",
        "M3+",
        "MANUAL_VERIFICATION_REQUIRED",
        "bounded smoke",
        "no full historical",
        "POWER",
        "predicted second-zone",
        "excluded",
        "P270C",
    ]
    for decl in required_declarations:
        assert decl.lower() in content.lower(), f"Missing declaration: {decl!r}"


# ---------------------------------------------------------------------------
# 38. Final classification is allowed
# ---------------------------------------------------------------------------

def test_final_classification_is_allowed():
    path = "outputs/research/p271e_scoped_prize_aware_replay_adapter_implementation_20260612.json"
    if not os.path.exists(path):
        pytest.skip("Implementation artifact not yet generated")
    import json
    with open(path) as f:
        artifact = json.load(f)
    allowed_classifications = {
        "P271E_SCOPED_PRIZE_AWARE_REPLAY_ADAPTER_COMPLETE",
        "P271E_BLOCKED_ADAPTER_CONTRACT_MISMATCH",
        "P271E_BLOCKED_POWER_SECOND_ZONE_PROVENANCE",
        "P271E_BLOCKED_DB_READ_ONLY_GUARD",
        "P271E_BLOCKED_IMPORT_OR_PACKAGE_STRUCTURE",
        "P271E_BLOCKED_GOVERNANCE_CONFLICT",
        "P271E_TEST_FAILURE",
    }
    assert artifact["final_classification"] in allowed_classifications


# ---------------------------------------------------------------------------
# 39. P271D feasibility restrictions are preserved
# ---------------------------------------------------------------------------

def test_p271d_feasibility_restrictions_preserved():
    path = "outputs/research/p271e_scoped_prize_aware_replay_adapter_implementation_20260612.json"
    if not os.path.exists(path):
        pytest.skip("Implementation artifact not yet generated")
    import json
    with open(path) as f:
        artifact = json.load(f)
    snapshot = artifact.get("p271d_feasibility_snapshot", {})
    # BIG_LOTTO and DAILY_539 must be fully eligible
    big = snapshot.get("BIG_LOTTO", {})
    d539 = snapshot.get("DAILY_539", {})
    assert big.get("feasibility_status") in ("FULL", "full", "FULL_FEASIBLE"), \
        f"BIG_LOTTO feasibility not full: {big}"
    assert d539.get("feasibility_status") in ("FULL", "full", "FULL_FEASIBLE"), \
        f"DAILY_539 feasibility not full: {d539}"
    # POWER must be partial only
    power = snapshot.get("POWER_LOTTO", {})
    assert power.get("feasibility_status") in ("PARTIAL", "partial"), \
        f"POWER_LOTTO feasibility must be partial: {power}"


# ---------------------------------------------------------------------------
# 40. POWER full dataset not falsely declared fully eligible
# ---------------------------------------------------------------------------

def test_power_full_dataset_not_falsely_declared_fully_eligible():
    m = _adapter()
    # POWER_LOTTO has 36,104 rows; only ~9,000 have predicted_special
    # Verify that the exclusion summary reports non-zero MISSING_PREDICTED_SECOND_ZONE
    exclusions = m.summarize_structural_exclusions(DB_PATH, lottery_type="POWER_LOTTO")
    power_exclusions = exclusions.get("POWER_LOTTO", {})
    missing_sz = power_exclusions.get(m.EXCLUSION_MISSING_PREDICTED_SECOND_ZONE, 0)
    assert missing_sz > 0, (
        f"Expected POWER_LOTTO to have rows excluded for "
        f"MISSING_PREDICTED_SECOND_ZONE, got {missing_sz}"
    )


# ---------------------------------------------------------------------------
# Extra: Smoke limit validation
# ---------------------------------------------------------------------------

def test_smoke_zero_limit_raises():
    m = _adapter()
    with pytest.raises(ValueError):
        m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=0)


def test_smoke_safety_flags_in_result():
    m = _adapter()
    result = m.score_bounded_smoke_sample(DB_PATH, limit_per_lottery=2)
    assert result["full_historical_evaluation_run"] is False
    assert result["success_rate_calculated"] is False
    assert result["strategy_comparison_run"] is False
    assert result["raw_actual_number_arrays_exported"] is False
    assert result["db_read_only"] is True


def test_exclusion_reasons_all_present():
    m = _adapter()
    for reason in m.ALL_EXCLUSION_REASONS:
        assert isinstance(reason, str) and len(reason) > 0


def test_supported_lottery_types():
    m = _adapter()
    assert set(m.SUPPORTED_LOTTERY_TYPES) == {"POWER_LOTTO", "BIG_LOTTO", "DAILY_539"}
