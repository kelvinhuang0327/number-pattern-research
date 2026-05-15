#!/usr/bin/env python3
"""
P1-A: 5注正交注4 三域精化回測
================================
現行注4 = 頻率正交殘差 (pure freq ranking)
精化注4 = Fourier殘差 × Freq殘差 × gap<7 三域交集評分

本期驗證: 注4 FreqOrt 命中 {3,38}
目標: 精化後注4能否在保持{3,38}類型命中的同時提升整體Edge

方法:
  score4(n) = fourier_residual_rank(n) × freq_residual_rank(n) × gap_score(n)
  gap_score = 1/(gap+1) if gap<7 else 0.5
"""
import sys, os, json, numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)


def get_fourier_scores(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 38
    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
                bitstreams[n][idx] = 1
    scores = {}
    for n in range(1, max_num + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf, pos_yf = xf[idx_pos], np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def get_gap_map(history):
    gaps = {}
    for n in range(1, 39):
        for i in range(len(history)-1, -1, -1):
            if n in history[i]['numbers']:
                gaps[n] = len(history) - 1 - i
                break
        else:
            gaps[n] = len(history)
    return gaps


def predict_ort5_original(history):
    """原版5注正交: 注1+2 Fourier, 注3+4 FreqOrt, 注5 Cold"""
    f_scores = get_fourier_scores(history)
    f_ranked = sorted(range(1, 39), key=lambda x: -f_scores.get(x, 0))

    bet1 = sorted(f_ranked[:6])
    bet2 = sorted(f_ranked[6:12])
    used = set(bet1) | set(bet2)

    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    freq_ranked = sorted(range(1, 39), key=lambda x: -freq100.get(x, 0))

    remaining = [n for n in freq_ranked if n not in used]
    bet3 = sorted(remaining[:6])
    used |= set(bet3)

    remaining2 = [n for n in freq_ranked if n not in used]
    bet4 = sorted(remaining2[:6])
    used |= set(bet4)

    remaining3 = sorted([n for n in range(1, 39) if n not in used],
                        key=lambda x: freq100.get(x, 0))  # cold first
    bet5 = sorted(remaining3[:6])

    return [bet1, bet2, bet3, bet4, bet5]


def predict_ort5_refined(history):
    """精化5注正交: 注4用三域交集評分"""
    f_scores = get_fourier_scores(history)
    f_ranked = sorted(range(1, 39), key=lambda x: -f_scores.get(x, 0))

    bet1 = sorted(f_ranked[:6])
    bet2 = sorted(f_ranked[6:12])
    used = set(bet1) | set(bet2)

    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    freq_ranked = sorted(range(1, 39), key=lambda x: -freq100.get(x, 0))

    remaining = [n for n in freq_ranked if n not in used]
    bet3 = sorted(remaining[:6])
    used |= set(bet3)

    # 注4: 三域交集精化評分
    gaps = get_gap_map(history)
    all_nums = range(1, 39)
    # 殘差排名 (排除已用)
    f_residual = [n for n in f_ranked if n not in used]
    freq_residual = [n for n in freq_ranked if n not in used]

    def score4(n):
        if n in used:
            return -1
        f_rank = f_residual.index(n) + 1 if n in f_residual else 999
        freq_rank = freq_residual.index(n) + 1 if n in freq_residual else 999
        gap = gaps.get(n, 999)
        gap_score = 1.0 / (gap + 1) if gap < 7 else 0.3
        # 正規化排名: 越小越好 → 轉為越大越好
        f_norm = (len(f_residual) - f_rank + 1) / len(f_residual) if f_residual else 0
        fr_norm = (len(freq_residual) - freq_rank + 1) / len(freq_residual) if freq_residual else 0
        return f_norm * fr_norm * gap_score

    candidates4 = sorted([n for n in range(1, 39) if n not in used],
                          key=lambda x: -score4(x))
    bet4 = sorted(candidates4[:6])
    used |= set(bet4)

    remaining3 = sorted([n for n in range(1, 39) if n not in used],
                        key=lambda x: freq100.get(x, 0))
    bet5 = sorted(remaining3[:6])

    return [bet1, bet2, bet3, bet4, bet5]


def count_hits(bets, actual):
    return max(len(set(b) & set(actual)) for b in bets)


def calc_edge(hits_list, single_p=0.0387, n_bets=5):
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
    print("  5注正交 注4精化 (FreqOrt vs 三域交集) 回測")
    print(f"  N={len(draws)}期, seed={SEED}, n_bets=5")
    print("=" * 70)

    results = {}
    for name, predictor in [("Ort5_orig", predict_ort5_original),
                             ("Ort5_refined", predict_ort5_refined)]:
        print(f"\n[{name}]")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, predictor)
            edge, m3r, base = calc_edge(hits, n_bets=5)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r, 'base': base}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%, M3+={m3r*100:.2f}% (base={base*100:.2f}%)")
        results[name] = row

    # McNemar
    hits_orig = run_backtest(draws, 1500, predict_ort5_original)
    hits_ref = run_backtest(draws, 1500, predict_ort5_refined)
    n_min = min(len(hits_orig), len(hits_ref))
    mcn_p, net, n_disc = mcnemar_test(hits_orig[-n_min:], hits_ref[-n_min:])
    print(f"\n[McNemar refined vs orig (1500期)]:")
    print(f"  refined新增={max(0,net)}, 損失={max(0,-net)}, 差={net:+d}")
    print(f"  McNemar p={mcn_p:.4f} {'✓ 顯著' if mcn_p < 0.05 else '✗ 不顯著'}")

    # Perm test for refined
    print(f"\n[Permutation Test Ort5_refined (200次)...]")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_ort5_refined, n_perm=200)
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle={shuffle_mean*100:.2f}%")

    e_150 = results["Ort5_refined"][150]['edge']
    e_500 = results["Ort5_refined"][500]['edge']
    e_1500 = results["Ort5_refined"][1500]['edge']
    o_1500 = results["Ort5_orig"][1500]['edge']
    all_pos = e_150 > 0 and e_500 > 0 and e_1500 > 0
    verdict = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  Ort5_orig:     150={results['Ort5_orig'][150]['edge']*100:+.2f}%, 500={results['Ort5_orig'][500]['edge']*100:+.2f}%, 1500={o_1500*100:+.2f}%")
    print(f"  Ort5_refined:  150={e_150*100:+.2f}%, 500={e_500*100:+.2f}%, 1500={e_1500*100:+.2f}%")
    print(f"  三窗口全正: {'PASS' if all_pos else 'FAIL'}")
    print(f"  Perm: {verdict} (p={perm_p:.4f})")
    print(f"  改善: {(e_1500-o_1500)*100:+.2f}%")
    print(f"  McNemar: net={net:+d}, p={mcn_p:.4f}")

    out = {
        'strategy': 'ort5_bet4_three_domain_refinement',
        'draw_count': len(draws),
        'seed': SEED,
        'n_bets': 5,
        'windows': {
            'orig': {w: {'edge': results['Ort5_orig'][w]['edge'], 'm3r': results['Ort5_orig'][w]['m3r']} for w in [150,500,1500]},
            'refined': {w: {'edge': results['Ort5_refined'][w]['edge'], 'm3r': results['Ort5_refined'][w]['m3r']} for w in [150,500,1500]}
        },
        'perm_p': perm_p,
        'mcnemar_p': mcn_p,
        'mcnemar_net': net,
        'verdict': verdict,
        'three_window': 'PASS' if all_pos else 'FAIL',
        'improvement_1500p': e_1500 - o_1500
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest_power_ort5_refine_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: {os.path.abspath(out_path)}")
    print("=" * 70)
    return out


if __name__ == "__main__":
    main()
