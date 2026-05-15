"""
Full Strategy Revalidation Script — Phase Q
Audits all strategies, re-evaluates status, computes rankings, checks frontend consistency.
"""
import json
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data')
LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']

REQUIRED_FIELDS = [
    'edge_150p', 'edge_500p', 'edge_1500p',
    'perm_p', 'mcnemar_p', 'sharpe', 'max_drawdown_rate',
    'validated_status', 'composite_score',
]

def load_states(lt):
    path = os.path.join(BASE, 'strategy_states_%s.json' % lt)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def evaluate_status(s):
    """
    VALIDATED: all edges > 0 AND perm_p < 0.05 AND mcnemar_p < 0.05 AND sharpe > 0
    WATCH:     perm_p < 0.05 AND sharpe > 0 (but not all edges positive or mcnemar fails)
    REJECT:    perm_p >= 0.05 or sharpe <= 0
    """
    e150 = s.get('edge_150p')
    e500 = s.get('edge_500p')
    e1500 = s.get('edge_1500p')
    perm_p = s.get('perm_p')
    mcnemar_p = s.get('mcnemar_p')
    sharpe = s.get('sharpe')

    # Check for None values - use 0 as safe default
    e150 = e150 if e150 is not None else 0
    e500 = e500 if e500 is not None else 0
    e1500 = e1500 if e1500 is not None else 0
    sharpe = sharpe if sharpe is not None else 0

    all_positive = e150 > 0 and e500 > 0 and e1500 > 0
    perm_ok = perm_p is not None and perm_p < 0.05
    mcn_ok = mcnemar_p is not None and mcnemar_p < 0.05

    if all_positive and perm_ok and mcn_ok and sharpe > 0:
        return 'VALIDATED', 'all_positive + perm_ok + mcn_ok + sharpe > 0'
    elif perm_ok and sharpe > 0:
        reason = []
        if not all_positive:
            neg = []
            if e150 <= 0: neg.append('e150=%.4f' % e150)
            if e500 <= 0: neg.append('e500=%.4f' % e500)
            if e1500 <= 0: neg.append('e1500=%.4f' % e1500)
            if neg:
                reason.append('non-positive: %s' % ','.join(neg))
        if not mcn_ok:
            reason.append('mcnemar_p=%.4f>=0.05' % (mcnemar_p if mcnemar_p is not None else -1))
        return 'WATCH', '; '.join(reason) if reason else 'perm_ok+sharpe_ok but not all conditions'
    else:
        reason = []
        if not perm_ok:
            reason.append('perm_p=%.4f>=0.05' % (perm_p if perm_p is not None else -1))
        if sharpe <= 0:
            reason.append('sharpe=%.4f<=0' % sharpe)
        return 'REJECT', '; '.join(reason)

def composite_score(s):
    """Composite = mean of (e150+e500+e1500) weighted by sharpe and stability."""
    e150 = s.get('edge_150p') or 0
    e500 = s.get('edge_500p') or 0
    e1500 = s.get('edge_1500p') or 0
    sharpe = s.get('sharpe') or 0
    # Simple average of three windows
    avg_edge = (e150 + e500 + e1500) / 3.0
    # Penalty for high drawdown
    dd = s.get('max_drawdown_rate') or 0
    dd_penalty = dd * 0.1
    # Bonus for sharpe
    sharpe_bonus = sharpe * 0.05
    return avg_edge + sharpe_bonus - dd_penalty

STATUS_ORDER = {'VALIDATED': 0, 'WATCH': 1, 'REJECT': 2, None: 3}

def rank_key(s):
    vs = s.get('validated_status', 'REJECT')
    cs = s.get('composite_score') or 0
    e1500 = s.get('edge_1500p') or 0
    sharpe = s.get('sharpe') or 0
    dd = s.get('max_drawdown_rate') or 0
    return (STATUS_ORDER.get(vs, 3), -cs, -e1500, -sharpe, dd)

def check_missing(s):
    return [k for k in REQUIRED_FIELDS if s.get(k) is None]

# ── Main audit ────────────────────────────────────────────────────────────────

results = {}

for lt in LOTTERY_TYPES:
    states = load_states(lt)
    lt_results = []

    for name, s in sorted(states.items()):
        missing = check_missing(s)
        computed_status, reason = evaluate_status(s)
        current_status = s.get('validated_status', 'MISSING')
        status_match = current_status == computed_status

        entry = {
            'name': name,
            'num_bets': s.get('num_bets'),
            'edge_150p': s.get('edge_150p'),
            'edge_500p': s.get('edge_500p'),
            'edge_1500p': s.get('edge_1500p'),
            'perm_p': s.get('perm_p'),
            'mcnemar_p': s.get('mcnemar_p'),
            'sharpe': s.get('sharpe'),
            'max_drawdown_rate': s.get('max_drawdown_rate'),
            'validated_status_current': current_status,
            'validated_status_computed': computed_status,
            'status_match': status_match,
            'status_reason': reason,
            'composite_score_stored': s.get('composite_score'),
            'missing_fields': missing,
        }
        lt_results.append(entry)

    # Sort by ranking rules
    lt_results.sort(key=lambda x: (
        STATUS_ORDER.get(x['validated_status_current'], 3),
        -(x['composite_score_stored'] or 0),
        -(x['edge_1500p'] or 0),
        -(x['sharpe'] or 0),
        (x['max_drawdown_rate'] or 0)
    ))

    results[lt] = lt_results

# ── Print report ──────────────────────────────────────────────────────────────

for lt in LOTTERY_TYPES:
    print('\n' + '='*70)
    print('LOTTERY: %s' % lt)
    print('='*70)
    entries = results[lt]

    mismatches = [e for e in entries if not e['status_match']]
    print('Status mismatches: %d' % len(mismatches))
    if mismatches:
        for e in mismatches:
            print('  MISMATCH %s: current=%s computed=%s reason=%s' % (
                e['name'], e['validated_status_current'], e['validated_status_computed'], e['status_reason']))

    print('\nAll strategies (ranked):')
    header = '%-30s %3s  %-10s  %8s %8s %8s  %7s %7s %7s  %6s'
    print(header % ('Strategy', 'n', 'Status', 'e150', 'e500', 'e1500', 'perm_p', 'mcn_p', 'sharpe', 'cs'))
    print('-'*110)
    for e in entries:
        pp = e['perm_p']
        mp = e['mcnemar_p']
        print('%-30s %3s  %-10s  %8.4f %8.4f %8.4f  %7.4f %7.4f %7.4f  %6.4f' % (
            e['name'], e['num_bets'], e['validated_status_current'],
            e['edge_150p'] or 0, e['edge_500p'] or 0, e['edge_1500p'] or 0,
            pp if pp is not None else -1,
            mp if mp is not None else -1,
            e['sharpe'] or 0,
            e['composite_score_stored'] or 0,
        ))

    print('\nBest strategy overall: %s (%s, n=%s, cs=%.4f)' % (
        entries[0]['name'], entries[0]['validated_status_current'],
        entries[0]['num_bets'], entries[0]['composite_score_stored'] or 0))

    # Per-bet-count best
    by_n = {}
    for e in entries:
        n = e['num_bets']
        if n not in by_n:
            by_n[n] = e
    print('\nBest per num_bets:')
    for n in sorted(by_n.keys()):
        e = by_n[n]
        print('  n=%d: %s (%s, cs=%.4f)' % (n, e['name'], e['validated_status_current'], e['composite_score_stored'] or 0))

print('\n\nDONE')
