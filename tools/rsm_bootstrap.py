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
    RollingStrategyMonitor, StrategyStateStore, BASELINES, METRIC_KEY, METRIC_LABEL
)

np.random.seed(42)

DB_PATH = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
DATA_DIR = os.path.join(project_root, 'data')


# ============================================================
# Strategy Definitions (inline to avoid circular import issues)
# ============================================================

def get_power_lotto_strategies_inline():
    """威力彩策略 — inline 定義 (2026-03-16 更新: 新增 MidFreq+Fourier 2/3注)"""
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_2bet_hedging import bet1_fourier30, bet2_markov30, diversify_bets
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
    from tools.power_midfreq_fourier import midfreq_fourier_2bet, midfreq_fourier_markov_3bet

    def fourier_2bet(history):
        return fourier_rhythm_predict(history, n_bets=2, window=500)

    def fourier_3bet(history):
        return fourier_rhythm_predict(history, n_bets=3, window=500)

    def hedging_2bet(history):
        b1 = bet1_fourier30(history)
        b2 = bet2_markov30(history)
        b1, b2 = diversify_bets(b1, b2, history, max_overlap=3)
        return [b1, b2]

    def pp3_freqort_4bet(history):
        return generate_orthogonal_5bet(history)[:4]

    def orthogonal_5bet(history):
        return generate_orthogonal_5bet(history)

    return [
        {'name': 'fourier_rhythm_2bet',    'predict_func': fourier_2bet,     'num_bets': 2},
        {'name': 'fourier_rhythm_3bet',    'predict_func': fourier_3bet,     'num_bets': 3},
        {'name': 'fourier30_markov30_2bet','predict_func': hedging_2bet,     'num_bets': 2},
        {'name': 'pp3_freqort_4bet',       'predict_func': pp3_freqort_4bet, 'num_bets': 4},
        {'name': 'orthogonal_5bet',        'predict_func': orthogonal_5bet,  'num_bets': 5},
        # ─── 2026-03-16 Cross-Game Transfer: MidFreq+Fourier (p=0.005) ───
        {'name': 'midfreq_fourier_2bet',   'predict_func': midfreq_fourier_2bet,        'num_bets': 2},
        {'name': 'midfreq_fourier_mk_3bet','predict_func': midfreq_fourier_markov_3bet, 'num_bets': 3},
    ]


def get_big_lotto_strategies_inline():
    """大樂透策略 — inline 定義 (2026-03-13 更新: 新增 TS3+Regime 3注/Regime 2注)"""
    from tools.predict_biglotto_triple_strike import (
        generate_triple_strike, fourier_rhythm_bet, cold_numbers_bet
    )
    from tools.predict_biglotto_regime import generate_ts3_regime, generate_regime_2bet
    from tools.predict_biglotto_deviation_2bet import deviation_complement_2bet
    from tools.predict_biglotto_echo_3bet import echo_aware_mixed_3bet
    from tools.backtest_biglotto_5bet_ts3markov import (
        generate_ts3_markov_4bet, generate_ts3_markov_freq_5bet
    )
    from tools.backtest_p0_p3_optimization import neighbor_cold_2bet
    from tools.backtest_p1_deviation_4bet import p1_deviation_4bet as _p1_dev_4bet
    from tools.quick_predict import biglotto_p1_deviation_5bet as _p1_dev_5bet

    def fourier_2bet(history):
        bet1 = fourier_rhythm_bet(history, window=500)
        bet2 = cold_numbers_bet(history, window=100, exclude=set(bet1))
        return [bet1, bet2]

    def regime_2bet(history):
        return generate_regime_2bet(history)

    def p1_neighbor_cold_2bet(history):
        return neighbor_cold_2bet(history, cold_window=100, cold_pool=12)

    def deviation_2bet(history):
        return deviation_complement_2bet(history)

    def ts3_regime_3bet(history):
        return generate_ts3_regime(history)

    def triple_strike_3bet(history):
        return generate_triple_strike(history)

    def echo_3bet(history):
        return echo_aware_mixed_3bet(history)

    def ts3_markov_4bet(history):
        return generate_ts3_markov_4bet(history, markov_window=30)

    def p1_deviation_4bet(history):
        return _p1_dev_4bet(history)

    def ts3_markov_freq_5bet(history):
        return generate_ts3_markov_freq_5bet(history, markov_window=30)

    def p1_dev_sum5bet(history):
        # biglotto_p1_deviation_5bet returns [{'numbers': [...]}, ...]; convert to [[...], ...]
        bets = _p1_dev_5bet(history)
        return [b['numbers'] for b in bets]

    return [
        # ─── 2注 ───
        {'name': 'fourier_rhythm_2bet',      'predict_func': fourier_2bet,       'num_bets': 2},
        {'name': 'p1_neighbor_cold_2bet',    'predict_func': p1_neighbor_cold_2bet, 'num_bets': 2},
        {'name': 'deviation_complement_2bet','predict_func': deviation_2bet,     'num_bets': 2},
        {'name': 'regime_2bet',              'predict_func': regime_2bet,        'num_bets': 2},
        # ─── 3注 ───
        {'name': 'ts3_regime_3bet',          'predict_func': ts3_regime_3bet,    'num_bets': 3},  # ★現行最佳
        {'name': 'triple_strike_3bet',       'predict_func': triple_strike_3bet, 'num_bets': 3},  # 歷史基線
        {'name': 'echo_aware_3bet',          'predict_func': echo_3bet,          'num_bets': 3},
        # ─── 4注 ───
        {'name': 'p1_deviation_4bet',        'predict_func': p1_deviation_4bet,  'num_bets': 4},
        {'name': 'ts3_markov_4bet_w30',      'predict_func': ts3_markov_4bet,    'num_bets': 4},  # SUPERSEDED
        # ─── 5注 ───
        {'name': 'p1_dev_sum5bet',           'predict_func': p1_dev_sum5bet,     'num_bets': 5},  # ★現行最佳
        {'name': 'ts3_markov_freq_5bet_w30', 'predict_func': ts3_markov_freq_5bet, 'num_bets': 5},  # SUPERSEDED
    ]


def get_daily_539_strategies_inline():
    """今彩539策略 — inline 定義 (2026-03-13 更新: 加入 F4Cold 3注/5注)"""
    from tools.quick_predict import (
        _539_acb_bet, _539_midfreq_bet, _539_markov_bet, _539_fourier_scores,
        enforce_tail_diversity
    )
    from tools.predict_539_5bet_f4cold import predict as f4cold_predict

    def acb_1bet(history):
        return [_539_acb_bet(history)]

    def midfreq_acb_2bet(history):
        bet1 = _539_midfreq_bet(history)
        bet2 = _539_acb_bet(history, exclude=set(bet1))
        return [bet1, bet2]

    def acb_markov_fourier_3bet(history):
        bet1 = _539_acb_bet(history)
        bet2 = _539_markov_bet(history, exclude=set(bet1))
        excl = set(bet1) | set(bet2)
        sc = _539_fourier_scores(history, window=500)
        f_ranked = [n for n in sorted(sc, key=lambda x: -sc[x]) if sc[n] > 0 and n not in excl]
        bet3 = sorted(f_ranked[:5])
        return [bet1, bet2, bet3]

    def acb_markov_midfreq_3bet(history):
        """RSM備選監控: ACB+Markov+MidFreq (150p更強，McNemar p=0.808等效)"""
        bet1 = _539_acb_bet(history)
        bet2 = _539_markov_bet(history, exclude=set(bet1))
        excl = set(bet1) | set(bet2)
        bet3 = _539_midfreq_bet(history, exclude=excl)
        return [bet1, bet2, bet3]

    def f4cold_3bet(history):
        bets = f4cold_predict(history)  # returns list[list[int]]
        return bets[:3]

    def f4cold_5bet(history):
        return f4cold_predict(history)

    return [
        # ─── 現行採納策略 ───
        {'name': 'acb_1bet',                'predict_func': acb_1bet,               'num_bets': 1},
        {'name': 'midfreq_acb_2bet',        'predict_func': midfreq_acb_2bet,       'num_bets': 2},
        {'name': 'acb_markov_fourier_3bet', 'predict_func': acb_markov_fourier_3bet,'num_bets': 3},
        # ─── RSM 備選監控 ───
        {'name': 'acb_markov_midfreq_3bet', 'predict_func': acb_markov_midfreq_3bet,'num_bets': 3},
        {'name': 'f4cold_3bet',             'predict_func': f4cold_3bet,            'num_bets': 3},  # PROVISIONAL
        {'name': 'f4cold_5bet',             'predict_func': f4cold_5bet,            'num_bets': 5},  # PROVISIONAL
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

    # 持久化策略狀態（含 Sharpe、trend 等）
    store = StrategyStateStore(lottery_type, data_dir=os.path.join(project_root, 'lottery_api', 'data'))
    updated_states = store.update_from_monitor(rsm, strategy_configs)
    print(f"  策略狀態已儲存: {len(updated_states)} 條 → strategy_states_{lottery_type}.json")

    return rsm


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rolling Strategy Monitor Bootstrap")
    parser.add_argument('--lottery', choices=['POWER_LOTTO', 'BIG_LOTTO', 'DAILY_539', 'ALL'],
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

    if args.lottery in ('DAILY_539', 'ALL'):
        configs = get_daily_539_strategies_inline()
        rsm = run_bootstrap_and_report('DAILY_539', configs, args.periods)
        results['DAILY_539'] = rsm

    # 總結
    print("\n" + "=" * 72)
    print("  === 總結 ===")
    print("=" * 72)

    for lt, rsm in results.items():
        metric_key = METRIC_KEY.get(lt, 'is_m3plus')
        metric_lbl = METRIC_LABEL.get(lt, 'M3+')
        print(f"\n  {lt} ({metric_lbl}):")
        strategies = rsm.tracker.get_all_strategy_names()
        for name in strategies:
            n = rsm.tracker.total_records(name)
            records = rsm.tracker.get_records(name)
            if not records:
                continue
            hit_total = sum(1 for r in records if r.get(metric_key, False))
            rate = hit_total / n if n > 0 else 0
            num_bets = records[0].get('num_bets', 1) if records else 1
            baseline = BASELINES.get(lt, {}).get(num_bets, 0)
            edge = rate - baseline
            print(f"    {name}: {n} 期, {metric_lbl} {hit_total} ({rate*100:.2f}%), Edge {edge*100:+.2f}%")


if __name__ == '__main__':
    main()
