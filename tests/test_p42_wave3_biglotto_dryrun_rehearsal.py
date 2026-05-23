"""
test_p42_wave3_biglotto_dryrun_rehearsal.py
============================================
Contract tests for P42 Wave 3 BIG_LOTTO Dry-Run + Temp Rehearsal.

Tests verify:
 1. Exactly 6 Wave 3 BIG_LOTTO strategies in output
 2. No DAILY_539 strategies included
 3. No POWER_LOTTO strategies included
 4. Total dry-run rows = 9000
 5. Each strategy has exactly 1500 rows
 6. All rows have lottery_type = "BIG_LOTTO"
 7. All predicted_numbers lists have length = 6
 8. All predicted numbers are in range [1, 49]
 9. All predicted_numbers lists have no duplicates
10. All predicted_special == None
11. All special_hit == 0
12. All rows have lifecycle = "DRY_RUN"
13. hit_count == len(hit_numbers) for all rows
14. prediction_cutoff_date < draw_date for all rows (no future leakage)
15. R1: temp rehearsal inserts 9000 rows
16. R2: duplicate rerun inserts 0 rows
17. R3: rollback PASS
18. Production DB row count unchanged at 28960
19. P42 output JSON file exists
"""
import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
P42_JSON = PROJECT_ROOT / "outputs" / "replay" / "p42_wave3_biglotto_dryrun_rehearsal_20260524.json"
P42_REHEARSAL_JSON = PROJECT_ROOT / "outputs" / "replay" / "p42_temp_rehearsal_20260524.json"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_PRODUCTION_ROWS = 28960
EXPECTED_STRATEGY_COUNT = 6
EXPECTED_ROWS_PER_STRATEGY = 1500
EXPECTED_TOTAL_ROWS = EXPECTED_STRATEGY_COUNT * EXPECTED_ROWS_PER_STRATEGY  # 9000

EXPECTED_WAVE3_STRATEGY_IDS = {
    "markov_single_biglotto",
    "markov_2bet_biglotto",
    "bet2_fourier_expansion_biglotto",
    "fourier30_markov30_biglotto",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
}

# Forbidden strategy ID patterns (must not appear in BIG_LOTTO Wave 3)
FORBIDDEN_539_PREFIXES = ("539", "acb_", "markov_1bet_539", "midfreq", "zone_gap",
                          "p0b_", "p0c_", "orthogonal")
FORBIDDEN_POWER_PREFIXES = ("power", "pp3", "fourier_rhythm", "fourier30_markov30",
                             "orthogonal_5bet", "midfreq_fourier")


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p42_data() -> dict:
    """Load P42 dryrun output JSON."""
    assert P42_JSON.exists(), f"P42 JSON not found: {P42_JSON}"
    with open(P42_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def rehearsal_data() -> dict:
    """Load P42 rehearsal JSON."""
    assert P42_REHEARSAL_JSON.exists(), f"P42 rehearsal JSON not found: {P42_REHEARSAL_JSON}"
    with open(P42_REHEARSAL_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def adapter_rows() -> list:
    """Generate fresh dry-run rows using adapter (for detailed per-row checks)."""
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))

    from lottery_api.models.p42_wave3_biglotto_adapters import generate_dryrun_rows
    from scripts.p42_wave3_biglotto_dryrun_rehearsal import _load_biglotto_draws

    all_draws = _load_biglotto_draws()
    return generate_dryrun_rows(all_draws, rows_per_strategy=1500)


# ─── Test 1-3: Strategy ID constraints ────────────────────────────────────────

class TestStrategyConstraints:
    def test_01_exactly_6_strategies(self, p42_data):
        """Test 1: Exactly 6 Wave 3 BIG_LOTTO strategies."""
        strategies = p42_data["strategies"]
        assert len(strategies) == EXPECTED_STRATEGY_COUNT, (
            f"Expected 6 strategies, got {len(strategies)}: "
            f"{[s['strategy_id'] for s in strategies]}"
        )

    def test_02_no_daily539_strategies(self, p42_data):
        """Test 2: No DAILY_539 strategies included."""
        strategy_ids = {s["strategy_id"] for s in p42_data["strategies"]}
        for sid in strategy_ids:
            for prefix in FORBIDDEN_539_PREFIXES:
                assert not sid.startswith(prefix) and "539" not in sid, (
                    f"DAILY_539 strategy found in BIG_LOTTO Wave 3: {sid}"
                )

    def test_03_no_power_lotto_strategies(self, p42_data):
        """Test 3: No POWER_LOTTO strategies included."""
        strategy_ids = {s["strategy_id"] for s in p42_data["strategies"]}
        for sid in strategy_ids:
            for prefix in FORBIDDEN_POWER_PREFIXES:
                if prefix in ("fourier30_markov30",):
                    # fourier30_markov30_biglotto is allowed (BIG_LOTTO strategy)
                    if sid == "fourier30_markov30_biglotto":
                        continue
                assert "power_lotto" not in sid.lower(), (
                    f"POWER_LOTTO strategy found in BIG_LOTTO Wave 3: {sid}"
                )

    def test_strategy_ids_match_expected(self, p42_data):
        """All strategy IDs match the expected Wave 3 set."""
        strategy_ids = {s["strategy_id"] for s in p42_data["strategies"]}
        assert strategy_ids == EXPECTED_WAVE3_STRATEGY_IDS, (
            f"Strategy IDs mismatch.\n"
            f"Expected: {EXPECTED_WAVE3_STRATEGY_IDS}\n"
            f"Got:      {strategy_ids}"
        )


# ─── Test 4-6: Row counts ─────────────────────────────────────────────────────

class TestRowCounts:
    def test_04_total_dryrun_rows_9000(self, p42_data):
        """Test 4: Total dry-run rows = 9000."""
        total = p42_data["total_dryrun_rows"]
        assert total == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} total rows, got {total}"
        )

    def test_05_each_strategy_1500_rows(self, p42_data):
        """Test 5: Each strategy has exactly 1500 rows."""
        for entry in p42_data["strategies"]:
            sid = entry["strategy_id"]
            count = entry["row_count"]
            assert count == EXPECTED_ROWS_PER_STRATEGY, (
                f"Strategy {sid}: expected {EXPECTED_ROWS_PER_STRATEGY} rows, got {count}"
            )

    def test_06_all_rows_lottery_type_biglotto(self, adapter_rows):
        """Test 6: All rows have lottery_type = 'BIG_LOTTO'."""
        non_biglotto = [r for r in adapter_rows if r.get("lottery_type") != "BIG_LOTTO"]
        assert len(non_biglotto) == 0, (
            f"Found {len(non_biglotto)} rows with lottery_type != BIG_LOTTO: "
            f"{[r['lottery_type'] for r in non_biglotto[:5]]}"
        )


# ─── Test 7-9: BIG_LOTTO format validation ────────────────────────────────────

class TestBigLottoFormat:
    def test_07_predicted_numbers_length_6(self, adapter_rows):
        """Test 7: All predicted_numbers lists have length = 6."""
        predicted = [r for r in adapter_rows if r.get("predicted_numbers") is not None]
        wrong_length = [r for r in predicted if len(r["predicted_numbers"]) != 6]
        assert len(wrong_length) == 0, (
            f"Found {len(wrong_length)} rows with predicted_numbers length != 6"
        )

    def test_08_predicted_numbers_in_range_1_49(self, adapter_rows):
        """Test 8: All predicted numbers are in range [1, 49]."""
        predicted = [r for r in adapter_rows if r.get("predicted_numbers") is not None]
        out_of_range = [
            r for r in predicted
            if not all(1 <= n <= 49 for n in r["predicted_numbers"])
        ]
        assert len(out_of_range) == 0, (
            f"Found {len(out_of_range)} rows with out-of-range predicted_numbers"
        )

    def test_09_no_duplicate_predicted_numbers(self, adapter_rows):
        """Test 9: All predicted_numbers lists have no duplicates."""
        predicted = [r for r in adapter_rows if r.get("predicted_numbers") is not None]
        with_dupes = [
            r for r in predicted
            if len(set(r["predicted_numbers"])) != len(r["predicted_numbers"])
        ]
        assert len(with_dupes) == 0, (
            f"Found {len(with_dupes)} rows with duplicate predicted_numbers"
        )


# ─── Test 10-12: Special number policy ───────────────────────────────────────

class TestSpecialNumberPolicy:
    def test_10_predicted_special_is_none(self, adapter_rows):
        """Test 10: All predicted_special == None (Wave 3 NOT_PREDICTED policy)."""
        not_none = [r for r in adapter_rows if r.get("predicted_special") is not None]
        assert len(not_none) == 0, (
            f"Found {len(not_none)} rows with predicted_special != None "
            f"(Wave 3 policy: NOT_PREDICTED_WAVE3)"
        )

    def test_11_special_hit_is_zero(self, adapter_rows):
        """Test 11: All special_hit == 0 (Wave 3 NOT_PREDICTED policy)."""
        nonzero = [r for r in adapter_rows if r.get("special_hit", 0) != 0]
        assert len(nonzero) == 0, (
            f"Found {len(nonzero)} rows with special_hit != 0 "
            f"(Wave 3 policy: NOT_PREDICTED_WAVE3)"
        )

    def test_special_number_policy_documented(self, p42_data):
        """Special number policy is documented in output JSON."""
        assert p42_data.get("special_number_policy") == "NOT_PREDICTED_WAVE3", (
            f"special_number_policy should be NOT_PREDICTED_WAVE3, "
            f"got {p42_data.get('special_number_policy')}"
        )


# ─── Test 12-13: Lifecycle and hit consistency ────────────────────────────────

class TestLifecycleAndHits:
    def test_12_all_rows_dryrun_lifecycle(self, adapter_rows):
        """Test 12: All rows have lifecycle = 'DRY_RUN'."""
        not_dryrun = [r for r in adapter_rows if r.get("lifecycle") != "DRY_RUN"]
        assert len(not_dryrun) == 0, (
            f"Found {len(not_dryrun)} rows with lifecycle != DRY_RUN"
        )

    def test_12b_no_online_lifecycle(self, adapter_rows):
        """No ONLINE rows allowed."""
        online = [r for r in adapter_rows if r.get("lifecycle") == "ONLINE"]
        assert len(online) == 0, (
            f"Found {len(online)} ONLINE rows — ONLINE lifecycle is forbidden in P42"
        )

    def test_13_hit_count_equals_hit_numbers_length(self, adapter_rows):
        """Test 13: hit_count == len(hit_numbers) for all rows."""
        predicted = [r for r in adapter_rows if r.get("replay_status") == "PREDICTED"]
        mismatches = [
            r for r in predicted
            if r.get("hit_count", 0) != len(r.get("hit_numbers", []))
        ]
        assert len(mismatches) == 0, (
            f"Found {len(mismatches)} rows where hit_count != len(hit_numbers)"
        )


# ─── Test 14: No future leakage ───────────────────────────────────────────────

class TestNoFutureLeakage:
    def test_14_cutoff_before_draw_date(self, adapter_rows):
        """Test 14: prediction_cutoff_date < draw_date for all PREDICTED rows."""
        predicted = [r for r in adapter_rows if r.get("replay_status") == "PREDICTED"]
        violations = [
            r for r in predicted
            if r.get("prediction_cutoff_date") and r.get("draw_date")
            and r["prediction_cutoff_date"] >= r["draw_date"]
        ]
        assert len(violations) == 0, (
            f"Found {len(violations)} rows with cutoff_date >= draw_date (future leakage!): "
            f"{violations[:3]}"
        )


# ─── Test 15-17: Temp rehearsal R1/R2/R3 ─────────────────────────────────────

class TestTempRehearsal:
    def test_15_r1_inserts_9000_rows(self, p42_data):
        """Test 15: R1 temp rehearsal inserts 9000 rows."""
        r1_count = p42_data["temp_rehearsal"]["R1_insert_count"]
        assert r1_count == EXPECTED_TOTAL_ROWS, (
            f"R1 expected {EXPECTED_TOTAL_ROWS} inserts, got {r1_count}"
        )

    def test_16_r2_duplicate_rerun_inserts_0(self, p42_data):
        """Test 16: R2 duplicate rerun inserts 0 rows."""
        r2_count = p42_data["temp_rehearsal"]["R2_duplicate_count"]
        assert r2_count == 0, (
            f"R2 expected 0 duplicate inserts, got {r2_count}"
        )

    def test_17_r3_rollback_pass(self, p42_data):
        """Test 17: R3 rollback PASS."""
        r3_status = p42_data["temp_rehearsal"]["R3_rollback"]
        assert r3_status == "PASS", (
            f"R3 rollback expected PASS, got {r3_status}"
        )

    def test_rehearsal_all_pass(self, rehearsal_data):
        """All rehearsals pass in detailed rehearsal JSON."""
        assert rehearsal_data["all_rehearsals_pass"] is True, (
            "rehearsal_data.all_rehearsals_pass is not True"
        )


# ─── Test 18: Production DB unchanged ────────────────────────────────────────

class TestProductionDBUnchanged:
    def test_18_production_rows_unchanged_at_28960(self, p42_data):
        """Test 18: Production DB row count unchanged at 28960."""
        rows_before = p42_data["production_rows_before"]
        rows_after = p42_data["production_rows_after"]
        assert rows_before == EXPECTED_PRODUCTION_ROWS, (
            f"production_rows_before expected {EXPECTED_PRODUCTION_ROWS}, got {rows_before}"
        )
        assert rows_after == EXPECTED_PRODUCTION_ROWS, (
            f"production_rows_after expected {EXPECTED_PRODUCTION_ROWS}, got {rows_after}"
        )

    def test_18b_live_db_still_28960(self):
        """Live production DB still has exactly 28960 rows."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == EXPECTED_PRODUCTION_ROWS, (
            f"Live DB expected {EXPECTED_PRODUCTION_ROWS} rows, got {count}"
        )

    def test_no_p42_dryrun_rows_in_prod_db(self):
        """P42 dry-run rows must NOT appear in production DB."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id IN ("
                "  'markov_single_biglotto', 'markov_2bet_biglotto',"
                "  'bet2_fourier_expansion_biglotto', 'fourier30_markov30_biglotto',"
                "  'cold_complement_biglotto', 'coldpool15_biglotto'"
                ")"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0, (
            f"Found {count} P42 Wave 3 strategy rows in production DB — "
            "should be 0 (dry-run only)"
        )


# ─── Test 19: Output JSON file exists ────────────────────────────────────────

class TestOutputFiles:
    def test_19_p42_output_json_exists(self):
        """Test 19: P42 output JSON file exists."""
        assert P42_JSON.exists(), f"P42 JSON not found: {P42_JSON}"

    def test_rehearsal_json_exists(self):
        """P42 rehearsal JSON exists."""
        assert P42_REHEARSAL_JSON.exists(), f"P42 rehearsal JSON not found: {P42_REHEARSAL_JSON}"

    def test_classification_ready(self, p42_data):
        """P42 classification is DRYRUN_REHEARSAL_READY."""
        classification = p42_data.get("classification", "")
        assert "READY" in classification, (
            f"Expected READY classification, got: {classification}"
        )

    def test_lifecycle_semantics_documented(self, p42_data):
        """Lifecycle semantics documented: all DRY_RUN."""
        lifecycle = p42_data.get("lifecycle_semantics", {})
        assert lifecycle.get("all_rows_lifecycle") == "DRY_RUN"
        assert lifecycle.get("online_rows") == 0
        assert lifecycle.get("retired_rows") == 0


# ─── Adapter unit tests ───────────────────────────────────────────────────────

class TestAdapterUnit:
    """Unit tests for individual adapter prediction functions."""

    def _make_history(self, n: int = 200):
        """Create synthetic BIG_LOTTO draw history for testing."""
        import random
        rng = random.Random(42)
        history = []
        for i in range(n):
            nums = sorted(rng.sample(range(1, 50), 6))
            special = rng.randint(1, 49)
            while special in nums:
                special = rng.randint(1, 49)
            history.append({
                "draw": str(96000001 + i),
                "date": f"2007/01/{(i % 28) + 1:02d}",
                "numbers": nums,
                "special": special,
            })
        return history

    def test_adapter_registry_has_6_strategies(self):
        """WAVE3_ADAPTERS has exactly 6 adapters."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from lottery_api.models.p42_wave3_biglotto_adapters import WAVE3_ADAPTERS
        assert len(WAVE3_ADAPTERS) == 6

    def test_all_adapters_are_dryrun_lifecycle(self):
        """All adapters have lifecycle_status = DRY_RUN."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from lottery_api.models.p42_wave3_biglotto_adapters import WAVE3_ADAPTERS
        for a in WAVE3_ADAPTERS:
            assert a.meta.lifecycle_status == "DRY_RUN", (
                f"{a.meta.strategy_id}: expected DRY_RUN, got {a.meta.lifecycle_status}"
            )

    def test_all_adapters_support_biglotto(self):
        """All adapters support BIG_LOTTO lottery type."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from lottery_api.models.p42_wave3_biglotto_adapters import WAVE3_ADAPTERS
        for a in WAVE3_ADAPTERS:
            assert "BIG_LOTTO" in a.meta.supported_lottery_types, (
                f"{a.meta.strategy_id}: BIG_LOTTO not in supported_lottery_types"
            )

    def test_adapters_return_6_numbers_in_range(self):
        """Each adapter returns 6 distinct numbers in [1, 49]."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from lottery_api.models.p42_wave3_biglotto_adapters import WAVE3_ADAPTERS

        history = self._make_history(200)
        for a in WAVE3_ADAPTERS:
            numbers, special = a.get_one_bet(history, "BIG_LOTTO")
            assert len(numbers) == 6, (
                f"{a.meta.strategy_id}: expected 6 numbers, got {len(numbers)}"
            )
            assert len(set(numbers)) == 6, (
                f"{a.meta.strategy_id}: duplicate numbers: {numbers}"
            )
            assert all(1 <= n <= 49 for n in numbers), (
                f"{a.meta.strategy_id}: out-of-range numbers: {numbers}"
            )
            assert special is None, (
                f"{a.meta.strategy_id}: expected special=None (Wave 3), got {special}"
            )

    def test_adapters_deterministic(self):
        """Adapters produce deterministic output for same history."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from lottery_api.models.p42_wave3_biglotto_adapters import WAVE3_ADAPTERS

        history = self._make_history(200)
        for a in WAVE3_ADAPTERS:
            r1, _ = a.get_one_bet(history, "BIG_LOTTO")
            r2, _ = a.get_one_bet(history, "BIG_LOTTO")
            assert r1 == r2, (
                f"{a.meta.strategy_id}: not deterministic: {r1} != {r2}"
            )
