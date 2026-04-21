"""Phase S gating demonstration with fabricated high-sample data."""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
from engine.rule_weight_manager import _build_map_from_rule_stats, summarize_weight_map

fake_stats = {
    'R01_DEGRADING':            {'rule_score': -0.55, 'total':  8},
    'R02_NEAR_THRESHOLD':       {'rule_score':  0.45, 'total':  7},
    'R03_LEARNING_INEFFECTIVE': {'rule_score': -0.10, 'total': 10},
    'R04_QUALITY_DOMINANT':     {'rule_score':  0.80, 'total':  6},
    'R06_NO_VALIDATED':         {'rule_score':  0.20, 'total':  3},
    'R09_HIGH_DRAWDOWN':        {'rule_score': -0.80, 'total': 12},
}
wmap = _build_map_from_rule_stats(fake_stats)
s = summarize_weight_map(wmap)
print('=== Phase S gating scenario (fabricated) ===')
print('  boosted   :', [r['code'] for r in s['boosted']])
print('  downgraded:', [r['code'] for r in s['downgraded']])
print('  disabled  :', [r['code'] for r in s['disabled']])
print('  low_conf  :', [r['code'] for r in s['low_conf']])
print('  neutral   :', [r['code'] for r in s['neutral']])
print()
for c, e in wmap.items():
    print('  {:<28} w={:<4} status={:<14} reason={}'.format(
        c, e['weight'], e['status'], e['reason']))
