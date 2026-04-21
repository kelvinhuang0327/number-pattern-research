"""Phase N backward compatibility validation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))

from lottery_api.engine.decision_profiles import get_profile
from lottery_api.engine.strategy_coordinator import StrategyCoordinator
from database import DatabaseManager

# 1. Verify balanced = identity
p = get_profile('balanced')
assert p.learning_amp == 1.0
assert p.quality_amp == 1.0
assert p.var_n_scale == 1.0
assert p.concentration_bias == 1.0
print('✅ Balanced profile = identity multipliers')

# 2. Verify coordinator balanced = default for BIG_LOTTO
db = DatabaseManager(db_path='lottery_api/data/lottery_v2.db')
history = sorted(db.get_all_draws(lottery_type='BIG_LOTTO'),
                 key=lambda x: (x['date'], x['draw']))

coord_b = StrategyCoordinator('BIG_LOTTO', profile='balanced')
coord_d = StrategyCoordinator('BIG_LOTTO', profile=None)  # maps to balanced

scores_b = coord_b.aggregate_scores(history)
scores_d = coord_d.aggregate_scores(history)

diffs = {n: abs(scores_b[n] - scores_d[n]) for n in scores_b}
max_diff = max(diffs.values())
print(f'Max score diff (balanced vs default): {max_diff:.2e}')
assert max_diff < 1e-10, f'Regression! max_diff={max_diff}'
print('✅ No regression: balanced = default')

# 3. Verify profiles produce different outputs
coord_c = StrategyCoordinator('BIG_LOTTO', profile='conservative')
coord_a = StrategyCoordinator('BIG_LOTTO', profile='aggressive')
scores_c = coord_c.aggregate_scores(history)
scores_a = coord_a.aggregate_scores(history)

# Should differ from balanced
diff_c = max(abs(scores_c[n] - scores_b[n]) for n in scores_b)
diff_a = max(abs(scores_a[n] - scores_b[n]) for n in scores_b)
print(f'Conservative vs balanced max diff: {diff_c:.6f}')
print(f'Aggressive vs balanced max diff: {diff_a:.6f}')
assert diff_c > 1e-6, 'Conservative should differ from balanced'
assert diff_a > 1e-6, 'Aggressive should differ from balanced'
print('✅ Different profiles produce different outputs')
print()
print('Phase N backward compatibility: ALL PASSED')
