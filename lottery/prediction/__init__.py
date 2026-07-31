"""Lottery prediction package."""
from lottery.prediction.generate import generate_one_bet, generate_biglotto_bet
from lottery.prediction.batch_generate import generate_bets
from lottery.prediction import daily539

__all__ = ["generate_one_bet", "generate_biglotto_bet", "generate_bets", "daily539"]
