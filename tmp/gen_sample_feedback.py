"""
Generate sample output for Phase R — Action Feedback Layer.
Simulates 3 lotteries with completed actions + rule stats.
"""
import json
import os
import sys
import shutil

sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

# ── Temporarily set up a mock feedback store with realistic data ──────────────

FEEDBACK_PATH = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/action_feedback.json'

# Backup any existing store
if os.path.exists(FEEDBACK_PATH):
    shutil.copy(FEEDBACK_PATH, FEEDBACK_PATH + '.bak_sample')

import uuid
from datetime import datetime, timezone, timedelta

def ts(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

def make_action(lt, code, prio, title, strategy, draw_ref, baseline,
                status='COMPLETED', outcome=None):
    return {
        'action_id': str(uuid.uuid4()),
        '_fingerprint': f'{lt}|{code}|{strategy}|{(draw_ref//10)*10}',
        'lottery_type': lt,
        'strategy': strategy,
        'priority': prio,
        'action_type': code,
        'action_title': title,
        'created_at': ts(35),
        'created_draw_ref': draw_ref,
        'baseline': baseline,
        'tracking_window': 30,
        'status': status,
        'evaluated_at': ts(2) if status == 'COMPLETED' else None,
        'outcome': outcome,
    }

mock_actions = [
    # ── DAILY_539 ───────────────────────────────────────────────────────────
    make_action('DAILY_539', 'R03_LEARNING_INEFFECTIVE', 'P2', 'Learning 未產生實質影響',
                'f4cold_5bet', 5000,
                {'edge_1500p': 0.0861, 'sharpe': 0.1728, 'drawdown': 0.018},
                'COMPLETED',
                {'edge_delta': 0.0042, 'sharpe_delta': 0.0021, 'drawdown_delta': -0.002,
                 'effectiveness': 'EFFECTIVE', 'draws_elapsed': 32,
                 'current_metrics': {'edge_1500p': 0.0903, 'sharpe': 0.1749, 'drawdown': 0.016}}),

    make_action('DAILY_539', 'R05_WEAK_RESEARCH', 'P2', '研究訊號弱',
                'f4cold_5bet', 4970,
                {'edge_1500p': 0.0840, 'sharpe': 0.1700, 'drawdown': 0.019},
                'COMPLETED',
                {'edge_delta': 0.0021, 'sharpe_delta': 0.0028, 'drawdown_delta': -0.001,
                 'effectiveness': 'EFFECTIVE', 'draws_elapsed': 30,
                 'current_metrics': {'edge_1500p': 0.0861, 'sharpe': 0.1728, 'drawdown': 0.018}}),

    make_action('DAILY_539', 'R08_LOW_SHARPE', 'P2', '風險調整後績效偏低',
                'acb_1bet', 4980,
                {'edge_1500p': 0.0260, 'sharpe': 0.0749, 'drawdown': 0.030},
                'COMPLETED',
                {'edge_delta': -0.001, 'sharpe_delta': 0.001, 'drawdown_delta': 0.002,
                 'effectiveness': 'NEUTRAL', 'draws_elapsed': 30,
                 'current_metrics': {'edge_1500p': 0.0250, 'sharpe': 0.0759, 'drawdown': 0.032}}),

    # ── BIG_LOTTO ───────────────────────────────────────────────────────────
    make_action('BIG_LOTTO', 'R06_NO_VALIDATED', 'P0', '目前無完整驗證策略',
                'regime_2bet', 2600,
                {'edge_1500p': 0.0110, 'sharpe': 0.0530, 'drawdown': 0.038},
                'COMPLETED',
                {'edge_delta': 0.0018, 'sharpe_delta': 0.0059, 'drawdown_delta': -0.003,
                 'effectiveness': 'EFFECTIVE', 'draws_elapsed': 30,
                 'current_metrics': {'edge_1500p': 0.0128, 'sharpe': 0.0589, 'drawdown': 0.035}}),

    make_action('BIG_LOTTO', 'R07_ALL_WATCH', 'P1', '所有策略仍在觀察期',
                'p1_deviation_4bet', 2600,
                {'edge_1500p': 0.0230, 'sharpe': 0.0780, 'drawdown': 0.032},
                'COMPLETED',
                {'edge_delta': 0.0003, 'sharpe_delta': 0.001, 'drawdown_delta': 0.0,
                 'effectiveness': 'NEUTRAL', 'draws_elapsed': 31,
                 'current_metrics': {'edge_1500p': 0.0233, 'sharpe': 0.0790, 'drawdown': 0.032}}),

    make_action('BIG_LOTTO', 'R09_HIGH_DRAWDOWN', 'P1', '近期回撤超過警戒線',
                'ts3_regime_3bet', 2590,
                {'edge_1500p': 0.0112, 'sharpe': 0.0449, 'drawdown': 0.055},
                'COMPLETED',
                {'edge_delta': -0.0005, 'sharpe_delta': -0.002, 'drawdown_delta': 0.008,
                 'effectiveness': 'NEGATIVE', 'draws_elapsed': 33,
                 'current_metrics': {'edge_1500p': 0.0107, 'sharpe': 0.0429, 'drawdown': 0.063}}),

    # ── POWER_LOTTO ─────────────────────────────────────────────────────────
    make_action('POWER_LOTTO', 'R06_NO_VALIDATED', 'P0', '目前無完整驗證策略',
                'orthogonal_5bet', 1900,
                {'edge_1500p': 0.0382, 'sharpe': 0.0850, 'drawdown': 0.025},
                'COMPLETED',
                {'edge_delta': -0.002, 'sharpe_delta': -0.006, 'drawdown_delta': 0.004,
                 'effectiveness': 'NEGATIVE', 'draws_elapsed': 30,
                 'current_metrics': {'edge_1500p': 0.0362, 'sharpe': 0.0790, 'drawdown': 0.029}}),

    make_action('POWER_LOTTO', 'R02_NEAR_THRESHOLD', 'P2', '策略接近驗證門檻',
                'midfreq_fourier_mk_3bet', 1890,
                {'edge_1500p': 0.0243, 'sharpe': 0.0751, 'drawdown': 0.027},
                'COMPLETED',
                {'edge_delta': 0.0000, 'sharpe_delta': 0.000, 'drawdown_delta': 0.0,
                 'effectiveness': 'NEUTRAL', 'draws_elapsed': 30,
                 'current_metrics': {'edge_1500p': 0.0243, 'sharpe': 0.0751, 'drawdown': 0.027}}),

    make_action('POWER_LOTTO', 'R03_LEARNING_INEFFECTIVE', 'P2', 'Learning 未產生實質影響',
                'orthogonal_5bet', 1880,
                {'edge_1500p': 0.0380, 'sharpe': 0.0840, 'drawdown': 0.024},
                'COMPLETED',
                {'edge_delta': 0.0002, 'sharpe_delta': 0.001, 'drawdown_delta': 0.001,
                 'effectiveness': 'NEUTRAL', 'draws_elapsed': 32,
                 'current_metrics': {'edge_1500p': 0.0382, 'sharpe': 0.0850, 'drawdown': 0.025}}),

    # Tracking (not yet evaluated)
    make_action('DAILY_539', 'R01_DEGRADING', 'P1', '策略可能進入衰退期',
                'f4cold_5bet', 5030,
                {'edge_1500p': 0.0903, 'sharpe': 0.1749, 'drawdown': 0.016},
                'TRACKING', None),

    make_action('BIG_LOTTO', 'R02_NEAR_THRESHOLD', 'P2', '策略接近驗證門檻',
                'p1_dev_sum5bet', 2630,
                {'edge_1500p': 0.0274, 'sharpe': 0.0852, 'drawdown': 0.028},
                'OPEN', None),
]

# Write mock store
store = {'actions': mock_actions, 'last_updated': ts()}
with open(FEEDBACK_PATH, 'w') as f:
    json.dump(store, f, indent=2, ensure_ascii=False)

print('Mock feedback store written.')

# Now run the actual engine
from engine.action_feedback import get_feedback_summary, get_rule_rankings, get_all_actions

print('\n' + '='*60)
print('GET /api/actionable/feedback (sample output)')
print('='*60)
result = get_feedback_summary()
print(json.dumps(result, indent=2, ensure_ascii=False))

print('\n' + '='*60)
print('GET /api/actionable/rules (sample output)')
print('='*60)
rules = get_rule_rankings()
for r in rules:
    rec = r['recommendation']
    print(f"  {r['action_type']:<30} score={r['rule_score']:+.2f}  eff={r['effectiveness_rate']:.0%}  total={r['total']}  → {rec}")

# Restore backup if it existed
bak = FEEDBACK_PATH + '.bak_sample'
if os.path.exists(bak):
    shutil.copy(bak, FEEDBACK_PATH)
    os.remove(bak)
    print('\nOriginal feedback store restored.')
else:
    print(f'\nSample data left at {FEEDBACK_PATH} (no prior store existed).')
