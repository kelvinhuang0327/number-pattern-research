"""
test_replay_strategy_registry_online_candidates.py
====================================================
P1.3 registry ONLINE proposal tests.

Validates:
1. Registry total count is now 18 (was 16).
2. fourier_rhythm_3bet exists with ONLINE status and POWER_LOTTO type.
3. ts3_regime_3bet exists with ONLINE status and BIG_LOTTO type.
4. Both new strategy IDs appear in list_strategies(lifecycle_status="ONLINE").
5. Neither new strategy is classified as tombstone / non-ONLINE.
6. All existing 16 registry entries are still present and unchanged.
7. fourier_rhythm_3bet is executable (get_adapter returns adapter).
8. ts3_regime_3bet raises AdapterBindingPending (not LifecycleNotExecutable).
9. No DB writes on import.
"""
from __future__ import annotations

import pytest

from lottery_api.models.replay_strategy_registry import (
    LIFECYCLE_STATUSES,
    AdapterBindingPending,
    LifecycleNotExecutable,
    _ALL_ADAPTERS,
    _REGISTRY,
    get_adapter,
    get_adapters_for_lottery,
    get_strategy_lifecycle_status,
    list_executable_strategy_ids,
    list_non_executable_strategy_ids,
    list_strategies,
)

# ─── Expected strategy sets (P1.3 post-update) ───────────────────────────────

# Original 6 ONLINE strategies (unchanged)
_ORIGINAL_ONLINE_IDS = frozenset({
    "power_precision_3bet",
    "power_orthogonal_5bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "daily539_f4cold",
    "daily539_markov_cold",
})

# P1.3 new ONLINE additions
_P13_NEW_ONLINE_IDS = frozenset({
    "fourier_rhythm_3bet",
    "ts3_regime_3bet",
})

# All 8 ONLINE strategies post-P1.3
_ALL_ONLINE_IDS = _ORIGINAL_ONLINE_IDS | _P13_NEW_ONLINE_IDS

# Original non-ONLINE strategies (unchanged)
_ORIGINAL_NON_ONLINE_IDS = frozenset({
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "power_shlc_midfreq",
    "p1_deviation_2bet_539",
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
})

_EXPECTED_TOTAL = len(_ALL_ONLINE_IDS) + len(_ORIGINAL_NON_ONLINE_IDS)  # 18


# ─── Test class: Registry count ──────────────────────────────────────────────

class TestRegistryCount:
    """Total registry count must be 18 after P1.3."""

    def test_total_adapter_count_is_18(self):
        assert len(_ALL_ADAPTERS) == 18, (
            f"Expected 18 adapters (16 original + 2 P1.3), got {len(_ALL_ADAPTERS)}"
        )

    def test_list_strategies_total_count_is_18(self):
        all_entries = list_strategies()
        assert len(all_entries) == 18, (
            f"list_strategies() returned {len(all_entries)}, expected 18"
        )

    def test_online_count_is_8(self):
        online = list_strategies(lifecycle_status="ONLINE")
        assert len(online) == 8, (
            f"Expected 8 ONLINE strategies, got {len(online)}"
        )

    def test_non_online_count_is_10(self):
        non_online = [
            a for a in _ALL_ADAPTERS
            if a.meta.lifecycle_status != "ONLINE"
        ]
        assert len(non_online) == 10, (
            f"Expected 10 non-ONLINE adapters (unchanged), got {len(non_online)}"
        )


# ─── Test class: New ONLINE strategy IDs exist ───────────────────────────────

class TestNewOnlineStrategiesExist:
    """Both P1.3 new strategies must be registered as ONLINE."""

    def test_fourier_rhythm_3bet_in_all_adapters(self):
        ids = {a.meta.strategy_id for a in _ALL_ADAPTERS}
        assert "fourier_rhythm_3bet" in ids

    def test_ts3_regime_3bet_in_all_adapters(self):
        ids = {a.meta.strategy_id for a in _ALL_ADAPTERS}
        assert "ts3_regime_3bet" in ids

    def test_fourier_rhythm_3bet_lifecycle_status_online(self):
        status = get_strategy_lifecycle_status("fourier_rhythm_3bet")
        assert status == "ONLINE", f"Expected ONLINE, got {status!r}"

    def test_ts3_regime_3bet_lifecycle_status_online(self):
        status = get_strategy_lifecycle_status("ts3_regime_3bet")
        assert status == "ONLINE", f"Expected ONLINE, got {status!r}"

    def test_fourier_rhythm_3bet_lottery_type_power_lotto(self):
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id == "fourier_rhythm_3bet":
                assert "POWER_LOTTO" in a.meta.supported_lottery_types
                break
        else:
            pytest.fail("fourier_rhythm_3bet not found in _ALL_ADAPTERS")

    def test_ts3_regime_3bet_lottery_type_big_lotto(self):
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id == "ts3_regime_3bet":
                assert "BIG_LOTTO" in a.meta.supported_lottery_types
                break
        else:
            pytest.fail("ts3_regime_3bet not found in _ALL_ADAPTERS")

    def test_both_new_ids_in_list_strategies_online_filter(self):
        online_ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="ONLINE")}
        assert "fourier_rhythm_3bet" in online_ids
        assert "ts3_regime_3bet" in online_ids

    def test_all_8_online_ids_present(self):
        online_ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="ONLINE")}
        assert online_ids == _ALL_ONLINE_IDS, (
            f"ONLINE IDs mismatch.\n"
            f"  Expected: {sorted(_ALL_ONLINE_IDS)}\n"
            f"  Got:      {sorted(online_ids)}"
        )


# ─── Test class: No tombstone / not in non-ONLINE lists ──────────────────────

class TestNewStrategiesNotTombstoned:
    """New strategies must NOT appear in REJECTED, RETIRED, or OBSERVATION lists."""

    def test_fourier_rhythm_3bet_not_rejected(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="REJECTED")}
        assert "fourier_rhythm_3bet" not in ids

    def test_fourier_rhythm_3bet_not_retired(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="RETIRED")}
        assert "fourier_rhythm_3bet" not in ids

    def test_fourier_rhythm_3bet_not_observation(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="OBSERVATION")}
        assert "fourier_rhythm_3bet" not in ids

    def test_ts3_regime_3bet_not_rejected(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="REJECTED")}
        assert "ts3_regime_3bet" not in ids

    def test_ts3_regime_3bet_not_retired(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="RETIRED")}
        assert "ts3_regime_3bet" not in ids

    def test_ts3_regime_3bet_not_observation(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="OBSERVATION")}
        assert "ts3_regime_3bet" not in ids

    def test_new_strategies_not_in_non_executable_list(self):
        non_exec = set(list_non_executable_strategy_ids())
        assert "fourier_rhythm_3bet" not in non_exec
        assert "ts3_regime_3bet" not in non_exec


# ─── Test class: Existing 16 entries unchanged ───────────────────────────────

class TestExistingEntriesUnchanged:
    """All 16 original registry entries must still be present and unchanged."""

    def test_original_6_online_ids_still_present(self):
        online_ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="ONLINE")}
        missing = _ORIGINAL_ONLINE_IDS - online_ids
        assert not missing, f"Original ONLINE IDs missing: {missing}"

    def test_original_non_online_ids_still_present(self):
        all_ids = {a.meta.strategy_id for a in _ALL_ADAPTERS}
        missing = _ORIGINAL_NON_ONLINE_IDS - all_ids
        assert not missing, f"Original non-ONLINE IDs missing: {missing}"

    def test_original_online_strategies_still_executable(self):
        """Original ONLINE adapters must still be get_adapter()-accessible."""
        for sid in _ORIGINAL_ONLINE_IDS:
            adapter = get_adapter(sid)
            assert adapter.meta.strategy_id == sid
            assert adapter.meta.lifecycle_status == "ONLINE"

    def test_strategy_ids_unique(self):
        all_ids = [a.meta.strategy_id for a in _ALL_ADAPTERS]
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate strategy_ids detected: "
            f"{[x for x in all_ids if all_ids.count(x) > 1]}"
        )

    def test_all_lifecycle_statuses_valid(self):
        valid = set(LIFECYCLE_STATUSES)
        for a in _ALL_ADAPTERS:
            assert a.meta.lifecycle_status in valid, (
                f"{a.meta.strategy_id}: invalid status {a.meta.lifecycle_status!r}"
            )


# ─── Test class: fourier_rhythm_3bet adapter behavior ────────────────────────

class TestFourierRhythm3BetAdapter:
    """fourier_rhythm_3bet must be get_adapter()-accessible and ONLINE."""

    def test_get_adapter_returns_adapter(self):
        adapter = get_adapter("fourier_rhythm_3bet")
        assert adapter is not None
        assert adapter.meta.strategy_id == "fourier_rhythm_3bet"

    def test_adapter_lifecycle_status_is_online(self):
        adapter = get_adapter("fourier_rhythm_3bet")
        assert adapter.meta.lifecycle_status == "ONLINE"

    def test_adapter_supports_power_lotto(self):
        adapter = get_adapter("fourier_rhythm_3bet")
        assert "POWER_LOTTO" in adapter.meta.supported_lottery_types

    def test_adapter_not_in_non_executable_list(self):
        non_exec = list_non_executable_strategy_ids()
        assert "fourier_rhythm_3bet" not in non_exec

    def test_get_adapters_for_power_lotto_includes_fourier_rhythm_3bet(self):
        power_adapters = get_adapters_for_lottery("POWER_LOTTO")
        ids = {a.meta.strategy_id for a in power_adapters}
        assert "fourier_rhythm_3bet" in ids

    def test_min_history_is_reasonable(self):
        adapter = get_adapter("fourier_rhythm_3bet")
        assert adapter.meta.min_history >= 50, (
            f"min_history too low: {adapter.meta.min_history}"
        )


# ─── Test class: ts3_regime_3bet adapter behavior ────────────────────────────

class TestTs3Regime3BetAdapter:
    """ts3_regime_3bet is ONLINE but adapter binding is PENDING (P1.4).
    get_one_bet() must raise AdapterBindingPending, NOT LifecycleNotExecutable."""

    def test_get_adapter_returns_adapter(self):
        """ts3_regime_3bet must be in _REGISTRY (ONLINE)."""
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter is not None
        assert adapter.meta.strategy_id == "ts3_regime_3bet"

    def test_adapter_lifecycle_status_is_online(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter.meta.lifecycle_status == "ONLINE"

    def test_adapter_supports_big_lotto(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert "BIG_LOTTO" in adapter.meta.supported_lottery_types

    def test_get_one_bet_raises_adapter_binding_pending(self):
        """get_one_bet must raise AdapterBindingPending (not LifecycleNotExecutable)."""
        adapter = get_adapter("ts3_regime_3bet")
        with pytest.raises(AdapterBindingPending):
            adapter.get_one_bet([], "BIG_LOTTO")

    def test_get_one_bet_does_not_raise_lifecycle_not_executable(self):
        """ts3_regime_3bet is ONLINE — must NOT raise LifecycleNotExecutable."""
        adapter = get_adapter("ts3_regime_3bet")
        with pytest.raises(Exception) as exc_info:
            adapter.get_one_bet([], "BIG_LOTTO")
        assert not isinstance(exc_info.value, LifecycleNotExecutable), (
            "ts3_regime_3bet raised LifecycleNotExecutable but it is ONLINE. "
            "Expected AdapterBindingPending instead."
        )

    def test_get_adapters_for_big_lotto_includes_ts3_regime_3bet(self):
        big_adapters = get_adapters_for_lottery("BIG_LOTTO")
        ids = {a.meta.strategy_id for a in big_adapters}
        assert "ts3_regime_3bet" in ids

    def test_ts3_regime_3bet_not_in_non_executable_list(self):
        """ts3_regime_3bet is ONLINE — must NOT appear in non_executable list."""
        non_exec = list_non_executable_strategy_ids()
        assert "ts3_regime_3bet" not in non_exec

    def test_min_history_is_reasonable(self):
        adapter = get_adapter("ts3_regime_3bet")
        assert adapter.meta.min_history >= 50


# ─── Test class: No DB writes ─────────────────────────────────────────────────

class TestNoDbWrites:
    """Registry must not touch any database (structural checks, no reload)."""

    def test_registry_is_pure_in_memory(self):
        """Verify no DB-related attributes on registry module (structural check).
        Full reload test is in test_replay_strategy_lifecycle_registry.py.
        Duplicate reload would cause test-isolation issues with isinstance checks.
        """
        import lottery_api.models.replay_strategy_registry as mod
        # Module must not have a DB connection attribute
        assert not hasattr(mod, "_db_connection"), (
            "Registry module has _db_connection — possible DB write on import"
        )
        assert not hasattr(mod, "_db_path_bound"), (
            "Registry module has _db_path_bound — possible DB init on import"
        )


# ─── Test class: P1.3 governance metadata ────────────────────────────────────

class TestP13GovernanceMetadata:
    """Confirm P1.3 additions conform to governance requirements."""

    def test_fourier_rhythm_3bet_in_executable_list(self):
        exec_ids = list_executable_strategy_ids()
        assert "fourier_rhythm_3bet" in exec_ids

    def test_ts3_regime_3bet_in_executable_list(self):
        """ts3_regime_3bet is ONLINE so it must appear in executable list,
        even though its adapter raises AdapterBindingPending at runtime."""
        exec_ids = list_executable_strategy_ids()
        assert "ts3_regime_3bet" in exec_ids

    def test_both_new_strategies_have_valid_strategy_version(self):
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id in _P13_NEW_ONLINE_IDS:
                assert a.meta.strategy_version, (
                    f"{a.meta.strategy_id} missing strategy_version"
                )

    def test_fourier_rhythm_3bet_display_name_not_empty(self):
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id == "fourier_rhythm_3bet":
                assert a.meta.strategy_name, "fourier_rhythm_3bet has empty strategy_name"
                break

    def test_ts3_regime_3bet_display_name_not_empty(self):
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id == "ts3_regime_3bet":
                assert a.meta.strategy_name, "ts3_regime_3bet has empty strategy_name"
                break
