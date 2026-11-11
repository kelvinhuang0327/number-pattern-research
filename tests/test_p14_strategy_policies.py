"""
tests/test_p14_strategy_policies.py

P14: Tests for strategy_policies.py

Covers:
- PolicyDecision invariants
- flat_stake_policy: selects bet above threshold, rejects below
- capped_kelly_policy: requires market odds, computes fraction
- confidence_rank_policy: selects top N by rank
- no_bet_policy: always returns CONTROL_NO_BET
- paper_only=False is rejected by all policies (except no_bet)
- Invalid probabilities are rejected
"""
from __future__ import annotations

import pytest

from wbc_backend.simulation.strategy_policies import (
    REASON_CODES,
    PolicyDecision,
    capped_kelly_policy,
    confidence_rank_policy,
    flat_stake_policy,
    no_bet_policy,
)


# ── PolicyDecision invariants ─────────────────────────────────────────────────

class TestPolicyDecision:
    def test_valid_construction(self) -> None:
        d = PolicyDecision(
            should_bet=True,
            stake_fraction=0.02,
            reason="POLICY_SELECTED",
            policy_name="flat_stake",
        )
        assert d.should_bet is True
        assert d.stake_fraction == 0.02

    def test_invalid_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="REASON_CODES"):
            PolicyDecision(
                should_bet=False,
                stake_fraction=0.0,
                reason="NOT_A_REASON",
                policy_name="flat_stake",
            )

    def test_negative_stake_raises(self) -> None:
        with pytest.raises(ValueError, match="stake_fraction"):
            PolicyDecision(
                should_bet=False,
                stake_fraction=-0.01,
                reason="CONTROL_NO_BET",
                policy_name="no_bet",
            )

    def test_should_bet_with_zero_stake_raises(self) -> None:
        with pytest.raises(ValueError, match="stake_fraction > 0.0"):
            PolicyDecision(
                should_bet=True,
                stake_fraction=0.0,
                reason="POLICY_SELECTED",
                policy_name="flat_stake",
            )

    def test_all_reason_codes_are_valid(self) -> None:
        for code in REASON_CODES:
            d = PolicyDecision(
                should_bet=False,
                stake_fraction=0.0,
                reason=code,
                policy_name="test",
            )
            assert d.reason == code


# ── flat_stake_policy ─────────────────────────────────────────────────────────

class TestFlatStakePolicy:
    def test_bets_above_threshold(self) -> None:
        row = {"p_model": 0.65}
        dec = flat_stake_policy(row, threshold=0.55, stake_fraction=0.02)
        assert dec.should_bet is True
        assert dec.stake_fraction == 0.02
        assert dec.reason == "POLICY_SELECTED"
        assert dec.policy_name == "flat_stake"

    def test_no_bet_below_threshold(self) -> None:
        row = {"p_model": 0.50}
        dec = flat_stake_policy(row, threshold=0.55)
        assert dec.should_bet is False
        assert dec.stake_fraction == 0.0
        assert dec.reason == "BELOW_EDGE_THRESHOLD"

    def test_exactly_at_threshold_no_bet(self) -> None:
        row = {"p_model": 0.55}
        dec = flat_stake_policy(row, threshold=0.55)
        # p > threshold (strict), so 0.55 should NOT bet
        assert dec.should_bet is False

    def test_paper_only_false_refuses(self) -> None:
        row = {"p_model": 0.70}
        dec = flat_stake_policy(row, paper_only=False)
        assert dec.should_bet is False
        assert dec.reason == "PAPER_ONLY_REQUIRED"

    def test_invalid_prob_none_refuses(self) -> None:
        row = {"p_model": None}
        dec = flat_stake_policy(row)
        assert dec.should_bet is False
        assert dec.reason == "INVALID_PROBABILITY"

    def test_invalid_prob_nan_refuses(self) -> None:
        row = {"p_model": float("nan")}
        dec = flat_stake_policy(row)
        assert dec.should_bet is False
        assert dec.reason == "INVALID_PROBABILITY"

    def test_invalid_prob_boundary_zero(self) -> None:
        row = {"p_model": 0.0}
        dec = flat_stake_policy(row)
        assert dec.should_bet is False
        assert dec.reason == "INVALID_PROBABILITY"

    def test_invalid_prob_boundary_one(self) -> None:
        row = {"p_model": 1.0}
        dec = flat_stake_policy(row)
        assert dec.should_bet is False
        assert dec.reason == "INVALID_PROBABILITY"

    def test_custom_stake_fraction(self) -> None:
        row = {"p_model": 0.80}
        dec = flat_stake_policy(row, threshold=0.55, stake_fraction=0.05)
        assert dec.stake_fraction == 0.05


# ── capped_kelly_policy ───────────────────────────────────────────────────────

class TestCappedKellyPolicy:
    def _make_row(
        self,
        p_model: float = 0.60,
        decimal_odds: float = 1.95,
        p_market: float = 0.51,
    ) -> dict:
        return {
            "p_model": p_model,
            "decimal_odds": decimal_odds,
            "p_market": p_market,
        }

    def test_bets_with_positive_edge(self) -> None:
        row = self._make_row(p_model=0.60, decimal_odds=2.0, p_market=0.49)
        dec = capped_kelly_policy(row, edge_threshold=0.0, kelly_cap=0.05)
        assert dec.should_bet is True
        assert dec.stake_fraction > 0.0
        assert dec.stake_fraction <= 0.05
        assert dec.reason == "POLICY_SELECTED"

    def test_no_bet_when_edge_zero(self) -> None:
        row = self._make_row(p_model=0.50, decimal_odds=2.0, p_market=0.50)
        dec = capped_kelly_policy(row, edge_threshold=0.0)
        assert dec.should_bet is False
        assert dec.reason == "BELOW_EDGE_THRESHOLD"

    def test_market_odds_absent_blocked(self) -> None:
        row = {"p_model": 0.65, "decimal_odds": None, "p_market": None}
        dec = capped_kelly_policy(row)
        assert dec.should_bet is False
        assert dec.reason == "MARKET_ODDS_ABSENT"
        assert dec.policy_name == "capped_kelly"

    def test_p_market_absent_blocked(self) -> None:
        row = {"p_model": 0.65, "decimal_odds": 1.90, "p_market": None}
        dec = capped_kelly_policy(row)
        assert dec.should_bet is False
        assert dec.reason == "MARKET_ODDS_ABSENT"

    def test_paper_only_false_refuses(self) -> None:
        row = self._make_row()
        dec = capped_kelly_policy(row, paper_only=False)
        assert dec.reason == "PAPER_ONLY_REQUIRED"

    def test_kelly_capped_at_cap(self) -> None:
        # Large edge → raw kelly > cap
        row = self._make_row(p_model=0.90, decimal_odds=2.0, p_market=0.50)
        dec = capped_kelly_policy(row, kelly_cap=0.03)
        assert dec.should_bet is True
        assert dec.stake_fraction <= 0.03

    def test_invalid_prob_rejected(self) -> None:
        row = {"p_model": 1.5, "decimal_odds": 2.0, "p_market": 0.50}
        dec = capped_kelly_policy(row)
        assert dec.reason == "INVALID_PROBABILITY"

    def test_decimal_odds_le_1_blocked(self) -> None:
        row = {"p_model": 0.60, "decimal_odds": 0.9, "p_market": 0.50}
        dec = capped_kelly_policy(row)
        assert dec.reason == "MARKET_ODDS_ABSENT"


# ── confidence_rank_policy ────────────────────────────────────────────────────

class TestConfidenceRankPolicy:
    def test_top_ranked_bets(self) -> None:
        row = {"p_model": 0.75, "confidence_rank": 5, "n_total": 100}
        dec = confidence_rank_policy(row, top_n_pct=0.30)
        assert dec.should_bet is True
        assert dec.reason == "POLICY_SELECTED"
        assert dec.policy_name == "confidence_rank"

    def test_outside_top_pct_no_bet(self) -> None:
        row = {"p_model": 0.75, "confidence_rank": 80, "n_total": 100}
        dec = confidence_rank_policy(row, top_n_pct=0.30)
        assert dec.should_bet is False
        assert dec.reason == "BELOW_EDGE_THRESHOLD"

    def test_fallback_without_rank_metadata(self) -> None:
        row = {"p_model": 0.70}  # no confidence_rank or n_total
        dec = confidence_rank_policy(row)
        assert dec.should_bet is True

    def test_fallback_low_confidence_no_bet(self) -> None:
        row = {"p_model": 0.52}
        dec = confidence_rank_policy(row)
        assert dec.should_bet is False

    def test_paper_only_false_refuses(self) -> None:
        row = {"p_model": 0.70, "confidence_rank": 1, "n_total": 10}
        dec = confidence_rank_policy(row, paper_only=False)
        assert dec.reason == "PAPER_ONLY_REQUIRED"

    def test_invalid_prob_rejected(self) -> None:
        row = {"p_model": None, "confidence_rank": 1, "n_total": 10}
        dec = confidence_rank_policy(row)
        assert dec.reason == "INVALID_PROBABILITY"

    def test_rank_override(self) -> None:
        row = {"p_model": 0.70}
        dec = confidence_rank_policy(row, rank=1, n_total=100, top_n_pct=0.30)
        assert dec.should_bet is True

    def test_boundary_rank_bets(self) -> None:
        # top_n_pct=0.30 of 100 = 30; rank 30 should bet
        row = {"p_model": 0.60, "confidence_rank": 30, "n_total": 100}
        dec = confidence_rank_policy(row, top_n_pct=0.30)
        assert dec.should_bet is True

    def test_boundary_rank_above_no_bet(self) -> None:
        # rank 31 should not bet
        row = {"p_model": 0.60, "confidence_rank": 31, "n_total": 100}
        dec = confidence_rank_policy(row, top_n_pct=0.30)
        assert dec.should_bet is False


# ── no_bet_policy ─────────────────────────────────────────────────────────────

class TestNoBetPolicy:
    def test_always_no_bet(self) -> None:
        for p in [0.0, 0.5, 0.99, None]:
            row = {"p_model": p}
            dec = no_bet_policy(row)
            assert dec.should_bet is False
            assert dec.stake_fraction == 0.0
            assert dec.reason == "CONTROL_NO_BET"
            assert dec.policy_name == "no_bet"

    def test_empty_row(self) -> None:
        dec = no_bet_policy({})
        assert dec.should_bet is False
        assert dec.reason == "CONTROL_NO_BET"
