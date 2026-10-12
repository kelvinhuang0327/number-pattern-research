"""
test_replay_strategy_lifecycle_registry.py
===========================================
P2 lifecycle registry tests.

Validates:
1. Required canonical ONLINE strategies remain present and executable.
2. Every non-ONLINE stub appears in list_strategies() with its live lifecycle.
3. Non-ONLINE stubs raise LifecycleNotExecutable on get_one_bet().
4. Non-ONLINE stubs raise KeyError from get_adapter().
5. Strategy ID uniqueness and valid lifecycle status values.
6. No DB writes occur (registry is in-memory only).

Registry totals intentionally remain dynamic.  Adding a semantically valid unique
adapter must not require editing a historical count assertion.
"""
from __future__ import annotations

import pytest

from lottery_api.models.replay_strategy_registry import (
    LIFECYCLE_STATUSES,
    LifecycleNotExecutable,
    _ALL_ADAPTERS,
    _REGISTRY,
    get_adapter,
    get_adapters_for_lottery,
    get_strategy_lifecycle_status,
    list_strategies,
    normalise_lifecycle_status,
)

# ─── Expected strategy sets ───────────────────────────────────────────────────

# Historical canonical identities remain required; aggregate size is live data.
REQUIRED_ONLINE_IDS = frozenset({
    "power_precision_3bet",
    "power_orthogonal_5bet",
    # P1.3 additions:
    "fourier_rhythm_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    # P1.3 additions:
    "ts3_regime_3bet",
    "daily539_f4cold",
    "daily539_markov_cold",
})

REQUIRED_REJECTED_IDS = frozenset({
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "power_shlc_midfreq",
    "p1_deviation_2bet_539",
})

REQUIRED_RETIRED_IDS = frozenset({
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
})

REQUIRED_OBSERVATION_IDS = frozenset({
    "h6_gate_mk20_ew85",
})

REQUIRED_NON_ONLINE_IDS = (
    REQUIRED_REJECTED_IDS | REQUIRED_RETIRED_IDS | REQUIRED_OBSERVATION_IDS
)


def live_ids_for_status(status: str) -> set[str]:
    return {
        adapter.meta.strategy_id
        for adapter in _ALL_ADAPTERS
        if adapter.meta.lifecycle_status == status
    }


def live_non_online_ids() -> set[str]:
    return {
        adapter.meta.strategy_id
        for adapter in _ALL_ADAPTERS
        if adapter.meta.lifecycle_status != "ONLINE"
    }


# ─── Test class: ONLINE strategies are unchanged ─────────────────────────────

class TestOnlineStrategiesUnchanged:
    """Required canonical ONLINE identities must remain executable."""

    def test_registry_contains_required_online_ids(self):
        assert REQUIRED_ONLINE_IDS.issubset(_REGISTRY)
        assert set(_REGISTRY) == live_ids_for_status("ONLINE")

    def test_list_strategies_online_filter_returns_all_eight(self):
        online = list_strategies(lifecycle_status="ONLINE")
        ids = {s["strategy_id"] for s in online}
        assert ids == live_ids_for_status("ONLINE")
        assert REQUIRED_ONLINE_IDS.issubset(ids)

    def test_get_adapter_succeeds_for_all_online(self):
        for sid in REQUIRED_ONLINE_IDS:
            adapter = get_adapter(sid)
            assert adapter.meta.strategy_id == sid
            assert adapter.meta.lifecycle_status == "ONLINE"

    def test_get_adapters_for_lottery_returns_only_online_adapters(self):
        for lottery in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
            adapters = get_adapters_for_lottery(lottery)
            for a in adapters:
                assert a.meta.lifecycle_status == "ONLINE", (
                    f"get_adapters_for_lottery returned non-ONLINE adapter: "
                    f"{a.meta.strategy_id} ({a.meta.lifecycle_status})"
                )

    def test_online_strategy_lifecycle_status_lookup(self):
        for sid in REQUIRED_ONLINE_IDS:
            assert get_strategy_lifecycle_status(sid) == "ONLINE"


# ─── Test class: Non-ONLINE metadata is visible ───────────────────────────────

class TestNonOnlineMetadataVisible:
    """Non-ONLINE stubs must appear in list_strategies() and lifecycle lookups."""

    def test_all_non_online_ids_in_full_strategy_list(self):
        all_ids = {s["strategy_id"] for s in list_strategies()}
        assert REQUIRED_NON_ONLINE_IDS.issubset(all_ids)
        assert live_non_online_ids().issubset(all_ids)

    def test_list_strategies_filter_rejected(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="REJECTED")}
        assert ids == live_ids_for_status("REJECTED")
        assert REQUIRED_REJECTED_IDS.issubset(ids)

    def test_list_strategies_filter_retired(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="RETIRED")}
        assert ids == live_ids_for_status("RETIRED")
        assert REQUIRED_RETIRED_IDS.issubset(ids)

    def test_list_strategies_filter_observation(self):
        ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="OBSERVATION")}
        assert ids == live_ids_for_status("OBSERVATION")
        assert REQUIRED_OBSERVATION_IDS.issubset(ids)

    def test_get_strategy_lifecycle_status_rejected(self):
        for sid in REQUIRED_REJECTED_IDS:
            assert get_strategy_lifecycle_status(sid) == "REJECTED", \
                f"{sid} expected REJECTED"

    def test_get_strategy_lifecycle_status_retired(self):
        for sid in REQUIRED_RETIRED_IDS:
            assert get_strategy_lifecycle_status(sid) == "RETIRED", \
                f"{sid} expected RETIRED"

    def test_get_strategy_lifecycle_status_observation(self):
        for sid in REQUIRED_OBSERVATION_IDS:
            assert get_strategy_lifecycle_status(sid) == "OBSERVATION", \
                f"{sid} expected OBSERVATION"

    def test_non_online_not_in_online_list(self):
        online_ids = {s["strategy_id"] for s in list_strategies(lifecycle_status="ONLINE")}
        assert online_ids.isdisjoint(live_non_online_ids())


# ─── Test class: Non-ONLINE strategies cannot be executed ─────────────────────

class TestNonOnlineNotExecutable:
    """Non-ONLINE stubs must raise LifecycleNotExecutable on execution attempts."""

    def test_get_adapter_raises_key_error_for_non_online(self):
        for sid in live_non_online_ids():
            with pytest.raises(KeyError):
                get_adapter(sid)

    def test_get_one_bet_raises_lifecycle_not_executable(self):
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id in live_non_online_ids():
                with pytest.raises(LifecycleNotExecutable):
                    a.get_one_bet([], "POWER_LOTTO")

    def test_get_one_bet_raises_lifecycle_not_executable_all_lottery_types(self):
        """Stubs must raise regardless of lottery type argument."""
        for a in _ALL_ADAPTERS:
            if a.meta.strategy_id in live_non_online_ids():
                for lottery in ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539"):
                    with pytest.raises(LifecycleNotExecutable):
                        a.get_one_bet([], lottery)


# ─── Test class: Data integrity ───────────────────────────────────────────────

class TestDataIntegrity:
    """Registry data consistency checks."""

    def test_strategy_ids_unique_across_all_adapters(self):
        all_ids = [a.meta.strategy_id for a in _ALL_ADAPTERS]
        assert len(all_ids) == len(set(all_ids)), \
            f"Duplicate strategy_ids: {[x for x in all_ids if all_ids.count(x) > 1]}"

    def test_all_lifecycle_statuses_valid(self):
        valid = set(LIFECYCLE_STATUSES)
        for a in _ALL_ADAPTERS:
            assert a.meta.lifecycle_status in valid, \
                f"{a.meta.strategy_id}: invalid status {a.meta.lifecycle_status!r}"

    def test_required_canonical_identities_are_present(self):
        all_ids = {adapter.meta.strategy_id for adapter in _ALL_ADAPTERS}
        assert (REQUIRED_ONLINE_IDS | REQUIRED_NON_ONLINE_IDS).issubset(all_ids)

    def test_list_strategies_matches_adapter_universe(self):
        listed_ids = {row["strategy_id"] for row in list_strategies()}
        adapter_ids = {adapter.meta.strategy_id for adapter in _ALL_ADAPTERS}
        assert listed_ids == adapter_ids

    def test_active_alias_resolves_consistently_to_online(self):
        assert normalise_lifecycle_status("ACTIVE") == "ONLINE"
        active_ids = {row["strategy_id"] for row in list_strategies(lifecycle_status="ACTIVE")}
        online_ids = {row["strategy_id"] for row in list_strategies(lifecycle_status="ONLINE")}
        assert active_ids == online_ids

    def test_no_duplicate_executable_adapter_entrypoints(self):
        adapter_object_ids = [id(adapter) for adapter in _REGISTRY.values()]
        assert len(adapter_object_ids) == len(set(adapter_object_ids))

    def test_unknown_strategy_id_returns_none_from_lifecycle_status(self):
        assert get_strategy_lifecycle_status("__not_a_real_strategy__") is None

    def test_no_db_write_on_import(self, tmp_path, monkeypatch):
        """Importing the registry must not touch any database."""
        import sqlite3
        calls: list = []
        orig_connect = sqlite3.connect

        def mock_connect(*args, **kwargs):
            calls.append(args)
            return orig_connect(*args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", mock_connect)
        # Re-import triggers module-level code; no connect call expected
        import importlib
        import lottery_api.models.replay_strategy_registry as mod
        importlib.reload(mod)
        assert calls == [], f"Unexpected sqlite3.connect calls: {calls}"
