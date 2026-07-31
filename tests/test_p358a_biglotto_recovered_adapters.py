import importlib
import sqlite3

import pytest


def fixture_history(size=120):
    draws = []
    for idx in range(size):
        start = (idx * 7) % 49
        numbers = sorted((((start + offset * 8) % 49) + 1) for offset in range(6))
        if len(set(numbers)) < 6:
            numbers = sorted({((idx + offset * 11) % 49) + 1 for offset in range(9)})[:6]
        draws.append(
            {
                "draw": f"T{idx:04d}",
                "date": f"2026/01/{(idx % 28) + 1:02d}",
                "numbers": numbers,
                "special": ((idx * 5) % 49) + 1,
            }
        )
    return draws


def assert_biglotto_bets(bets, expected_count):
    assert isinstance(bets, list)
    assert len(bets) == expected_count
    for bet in bets:
        assert isinstance(bet, list)
        assert bet == sorted(bet)
        assert len(bet) == 6
        assert len(set(bet)) == 6
        assert all(1 <= n <= 49 for n in bet)


def test_import_does_not_require_production_registry_or_open_db(monkeypatch):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", blocked_connect)
    module = importlib.import_module("recovered_strategies.biglotto.historical_adapters")
    assert "adapt_biglotto_p0_2bet" in module.ADAPTER_METADATA


@pytest.mark.parametrize(
    ("function_name", "expected_count"),
    [
        ("adapt_biglotto_p0_2bet", 2),
        ("adapt_predict_biglotto_echo_2bet", 2),
        ("adapt_predict_biglotto_echo_phase2_2bet", 2),
        ("adapt_predict_biglotto_echo_phase2_3bet", 3),
        ("adapt_predict_biglotto_echo_mixed_3bet", 3),
        ("adapt_biglotto_zonal_pruning", 4),
        ("adapt_biglotto_5bet_orthogonal", 5),
        ("adapt_predict_biglotto_regime_3bet", 3),
        ("adapt_biglotto_10bet_combined", 10),
    ],
)
def test_adapters_are_deterministic_valid_and_no_db(monkeypatch, function_name, expected_count):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", blocked_connect)
    from recovered_strategies.biglotto import historical_adapters as adapters

    func = getattr(adapters, function_name)
    history = fixture_history()
    first = func(history)
    second = func(history)
    assert first == second
    assert_biglotto_bets(first, expected_count)


def test_shape_only_adapters_are_labeled():
    from recovered_strategies.biglotto.historical_adapters import ADAPTER_METADATA

    shape_only = {
        "adapt_biglotto_zonal_pruning",
        "adapt_biglotto_5bet_orthogonal",
        "adapt_predict_biglotto_regime_3bet",
        "adapt_biglotto_10bet_combined",
    }
    for adapter_id in shape_only:
        assert ADAPTER_METADATA[adapter_id]["parity_status"] == "PARITY_PARTIAL_SHAPE_ONLY"


def test_id_reuse_contamination_not_adapted():
    from recovered_strategies.biglotto.historical_adapters import ADAPTER_METADATA

    adapted_ids = {meta["source_strategy_id"] for meta in ADAPTER_METADATA.values()}
    assert "bet2_fourier_expansion_biglotto" not in adapted_ids
    assert "biglotto_ts3_acb_4bet" not in adapted_ids
    assert "ts3_acb_4bet_biglotto" not in adapted_ids
