"""Vertical acceptance tests for the target-native Big Lotto P0 2Bet IDs."""
from __future__ import annotations

import ast
import builtins
import copy
import inspect
import json
import os
import random
import socket
import sqlite3
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from lottery_api.models import biglotto_p0_2bet_adapter as p0
from lottery_api.models import biglotto_zone_split_adapter as zone
from lottery_api.models import replay_strategy_registry as registry


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures/biglotto_p0_2bet_parity.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
HISTORY = FIXTURE["history"]
EXPECTED_BETS = [FIXTURE["expected_bet1"], FIXTURE["expected_bet2"]]

BET1_ID = "biglotto_p0_2bet_bet1"
BET2_ID = "biglotto_p0_2bet_bet2"
FAMILY_ID = "biglotto_p0_2bet"
EXPECTED_METADATA = {
    BET1_ID: {
        "strategy_id": BET1_ID,
        "strategy_name": "大樂透 P0 偏差互補＋回聲 2注（Replay Bet 1）",
        "strategy_version": "v0.1",
        "supported_lottery_types": ["BIG_LOTTO"],
        "min_history": 1,
        "lifecycle_status": "ONLINE",
    },
    BET2_ID: {
        "strategy_id": BET2_ID,
        "strategy_name": "大樂透 P0 偏差互補＋回聲 2注（Replay Bet 2）",
        "strategy_version": "v0.1",
        "supported_lottery_types": ["BIG_LOTTO"],
        "min_history": 1,
        "lifecycle_status": "ONLINE",
    },
}


def _row(index: int, numbers: list[int]) -> dict:
    return {
        "draw": f"d{index}",
        "date": f"2026-07-{(index % 28) + 1:02d}",
        "numbers": numbers,
        "special": 49,
    }


def _history(*number_rows: list[int]) -> list[dict]:
    return [_row(index, numbers) for index, numbers in enumerate(number_rows)]


def _assert_numpy_state_equal(left: tuple, right: tuple) -> None:
    assert left[0] == right[0]
    assert np.array_equal(left[1], right[1])
    assert left[2:] == right[2:]


def test_exact_public_ids_and_no_aggregate_executable_id():
    assert p0.BET1_STRATEGY_ID == BET1_ID
    assert p0.BET2_STRATEGY_ID == BET2_ID
    assert p0.STRATEGY_IDS == (BET1_ID, BET2_ID)
    assert FAMILY_ID not in registry.list_executable_strategy_ids()
    assert FAMILY_ID not in {
        adapter.meta.strategy_id for adapter in registry._ALL_ADAPTERS
    }


def test_exact_metadata_registry_resolution_and_online_lifecycle():
    for strategy_id in (BET1_ID, BET2_ID):
        adapter = registry.get_adapter(strategy_id)
        assert adapter.meta.strategy_id == strategy_id
        assert adapter.meta.status == "ONLINE"
        assert adapter.meta.lifecycle_status == "ONLINE"
        assert registry.get_strategy_lifecycle_metadata(strategy_id) == (
            EXPECTED_METADATA[strategy_id]
        )
        assert strategy_id in registry.list_executable_strategy_ids()


def test_shared_producer_matches_both_golden_tickets():
    assert p0._p0_2bet_bets(copy.deepcopy(HISTORY)) == EXPECTED_BETS


def test_each_public_adapter_returns_its_one_golden_ticket_without_special():
    for strategy_id, expected in zip((BET1_ID, BET2_ID), EXPECTED_BETS):
        numbers, special = registry.get_adapter(strategy_id).get_one_bet(
            copy.deepcopy(HISTORY),
            "BIG_LOTTO",
        )
        assert numbers == expected
        assert special is None


def test_both_adapters_use_the_same_two_ticket_producer(monkeypatch):
    calls: list[list[dict]] = []

    def fake_producer(history, error_type=ValueError):
        calls.append(copy.deepcopy(history))
        return [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]

    monkeypatch.setattr(p0, "_p0_2bet_bets", fake_producer)
    one_row = _history([1, 2, 3, 4, 5, 6])
    assert registry.get_adapter(BET1_ID).get_one_bet(
        one_row,
        "BIG_LOTTO",
    ) == ([1, 2, 3, 4, 5, 6], None)
    assert registry.get_adapter(BET2_ID).get_one_bet(
        one_row,
        "BIG_LOTTO",
    ) == ([7, 8, 9, 10, 11, 12], None)
    assert calls == [one_row, one_row]


def test_only_the_final_50_rows_affect_scoring():
    history = copy.deepcopy(HISTORY)
    assert len(history) > 50
    assert p0._p0_2bet_bets(history) == p0._p0_2bet_bets(history[-50:])


def test_lag_two_echo_promotes_the_second_to_last_draw():
    history = _history(
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
    )
    bet1, _ = p0._p0_2bet_bets(history)
    assert bet1 == [7, 8, 9, 10, 11, 12]


def test_bet1_score_ties_choose_lower_numbers_first():
    history = _history(
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 7],
        [1, 2, 3, 6, 7, 8],
        [4, 5, 6, 7, 9, 10],
        [11, 12, 13, 14, 15, 16],
        [17, 18, 19, 20, 21, 22],
        [23, 24, 25, 26, 27, 28],
        [29, 30, 31, 32, 33, 34],
        [40, 41, 42, 43, 44, 45],
        [35, 36, 37, 38, 39, 46],
    )
    bet1, _ = p0._p0_2bet_bets(history)
    assert bet1 == [1, 2, 3, 4, 5, 6]


def test_bet1_fallback_uses_absolute_score_then_number():
    bet1, _ = p0._p0_2bet_bets(_history([1, 2, 3, 4, 5, 6]))
    assert bet1 == [7, 8, 9, 10, 11, 12]


def test_bet2_cold_ranking_prefers_larger_absolute_deviation():
    rows = [[1, 2, 3, 4, 5, 6] for _ in range(17)]
    rows.append([1, 2, 3, 4, 5, 7])
    bet1, bet2 = p0._p0_2bet_bets(_history(*rows))
    assert bet1 == [1, 2, 3, 4, 5, 6]
    assert bet2 == [8, 9, 10, 11, 12, 13]


def test_bet2_is_disjoint_from_bet1():
    bet1, bet2 = p0._p0_2bet_bets(copy.deepcopy(HISTORY))
    assert set(bet1).isdisjoint(bet2)


def test_bet2_numeric_fallback_uses_remaining_numbers():
    bet1, bet2 = p0._p0_2bet_bets(_history([1, 2, 3, 4, 5, 6]))
    assert bet1 == [7, 8, 9, 10, 11, 12]
    assert bet2 == [1, 2, 3, 4, 5, 6]


def test_repeated_calls_are_deterministic():
    first = p0._p0_2bet_bets(copy.deepcopy(HISTORY))
    second = p0._p0_2bet_bets(copy.deepcopy(HISTORY))
    assert first == second


def test_python_and_numpy_rng_state_are_isolated():
    python_before = random.getstate()
    numpy_before = np.random.get_state()
    result = p0._p0_2bet_bets(copy.deepcopy(HISTORY))
    python_after = random.getstate()
    numpy_after = np.random.get_state()

    assert result == EXPECTED_BETS
    assert python_before == python_after
    _assert_numpy_state_equal(numpy_before, numpy_after)


def test_caller_history_is_unchanged():
    history = copy.deepcopy(HISTORY)
    before = copy.deepcopy(history)
    before_bytes = json.dumps(
        history,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    p0._p0_2bet_bets(history)
    registry.get_adapter(BET1_ID).get_one_bet(history, "BIG_LOTTO")
    registry.get_adapter(BET2_ID).get_one_bet(history, "BIG_LOTTO")

    assert history == before
    assert json.dumps(
        history,
        sort_keys=True,
        separators=(",", ":"),
    ).encode() == before_bytes


def test_empty_history_raises_registry_insufficient_history():
    for strategy_id in (BET1_ID, BET2_ID):
        with pytest.raises(registry.InsufficientHistory):
            registry.get_adapter(strategy_id).get_one_bet([], "BIG_LOTTO")


@pytest.mark.parametrize(
    "history",
    [
        None,
        (),
        iter(()),
        "history",
        {"draw": "1"},
        type("ListSubclass", (list,), {})([_row(0, [1, 2, 3, 4, 5, 6])]),
    ],
)
def test_non_exact_list_history_fails_closed(history):
    with pytest.raises(registry.InvalidOutput):
        registry.get_adapter(BET1_ID).get_one_bet(history, "BIG_LOTTO")


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {"draw": "", "date": "2026-07-01", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "1", "date": "", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": 1, "date": "2026-07-01", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "1", "date": 1, "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "1", "date": "2026-07-01", "numbers": "123456"},
        {"draw": "1", "date": "2026-07-01", "numbers": [1, 2, 3, 4, 5]},
        {"draw": "1", "date": "2026-07-01", "numbers": [1, 1, 2, 3, 4, 5]},
        {"draw": "1", "date": "2026-07-01", "numbers": [1, 2, 3, 4, 5, 50]},
        {"draw": "1", "date": "2026-07-01", "numbers": [1, 2, 3, 4, 5, True]},
    ],
)
def test_malformed_rows_and_invalid_numbers_fail_closed(row):
    with pytest.raises(registry.InvalidOutput):
        registry.get_adapter(BET1_ID).get_one_bet([row], "BIG_LOTTO")


def test_unsupported_lottery_fails_closed_before_history_processing():
    for strategy_id in (BET1_ID, BET2_ID):
        with pytest.raises(registry.UnsupportedLotteryType):
            registry.get_adapter(strategy_id).get_one_bet([], "POWER_LOTTO")


def test_original_and_recovered_donor_modules_are_not_runtime_imported():
    donor_modules = (
        "tools.quick_predict",
        "recovered_strategies.biglotto.historical_adapters",
    )
    for module_name in donor_modules:
        sys.modules.pop(module_name, None)

    assert registry.get_adapter(BET1_ID).get_one_bet(
        copy.deepcopy(HISTORY),
        "BIG_LOTTO",
    )[0] == EXPECTED_BETS[0]
    assert registry.get_adapter(BET2_ID).get_one_bet(
        copy.deepcopy(HISTORY),
        "BIG_LOTTO",
    )[0] == EXPECTED_BETS[1]
    assert all(module_name not in sys.modules for module_name in donor_modules)


def test_target_source_has_no_donor_or_external_state_imports():
    source = inspect.getsource(p0)
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported_roots.isdisjoint(
        {
            "datetime",
            "numpy",
            "os",
            "pathlib",
            "random",
            "requests",
            "socket",
            "sqlite3",
            "subprocess",
            "time",
            "tools",
            "urllib",
        }
    )
    assert "recovered_strategies" not in source
    assert "quick_predict" not in source


def test_prediction_performs_no_file_db_environment_or_network_access(
    monkeypatch,
):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("external-state access is forbidden")

    history = copy.deepcopy(HISTORY)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)

    assert registry.get_adapter(BET1_ID).get_one_bet(
        history,
        "BIG_LOTTO",
    ) == (EXPECTED_BETS[0], None)
    assert registry.get_adapter(BET2_ID).get_one_bet(
        history,
        "BIG_LOTTO",
    ) == (EXPECTED_BETS[1], None)


def test_zone_split_ids_and_metadata_remain_unchanged():
    expected = {
        zone.STRATEGY_IDS[0]: ("大樂透 Zone Split 3注（Replay Bet 1）", "v0.1", 1),
        zone.STRATEGY_IDS[1]: ("大樂透 Zone Split 3注（Replay Bet 2）", "v0.1", 1),
        zone.STRATEGY_IDS[2]: ("大樂透 Zone Split 3注（Replay Bet 3）", "v0.1", 1),
    }
    for strategy_id, metadata in expected.items():
        adapter = registry.get_adapter(strategy_id)
        assert (
            adapter.meta.strategy_name,
            adapter.meta.strategy_version,
            adapter.meta.min_history,
        ) == metadata
        assert adapter.meta.supported_lottery_types == ["BIG_LOTTO"]
        assert adapter.meta.lifecycle_status == "ONLINE"


def test_social_wisdom_identity_and_metadata_remain_unchanged():
    strategy_id = "biglotto_social_wisdom_anti_popularity"
    adapter = registry.get_adapter(strategy_id)
    assert adapter.meta.strategy_name == "大樂透 Social Wisdom Anti-Popularity"
    assert adapter.meta.strategy_version == "v0.1"
    assert adapter.meta.supported_lottery_types == ["BIG_LOTTO"]
    assert adapter.meta.min_history == 1
    assert adapter.meta.lifecycle_status == "ONLINE"


def test_ts3_identity_and_metadata_remain_unchanged():
    adapter = registry.get_adapter("ts3_regime_3bet")
    assert adapter.meta.strategy_name == "大樂透 TS3+Regime 3注"
    assert adapter.meta.strategy_version == "v0.1"
    assert adapter.meta.supported_lottery_types == ["BIG_LOTTO"]
    assert adapter.meta.min_history == 100
    assert adapter.meta.lifecycle_status == "ONLINE"


def test_lifecycle_registry_remains_unique_and_consistent():
    all_ids = [adapter.meta.strategy_id for adapter in registry._ALL_ADAPTERS]
    online_ids = {
        adapter.meta.strategy_id
        for adapter in registry._ALL_ADAPTERS
        if adapter.meta.lifecycle_status == "ONLINE"
    }
    listed_ids = {
        row["strategy_id"] for row in registry.list_strategy_lifecycle_metadata()
    }

    assert len(all_ids) == len(set(all_ids))
    assert set(registry._REGISTRY) == online_ids
    assert listed_ids == set(all_ids)
    assert {BET1_ID, BET2_ID}.issubset(online_ids)
