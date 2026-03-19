#!/usr/bin/env python3
"""Quick test of all optimized strategies"""
import sys, os
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from lottery_api.database import DatabaseManager
db = DatabaseManager('lottery_api/data/lottery_v2.db')
draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

# Test PP3v2
from tools.predict_power_precision_3bet import generate_power_precision_3bet
bets = generate_power_precision_3bet(draws)
print('PP3v2 bets:')
for i, b in enumerate(bets):
    print(f'  bet{i+1}: {b}')

# Test Markov+Echo 2bet
from tools.quick_predict import power_markov_echo_2bet
bets2 = power_markov_echo_2bet(draws)
print('\nMarkov+Echo 2bet:')
for i, b in enumerate(bets2):
    print(f'  bet{i+1}: {b["numbers"]}')

# Test Special CSN
from models.special_predictor import PowerLottoSpecialPredictor
rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
sp = PowerLottoSpecialPredictor(rules)
top3 = sp.predict_top_n(draws, n=3)
print(f'\nSpecial V3+CSN: {top3}')

# Test predict_power dispatcher
from tools.quick_predict import predict_power
for nb in [2, 3, 5]:
    bets_d, strat = predict_power(draws, {}, nb)
    nums = [b['numbers'] for b in bets_d]
    print(f'\npredict_power({nb}bet): strategy={strat}')
    for i, n in enumerate(nums):
        print(f'  bet{i+1}: {n}')
