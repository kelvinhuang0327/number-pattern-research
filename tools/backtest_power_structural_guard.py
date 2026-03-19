#!/usr/bin/env python3
"""
P3: 結構後處理過濾器 (Structural Zone Guard) 回測
====================================================
來源: 115000018期 — Z1(1-9) 有效號碼 #7,#9; Z4(30-38) 完全缺席
設計: 若 PP3 全部3注在某 Zone 均無覆蓋, 自動補入1個該 Zone 號碼

Zone 定義 (Power Lotto 1-38):
  Z1 = 1-9   (9 號)
  Z2 = 10-19 (10 號)
  Z3 = 20-29 (10 號)
  Z4 = 30-38  (9 號)

觸發條件: PP3 三注均無 Z1 號碼 (歷史概率 ~0.5-2%)
補充邏輯: 在 bet3 中, 替換得分最低的 1 個號碼為 Z1 中 Fourier 最高分

注意: 結構過濾可能損害信號品質 → 需完整回測確認不引入負 Edge
依 L27_C 教訓: 統計信號真實 ≠ 在現有框架下可操作

驗證: 150/500/1500 三窗口 + McNemar vs PP3_orig + Permutation Test
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

# Zone 定義
ZONES = {
    'Z1': list(range(1, 10)),    # 1-9
    'Z2': list(range(10, 20)),   # 10-19
    'Z3': list(range(20, 30)),   # 20-29
    'Z4': list(range(30, 39)),   # 30-38
}


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


def get_zone(n):
    for zone_name, nums in ZONES.items():
        if n in nums:
            return zone_name
    return 'UNKNOWN'


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


def apply_zone_guard(bets, f_scores, guard_zone='Z1'):
    """
    若所有注在 guard_zone 均無覆蓋, 在 bet3 中替換得分最低的數為 guard_zone 最高Fourier分
    返回 (modified_bets, triggered)
    """
    zone_nums = ZONES[guard_zone]
    # 檢查是否觸發
    all_bets_flat = set(n for b in bets for n in b)
    if any(n in all_bets_flat for n in zone_nums):
        return bets, False  # 已有覆蓋, 不觸發

    # 觸發: 從 guard_zone 中找 Fourier 最高分且未使用的
    available_zone_nums = [n for n in zone_nums if n not in all_bets_flat]
    if not available_zone_nums:
        return bets, False

    # 選 Fourier 最高的 Z1 候選
    best_zone_num = max(available_zone_nums, key=lambda x: f_scores.get(x, 0))

    # 在 bet3 中替換 Fourier 最低分的數
    bet3 = list(bets[2])
    worst_in_bet3 = min(bet3, key=lambda x: f_scores.get(x, 0))
    bet3.remove(worst_in_bet3)
    bet3.append(best_zone_num)
    bet3 = sorted(bet3)

    modified = [bets[0], bets[1], bet3]
    return modified, True


def predict_pp3_z1_guard(history):
    """PP3 + Z1 守護: 若三注均無 Z1(1-9), 在 bet3 注入1個 Z1"""
    f_scores = get_fourier_scores(history)
    bets = predict_pp3_original(history)
    modified_bets, _ = apply_zone_guard(bets, f_scores, guard_zone='Z1')
    return modified_bets


def predict_pp3_z1_z4_guard(history):
    """PP3 + Z1+Z4 雙守護: 若三注均無 Z1 或均無 Z4, 分別注入"""
    f_scores = get_fourier_scores(history)
    bets = predict_pp3_original(history)
    # Z1 守護
    bets, trig1 = apply_zone_guard(bets, f_scores, guard_zone='Z1')
    # Z4 守護 (在修改後的 bets 上繼續)
    bets, trig2 = apply_zone_guard(bets, f_scores, guard_zone='Z4')
    return bets


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
    """分析觸發頻率和觸發後的命中情況"""
    trigger_z1_count = 0
    trigger_z1_hit = 0
    trigger_z4_count = 0
    trigger_z4_hit = 0
    total = 0
    for i in range(100, len(draws)):
        history = draws[:i]
        actual = set(draws[i]['numbers'])
        total += 1
        try:
            bets = predict_pp3_original(history)
            all_flat = set(n for b in bets for n in b)
            # Z1 觸發
            if not any(n in all_flat for n in ZONES['Z1']):
                trigger_z1_count += 1
                if any(n in actual for n in ZONES['Z1']):
                    trigger_z1_hit += 1
            # Z4 觸發
            if not any(n in all_flat for n in ZONES['Z4']):
                trigger_z4_count += 1
                if any(n in actual for n in ZONES['Z4']):
                    trigger_z4_hit += 1
        except:
            pass

    return trigger_z1_count, trigger_z1_hit, trigger_z4_count, trigger_z4_hit, total


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))

    print("=" * 70)
    print("  P3: 結構後處理 Zone Guard 回測 (威力彩)")
    print(f"  N={len(draws)}期, seed={SEED}")
    print("=" * 70)

    # 觸發統計分析
    print("\n[觸發統計分析 (全資料)]...")
    tz1, tz1h, tz4, tz4h, total = analyze_trigger_stats(draws)
    print(f"  PP3 Z1(1-9) 完全缺席: {tz1}/{total} = {tz1/total*100:.2f}%")
    if tz1 > 0:
        actual_z1_rate = tz1h/tz1*100
        print(f"    → 觸發後實際有Z1的比率: {actual_z1_rate:.1f}%")
        hist_z1_rate = sum(1 for d in draws if any(n in ZONES['Z1'] for n in d['numbers'])) / len(draws) * 100
        print(f"    → 歷史整體Z1出現率: {hist_z1_rate:.1f}%")
    print(f"  PP3 Z4(30-38) 完全缺席: {tz4}/{total} = {tz4/total*100:.2f}%")
    if tz4 > 0:
        actual_z4_rate = tz4h/tz4*100
        print(f"    → 觸發後實際有Z4的比率: {actual_z4_rate:.1f}%")

    if tz1 < 5:
        print(f"\n  ⚠️  Z1 觸發次數僅 {tz1} 次, 樣本太少 → 結構守護影響極有限")

    # 主回測
    strategies = [
        ("PP3_orig",        predict_pp3_original),
        ("PP3_Z1guard",     predict_pp3_z1_guard),
        ("PP3_Z1Z4guard",   predict_pp3_z1_z4_guard),
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

    # McNemar 比較
    print(f"\n[McNemar PP3_Z1guard vs PP3_orig (1500期)]:")
    h_orig = results['PP3_orig'][1500]['hits']
    h_z1 = results['PP3_Z1guard'][1500]['hits']
    mc1_p, mc1_net, mc1_disc = mcnemar_test(h_orig, h_z1)
    print(f"  Z1guard新增={max(0,mc1_net)}, 損失={max(0,-mc1_net)}, 差={mc1_net:+d}")
    print(f"  McNemar p={mc1_p:.4f} {'✓ 顯著' if mc1_p < 0.05 else '✗ 不顯著'}")

    print(f"\n[McNemar PP3_Z1Z4guard vs PP3_orig (1500期)]:")
    h_z1z4 = results['PP3_Z1Z4guard'][1500]['hits']
    mc2_p, mc2_net, mc2_disc = mcnemar_test(h_orig, h_z1z4)
    print(f"  Z1Z4guard新增={max(0,mc2_net)}, 損失={max(0,-mc2_net)}, 差={mc2_net:+d}")
    print(f"  McNemar p={mc2_p:.4f} {'✓ 顯著' if mc2_p < 0.05 else '✗ 不顯著'}")

    # Permutation Test (Z1 guard 最有可能通過, 先測這個)
    print(f"\n[Permutation Test PP3_Z1guard (200次, 1500期)]...")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_pp3_z1_guard, n_perm=200)
    signal_e = real_e - shuffle_mean
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle={shuffle_mean*100:.2f}%, Signal Edge={signal_e*100:.2f}%")
    verdict = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")

    # 判定
    e_orig_1500 = results['PP3_orig'][1500]['edge']
    e_z1_1500 = results['PP3_Z1guard'][1500]['edge']
    all_pos = all(results['PP3_Z1guard'][w]['edge'] > 0 for w in [150, 500, 1500])

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  PP3_orig:     1500p Edge={e_orig_1500*100:+.2f}%")
    print(f"  PP3_Z1guard:  150={results['PP3_Z1guard'][150]['edge']*100:+.2f}%, 500={results['PP3_Z1guard'][500]['edge']*100:+.2f}%, 1500={e_z1_1500*100:+.2f}%")
    print(f"  三窗口全正: {'PASS' if all_pos else 'FAIL'}")
    print(f"  Perm: {verdict} (p={perm_p:.4f})")
    print(f"  改善: {(e_z1_1500-e_orig_1500)*100:+.2f}%")
    print(f"  Z1 觸發次數: {tz1} (影響規模小)")

    if perm_p <= 0.05 and all_pos and mc1_p < 0.05:
        conclusion = "ADOPT: Zone Guard顯著改善 → 更新PP3"
    elif e_z1_1500 > e_orig_1500 and mc1_net >= 0:
        conclusion = f"WEAK: 輕微改善(觸發{tz1}次), 效益有限; 若Z1觸發率<2%則不值得引入複雜度"
    else:
        conclusion = "REJECT: Zone Guard 損害信號品質 → 依L27_C教訓: 統計真實信號≠框架可操作"

    print(f"\n  [結論] {conclusion}")

    out = {
        'strategy': 'pp3_structural_zone_guard',
        'draw_count': len(draws),
        'seed': SEED,
        'trigger_stats': {
            'z1_trigger_count': tz1,
            'z1_trigger_rate_pct': tz1/total*100 if total > 0 else 0,
            'z1_trigger_hit_rate': tz1h/tz1 if tz1 > 0 else 0,
            'z4_trigger_count': tz4,
            'z4_trigger_rate_pct': tz4/total*100 if total > 0 else 0,
        },
        'results': {
            name: {w: {'edge': results[name][w]['edge'], 'm3r': results[name][w]['m3r']}
                   for w in [150, 500, 1500]}
            for name in results
        },
        'permutation': {'perm_p': perm_p, 'real_edge': real_e, 'shuffle_mean': shuffle_mean, 'signal_edge': signal_e, 'verdict': verdict},
        'mcnemar': {
            'z1guard_vs_orig': {'net': mc1_net, 'p': mc1_p},
            'z1z4guard_vs_orig': {'net': mc2_net, 'p': mc2_p}
        },
        'conclusion': conclusion
    }
    out_path = os.path.join(project_root, 'backtest_power_structural_guard_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已保存: backtest_power_structural_guard_results.json")


if __name__ == '__main__':
    main()
