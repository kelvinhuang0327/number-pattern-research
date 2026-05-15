"""Validation assertions for Phase R fixes."""
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')

from lottery_api.engine.prediction_tracker import _derive_strategy_status, _rank_key_phase_v

# Test 1: VALIDATED -> PRODUCTION
assert _derive_strategy_status({'validated_status': 'VALIDATED'}) == 'PRODUCTION'

# Test 2: WATCH must stay WATCH even if edge_300p is present (legacy field)
result = _derive_strategy_status({'validated_status': 'WATCH', 'edge_300p': 9999})
assert result == 'WATCH', 'Expected WATCH, got: %s' % result

# Test 3: REJECT -> ADVISORY_ONLY
assert _derive_strategy_status({'validated_status': 'REJECT'}) == 'ADVISORY_ONLY'
assert _derive_strategy_status({'validated_status': 'REJECTED'}) == 'ADVISORY_ONLY'

# Test 4: VALIDATED always ranks above WATCH (regardless of composite_score)
v = {'validated_status': 'VALIDATED', 'composite_score': 0.001}
w = {'validated_status': 'WATCH', 'composite_score': 0.999}
assert _rank_key_phase_v(v) > _rank_key_phase_v(w), 'VALIDATED must rank above WATCH'

# Test 5: Higher edge_1500p wins tie when cs is equal
s1 = {'validated_status': 'WATCH', 'composite_score': 0.03, 'edge_1500p': 0.05, 'sharpe': 0.1, 'max_drawdown_rate': 0.2}
s2 = {'validated_status': 'WATCH', 'composite_score': 0.03, 'edge_1500p': 0.04, 'sharpe': 0.2, 'max_drawdown_rate': 0.1}
assert _rank_key_phase_v(s1) > _rank_key_phase_v(s2), 'Higher edge_1500p should rank higher'

print('All assertions passed')
