#!/usr/bin/env python3
"""
Rolling Strategy Monitor — Bootstrap & Validation
===================================================
對威力彩和大樂透的已驗證策略進行 300 期滾動式回測，
產出 30/100/300 期三窗口報告 + 趨勢分類。

Anti-leakage: history = draws[:idx] (嚴格時序隔離)
Seed: 42

2026-02-10 Created
"""
import os
import sys
import time
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.engine.rolling_strategy_monitor import (
    RollingStrategyMonitor, BASELINES
)

np.random.seed(42)

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
DATA_DIR = os.path.join(project_root, 'data')


# ============================================================
# Strategy Definitions (inline to avoid circular import issues)
# ============================================================

def get_power_lotto_strategies_inline():
    """威力彩策略 — inline 定義"""
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_2bet_hedging import bet1_fourier30, bet2_markov30, diversify_bets

    def fourier_2bet(history):
        return fourier_rhythm_predict(history, n_bets=2, window=500)

    def fourier_3bet(history):
        return fourier_rhythm_predict(history, n_bets=3, window=500)

    def hedging_2bet(history):
        b1 = bet1_fourier30(history)
        b2 = bet2_markov30(history)
        b1, b2 = diversify_bets(b1, b2, history, max_overlap=3)
        return [b1, b2]

    return [
        {'name': 'fourier_rhythm_2bet', 'predict_func': fourier_2bet, 'num_bets': 2},
        {'name': 'fourier_rhythm_3bet', 'predict_func': fourier_3bet, 'num_bets': 3},
        {'name': 'fourier30_markov30_2bet', 'predict_func': hedging_2bet, 'num_bets': 2},
    ]


def get_big_lotto_strategies_inline():
    """大樂透策略 — inline 定義"""
    from tools.predict_biglotto_triple_strike import (
        generate_triple_strike, fourier_rhythm_bet, cold_numbers_bet
    )
    from tools.predict_biglotto_deviation_2bet import deviation_complement_2bet
    from tools.predict_biglotto_echo_3bet import echo_aware_mixed_3bet

    def fourier_2bet(history):
        bet1 = fourier_rhythm_bet(history, window=500)
        bet2 = cold_numbers_bet(history, window=100, exclude=set(bet1))
        return [bet1, bet2]

    def triple_strike_3bet(history):
        return generate_triple_strike(history)

    def deviation_2bet(history):
        return deviation_complement_2bet(history)

    def echo_3bet(history):
        return echo_aware_mixed_3bet(history)

    return [
        {'name': 'fourier_rhythm_2bet', 'predict_func': fourier_2bet, 'num_bets': 2},
        {'name': 'deviation_complement_2bet', 'predict_func': deviation_2bet, 'num_bets': 2},
        {'name': 'triple_strike_3bet', 'predict_func': triple_strike_3bet, 'num_bets': 3},
        {'name': 'echo_aware_3bet', 'predict_func': echo_3bet, 'num_bets': 3},
    ]


# ============================================================
# Main
# ============================================================

def run_bootstrap_and_report(lottery_type, strategy_configs, n_periods=300):
    """Bootstrap + 產出三窗口報告"""
    print(f"\n{'=' * 72}")
    print(f"  {lottery_type} — Rolling Strategy Monitor")
    print(f"{'=' * 72}")

    db = DatabaseManager(DB_PATH)
    draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
    print(f"  資料庫: {len(draws)} 期")

    # 建立 RSM
    rsm = RollingStrategyMonitor(lottery_type, data_dir=DATA_DIR)

    # Bootstrap
    t0 = time.time()
    rsm.bootstrap(draws, strategy_configs, n_periods=n_periods, seed=42, verbose=True)
    elapsed = time.time() - t0
    print(f"  Bootstrap 耗時: {elapsed:.1f}s")

    # 報告
    rsm.print_report(strategy_configs)

    return rsm


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rolling Strategy Monitor Bootstrap")
    parser.add_argument('--lottery', choices=['POWER_LOTTO', 'BIG_LOTTO', 'ALL'],
                        default='ALL', help='彩種')
    parser.add_argument('--periods', type=int, default=300, help='Bootstrap 期數')
    args = parser.parse_args()

    results = {}

    if args.lottery in ('POWER_LOTTO', 'ALL'):
        configs = get_power_lotto_strategies_inline()
        rsm = run_bootstrap_and_report('POWER_LOTTO', configs, args.periods)
        results['POWER_LOTTO'] = rsm

    if args.lottery in ('BIG_LOTTO', 'ALL'):
        configs = get_big_lotto_strategies_inline()
        rsm = run_bootstrap_and_report('BIG_LOTTO', configs, args.periods)
        results['BIG_LOTTO'] = rsm

    # 總結
    print("\n" + "=" * 72)
    print("  === 總結 ===")
    print("=" * 72)

    for lt, rsm in results.items():
        print(f"\n  {lt}:")
        strategies = rsm.tracker.get_all_strategy_names()
        for name in strategies:
            n = rsm.tracker.total_records(name)
            records = rsm.tracker.get_records(name)
            if not records:
                continue
            m3_total = sum(1 for r in records if r.get('is_m3plus', False))
            rate = m3_total / n if n > 0 else 0
            num_bets = records[0].get('num_bets', 1) if records else 1
            baseline = BASELINES.get(lt, {}).get(num_bets, 0)
            edge = rate - baseline
            print(f"    {name}: {n} 期, M3+ {m3_total} ({rate*100:.2f}%), Edge {edge*100:+.2f}%")


if __name__ == '__main__':
    main()
