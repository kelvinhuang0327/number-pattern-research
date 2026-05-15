#!/usr/bin/env python3
"""
Per-Agent Hit Tracking — 回溯分析
==================================
分析 Strategy Coordinator 中各 Agent 對最近 N 期開獎的個別貢獻。
用於校準 Agent 權重和識別信號品質差異。

2026-03-14 Created (P2-3 行動項目)
"""
import os, sys, json, time
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from lottery_api.engine.strategy_coordinator import StrategyCoordinator


def run_agent_tracking(lottery_type='DAILY_539', n_periods=100):
    """回溯分析各 Agent 對最近 N 期開獎的命中貢獻"""
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
    draws = [d for d in draws if d.get('numbers')]

    print(f"{'=' * 72}")
    print(f"  Per-Agent Hit Tracking: {lottery_type}")
    print(f"  Total draws: {len(draws)}, Analysis window: last {n_periods} draws")
    print(f"{'=' * 72}\n")

    max_num = 39 if lottery_type == 'DAILY_539' else 49 if lottery_type == 'BIG_LOTTO' else 38
    bet_size = 5 if lottery_type == 'DAILY_539' else 6

    coord = StrategyCoordinator(lottery_type)
    agent_names = list(coord.agents.keys())

    # Per-agent cumulative stats
    stats = {a: {'top5_hits': 0, 'top10_hits': 0, 'total': 0,
                 'rank_sum': 0, 'rank_count': 0} for a in agent_names}
    per_draw_records = []

    start_idx = max(100, len(draws) - n_periods)
    actual_periods = len(draws) - start_idx

    for idx in range(start_idx, len(draws)):
        hist = draws[:idx]
        actual = draws[idx]['numbers'][:bet_size]
        draw_id = draws[idx].get('draw', str(idx))

        analysis = coord.agent_hit_analysis(hist, actual)

        record = {'draw_id': draw_id, 'actual': actual, 'agents': {}}
        for agent_name, data in analysis.items():
            stats[agent_name]['top5_hits'] += data['top5_count']
            stats[agent_name]['top10_hits'] += data['top10_count']
            stats[agent_name]['total'] += 1
            for n, rank in data['rankings'].items():
                stats[agent_name]['rank_sum'] += rank
                stats[agent_name]['rank_count'] += 1
            record['agents'][agent_name] = {
                't5': data['top5_count'],
                't10': data['top10_count'],
            }
        per_draw_records.append(record)

        if (idx - start_idx + 1) % 20 == 0:
            print(f"  Progress: {idx - start_idx + 1}/{actual_periods}")

    # Summary
    print(f"\n{'=' * 72}")
    print(f"  Agent Performance Summary ({actual_periods} periods)")
    print(f"{'=' * 72}")
    print(f"\n  {'Agent':<20} {'Top5 Hits':>10} {'Top5 Rate':>10} {'Top10 Hits':>11} {'Top10 Rate':>11} {'Avg Rank':>9}")
    print(f"  {'─' * 72}")

    expected_top5 = bet_size * bet_size / max_num  # E[hits in top5]
    expected_top10 = bet_size * (bet_size * 2) / max_num  # E[hits in top10]

    agent_summary = {}
    for agent_name in agent_names:
        s = stats[agent_name]
        n = s['total']
        if n == 0: continue
        t5_rate = s['top5_hits'] / (n * bet_size) * 100
        t10_rate = s['top10_hits'] / (n * bet_size) * 100
        avg_rank = s['rank_sum'] / s['rank_count'] if s['rank_count'] > 0 else max_num / 2
        weight = coord._weights.get(agent_name, 0)

        # Edge over random
        random_t5_rate = bet_size / max_num * 100
        t5_edge = t5_rate - random_t5_rate

        print(f"  {agent_name:<20} {s['top5_hits']:>10} {t5_rate:>9.2f}% {s['top10_hits']:>11} {t10_rate:>10.2f}% {avg_rank:>9.1f}")

        agent_summary[agent_name] = {
            'top5_hits': s['top5_hits'],
            'top5_rate': round(t5_rate, 3),
            'top5_edge': round(t5_edge, 3),
            'top10_hits': s['top10_hits'],
            'top10_rate': round(t10_rate, 3),
            'avg_rank': round(avg_rank, 2),
            'current_weight': round(weight, 4),
            'periods': n,
        }

    print(f"\n  Random baseline: Top5 rate = {bet_size/max_num*100:.2f}%, Avg rank = {(max_num+1)/2:.1f}")

    # Recommendation
    print(f"\n  {'─' * 72}")
    print(f"  Weight Adjustment Recommendations:")
    best_agent = max(agent_summary, key=lambda a: agent_summary[a]['top5_edge'])
    worst_agent = min(agent_summary, key=lambda a: agent_summary[a]['top5_edge'])
    print(f"    Best signal:  {best_agent} (top5_edge={agent_summary[best_agent]['top5_edge']:+.2f}%)")
    print(f"    Worst signal: {worst_agent} (top5_edge={agent_summary[worst_agent]['top5_edge']:+.2f}%)")

    # Save results
    result = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'lottery_type': lottery_type,
        'n_periods': actual_periods,
        'total_draws': len(draws),
        'summary': agent_summary,
    }
    out_path = os.path.join(project_root, 'lottery_api', 'data', f'agent_tracking_{lottery_type}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2,
                  default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    print(f"\n  Results saved: {out_path}")

    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Per-Agent Hit Tracking")
    parser.add_argument('--lottery', default='DAILY_539',
                        choices=['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'])
    parser.add_argument('--periods', type=int, default=100,
                        help='Number of recent periods to analyze')
    args = parser.parse_args()

    run_agent_tracking(args.lottery, args.periods)
