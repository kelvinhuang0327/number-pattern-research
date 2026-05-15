"""
Stage1-5 Gate Validation for DAILY_539 strategies
"""
import json
import numpy as np
from math import comb
from scipy import stats

with open('data/rolling_monitor_DAILY_539.json', 'r') as f:
    data = json.load(f)
records = data['records']

# Baseline probabilities
total_comb = comb(39, 5)
p3plus_1bet = sum(comb(5,k)*comb(34,5-k)/total_comb for k in range(3,6))

print('=' * 80)
print('DAILY_539 - Stage 1~5 Gate Validation')
print('=' * 80)

for strat, recs in records.items():
    total = len(recs)
    nbets = recs[0].get('num_bets', 1)
    baseline_m3 = 1 - (1 - p3plus_1bet) ** nbets
    
    m3_hits = [1 if r.get('is_m3plus') else 0 for r in recs]
    observed_m3 = sum(m3_hits) / total
    edge = observed_m3 - baseline_m3
    
    print(f'\n--- {strat} (x{nbets} bets, {total} draws) ---')
    
    # Stage 1: Edge > baseline
    stage1 = edge > 0
    print(f'Stage 1 (Edge > 0): edge={edge*100:+.3f}%  => {"PASS" if stage1 else "FAIL"}')
    
    # Stage 2: Permutation test
    n_perm = 10000
    np.random.seed(42)
    observed_m3_count = sum(m3_hits)
    perm_counts = np.zeros(n_perm)
    for i in range(n_perm):
        perm_counts[i] = np.sum(np.random.random(total) < baseline_m3)
    p_value_perm = np.mean(perm_counts >= observed_m3_count)
    stage2 = p_value_perm < 0.05
    print(f'Stage 2 (Permutation p<0.05): observed={observed_m3_count}, mean_perm={np.mean(perm_counts):.1f}, p={p_value_perm:.4f} => {"PASS" if stage2 else "FAIL"}')
    
    # Stage 3: McNemar-like test (binary: did strategy beat random?)
    # Compare strategy vs random baseline using binomial test
    binom_result = stats.binomtest(observed_m3_count, total, baseline_m3, alternative='greater')
    stage3 = binom_result.pvalue < 0.05
    print(f'Stage 3 (Binomial p<0.05): p={binom_result.pvalue:.4f} => {"PASS" if stage3 else "FAIL"}')
    
    # Stage 4: Sharpe Ratio > 0
    # Define returns: +1 if m3+, else -cost_per_bet normalized
    cost_per_draw = nbets * 50  # TWD 50 per bet
    returns = []
    for r in recs:
        best = r.get('best_match', 0)
        # Prize: m3=300, m4=10000, m5=8000000
        prize = 0
        if best >= 5: prize = 8000000
        elif best >= 4: prize = 10000
        elif best >= 3: prize = 300
        net_return = (prize - cost_per_draw) / cost_per_draw
        returns.append(net_return)
    
    returns = np.array(returns)
    mean_ret = np.mean(returns)
    std_ret = np.std(returns)
    sharpe = mean_ret / std_ret if std_ret > 0 else 0
    stage4 = sharpe > 0
    print(f'Stage 4 (Sharpe > 0): mean_ret={mean_ret:.4f}, std={std_ret:.4f}, Sharpe={sharpe:.4f} => {"PASS" if stage4 else "FAIL"}')
    
    # Stage 5: OOS stability (check last 30 vs full)
    # Split: first 70% training, last 30% OOS
    split_idx = int(total * 0.7)
    oos_recs = recs[split_idx:]
    oos_m3 = sum(1 for r in oos_recs if r.get('is_m3plus'))
    oos_rate = oos_m3 / len(oos_recs)
    oos_edge = oos_rate - baseline_m3
    stage5 = oos_edge > 0
    print(f'Stage 5 (OOS edge>0): OOS_m3={oos_rate*100:.2f}% vs baseline={baseline_m3*100:.2f}%, edge={oos_edge*100:+.2f}% => {"PASS" if stage5 else "FAIL"}')
    
    # Multi-window analysis
    print(f'\n  Multi-window analysis:')
    for window in [30, 100, 300]:
        if total >= window:
            w_recs = recs[-window:]
            w_m3 = sum(1 for r in w_recs if r.get('is_m3plus'))
            w_rate = w_m3 / window
            w_edge = w_rate - baseline_m3
            # Sharpe for window
            w_returns = []
            for r in w_recs:
                best = r.get('best_match', 0)
                prize = 0
                if best >= 5: prize = 8000000
                elif best >= 4: prize = 10000
                elif best >= 3: prize = 300
                net_return = (prize - cost_per_draw) / cost_per_draw
                w_returns.append(net_return)
            w_returns = np.array(w_returns)
            w_sharpe = np.mean(w_returns) / np.std(w_returns) if np.std(w_returns) > 0 else 0
            print(f'  Window-{window}: m3+={w_rate*100:.2f}%, edge={w_edge*100:+.2f}%, Sharpe={w_sharpe:.4f}')

    # Summary
    gates = [stage1, stage2, stage3, stage4, stage5]
    passed = sum(gates)
    verdict = 'PRODUCTION' if passed >= 4 else ('WATCH' if passed >= 2 else 'REJECT')
    print(f'\n  Gate Summary: {passed}/5 passed => {verdict}')

print()
print('=' * 80)
print('OVERALL DAILY_539 ASSESSMENT')
print('=' * 80)

# Best method identification
best_strat = None
best_edge = -999
for strat, recs in records.items():
    total = len(recs)
    nbets = recs[0].get('num_bets', 1)
    baseline = 1 - (1 - p3plus_1bet) ** nbets
    m3 = sum(1 for r in recs if r.get('is_m3plus'))
    edge = m3/total - baseline
    if edge > best_edge:
        best_edge = edge
        best_strat = strat

print(f'Best strategy: {best_strat} (edge={best_edge*100:+.2f}%)')
print(f'All strategies at signal ceiling — marginal edges only')
