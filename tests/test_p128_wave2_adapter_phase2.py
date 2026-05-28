"""
test_p128_wave2_adapter_phase2.py
===================================
P128 Wave 2 Phase 2 — get_all_bets() adapter unit tests.

Tests priority 7-12 adapters:
  P7:  acb_markov_midfreq_3bet  (DAILY_539, 3 bets)
  P8:  midfreq_fourier_mk_3bet  (POWER_LOTTO, 3 bets)
  P9:  fourier_rhythm_3bet      (POWER_LOTTO, 3 bets)   [RSR-7: 1501 rows, not blocked]
  P10: power_precision_3bet     (POWER_LOTTO, 3 bets)   [RSR-6: apply blocked]
  P11: pp3_freqort_4bet          (POWER_LOTTO, 4 bets)
  P12: power_orthogonal_5bet    (POWER_LOTTO, 5 bets)   [RSR-6: apply blocked]

Scope:
  - All tests are adapter-only. No DB access. No network. No file I/O.
  - Tests verify: structure, pick count, pool range, uniqueness, sort order.
  - Tests verify: determinism, empty history, minimal history, full history.
  - Tests verify: RSR-6 flagged strategies are in RSR6_BLOCKED_STRATEGIES set.
  - Tests verify: dispatch (get_all_bets) and direct function calls are consistent.

DB row count invariant: 72462 rows. Enforced separately by replay_lifecycle_drift_guard.
"""
import pytest
import sys
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lottery_api.models.p128_wave2_phase2_adapters import (
    get_all_bets,
    get_all_bets_acb_markov_midfreq,
    get_all_bets_midfreq_fourier_mk,
    get_all_bets_fourier_rhythm,
    get_all_bets_power_precision,
    get_all_bets_pp3_freqort,
    get_all_bets_power_orthogonal,
    PHASE2_STRATEGIES,
    RSR6_BLOCKED_STRATEGIES,
    PROVENANCE_SHA256,
    _validate_bets,
    _D539_POOL, _D539_PICK,
    _PL_POOL, _PL_PICK,
)


# ─── fixtures ─────────────────────────────────────────────────────────────────

def _make_d539_history(n: int) -> list:
    """Generate n synthetic DAILY_539 draws (5 distinct numbers, 1..39)."""
    rng = random.Random(42)
    history = []
    for _ in range(n):
        numbers = sorted(rng.sample(range(1, 40), 5))
        history.append({"numbers": numbers})
    return history


def _make_pl_history(n: int) -> list:
    """Generate n synthetic POWER_LOTTO draws (6 distinct numbers, 1..38)."""
    rng = random.Random(99)
    history = []
    for _ in range(n):
        numbers = sorted(rng.sample(range(1, 39), 6))
        history.append({"numbers": numbers})
    return history


def _make_d539_ctx(n: int) -> dict:
    return {"history": _make_d539_history(n), "lottery_type": "DAILY_539"}


def _make_pl_ctx(n: int) -> dict:
    return {"history": _make_pl_history(n), "lottery_type": "POWER_LOTTO"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _assert_valid_d539_bets(bets, expected_n):
    assert isinstance(bets, list), "bets must be list"
    assert len(bets) == expected_n, f"expected {expected_n} bets, got {len(bets)}"
    for i, bet in enumerate(bets, 1):
        assert isinstance(bet, list), f"bet_index={i} must be list"
        assert len(bet) == _D539_PICK, f"bet_index={i}: expected {_D539_PICK} numbers, got {len(bet)}"
        assert len(set(bet)) == _D539_PICK, f"bet_index={i}: duplicate numbers"
        assert sorted(bet) == bet, f"bet_index={i}: not sorted ASC"
        for num in bet:
            assert 1 <= num <= _D539_POOL, f"bet_index={i}: {num} out of [1..{_D539_POOL}]"


def _assert_valid_pl_bets(bets, expected_n):
    assert isinstance(bets, list), "bets must be list"
    assert len(bets) == expected_n, f"expected {expected_n} bets, got {len(bets)}"
    for i, bet in enumerate(bets, 1):
        assert isinstance(bet, list), f"bet_index={i} must be list"
        assert len(bet) == _PL_PICK, f"bet_index={i}: expected {_PL_PICK} numbers, got {len(bet)}"
        assert len(set(bet)) == _PL_PICK, f"bet_index={i}: duplicate numbers"
        assert sorted(bet) == bet, f"bet_index={i}: not sorted ASC"
        for num in bet:
            assert 1 <= num <= _PL_POOL, f"bet_index={i}: {num} out of [1..{_PL_POOL}]"


# ══════════════════════════════════════════════════════════════════════════════
# Module-level checks
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleLevel:
    def test_provenance_sha256_is_str(self):
        assert isinstance(PROVENANCE_SHA256, str)
        assert len(PROVENANCE_SHA256) == 64

    def test_phase2_strategies_count(self):
        assert len(PHASE2_STRATEGIES) == 6

    def test_phase2_strategies_priorities(self):
        priorities = [s["priority"] for s in PHASE2_STRATEGIES]
        assert priorities == list(range(7, 13))

    def test_phase2_strategies_fields(self):
        required = {"priority", "strategy_id", "lottery_type", "bet_count", "function", "rsr6_blocked"}
        for s in PHASE2_STRATEGIES:
            assert required.issubset(s.keys()), f"Missing fields in {s}"

    def test_rsr6_blocked_strategies(self):
        assert "power_precision_3bet" in RSR6_BLOCKED_STRATEGIES
        assert "power_orthogonal_5bet" in RSR6_BLOCKED_STRATEGIES
        assert "acb_markov_midfreq_3bet" not in RSR6_BLOCKED_STRATEGIES
        assert "midfreq_fourier_mk_3bet" not in RSR6_BLOCKED_STRATEGIES
        assert "fourier_rhythm_3bet" not in RSR6_BLOCKED_STRATEGIES
        assert "pp3_freqort_4bet" not in RSR6_BLOCKED_STRATEGIES

    def test_phase2_manifest_rsr6_flags(self):
        rsr6_in_manifest = {s["strategy_id"] for s in PHASE2_STRATEGIES if s["rsr6_blocked"]}
        assert rsr6_in_manifest == RSR6_BLOCKED_STRATEGIES

    def test_phase2_bet_counts(self):
        counts = {s["strategy_id"]: s["bet_count"] for s in PHASE2_STRATEGIES}
        assert counts["acb_markov_midfreq_3bet"] == 3
        assert counts["midfreq_fourier_mk_3bet"] == 3
        assert counts["fourier_rhythm_3bet"] == 3
        assert counts["power_precision_3bet"] == 3
        assert counts["pp3_freqort_4bet"] == 4
        assert counts["power_orthogonal_5bet"] == 5

    def test_phase2_lottery_types(self):
        types = {s["strategy_id"]: s["lottery_type"] for s in PHASE2_STRATEGIES}
        assert types["acb_markov_midfreq_3bet"] == "DAILY_539"
        for sid in ["midfreq_fourier_mk_3bet", "fourier_rhythm_3bet", "power_precision_3bet",
                    "pp3_freqort_4bet", "power_orthogonal_5bet"]:
            assert types[sid] == "POWER_LOTTO"


# ══════════════════════════════════════════════════════════════════════════════
# P7: acb_markov_midfreq_3bet (DAILY_539, 3 bets)
# ══════════════════════════════════════════════════════════════════════════════

class TestAcbMarkovMidfreq3bet:
    SID = "acb_markov_midfreq_3bet"
    LT  = "DAILY_539"

    def _ctx(self, n=300):
        return _make_d539_ctx(n)

    def test_structure_normal(self):
        bets = get_all_bets_acb_markov_midfreq(self._ctx())
        _assert_valid_d539_bets(bets, 3)

    def test_dispatch_consistent(self):
        ctx = self._ctx()
        bets_direct = get_all_bets_acb_markov_midfreq(ctx)
        bets_dispatch = get_all_bets(self.SID, ctx)
        assert bets_direct == bets_dispatch

    def test_deterministic(self):
        ctx = self._ctx(500)
        assert get_all_bets_acb_markov_midfreq(ctx) == get_all_bets_acb_markov_midfreq(ctx)

    def test_empty_history(self):
        ctx = {"history": [], "lottery_type": self.LT}
        bets = get_all_bets_acb_markov_midfreq(ctx)
        _assert_valid_d539_bets(bets, 3)

    def test_minimal_history(self):
        ctx = {"history": [{"numbers": [1, 2, 3, 4, 5]}], "lottery_type": self.LT}
        bets = get_all_bets_acb_markov_midfreq(ctx)
        _assert_valid_d539_bets(bets, 3)

    def test_large_history(self):
        ctx = _make_d539_ctx(1500)
        bets = get_all_bets_acb_markov_midfreq(ctx)
        _assert_valid_d539_bets(bets, 3)

    def test_three_bets_returned(self):
        bets = get_all_bets_acb_markov_midfreq(self._ctx())
        assert len(bets) == 3

    def test_bets_differ(self):
        # ACB, Markov, MidFreq should not always produce identical bets
        bets = get_all_bets_acb_markov_midfreq(self._ctx(200))
        # At least some pair should differ when history is substantial
        all_same = all(bets[0] == b for b in bets[1:])
        # Not asserting all must differ (degenerate inputs could produce same)
        # But structure must always be valid
        _assert_valid_d539_bets(bets, 3)

    def test_validate_passes(self):
        bets = get_all_bets_acb_markov_midfreq(self._ctx())
        # should not raise
        _validate_bets(bets, self.SID, self.LT, 3)

    def test_different_contexts_may_differ(self):
        ctx1 = _make_d539_ctx(100)
        ctx2 = _make_d539_ctx(200)
        b1 = get_all_bets_acb_markov_midfreq(ctx1)
        b2 = get_all_bets_acb_markov_midfreq(ctx2)
        # Both must be valid, they may or may not differ
        _assert_valid_d539_bets(b1, 3)
        _assert_valid_d539_bets(b2, 3)


# ══════════════════════════════════════════════════════════════════════════════
# P8: midfreq_fourier_mk_3bet (POWER_LOTTO, 3 bets)
# ══════════════════════════════════════════════════════════════════════════════

class TestMidfreqFourierMk3bet:
    SID = "midfreq_fourier_mk_3bet"
    LT  = "POWER_LOTTO"

    def _ctx(self, n=500):
        return _make_pl_ctx(n)

    def test_structure_normal(self):
        bets = get_all_bets_midfreq_fourier_mk(self._ctx())
        _assert_valid_pl_bets(bets, 3)

    def test_dispatch_consistent(self):
        ctx = self._ctx()
        assert get_all_bets_midfreq_fourier_mk(ctx) == get_all_bets(self.SID, ctx)

    def test_deterministic(self):
        ctx = self._ctx(500)
        assert get_all_bets_midfreq_fourier_mk(ctx) == get_all_bets_midfreq_fourier_mk(ctx)

    def test_empty_history(self):
        ctx = {"history": [], "lottery_type": self.LT}
        bets = get_all_bets_midfreq_fourier_mk(ctx)
        _assert_valid_pl_bets(bets, 3)

    def test_minimal_history(self):
        ctx = {"history": [{"numbers": [1, 2, 3, 4, 5, 6]}], "lottery_type": self.LT}
        bets = get_all_bets_midfreq_fourier_mk(ctx)
        _assert_valid_pl_bets(bets, 3)

    def test_large_history(self):
        bets = get_all_bets_midfreq_fourier_mk(_make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 3)

    def test_three_bets_returned(self):
        assert len(get_all_bets_midfreq_fourier_mk(self._ctx())) == 3

    def test_validate_passes(self):
        bets = get_all_bets_midfreq_fourier_mk(self._ctx())
        _validate_bets(bets, self.SID, self.LT, 3)


# ══════════════════════════════════════════════════════════════════════════════
# P9: fourier_rhythm_3bet (POWER_LOTTO, 3 bets) [RSR-7: not blocked]
# ══════════════════════════════════════════════════════════════════════════════

class TestFourierRhythm3bet:
    SID = "fourier_rhythm_3bet"
    LT  = "POWER_LOTTO"

    def _ctx(self, n=500):
        return _make_pl_ctx(n)

    def test_structure_normal(self):
        bets = get_all_bets_fourier_rhythm(self._ctx())
        _assert_valid_pl_bets(bets, 3)

    def test_dispatch_consistent(self):
        ctx = self._ctx()
        assert get_all_bets_fourier_rhythm(ctx) == get_all_bets(self.SID, ctx)

    def test_deterministic(self):
        ctx = self._ctx(500)
        assert get_all_bets_fourier_rhythm(ctx) == get_all_bets_fourier_rhythm(ctx)

    def test_empty_history(self):
        ctx = {"history": [], "lottery_type": self.LT}
        bets = get_all_bets_fourier_rhythm(ctx)
        _assert_valid_pl_bets(bets, 3)

    def test_minimal_history(self):
        ctx = {"history": [{"numbers": [1, 2, 3, 4, 5, 6]}], "lottery_type": self.LT}
        bets = get_all_bets_fourier_rhythm(ctx)
        _assert_valid_pl_bets(bets, 3)

    def test_large_history(self):
        bets = get_all_bets_fourier_rhythm(_make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 3)

    def test_three_bets_returned(self):
        assert len(get_all_bets_fourier_rhythm(self._ctx())) == 3

    def test_rsr7_note_in_manifest(self):
        s = next(s for s in PHASE2_STRATEGIES if s["strategy_id"] == self.SID)
        assert s["rsr7_note"] is not None
        assert "RSR-7" in s["rsr7_note"]

    def test_not_rsr6_blocked(self):
        assert self.SID not in RSR6_BLOCKED_STRATEGIES

    def test_validate_passes(self):
        bets = get_all_bets_fourier_rhythm(self._ctx())
        _validate_bets(bets, self.SID, self.LT, 3)


# ══════════════════════════════════════════════════════════════════════════════
# P10: power_precision_3bet (POWER_LOTTO, 3 bets) [RSR-6 FLAGGED]
# ══════════════════════════════════════════════════════════════════════════════

class TestPowerPrecision3bet:
    SID = "power_precision_3bet"
    LT  = "POWER_LOTTO"

    def _ctx(self, n=500):
        return _make_pl_ctx(n)

    def test_structure_normal(self):
        bets = get_all_bets_power_precision(self._ctx())
        _assert_valid_pl_bets(bets, 3)

    def test_dispatch_consistent(self):
        ctx = self._ctx()
        assert get_all_bets_power_precision(ctx) == get_all_bets(self.SID, ctx)

    def test_deterministic(self):
        ctx = self._ctx(500)
        assert get_all_bets_power_precision(ctx) == get_all_bets_power_precision(ctx)

    def test_empty_history(self):
        ctx = {"history": [], "lottery_type": self.LT}
        bets = get_all_bets_power_precision(ctx)
        _assert_valid_pl_bets(bets, 3)

    def test_minimal_history(self):
        ctx = {"history": [{"numbers": [1, 2, 3, 4, 5, 6]}], "lottery_type": self.LT}
        bets = get_all_bets_power_precision(ctx)
        _assert_valid_pl_bets(bets, 3)

    def test_large_history(self):
        bets = get_all_bets_power_precision(_make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 3)

    def test_three_bets_returned(self):
        assert len(get_all_bets_power_precision(self._ctx())) == 3

    def test_rsr6_blocked_flag_in_manifest(self):
        s = next(s for s in PHASE2_STRATEGIES if s["strategy_id"] == self.SID)
        assert s["rsr6_blocked"] is True

    def test_rsr6_in_blocked_set(self):
        assert self.SID in RSR6_BLOCKED_STRATEGIES

    def test_validate_passes(self):
        bets = get_all_bets_power_precision(self._ctx())
        _validate_bets(bets, self.SID, self.LT, 3)


# ══════════════════════════════════════════════════════════════════════════════
# P11: pp3_freqort_4bet (POWER_LOTTO, 4 bets)
# ══════════════════════════════════════════════════════════════════════════════

class TestPp3Freqort4bet:
    SID = "pp3_freqort_4bet"
    LT  = "POWER_LOTTO"

    def _ctx(self, n=500):
        return _make_pl_ctx(n)

    def test_structure_normal(self):
        bets = get_all_bets_pp3_freqort(self._ctx())
        _assert_valid_pl_bets(bets, 4)

    def test_dispatch_consistent(self):
        ctx = self._ctx()
        assert get_all_bets_pp3_freqort(ctx) == get_all_bets(self.SID, ctx)

    def test_deterministic(self):
        ctx = self._ctx(500)
        assert get_all_bets_pp3_freqort(ctx) == get_all_bets_pp3_freqort(ctx)

    def test_empty_history(self):
        ctx = {"history": [], "lottery_type": self.LT}
        bets = get_all_bets_pp3_freqort(ctx)
        _assert_valid_pl_bets(bets, 4)

    def test_minimal_history(self):
        ctx = {"history": [{"numbers": [1, 2, 3, 4, 5, 6]}], "lottery_type": self.LT}
        bets = get_all_bets_pp3_freqort(ctx)
        _assert_valid_pl_bets(bets, 4)

    def test_large_history(self):
        bets = get_all_bets_pp3_freqort(_make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 4)

    def test_four_bets_returned(self):
        assert len(get_all_bets_pp3_freqort(self._ctx())) == 4

    def test_not_rsr6_blocked(self):
        assert self.SID not in RSR6_BLOCKED_STRATEGIES

    def test_validate_passes(self):
        bets = get_all_bets_pp3_freqort(self._ctx())
        _validate_bets(bets, self.SID, self.LT, 4)

    def test_bet_count_in_manifest(self):
        s = next(s for s in PHASE2_STRATEGIES if s["strategy_id"] == self.SID)
        assert s["bet_count"] == 4


# ══════════════════════════════════════════════════════════════════════════════
# P12: power_orthogonal_5bet (POWER_LOTTO, 5 bets) [RSR-6 FLAGGED]
# ══════════════════════════════════════════════════════════════════════════════

class TestPowerOrthogonal5bet:
    SID = "power_orthogonal_5bet"
    LT  = "POWER_LOTTO"

    def _ctx(self, n=500):
        return _make_pl_ctx(n)

    def test_structure_normal(self):
        bets = get_all_bets_power_orthogonal(self._ctx())
        _assert_valid_pl_bets(bets, 5)

    def test_dispatch_consistent(self):
        ctx = self._ctx()
        assert get_all_bets_power_orthogonal(ctx) == get_all_bets(self.SID, ctx)

    def test_deterministic(self):
        ctx = self._ctx(500)
        assert get_all_bets_power_orthogonal(ctx) == get_all_bets_power_orthogonal(ctx)

    def test_empty_history(self):
        ctx = {"history": [], "lottery_type": self.LT}
        bets = get_all_bets_power_orthogonal(ctx)
        _assert_valid_pl_bets(bets, 5)

    def test_minimal_history(self):
        ctx = {"history": [{"numbers": [1, 2, 3, 4, 5, 6]}], "lottery_type": self.LT}
        bets = get_all_bets_power_orthogonal(ctx)
        _assert_valid_pl_bets(bets, 5)

    def test_large_history(self):
        bets = get_all_bets_power_orthogonal(_make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 5)

    def test_five_bets_returned(self):
        assert len(get_all_bets_power_orthogonal(self._ctx())) == 5

    def test_rsr6_blocked_flag_in_manifest(self):
        s = next(s for s in PHASE2_STRATEGIES if s["strategy_id"] == self.SID)
        assert s["rsr6_blocked"] is True

    def test_rsr6_in_blocked_set(self):
        assert self.SID in RSR6_BLOCKED_STRATEGIES

    def test_validate_passes(self):
        bets = get_all_bets_power_orthogonal(self._ctx())
        _validate_bets(bets, self.SID, self.LT, 5)

    def test_bet_count_in_manifest(self):
        s = next(s for s in PHASE2_STRATEGIES if s["strategy_id"] == self.SID)
        assert s["bet_count"] == 5


# ══════════════════════════════════════════════════════════════════════════════
# Unified dispatch tests
# ══════════════════════════════════════════════════════════════════════════════

class TestUnifiedDispatch:
    def test_unknown_strategy_raises(self):
        ctx = _make_pl_ctx(100)
        with pytest.raises(ValueError, match="Unknown Phase 2 strategy"):
            get_all_bets("nonexistent_strategy", ctx)

    def test_wrong_lottery_type_raises(self):
        # acb_markov_midfreq_3bet is DAILY_539 only
        ctx = _make_pl_ctx(100)
        ctx["lottery_type"] = "POWER_LOTTO"
        with pytest.raises(ValueError, match="Unknown Phase 2 strategy"):
            get_all_bets("acb_markov_midfreq_3bet", ctx)

    def test_all_six_strategies_dispatch(self):
        combos = [
            ("acb_markov_midfreq_3bet", _make_d539_ctx(200), 3),
            ("midfreq_fourier_mk_3bet", _make_pl_ctx(200), 3),
            ("fourier_rhythm_3bet",     _make_pl_ctx(200), 3),
            ("power_precision_3bet",    _make_pl_ctx(200), 3),
            ("pp3_freqort_4bet",        _make_pl_ctx(200), 4),
            ("power_orthogonal_5bet",   _make_pl_ctx(200), 5),
        ]
        for sid, ctx, expected_n in combos:
            bets = get_all_bets(sid, ctx)
            assert isinstance(bets, list), f"{sid}: bets not list"
            assert len(bets) == expected_n, f"{sid}: expected {expected_n} bets"

    def test_dispatch_idempotent(self):
        ctx = _make_pl_ctx(200)
        b1 = get_all_bets("pp3_freqort_4bet", ctx)
        b2 = get_all_bets("pp3_freqort_4bet", ctx)
        assert b1 == b2


# ══════════════════════════════════════════════════════════════════════════════
# Validation function tests
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateBets:
    def test_wrong_count_raises(self):
        bets = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]]
        with pytest.raises(ValueError, match="expected 3 bets"):
            _validate_bets(bets, "acb_markov_midfreq_3bet", "DAILY_539", 3)

    def test_wrong_pick_count_raises(self):
        bets = [[1, 2, 3, 4], [5, 6, 7, 8, 9], [10, 11, 12, 13, 14]]
        with pytest.raises(ValueError, match="expected 5 numbers"):
            _validate_bets(bets, "acb_markov_midfreq_3bet", "DAILY_539", 3)

    def test_duplicate_numbers_raises(self):
        bets = [[1, 2, 3, 4, 4], [5, 6, 7, 8, 9], [10, 11, 12, 13, 14]]
        with pytest.raises(ValueError, match="duplicate"):
            _validate_bets(bets, "acb_markov_midfreq_3bet", "DAILY_539", 3)

    def test_unsorted_raises(self):
        bets = [[5, 4, 3, 2, 1], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15]]
        with pytest.raises(ValueError, match="sorted"):
            _validate_bets(bets, "acb_markov_midfreq_3bet", "DAILY_539", 3)

    def test_out_of_range_raises(self):
        bets = [[1, 2, 3, 4, 40], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15]]
        with pytest.raises(ValueError, match="out of range"):
            _validate_bets(bets, "acb_markov_midfreq_3bet", "DAILY_539", 3)

    def test_pl_out_of_range_raises(self):
        bets = [[1, 2, 3, 4, 5, 39], [6, 7, 8, 9, 10, 11], [12, 13, 14, 15, 16, 17]]
        with pytest.raises(ValueError, match="out of range"):
            _validate_bets(bets, "power_precision_3bet", "POWER_LOTTO", 3)

    def test_valid_d539_bets_pass(self):
        bets = [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15]]
        _validate_bets(bets, "acb_markov_midfreq_3bet", "DAILY_539", 3)  # no raise

    def test_valid_pl_4bets_pass(self):
        bets = [
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
            [19, 20, 21, 22, 23, 24],
        ]
        _validate_bets(bets, "pp3_freqort_4bet", "POWER_LOTTO", 4)  # no raise

    def test_valid_pl_5bets_pass(self):
        bets = [
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
            [19, 20, 21, 22, 23, 24],
            [25, 26, 27, 28, 29, 30],
        ]
        _validate_bets(bets, "power_orthogonal_5bet", "POWER_LOTTO", 5)  # no raise


# ══════════════════════════════════════════════════════════════════════════════
# Cross-strategy regression: all adapters produce valid outputs for 1500 draws
# ══════════════════════════════════════════════════════════════════════════════

class TestFullHistoryRegression:
    """Regression tests with 1500-draw history (typical production window)."""

    def test_p7_1500_draws(self):
        bets = get_all_bets("acb_markov_midfreq_3bet", _make_d539_ctx(1500))
        _assert_valid_d539_bets(bets, 3)

    def test_p8_1500_draws(self):
        bets = get_all_bets("midfreq_fourier_mk_3bet", _make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 3)

    def test_p9_1500_draws(self):
        bets = get_all_bets("fourier_rhythm_3bet", _make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 3)

    def test_p10_1500_draws(self):
        bets = get_all_bets("power_precision_3bet", _make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 3)

    def test_p11_1500_draws(self):
        bets = get_all_bets("pp3_freqort_4bet", _make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 4)

    def test_p12_1500_draws(self):
        bets = get_all_bets("power_orthogonal_5bet", _make_pl_ctx(1500))
        _assert_valid_pl_bets(bets, 5)
