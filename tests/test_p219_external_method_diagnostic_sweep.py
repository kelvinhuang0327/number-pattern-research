"""Tests for P219 ten-method external diagnostic sweep (read-only engine).

Covers: simulated-row exclusion, false-positive control on random input,
power on injected bias, multiplicity-correction monotonicity, empirical-p
bounds, and method-level seed reproducibility. Pure stdlib; no DB write.
"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analysis.p219_external_method_diagnostic_sweep import (  # noqa: E402
    GAMES, correct, empirical_p, load_game, m1_markov, m4_changepoint,
    resolve_db, sim_uniform_number_draws,
)

NUMCFG = {"pool": 39, "k": 5, "kind": "number"}


def _db_or_skip():
    try:
        return resolve_db(None)
    except FileNotFoundError:
        pytest.skip("lottery_v2.db not available")


# --- data integrity ---------------------------------------------------------
def test_big_lotto_excludes_simulation_artifacts():
    """BIG_LOTTO must load only hyphen-free real draws (~3138), not the
    22,238 raw rows that include 19,100 composite-ID simulation artifacts."""
    db = _db_or_skip()
    draws = load_game(db, "BIG_LOTTO")
    assert 3000 <= len(draws) <= 3300, f"expected ~3138 real draws, got {len(draws)}"
    assert len(draws) < 5000, "simulation artifacts leaked into BIG_LOTTO load"


def test_loaded_draws_have_correct_size():
    db = _db_or_skip()
    for game, cfg in GAMES.items():
        draws = load_game(db, game)
        assert draws, f"{game} loaded empty"
        sample = draws[0]
        assert len(sample) == cfg["k"], f"{game} draw size mismatch"


# --- empirical p bounds -----------------------------------------------------
def test_empirical_p_bounds():
    null = [0.0] * 100
    assert empirical_p(1.0, null, "greater") == pytest.approx(1 / 101)  # nothing exceeds
    assert empirical_p(-1.0, null, "greater") == pytest.approx(101 / 101)  # all exceed
    assert 0 < empirical_p(0.5, null, "two-sided") <= 1.0


# --- false-positive control: random input must not fire ---------------------
def test_random_input_no_false_positive_m1():
    rng = random.Random(7)
    draws = sim_uniform_number_draws(rng, 1500, 39, 5)
    res = m1_markov(draws, NUMCFG, random.Random(11), 400)
    assert res["p"] > 0.05, f"random input falsely fired M1 (p={res['p']})"


def test_random_input_no_false_positive_m4():
    rng = random.Random(8)
    draws = sim_uniform_number_draws(rng, 1500, 39, 5)
    res = m4_changepoint(draws, NUMCFG, random.Random(13), 400)
    assert res["p"] > 0.05, f"random input falsely fired M4 (p={res['p']})"


# --- power: injected bias must be detected ----------------------------------
def test_m1_detects_consecutive_dependency():
    """A near-repeating walk (each draw = previous with 1 swap) has high
    consecutive overlap that vanishes under order-shuffle -> M1 should fire."""
    rng = random.Random(3)
    pool = list(range(1, 40))
    cur = set(rng.sample(pool, 5))
    draws = [frozenset(cur)]
    for _ in range(800):
        cur = set(cur)
        out = rng.choice(list(cur))
        cur.discard(out)
        cand = rng.choice([p for p in pool if p not in cur])
        cur.add(cand)
        draws.append(frozenset(cur))
    res = m1_markov(draws, NUMCFG, random.Random(5), 500)
    assert res["p"] < 0.05, f"M1 failed to detect injected dependency (p={res['p']})"


def test_m4_detects_level_shift():
    """Draws built so the draw-sum jumps halfway through -> CUSUM range large,
    destroyed by shuffle -> M4 should fire."""
    rng = random.Random(4)
    low = list(range(1, 20))
    high = list(range(20, 40))
    draws = []
    for t in range(800):
        src = low if t < 400 else high
        draws.append(frozenset(rng.sample(src, 5)))
    res = m4_changepoint(draws, NUMCFG, random.Random(6), 500)
    assert res["p"] < 0.05, f"M4 failed to detect level shift (p={res['p']})"


# --- multiplicity correction ------------------------------------------------
def test_bonferroni_implies_bh():
    tests = [{"p": p} for p in [0.0001, 0.001, 0.02, 0.04, 0.3, 0.5, 0.8]]
    m, bonf = correct(tests)
    assert m == 7
    for t in tests:
        if t.get("bonferroni_sig"):
            assert t.get("bh_sig"), "Bonferroni-significant test must also be BH-significant"


def test_correction_all_null_when_no_signal():
    tests = [{"p": p} for p in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9]]
    correct(tests)
    assert not any(t["bonferroni_sig"] for t in tests)
    assert not any(t["bh_sig"] for t in tests)


# --- reproducibility --------------------------------------------------------
def test_method_seed_reproducible():
    rng = random.Random(99)
    draws = sim_uniform_number_draws(rng, 600, 39, 5)
    r1 = m1_markov(draws, NUMCFG, random.Random(42), 200)
    r2 = m1_markov(draws, NUMCFG, random.Random(42), 200)
    assert r1["obs"] == r2["obs"]
    assert r1["p"] == r2["p"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
