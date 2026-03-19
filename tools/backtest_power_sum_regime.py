#!/usr/bin/env python3
"""
P0-B: Sum Regime Detector 回測
================================
偵測近30期Sum均值偏高/偏低 Regime，動態調整注3 Sum-Constraint目標。
高Sum Regime(均值>mu+0.3σ): 目標 [mu+0.2σ, mu+1.0σ]
低Sum Regime(均值<mu-0.3σ): 目標 [mu-1.0σ, mu-0.2σ]
中性Regime: 目標 [mu-0.5σ, mu+0.5σ] (現行)

比較: PP3 原版 vs PP3+SumRegime
"""
import sys, os, json, numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)


def get_fourier_rank(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 38
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf, pos_yf = xf[idx_pos], np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]


def get_sum_target(history, window_sum=500, regime_window=30):
    """根據近期Sum Regime計算目標範圍"""
    all_sums = [sum(d['numbers']) for d in history[-window_sum:]]
    mu = np.mean(all_sums)
    sigma = np.std(all_sums)

    recent_sums = [sum(d['numbers']) for d in history[-regime_window:]]
    recent_mu = np.mean(recent_sums)

    if recent_mu > mu + 0.3 * sigma:
        regime = 'HIGH'
        lo, hi = mu + 0.2 * sigma, mu + 1.0 * sigma
    elif recent_mu < mu - 0.3 * sigma:
        regime = 'LOW'
        lo, hi = mu - 1.0 * sigma, mu - 0.2 * sigma
    else:
        regime = 'NEUTRAL'
        lo, hi = mu - 0.5 * sigma, mu + 0.5 * sigma

    return lo, hi, regime, mu, sigma


def predict_pp3_original(history):
    f_rank = get_fourier_rank(history)
    f_valid = [n for n in f_rank if n != 0]
    bet1 = sorted(f_valid[:6])
    bet2 = sorted(f_valid[6:12])
    exclude = set(bet1) | set(bet2)
    echo = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = sorted([n for n in range(1, 39) if n not in exclude and n not in echo],
                       key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo + remaining)[:6])
    return [bet1, bet2, bet3]


def predict_pp3_sum_regime(history):
    """PP3 + Sum Regime: 注3加入Sum-Constraint基於Regime"""
    f_rank = get_fourier_rank(history)
    f_valid = [n for n in f_rank if n != 0]
    bet1 = sorted(f_valid[:6])
    bet2 = sorted(f_valid[6:12])
    exclude = set(bet1) | set(bet2)
    echo = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])

    remaining = [n for n in range(1, 39) if n not in exclude and n not in echo]
    remaining.sort(key=lambda x: freq100.get(x, 0))  # cold first

    candidates = echo + remaining  # all candidates for注3
    lo, hi, regime, mu, sigma = get_sum_target(history)

    # 嘗試找Sum落在目標範圍的最佳6號組合 (貪婪排序後sum過濾)
    # 策略: 從candidates前12個中選sum最接近目標中心的6個
    pool = candidates[:14]
    target_center = (lo + hi) / 2

    best_bet3 = None
    best_dist = float('inf')

    from itertools import combinations
    pool_small = pool[:12]
    for combo in combinations(pool_small, min(6, len(pool_small))):
        s = sum(combo)
        if lo <= s <= hi:
            dist = abs(s - target_center)
            if dist < best_dist:
                best_dist = dist
                best_bet3 = sorted(combo)

    if best_bet3 is None:
        # Fallback: 不限制sum，直接取前6
        best_bet3 = sorted(candidates[:6])

    return [bet1, bet2, best_bet3]


def count_hits(bets, actual):
    return max(len(set(b) & set(actual)) for b in bets)


def calc_edge(hits_list, single_p=0.0387, n_bets=3):
    baseline = 1 - (1 - single_p) ** n_bets
    m3r = sum(1 for h in hits_list if h >= 3) / len(hits_list)
    return m3r - baseline, m3r, baseline


def run_backtest(draws, window, predictor, min_history=100):
    hits = []
    start = max(min_history, len(draws) - window)
    for i in range(start, len(draws)):
        history = draws[:i]
        actual = draws[i]['numbers']
        try:
            bets = predictor(history)
            hits.append(count_hits(bets, actual))
        except Exception:
            hits.append(0)
    return hits


def permutation_test(draws, window, predictor, n_perm=200, seed=42):
    rng = np.random.default_rng(seed)
    real_hits = run_backtest(draws, window, predictor)
    real_edge, _, _ = calc_edge(real_hits)
    start = max(100, len(draws) - window)
    idxs = list(range(start, len(draws)))
    perm_edges = []
    for _ in range(n_perm):
        shuffled = [draws[i] for i in rng.permutation(len(draws))]
        perm_hits = []
        for i in idxs:
            history = shuffled[:i]
            if len(history) < 100:
                continue
            actual = shuffled[i]['numbers']
            try:
                bets = predictor(history)
                perm_hits.append(count_hits(bets, actual))
            except Exception:
                perm_hits.append(0)
        pe, _, _ = calc_edge(perm_hits)
        perm_edges.append(pe)
    perm_p = np.mean(np.array(perm_edges) >= real_edge)
    return perm_p, real_edge, np.mean(perm_edges)


def mcnemar_test(hits_a, hits_b):
    assert len(hits_a) == len(hits_b)
    a_only = sum(1 for a, b in zip(hits_a, hits_b) if a >= 3 and b < 3)
    b_only = sum(1 for a, b in zip(hits_a, hits_b) if b >= 3 and a < 3)
    net = a_only - b_only
    n = a_only + b_only
    if n == 0:
        return 1.0, 0, 0
    from scipy.stats import binom
    p = 2 * binom.cdf(min(a_only, b_only), n, 0.5)
    return p, net, n


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))

    print("=" * 70)
    print("  PP3 Sum Regime Detector 三窗口回測")
    print(f"  N={len(draws)}期, seed={SEED}")
    print("=" * 70)

    results = {}
    for name, predictor in [("PP3_orig", predict_pp3_original),
                             ("PP3_SumRegime", predict_pp3_sum_regime)]:
        print(f"\n[{name}]")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, predictor)
            edge, m3r, base = calc_edge(hits)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%, M3+={m3r*100:.2f}% (base={base*100:.2f}%)")
        results[name] = row

    # Regime分佈統計
    print(f"\n[Regime分佈(1500期)]:")
    regimes = []
    for i in range(max(100, len(draws)-1500), len(draws)):
        history = draws[:i]
        if len(history) < 100:
            continue
        _, _, regime, _, _ = get_sum_target(history)
        regimes.append(regime)
    from collections import Counter
    rc = Counter(regimes)
    for r, c in rc.items():
        print(f"  {r}: {c}期 = {c/len(regimes)*100:.1f}%")

    # McNemar
    hits_orig = run_backtest(draws, 1500, predict_pp3_original)
    hits_reg = run_backtest(draws, 1500, predict_pp3_sum_regime)
    n_min = min(len(hits_orig), len(hits_reg))
    mcn_p, net, n_disc = mcnemar_test(hits_orig[-n_min:], hits_reg[-n_min:])
    print(f"\n[McNemar SumRegime vs orig (1500期)]:")
    print(f"  SumRegime新增={max(0,net)}, 損失={max(0,-net)}, 差={net:+d}")
    print(f"  McNemar p={mcn_p:.4f} {'✓ 顯著' if mcn_p < 0.05 else '✗ 不顯著'}")

    # Perm
    print(f"\n[Permutation Test SumRegime (200次)...]")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_pp3_sum_regime, n_perm=200)
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle={shuffle_mean*100:.2f}%")

    e_150 = results["PP3_SumRegime"][150]['edge']
    e_500 = results["PP3_SumRegime"][500]['edge']
    e_1500 = results["PP3_SumRegime"][1500]['edge']
    o_1500 = results["PP3_orig"][1500]['edge']
    all_pos = e_150 > 0 and e_500 > 0 and e_1500 > 0
    verdict = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  PP3_orig:      150={results['PP3_orig'][150]['edge']*100:+.2f}%, 500={results['PP3_orig'][500]['edge']*100:+.2f}%, 1500={o_1500*100:+.2f}%")
    print(f"  PP3_SumRegime: 150={e_150*100:+.2f}%, 500={e_500*100:+.2f}%, 1500={e_1500*100:+.2f}%")
    print(f"  三窗口全正: {'PASS' if all_pos else 'FAIL'}")
    print(f"  Perm: {verdict} (p={perm_p:.4f})")
    print(f"  改善: {(e_1500-o_1500)*100:+.2f}%")

    out = {
        'strategy': 'PP3_sum_regime_detector',
        'draw_count': len(draws),
        'seed': SEED,
        'regime_dist': dict(rc),
        'windows': {
            'orig': {w: {'edge': results['PP3_orig'][w]['edge'], 'm3r': results['PP3_orig'][w]['m3r']} for w in [150,500,1500]},
            'regime': {w: {'edge': results['PP3_SumRegime'][w]['edge'], 'm3r': results['PP3_SumRegime'][w]['m3r']} for w in [150,500,1500]}
        },
        'perm_p': perm_p,
        'mcnemar_p': mcn_p,
        'mcnemar_net': net,
        'verdict': verdict,
        'three_window': 'PASS' if all_pos else 'FAIL',
        'improvement_1500p': e_1500 - o_1500
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest_power_sum_regime_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: {os.path.abspath(out_path)}")
    print("=" * 70)
    return out


if __name__ == "__main__":
    main()
