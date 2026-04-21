import json
with open('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/strategy_states_BIG_LOTTO.json') as f:
    data = json.load(f)

rows = []
for k, v in data.items():
    rows.append({
        'name':  v.get('name', k),
        'bets':  v.get('num_bets'),
        'stat':  v.get('validated_status') or v.get('status'),
        'e150':  v.get('edge_150p'),
        'e500':  v.get('edge_500p'),
        'e1500': v.get('edge_1500p'),
        'perm':  v.get('perm_p'),
        'mc':    v.get('mcnemar_p'),
        'sh':    v.get('sharpe'),
        'dd':    v.get('max_drawdown_rate'),
        'comp':  v.get('composite_score'),
        'note':  v.get('validation_notes', ''),
    })

def fnum(x, d=4):
    return f'{x:.{d}f}' if isinstance(x, (int, float)) else '—'

rows.sort(key=lambda r: (-(r['e500'] or -9)))

hdr = f"{'name':<38} {'bets':>4} {'status':<12} {'e150':>8} {'e500':>8} {'e1500':>8} {'perm':>7} {'mc':>7} {'sharpe':>7} {'dd':>7} {'comp':>8}"
print(hdr)
print('-' * len(hdr))
for r in rows:
    line = f"{r['name'][:38]:<38} {str(r['bets']):>4} {str(r['stat']):<12} "
    line += f"{fnum(r['e150']):>8} {fnum(r['e500']):>8} {fnum(r['e1500']):>8} "
    line += f"{fnum(r['perm'], 3):>7} {fnum(r['mc'], 3):>7} {fnum(r['sh']):>7} "
    line += f"{fnum(r['dd'], 4):>7} {fnum(r['comp']):>8}"
    print(line)
    if r['note']:
        print(f"    note: {r['note']}")

print()
print(f'Total: {len(rows)}')

# Group by bet count
from collections import defaultdict
by_bets = defaultdict(list)
for r in rows:
    by_bets[r['bets']].append(r)

print('\n=== By Bet Count (avg of strategies with each bet count) ===')
for bets in sorted(by_bets.keys(), key=lambda x: x or 0):
    strs = by_bets[bets]
    n = len(strs)
    ae150 = sum((s['e150'] or 0) for s in strs) / n
    ae500 = sum((s['e500'] or 0) for s in strs) / n
    ae1500 = sum((s['e1500'] or 0) for s in strs) / n
    ash = sum((s['sh'] or 0) for s in strs) / n
    add = sum((s['dd'] or 0) for s in strs) / n
    print(f'{bets}-bet: n={n}  avg_e150={ae150:+.4f}  avg_e500={ae500:+.4f}  avg_e1500={ae1500:+.4f}  avg_sharpe={ash:+.4f}  avg_dd={add:.4f}')

# Best by each bet count (by e500)
print('\n=== Best per Bet Count (by e500) ===')
for bets in sorted(by_bets.keys(), key=lambda x: x or 0):
    strs = by_bets[bets]
    best = max(strs, key=lambda s: s['e500'] or -99)
    print(f'{bets}-bet: {best["name"]} | e500={fnum(best["e500"])} e1500={fnum(best["e1500"])} perm={fnum(best["perm"],3)} mc={fnum(best["mc"],3)} sh={fnum(best["sh"])} dd={fnum(best["dd"],4)} status={best["stat"]}')

# Strategy family classification
print('\n=== By Strategy Family ===')
fams = defaultdict(list)
for r in rows:
    nm = r['name'].lower()
    if 'fourier' in nm and 'markov' in nm:  fams['Hybrid(F+M)'].append(r)
    elif 'fourier' in nm:                   fams['Fourier'].append(r)
    elif 'markov' in nm:                    fams['Markov'].append(r)
    elif 'deviation' in nm:                 fams['Deviation'].append(r)
    else:                                   fams['Other'].append(r)
for fam, strs in fams.items():
    n = len(strs)
    valid = sum(1 for s in strs if s['stat'] in ('PRODUCTION','VALIDATED'))
    watch = sum(1 for s in strs if s['stat'] == 'WATCH')
    rej   = sum(1 for s in strs if s['stat'] in ('REJECT','REJECTED'))
    ae500 = sum((s['e500'] or 0) for s in strs) / n
    ae1500 = sum((s['e1500'] or 0) for s in strs) / n
    ash = sum((s['sh'] or 0) for s in strs) / n
    print(f'{fam:<20} n={n}  PROD/VAL={valid}  WATCH={watch}  REJ={rej}  avg_e500={ae500:+.4f}  avg_e1500={ae1500:+.4f}  avg_sharpe={ash:+.4f}')
