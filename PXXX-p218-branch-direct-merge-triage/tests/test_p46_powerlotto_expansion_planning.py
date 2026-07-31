"""
test_p46_powerlotto_expansion_planning.py
==========================================
P46 contract tests for POWER_LOTTO expansion planning (read-only).

Verifies:
  1.  P46 output JSON exists.
  2.  Production rows remain 37960.
  3.  POWER_LOTTO current-state inventory is documented.
  4.  POWER_LOTTO candidate classification exists.
  5.  No adapter implementation was added (p47_wave4_powerlotto_adapters.py must NOT exist).
  6.  No dry-run rows generated (production rows still 37960).
  7.  Special number semantics are documented in output.
  8.  Adapter bootstrap design is documented.
  9.  Next-phase recommendation exists.
  10. P46 output lists valid classification values.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
P46_JSON = PROJECT_ROOT / "outputs" / "replay" / "p46_powerlotto_expansion_planning_20260524.json"
P46_DOC = PROJECT_ROOT / "docs" / "replay" / "p46_powerlotto_expansion_planning_20260524.md"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
FORBIDDEN_ADAPTER = PROJECT_ROOT / "lottery_api" / "models" / "p47_wave4_powerlotto_adapters.py"

EXPECTED_PRODUCTION_ROWS = 37960
VALID_CLASSIFICATIONS = frozenset(
    {"ready_for_bootstrap", "needs_manual_review", "unsupported", "already_covered"}
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p46_data() -> dict:
    assert P46_JSON.exists(), f"P46 output JSON not found: {P46_JSON}"
    with P46_JSON.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_row_count() -> int:
    assert DB_PATH.exists(), f"Database not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        return cur.fetchone()[0]
    finally:
        conn.close()


# ─── Tests ────────────────────────────────────────────────────────────────────


# 1. P46 output JSON exists
def test_p46_output_json_exists():
    assert P46_JSON.exists(), f"P46 output JSON not found: {P46_JSON}"


# 2. Production rows remain 37960
def test_production_rows_unchanged(db_row_count):
    assert db_row_count == EXPECTED_PRODUCTION_ROWS, (
        f"Expected {EXPECTED_PRODUCTION_ROWS} rows, got {db_row_count}"
    )


# 3. POWER_LOTTO current-state inventory is documented
def test_powerlotto_current_state_inventory_present(p46_data):
    inventory = p46_data.get("current_state_inventory")
    assert inventory is not None, "current_state_inventory key missing from P46 output"
    assert isinstance(inventory, list), "current_state_inventory must be a list"
    assert len(inventory) >= 3, (
        f"Expected at least 3 strategies in inventory, got {len(inventory)}"
    )
    # Each entry must have required fields
    required_fields = {"strategy_id", "lottery_type", "registry_lifecycle",
                       "production_row_count", "row_backed"}
    for entry in inventory:
        missing = required_fields - set(entry.keys())
        assert not missing, f"Entry {entry.get('strategy_id')} missing fields: {missing}"


# 4. POWER_LOTTO candidate classification exists
def test_expansion_candidates_present(p46_data):
    candidates = p46_data.get("expansion_candidates")
    assert candidates is not None, "expansion_candidates key missing from P46 output"
    assert isinstance(candidates, list), "expansion_candidates must be a list"
    assert len(candidates) >= 1, "expansion_candidates must contain at least one entry"
    for c in candidates:
        assert "strategy_id" in c, "Each candidate must have strategy_id"
        assert "classification" in c, "Each candidate must have classification"


# 5. No adapter implementation was added
def test_forbidden_adapter_file_does_not_exist():
    assert not FORBIDDEN_ADAPTER.exists(), (
        f"FORBIDDEN: p47_wave4_powerlotto_adapters.py was created in P46 — "
        f"this is a read-only planning task: {FORBIDDEN_ADAPTER}"
    )


# 6. No dry-run rows generated (production rows still 37960)
def test_no_dry_run_rows_generated(p46_data, db_row_count):
    reported = p46_data.get("production_rows_unchanged")
    assert reported == EXPECTED_PRODUCTION_ROWS, (
        f"P46 JSON reports {reported} rows but expected {EXPECTED_PRODUCTION_ROWS}"
    )
    assert db_row_count == EXPECTED_PRODUCTION_ROWS, (
        f"DB has {db_row_count} rows but P46 must not generate new rows"
    )


# 7. Special number semantics are documented
def test_special_number_semantics_documented(p46_data):
    bootstrap = p46_data.get("bootstrap_design", {})
    assert "second_zone_special" in bootstrap, (
        "bootstrap_design must document second_zone_special"
    )
    assert "special_hit_semantics" in bootstrap, (
        "bootstrap_design must document special_hit_semantics"
    )
    # Verify the semantics describe the 1-8 separate pool
    second_zone = bootstrap["second_zone_special"]
    assert "1-8" in str(second_zone) or "1, 8" in str(second_zone) or "[1,8]" in str(second_zone), (
        f"second_zone_special should reference the 1-8 pool, got: {second_zone}"
    )
    # Verify first zone pool is documented correctly
    pool_constants = bootstrap.get("pool_constants", {})
    assert pool_constants.get("POWER_LOTTO_FIRST_ZONE_POOL") == 38, (
        f"POWER_LOTTO_FIRST_ZONE_POOL should be 38, got: {pool_constants.get('POWER_LOTTO_FIRST_ZONE_POOL')}"
    )
    assert pool_constants.get("POWER_LOTTO_SPECIAL_POOL") == 8, (
        f"POWER_LOTTO_SPECIAL_POOL should be 8, got: {pool_constants.get('POWER_LOTTO_SPECIAL_POOL')}"
    )


# 8. Adapter bootstrap design is documented
def test_adapter_bootstrap_design_documented(p46_data):
    bootstrap = p46_data.get("bootstrap_design")
    assert bootstrap is not None, "bootstrap_design key missing from P46 output"
    required_keys = {
        "first_zone_format", "second_zone_special",
        "hit_count_semantics", "special_hit_semantics",
        "cutoff_semantics", "lifecycle",
        "pool_constants"
    }
    missing = required_keys - set(bootstrap.keys())
    assert not missing, f"bootstrap_design missing required keys: {missing}"
    # Lifecycle must be DRY_RUN
    assert bootstrap.get("lifecycle") == "DRY_RUN", (
        f"bootstrap lifecycle must be DRY_RUN, got: {bootstrap.get('lifecycle')}"
    )


# 9. Next-phase recommendation exists
def test_next_phase_recommendation_exists(p46_data):
    recommendation = p46_data.get("next_phase_recommendation")
    assert recommendation is not None, "next_phase_recommendation missing from P46 output"
    assert isinstance(recommendation, str), "next_phase_recommendation must be a string"
    assert len(recommendation) > 10, "next_phase_recommendation must be non-trivial"
    candidates = p46_data.get("next_phase_candidates")
    assert candidates is not None, "next_phase_candidates missing from P46 output"
    assert isinstance(candidates, list), "next_phase_candidates must be a list"
    assert len(candidates) >= 1, "next_phase_candidates must contain at least one entry"


# 10. P46 output lists valid classification values
def test_candidate_classification_values_valid(p46_data):
    candidates = p46_data.get("expansion_candidates", [])
    for c in candidates:
        classification = c.get("classification")
        assert classification in VALID_CLASSIFICATIONS, (
            f"Strategy {c.get('strategy_id')} has invalid classification: "
            f"'{classification}'. Valid values: {VALID_CLASSIFICATIONS}"
        )


# Additional: Verify 3 ONLINE strategies are in inventory as already_covered
def test_three_online_strategies_in_inventory(p46_data):
    inventory = p46_data.get("current_state_inventory", [])
    online_strategies = [
        e for e in inventory
        if e.get("registry_lifecycle") == "ONLINE"
    ]
    assert len(online_strategies) == 3, (
        f"Expected 3 ONLINE POWER_LOTTO strategies in inventory, "
        f"got {len(online_strategies)}: {[s.get('strategy_id') for s in online_strategies]}"
    )
    expected_online = {"fourier_rhythm_3bet", "power_orthogonal_5bet", "power_precision_3bet"}
    found_ids = {s["strategy_id"] for s in online_strategies}
    assert found_ids == expected_online, (
        f"Expected ONLINE strategies {expected_online}, found {found_ids}"
    )


# Additional: Summary counts match candidate list
def test_candidate_summary_counts_consistent(p46_data):
    summary = p46_data.get("expansion_candidates_summary", {})
    candidates = p46_data.get("expansion_candidates", [])
    # ready_for_bootstrap count in summary should match candidates with that classification
    ready_count = sum(
        1 for c in candidates
        if c.get("classification") == "ready_for_bootstrap"
    )
    reported_ready = summary.get("ready_for_bootstrap", 0)
    assert ready_count == reported_ready, (
        f"Summary reports {reported_ready} ready_for_bootstrap, "
        f"but found {ready_count} in candidates list"
    )


# Additional: P46 doc file exists
def test_p46_doc_file_exists():
    assert P46_DOC.exists(), f"P46 planning doc not found: {P46_DOC}"


# Additional: P46 classification matches expected
def test_p46_classification(p46_data):
    classification = p46_data.get("classification")
    assert classification == "P46_POWERLOTTO_EXPANSION_PLANNING_MERGED_TO_MAIN", (
        f"Unexpected classification: {classification}"
    )
