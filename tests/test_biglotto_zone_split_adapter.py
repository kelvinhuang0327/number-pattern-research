"""Target-native Big Lotto Zone Split vertical acceptance tests."""
from __future__ import annotations

import ast
import copy
import inspect
import json
import random
from pathlib import Path

import pytest

from lottery_api.models import biglotto_zone_split_adapter as zone
from lottery_api.models import replay_strategy_registry as registry
from lottery_api.routes import replay as replay_route


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures/biglotto_zone_split_p541d.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
HISTORY = FIXTURE["canonical_history"]
IDS = FIXTURE["strategy_ids"]
EXPECTED = [
    FIXTURE["expected_bet1"],
    FIXTURE["expected_bet2"],
    FIXTURE["expected_bet3"],
]


def _make_ts3_history(n: int = 100) -> list[dict]:
    rng = random.Random(42)
    return [
        {
            "numbers": sorted(rng.sample(range(1, 50), 6)),
            "special": rng.randint(1, 8),
            "draw": str(110000000 + index),
            "date": f"2025-01-{(index % 28) + 1:02d}",
        }
        for index in range(n)
    ]


def test_exact_bet1_golden_parity():
    assert registry.get_adapter(IDS[0]).get_one_bet(HISTORY, "BIG_LOTTO") == (
        EXPECTED[0],
        None,
    )


def test_exact_bet2_golden_parity():
    assert registry.get_adapter(IDS[1]).get_one_bet(HISTORY, "BIG_LOTTO") == (
        EXPECTED[1],
        None,
    )


def test_exact_bet3_golden_parity():
    assert registry.get_adapter(IDS[2]).get_one_bet(HISTORY, "BIG_LOTTO") == (
        EXPECTED[2],
        None,
    )


def test_exact_generation_order_and_bet1_seed_identity():
    assert FIXTURE["generation_order"] == IDS
    assert FIXTURE["seed_identity"]["strategy_id"] == IDS[0]
    assert zone._zone_seed_digest(HISTORY) == FIXTURE["seed_identity"]["sha256"]
    assert zone._zone_split_bets(HISTORY) == EXPECTED


def test_repeatability():
    first = [registry.get_adapter(strategy_id).get_one_bet(HISTORY, "BIG_LOTTO") for strategy_id in IDS]
    second = [
        registry.get_adapter(strategy_id).get_one_bet(
            copy.deepcopy(HISTORY),
            "BIG_LOTTO",
        )
        for strategy_id in IDS
    ]
    assert first == second


def test_global_rng_isolation():
    before = random.getstate()
    zone._zone_split_bets(HISTORY)
    assert random.getstate() == before


def test_one_sequential_local_rng_contract(monkeypatch):
    real_random = random.Random
    events = []

    class TrackingRandom:
        def __init__(self, seed):
            events.append(("init", seed))
            self._rng = real_random(seed)

        def sample(self, pool, count):
            events.append(("sample", list(pool), count))
            return self._rng.sample(pool, count)

    monkeypatch.setattr(zone.random, "Random", TrackingRandom)
    assert zone._zone_split_bets(HISTORY) == EXPECTED
    assert [event[0] for event in events] == ["init", "sample", "sample", "sample"]
    assert [event[1] for event in events[1:]] == zone._zone_split_pools()


def test_minimum_history_boundary():
    assert FIXTURE["minimum_history"] == 1
    for strategy_id, expected in zip(IDS, EXPECTED):
        assert registry.get_adapter(strategy_id).get_one_bet(
            HISTORY,
            "BIG_LOTTO",
        ) == (expected, None)


def test_insufficient_history_fails_closed():
    for strategy_id in IDS:
        with pytest.raises(registry.InsufficientHistory):
            registry.get_adapter(strategy_id).get_one_bet([], "BIG_LOTTO")


def test_malformed_history_uses_target_invalid_output():
    for strategy_id in IDS:
        with pytest.raises(registry.InvalidOutput):
            registry.get_adapter(strategy_id).get_one_bet(
                [{"draw": "1", "date": "2026-01-01", "numbers": [1, 2, 3]}],
                "BIG_LOTTO",
            )


def test_input_history_is_unchanged():
    history = copy.deepcopy(HISTORY)
    before = copy.deepcopy(history)
    before_bytes = json.dumps(history, sort_keys=True).encode()
    for strategy_id in IDS:
        registry.get_adapter(strategy_id).get_one_bet(history, "BIG_LOTTO")
    assert history == before
    assert json.dumps(history, sort_keys=True).encode() == before_bytes


def test_exact_public_ids_and_no_aggregate_id():
    registered = {
        item["strategy_id"] for item in registry.list_strategy_lifecycle_metadata()
    }
    matching = {
        strategy_id
        for strategy_id in registered
        if strategy_id.startswith("biglotto_zone_split_3bet")
    }
    assert matching == set(IDS)
    assert "biglotto_zone_split_3bet" not in registered


def test_registry_resolves_all_three_executable_adapters():
    assert all(registry.get_adapter(strategy_id) for strategy_id in IDS)
    assert set(IDS).issubset(registry.list_executable_strategy_ids())
    assert set(IDS).isdisjoint(registry.list_non_executable_strategy_ids())


def test_bet1_metadata_remains_compatible_except_executable_lifecycle():
    metadata = registry.get_strategy_lifecycle_metadata(IDS[0])
    assert metadata == {
        "strategy_id": IDS[0],
        "strategy_name": "大樂透 Zone Split 3注（Replay Bet 1）",
        "strategy_version": "v0.1",
        "supported_lottery_types": ["BIG_LOTTO"],
        "min_history": 1,
        "lifecycle_status": "ONLINE",
    }


def test_ts3_regime_3bet_behavior_remains_unchanged():
    assert registry.get_adapter("ts3_regime_3bet").get_one_bet(
        _make_ts3_history(),
        "BIG_LOTTO",
    ) == ([9, 19, 26, 28, 38, 42], None)


def test_replay_lifecycle_metadata_is_route_compatible_without_route_edits():
    route_metadata = replay_route.list_strategy_lifecycle_metadata()
    route_ids = {item["strategy_id"] for item in route_metadata}
    assert set(IDS).issubset(route_ids)
    assert set(IDS).issubset(replay_route.list_executable_strategy_ids())


def test_target_has_exact_donor_provenance_without_runtime_donor_import():
    assert FIXTURE["donor_ref"] == "24617fe3bb7ec087acf121f302bffd638ccfa179"
    assert FIXTURE["donor_source_path"] == (
        "lottery_api/models/p541d_r2_biglotto_selected_adapters.py"
    )
    assert FIXTURE["donor_symbol"] == "_zone_split_bets"
    assert FIXTURE["donor_test_path"] == (
        "tests/test_p541d_r2_biglotto_selected_adapters.py"
    )

    tree = ast.parse(inspect.getsource(zone))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert "lottery_api.models.p541d_r2_biglotto_selected_adapters" not in imports
