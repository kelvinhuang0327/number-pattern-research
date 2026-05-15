#!/usr/bin/env python3
"""
P0: SHLC (Short-Hot Long-Cold) 中頻指標回測
============================================
來源: 115000018期檢討 — #11 在100期排名#5, 500期排名#34, 信號矛盾

SHLC = rank_500 / rank_100
  高SHLC = 長期冷但近期熱 (歷史中等但最近頻繁出現)
  閾值 > 3.0 的號碼視為「正在甦醒」的信號

測試項目:
  1. SHLC_1bet: SHLC Top-6 作為單注 (與隨機3.87%比較)
  2. PP3+SHLC: 用 SHLC Top-6 替換 PP3 注2 (Fourier 7-12)
              → 注1=Fourier 1-6, 注2=SHLC Top-6, 注3=Echo/Cold
  3. McNemar: PP3+SHLC vs PP3 原版

驗證: 150/500/1500期三窗口 + permutation test
Seed: 42
"""
import sys, os, json
import numpy as np
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


def get_shlc_scores(history, short_window=100, long_window=500):
    """
    SHLC = rank_long / rank_short
    高分 = 長期冷但近期熱 = 「正在甦醒」信號
    """
    max_num = 38
    # 短窗口頻率排名
    h_short = history[-short_window:] if len(history) >= short_window else history
    freq_short = Counter([n for d in h_short for n in d['numbers'] if n <= max_num])
    nums = list(range(1, max_num + 1))
    # rank_short: rank 1 = most frequent
    sorted_short = sorted(nums, key=lambda x: -freq_short.get(x, 0))
    rank_short = {n: i + 1 for i, n in enumerate(sorted_short)}

    # 長窗口頻率排名
    h_long = history[-long_window:] if len(history) >= long_window else history
    freq_long = Counter([n for d in h_long for n in d['numbers'] if n <= max_num])
    sorted_long = sorted(nums, key=lambda x: -freq_long.get(x, 0))
    rank_long = {n: i + 1 for i, n in enumerate(sorted_long)}

    # SHLC = rank_long / rank_short (高 = 近期升溫)
    shlc = {}
    for n in nums:
        rs = rank_short.get(n, max_num)
        rl = rank_long.get(n, max_num)
        shlc[n] = rl / rs  # > 3.0 = 歷史中等但近期熱

    return shlc


def predict_pp3_original(history):
    """PP3 原版: Fourier注1+2 + Echo/Cold注3"""
    f_scores = get_fourier_scores(history)
    f_ranked = sorted(range(1, 39), key=lambda x: -f_scores.get(x, 0))

    bet1 = sorted(f_ranked[:6])
    bet2 = sorted(f_ranked[6:12])
    exclude = set(bet1) | set(bet2)

    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]


def predict_pp3_shlc_bet2(history):
    """PP3 + SHLC: 用 SHLC Top-6 替換注2"""
    f_scores = get_fourier_scores(history)
    f_ranked = sorted(range(1, 39), key=lambda x: -f_scores.get(x, 0))
    bet1 = sorted(f_ranked[:6])
    exclude1 = set(bet1)

    # 注2: SHLC Top-6 (排除bet1)
    shlc = get_shlc_scores(history)
    shlc_ranked = sorted([n for n in range(1, 39) if n not in exclude1],
                         key=lambda x: -shlc.get(x, 0))
    bet2 = sorted(shlc_ranked[:6])
    exclude = exclude1 | set(bet2)

    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = [n for n in range(1, 39) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])
    return [bet1, bet2, bet3]


def predict_shlc_1bet(history):
    """SHLC Top-6 單注"""
    shlc = get_shlc_scores(history)
    ranked = sorted(range(1, 39), key=lambda x: -shlc.get(x, 0))
    return [sorted(ranked[:6])]


def count_hits(bets, actual):
    return max(len(set(b) & set(actual)) for b in bets)


def calc_edge(hits_list, single_p=0.0387, n_bets=1):
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


def permutation_test(draws, window, predictor, n_bets, n_perm=200, seed=42):
    rng = np.random.default_rng(seed)
    real_hits = run_backtest(draws, window, predictor)
    real_edge, _, _ = calc_edge(real_hits, n_bets=n_bets)
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
        pe, _, _ = calc_edge(perm_hits, n_bets=n_bets)
        perm_edges.append(pe)
    perm_p = np.mean(np.array(perm_edges) >= real_edge)
    return perm_p, real_edge, np.mean(perm_edges)


def mcnemar_test(hits_a, hits_b):
    n = min(len(hits_a), len(hits_b))
    hits_a, hits_b = hits_a[-n:], hits_b[-n:]
    a_only = sum(1 for a, b in zip(hits_a, hits_b) if a >= 3 and b < 3)
    b_only = sum(1 for a, b in zip(hits_a, hits_b) if b >= 3 and a < 3)
    net = a_only - b_only
    total_disc = a_only + b_only
    if total_disc == 0:
        return 1.0, 0, 0
    from scipy.stats import binom
    p = 2 * binom.cdf(min(a_only, b_only), total_disc, 0.5)
    return p, net, total_disc


def analyze_shlc_distribution(draws):
    """分析歷史資料中 SHLC > 3.0 的命中率"""
    shlc_hit = 0
    shlc_total = 0
    baseline_hit = 0
    baseline_total = 0
    start = 600
    for i in range(start, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        shlc = get_shlc_scores(history)
        high_shlc = [n for n in range(1, 39) if shlc.get(n, 0) > 3.0]
        for n in actual:
            baseline_total += 1
            if shlc.get(n, 0) > 3.0:
                shlc_hit += 1
        shlc_total += len(high_shlc) * 6  # expected coverage denominator
    return shlc_hit, shlc_total, baseline_total


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))

    print("=" * 70)
    print("  P0: SHLC 中頻指標回測 (威力彩)")
    print(f"  N={len(draws)}期, seed={SEED}")
    print("=" * 70)

    # --- SHLC 分布分析 ---
    print("\n[SHLC 信號分析 (最近1000期)] ...")
    shlc_hits = []
    random_hits = []
    for i in range(len(draws) - 1000, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        if len(history) < 600:
            continue
        shlc = get_shlc_scores(history)
        # 高SHLC候選 (top 10)
        top10 = sorted(range(1, 39), key=lambda x: -shlc.get(x, 0))[:10]
        shlc_hits.append(len(actual & set(top10)))
        # 隨機10個
        rng_tmp = np.random.default_rng(SEED + i)
        rand10 = list(rng_tmp.choice(38, 10, replace=False) + 1)
        random_hits.append(len(actual & set(rand10)))

    if shlc_hits:
        shlc_m2 = sum(1 for h in shlc_hits if h >= 2) / len(shlc_hits)
        rand_m2 = sum(1 for h in random_hits if h >= 2) / len(random_hits)
        shlc_avg = np.mean(shlc_hits)
        rand_avg = np.mean(random_hits)
        print(f"  SHLC Top-10 平均命中: {shlc_avg:.3f} | M2+率: {shlc_m2*100:.2f}%")
        print(f"  隨機 10個  平均命中: {rand_avg:.3f} | M2+率: {rand_m2*100:.2f}%")
        print(f"  SHLC信號增益: {(shlc_avg - rand_avg):.3f} ({'+' if shlc_avg >= rand_avg else ''}{(shlc_avg - rand_avg)/rand_avg*100:.1f}%)")

    # --- 主回測 ---
    strategies = [
        ("SHLC_1bet", predict_shlc_1bet, 1),
        ("PP3_orig", predict_pp3_original, 3),
        ("PP3+SHLC_bet2", predict_pp3_shlc_bet2, 3),
    ]

    results = {}
    for name, predictor, n_bets in strategies:
        print(f"\n[{name}] (n_bets={n_bets})")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, predictor)
            edge, m3r, base = calc_edge(hits, n_bets=n_bets)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r, 'base': base}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%, M3+={m3r*100:.2f}% (base={base*100:.2f}%)")
        results[name] = row

    # --- McNemar: PP3+SHLC vs PP3_orig ---
    print(f"\n[McNemar PP3+SHLC_bet2 vs PP3_orig (1500期)]:")
    h_orig = results['PP3_orig'][1500]['hits']
    h_shlc = results['PP3+SHLC_bet2'][1500]['hits']
    mc_p, mc_net, mc_disc = mcnemar_test(h_orig, h_shlc)
    print(f"  SHLC_bet2新增={max(0,mc_net)}, 損失={max(0,-mc_net)}, 差={mc_net:+d}")
    print(f"  McNemar p={mc_p:.4f} {'✓ 顯著' if mc_p < 0.05 else '✗ 不顯著'}")

    # --- Permutation Test for PP3+SHLC_bet2 ---
    print(f"\n[Permutation Test PP3+SHLC_bet2 (200次, 1500期)]...")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_pp3_shlc_bet2, 3, n_perm=200)
    signal_e = real_e - shuffle_mean
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle={shuffle_mean*100:.2f}%, Signal Edge={signal_e*100:.2f}%")
    verdict_shlc = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")

    # --- Permutation Test for SHLC_1bet ---
    print(f"\n[Permutation Test SHLC_1bet (200次, 1500期)]...")
    perm_p1, real_e1, shuffle1 = permutation_test(draws, 1500, predict_shlc_1bet, 1, n_perm=200)
    signal_e1 = real_e1 - shuffle1
    print(f"  Perm p={perm_p1:.4f}, real={real_e1*100:.2f}%, shuffle={shuffle1*100:.2f}%, Signal Edge={signal_e1*100:.2f}%")
    verdict_1bet = "SIGNAL_DETECTED" if perm_p1 <= 0.05 else ("MARGINAL" if perm_p1 <= 0.10 else "NO_SIGNAL")

    # --- 判定 ---
    e_orig_1500 = results['PP3_orig'][1500]['edge']
    e_shlc_1500 = results['PP3+SHLC_bet2'][1500]['edge']
    e_1bet_1500 = results['SHLC_1bet'][1500]['edge']
    all_pos_shlc = all(results['PP3+SHLC_bet2'][w]['edge'] > 0 for w in [150, 500, 1500])
    all_pos_1bet = all(results['SHLC_1bet'][w]['edge'] > 0 for w in [150, 500, 1500])

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  PP3_orig:      1500p Edge={e_orig_1500*100:+.2f}%")
    print(f"  PP3+SHLC:      150={results['PP3+SHLC_bet2'][150]['edge']*100:+.2f}%, 500={results['PP3+SHLC_bet2'][500]['edge']*100:+.2f}%, 1500={e_shlc_1500*100:+.2f}%")
    print(f"  SHLC_1bet:     150={results['SHLC_1bet'][150]['edge']*100:+.2f}%, 500={results['SHLC_1bet'][500]['edge']*100:+.2f}%, 1500={e_1bet_1500*100:+.2f}%")
    print(f"  PP3+SHLC 三窗口全正: {'PASS' if all_pos_shlc else 'FAIL'}")
    print(f"  SHLC_1bet 三窗口全正: {'PASS' if all_pos_1bet else 'FAIL'}")
    print(f"  PP3+SHLC Perm: {verdict_shlc} (p={perm_p:.4f})")
    print(f"  SHLC_1bet Perm: {verdict_1bet} (p={perm_p1:.4f})")
    print(f"  PP3+SHLC vs PP3_orig 改善: {(e_shlc_1500-e_orig_1500)*100:+.2f}%")
    print(f"  McNemar: net={mc_net:+d}, p={mc_p:.4f}")

    # --- 結論 ---
    if perm_p <= 0.05 and all_pos_shlc and mc_p < 0.05:
        conclusion = "ADOPT: PP3+SHLC顯著優於PP3原版 → 更新quick_predict.py"
    elif perm_p <= 0.10 and e_shlc_1500 > e_orig_1500:
        conclusion = "PROVISIONAL: PP3+SHLC邊際改善, 監控200期"
    elif perm_p1 <= 0.05 and all_pos_1bet:
        conclusion = "PARTIAL: SHLC_1bet獨立通過, PP3+SHLC組合待觀察"
    else:
        conclusion = "REJECT: SHLC信號不足, 歸檔"

    print(f"\n  [結論] {conclusion}")

    # 保存結果
    out = {
        'strategy': 'shlc_midfreq_indicator',
        'draw_count': len(draws),
        'seed': SEED,
        'shlc_definition': 'rank_500 / rank_100',
        'results': {
            name: {w: {'edge': results[name][w]['edge'], 'm3r': results[name][w]['m3r'], 'base': results[name][w]['base']}
                   for w in [150, 500, 1500]}
            for name in results
        },
        'permutation': {
            'PP3+SHLC_bet2': {'perm_p': perm_p, 'real_edge': real_e, 'shuffle_mean': shuffle_mean, 'signal_edge': signal_e, 'verdict': verdict_shlc},
            'SHLC_1bet': {'perm_p': perm_p1, 'real_edge': real_e1, 'shuffle_mean': shuffle1, 'signal_edge': signal_e1, 'verdict': verdict_1bet}
        },
        'mcnemar': {'net': mc_net, 'p': mc_p, 'n_discordant': mc_disc},
        'conclusion': conclusion
    }
    out_path = os.path.join(project_root, 'backtest_power_shlc_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已保存: backtest_power_shlc_results.json")


if __name__ == '__main__':
    main()
