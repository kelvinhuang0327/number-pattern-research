#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug DAILY_539 30p simulation"""
import sys, json, sqlite3, traceback
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from tools.rsm_bootstrap import get_daily_539_strategies_inline

strats = get_daily_539_strategies_inline()
func = None
for s in strats:
    if s['name'] == 'acb_markov_midfreq_3bet':
        func = s['predict_func']
        break

print(f"Function found: {func is not None}")

conn = sqlite3.connect('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db')
cur = conn.cursor()
cur.execute("SELECT draw, numbers, special FROM draws WHERE lottery_type='DAILY_539' ORDER BY CAST(draw AS INTEGER) ASC")
rows = cur.fetchall()
conn.close()
print(f"Total DAILY_539 draws: {len(rows)}")

history = []
for draw, numbers_str, special in rows[:-30]:
    history.append({'draw': draw, 'numbers': json.loads(numbers_str), 'special': special})

print(f"History size: {len(history)}")
target_row = rows[-30]
target_draw = {'draw': target_row[0], 'numbers': json.loads(target_row[1]), 'special': target_row[2]}
print(f"Target draw: {target_draw['draw']}, actual: {target_draw['numbers']}")

try:
    bets = func(history)
    print(f"Bets returned: {len(bets)}, type of first: {type(bets[0])}")
    for i, b in enumerate(bets[:3]):
        print(f"  Bet {i+1}: {b}")
    # hits calc
    for i, b in enumerate(bets):
        raw_b = b.get('numbers', b) if isinstance(b, dict) else list(b)
        h = len(set(raw_b) & set(target_draw['numbers']))
        print(f"  Bet {i+1} hits: {h}")
except Exception as e:
    traceback.print_exc()

# Also check raw: does the 539 strategy need a different history format?
print("\nSample history entry:", history[-1])
