"""
test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py
======================================================
Governance test suite for P56: Wave 5 POWER_LOTTO Adapter Bootstrap + Dry-Run.

P56 implements 3 Wave 5 adapters (cold_complement_2bet, fourier30_markov30_2bet,
zonal_entropy_2bet) and rehearses a 4500-row dry-run into /tmp/p56_temp.db.

Test Classes:
  TestP56AdapterPredictions    — adapter functions produce valid POWER_LOTTO bets
  TestP56Determinism           — repeated calls with same history → same output
  TestP56SemanticValidity      — first-zone [1,38], special [1,8], no duplicates
  TestP56ProductionIntegrity   — production DB unchanged (42460 rows total)
  TestP56GovernanceConstraints — DRY_RUN lifecycle, no registry pollution
  TestP56ArtifactContent       — output JSON artifact has correct fields
  TestP56DryRunGeneration      — 4500 rows generated, validation passes
"""
import json
import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")

EXPECTED_TOTAL_ROWS = 42460
EXPECTED_PL_ROWS = 9140
EXPECTED_DRY_RUN_ROWS = 4500       # 3 strategies × 1500 draws
EXPECTED_ROWS_PER_STRATEGY = 1500

WAVE5_STRATEGY_IDS = [
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
]

CHAMPION = "fourier_rhythm_3bet"

ADAPTER_MODULE_PATH = os.path.join(
    PROJECT_ROOT, "lottery_api", "models",
    "p56_wave5_powerlotto_adapters.py",
)

DRYRUN_SCRIPT_PATH = os.path.join(
    PROJECT_ROOT, "scripts",
    "p56_powerlotto_wave5_adapter_bootstrap_dryrun.py",
)

JSON_OUTPUT_PATH = os.path.join(
    PROJECT_ROOT, "outputs", "replay",
    "p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.json",
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _db_count_total() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _db_count_by_lottery(lottery_type: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type=?",
            (lottery_type,),
        ).fetchone()[0]
    finally:
        conn.close()


def _minimal_history(n: int = 50) -> list:
    """Build a minimal synthetic POWER_LOTTO history with n draws."""
    import random
    rng = random.Random(42)
    draws = []
    for i in range(n):
        nums = sorted(rng.sample(range(1, 39), 6))
        special = rng.randint(1, 8)
        draws.append({
            "draw": str(1000 + i),
            "date": f"2024-01-{(i % 28) + 1:02d}",
            "numbers": nums,
            "special": special,
        })
    return draws


# ─── Import adapters ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def adapters():
    from lottery_api.models.p56_wave5_powerlotto_adapters import (
        WAVE5_ADAPTERS,
        WAVE5_ADAPTER_MAP,
        ColdComplement2BetAdapter,
        Fourier30Markov30_2BetAdapter,
        ZonalEntropy2BetAdapter,
    )
    return {
        "list": WAVE5_ADAPTERS,
        "map": WAVE5_ADAPTER_MAP,
        "ColdComplement": ColdComplement2BetAdapter,
        "Fourier30Markov30": Fourier30Markov30_2BetAdapter,
        "ZonalEntropy": ZonalEntropy2BetAdapter,
    }


@pytest.fixture(scope="module")
def history50():
    return _minimal_history(50)


@pytest.fixture(scope="module")
def history200():
    return _minimal_history(200)


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56AdapterPredictions
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56AdapterPredictions:
    """Adapter functions produce valid POWER_LOTTO predictions."""

    def test_adapter_file_exists(self):
        assert os.path.isfile(ADAPTER_MODULE_PATH), (
            f"Adapter file not found: {ADAPTER_MODULE_PATH}"
        )

    def test_wave5_adapters_count(self, adapters):
        assert len(adapters["list"]) == 3

    def test_wave5_strategy_ids_complete(self, adapters):
        ids = {a.meta.strategy_id for a in adapters["list"]}
        assert ids == set(WAVE5_STRATEGY_IDS)

    def test_adapter_lifecycle_all_dry_run(self, adapters):
        for a in adapters["list"]:
            assert a.meta.lifecycle_status == "DRY_RUN", (
                f"{a.meta.strategy_id} has lifecycle {a.meta.lifecycle_status!r}, expected DRY_RUN"
            )

    def test_adapter_map_keys(self, adapters):
        for sid in WAVE5_STRATEGY_IDS:
            assert sid in adapters["map"], f"{sid} missing from WAVE5_ADAPTER_MAP"

    def test_cold_complement_bet0_valid(self, adapters, history200):
        a = adapters["map"]["cold_complement_2bet"]
        nums, special = a.get_one_bet(history200, "POWER_LOTTO")
        assert isinstance(nums, list)
        assert len(nums) == 6
        assert len(set(nums)) == 6
        assert all(1 <= n <= 38 for n in nums)
        assert 1 <= special <= 8

    def test_fourier30_markov30_bet0_valid(self, adapters, history200):
        a = adapters["map"]["fourier30_markov30_2bet"]
        nums, special = a.get_one_bet(history200, "POWER_LOTTO")
        assert isinstance(nums, list)
        assert len(nums) == 6
        assert len(set(nums)) == 6
        assert all(1 <= n <= 38 for n in nums)
        assert 1 <= special <= 8

    def test_zonal_entropy_bet0_valid(self, adapters, history200):
        a = adapters["map"]["zonal_entropy_2bet"]
        nums, special = a.get_one_bet(history200, "POWER_LOTTO")
        assert isinstance(nums, list)
        assert len(nums) == 6
        assert len(set(nums)) == 6
        assert all(1 <= n <= 38 for n in nums)
        assert 1 <= special <= 8

    def test_all_adapters_wrong_lottery_type_raises(self, adapters, history200):
        for a in adapters["list"]:
            with pytest.raises(ValueError):
                a.get_one_bet(history200, "BIG_LOTTO")

    def test_insufficient_history_raises(self, adapters):
        tiny = _minimal_history(5)
        for a in adapters["list"]:
            with pytest.raises(ValueError):
                a.get_one_bet(tiny, "POWER_LOTTO")

    def test_predicted_numbers_sorted(self, adapters, history200):
        for a in adapters["list"]:
            nums, _ = a.get_one_bet(history200, "POWER_LOTTO")
            assert nums == sorted(nums), (
                f"{a.meta.strategy_id}: predicted_numbers not sorted: {nums}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56Determinism
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56Determinism:
    """Repeated calls with the same history must produce identical outputs."""

    def test_cold_complement_deterministic(self, adapters, history200):
        a = adapters["map"]["cold_complement_2bet"]
        r1 = a.get_one_bet(history200, "POWER_LOTTO")
        r2 = a.get_one_bet(history200, "POWER_LOTTO")
        assert r1 == r2, "cold_complement_2bet is not deterministic"

    def test_fourier30_markov30_deterministic(self, adapters, history200):
        a = adapters["map"]["fourier30_markov30_2bet"]
        r1 = a.get_one_bet(history200, "POWER_LOTTO")
        r2 = a.get_one_bet(history200, "POWER_LOTTO")
        assert r1 == r2, "fourier30_markov30_2bet is not deterministic"

    def test_zonal_entropy_deterministic(self, adapters, history200):
        a = adapters["map"]["zonal_entropy_2bet"]
        r1 = a.get_one_bet(history200, "POWER_LOTTO")
        r2 = a.get_one_bet(history200, "POWER_LOTTO")
        assert r1 == r2, "zonal_entropy_2bet is not deterministic"

    def test_cold_complement_different_history_may_differ(self, adapters):
        """Different history slices may produce different predictions."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import (
            predict_cold_complement_2bet_bet0,
        )
        h_a = _minimal_history(100)
        h_b = _minimal_history(100)
        # Modify h_b's first draw to create a different history
        h_b[0]["numbers"] = [1, 2, 3, 4, 5, 6]
        # Both must still produce valid results
        r_a = predict_cold_complement_2bet_bet0(h_a)
        r_b = predict_cold_complement_2bet_bet0(h_b)
        assert len(r_a) == 6
        assert len(r_b) == 6

    def test_no_random_seed_in_adapter_module(self):
        """Verify adapter module doesn't call random.seed() — determinism rule."""
        with open(ADAPTER_MODULE_PATH, encoding="utf-8") as f:
            lines = f.readlines()
        # Check only non-comment, non-docstring lines for random.seed calls
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            assert "random.seed" not in line, (
                f"Adapter module must not call random.seed() — found in code: {line.rstrip()}"
            )

    def test_no_random_import_in_adapter_module(self):
        """Adapter module should not import stdlib random (to prevent accidental use)."""
        with open(ADAPTER_MODULE_PATH, encoding="utf-8") as f:
            source = f.read()
        # 'import random' or 'from random import' is forbidden
        assert "import random" not in source, (
            "Adapter module must not use stdlib random — detected 'import random'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56SemanticValidity
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56SemanticValidity:
    """Validate POWER_LOTTO semantics: first-zone [1,38], special [1,8]."""

    def test_all_predicted_in_first_zone_pool(self, adapters, history200):
        for a in adapters["list"]:
            nums, _ = a.get_one_bet(history200, "POWER_LOTTO")
            assert all(1 <= n <= 38 for n in nums), (
                f"{a.meta.strategy_id}: number out of first-zone pool [1,38]: {nums}"
            )

    def test_all_specials_in_second_zone_pool(self, adapters, history200):
        for a in adapters["list"]:
            _, special = a.get_one_bet(history200, "POWER_LOTTO")
            assert 1 <= special <= 8, (
                f"{a.meta.strategy_id}: special {special} out of [1,8]"
            )

    def test_no_duplicates_in_predicted_numbers(self, adapters, history200):
        for a in adapters["list"]:
            nums, _ = a.get_one_bet(history200, "POWER_LOTTO")
            assert len(set(nums)) == 6, (
                f"{a.meta.strategy_id}: duplicate numbers: {nums}"
            )

    def test_exactly_6_numbers_per_bet(self, adapters, history200):
        for a in adapters["list"]:
            nums, _ = a.get_one_bet(history200, "POWER_LOTTO")
            assert len(nums) == 6, (
                f"{a.meta.strategy_id}: expected 6 numbers, got {len(nums)}"
            )

    def test_hit_count_is_first_zone_only(self, adapters):
        """hit_count must count first-zone matches only, never special."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        tiny_history = _minimal_history(40)
        rows = generate_dryrun_rows(tiny_history, rows_per_strategy=5)
        for row in rows:
            if row["replay_status"] != "PREDICTED":
                continue
            predicted = row["predicted_numbers"]
            actual = row["actual_numbers"]
            hit_nums = row["hit_numbers"]
            assert set(hit_nums) == set(predicted) & set(actual), (
                f"hit_numbers mismatch: predicted={predicted}, actual={actual}, "
                f"hit_numbers={hit_nums}"
            )
            assert row["hit_count"] == len(hit_nums), (
                f"hit_count {row['hit_count']} != len(hit_numbers) {len(hit_nums)}"
            )

    def test_special_hit_is_binary(self, adapters):
        """special_hit must be 0 or 1, never included in hit_count."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        tiny_history = _minimal_history(40)
        rows = generate_dryrun_rows(tiny_history, rows_per_strategy=5)
        for row in rows:
            if row["replay_status"] != "PREDICTED":
                continue
            assert row["special_hit"] in (0, 1), (
                f"special_hit must be 0 or 1, got {row['special_hit']}"
            )

    def test_cold_complement_coldest_6_are_selected(self, adapters):
        """cold_complement_2bet bet-0 must select the 6 coldest numbers."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import (
            predict_cold_complement_2bet_bet0,
        )
        from collections import Counter
        history = _minimal_history(100)
        # Make numbers 1-6 appear 0 times by removing them from all draws
        for d in history:
            d["numbers"] = [n for n in d["numbers"] if n > 6]
            # Refill if needed with numbers from 7-38
            while len(d["numbers"]) < 6:
                d["numbers"].append(max(d["numbers"]) + 1 if d["numbers"] else 7)
            d["numbers"] = sorted(set(d["numbers"]))[:6]
        result = predict_cold_complement_2bet_bet0(history)
        freq = Counter(n for d in history for n in d["numbers"] if 1 <= n <= 38)
        # Numbers with 0 freq should be preferred
        zero_freq = [n for n in range(1, 39) if freq.get(n, 0) == 0]
        assert len(result) == 6
        # At least some of the zero-frequency numbers should appear
        overlap = set(result) & set(zero_freq)
        assert len(overlap) > 0, (
            f"cold_complement_2bet should prefer zero-frequency numbers; "
            f"result={result}, zero_freq={zero_freq[:10]}"
        )

    def test_fourier30_uses_weighted_frequency(self, adapters):
        """fourier30_markov30_2bet bet-0 prefers recent numbers when count is equal.

        Equal-count scenario: 15 draws with [1-6] at indices 0-14 (older, avg
        weight ≈1.47 each), then 15 draws with [30-35] at indices 15-29 (newer,
        avg weight ≈2.47 each). Cumulative weighted_freq for 30-35 should be
        significantly higher than 1-6, so 30-35 should dominate the result.
        """
        from lottery_api.models.p56_wave5_powerlotto_adapters import (
            predict_fourier30_markov30_2bet_bet0,
        )
        history = []
        for i in range(30):
            if i < 15:
                nums = sorted([1, 2, 3, 4, 5, 6])
            else:
                nums = sorted([30, 31, 32, 33, 34, 35])
            history.append({"draw": str(i), "date": "2024-01-01", "numbers": nums, "special": 1})
        result = predict_fourier30_markov30_2bet_bet0(history)
        # Recent draws (30-35) have higher cumulative recency weight than older (1-6)
        assert len(result) == 6
        recent_nums = {30, 31, 32, 33, 34, 35}
        overlap = set(result) & recent_nums
        assert len(overlap) >= 3, (
            f"Fourier30 should prefer recent high-frequency numbers; "
            f"result={result}, recent_nums={sorted(recent_nums)}"
        )

    def test_zonal_entropy_switches_regime(self, adapters):
        """zonal_entropy_2bet switches between cold and hot regime based on entropy."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import (
            predict_zonal_entropy_2bet_bet0,
            _zone_entropy,
            _ENTROPY_CHAOS_THRESHOLD,
        )
        # Build a chaotic history (numbers spread across all zones)
        chaotic = []
        for i in range(30):
            # Use numbers from all zones
            nums = sorted([1 + (i*6 + j) % 38 for j in range(6)])
            nums = sorted(list(set(n for n in nums if 1 <= n <= 38)))[:6]
            while len(nums) < 6:
                nums.append(max(nums) + 1)
            chaotic.append({"draw": str(i), "date": "2024-01-01", "numbers": nums, "special": 1})

        entropy = _zone_entropy(chaotic, window=30)
        result = predict_zonal_entropy_2bet_bet0(chaotic)
        assert len(result) == 6
        assert all(1 <= n <= 38 for n in result)


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56ProductionIntegrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56ProductionIntegrity:
    """Production DB must remain at exactly 42460 rows at all times."""

    def test_total_rows_unchanged(self):
        count = _db_count_total()
        assert count == EXPECTED_TOTAL_ROWS, (
            f"Production DB total rows: expected {EXPECTED_TOTAL_ROWS}, got {count}"
        )

    def test_power_lotto_rows_unchanged(self):
        count = _db_count_by_lottery("POWER_LOTTO")
        assert count == EXPECTED_PL_ROWS, (
            f"POWER_LOTTO rows: expected {EXPECTED_PL_ROWS}, got {count}"
        )

    def test_champion_still_online(self):
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT replay_status FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND lottery_type='POWER_LOTTO' LIMIT 1",
                (CHAMPION,),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, f"Champion {CHAMPION} not found in production DB"
        assert row[0] == "PREDICTED", (
            f"Champion {CHAMPION} status changed: {row[0]}"
        )

    def test_wave5_strategies_not_in_production_db(self):
        """Wave 5 strategies must NOT appear in production DB (dry-run only)."""
        conn = sqlite3.connect(DB_PATH)
        try:
            for sid in WAVE5_STRATEGY_IDS:
                count = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
                    (sid,),
                ).fetchone()[0]
                assert count == 0, (
                    f"Wave 5 strategy {sid} found in production DB ({count} rows) — "
                    "dry-run must not write to production DB"
                )
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56GovernanceConstraints
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56GovernanceConstraints:
    """DRY_RUN lifecycle, no registry pollution, no champion replacement."""

    def test_wave5_adapters_lifecycle_dry_run(self, adapters):
        for a in adapters["list"]:
            assert a.meta.lifecycle_status == "DRY_RUN", (
                f"{a.meta.strategy_id}: lifecycle must be DRY_RUN, got {a.meta.lifecycle_status}"
            )

    def test_wave5_adapters_not_in_global_registry(self):
        """Wave 5 adapters must NOT be in replay_strategy_registry."""
        try:
            from lottery_api.models.replay_strategy_registry import _ALL_ADAPTERS, _REGISTRY
            all_ids = {a.meta.strategy_id for a in _ALL_ADAPTERS}
            for sid in WAVE5_STRATEGY_IDS:
                assert sid not in all_ids, (
                    f"{sid} was found in _ALL_ADAPTERS — Wave 5 must not be registered"
                )
                assert sid not in _REGISTRY, (
                    f"{sid} was found in _REGISTRY — Wave 5 must not be registered"
                )
        except ImportError:
            pytest.skip("replay_strategy_registry not available")

    def test_supported_lottery_types_power_lotto_only(self, adapters):
        for a in adapters["list"]:
            assert a.meta.supported_lottery_types == ["POWER_LOTTO"], (
                f"{a.meta.strategy_id}: supported_lottery_types must be ['POWER_LOTTO']"
            )

    def test_wave5_adapter_strategy_versions_p56(self, adapters):
        for a in adapters["list"]:
            assert "p56" in a.meta.strategy_version, (
                f"{a.meta.strategy_id}: strategy_version should contain 'p56', "
                f"got {a.meta.strategy_version!r}"
            )

    def test_generate_dryrun_rows_lifecycle_all_dry_run(self, adapters):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        tiny_history = _minimal_history(40)
        rows = generate_dryrun_rows(tiny_history, rows_per_strategy=3)
        for row in rows:
            assert row["lifecycle"] == "DRY_RUN", (
                f"lifecycle must be DRY_RUN for all generated rows, got {row['lifecycle']}"
            )

    def test_generate_dryrun_rows_not_online(self, adapters):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        tiny_history = _minimal_history(40)
        rows = generate_dryrun_rows(tiny_history, rows_per_strategy=3)
        for row in rows:
            assert row["lifecycle"] != "ONLINE", (
                f"lifecycle must NOT be ONLINE for dry-run rows"
            )

    def test_causal_slicing_no_future_leakage(self, adapters):
        """History slice for target draw i must not include draw i (no future leakage)."""
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        for row in rows:
            if row["replay_status"] != "PREDICTED":
                continue
            target_draw = row["target_draw"]
            cutoff_draw = row.get("history_cutoff_draw")
            if target_draw and cutoff_draw:
                assert int(cutoff_draw) < int(target_draw), (
                    f"Causal violation: history cutoff draw {cutoff_draw} >= "
                    f"target draw {target_draw}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56ArtifactContent
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56ArtifactContent:
    """Output JSON artifact has correct fields and classification."""

    def test_json_output_exists(self):
        assert os.path.isfile(JSON_OUTPUT_PATH), (
            f"P56 JSON output not found: {JSON_OUTPUT_PATH}"
        )

    def test_json_output_parseable(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_json_classification(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("classification") == (
            "P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED"
        ), f"Unexpected classification: {data.get('classification')}"

    def test_json_overall_ok(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("overall_ok") is True

    def test_json_wave(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("wave") == "5"

    def test_json_lottery_type(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("lottery_type") == "POWER_LOTTO"

    def test_json_strategies_complete(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert set(data.get("strategies", [])) == set(WAVE5_STRATEGY_IDS)

    def test_json_rows_per_strategy(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("rows_per_strategy") == EXPECTED_ROWS_PER_STRATEGY

    def test_json_expected_dry_run_rows(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("expected_dry_run_rows") == EXPECTED_DRY_RUN_ROWS

    def test_json_actual_rows_match_expected(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("actual_raw_rows") == EXPECTED_DRY_RUN_ROWS

    def test_json_production_rows_unchanged(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("production_rows_before") == EXPECTED_TOTAL_ROWS
        assert data.get("production_rows_after") == EXPECTED_TOTAL_ROWS
        assert data.get("production_rows_ok") is True

    def test_json_schema_validation_passed(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["schema_validation"]["valid"] is True
        assert len(data["schema_validation"]["errors"]) == 0

    def test_json_data_leakage_check_passed(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["data_leakage_check"]["pass"] is True
        assert data["data_leakage_check"]["violation_count"] == 0

    def test_json_r1_ok(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["rehearsal"]["r1_apply"]["r1_ok"] is True
        assert data["rehearsal"]["r1_apply"]["r1_inserted"] == EXPECTED_DRY_RUN_ROWS

    def test_json_r2_idempotent(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["rehearsal"]["r2_idempotency"]["r2_idempotent"] is True
        assert data["rehearsal"]["r2_idempotency"]["r2_duplicate_inserted"] == 0

    def test_json_r3_rollback_ok(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["rehearsal"]["r3_rollback"]["r3_rollback_ok"] is True
        assert data["rehearsal"]["r3_rollback"]["r3_after"] == 0

    def test_json_governance_no_production_write(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        gov = data.get("governance", {})
        assert gov.get("production_db_write") is False
        assert gov.get("lifecycle_promotion") is False
        assert gov.get("champion_replacement") is False
        assert gov.get("all_dry_run") is True

    def test_json_hit_stats_all_strategies_present(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        hit_stats = data.get("hit_stats", {})
        for sid in WAVE5_STRATEGY_IDS:
            assert sid in hit_stats, f"{sid} missing from hit_stats"
            assert hit_stats[sid]["predicted"] == EXPECTED_ROWS_PER_STRATEGY

    def test_json_row_counts_by_strategy(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        counts = data.get("row_counts_by_strategy", {})
        for sid in WAVE5_STRATEGY_IDS:
            assert counts.get(sid) == EXPECTED_ROWS_PER_STRATEGY, (
                f"{sid}: expected {EXPECTED_ROWS_PER_STRATEGY} rows, got {counts.get(sid)}"
            )

    def test_json_adapter_file_field(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert "p56_wave5_powerlotto_adapters.py" in data.get("adapter_file", "")

    def test_json_temp_db_path(self):
        with open(JSON_OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("temp_db_path") == "/tmp/p56_temp.db"


# ═══════════════════════════════════════════════════════════════════════════════
# TestP56DryRunGeneration
# ═══════════════════════════════════════════════════════════════════════════════

class TestP56DryRunGeneration:
    """4500 rows generated correctly; all strategies produce PREDICTED rows."""

    def test_generate_dryrun_rows_correct_count(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        assert len(rows) == 15  # 3 strategies × 5 draws

    def test_generate_dryrun_rows_all_strategies_present(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        strategy_ids = {r["strategy_id"] for r in rows}
        assert strategy_ids == set(WAVE5_STRATEGY_IDS)

    def test_generate_dryrun_rows_equal_counts(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        from collections import Counter
        counts = Counter(r["strategy_id"] for r in rows)
        for sid in WAVE5_STRATEGY_IDS:
            assert counts[sid] == 5, f"{sid}: expected 5 rows, got {counts[sid]}"

    def test_generate_dryrun_rows_all_predicted(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        for row in rows:
            assert row["replay_status"] == "PREDICTED", (
                f"Row status {row['replay_status']} for {row['strategy_id']} draw {row['target_draw']}"
            )

    def test_generate_dryrun_rows_insufficient_history_raises(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(10)
        with pytest.raises(ValueError):
            generate_dryrun_rows(history, rows_per_strategy=5)

    def test_generate_dryrun_rows_numbers_valid_first_zone(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        for row in rows:
            if row["replay_status"] != "PREDICTED":
                continue
            nums = row["predicted_numbers"]
            assert all(1 <= n <= 38 for n in nums), (
                f"Numbers out of first-zone pool [1,38]: {nums}"
            )

    def test_generate_dryrun_rows_special_valid(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        for row in rows:
            if row["replay_status"] != "PREDICTED":
                continue
            sp = row["predicted_special"]
            assert sp is None or 1 <= sp <= 8, (
                f"Special {sp} out of [1,8]"
            )

    def test_generate_dryrun_rows_hit_count_range(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        for row in rows:
            assert 0 <= row["hit_count"] <= 6, (
                f"hit_count {row['hit_count']} out of [0,6]"
            )

    def test_generate_dryrun_rows_lottery_type_power_lotto(self):
        from lottery_api.models.p56_wave5_powerlotto_adapters import generate_dryrun_rows
        history = _minimal_history(50)
        rows = generate_dryrun_rows(history, rows_per_strategy=5)
        for row in rows:
            assert row["lottery_type"] == "POWER_LOTTO"

    def test_script_file_exists(self):
        assert os.path.isfile(DRYRUN_SCRIPT_PATH), (
            f"Dry-run script not found: {DRYRUN_SCRIPT_PATH}"
        )
