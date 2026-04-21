import json
from math import comb

# The user says: 115000076 actual = [14, 17, 20, 24, 37]
actual = sorted([14, 17, 20, 24, 37])
print('=== 115000076 actual numbers analysis ===')
print(f'Numbers: {actual}')
print(f'Sum: {sum(actual)}')
print(f'Odd/Even: {sum(1 for n in actual if n%2==1)}/{sum(1 for n in actual if n%2==0)}')
print(f'High(>=20)/Low(<20): {sum(1 for n in actual if n>=20)}/{sum(1 for n in actual if n<20)}')
gaps = [actual[i+1]-actual[i] for i in range(len(actual)-1)]
print(f'Gaps between consecutive: {gaps}')
print(f'Tail digits: {[n%10 for n in actual]}')
zones = []
for n in actual:
    if n <= 10: zones.append('Z1')
    elif n <= 20: zones.append('Z2')
    elif n <= 30: zones.append('Z3')
    else: zones.append('Z4')
print(f'Zone distribution: {zones}')
print(f'Zone counts: Z1={zones.count("Z1")}, Z2={zones.count("Z2")}, Z3={zones.count("Z3")}, Z4={zones.count("Z4")}')

# Check if 115000076 exists in rolling monitor
with open('data/rolling_monitor_DAILY_539.json','r') as f:
    data = json.load(f)

print()
print('=== Predictions for 115000076 (if available) ===')
found_076 = False
for strat, recs in data['records'].items():
    for r in recs:
        if r['draw_id'] == '115000076':
            found_076 = True
            print(f'{strat}: predicted={r["predicted_bets"]}')
            for i, bet in enumerate(r['predicted_bets']):
                hits = set(bet) & set(actual)
                print(f'  bet {i+1}: {bet} => hits={sorted(hits)} ({len(hits)})')

if not found_076:
    print('115000076 NOT in rolling monitor - data not yet synced')
    print()
    print('=== Using 115000075 predictions as reference ===')
    for strat, recs in data['records'].items():
        for r in recs:
            if r['draw_id'] == '115000075':
                print(f'\n{strat} (predicted for 075, comparing shape vs 076):')
                for i, bet in enumerate(r['predicted_bets']):
                    hits_076 = set(bet) & set(actual)
                    print(f'  bet {i+1}: {bet} => hits vs 076 actual={sorted(hits_076)} ({len(hits_076)})')
                break

# JSONL predictions
print()
print('=== JSONL prediction for 115000075 (pending, comparing with 076) ===')
with open('lottery_api/data/predictions_DAILY_539.jsonl') as f:
    for line in f:
        d = json.loads(line.strip())
        if d['period'] == '115000075':
            print(f'Strategy: {d["strategy"]}, bets={d["bets"]}')
            for i, bet in enumerate(d['bets']):
                hits = set(bet) & set(actual)
                print(f'  bet {i+1}: {bet} => hits vs 076={sorted(hits)} ({len(hits)})')

# Feature analysis for recent draws
print()
print('=== Recent draw feature patterns ===')
# Get last 10 draws from rolling monitor
strat0 = list(data['records'].keys())[0]
recent = data['records'][strat0][-10:]
for r in recent:
    a = r['actual']
    s = sum(a)
    oe = f'{sum(1 for n in a if n%2==1)}O/{sum(1 for n in a if n%2==0)}E'
    g = [a[i+1]-a[i] for i in range(len(a)-1)]
    print(f'  {r["draw_id"]} {r["date"]}: {a} sum={s} {oe} gaps={g}')

# Now add 115000076
s076 = sum(actual)
oe076 = f'{sum(1 for n in actual if n%2==1)}O/{sum(1 for n in actual if n%2==0)}E'
g076 = [actual[i+1]-actual[i] for i in range(len(actual)-1)]
print(f'  115000076 115/03/26: {actual} sum={s076} {oe076} gaps={g076}')

# Popularity analysis (Winning Quality)
print()
print('=== Winning Quality Analysis for 115000076 ===')
# Common popular numbers in Taiwan 539 (birthdays, lucky numbers)
popular_nums = {1,2,3,5,6,7,8,9,10,11,12,13,15,18,22,23,25,28,33,38}
hits_popular = set(actual) & popular_nums
print(f'Popular overlap: {sorted(hits_popular)} ({len(hits_popular)}/5)')

# Birthday numbers (1-31)   
birthday = sum(1 for n in actual if n <= 31)
print(f'Birthday range (1-31): {birthday}/5')

# Consecutive check
consec = sum(1 for i in range(len(actual)-1) if actual[i+1]-actual[i]==1)
print(f'Consecutive pairs: {consec}')

# Split risk estimation
if birthday >= 4:
    split_risk = 'HIGH'
elif birthday >= 3:
    split_risk = 'MED'
else:
    split_risk = 'LOW'
print(f'Split risk: {split_risk} (birthday={birthday}/5)')

# Payout quality
if split_risk == 'LOW' and len(hits_popular) <= 2:
    payout_q = 'HIGH'
elif split_risk == 'HIGH':
    payout_q = 'LOW'
else:
    payout_q = 'MED'
print(f'Payout quality: {payout_q}')

# Expected winners estimation (rough heuristic)
# Taiwan 539 daily sales ~15M TWD, each bet 50 TWD => ~300K bets/draw
est_bets = 300000
# If numbers are popular, more people pick them
if len(hits_popular) >= 4:
    winner_multiplier = 2.5
elif len(hits_popular) >= 3:
    winner_multiplier = 1.5
else:
    winner_multiplier = 1.0
# Base winners assuming uniform: est_bets / C(39,5)
base_winners_5 = est_bets / comb(39,5)
est_winners = base_winners_5 * winner_multiplier
print(f'Estimated winners (5-match): {est_winners:.2f} (multiplier={winner_multiplier}x)')
