"""
test_p31a_wave1_daily539_retired_adapter_readiness.py
======================================================
P31A Wave 1 — DAILY_539 Retired Adapter Readiness Tests

Verifies:
  1. Adapter module imports without registry side-effects.
  2. All 5 Wave 1 adapters predict valid DAILY_539 bets from test history.
  3. Rehearsal output JSON exists and passes all invariants.
  4. Readiness output JSON exists with correct status.
  5. Production DB remains at exactly 12460 rows (immutable).
  6. Temp DB has 7500 dry-run rows.
  7. Wave 1 strategies are NOT in _GENERATION_STATUSES.
  8. R1/R2/R3 rehearsal results all pass.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
_PROD_DB    = LOTTERY_API / "data" / "lottery_v2.db"
_TEMP_DB    = Path("/tmp/p31a_temp.db")

_REHEARSAL  = REPO_ROOT / "outputs" / "replay" / "p31a_temp_rehearsal_20260523.json"
_READINESS  = REPO_ROOT / "outputs" / "replay" / "p31a_wave1_daily539_retired_adapter_readiness_20260523.json"

EXPECTED_PROD_ROWS   = 12460
EXPECTED_TEMP_ROWS   = 7500
EXPECTED_STRATEGIES  = 5
WAVE1_STRATEGY_IDS   = frozenset({
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
})


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rehearsal() -> dict:
    assert _REHEARSAL.exists(), f"Rehearsal output not found: {_REHEARSAL}"
    return json.loads(_REHEARSAL.read_text())


@pytest.fixture(scope="module")
def readiness() -> dict:
    assert _READINESS.exists(), f"Readiness output not found: {_READINESS}"
    return json.loads(_READINESS.read_text())


@pytest.fixture(scope="module")
def sample_history() -> list[dict]:
    """Load 200 DAILY_539 draws from production DB as test history."""
    conn = sqlite3.connect(str(_PROD_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT draw, date, numbers FROM draws "
        "WHERE lottery_type='DAILY_539' ORDER BY date ASC LIMIT 200"
    ).fetchall()
    conn.close()
    return [
        {"draw": r["draw"], "date": r["date"],
         "numbers": json.loads(r["numbers"])}
        for r in rows
    ]


# ── Output file tests ─────────────────────────────────────────────────────────

def test_rehearsal_output_exists():
    assert _REHEARSAL.exists()


def test_readiness_output_exists():
    assert _READINESS.exists()


# ── Rehearsal JSON tests ──────────────────────────────────────────────────────

def test_rehearsal_phase(rehearsal):
    assert rehearsal["phase"] == "P31A_WAVE1_DAILY539_RETIRED_ADAPTER_DRY_RUN"


def test_rehearsal_prod_rows_unchanged(rehearsal):
    assert rehearsal["prod_rows_unchanged"] is True


def test_rehearsal_r1_inserted_7500(rehearsal):
    assert rehearsal["r1"]["r1_inserted"] == EXPECTED_TEMP_ROWS


def test_rehearsal_r2_idempotent(rehearsal):
    assert rehearsal["r2"]["r2_idempotent"] is True


def test_rehearsal_r3_rollback_ok(rehearsal):
    assert rehearsal["r3"]["r3_rollback_ok"] is True


def test_rehearsal_all_pass(rehearsal):
    assert rehearsal["all_rehearsals_pass"] is True


def test_rehearsal_total_dry_run_rows(rehearsal):
    assert rehearsal["total_dry_run_rows"] == EXPECTED_TEMP_ROWS


# ── Readiness JSON tests ──────────────────────────────────────────────────────

def test_readiness_phase(readiness):
    assert readiness["phase"] == "P31A_WAVE1_DAILY539_RETIRED_ADAPTER_READINESS"


def test_readiness_status(readiness):
    assert readiness["status"] == "READY_NO_DB_WRITE"


def test_readiness_no_db_write(readiness):
    assert readiness["no_db_write"] is True


def test_readiness_prod_db_unchanged(readiness):
    assert readiness["production_db"]["unchanged"] is True
    assert readiness["production_db"]["dry_run_applied"] is False


def test_readiness_all_wave1_strategies_present(readiness):
    for sid in WAVE1_STRATEGY_IDS:
        assert sid in readiness["strategies"], f"Missing strategy: {sid}"


def test_readiness_all_strategies_lifecycle_retired(readiness):
    for sid, info in readiness["strategies"].items():
        assert info["lifecycle_status"] == "RETIRED", (
            f"{sid}: expected RETIRED, got {info['lifecycle_status']}"
        )


def test_readiness_lifecycle_decision_option_a(readiness):
    sem = readiness["lifecycle_semantics"]
    assert sem["decision"] == "OPTION_A"
    assert sem["label"] == "retired"
    assert sem["replay_available_flag"] is True


def test_readiness_reconstructible_count_zero_under_option_a(readiness):
    spec = readiness["lifecycle_semantics"]["reconstructible_population_spec"]
    assert spec["after_p31b_option_a"] == 0
    assert spec["chosen_option"] == "A"


def test_readiness_p31b_requires_authorization(readiness):
    assert readiness["p31b_apply_requires_authorization"] is True


# ── Production DB immutability ────────────────────────────────────────────────

def test_production_db_row_count():
    """Production DB MUST have exactly 12460 rows after P31A."""
    conn = sqlite3.connect(str(_PROD_DB))
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()
    assert count == EXPECTED_PROD_ROWS, (
        f"Production DB row invariant violated: expected {EXPECTED_PROD_ROWS}, got {count}"
    )


def test_production_db_no_p31a_rows():
    """Production DB must NOT contain any P31A dry-run rows."""
    conn = sqlite3.connect(str(_PROD_DB))
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE source = 'P31A_WAVE1_DRYRUN' OR dry_run = 1"
    ).fetchone()[0]
    conn.close()
    assert count == 0, (
        f"Production DB contains {count} P31A dry-run rows — must be 0"
    )


# ── Temp DB tests ─────────────────────────────────────────────────────────────

def test_temp_db_exists():
    assert _TEMP_DB.exists(), f"Temp DB not found: {_TEMP_DB}"


def test_temp_db_row_count():
    conn = sqlite3.connect(str(_TEMP_DB))
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert count == EXPECTED_TEMP_ROWS, (
        f"Temp DB: expected {EXPECTED_TEMP_ROWS} rows, got {count}"
    )


def test_temp_db_all_dry_run():
    """All temp DB rows must have dry_run=1."""
    conn = sqlite3.connect(str(_TEMP_DB))
    not_dry = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE dry_run != 1"
    ).fetchone()[0]
    conn.close()
    assert not_dry == 0


def test_temp_db_strategy_counts():
    """Each of the 5 strategies must have exactly 1500 rows in temp DB."""
    conn = sqlite3.connect(str(_TEMP_DB))
    rows = conn.execute(
        "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays "
        "GROUP BY strategy_id"
    ).fetchall()
    conn.close()
    counts = {r[0]: r[1] for r in rows}
    for sid in WAVE1_STRATEGY_IDS:
        assert counts.get(sid, 0) == 1500, (
            f"{sid}: expected 1500 rows in temp DB, got {counts.get(sid, 0)}"
        )


def test_temp_db_all_lottery_type_daily539():
    conn = sqlite3.connect(str(_TEMP_DB))
    bad = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE lottery_type != 'DAILY_539'"
    ).fetchone()[0]
    conn.close()
    assert bad == 0


def test_temp_db_predicted_numbers_valid():
    """Sample: check 50 random predicted_numbers rows are valid DAILY_539 bets."""
    conn = sqlite3.connect(str(_TEMP_DB))
    rows = conn.execute(
        "SELECT strategy_id, target_draw, predicted_numbers "
        "FROM strategy_prediction_replays "
        "WHERE replay_status = 'PREDICTED' LIMIT 50"
    ).fetchall()
    conn.close()
    for sid, draw, nums_json in rows:
        nums = json.loads(nums_json)
        assert len(nums) == 5, f"{sid}/{draw}: expected 5 numbers, got {len(nums)}"
        assert len(set(nums)) == 5, f"{sid}/{draw}: duplicate numbers {nums}"
        assert all(1 <= n <= 39 for n in nums), f"{sid}/{draw}: out-of-range {nums}"


def test_temp_db_no_predicted_special():
    """DAILY_539 has no special number — predicted_special must be NULL."""
    conn = sqlite3.connect(str(_TEMP_DB))
    bad = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE predicted_special IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    assert bad == 0


# ── Adapter unit tests ────────────────────────────────────────────────────────

def test_adapters_import_no_registry_sideeffect():
    """Importing adapter module must NOT mutate replay_strategy_registry._ALL_ADAPTERS."""
    import importlib
    from lottery_api.models import replay_strategy_registry as reg

    before_count = len(reg._ALL_ADAPTERS)

    importlib.import_module("lottery_api.models.p31a_wave1_retired_adapters")

    after_count = len(reg._ALL_ADAPTERS)
    assert after_count == before_count, (
        f"Importing P31A adapters changed _ALL_ADAPTERS from {before_count} to {after_count}"
    )


def test_wave1_strategy_ids_not_in_registry():
    """Wave 1 strategy IDs must NOT appear in the main _REGISTRY (ONLINE-only dict)."""
    from lottery_api.models.replay_strategy_registry import _REGISTRY
    registry_ids = set(_REGISTRY.keys())
    for sid in WAVE1_STRATEGY_IDS:
        assert sid not in registry_ids, (
            f"{sid} should NOT be in production _REGISTRY (must remain RETIRED)"
        )


def test_all_adapters_lifecycle_retired(sample_history):
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTERS
    for adapter in WAVE1_ADAPTERS:
        assert adapter.meta.lifecycle_status == "RETIRED"


def test_all_adapters_predict_valid_bet(sample_history):
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTERS
    for adapter in WAVE1_ADAPTERS:
        history = sample_history[:150]
        numbers, special = adapter.get_one_bet(history, "DAILY_539")
        assert len(numbers) == 5, f"{adapter.meta.strategy_id}: expected 5 numbers"
        assert len(set(numbers)) == 5, f"{adapter.meta.strategy_id}: duplicates"
        assert all(1 <= n <= 39 for n in numbers), f"{adapter.meta.strategy_id}: out of range"
        assert special is None, f"{adapter.meta.strategy_id}: expected no special"


def test_adapters_refuse_wrong_lottery_type(sample_history):
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTERS
    for adapter in WAVE1_ADAPTERS:
        with pytest.raises(ValueError, match="does not support"):
            adapter.get_one_bet(sample_history[:150], "POWER_LOTTO")


def test_adapters_refuse_insufficient_history():
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTERS
    tiny_history = [{"draw": i, "date": "2026/01/01", "numbers": [1, 2, 3, 4, 5]}
                    for i in range(5)]
    for adapter in WAVE1_ADAPTERS:
        with pytest.raises(ValueError, match="needs"):
            adapter.get_one_bet(tiny_history, "DAILY_539")
