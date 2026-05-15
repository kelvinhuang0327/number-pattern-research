#!/usr/bin/env python3
"""
P1: Sum 反轉信號 → PP3 Sum 下界過濾回測
==========================================
來源: 115000018期檢討 — 前期 Sum≥145 → 下期 Sum≤110 比率=42.7% (基準~32%)

設計原則: L09 — Sum 信號做 portfolio constraint, 不做個號選擇
  正確做法: 在 PP3 bet3 的候選池 (12個) 中, 找最接近低 Sum 目標的組合
  錯誤做法: 直接選低頻率的低號碼 (會混淆信號)

觸發條件: prev_sum >= 145 (Power Lotto: 1889期中 ~13% 觸發)
目標: 當觸發時, bet3 的 sum <= 110 (或盡量接近中性低端)

基準:
  Power Lotto mean_sum ≈ 117, sigma ≈ 25.3
  觸發後 sum≤110 期望: 42.7% (vs 32% 基準, +10.7%)

測試: 150/500/1500 三窗口 + McNemar vs PP3_orig + Permutation Test
"""
import sys, os, json
import numpy as np
from collections import Counter
from itertools import combinations
from scipy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)

# Power Lotto sum 統計 (1-38 choose 6)
POWER_SUM_MEAN = 117.0
POWER_SUM_STD = 25.3
SUM_TRIGGER = 145    # 觸發門檻: 前期 Sum >= 145
SUM_TARGET_MAX = 110  # 目標: bet3 sum <= 110


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


def predict_pp3_original(history):
    """PP3 原版"""
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


def predict_pp3_sum_reversal(history):
    """PP3 + Sum 反轉: 當前期 prev_sum >= 145 時, bet3 優先低 sum 組合"""
    # 前期 sum
    if not history:
        return predict_pp3_original(history)
    prev_sum = sum(history[-1]['numbers'])
    triggered = (prev_sum >= SUM_TRIGGER)

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

    if not triggered:
        # 未觸發: 使用原始邏輯
        bet3 = sorted((echo_nums + remaining)[:6])
        return [bet1, bet2, bet3]

    # 觸發: 從候選池 (top-12) 中找 sum <= SUM_TARGET_MAX 的最佳組合
    candidates = (echo_nums + remaining)[:12]
    if len(candidates) < 6:
        candidates = (echo_nums + remaining)[:6]
        return [bet1, bet2, sorted(candidates)]

    # 枚舉 C(candidates, 6) 找符合 sum <= SUM_TARGET_MAX 的組合
    # 若無符合, 取 sum 最小的組合
    best_combo = None
    best_sum = float('inf')
    target_sum = SUM_TARGET_MAX  # 目標: ≤ 110

    for combo in combinations(candidates, 6):
        s = sum(combo)
        if s <= target_sum:
            # 在符合條件中找 sum 最接近目標中心 (95) 的
            dist = abs(s - 95)
            if best_combo is None or dist < best_sum:
                best_combo = combo
                best_sum = dist
        elif best_combo is None:
            # 備用: 找最小 sum
            if s < best_sum:
                best_combo = combo
                best_sum = s

    bet3 = sorted(best_combo)
    return [bet1, bet2, bet3]


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


def analyze_trigger_stats(draws):
    """分析觸發頻率和條件命中率"""
    trigger_count = 0
    trigger_actual_low_sum = 0
    all_actual_low_sum = 0
    for i in range(1, len(draws)):
        prev_sum = sum(draws[i-1]['numbers'])
        actual_sum = sum(draws[i]['numbers'])
        if prev_sum >= SUM_TRIGGER:
            trigger_count += 1
            if actual_sum <= 110:
                trigger_actual_low_sum += 1
        if actual_sum <= 110:
            all_actual_low_sum += 1
    total = len(draws) - 1
    overall_rate = all_actual_low_sum / total
    trigger_rate = trigger_actual_low_sum / trigger_count if trigger_count > 0 else 0
    return trigger_count, total, overall_rate, trigger_rate


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))

    print("=" * 70)
    print("  P1: Sum 反轉 PP3 Sum 下界過濾回測 (威力彩)")
    print(f"  N={len(draws)}期, seed={SEED}")
    print(f"  觸發: prev_sum >= {SUM_TRIGGER}, 目標: bet3 sum <= {SUM_TARGET_MAX}")
    print("=" * 70)

    # 分析觸發統計
    trig_cnt, total, overall_rate, trig_rate = analyze_trigger_stats(draws)
    print(f"\n[Sum 統計]")
    print(f"  Power Lotto 期望 sum={POWER_SUM_MEAN:.0f} ± {POWER_SUM_STD:.1f}")
    print(f"  觸發次數(sum≥{SUM_TRIGGER}): {trig_cnt}/{total} = {trig_cnt/total*100:.1f}%")
    print(f"  整體 sum≤110 比率: {overall_rate*100:.1f}%")
    print(f"  觸發後 sum≤110 比率: {trig_rate*100:.1f}% (報告值: 42.7%)")
    print(f"  實際信號增益: {(trig_rate - overall_rate)*100:+.1f}%")

    # 主回測
    strategies = [
        ("PP3_orig", predict_pp3_original),
        ("PP3_SumReversal", predict_pp3_sum_reversal),
    ]
    results = {}
    for name, predictor in strategies:
        print(f"\n[{name}]")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, predictor)
            edge, m3r, base = calc_edge(hits)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r, 'base': base}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%, M3+={m3r*100:.2f}% (base={base*100:.2f}%)")
        results[name] = row

    # McNemar
    print(f"\n[McNemar PP3_SumReversal vs PP3_orig (1500期)]:")
    h_orig = results['PP3_orig'][1500]['hits']
    h_sr = results['PP3_SumReversal'][1500]['hits']
    mc_p, mc_net, mc_disc = mcnemar_test(h_orig, h_sr)
    print(f"  SumReversal新增={max(0,mc_net)}, 損失={max(0,-mc_net)}, 差={mc_net:+d}")
    print(f"  McNemar p={mc_p:.4f} {'✓ 顯著' if mc_p < 0.05 else '✗ 不顯著'}")

    # Permutation Test
    print(f"\n[Permutation Test PP3_SumReversal (200次, 1500期)]...")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_pp3_sum_reversal, n_perm=200)
    signal_e = real_e - shuffle_mean
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle={shuffle_mean*100:.2f}%, Signal Edge={signal_e*100:.2f}%")
    verdict = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")

    e_orig_1500 = results['PP3_orig'][1500]['edge']
    e_sr_1500 = results['PP3_SumReversal'][1500]['edge']
    all_pos = all(results['PP3_SumReversal'][w]['edge'] > 0 for w in [150, 500, 1500])

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  PP3_orig:        1500p Edge={e_orig_1500*100:+.2f}%")
    print(f"  PP3_SumReversal: 150={results['PP3_SumReversal'][150]['edge']*100:+.2f}%, 500={results['PP3_SumReversal'][500]['edge']*100:+.2f}%, 1500={e_sr_1500*100:+.2f}%")
    print(f"  三窗口全正: {'PASS' if all_pos else 'FAIL'}")
    print(f"  Perm: {verdict} (p={perm_p:.4f})")
    print(f"  改善: {(e_sr_1500-e_orig_1500)*100:+.2f}%")
    print(f"  McNemar: net={mc_net:+d}, p={mc_p:.4f}")

    if perm_p <= 0.05 and all_pos and mc_p < 0.05:
        conclusion = "ADOPT: Sum反轉顯著改善PP3 → 更新PP3策略"
    elif perm_p <= 0.10 and e_sr_1500 > e_orig_1500:
        conclusion = "PROVISIONAL: 邊際改善, 監控200期"
    elif e_sr_1500 > e_orig_1500 and mc_net > 0:
        conclusion = "WEAK_SIGNAL: 輕微改善但不顯著, 保留觀察"
    else:
        conclusion = "REJECT: Sum反轉無法改善PP3 → L09確認(portfolio信號不可個別化)"

    print(f"\n  [結論] {conclusion}")

    out = {
        'strategy': 'pp3_sum_reversal_constraint',
        'draw_count': len(draws),
        'seed': SEED,
        'trigger_threshold': SUM_TRIGGER,
        'sum_target_max': SUM_TARGET_MAX,
        'trigger_stats': {
            'trigger_count': trig_cnt,
            'total': total,
            'trigger_rate_pct': trig_cnt/total*100,
            'overall_low_sum_rate': overall_rate,
            'triggered_low_sum_rate': trig_rate,
            'lift': trig_rate / overall_rate if overall_rate > 0 else 0
        },
        'results': {
            name: {w: {'edge': results[name][w]['edge'], 'm3r': results[name][w]['m3r']}
                   for w in [150, 500, 1500]}
            for name in results
        },
        'permutation': {'perm_p': perm_p, 'real_edge': real_e, 'shuffle_mean': shuffle_mean, 'signal_edge': signal_e, 'verdict': verdict},
        'mcnemar': {'net': mc_net, 'p': mc_p, 'n_discordant': mc_disc},
        'conclusion': conclusion
    }
    out_path = os.path.join(project_root, 'backtest_power_sum_reversal_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已保存: backtest_power_sum_reversal_results.json")


if __name__ == '__main__':
    main()
