"""
test_p47_powerlotto_wave4_dryrun_rehearsal.py
=============================================
P47 contract tests for POWER_LOTTO Wave 4 dry-run + temp DB rehearsal.

Verifies:
  1.  Exactly 3 Wave 4 POWER_LOTTO strategies in output.
  2.  No BIG_LOTTO strategies included.
  3.  No DAILY_539 strategies included.
  4.  Total dry-run rows = 4500.
  5.  Each strategy has exactly 1500 rows.
  6.  All rows have lottery_type = "POWER_LOTTO".
  7.  All predicted_numbers lists have length = 6.
  8.  All predicted numbers are in range [1, 38].
  9.  All predicted_numbers have no duplicates.
  10. All predicted_special are in range [1, 8].
  11. All rows have lifecycle = "DRY_RUN".
  12. hit_count == len(hit_numbers) for all rows.
  13. special_hit is 0 or 1 for all rows.
  14. prediction_cutoff_date < draw_date (no future leakage).
  15. R1: temp rehearsal inserts 4500 rows.
  16. R2: duplicate rerun inserts 0 rows.
  17. R3: rollback PASS, production rows remain 37960.
  18. Production DB row count unchanged at 37960.
  19. Output JSON classification is READY.
  20. Adapter module contains no production registry side-effects.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
P47_JSON = PROJECT_ROOT / "outputs" / "replay" / "p47_powerlotto_wave4_dryrun_rehearsal_20260524.json"
P47_REHEARSAL_JSON = PROJECT_ROOT / "outputs" / "replay" / "p47_temp_rehearsal_20260524.json"
P47_DOC = PROJECT_ROOT / "docs" / "replay" / "p47_powerlotto_wave4_dryrun_rehearsal_20260524.md"
P47_ADAPTER = PROJECT_ROOT / "lottery_api" / "models" / "p47_wave4_powerlotto_adapters.py"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_PRODUCTION_ROWS = 37960
# Updated after P48 POWER_LOTTO Wave 4 production apply (4500 rows, 2026-05-24)
POST_P48_PRODUCTION_ROWS = 42460
WAVE4_STRATEGY_IDS = frozenset({
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
})
EXPECTED_ROWS_PER_STRATEGY = 1500
EXPECTED_TOTAL_ROWS = 4500
FORBIDDEN_LOTTERY_TYPES = frozenset({"BIG_LOTTO", "DAILY_539"})

BIGLOTTO_STRATEGY_PREFIXES = (
    "markov_single_biglotto", "markov_2bet_biglotto",
    "bet2_fourier_expansion_biglotto", "fourier30_markov30_biglotto",
    "cold_complement_biglotto", "coldpool15_biglotto",
)
DAILY539_STRATEGY_PREFIXES = (
    "acb_", "f4cold_", "markov_1bet_539", "midfreq_acb_",
    "acb_markov_", "p0b_539", "p0c_539",
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p47_data() -> dict:
    assert P47_JSON.exists(), f"P47 output JSON not found: {P47_JSON}"
    with P47_JSON.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p47_rehearsal_data() -> dict:
    assert P47_REHEARSAL_JSON.exists(), f"P47 rehearsal JSON not found: {P47_REHEARSAL_JSON}"
    with P47_REHEARSAL_JSON.open() as f:
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


# ─── Adapter module tests ─────────────────────────────────────────────────────

# 20. Adapter module exists
def test_p47_adapter_module_exists():
    assert P47_ADAPTER.exists(), f"Adapter file not found: {P47_ADAPTER}"


# 20. Adapter has no production registry side-effects
def test_p47_adapter_not_in_registry():
    """The P47 adapter must NOT be imported by replay_strategy_registry."""
    registry_path = PROJECT_ROOT / "lottery_api" / "models" / "replay_strategy_registry.py"
    if registry_path.exists():
        content = registry_path.read_text()
        assert "p47_wave4_powerlotto_adapters" not in content, (
            "P47 adapter must NOT be imported in replay_strategy_registry.py"
        )


# ─── Output file tests ────────────────────────────────────────────────────────

# Output JSON exists
def test_p47_output_json_exists():
    assert P47_JSON.exists(), f"P47 output JSON not found: {P47_JSON}"


# Rehearsal JSON exists
def test_p47_rehearsal_json_exists():
    assert P47_REHEARSAL_JSON.exists(), f"P47 rehearsal JSON not found: {P47_REHEARSAL_JSON}"


# ─── Strategy count and identity tests ────────────────────────────────────────

# 1. Exactly 3 Wave 4 POWER_LOTTO strategies
def test_exactly_3_wave4_strategies(p47_data):
    strategies = p47_data.get("strategies", [])
    assert len(strategies) == 3, f"Expected 3 strategies, got {len(strategies)}"
    strategy_ids = {s["strategy_id"] for s in strategies}
    assert strategy_ids == WAVE4_STRATEGY_IDS, (
        f"Strategy IDs mismatch: got {strategy_ids}, expected {WAVE4_STRATEGY_IDS}"
    )


# 2. No BIG_LOTTO strategies
def test_no_biglotto_strategies(p47_data):
    strategies = p47_data.get("strategies", [])
    for s in strategies:
        sid = s["strategy_id"]
        assert not any(sid.startswith(p) for p in BIGLOTTO_STRATEGY_PREFIXES), (
            f"BIG_LOTTO strategy found in P47 output: {sid}"
        )
        # Also check lottery type if present
        lt = s.get("lottery_type", "POWER_LOTTO")
        assert lt != "BIG_LOTTO", f"BIG_LOTTO lottery_type found: {s}"


# 3. No DAILY_539 strategies
def test_no_daily539_strategies(p47_data):
    strategies = p47_data.get("strategies", [])
    for s in strategies:
        sid = s["strategy_id"]
        assert not any(sid.startswith(p) for p in DAILY539_STRATEGY_PREFIXES), (
            f"DAILY_539 strategy found in P47 output: {sid}"
        )
        lt = s.get("lottery_type", "POWER_LOTTO")
        assert lt != "DAILY_539", f"DAILY_539 lottery_type found: {s}"


# ─── Row count tests ──────────────────────────────────────────────────────────

# 4. Total dry-run rows = 4500
def test_total_dryrun_rows(p47_data):
    total = p47_data.get("total_dryrun_rows")
    assert total == EXPECTED_TOTAL_ROWS, (
        f"Expected {EXPECTED_TOTAL_ROWS} total rows, got {total}"
    )


# 5. Each strategy has exactly 1500 rows
def test_each_strategy_has_1500_rows(p47_data):
    strategies = p47_data.get("strategies", [])
    for s in strategies:
        assert s["row_count"] == EXPECTED_ROWS_PER_STRATEGY, (
            f"Strategy {s['strategy_id']}: expected {EXPECTED_ROWS_PER_STRATEGY} rows, "
            f"got {s['row_count']}"
        )


# ─── Format validation tests (from rehearsal JSON) ────────────────────────────

# 6. All rows have lottery_type = "POWER_LOTTO"
def test_all_rows_powerlotto_type(p47_rehearsal_data):
    schema = p47_rehearsal_data.get("schema_validation", {})
    assert schema.get("valid") is True, (
        f"Schema validation failed: {schema.get('errors', [])[:5]}"
    )


# 7+8+9. predicted_numbers: length=6, in [1,38], no duplicates
def test_powerlotto_format_validation(p47_data, p47_rehearsal_data):
    fmt = p47_data.get("powerlotto_format_validation", {})
    assert fmt.get("numbers_per_prediction") == 6
    assert fmt.get("first_zone_range") == "1-38"
    assert fmt.get("no_duplicates") is True
    assert fmt.get("format_ok") is True, "POWER_LOTTO first-zone format validation failed"


# 10. All predicted_special are in range [1, 8]
def test_special_zone_format(p47_data, p47_rehearsal_data):
    fmt = p47_data.get("powerlotto_format_validation", {})
    assert fmt.get("special_zone_range") == "1-8"
    assert fmt.get("special_format_ok") is True, "Special zone format validation failed"


# 11. All rows have lifecycle = "DRY_RUN"
def test_all_rows_lifecycle_dryrun(p47_data):
    lifecycle_info = p47_data.get("lifecycle_semantics", {})
    assert lifecycle_info.get("all_rows_lifecycle") == "DRY_RUN"
    assert lifecycle_info.get("online_rows") == 0
    assert lifecycle_info.get("retired_rows") == 0
    strategies = p47_data.get("strategies", [])
    for s in strategies:
        assert s.get("lifecycle") == "DRY_RUN", (
            f"Strategy {s['strategy_id']} has lifecycle={s.get('lifecycle')}, expected DRY_RUN"
        )


# 12. hit_count == len(hit_numbers) for all rows
def test_hit_count_consistency(p47_rehearsal_data):
    schema = p47_rehearsal_data.get("schema_validation", {})
    assert schema.get("valid") is True, (
        f"hit_count consistency check failed: {schema.get('errors', [])[:5]}"
    )


# 13. special_hit is 0 or 1 for all rows
def test_special_hit_range(p47_rehearsal_data):
    schema = p47_rehearsal_data.get("schema_validation", {})
    assert schema.get("valid") is True, (
        "special_hit range check failed — schema_validation errors found"
    )


# 14. prediction_cutoff_date < draw_date (no future leakage)
def test_no_future_leakage(p47_data, p47_rehearsal_data):
    leakage = p47_rehearsal_data.get("leakage_check", {})
    assert leakage.get("pass") is True, (
        f"Data leakage violations: {leakage.get('violations', [])}"
    )
    assert leakage.get("violation_count", 1) == 0


# ─── Temp rehearsal tests ─────────────────────────────────────────────────────

# 15. R1: temp rehearsal inserts 4500 rows
def test_r1_insert_count(p47_data, p47_rehearsal_data):
    tr = p47_data.get("temp_rehearsal", {})
    assert tr.get("R1_insert_count") == EXPECTED_TOTAL_ROWS, (
        f"R1 expected {EXPECTED_TOTAL_ROWS} inserts, got {tr.get('R1_insert_count')}"
    )
    r1 = p47_rehearsal_data.get("r1", {})
    assert r1.get("r1_ok") is True, f"R1 not ok: {r1}"


# 16. R2: duplicate rerun inserts 0 rows
def test_r2_duplicate_count_zero(p47_data, p47_rehearsal_data):
    tr = p47_data.get("temp_rehearsal", {})
    assert tr.get("R2_duplicate_count") == 0, (
        f"R2 expected 0 duplicates, got {tr.get('R2_duplicate_count')}"
    )
    r2 = p47_rehearsal_data.get("r2", {})
    assert r2.get("r2_idempotent") is True, f"R2 not idempotent: {r2}"


# 17. R3: rollback PASS
def test_r3_rollback_pass(p47_data, p47_rehearsal_data):
    tr = p47_data.get("temp_rehearsal", {})
    assert tr.get("R3_rollback") == "PASS", f"R3 rollback not PASS: {tr.get('R3_rollback')}"
    r3 = p47_rehearsal_data.get("r3", {})
    assert r3.get("r3_rollback_ok") is True, f"R3 rollback not ok: {r3}"
    assert r3.get("r3_after") == 0, f"R3 expected 0 rows after rollback, got {r3.get('r3_after')}"


# ─── Production invariant tests ───────────────────────────────────────────────

# 18. Production DB row count is 42460 after P48 apply (P47 dryrun did not mutate the DB)
def test_production_rows_unchanged(db_row_count):
    assert db_row_count == POST_P48_PRODUCTION_ROWS, (
        f"Expected {POST_P48_PRODUCTION_ROWS} rows, got {db_row_count}"
    )


def test_production_rows_before_after_match(p47_data):
    before = p47_data.get("production_rows_before")
    after = p47_data.get("production_rows_after")
    assert before == EXPECTED_PRODUCTION_ROWS, (
        f"production_rows_before expected {EXPECTED_PRODUCTION_ROWS}, got {before}"
    )
    assert after == EXPECTED_PRODUCTION_ROWS, (
        f"production_rows_after expected {EXPECTED_PRODUCTION_ROWS}, got {after}"
    )


# ─── Classification and readiness tests ──────────────────────────────────────

# 19. Output JSON classification is READY
def test_classification_ready(p47_data):
    classification = p47_data.get("classification")
    assert classification == "P47_POWERLOTTO_WAVE4_DRYRUN_REHEARSAL_READY", (
        f"Expected READY classification, got {classification}"
    )


def test_all_rehearsals_pass(p47_data, p47_rehearsal_data):
    assert p47_data.get("all_rehearsals_pass") is True, (
        "all_rehearsals_pass is False in dryrun output"
    )
    assert p47_rehearsal_data.get("all_rehearsals_pass") is True, (
        "all_rehearsals_pass is False in rehearsal output"
    )


def test_production_apply_readiness(p47_data):
    readiness = p47_data.get("production_apply_readiness", {})
    assert readiness.get("ready") is True, f"P48 readiness not ready: {readiness}"
    assert readiness.get("requires_p48_authorization") is True, (
        "P48 authorization gate must be explicit"
    )
    assert readiness.get("blockers") == [], f"Unexpected blockers: {readiness.get('blockers')}"


# ─── Semantics tests ──────────────────────────────────────────────────────────

def test_hit_count_semantics(p47_data):
    assert p47_data.get("hit_count_semantics") == "first_zone_only", (
        "hit_count_semantics must be 'first_zone_only'"
    )


def test_special_hit_semantics(p47_data):
    assert p47_data.get("special_hit_semantics") == "predicted_special == actual_special", (
        "special_hit_semantics must be 'predicted_special == actual_special'"
    )


def test_first_zone_format(p47_data):
    assert p47_data.get("first_zone_format") == "6 unique ints in [1,38]", (
        f"first_zone_format mismatch: {p47_data.get('first_zone_format')}"
    )


def test_special_zone_format_string(p47_data):
    assert p47_data.get("special_zone_format") == "1 int in [1,8]", (
        f"special_zone_format mismatch: {p47_data.get('special_zone_format')}"
    )


# ─── Adapter unit tests ───────────────────────────────────────────────────────

def _make_fake_draws(n: int) -> list:
    """Generate n fake POWER_LOTTO draws for unit testing."""
    import random
    rng = random.Random(42)
    draws = []
    for i in range(n):
        numbers = sorted(rng.sample(range(1, 39), 6))
        special = rng.randint(1, 8)
        draws.append({
            "draw": str(97000001 + i),
            "date": f"2008/{1 + (i // 30):02d}/{1 + (i % 28):02d}",
            "numbers": numbers,
            "special": special,
        })
    return draws


def test_adapter_pp3_freqort_output_format():
    """pp3_freqort_4bet: output must be 6 unique ints in [1,38]."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import Pp3FreqOrt4BetAdapter
    adapter = Pp3FreqOrt4BetAdapter()
    history = _make_fake_draws(200)
    numbers, special = adapter.get_one_bet(history, "POWER_LOTTO")
    assert len(numbers) == 6
    assert len(set(numbers)) == 6
    assert all(1 <= n <= 38 for n in numbers)
    assert 1 <= special <= 8


def test_adapter_midfreq_fourier_mk3bet_output_format():
    """midfreq_fourier_mk_3bet: output must be 6 unique ints in [1,38]."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import MidFreqFourierMk3BetAdapter
    adapter = MidFreqFourierMk3BetAdapter()
    history = _make_fake_draws(100)
    numbers, special = adapter.get_one_bet(history, "POWER_LOTTO")
    assert len(numbers) == 6
    assert len(set(numbers)) == 6
    assert all(1 <= n <= 38 for n in numbers)
    assert 1 <= special <= 8


def test_adapter_midfreq_fourier_2bet_output_format():
    """midfreq_fourier_2bet: output must be 6 unique ints in [1,38]."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import MidFreqFourier2BetAdapter
    adapter = MidFreqFourier2BetAdapter()
    history = _make_fake_draws(50)
    numbers, special = adapter.get_one_bet(history, "POWER_LOTTO")
    assert len(numbers) == 6
    assert len(set(numbers)) == 6
    assert all(1 <= n <= 38 for n in numbers)
    assert 1 <= special <= 8


def test_adapter_rejects_biglotto_type():
    """Adapters must reject BIG_LOTTO lottery_type."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import Pp3FreqOrt4BetAdapter
    adapter = Pp3FreqOrt4BetAdapter()
    history = _make_fake_draws(100)
    with pytest.raises(ValueError, match="does not support"):
        adapter.get_one_bet(history, "BIG_LOTTO")


def test_adapter_rejects_daily539_type():
    """Adapters must reject DAILY_539 lottery_type."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import MidFreqFourier2BetAdapter
    adapter = MidFreqFourier2BetAdapter()
    history = _make_fake_draws(50)
    with pytest.raises(ValueError, match="does not support"):
        adapter.get_one_bet(history, "DAILY_539")


def test_adapter_rejects_insufficient_history():
    """Adapters must raise ValueError when history < min_history."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import MidFreqFourierMk3BetAdapter
    adapter = MidFreqFourierMk3BetAdapter()
    with pytest.raises(ValueError, match="needs"):
        adapter.get_one_bet([], "POWER_LOTTO")


def test_all_adapter_lifecycle_is_dryrun():
    """All Wave 4 adapters must have lifecycle_status = DRY_RUN."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTERS
    for adapter in WAVE4_ADAPTERS:
        assert adapter.meta.lifecycle_status == "DRY_RUN", (
            f"{adapter.meta.strategy_id}: lifecycle_status={adapter.meta.lifecycle_status}, "
            f"expected DRY_RUN"
        )


def test_wave4_strategy_ids_complete():
    """WAVE4_ADAPTERS must contain exactly the 3 expected strategy IDs."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTERS, WAVE4_STRATEGY_IDS
    adapter_ids = frozenset(a.meta.strategy_id for a in WAVE4_ADAPTERS)
    assert adapter_ids == WAVE4_STRATEGY_IDS, (
        f"Adapter IDs {adapter_ids} != expected {WAVE4_STRATEGY_IDS}"
    )
