import json

with open('data/rolling_monitor_DAILY_539.json','r') as f:
    data = json.load(f)
records = data['records']

# Check if 115000076 exists
for strat, recs in records.items():
    ids = [r['draw_id'] for r in recs]
    if '115000076' in ids:
        print(f'{strat} has 115000076')
    for r in recs:
        if r['draw_id'] == '115000075':
            print(f'{strat} 115000075: predicted={r["predicted_bets"]}, actual={r["actual"]}')
            break

print()
print('=== Rolling monitor full stats ===')
for strat, recs in records.items():
    total = len(recs)
    m3 = sum(1 for r in recs if r.get('is_m3plus'))
    m2 = sum(1 for r in recs if r.get('is_m2plus'))
    best_matches = [r.get('best_match',0) for r in recs]
    avg_best = sum(best_matches)/len(best_matches) if best_matches else 0
    nbets = recs[0].get('num_bets',1) if recs else 1
    print(f'{strat}: total={total}, nbets={nbets}, m3+={m3} ({m3/total*100:.1f}%), m2+={m2} ({m2/total*100:.1f}%), avg_best={avg_best:.2f}')
    
    # Last 30
    last30 = recs[-30:] if len(recs)>=30 else recs
    m3_30 = sum(1 for r in last30 if r.get('is_m3plus'))
    m2_30 = sum(1 for r in last30 if r.get('is_m2plus'))
    avg30 = sum(r.get('best_match',0) for r in last30)/len(last30) if last30 else 0
    print(f'  last-{len(last30)}: m3+={m3_30} ({m3_30/len(last30)*100:.1f}%), m2+={m2_30}, avg_best={avg30:.2f}')
    
    # Last 100
    last100 = recs[-100:] if len(recs)>=100 else recs
    m3_100 = sum(1 for r in last100 if r.get('is_m3plus'))
    avg100 = sum(r.get('best_match',0) for r in last100)/len(last100) if last100 else 0
    print(f'  last-{len(last100)}: m3+={m3_100} ({m3_100/len(last100)*100:.1f}%), avg_best={avg100:.2f}')

print()
# Check draw ID coverage
all_draws = set()
for strat, recs in records.items():
    for r in recs:
        all_draws.add(r['draw_id'])
sorted_draws = sorted(all_draws)
print(f'Draw range: {sorted_draws[0]} ~ {sorted_draws[-1]}, total unique={len(sorted_draws)}')

# Check continuity
int_draws = sorted([int(d) for d in all_draws])
gaps = []
for i in range(1, len(int_draws)):
    if int_draws[i] - int_draws[i-1] > 1:
        gaps.append((int_draws[i-1], int_draws[i]))
print(f'Gaps in draw sequence: {gaps[:10]}')

# Baseline calculation: random expected
# 539: pick 5 from 39. Expected hits for 1 bet = C(5,k)*C(34,5-k)/C(39,5)
from math import comb
total_comb = comb(39, 5)
print(f'\n=== Baseline (random) for 539 ===')
print(f'Total combinations: {total_comb}')
for k in range(6):
    p = comb(5,k) * comb(34, 5-k) / total_comb
    print(f'  P(match={k}) = {p:.6f} ({p*100:.3f}%)')

# For 3 bets
print('\nP(best_match>=3 | 3 bets):')
p3plus_1 = sum(comb(5,k)*comb(34,5-k)/total_comb for k in range(3,6))
p3plus_3 = 1 - (1 - p3plus_1)**3
print(f'  1 bet: {p3plus_1:.6f} ({p3plus_1*100:.3f}%)')
print(f'  3 bets: {p3plus_3:.6f} ({p3plus_3*100:.3f}%)')

p2plus_1 = sum(comb(5,k)*comb(34,5-k)/total_comb for k in range(2,6))
p2plus_3 = 1 - (1 - p2plus_1)**3
print(f'\nP(best_match>=2 | 3 bets):')
print(f'  1 bet: {p2plus_1:.6f} ({p2plus_1*100:.3f}%)')
print(f'  3 bets: {p2plus_3:.6f} ({p2plus_3*100:.3f}%)')

# Edge calculation
print('\n=== Edge by strategy (m3+ rate vs baseline) ===')
for strat, recs in records.items():
    total = len(recs)
    nbets = recs[0].get('num_bets',1) if recs else 1
    m3 = sum(1 for r in recs if r.get('is_m3plus'))
    baseline_m3 = 1 - (1-p3plus_1)**nbets
    observed = m3/total
    edge = observed - baseline_m3
    print(f'{strat} (x{nbets}): m3+={observed*100:.2f}% vs baseline={baseline_m3*100:.2f}%, edge={edge*100:+.2f}%')
    
    # Last 30
    last30 = recs[-30:]
    m3_30 = sum(1 for r in last30 if r.get('is_m3plus'))
    obs30 = m3_30/len(last30)
    print(f'  last-30: {obs30*100:.2f}% edge={((obs30-baseline_m3)*100):+.2f}%')
