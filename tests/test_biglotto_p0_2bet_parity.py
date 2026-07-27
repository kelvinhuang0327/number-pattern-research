"""Golden-vector donor-parity hardening for Big Lotto P0 2Bet
(BIGLOTTO_P0_2BET_GOLDEN_PARITY_HARDENING_R1).

Proves, against a committed fixed-history fixture, that
``tools.quick_predict.biglotto_p0_2bet`` and
``recovered_strategies.biglotto.historical_adapters.adapt_biglotto_p0_2bet``
produce identical Bet1/Bet2 number sets for well-formed input, and freezes
the two callables' documented validation/output-shape boundaries. No DB
access occurs anywhere in this file.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import random
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "biglotto_p0_2bet_parity.json"
REPO_ROOT = Path(__file__).parent.parent

ORIGINAL_MODULE = "tools.quick_predict"
RECOVERED_MODULE = "recovered_strategies.biglotto.historical_adapters"


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def _load_fixture() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _fresh_reimport(*module_names: str):
    """Drop the given modules (and any submodules) from sys.modules so the
    next import actually re-executes their top-level code, instead of
    silently reusing an already-imported (and therefore already-proven-safe)
    cached module."""
    for name in list(sys.modules):
        if any(name == m or name.startswith(m + ".") for m in module_names):
            del sys.modules[name]
    return [importlib.import_module(m) for m in module_names]


def _normalize_original(result):
    return [d["numbers"] for d in result]


# --- 1. Fixture parses -------------------------------------------------

def test_fixture_parses():
    fx = _load_fixture()
    assert fx["schema_version"] == 1
    assert fx["window"] == 50
    assert fx["echo_boost"] == 1.5
    assert fx["history_order"] == "old_to_new"
    assert len(fx["history"]) >= 60
    assert len(fx["history"]) > fx["window"], "fixture must exceed the default window to exercise truncation"
    for draw in fx["history"]:
        assert len(draw["numbers"]) == 6
        assert len(set(draw["numbers"])) == 6
        assert all(1 <= n <= 49 for n in draw["numbers"])


# --- 2. Authority ref and blob metadata are exact -----------------------

def test_authority_and_blob_metadata_are_exact():
    fx = _load_fixture()
    original_path = REPO_ROOT / fx["original_source_path"]
    recovered_path = REPO_ROOT / fx["recovered_source_path"]

    assert fx["original_source_path"] == "tools/quick_predict.py"
    assert fx["original_source_symbol"] == "biglotto_p0_2bet"
    assert fx["recovered_source_path"] == "recovered_strategies/biglotto/historical_adapters.py"
    assert fx["recovered_source_symbol"] == "adapt_biglotto_p0_2bet"

    assert _git_blob_sha1(original_path) == fx["original_source_blob_sha"] == "f3114603cbd77c6e0e096cfb4543a6894f7b758d"
    assert _git_blob_sha1(recovered_path) == fx["recovered_source_blob_sha"] == "9a8c990d5b640bb0492ba79757e748f1e7d074de"

    assert fx["authority_ref"]["approved_base_head"] == "6b3c0b74bc26a9b7fbb913b45d8cd3457d736ac3"
    assert fx["authority_ref"]["base_pr"] == 711


# --- 3/5. Original: import and call open no SQLite ----------------------

def test_original_imports_and_calls_without_sqlite(monkeypatch):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", blocked_connect)
    original = _fresh_reimport(ORIGINAL_MODULE, "database")[0]

    fx = _load_fixture()
    result = original.biglotto_p0_2bet(
        copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    assert isinstance(result, list) and len(result) == 2


# --- 4/6. Recovered: import and call open no SQLite ----------------------

def test_recovered_imports_and_calls_without_sqlite(monkeypatch):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setattr(sqlite3, "connect", blocked_connect)
    (recovered,) = _fresh_reimport(RECOVERED_MODULE)

    fx = _load_fixture()
    result = recovered.adapt_biglotto_p0_2bet(
        copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    assert isinstance(result, list) and len(result) == 2


# --- 7/8/9. Golden-vector correctness and cross-callable parity ---------

def test_original_matches_golden_bets():
    fx = _load_fixture()
    from tools import quick_predict

    result = quick_predict.biglotto_p0_2bet(
        copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    assert _normalize_original(result) == [fx["expected_bet1"], fx["expected_bet2"]]
    # boundary: original stays dict-wrapped even while matching the golden numbers
    assert all(isinstance(bet, dict) and set(bet.keys()) == {"numbers"} for bet in result)


def test_recovered_matches_golden_bets():
    fx = _load_fixture()
    from recovered_strategies.biglotto import historical_adapters as adapters

    result = adapters.adapt_biglotto_p0_2bet(
        copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    assert result == [fx["expected_bet1"], fx["expected_bet2"]]
    assert all(isinstance(bet, list) for bet in result)


def test_original_and_recovered_agree_after_normalization():
    fx = _load_fixture()
    from tools import quick_predict
    from recovered_strategies.biglotto import historical_adapters as adapters

    original = quick_predict.biglotto_p0_2bet(
        copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    recovered = adapters.adapt_biglotto_p0_2bet(
        copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    assert _normalize_original(original) == recovered
    assert set(fx["expected_bet1"]).isdisjoint(set(fx["expected_bet2"]))


# --- 10. Default 50-row truncation is exercised --------------------------

def test_default_window_truncation_is_exercised():
    fx = _load_fixture()
    from tools import quick_predict

    history = fx["history"]
    assert len(history) > fx["window"]

    truncated = quick_predict.biglotto_p0_2bet(
        copy.deepcopy(history), window=fx["window"], echo_boost=fx["echo_boost"]
    )
    untruncated = quick_predict.biglotto_p0_2bet(
        copy.deepcopy(history), window=len(history), echo_boost=fx["echo_boost"]
    )
    assert truncated != untruncated, "the first (window-excluded) rows must actually change the outcome"
    assert _normalize_original(truncated) == [fx["expected_bet1"], fx["expected_bet2"]]


# --- 11. Lag-2 echo behavior is exercised --------------------------------

def test_lag2_echo_is_exercised():
    fx = _load_fixture()
    from tools import quick_predict

    echo_meta = fx["engineered_echo_case"]
    history = fx["history"]
    target = echo_meta["echo_target_number"]

    no_echo = quick_predict.biglotto_p0_2bet(copy.deepcopy(history), window=fx["window"], echo_boost=0.0)
    with_echo = quick_predict.biglotto_p0_2bet(copy.deepcopy(history), window=fx["window"], echo_boost=fx["echo_boost"])

    assert target not in no_echo[0]["numbers"], "echo target must NOT be in Bet1 without the lag-2 boost"
    assert target in with_echo[0]["numbers"], "echo target must be in Bet1 with the lag-2 boost"
    assert with_echo[0]["numbers"] == fx["expected_bet1"]
    assert no_echo[0]["numbers"] == echo_meta["bet1_without_echo_boost"]
    assert with_echo[0]["numbers"] == echo_meta["bet1_with_echo_boost"]


# --- 12/13. Bet1 ranking/tie behavior and Bet2 disjointness/fallback are
# frozen, via a small hand-verifiable history independent of the big
# fixture (isolates padding/tie-break logic from frequency-domination
# noise in the 62-row fixture). ------------------------------------------

_TIEBREAK_HISTORY = [{"numbers": [1, 2, 3, 4, 5, 6]}]
# With one draw: expected = 1*6/49 ~= 0.1224. Drawn numbers {1..6} score
# ~0.8776 (abs), all other 43 numbers score ~-0.1224 (abs ~0.1224, smaller).
# Neither group crosses the +-1 hot/cold threshold, so both bets come
# entirely from the ascending-abs-deviation mid-fill / ascending-numeric
# fallback paths. Numbers 7..49 have the smaller absolute deviation, so
# they win the mid-fill for Bet1 (ascending tie-break -> 7,8,9,10,11,12);
# Bet2's cold list is also empty, so it falls back to ascending order over
# the remaining unused numbers -> 1,2,3,4,5,6.
_TIEBREAK_EXPECTED_BET1 = [7, 8, 9, 10, 11, 12]
_TIEBREAK_EXPECTED_BET2 = [1, 2, 3, 4, 5, 6]


def test_bet1_tie_break_and_bet2_fallback_are_frozen():
    from tools import quick_predict
    from recovered_strategies.biglotto import historical_adapters as adapters

    original = quick_predict.biglotto_p0_2bet(copy.deepcopy(_TIEBREAK_HISTORY), window=50, echo_boost=1.5)
    recovered = adapters.adapt_biglotto_p0_2bet(copy.deepcopy(_TIEBREAK_HISTORY), window=50, echo_boost=1.5)

    assert _normalize_original(original) == [_TIEBREAK_EXPECTED_BET1, _TIEBREAK_EXPECTED_BET2]
    assert recovered == [_TIEBREAK_EXPECTED_BET1, _TIEBREAK_EXPECTED_BET2]
    assert set(_TIEBREAK_EXPECTED_BET1).isdisjoint(_TIEBREAK_EXPECTED_BET2)


# --- 14. Caller history remains unchanged --------------------------------

def test_caller_history_is_not_mutated():
    fx = _load_fixture()
    from tools import quick_predict
    from recovered_strategies.biglotto import historical_adapters as adapters

    history_for_original = copy.deepcopy(fx["history"])
    before = copy.deepcopy(history_for_original)
    quick_predict.biglotto_p0_2bet(history_for_original, window=fx["window"], echo_boost=fx["echo_boost"])
    assert history_for_original == before

    history_for_recovered = copy.deepcopy(fx["history"])
    before2 = copy.deepcopy(history_for_recovered)
    adapters.adapt_biglotto_p0_2bet(history_for_recovered, window=fx["window"], echo_boost=fx["echo_boost"])
    assert history_for_recovered == before2


# --- 15. Repeated calls are deterministic --------------------------------

def test_repeated_calls_are_deterministic():
    fx = _load_fixture()
    from tools import quick_predict
    from recovered_strategies.biglotto import historical_adapters as adapters

    o1 = quick_predict.biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    o2 = quick_predict.biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    assert o1 == o2

    r1 = adapters.adapt_biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    r2 = adapters.adapt_biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    assert r1 == r2


# --- 16. Python/NumPy global RNG state does not affect results ----------

def test_global_rng_state_does_not_affect_results():
    fx = _load_fixture()
    from tools import quick_predict
    from recovered_strategies.biglotto import historical_adapters as adapters

    random.seed(1)
    np.random.seed(1)
    o1 = quick_predict.biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    r1 = adapters.adapt_biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])

    random.seed(999999)
    for _ in range(37):
        random.random()
    np.random.seed(424242)
    np.random.rand(13)

    o2 = quick_predict.biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    r2 = adapters.adapt_biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])

    assert o1 == o2
    assert r1 == r2


# --- 17/18. Output-shape boundary is frozen ------------------------------

def test_original_output_stays_dict_wrapped():
    fx = _load_fixture()
    from tools import quick_predict

    result = quick_predict.biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    assert isinstance(result, list)
    assert len(result) == 2
    for bet in result:
        assert isinstance(bet, dict)
        assert set(bet.keys()) == {"numbers"}
        assert isinstance(bet["numbers"], list)


def test_recovered_output_stays_bare_list_wrapped():
    fx = _load_fixture()
    from recovered_strategies.biglotto import historical_adapters as adapters

    result = adapters.adapt_biglotto_p0_2bet(copy.deepcopy(fx["history"]), window=fx["window"], echo_boost=fx["echo_boost"])
    assert isinstance(result, list)
    assert len(result) == 2
    for bet in result:
        assert isinstance(bet, list)
        assert all(isinstance(n, int) for n in bet)


# --- 19. Original empty-history behavior is documented and tested -------

def test_original_empty_history_is_permissive():
    """Documented boundary: the original callable performs no input
    validation. An empty history still yields a valid, padded 2-bet
    result rather than raising."""
    from tools import quick_predict

    result = quick_predict.biglotto_p0_2bet([], window=50, echo_boost=1.5)
    assert isinstance(result, list) and len(result) == 2
    for bet in result:
        numbers = bet["numbers"]
        assert len(numbers) == 6
        assert len(set(numbers)) == 6
        assert all(1 <= n <= 49 for n in numbers)


# --- 20. Recovered empty-history ValueError boundary is documented ------

def test_recovered_empty_history_raises_value_error():
    """Documented boundary: the recovered adapter requires at least one
    well-formed draw and fails closed on empty history."""
    from recovered_strategies.biglotto import historical_adapters as adapters

    with pytest.raises(ValueError, match="at least one"):
        adapters.adapt_biglotto_p0_2bet([], window=50, echo_boost=1.5)


# --- 21. Malformed-history validation boundary is documented ------------

def test_malformed_history_validation_boundary():
    """Documented boundary: a draw with the wrong number of main numbers
    is rejected by the recovered adapter (fail closed) but silently
    tolerated by the permissive original callable (fail open)."""
    from tools import quick_predict
    from recovered_strategies.biglotto import historical_adapters as adapters

    malformed_history = [{"numbers": [1, 2, 3, 4, 5]}] * 5  # only 5 numbers, not 6

    with pytest.raises(ValueError, match="6 unique"):
        adapters.adapt_biglotto_p0_2bet(copy.deepcopy(malformed_history), window=50, echo_boost=1.5)

    # original does not raise for the same malformed input
    result = quick_predict.biglotto_p0_2bet(copy.deepcopy(malformed_history), window=50, echo_boost=1.5)
    assert isinstance(result, list) and len(result) == 2


# --- 22. No registry, route or producer import is required --------------

def test_no_registry_route_or_producer_import_required():
    forbidden_prefixes = (
        "lottery_api.models.replay_strategy_registry",
        "lottery_api.routes",
    )
    for name in list(sys.modules):
        assert not any(name == p or name.startswith(p + ".") for p in forbidden_prefixes), (
            f"unexpected pre-existing import of {name} before fresh reimport"
        )

    _fresh_reimport(ORIGINAL_MODULE, "database")
    _fresh_reimport(RECOVERED_MODULE)

    for name in list(sys.modules):
        assert not any(name == p or name.startswith(p + ".") for p in forbidden_prefixes), (
            f"importing the parity callables pulled in {name}, which is out of scope for this task"
        )
