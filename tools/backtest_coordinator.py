"""
Coordinator 回測驗證
====================
對比 Coordinator vs 現有最佳單策略
- 今彩539: Coordinator(4agents) vs ACB+Markov+Fourier 3注
- 大樂透:  Coordinator(4agents) vs P1+Dev+Sum 5注
- 威力彩:  Coordinator(3agents) vs PP3 3注

回測規範（遵循 backtest-framework skill）:
  - Walk-forward OOS，嚴格時序隔離
  - 三窗口驗證 (150/500/1500期)
  - McNemar 對比現有冠軍
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))

import numpy as np
from collections import Counter
from itertools import combinations
from numpy.fft import fft, fftfreq
from database import DatabaseManager
from lottery_api.engine.strategy_coordinator import StrategyCoordinator

# ============================================================
# 回測基礎設施
# ============================================================
BASELINES = {
    'POWER_LOTTO': {3: 0.1117, 5: 0.1791},
    'BIG_LOTTO':   {3: 0.0549, 5: 0.0896},
    'DAILY_539':   {3: 0.3050},
}
METRIC = {
    'POWER_LOTTO': 'is_m3plus',
    'BIG_LOTTO':   'is_m3plus',
    'DAILY_539':   'is_m2plus',
}

def _metric_hit(bet_lists, actual, metric):
    actual_set = set(actual)
    best = max(len(set(b) & actual_set) for b in bet_lists)
    if metric == 'is_m3plus': return best >= 3
    return best >= 2

def _edge_stats(hits, n, baseline):
    rate = hits / n if n else 0
    edge = rate - baseline
    return {'n': n, 'hit': hits, 'rate': round(rate, 5), 'edge': round(edge, 5)}

def _mcnemar(a_hits, b_hits):
    """配對 McNemar 檢定 (a=coordinator, b=champion)"""
    a_only = sum(1 for a, b in zip(a_hits, b_hits) if a and not b)
    b_only = sum(1 for a, b in zip(a_hits, b_hits) if b and not a)
    n_disc = a_only + b_only
    if n_disc == 0:
        return {'a_only': 0, 'b_only': 0, 'chi2': 0, 'p': 1.0, 'winner': 'tie'}
    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_disc
    import scipy.stats as st
    p = 1 - st.chi2.cdf(chi2, df=1)
    winner = 'coordinator' if a_only > b_only else 'champion' if b_only > a_only else 'tie'
    return {'a_only': a_only, 'b_only': b_only, 'chi2': round(chi2, 3),
            'p': round(p, 4), 'winner': winner}

# ============================================================
# 現有冠軍策略（用於 McNemar 對比）
# ============================================================

def champion_539_3bet(history):
    """ACB+Markov+Fourier 3注"""
    from tools.quick_predict import _539_acb_bet, _539_markov_bet, _539_fourier_scores
    b1 = _539_acb_bet(history)
    b2 = _539_markov_bet(history, exclude=set(b1))
    excl = set(b1) | set(b2)
    sc = _539_fourier_scores(history)
    b3 = sorted([n for n in sorted(sc, key=lambda x: -sc[x]) if n not in excl][:5])
    return [b1, b2, b3]

def champion_bl_5bet(history):
    """P1+Dev+Sum 5注 (quick_predict)"""
    from tools.quick_predict import biglotto_p1_deviation_5bet
    bets = biglotto_p1_deviation_5bet(history)
    return [b['numbers'] for b in bets]

def champion_pl_3bet(history):
    """PP3 Power Precision"""
    from tools.predict_power_precision_3bet import generate_power_precision_3bet
    return generate_power_precision_3bet(history)

# ============================================================
# 單彩種回測
# ============================================================

def run_backtest(lottery_type, history, n_bets, champion_fn,
                 windows=(150, 500, 1500), weight_window=100):
    metric = METRIC[lottery_type]
    baseline = BASELINES[lottery_type].get(n_bets, 0.05)
    total = len(history)
    min_train = 150

    coord_hits_all, champ_hits_all = [], []

    for idx in range(min_train, total):
        train = history[:idx]
        actual = history[idx]['numbers']

        # Coordinator 預測
        try:
            coord = StrategyCoordinator(lottery_type, weight_window=weight_window)
            coord_bets = coord.predict(train, n_bets=n_bets)
            coord_hit = _metric_hit(coord_bets, actual, metric)
        except Exception:
            coord_hit = False

        # 冠軍預測
        try:
            champ_bets = champion_fn(train)
            champ_hit = _metric_hit(champ_bets, actual, metric)
        except Exception:
            champ_hit = False

        coord_hits_all.append(coord_hit)
        champ_hits_all.append(champ_hit)

    # 三窗口統計
    results = {'lottery_type': lottery_type, 'n_bets': n_bets,
               'baseline': baseline, 'total_oos': len(coord_hits_all)}
    for w in windows:
        c_w = coord_hits_all[-w:] if len(coord_hits_all) >= w else coord_hits_all
        ch_w = champ_hits_all[-w:] if len(champ_hits_all) >= w else champ_hits_all
        results[f'coord_{w}p'] = _edge_stats(sum(c_w), len(c_w), baseline)
        results[f'champ_{w}p'] = _edge_stats(sum(ch_w), len(ch_w), baseline)

    # McNemar (最後 1500 期)
    n = min(1500, len(coord_hits_all))
    results['mcnemar_1500p'] = _mcnemar(coord_hits_all[-n:], champ_hits_all[-n:])

    return results

# ============================================================
# 印出報告
# ============================================================

def print_report(results):
    lt = results['lottery_type']
    nb = results['n_bets']
    bl = results['baseline']
    print(f"\n{'='*68}")
    print(f"  {lt} — Coordinator {nb}注 vs 冠軍策略")
    print(f"  OOS 回測期數: {results['total_oos']}   Baseline: {bl*100:.2f}%")
    print(f"{'='*68}")
    print(f"  {'窗口':>6}  {'Coord Edge':>12}  {'Champ Edge':>12}  {'差':>8}")
    print(f"  {'-'*50}")
    for w in [150, 500, 1500]:
        co = results.get(f'coord_{w}p', {})
        ch = results.get(f'champ_{w}p', {})
        if not co:
            continue
        diff = co['edge'] - ch['edge']
        flag = '▲' if diff > 0.001 else ('▼' if diff < -0.001 else '→')
        print(f"  {w:>5}p  {co['edge']*100:>+10.2f}%  {ch['edge']*100:>+10.2f}%  {diff*100:>+6.2f}% {flag}")
    mc = results.get('mcnemar_1500p', {})
    print(f"\n  McNemar (1500p):")
    print(f"    Coordinator 獨贏: {mc.get('a_only',0)} 期")
    print(f"    冠軍 獨贏: {mc.get('b_only',0)} 期")
    print(f"    χ²={mc.get('chi2',0):.3f}  p={mc.get('p',1):.4f}  勝者: {mc.get('winner','?').upper()}")
    print(f"{'='*68}")


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('lottery', nargs='?', default='all',
                        choices=['all', '539', 'biglotto', 'power'])
    parser.add_argument('--windows', type=int, nargs='+', default=[150, 500, 1500])
    args = parser.parse_args()

    db = DatabaseManager(db_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'lottery_api', 'data', 'lottery_v2.db'))

    TASKS = {
        '539':      ('DAILY_539',   3, champion_539_3bet),
        'biglotto': ('BIG_LOTTO',   5, champion_bl_5bet),
        'power':    ('POWER_LOTTO', 3, champion_pl_3bet),
    }

    keys = list(TASKS.keys()) if args.lottery == 'all' else [args.lottery]
    all_results = {}

    for key in keys:
        lt, nb, champ_fn = TASKS[key]
        print(f"\n[{lt}] 載入歷史資料...", end=' ', flush=True)
        h = sorted(db.get_all_draws(lottery_type=lt), key=lambda x: (x['date'], x['draw']))
        print(f"{len(h)} 期")
        print(f"[{lt}] 執行回測（可能需要數分鐘）...", flush=True)
        res = run_backtest(lt, h, nb, champ_fn, windows=tuple(args.windows))
        all_results[key] = res
        print_report(res)

    # 存結果
    out_path = 'backtest_coordinator_results.json'
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n結果已存至 {out_path}")
