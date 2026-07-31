from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.wbc_data import OddsLine
from strategy.kelly_criterion import BankrollState, size_bet
from strategy.value_detector import ValueBet, detect


class TestValueDetectorGuards(unittest.TestCase):
    def test_large_positive_edge_gets_secondary_validation(self):
        odds = [OddsLine(book="TSL", market="ML", side="TPE", price=2.0)]
        bets = detect(odds, {"ML_TPE": 0.95})
        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].edge_tier, "SECONDARY_VALIDATION_REQUIRED")
        self.assertGreater(bets[0].ev, 0)

    def test_large_negative_edge_is_not_secondary_when_ev_non_positive(self):
        odds = [OddsLine(book="TSL", market="ML", side="AUS", price=2.0)]
        bets = detect(odds, {"ML_AUS": 0.05})
        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].edge_tier, "PASS")
        self.assertLessEqual(bets[0].ev, 0)

    def test_compressed_probability_is_clamped(self):
        odds = [OddsLine(book="TSL", market="ML", side="JPN", price=2.0)]
        bets = detect(odds, {"ML_JPN": 10.0})
        self.assertEqual(len(bets), 1)
        self.assertLessEqual(bets[0].true_prob, 0.99)
        self.assertGreaterEqual(bets[0].true_prob, 0.01)


class TestKellyRiskGuards(unittest.TestCase):
    def test_secondary_validation_forces_observation_stake(self):
        state = BankrollState()
        bet = ValueBet(
            market="ML",
            side="TPE",
            book="TSL",
            decimal_odds=2.0,
            implied_prob=0.5,
            true_prob=0.70,
            ev=0.40,
            line=None,
            edge_tier="SECONDARY_VALIDATION_REQUIRED",
            kelly_frac=0.40,
        )
        sizing = size_bet(bet, state)
        self.assertAlmostEqual(sizing.stake_pct, 0.005, places=6)

    def test_pass_or_non_positive_ev_results_in_zero_stake(self):
        state = BankrollState()
        bet = ValueBet(
            market="ML",
            side="AUS",
            book="TSL",
            decimal_odds=2.0,
            implied_prob=0.5,
            true_prob=0.30,
            ev=-0.40,
            line=None,
            edge_tier="PASS",
            kelly_frac=0.0,
        )
        sizing = size_bet(bet, state)
        self.assertEqual(sizing.stake_pct, 0.0)
        self.assertEqual(sizing.stake_amount, 0.0)

    def test_single_bet_cap_is_applied(self):
        state = BankrollState()
        bet = ValueBet(
            market="ML",
            side="JPN",
            book="TSL",
            decimal_odds=2.0,
            implied_prob=0.5,
            true_prob=0.90,
            ev=0.80,
            line=None,
            edge_tier="STRONG",
            kelly_frac=0.80,
        )
        sizing = size_bet(bet, state)
        self.assertAlmostEqual(sizing.stake_pct, 0.015, places=6)


if __name__ == "__main__":
    unittest.main()
