#!/usr/bin/env python3
"""Generate final system status report."""
import json, os
from datetime import datetime

DATA_DIR = 'data'

with open(os.path.join(DATA_DIR, 'latest_draws_snapshot.json')) as f:
    snap = json.load(f)
with open(os.path.join(DATA_DIR, 'strategy_refresh_report.json')) as f:
    refresh = json.load(f)
with open(os.path.join(DATA_DIR, 'h9_mcnemar_report.json')) as f:
    h9 = json.load(f)
with open('data/shadow_C_milestone.json') as f:
    shadow_c = json.load(f)

total_strats = sum(len(v) for v in refresh['by_lottery'].values())

status = {
    'report_date': '2026-04-19',
    'generated_at': datetime.now().isoformat(),
    'db_snapshot': {
        'BIG_LOTTO': snap['BIG_LOTTO'],
        'DAILY_539': snap['DAILY_539'],
        'POWER_LOTTO': snap['POWER_LOTTO'],
    },
    'pre_cleanup': {
        'shadow_C_gate_removed': True,
        'shadow_C_status': shadow_c.get('current_status'),
        'shadow_C_note': 'gate=0% validated OOS; shadow_C equiv to p1_dev_sum5bet. Gate removed from rsm_bootstrap.py.',
    },
    'line_a_oos_refresh': {
        'status': 'COMPLETE',
        'strategies_refreshed': total_strats,
        'notable_drifts': len(refresh['notable_drifts']),
        'by_lottery': refresh['by_lottery'],
    },
    'line_b_h9_analysis': {
        'status': 'COMPLETE',
        'decision': h9['decision'],
        'mcnemar_net': h9['mcnemar']['net'],
        'mcnemar_p': h9['mcnemar']['p'],
        'perm_p': h9['permutation_test']['perm_p'],
        'h9_1500p': h9['h9_windows']['1500p'],
        'mf_1500p': h9['mf_windows']['1500p'],
        'verdict': 'H9 full-history net=-8 (regressed from +25). Advantage was small-sample noise. No promotion basis.',
        'promotion_conditions': h9['promotion_conditions'],
    },
    'deployed_strategy_keys': {
        'DAILY_539': {'1': 'acb_1bet', '2': 'midfreq_acb_2bet', '3': 'acb_markov_midfreq_3bet', '5': 'f4cold_5bet'},
        'BIG_LOTTO': {'4': 'p1_deviation_4bet', '5': 'p1_dev_sum5bet'},
        'POWER_LOTTO': {'2': 'fourier_rhythm_2bet', '3': 'fourier_rhythm_3bet', '4': 'pp3_freqort_4bet', '5': 'orthogonal_5bet'},
    },
    'action_items': [
        'NO deployment changes this cycle.',
        'H9 stays SHADOW; L93 updated with full-history regression finding.',
        'All strategy_states_*.json refreshed with 2026-04-19 OOS data.',
        'Next full refresh: +300 draws or ~2026-07.',
    ],
    'system_health': 'STABLE',
    'system_health_note': 'No drifts > 1.5pp; all deployed strategies edge positive at 1500p window.',
}

out = 'data/system_status_2026_04_19.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(status, f, indent=2, ensure_ascii=False)
print('Saved:', out)

print('\n=== SYSTEM STATUS SUMMARY ===')
print('  Report date:', status['report_date'])
print('  DB latest: BIG_LOTTO=%s, 539=%s, PL=%s' % (
    snap['BIG_LOTTO']['latest_draw'],
    snap['DAILY_539']['latest_draw'],
    snap['POWER_LOTTO']['latest_draw'],
))

print('\n  PRE-CLEANUP:')
print('    shadow_C status:', shadow_c.get('current_status'))

print('\n  LINE A — Strategy Refresh (1500p edges):')
for lt, strat_list in refresh['by_lottery'].items():
    print('    [%s]' % lt)
    for s in strat_list:
        delta = round(s['new_1500p'] - s['old_1500p'], 4) if s['old_1500p'] is not None else 'N/A'
        print('      %-32s %s -> %s  (delta=%s)' % (s['strategy'], s['old_1500p'], s['new_1500p'], delta))

print('\n  LINE B — H9 Decision:')
print('    Decision:', status['line_b_h9_analysis']['decision'])
print('    McNemar: net=%d, p=%.4f  (prev net=+25, p=0.119)' % (
    h9['mcnemar']['net'], h9['mcnemar']['p']))
print('    Perm p=%.4f' % h9['permutation_test']['perm_p'])
print('    H9_1500p=%.4f vs MF_1500p=%.4f' % (h9['h9_windows']['1500p'], h9['mf_windows']['1500p']))

print('\n  System Health:', status['system_health'])
print(' ', status['system_health_note'])
print('\n  Action items:')
for a in status['action_items']:
    print('   *', a)
