#!/usr/bin/env python3
"""Dry-call check for ONLINE adapters using venv python. Read-only."""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean')
from lottery_api.models.replay_strategy_registry import get_adapter

def make_hist(lottery_type, n=104):
    rows = []
    for i in range(n):
        y, mo, d = 2026, (i // 28) + 1, (i % 28) + 1
        if lottery_type in ('POWER_LOTTO', 'BIG_LOTTO'):
            rows.append({'draw_date': f'{y}-{mo:02d}-{d:02d}',
                         'numbers': [1, 2, 3, 4, 5, 6], 'special': 7,
                         'lottery_type': lottery_type})
        else:
            rows.append({'draw_date': f'{y}-{mo:02d}-{d:02d}',
                         'numbers': [1, 2, 3, 4, 5],
                         'lottery_type': lottery_type})
    return rows

TESTS = [
    ('power_precision_3bet',   'POWER_LOTTO'),
    ('power_orthogonal_5bet',  'POWER_LOTTO'),
    ('biglotto_triple_strike', 'BIG_LOTTO'),
    ('biglotto_deviation_2bet','BIG_LOTTO'),
    ('daily539_f4cold',        'DAILY_539'),
    ('daily539_markov_cold',   'DAILY_539'),
]

for sid, lt in TESTS:
    try:
        adapter = get_adapter(sid)
        result = adapter.get_one_bet(make_hist(lt), lt)
        print(f'{sid}|PASS|result_len={len(result)}|type={type(result).__name__}')
    except Exception as e:
        print(f'{sid}|FAIL|{type(e).__name__}|{str(e)[:120]}')
