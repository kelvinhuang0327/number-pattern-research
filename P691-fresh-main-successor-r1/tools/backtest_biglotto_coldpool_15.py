#!/usr/bin/env python3
"""
回測 B: 冷號池擴大 12→15 對比

基於現行「P1+偏差互補+Sum 5注」策略 (1500p Edge +2.71%)
僅修改 bet2 (冷號+Sum注) 的 pool_size = 12 → 15
其餘 4注完全不變

評估框架:
  - Walk-forward (嚴格時間隔離)
  - 三窗口: 150 / 500 / 1500 期
  - 基準: 5注 M3+ baseline = 8.96%
  - McNemar 對比: pool=12 vs pool=15

理論依據:
  - pool=15 → C(15,6)=5005 組合 (vs pool=12 的 924 組合)
  - 031期 #28 (冷號pool rank4) 在 pool=12 + Sum約束下被排除
  - pool=15 擴大搜索空間，Sum合法組合包含更多強信號號碼
"""
import sys
import os
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

MAX_NUM = 49
PICK = 6
BASELINE_5BET = 8.96  # M3+ 5注基準
MIN_HISTORY = 300     # 需要300期做 Sum 統計


# ── 來自 quick_predict.py 的核心函數 ─────────────────────────────────

def _bl_fourier_scores(history, window=500):
    """所有號碼的 Fourier 週期分數"""
    from numpy.fft import fft, fftfreq
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, 50):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0.0
    return scores


def _bl_markov_scores(history, window=30):
    """Markov 轉移分數"""
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            if cn not in transitions:
                transitions[cn] = Counter()
            for nn in recent[i + 1]['numbers']:
                transitions[cn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    return scores


def _bl_cold_sum_fixed(history, exclude=None, pool_size=12):
    """冷號 + 固定 Sum 目標 [mu-0.5σ, mu+0.5σ] (v2 驗證版)"""
    exclude = exclude or set()
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    candidates = sorted(
        [n for n in range(1, 50) if n not in exclude],
        key=lambda x: freq.get(x, 0)
    )
    pool = candidates[:pool_size]
    sums = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums), np.std(sums)
    tlo, thi = mu - 0.5 * sg, mu + 0.5 * sg
    tmid = mu
    best, best_dist, best_in = None, float('inf'), False
    for combo in combinations(pool, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in or dist < best_dist):
            best, best_dist, best_in = combo, dist, True
        elif not in_range and not best_in and dist < best_dist:
            best, best_dist = combo, dist
    return sorted(best if best else pool[:6])


def _bl_dev_complement_2bet(history, exclude=None, window=50):
    """偏差互補 2注 (Hot + Cold)"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * 6 / 49
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    hot, cold = [], []
    for n in range(1, 50):
        if n in exclude:
            continue
        dev = freq.get(n, 0) - expected
        if dev > 1:
            hot.append((n, dev))
        elif dev < -1:
            cold.append((n, abs(dev)))
    hot.sort(key=lambda x: -x[1])
    cold.sort(key=lambda x: -x[1])
    bet1 = [n for n, _ in hot[:6]]
    used = set(bet1) | exclude
    if len(bet1) < 6:
        mid = sorted([n for n in range(1, 50) if n not in used],
                     key=lambda n: abs(freq.get(n, 0) - expected))
        for n in mid:
            if len(bet1) < 6:
                bet1.append(n); used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < 6:
            bet2.append(n); used.add(n)
    if len(bet2) < 6:
        for n in range(1, 50):
            if n not in used and len(bet2) < 6:
                bet2.append(n); used.add(n)
    return sorted(bet1[:6]), sorted(bet2[:6])


def _bl_bet5_sum_conditional(history, pool):
    """第5注: 剩餘號碼池 + 條件式 Sum 目標"""
    if len(pool) <= 6:
        return sorted(pool[:6])
    sums = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums), np.std(sums)
    last_s = sum(history[-1]['numbers'])
    if last_s < mu - 0.5 * sg:
        tlo, thi = mu, mu + sg
    elif last_s > mu + 0.5 * sg:
        tlo, thi = mu - sg, mu
    else:
        tlo, thi = mu - 0.5 * sg, mu + 0.5 * sg
    tmid = (tlo + thi) / 2.0
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    expected = len(history[-100:]) * 6 / 49
    pool_sorted = sorted(pool, key=lambda n: abs(freq.get(n, 0) - expected))
    pool_cand = pool_sorted[:18] if len(pool_sorted) > 18 else pool_sorted
    best, best_dist, best_in = None, float('inf'), False
    for combo in combinations(pool_cand, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in or dist < best_dist):
            best, best_dist, best_in = combo, dist, True
        elif not in_range and not best_in and dist < best_dist:
            best, best_dist = combo, dist
    return sorted(best if best else pool_cand[:6])


# ── 5注策略生成 (pool_size 可配置) ───────────────────────────────────

def generate_5bet(history, cold_pool_size=12):
    """生成5注選號 (cold pool_size 可配置)"""
    # 注1: 鄰域 + Fourier+Markov
    prev_nums = history[-1]['numbers']
    neighbor_pool = set()
    for n in prev_nums:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 49:
                neighbor_pool.add(nn)

    f_scores = _bl_fourier_scores(history, window=500)
    mk_scores = _bl_markov_scores(history, window=30)
    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_scores.values()) or 1
    scored = {n: f_scores.get(n, 0) / f_max + 0.5 * (mk_scores.get(n, 0) / mk_max)
              for n in neighbor_pool}
    ranked = sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)
    bet1 = sorted(ranked[:6])
    used = set(bet1)

    # 注2: 冷號 + 固定 Sum (pool_size 可配置)
    bet2 = _bl_cold_sum_fixed(history, exclude=used, pool_size=cold_pool_size)
    used.update(bet2)

    # 注3+4: 偏差互補 Hot + Cold
    bet3, bet4 = _bl_dev_complement_2bet(history, exclude=used)
    used.update(bet3)
    used.update(bet4)

    # 注5: 剩餘號碼 + 條件式 Sum
    pool = [n for n in range(1, 50) if n not in used]
    bet5 = _bl_bet5_sum_conditional(history, pool)

    return [
        sorted(bet1),
        sorted(bet2),
        sorted(bet3),
        sorted(bet4),
        sorted(bet5),
    ]


def count_m3plus_any(bets, actual):
    """5注中任意1注達到 M3+ 即計1次"""
    a_set = set(actual)
    for bet in bets:
        if len(set(bet) & a_set) >= 3:
            return True
    return False


def backtest_compare(draws, windows=None):
    """完整比較 pool=12 vs pool=15"""
    if windows is None:
        windows = [150, 500, 1500]

    results_12 = []
    results_15 = []

    print(f"  進行 walk-forward 回測 ({len(draws) - MIN_HISTORY} 期)...", end='', flush=True)

    for i in range(MIN_HISTORY, len(draws)):
        history = draws[:i]
        actual = draws[i]['numbers']

        bets12 = generate_5bet(history, cold_pool_size=12)
        bets15 = generate_5bet(history, cold_pool_size=15)

        hit12 = count_m3plus_any(bets12, actual)
        hit15 = count_m3plus_any(bets15, actual)

        results_12.append(hit12)
        results_15.append(hit15)

        if (i - MIN_HISTORY) % 200 == 0:
            print('.', end='', flush=True)

    print(' 完成\n')
    return results_12, results_15


def compute_stats(results, baseline_pct):
    """計算命中率、Edge、z、p"""
    total = len(results)
    hits = sum(results)
    rate = hits / total * 100 if total > 0 else 0
    edge = rate - baseline_pct
    p0 = baseline_pct / 100
    se = np.sqrt(p0 * (1 - p0) / total)
    z = (rate / 100 - p0) / se if se > 0 else 0
    from scipy import stats as sp
    p_val = 1 - sp.norm.cdf(z)
    return {'total': total, 'hits': hits, 'rate': rate, 'edge': edge, 'z': z, 'p': p_val}


def mcnemar_test(res12, res15):
    """McNemar 配對顯著性檢定"""
    from scipy import stats as sp
    n01 = sum(1 for a, b in zip(res12, res15) if (not a) and b)   # 12失敗 15成功
    n10 = sum(1 for a, b in zip(res12, res15) if a and (not b))   # 12成功 15失敗
    b, c = n10, n01  # McNemar 慣例: b=12獨有, c=15獨有
    net = c - b  # 正值=15更好

    # 連續性校正 McNemar
    if b + c == 0:
        chi2 = 0
        p = 1.0
    else:
        chi2 = (abs(b - c) - 1) ** 2 / (b + c) if b + c > 0 else 0
        p = 1 - sp.chi2.cdf(chi2, df=1)

    return {'b': b, 'c': c, 'net': net, 'chi2': chi2, 'p': p}


def main():
    print("=" * 70)
    print("  回測 B: 大樂透 冷號池 pool=12 vs pool=15 比較")
    print("  策略: P1+偏差互補+Sum 5注 (現行策略 Edge +2.71%)")
    print("  變動: bet2 cold_pool_size 12 → 15 (其餘4注不變)")
    print("=" * 70)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='BIG_LOTTO')
    draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    print(f"\n  資料庫: {len(draws)} 期大樂透開獎資料")
    print(f"  回測起點: 第 {MIN_HISTORY+1} 期 (需 {MIN_HISTORY} 期暖機)")
    print(f"  有效回測期數: {len(draws) - MIN_HISTORY} 期\n")

    res12, res15 = backtest_compare(draws)

    # ── 三窗口比較 ─────────────────────────────────────────────────────
    print("  三窗口結果比較:")
    print(f"  {'窗口':>8}  {'pool=12 M3+':>11}  {'Edge12':>8}  {'pool=15 M3+':>11}  {'Edge15':>8}  {'Δ':>6}")
    print("  " + "-" * 65)

    windows = [('150期', 150), ('500期', 500), ('1500期', 1500)]
    deltas = []

    for wname, wsz in windows:
        r12 = res12[-wsz:] if len(res12) >= wsz else res12
        r15 = res15[-wsz:] if len(res15) >= wsz else res15
        s12 = compute_stats(r12, BASELINE_5BET)
        s15 = compute_stats(r15, BASELINE_5BET)
        delta = s15['edge'] - s12['edge']
        deltas.append(delta)
        marker = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"  {wname:>8}  {s12['hits']:>4}/{s12['total']:>6}  {s12['edge']:>+7.2f}%  "
              f"{s15['hits']:>4}/{s15['total']:>6}  {s15['edge']:>+7.2f}%  {delta:>+5.2f}% {marker}")

    print("  " + "-" * 65)

    # ── McNemar 檢定 ───────────────────────────────────────────────────
    print("\n  McNemar 配對比較 (全回測期數):")
    mn = mcnemar_test(res12, res15)
    print(f"  pool=12 獨有命中 (b): {mn['b']} 期")
    print(f"  pool=15 獨有命中 (c): {mn['c']} 期")
    print(f"  net (c-b) = {mn['net']:+d} (正值=pool=15更好)")
    print(f"  McNemar χ²={mn['chi2']:.4f}  p={mn['p']:.4f}")

    # McNemar on 1500-period window
    r12_1500 = res12[-1500:] if len(res12) >= 1500 else res12
    r15_1500 = res15[-1500:] if len(res15) >= 1500 else res15
    mn1500 = mcnemar_test(r12_1500, r15_1500)
    print(f"\n  McNemar (最近1500期): b={mn1500['b']}, c={mn1500['c']}, "
          f"net={mn1500['net']:+d}, p={mn1500['p']:.4f}")

    # ── 詳細三窗口統計 ─────────────────────────────────────────────────
    print("\n  詳細統計 (1500期):")
    r12_1500_res = res12[-1500:] if len(res12) >= 1500 else res12
    r15_1500_res = res15[-1500:] if len(res15) >= 1500 else res15
    s12_1500 = compute_stats(r12_1500_res, BASELINE_5BET)
    s15_1500 = compute_stats(r15_1500_res, BASELINE_5BET)
    print(f"  pool=12: M3+={s12_1500['hits']}/{s12_1500['total']}  "
          f"命中率={s12_1500['rate']:.2f}%  Edge={s12_1500['edge']:+.2f}%  "
          f"z={s12_1500['z']:+.2f}  p={s12_1500['p']:.4f}")
    print(f"  pool=15: M3+={s15_1500['hits']}/{s15_1500['total']}  "
          f"命中率={s15_1500['rate']:.2f}%  Edge={s15_1500['edge']:+.2f}%  "
          f"z={s15_1500['z']:+.2f}  p={s15_1500['p']:.4f}")

    # ── 判斷 ────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)

    all_delta_positive = all(d > 0 for d in deltas)
    significant = mn1500['p'] < 0.05
    net_positive = mn['net'] > 0

    if significant and all_delta_positive:
        verdict = "ADOPT — McNemar p<0.05 且三窗口全部改善，採納 pool=15"
        action = "→ 更新 quick_predict.py _bl_cold_sum_fixed(pool_size=15)"
    elif all_delta_positive and not significant:
        verdict = "MARGINAL — 三窗口全部改善但 McNemar p≥0.05，維持 pool=12"
        action = "→ 不替換（未達 McNemar 顯著門檻），記錄為待觀察"
    elif net_positive and not all_delta_positive:
        verdict = "MIXED — 部分窗口改善但不一致，維持 pool=12"
        action = "→ 歸檔，不做策略更動"
    else:
        verdict = "REJECT — pool=15 表現不優於 pool=12，維持 pool=12"
        action = "→ 歸檔 rejected/coldpool15_biglotto.json"

    print(f"\n  結論: {verdict}")
    print(f"  {action}")

    # Δ 摘要
    print(f"\n  三窗口 Δ Edge: 150p={deltas[0]:+.2f}%  500p={deltas[1]:+.2f}%  1500p={deltas[2]:+.2f}%")
    print(f"  McNemar(1500期) net={mn1500['net']:+d}  p={mn1500['p']:.4f}")
    print("=" * 70)


if __name__ == '__main__':
    try:
        from scipy import stats
    except ImportError:
        print("需要 scipy: pip install scipy")
        sys.exit(1)
    main()
