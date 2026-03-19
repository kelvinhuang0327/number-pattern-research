#!/usr/bin/env python3
"""
P0-A: Echo lag-3 延伸回測
===========================
比較 PP3 原版(lag-2 echo) vs PP3-lag3(lag-2 ∪ lag-3 echo)
目標: 捕獲 115000017 #38 (出現在 lag-3 期 014=[2,6,19,33,36,38])

驗證標準:
  - 1500/500/150 三窗口 Edge > baseline
  - perm p < 0.05 (SIGNAL_DETECTED)
  - McNemar vs PP3原版顯著 p < 0.05
"""
import sys, os, json, numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq
pass  # binom_test removed in newer scipy, using binom.cdf instead

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


def predict_pp3_original(history):
    """PP3原版: lag-2 echo"""
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


def predict_pp3_lag3(history):
    """PP3 lag-3 延伸: lag-2 ∪ lag-3 echo"""
    f_rank = get_fourier_rank(history)
    f_valid = [n for n in f_rank if n != 0]
    bet1 = sorted(f_valid[:6])
    bet2 = sorted(f_valid[6:12])
    exclude = set(bet1) | set(bet2)

    # 延伸: lag-2 union lag-3
    echo_lag2 = set(n for n in history[-2]['numbers'] if n <= 38 and n not in exclude)
    echo_lag3 = set(n for n in history[-3]['numbers'] if n <= 38 and n not in exclude)
    echo_pool = sorted(echo_lag2 | echo_lag3)

    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = sorted([n for n in range(1, 39) if n not in exclude and n not in set(echo_pool)],
                       key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo_pool + remaining)[:6])
    return [bet1, bet2, bet3]


def count_hits(bets, actual):
    """最佳注命中數 (M3+ 判定)"""
    return max(len(set(b) & set(actual)) for b in bets)


def calc_edge(hits_list, n_bets=3, single_p=0.0387):
    """Edge = actual_rate - baseline"""
    baseline = 1 - (1 - single_p) ** n_bets
    m3_rate = sum(1 for h in hits_list if h >= 3) / len(hits_list)
    return m3_rate - baseline, m3_rate, baseline


def run_backtest(draws, window, predictor, min_history=3):
    hits = []
    start = max(min_history, len(draws) - window)
    for i in range(start, len(draws)):
        history = draws[:i]
        if len(history) < min_history:
            continue
        actual = draws[i]['numbers']
        bets = predictor(history)
        hits.append(count_hits(bets, actual))
    return hits


def permutation_test(draws, window, predictor, n_perm=200, seed=42):
    rng = np.random.default_rng(seed)
    real_hits = run_backtest(draws, window, predictor)
    real_edge, _, _ = calc_edge(real_hits)

    perm_edges = []
    start = max(3, len(draws) - window)
    idxs = list(range(start, len(draws)))

    for _ in range(n_perm):
        shuffled = [draws[i] for i in rng.permutation(len(draws))]
        perm_hits = []
        for i in idxs:
            history = shuffled[:i]
            if len(history) < 3:
                continue
            actual = shuffled[i]['numbers']
            bets = predictor(history)
            perm_hits.append(count_hits(bets, actual))
        pe, _, _ = calc_edge(perm_hits)
        perm_edges.append(pe)

    perm_p = np.mean(np.array(perm_edges) >= real_edge)
    return perm_p, real_edge, np.mean(perm_edges)


def mcnemar_test(hits_a, hits_b):
    """McNemar test: A vs B 哪個方法多命中"""
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
    print("  PP3 Echo lag-2 vs Echo lag-2∪lag-3 三窗口對比回測")
    print(f"  N={len(draws)}期, seed={SEED}")
    print("=" * 70)

    single_p = 0.0387  # 威力彩 M3+ baseline

    results = {}
    for name, predictor in [("PP3_orig(lag2)", predict_pp3_original),
                             ("PP3_lag3(lag2∪3)", predict_pp3_lag3)]:
        print(f"\n[{name}]")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, predictor)
            edge, m3r, base = calc_edge(hits, single_p=single_p)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r, 'base': base, 'n': len(hits)}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%, M3+={m3r*100:.2f}% vs base={base*100:.2f}%")
        results[name] = row

    # McNemar 比較 (1500期)
    hits_orig = run_backtest(draws, 1500, predict_pp3_original)
    hits_lag3 = run_backtest(draws, 1500, predict_pp3_lag3)
    n_min = min(len(hits_orig), len(hits_lag3))
    hits_orig = hits_orig[-n_min:]
    hits_lag3 = hits_lag3[-n_min:]
    mcn_p, net, n_disc = mcnemar_test(hits_orig, hits_lag3)
    print(f"\n[McNemar 1500期 lag3 vs orig]:")
    print(f"  lag3新增命中={max(0,net)}, lag3損失命中={max(0,-net)}, 差={net:+d}")
    print(f"  McNemar p={mcn_p:.4f} {'✓ 顯著' if mcn_p < 0.05 else '✗ 不顯著'}")

    # Permutation test (1500期)
    print(f"\n[Permutation Test lag3 (1500期, n=200)...]")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_pp3_lag3, n_perm=200)
    edge_150 = results["PP3_lag3(lag2∪3)"][150]['edge']
    edge_500 = results["PP3_lag3(lag2∪3)"][500]['edge']
    edge_1500 = results["PP3_lag3(lag2∪3)"][1500]['edge']
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle_mean={shuffle_mean*100:.2f}%")

    # 判定
    all_pos = edge_150 > 0 and edge_500 > 0 and edge_1500 > 0
    verdict = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")
    three_window = "PASS" if all_pos else "FAIL"

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  三窗口全正: {three_window} ({'+' if edge_150>0 else '-'}/{'+' if edge_500>0 else '-'}/{'+' if edge_1500>0 else '-'})")
    print(f"  Perm test:  {verdict} (p={perm_p:.4f})")
    print(f"  McNemar:    net={net:+d}, p={mcn_p:.4f}")

    orig_150 = results["PP3_orig(lag2)"][150]['edge']
    orig_500 = results["PP3_orig(lag2)"][500]['edge']
    orig_1500 = results["PP3_orig(lag2)"][1500]['edge']
    print(f"\n  PP3 orig:  150={orig_150*100:+.2f}%, 500={orig_500*100:+.2f}%, 1500={orig_1500*100:+.2f}%")
    print(f"  PP3 lag3:  150={edge_150*100:+.2f}%, 500={edge_500*100:+.2f}%, 1500={edge_1500*100:+.2f}%")
    improvement = edge_1500 - orig_1500
    print(f"  改善幅度(1500p): {improvement*100:+.2f}%")

    # 儲存結果
    out = {
        'strategy': 'PP3_echo_lag3_extension',
        'draw_count': len(draws),
        'seed': SEED,
        'windows': {
            'orig': {w: {'edge': results["PP3_orig(lag2)"][w]['edge'],
                         'm3r': results["PP3_orig(lag2)"][w]['m3r']} for w in [150, 500, 1500]},
            'lag3': {w: {'edge': results["PP3_lag3(lag2∪3)"][w]['edge'],
                         'm3r': results["PP3_lag3(lag2∪3)"][w]['m3r']} for w in [150, 500, 1500]}
        },
        'perm_p': perm_p,
        'mcnemar_p': mcn_p,
        'mcnemar_net': net,
        'verdict': verdict,
        'three_window': three_window,
        'improvement_1500p': improvement
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest_power_echo_lag3_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: {os.path.abspath(out_path)}")
    print("=" * 70)
    return out


if __name__ == "__main__":
    main()
