"""Focused no-DB acceptance tests for target-native Big Lotto Social Wisdom."""
from __future__ import annotations

import ast
import builtins
import copy
import importlib
import inspect
import json
import os
import socket
import sqlite3
import sys
import urllib.request

import numpy as np
import pytest

from lottery_api.models import replay_strategy_registry as registry


STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
TARGET_MODULE_NAME = "lottery_api.models.biglotto_social_wisdom_adapter"
PREDICTOR_MODULE_NAME = "lottery_api.models.social_wisdom_predictor"
DONOR_MODULE_NAME = "lottery_api.models.p541d_r2_biglotto_selected_adapters"
ZONE_IDS = (
    "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet2",
    "biglotto_zone_split_3bet_bet3",
)
EXPECTED_META = {
    "strategy_id": STRATEGY_ID,
    "strategy_name": "大樂透 Social Wisdom Anti-Popularity",
    "strategy_version": "v0.1",
    "supported_lottery_types": ["BIG_LOTTO"],
    "min_history": 1,
    "lifecycle_status": "ONLINE",
}


def _history(count: int = 60) -> list[dict]:
    return [
        {
            "draw": f"d{index}",
            "date": f"2025-{index // 28 + 1:02d}-{index % 28 + 1:02d}",
            "numbers": sorted(
                {
                    index % 49 + 1,
                    (index + 7) % 49 + 1,
                    (index + 14) % 49 + 1,
                    (index + 21) % 49 + 1,
                    (index + 28) % 49 + 1,
                    (index + 35) % 49 + 1,
                }
            ),
            "ignored": {"index": index},
        }
        for index in range(count)
    ]


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _assert_rng_state_equal(left: tuple, right: tuple) -> None:
    assert left[0] == right[0]
    assert np.array_equal(left[1], right[1])
    assert left[2:] == right[2:]


def test_exact_public_strategy_id_and_single_registration():
    matching = [
        adapter
        for adapter in registry._ALL_ADAPTERS
        if adapter.meta.strategy_id == STRATEGY_ID
    ]
    assert len(matching) == 1
    assert matching[0].meta.strategy_id == STRATEGY_ID


def test_exact_metadata_and_online_lifecycle():
    adapter = registry.get_adapter(STRATEGY_ID)
    assert registry.get_strategy_lifecycle_metadata(STRATEGY_ID) == EXPECTED_META
    assert adapter.meta.status == "ONLINE"
    assert adapter.meta.lifecycle_status == "ONLINE"


def test_registry_lookup_and_executable_membership_succeed():
    adapter = registry.get_adapter(STRATEGY_ID)
    assert adapter.meta.strategy_id == STRATEGY_ID
    assert STRATEGY_ID in registry.list_executable_strategy_ids()
    assert STRATEGY_ID not in registry.list_non_executable_strategy_ids()
    assert STRATEGY_ID in {
        item.meta.strategy_id
        for item in registry.get_adapters_for_lottery("BIG_LOTTO")
    }


def test_exact_donor_direct_call_parity():
    from lottery_api.models.social_wisdom_predictor import SocialWisdomPredictor

    history = _history()
    direct_history = [
        {
            "draw": row["draw"],
            "date": row["date"],
            "numbers": sorted(row["numbers"]),
        }
        for row in history[-50:]
    ]
    direct_history.reverse()
    expected = SocialWisdomPredictor(max_num=49).predict(
        direct_history,
        pick_count=6,
    )

    actual, special = registry.get_adapter(STRATEGY_ID).get_one_bet(
        history,
        "BIG_LOTTO",
    )
    assert actual == expected
    assert special is None


def test_final_50_newest_first_canonical_copies_and_input_immutability(monkeypatch):
    predictor_module = importlib.import_module(PREDICTOR_MODULE_NAME)
    received: list[dict] = []

    class SpyPredictor:
        def __init__(self, max_num):
            assert max_num == 49

        def predict(self, history, pick_count):
            assert pick_count == 6
            received.extend(copy.deepcopy(history))
            history[0]["numbers"][0] = 49
            return [1, 2, 3, 4, 5, 6]

    monkeypatch.setattr(predictor_module, "SocialWisdomPredictor", SpyPredictor)
    history = _history()
    before = copy.deepcopy(history)
    before_bytes = _json_bytes(history)

    numbers, special = registry.get_adapter(STRATEGY_ID).get_one_bet(
        history,
        "BIG_LOTTO",
    )

    assert [row["draw"] for row in received] == [
        f"d{index}" for index in range(59, 9, -1)
    ]
    assert all(list(row) == ["draw", "date", "numbers"] for row in received)
    assert all(type(row) is dict for row in received)
    assert all(type(row["numbers"]) is list for row in received)
    assert numbers == [1, 2, 3, 4, 5, 6]
    assert special is None
    assert history == before
    assert _json_bytes(history) == before_bytes


def test_repeated_calls_are_deterministic():
    adapter = registry.get_adapter(STRATEGY_ID)
    history = _history()
    first = adapter.get_one_bet(copy.deepcopy(history), "BIG_LOTTO")
    second = adapter.get_one_bet(copy.deepcopy(history), "BIG_LOTTO")
    assert first == second


def test_numpy_global_rng_seed_and_state_do_not_affect_output():
    adapter = registry.get_adapter(STRATEGY_ID)
    history = _history()
    original_state = np.random.get_state()
    try:
        outputs = []
        for seed in (7, 998_244_353):
            np.random.seed(seed)
            before = np.random.get_state()
            outputs.append(adapter.get_one_bet(copy.deepcopy(history), "BIG_LOTTO"))
            after = np.random.get_state()
            _assert_rng_state_equal(before, after)
        assert outputs[0] == outputs[1]
    finally:
        np.random.set_state(original_state)


def test_predict_called_exactly_once_and_excluded_methods_never_called(monkeypatch):
    predictor_module = importlib.import_module(PREDICTOR_MODULE_NAME)
    calls = {"predict": 0}

    class SpyPredictor:
        def __init__(self, max_num):
            assert max_num == 49

        def predict(self, history, pick_count):
            calls["predict"] += 1
            return [1, 2, 3, 4, 5, 6]

        def predict_with_balance(self, *_args, **_kwargs):
            raise AssertionError("predict_with_balance must not be called")

        def generate_8_bets(self, *_args, **_kwargs):
            raise AssertionError("generate_8_bets must not be called")

    monkeypatch.setattr(predictor_module, "SocialWisdomPredictor", SpyPredictor)
    result = registry.get_adapter(STRATEGY_ID).get_one_bet(
        _history(),
        "BIG_LOTTO",
    )
    assert result == ([1, 2, 3, 4, 5, 6], None)
    assert calls == {"predict": 1}


def test_unsupported_lottery_fails_closed():
    with pytest.raises(registry.UnsupportedLotteryType):
        registry.get_adapter(STRATEGY_ID).get_one_bet(_history(), "POWER_LOTTO")


def test_empty_history_fails_closed_through_target_contract():
    with pytest.raises(registry.InsufficientHistory):
        registry.get_adapter(STRATEGY_ID).get_one_bet([], "BIG_LOTTO")


@pytest.mark.parametrize(
    "history",
    [
        None,
        (),
        iter(()),
        "history",
        {"draw": "1"},
        type("ListSubclass", (list,), {})(_history(1)),
    ],
)
def test_non_list_history_fails_closed(history):
    with pytest.raises(registry.InvalidOutput):
        registry.get_adapter(STRATEGY_ID).get_one_bet(history, "BIG_LOTTO")


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {"draw": "", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "1", "date": "", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": 1, "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "1", "date": 1, "numbers": [1, 2, 3, 4, 5, 6]},
        {"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3]},
        {"draw": "1", "date": "2026-01-01", "numbers": [1, 1, 2, 3, 4, 5]},
        {"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, 50]},
        {"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3, 4, 5, True]},
    ],
)
def test_invalid_history_row_fails_closed(row):
    with pytest.raises(registry.InvalidOutput):
        registry.get_adapter(STRATEGY_ID).get_one_bet([row], "BIG_LOTTO")


@pytest.mark.parametrize(
    "output",
    [
        None,
        (),
        [],
        [1, 2, 3, 4, 5],
        [1, 1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5, 50],
        [1, 2, 3, 4, 5, True],
    ],
)
def test_invalid_predictor_output_fails_closed(monkeypatch, output):
    predictor_module = importlib.import_module(PREDICTOR_MODULE_NAME)

    class InvalidPredictor:
        def __init__(self, max_num):
            assert max_num == 49

        def predict(self, history, pick_count):
            return output

    monkeypatch.setattr(
        predictor_module,
        "SocialWisdomPredictor",
        InvalidPredictor,
    )
    with pytest.raises(registry.InvalidOutput):
        registry.get_adapter(STRATEGY_ID).get_one_bet(
            _history(1),
            "BIG_LOTTO",
        )


def test_donor_adapter_module_is_not_imported_at_runtime():
    sys.modules.pop(DONOR_MODULE_NAME, None)
    result = registry.get_adapter(STRATEGY_ID).get_one_bet(
        _history(),
        "BIG_LOTTO",
    )
    assert result[1] is None
    assert DONOR_MODULE_NAME not in sys.modules


def test_target_adapter_source_excludes_external_state_and_alternate_methods():
    module = importlib.import_module(TARGET_MODULE_NAME)
    source = inspect.getsource(module)
    tree = ast.parse(source)
    forbidden_import_roots = {
        "os",
        "pathlib",
        "sqlite3",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "random",
        "numpy",
        "time",
        "datetime",
    }
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
    assert imported_roots.isdisjoint(forbidden_import_roots)
    assert "predict_with_balance" not in source
    assert "generate_8_bets" not in source
    assert DONOR_MODULE_NAME not in source


def test_prediction_call_performs_no_file_db_environment_or_network_access(
    monkeypatch,
):
    importlib.import_module(PREDICTOR_MODULE_NAME)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("external-state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    numbers, special = registry.get_adapter(STRATEGY_ID).get_one_bet(
        _history(),
        "BIG_LOTTO",
    )
    assert len(numbers) == 6
    assert special is None


def test_three_zone_split_ids_remain_executable_and_unchanged():
    expected = {
        ZONE_IDS[0]: ("大樂透 Zone Split 3注（Replay Bet 1）", "v0.1", 1),
        ZONE_IDS[1]: ("大樂透 Zone Split 3注（Replay Bet 2）", "v0.1", 1),
        ZONE_IDS[2]: ("大樂透 Zone Split 3注（Replay Bet 3）", "v0.1", 1),
    }
    for strategy_id, (name, version, min_history) in expected.items():
        adapter = registry.get_adapter(strategy_id)
        assert (
            adapter.meta.strategy_name,
            adapter.meta.strategy_version,
            adapter.meta.min_history,
        ) == (name, version, min_history)
        assert adapter.meta.supported_lottery_types == ["BIG_LOTTO"]
        assert adapter.meta.lifecycle_status == "ONLINE"


def test_ts3_regime_remains_executable_and_unchanged():
    adapter = registry.get_adapter("ts3_regime_3bet")
    assert adapter.meta.strategy_name == "大樂透 TS3+Regime 3注"
    assert adapter.meta.strategy_version == "v0.1"
    assert adapter.meta.supported_lottery_types == ["BIG_LOTTO"]
    assert adapter.meta.min_history == 100
    assert adapter.meta.lifecycle_status == "ONLINE"


def test_replay_lifecycle_metadata_remains_route_compatible_without_db(
    monkeypatch,
):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    replay_route = importlib.import_module("lottery_api.routes.replay")
    assert STRATEGY_ID in replay_route.list_executable_strategy_ids()
    metadata = {
        row["strategy_id"]: row
        for row in replay_route.list_strategy_lifecycle_metadata()
    }
    assert metadata[STRATEGY_ID] == EXPECTED_META
