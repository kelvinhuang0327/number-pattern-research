"""
Strategy Status Correction Script
Fixes 2 misclassified strategies in strategy_states JSON files:
- BIG_LOTTO: deviation_complement_2bet WATCH → REJECT
- POWER_LOTTO: fourier30_markov30_2bet WATCH → REJECT
"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data')

CORRECTIONS = [
    {
        'lt': 'BIG_LOTTO',
        'name': 'deviation_complement_2bet',
        'old_status': 'WATCH',
        'new_status': 'REJECT',
        'reason': 'perm_p=0.0637 >= 0.05, fails permutation test',
        'validation_notes': 'perm_p=0.0637>=0.05 (permutation test failed)',
    },
    {
        'lt': 'POWER_LOTTO',
        'name': 'fourier30_markov30_2bet',
        'old_status': 'WATCH',
        'new_status': 'REJECT',
        'reason': 'perm_p=0.3762 >= 0.05, fails permutation test; all edges negative',
        'validation_notes': 'perm_p=0.3762>=0.05 (permutation test failed); edge_150p=-0.0159<0; edge_500p=-0.0059<0; edge_1500p=-0.0012<0',
    },
]

for correction in CORRECTIONS:
    lt = correction['lt']
    name = correction['name']
    path = os.path.join(BASE, 'strategy_states_%s.json' % lt)

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if name not in data:
        print('WARNING: %s not found in %s' % (name, lt))
        continue

    old = data[name].get('validated_status')
    data[name]['validated_status'] = correction['new_status']
    data[name]['validation_notes'] = correction['validation_notes']
    # Composite score for REJECT strategies should remain but be marked
    # Not changing composite_score — it reflects real performance metrics

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print('Fixed %s / %s: %s → %s' % (lt, name, old, correction['new_status']))
    print('  reason: %s' % correction['reason'])

print('\nDone. Corrections applied.')
