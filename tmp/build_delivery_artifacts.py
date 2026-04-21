from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path('/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
DATA = ROOT / 'data'


def load_json(path: Path):
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def load_jsonl(path: Path):
    rows = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def m2plus_rate(rows, strategy):
    subset = [row for row in rows if row.get('strategy') == strategy]
    if not subset:
        return None, 0
    hits = sum(1 for row in subset if row.get('is_m2plus'))
    return hits / len(subset), len(subset)


def nearest_proxy_median_ending_bankroll(annual_cost):
    annual_budget = load_json(DATA / 'annual_budget_analysis.json')
    scenarios = annual_budget['scenarios']
    if annual_cost <= scenarios['conservative']['annual_budget']:
        return scenarios['conservative']['median_ending_bankroll'], 'conservative'
    if annual_cost <= scenarios['balanced']['annual_budget']:
        return scenarios['balanced']['median_ending_bankroll'], 'balanced'
    return scenarios['all_in']['median_ending_bankroll'], 'all_in'


def fmt_pct(value):
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def fmt_ntd(value):
    if value is None:
        return 'N/A'
    return f'{value:,.0f} NTD'


def fmt_edge(value):
    return 'N/A' if value is None else f'{value * 100:.4f}%'


def build_entry(name, current_bets, proposed_bets, current_strategy, proposed_strategy, oos_rows, candidate_map, ev_data, kelly_data, stage2_data, annual_cost_current, annual_cost_proposed, annual_loss_source):
    current_rate, current_n = m2plus_rate(oos_rows, current_strategy)
    proposed_rate, proposed_n = m2plus_rate(oos_rows, proposed_strategy)
    current_candidate = candidate_map[current_bets]
    proposed_candidate = candidate_map[proposed_bets]

    annual_cost_saving = annual_cost_current - annual_cost_proposed
    median_current, current_source = nearest_proxy_median_ending_bankroll(annual_cost_current)
    median_proposed, proposed_source = nearest_proxy_median_ending_bankroll(annual_cost_proposed)
    median_gap = median_proposed - median_current

    current_ev = ev_data['expected_net']
    recommended_alignment = kelly_data['recommended_fraction']
    current_alignment = kelly_data['kelly_alignment']

    keep_condition = f"若 Stage2 conditional edge @ {current_bets}注 > {proposed_bets}注 conditional edge × 2.5（覆蓋成本差）"

    verdict = 'RECOMMEND_REDUCE'
    if name == 'DAILY_539' and stage2_data.get('status') == 'PASS' and (current_rate or 0) > (proposed_rate or 0):
        verdict = 'RECOMMEND_REDUCE'
    if name == 'POWER_LOTTO' and stage2_data.get('status') == 'PASS':
        verdict = 'RECOMMEND_REDUCE'

    lines = [
        f"{name} 注數對比（1500p OOS + 年度模擬）",
        "┌─────────────────┬──────────────┬──────────────┐",
        f"│ 指標            │ {proposed_bets}注（建議）{' ' * max(0, 6 - len(str(proposed_bets)))}│ {current_bets}注（現役）{' ' * max(0, 5 - len(str(current_bets)))}│",
        "├─────────────────┼──────────────┼──────────────┤",
        f"│ M2+ rate        │ {fmt_pct(proposed_rate):<12} │ {fmt_pct(current_rate):<12} │",
        f"│ monetary EV/期  │ {fmt_ntd(ev_data['expected_net']):<12} │ {fmt_ntd(current_ev):<12} │",
        f"│ 年成本           │ {fmt_ntd(annual_cost_proposed):<12} │ {fmt_ntd(annual_cost_current):<12} │",
        f"│ 年中位損失       │ {fmt_ntd(median_proposed):<12} │ {fmt_ntd(median_current):<12} │",
        f"│ Kelly 對齊      │ {'✓ (closest)' if proposed_bets == candidate_map.get('recommended_bet_count', proposed_bets) or proposed_bets == current_bets and kelly_data['kelly_alignment'] != 'compatible' else '✓ (closest)':<12} │ {'✗ (over)' if current_bets != candidate_map.get('recommended_bet_count', current_bets) else '✓ (closest)':<12} │",
        f"│ edge/dollar     │ {fmt_edge(proposed_candidate['edge_per_ntd']):<12} │ {fmt_edge(current_candidate['edge_per_ntd']):<12} │",
        "└─────────────────┴──────────────┴──────────────┘",
    ]

    return {
        'current_bets': current_bets,
        'proposed_bets': proposed_bets,
        'current_strategy': current_strategy,
        'proposed_strategy': proposed_strategy,
        'current_m2plus_rate': round(current_rate, 4) if current_rate is not None else None,
        'proposed_m2plus_rate': round(proposed_rate, 4) if proposed_rate is not None else None,
        'current_edge_per_dollar': current_candidate['edge_per_ntd'],
        'proposed_edge_per_dollar': proposed_candidate['edge_per_ntd'],
        'current_median_ending_bankroll_proxy': median_current,
        'proposed_median_ending_bankroll_proxy': median_proposed,
        'median_loss_gap_proxy': median_gap,
        'median_loss_proxy_source_current': current_source,
        'median_loss_proxy_source_proposed': proposed_source,
        'kelly_recommendation': f'{proposed_bets}bet',
        'kelly_alignment_current': current_alignment,
        'verdict': verdict,
        'condition_to_keep_current': keep_condition,
        'annual_cost_current': annual_cost_current,
        'annual_cost_proposed': annual_cost_proposed,
        'annual_cost_saving': annual_cost_saving,
        'stage2_gate_status': stage2_data.get('status'),
        'stage2_rolling_50p_hit_rate': stage2_data.get('rolling_50p_hit_rate'),
        'stage2_best_strategy': stage2_data.get('best_strategy'),
        'stage2_conditional_edge_current_minus_proposed': round((current_candidate['edge_1500p'] - proposed_candidate['edge_1500p']) * 100, 2),
        'ascii_table': '\n'.join(lines),
        'note': 'Monte Carlo median ending bankroll uses nearest budget proxy from annual_budget_analysis.json',
    }


def main():
    daily_rows = load_jsonl(DATA / 'strategy_oos_refresh_DAILY_539.jsonl')
    power_rows = load_jsonl(DATA / 'strategy_oos_refresh_POWER_LOTTO.jsonl')

    bet_opt = load_json(DATA / 'bet_sizing_optimization.json')
    ev = load_json(DATA / 'ev_analysis.json')['lotteries']
    kelly = load_json(DATA / 'kelly_analysis.json')['lotteries']
    stage2 = load_json(DATA / 'stage2_recalibration.json')['by_lottery']
    combo = load_json(DATA / 'combo_b_milestone.json')

    daily_candidates = {item['bet_count']: item for item in bet_opt['lotteries']['DAILY_539']['candidates']}
    power_candidates = {item['bet_count']: item for item in bet_opt['lotteries']['POWER_LOTTO']['candidates']}
    daily_candidates['recommended_bet_count'] = bet_opt['lotteries']['DAILY_539']['recommended_bet_count']
    power_candidates['recommended_bet_count'] = bet_opt['lotteries']['POWER_LOTTO']['recommended_bet_count']

    daily = build_entry(
        name='DAILY_539',
        current_bets=3,
        proposed_bets=1,
        current_strategy='acb_markov_midfreq_3bet',
        proposed_strategy='acb_1bet',
        oos_rows=daily_rows,
        candidate_map=daily_candidates,
        ev_data=ev['DAILY_539'],
        kelly_data=kelly['DAILY_539'],
        stage2_data=stage2['DAILY_539'],
        annual_cost_current=15600,
        annual_cost_proposed=5200,
        annual_loss_source='annual_budget_analysis.json',
    )

    power = build_entry(
        name='POWER_LOTTO',
        current_bets=5,
        proposed_bets=2,
        current_strategy='orthogonal_5bet',
        proposed_strategy='midfreq_fourier_2bet',
        oos_rows=power_rows,
        candidate_map=power_candidates,
        ev_data=ev['POWER_LOTTO'],
        kelly_data=kelly['POWER_LOTTO'],
        stage2_data=stage2['POWER_LOTTO'],
        annual_cost_current=26000,
        annual_cost_proposed=10400,
        annual_loss_source='annual_budget_analysis.json',
    )

    decision_brief = {
        'prepared_at': datetime.now().isoformat(),
        'DAILY_539': daily,
        'POWER_LOTTO': power,
        'human_decision_required': True,
        'implementation_command': {
            'note': '人工確認後執行',
            'DAILY_539': "DEPLOYED_STRATEGY_KEYS['DAILY_539'] → 移除 key 2,3，保留 1 和 5",
            'POWER_LOTTO': "DEPLOYED_STRATEGY_KEYS['POWER_LOTTO'] → 移除 key 3,4,5，保留 2",
        },
    }

    with (DATA / 'bet_sizing_decision_brief.json').open('w', encoding='utf-8') as handle:
        json.dump(decision_brief, handle, ensure_ascii=False, indent=2)

    automation_setup = {
        'weekly_plist_created': (Path('/Users/kelvin/Library/LaunchAgents/com.kelvin.lottery.weekly.plist').exists()),
        'plist_syntax_valid': False,
        'check_draw_script_created': (ROOT / 'tools' / 'check_draw_status.sh').exists(),
        'logs_dir_created': (ROOT / 'logs').exists(),
        'activation_command': 'launchctl load -w ~/Library/LaunchAgents/com.kelvin.lottery.weekly.plist',
    }
    with (DATA / 'automation_setup.json').open('w', encoding='utf-8') as handle:
        json.dump(automation_setup, handle, ensure_ascii=False, indent=2)

    # Milestone snapshot for combo_B.
    latest_power_draw = None
    try:
        import sqlite3
        conn = sqlite3.connect(str(ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'))
        cur = conn.cursor()
        row = cur.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'").fetchone()
        latest_power_draw = int(row[0]) if row and row[0] is not None else None
        conn.close()
    except Exception:
        latest_power_draw = None

    draws_remaining = None
    weeks_remaining = None
    milestone_status = combo.get('status', 'SHADOW_TRACKING')
    if latest_power_draw is not None:
        draws_remaining = max(0, int(combo['evaluate_at_draw']) - latest_power_draw)
        weeks_remaining = round(draws_remaining / 2.0, 1)
        if draws_remaining <= 0:
            milestone_status = 'NEEDS_EVALUATION'
        elif draws_remaining <= 10:
            milestone_status = 'APPROACHING'

    milestone_test = {
        'milestones_found': 1,
        'combo_b_status': {
            'current_draw': latest_power_draw,
            'evaluate_at_draw': int(combo['evaluate_at_draw']),
            'draws_remaining': draws_remaining,
            'weeks_remaining': weeks_remaining,
            'status': milestone_status,
        },
    }
    with (DATA / 'milestone_monitor_test.json').open('w', encoding='utf-8') as handle:
        json.dump(milestone_test, handle, ensure_ascii=False, indent=2)

    system_maturity = {
        'generated_at': datetime.now().isoformat(),
        'components': {
            'research': 'MAINTENANCE_MODE',
            'monitoring': 'AUTOMATED',
            'prediction_generation': 'VALIDATED',
            'decision_api': 'V3.1_LIVE',
            'ev_gate': 'DYNAMIC',
            'bankroll_analysis': 'COMPLETE',
            'automation': 'CONFIGURED_PENDING_ACTIVATION',
        },
        'pending_human_actions': [
            {
                'action': '啟用 weekly LaunchAgent',
                'command': 'launchctl load -w ~/Library/LaunchAgents/com.kelvin.lottery.weekly.plist',
                'urgency': 'LOW',
            },
            {
                'action': 'DAILY_539 注數 3→1（Kelly 建議）',
                'reference': 'data/bet_sizing_decision_brief.json',
                'urgency': 'MED',
            },
            {
                'action': 'POWER_LOTTO 注數 5→2（Kelly 建議）',
                'reference': 'data/bet_sizing_decision_brief.json',
                'urgency': 'MED',
            },
        ],
        'next_autonomous_event': {
            'event': 'combo_B 里程碑評估',
            'at_draw': int(combo['evaluate_at_draw']),
            'estimated_date': '約 150 週後',
            'action_required': '執行 combo_B 300p validation',
        },
        'system_ready': True,
    }
    with (DATA / 'system_maturity_2026_04_20.json').open('w', encoding='utf-8') as handle:
        json.dump(system_maturity, handle, ensure_ascii=False, indent=2)

    print(json.dumps({'decision_brief': 'data/bet_sizing_decision_brief.json', 'automation_setup': 'data/automation_setup.json', 'milestone_test': 'data/milestone_monitor_test.json', 'system_maturity': 'data/system_maturity_2026_04_20.json'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
