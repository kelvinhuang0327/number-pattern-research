"""Phase T validation."""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

from engine.confidence_scorer import (
    holm_adjust, get_lottery_confidence, get_promotable, _tier_from_score,
)

# Unit tests — Holm
pairs = [('a', 0.01), ('b', 0.04), ('c', 0.03), ('d', 0.005), ('e', 0.20)]
adj = dict(holm_adjust(pairs))
# Sorted: d=0.005, a=0.01, c=0.03, b=0.04, e=0.20
# Holm: 0.005*5=0.025, 0.01*4=0.04, 0.03*3=0.09, 0.04*2=0.08→max(0.09,0.08)=0.09, 0.20*1=0.20
assert abs(adj['d'] - 0.025) < 1e-6, f"d={adj['d']}"
assert abs(adj['a'] - 0.040) < 1e-6, f"a={adj['a']}"
assert abs(adj['c'] - 0.090) < 1e-6, f"c={adj['c']}"
assert abs(adj['b'] - 0.090) < 1e-6, f"b={adj['b']}"   # monotone non-decreasing
assert abs(adj['e'] - 0.200) < 1e-6, f"e={adj['e']}"
print("Holm: OK")

# Tiers
assert _tier_from_score(0.80) == 'HIGH_CONFIDENCE'
assert _tier_from_score(0.60) == 'MEDIUM_CONFIDENCE'
assert _tier_from_score(0.40) == 'LOW_CONFIDENCE'
assert _tier_from_score(0.20) == 'UNRELIABLE'
print("Tiers: OK")

# Real data per lottery
for lt in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
    print(f'\n=== {lt} ===')
    table = get_lottery_confidence(lt)
    rows = sorted(table.values(), key=lambda r: -r['confidence_score'])
    hdr = '{:<38} {:<12} {:>6} {:>6} {:>8} {:<18} {}'
    print(hdr.format('name','val_status','mc_raw','mc_adj','conf','tier','promo'))
    print('-' * 100)
    for r in rows:
        print(hdr.format(
            r['name'][:38],
            r['validated_status'],
            f"{r['mcnemar_p_raw']:.3f}" if r['mcnemar_p_raw'] is not None else '—',
            f"{r['adjusted_mcnemar_p']:.3f}" if r['adjusted_mcnemar_p'] is not None else '—',
            f"{r['confidence_score']:.3f}",
            r['confidence_tier'],
            '★PROMOTE' if r['promotable'] else '',
        ))
    promos = get_promotable(lt)
    if promos:
        print(f'PROMOTABLE: {[p["name"] for p in promos]}')
    else:
        print('PROMOTABLE: (none)')
