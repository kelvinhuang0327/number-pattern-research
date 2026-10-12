"""
P36: Wave 2 DAILY_539 Dry-Run + Temp Rehearsal — Verification Tests

Tests verify:
1. Exactly 6 Wave 2 DAILY_539 candidates included (by strategy_id)
2. No P31B Wave 1 strategies included
3. No BIG_LOTTO strategies included
4. 9000 dry-run rows generated total
5. Each strategy has exactly 1500 rows
6. All rows have lottery_type == "DAILY_539"
7. All rows have lifecycle != "ONLINE"
8. predicted_numbers are lists of exactly 5 unique ints in [1,39]
9. hit_count == len(hit_numbers) for all rows
10. R1: temp rehearsal inserts 9000 rows
11. R2: duplicate rerun inserts 0 rows
12. R3: rollback PASS
13. Production DB row count unchanged at 19960
"""

import json
import os
import sqlite3
import pytest

# ── paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P36_JSON = os.path.join(REPO_ROOT, "outputs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.json")
P36_REHEARSAL_JSON = os.path.join(REPO_ROOT, "outputs/replay/p36_temp_rehearsal_20260523.json")
P36_DOC = os.path.join(REPO_ROOT, "docs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.md")
DB_PATH = os.path.join(REPO_ROOT, "lottery_api/data/lottery_v2.db")
TEMP_DB_PATH = "/tmp/p36_temp.db"

EXPECTED_PROD_ROWS = 19960
EXPECTED_TOTAL_ROWS = 9000
EXPECTED_ROWS_PER_STRATEGY = 1500
EXPECTED_STRATEGIES_COUNT = 6

WAVE2_STRATEGY_IDS = {
    "markov_1bet_539",
    "acb_single_539",
    "zone_gap_3bet_539",
    "539_3bet_orthogonal",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
}

# P31B Wave 1 strategies — must NOT appear in Wave 2
WAVE1_STRATEGY_IDS = {
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
}

# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p36_data():
    with open(P36_JSON) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def p36_rehearsal():
    with open(P36_REHEARSAL_JSON) as f:
        return json.load(f)

@pytest.fixture(scope="module")
def adapter_module():
    import sys
    sys.path.insert(0, REPO_ROOT)
    from lottery_api.models.p36_wave2_daily539_adapters import (
        WAVE2_ADAPTERS, WAVE2_STRATEGY_IDS as MODULE_IDS, generate_dryrun_rows
    )
    return WAVE2_ADAPTERS, MODULE_IDS, generate_dryrun_rows


# ── TestOutputArtifactsExist ──────────────────────────────────────────────────

class TestOutputArtifactsExist:
    """Verify all required output artifacts exist."""

    def test_p36_json_exists(self):
        assert os.path.exists(P36_JSON), f"Missing: {P36_JSON}"

    def test_p36_rehearsal_json_exists(self):
        assert os.path.exists(P36_REHEARSAL_JSON), f"Missing: {P36_REHEARSAL_JSON}"

    def test_p36_doc_exists(self):
        assert os.path.exists(P36_DOC), f"Missing: {P36_DOC}"


# ── TestP36MainOutput ─────────────────────────────────────────────────────────

class TestP36MainOutput:
    """Verify the main dry-run output JSON."""

    def test_p36_version(self, p36_data):
        assert p36_data.get("p36_version") == "20260523"

    def test_wave_is_2(self, p36_data):
        assert p36_data.get("wave") == 2

    def test_lottery_type(self, p36_data):
        assert p36_data.get("lottery_type") == "DAILY_539"

    def test_total_dryrun_rows(self, p36_data):
        assert p36_data["total_dryrun_rows"] == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} total rows, got {p36_data['total_dryrun_rows']}"
        )

    def test_exactly_6_strategies(self, p36_data):
        strategies = p36_data["strategies"]
        assert len(strategies) == EXPECTED_STRATEGIES_COUNT, (
            f"Expected {EXPECTED_STRATEGIES_COUNT} strategies, got {len(strategies)}"
        )

    def test_strategy_ids_match_wave2(self, p36_data):
        ids = {s["strategy_id"] for s in p36_data["strategies"]}
        assert ids == WAVE2_STRATEGY_IDS, (
            f"Strategy IDs mismatch. Expected {WAVE2_STRATEGY_IDS}, got {ids}"
        )

    def test_each_strategy_has_1500_rows(self, p36_data):
        for s in p36_data["strategies"]:
            assert s["row_count"] == EXPECTED_ROWS_PER_STRATEGY, (
                f"{s['strategy_id']}: expected {EXPECTED_ROWS_PER_STRATEGY} rows, "
                f"got {s['row_count']}"
            )

    def test_all_strategies_lifecycle_dryrun(self, p36_data):
        for s in p36_data["strategies"]:
            assert s["lifecycle"] == "DRY_RUN", (
                f"{s['strategy_id']}: lifecycle={s['lifecycle']} expected DRY_RUN"
            )

    def test_no_online_lifecycle(self, p36_data):
        for s in p36_data["strategies"]:
            assert s["lifecycle"] != "ONLINE", (
                f"{s['strategy_id']}: lifecycle=ONLINE is forbidden in P36"
            )

    def test_production_rows_before(self, p36_data):
        assert p36_data["production_rows_before"] == EXPECTED_PROD_ROWS

    def test_production_rows_after(self, p36_data):
        assert p36_data["production_rows_after"] == EXPECTED_PROD_ROWS

    def test_classification_ready(self, p36_data):
        assert p36_data["classification"] == "P36_WAVE2_DAILY539_DRYRUN_REHEARSAL_READY"

    def test_all_rehearsals_pass(self, p36_data):
        assert p36_data["all_rehearsals_pass"] is True


# ── TestP36TempRehearsal ──────────────────────────────────────────────────────

class TestP36TempRehearsal:
    """Verify R1/R2/R3 temp rehearsal results."""

    def test_r1_insert_count(self, p36_data):
        r = p36_data["temp_rehearsal"]
        assert r["R1_insert_count"] == EXPECTED_TOTAL_ROWS, (
            f"R1: expected {EXPECTED_TOTAL_ROWS} inserts, got {r['R1_insert_count']}"
        )

    def test_r2_duplicate_count(self, p36_data):
        r = p36_data["temp_rehearsal"]
        assert r["R2_duplicate_count"] == 0, (
            f"R2: expected 0 duplicate inserts, got {r['R2_duplicate_count']}"
        )

    def test_r3_rollback_pass(self, p36_data):
        r = p36_data["temp_rehearsal"]
        assert r["R3_rollback"] == "PASS", (
            f"R3: expected PASS, got {r['R3_rollback']}"
        )

    def test_rehearsal_r1_ok(self, p36_rehearsal):
        assert p36_rehearsal["r1"]["r1_ok"] is True

    def test_rehearsal_r2_idempotent(self, p36_rehearsal):
        assert p36_rehearsal["r2"]["r2_idempotent"] is True

    def test_rehearsal_r3_rollback_ok(self, p36_rehearsal):
        assert p36_rehearsal["r3"]["r3_rollback_ok"] is True

    def test_rehearsal_all_pass(self, p36_rehearsal):
        assert p36_rehearsal["all_rehearsals_pass"] is True


# ── TestNoWave1Strategies ─────────────────────────────────────────────────────

class TestNoWave1Strategies:
    """Ensure no P31B Wave 1 strategies are included in Wave 2."""

    def test_no_wave1_in_strategy_list(self, p36_data):
        ids = {s["strategy_id"] for s in p36_data["strategies"]}
        overlap = ids & WAVE1_STRATEGY_IDS
        assert not overlap, (
            f"Wave 1 strategies found in Wave 2 output: {overlap}"
        )

    def test_wave2_module_no_wave1(self, adapter_module):
        _, module_ids, _ = adapter_module
        overlap = module_ids & WAVE1_STRATEGY_IDS
        assert not overlap, (
            f"Wave 1 strategy IDs in module: {overlap}"
        )


# ── TestNoBigLottoStrategies ─────────────────────────────────────────────────

class TestNoBigLottoStrategies:
    """Ensure no BIG_LOTTO strategies are included."""

    BIG_LOTTO_KEYWORDS = {
        "biglotto", "big_lotto", "markov_2bet_biglotto", "markov_single_biglotto",
        "fourier30_markov30_biglotto", "cold_complement_biglotto", "coldpool15_biglotto",
    }

    def test_no_biglotto_strategy_ids(self, p36_data):
        ids = {s["strategy_id"].lower() for s in p36_data["strategies"]}
        overlap = {sid for sid in ids if "biglotto" in sid or "big_lotto" in sid}
        assert not overlap, f"BIG_LOTTO strategies found: {overlap}"

    def test_lottery_type_is_daily_539_only(self, p36_data):
        assert p36_data.get("lottery_type") == "DAILY_539"


# ── TestAdapterModule ─────────────────────────────────────────────────────────

class TestAdapterModule:
    """Verify the adapter module properties."""

    def test_wave2_adapter_count(self, adapter_module):
        adapters, _, _ = adapter_module
        assert len(adapters) == EXPECTED_STRATEGIES_COUNT, (
            f"Expected {EXPECTED_STRATEGIES_COUNT} adapters, got {len(adapters)}"
        )

    def test_wave2_adapter_strategy_ids(self, adapter_module):
        adapters, _, _ = adapter_module
        ids = {a.meta.strategy_id for a in adapters}
        assert ids == WAVE2_STRATEGY_IDS

    def test_all_adapters_lifecycle_dryrun(self, adapter_module):
        adapters, _, _ = adapter_module
        for a in adapters:
            assert a.meta.lifecycle_status == "DRY_RUN", (
                f"{a.meta.strategy_id}: lifecycle_status={a.meta.lifecycle_status}"
            )

    def test_all_adapters_support_daily539(self, adapter_module):
        adapters, _, _ = adapter_module
        for a in adapters:
            assert "DAILY_539" in a.meta.supported_lottery_types

    def test_module_strategy_ids_match(self, adapter_module):
        _, module_ids, _ = adapter_module
        assert module_ids == WAVE2_STRATEGY_IDS


# ── TestDryRunRowGeneration ───────────────────────────────────────────────────

class TestDryRunRowGeneration:
    """Verify dry-run row content using the adapter module directly."""

    @pytest.fixture(scope="class")
    def sample_rows(self, adapter_module):
        """Generate a small batch of rows for schema verification (50 draws)."""
        import sys
        sys.path.insert(0, REPO_ROOT)
        import sqlite3 as _sqlite3
        import json as _json

        _, _, generate_dryrun_rows = adapter_module

        # Load minimal draws
        conn = _sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws "
            "WHERE lottery_type = 'DAILY_539' "
            "ORDER BY date ASC, CAST(draw AS INTEGER) ASC"
        ).fetchall()
        conn.close()

        all_draws = []
        for r in rows:
            nums = _json.loads(r[2]) if isinstance(r[2], str) else r[2]
            all_draws.append({
                "draw": r[0],
                "date": r[1],
                "numbers": [int(n) for n in nums],
            })

        # Generate 50 rows per strategy for fast schema test
        return generate_dryrun_rows(all_draws, rows_per_strategy=50)

    def test_sample_total_rows(self, sample_rows):
        assert len(sample_rows) == 50 * EXPECTED_STRATEGIES_COUNT

    def test_all_rows_lottery_type_daily539(self, sample_rows):
        bad = [r for r in sample_rows if r.get("lottery_type") != "DAILY_539"]
        assert not bad, f"{len(bad)} rows have wrong lottery_type"

    def test_all_rows_lifecycle_not_online(self, sample_rows):
        bad = [r for r in sample_rows if r.get("lifecycle") == "ONLINE"]
        assert not bad, f"{len(bad)} rows have lifecycle=ONLINE"

    def test_all_rows_is_retired_false(self, sample_rows):
        bad = [r for r in sample_rows if r.get("is_retired") is not False and r.get("is_retired") != 0]
        assert not bad, f"{len(bad)} rows have is_retired=True"

    def test_predicted_numbers_format(self, sample_rows):
        predicted_rows = [r for r in sample_rows if r.get("replay_status") == "PREDICTED"]
        assert len(predicted_rows) > 0, "No PREDICTED rows found"
        for r in predicted_rows:
            pred = r.get("predicted_numbers")
            assert pred is not None, f"predicted_numbers is None for {r['strategy_id']}"
            assert len(pred) == 5, (
                f"{r['strategy_id']}: predicted_numbers len={len(pred)} expected 5"
            )
            assert len(set(pred)) == 5, (
                f"{r['strategy_id']}: duplicate predicted_numbers {pred}"
            )
            assert all(1 <= n <= 39 for n in pred), (
                f"{r['strategy_id']}: out-of-range predicted_numbers {pred}"
            )

    def test_hit_count_consistency(self, sample_rows):
        predicted_rows = [r for r in sample_rows if r.get("replay_status") == "PREDICTED"]
        for r in predicted_rows:
            hit_nums = r.get("hit_numbers", [])
            hit_count = r.get("hit_count", 0)
            assert hit_count == len(hit_nums), (
                f"{r['strategy_id']}: hit_count={hit_count} != len(hit_numbers)={len(hit_nums)}"
            )

    def test_no_biglotto_rows(self, sample_rows):
        bad = [r for r in sample_rows if r.get("lottery_type") != "DAILY_539"]
        assert not bad, f"Non-DAILY_539 rows found: {[r['lottery_type'] for r in bad]}"

    def test_strategy_ids_all_wave2(self, sample_rows):
        ids = {r["strategy_id"] for r in sample_rows}
        unknown = ids - WAVE2_STRATEGY_IDS
        assert not unknown, f"Unknown strategy IDs: {unknown}"

    def test_no_wave1_strategy_ids(self, sample_rows):
        ids = {r["strategy_id"] for r in sample_rows}
        wave1_found = ids & WAVE1_STRATEGY_IDS
        assert not wave1_found, f"Wave 1 strategies in rows: {wave1_found}"


# ── TestProductionDbUnchanged ─────────────────────────────────────────────────

class TestProductionDbUnchanged:
    """
    Verify production DB state after P36 dry-run rehearsal.

    NOTE: After P37 production apply, the production DB has 28960 rows
    (19960 + 9000 Wave 2 rows). These tests are updated to reflect that
    P36 kept production unchanged at 19960, and P37 subsequently applied
    the rows. The P37 test file (test_p37_wave2_daily539_production_apply.py)
    covers the post-P37 state.
    """

    def test_production_rows_after_p37_apply(self):
        """After P37 apply, production DB should have 28960 rows (19960 + 9000)."""
        conn = sqlite3.connect(DB_PATH)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        # P36 kept production at 19960; P37 has since applied 9000 more rows
        # to reach 28960. Either state is acceptable here.
        assert count in (EXPECTED_PROD_ROWS, 28960), (
            f"Production DB: unexpected row count {count} "
            f"(expected {EXPECTED_PROD_ROWS} pre-P37 or 28960 post-P37)"
        )

    def test_wave2_rows_in_production_are_from_p37(self):
        """If Wave 2 rows exist in production, they must belong to P37 controlled_apply_id."""
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute(
                "SELECT controlled_apply_id, COUNT(*) as cnt "
                "FROM strategy_prediction_replays "
                "WHERE strategy_id IN ('markov_1bet_539','acb_single_539',"
                "'zone_gap_3bet_539','539_3bet_orthogonal',"
                "'p0b_539_3bet_f_cold_fmid','p0c_539_3bet_f_cold_x2') "
                "GROUP BY controlled_apply_id"
            ).fetchall()
        finally:
            conn.close()
        # No rows at all (pre-P37) OR all rows belong to P37 apply ID
        p37_apply_id = "P37_DAILY539_WAVE2_9000_PROD_20260523"
        for row in rows:
            assert row[0] == p37_apply_id, (
                f"Wave 2 rows with unexpected controlled_apply_id='{row[0]}' found "
                f"({row[1]} rows). Only P37 is authorized to insert Wave 2 rows."
            )


# ── TestSchemaValidation ──────────────────────────────────────────────────────

class TestSchemaValidation:
    """Verify schema validation results from the rehearsal output."""

    def test_schema_validation_passed(self, p36_rehearsal):
        validation = p36_rehearsal.get("schema_validation", {})
        assert validation.get("valid") is True, (
            f"Schema validation failed: {validation.get('errors', [])[:5]}"
        )

    def test_schema_error_count_zero(self, p36_rehearsal):
        validation = p36_rehearsal.get("schema_validation", {})
        errors = validation.get("errors", [])
        assert len(errors) == 0, f"Schema errors: {errors[:5]}"


# ── TestLifecycleSemantics ────────────────────────────────────────────────────

class TestLifecycleSemantics:
    """Verify lifecycle semantics are correct for P36."""

    def test_lifecycle_semantics_all_dryrun(self, p36_data):
        semantics = p36_data.get("lifecycle_semantics", {})
        assert semantics.get("all_rows_lifecycle") == "DRY_RUN"

    def test_no_online_rows_in_semantics(self, p36_data):
        semantics = p36_data.get("lifecycle_semantics", {})
        assert semantics.get("online_rows", 0) == 0

    def test_p37_required_for_production(self, p36_data):
        readiness = p36_data.get("production_apply_readiness", {})
        assert readiness.get("requires_p37_authorization") is True

    def test_p36_does_not_change_lifecycle_to_online(self, p36_data):
        """P36 must not set lifecycle=ONLINE for any strategy."""
        for s in p36_data["strategies"]:
            assert s["lifecycle"] != "ONLINE", (
                f"P36 must not set lifecycle=ONLINE: {s['strategy_id']}"
            )
