#!/usr/bin/env python3
"""
結構族群分類 + 1500期驗證
===========================
假設: 開獎號碼具有結構慣性 (sum/zone/parity 均值回歸)，
      可利用上期結構特徵預測下期號碼分佈偏好。

驗證流程:
  Phase 0: 實證測試
    - sum 自相關 + 均值回歸機率
    - zone 分布轉移 (Z1-heavy → 下期 Z3/Z2 修正？)
    - parity 轉移
    - 各信號 Lift 量化

  Phase 1: 結構感知號碼選取
    - 根據上期結構推算下期「偏好族群」
    - 在偏好族群中加強頻率選號
    - 注入 Triple Strike 的 Bet 2 (Cold) 或獨立新注

  Phase 2: 三窗口回測 (150/500/1500)
    - 對比: Triple Strike 3注 基準
    - 新策略: TS3 + 結構感知注4 (結構版 Markov)

基準:
  - 3注 baseline: 5.49%
  - 4注 baseline: 7.25%
  - TS3 1500p Edge: +1.04% (MEMORY)
  - TS3+Markov(w=30) 4注 1500p Edge: +1.30%

用法:
    python3 tools/backtest_structural_group.py
"""
import os, sys, time
import numpy as np
from collections import Counter, defaultdict
from scipy.fft import fft, fftfreq
from scipy import stats as scipy_stats

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
SEED = 42
P_SINGLE = 0.0186
BASELINES = {3: 1-(1-P_SINGLE)**3, 4: 1-(1-P_SINGLE)**4}
WINDOWS = [150, 500, 1500]
MIN_HISTORY = 150


# ──────────────────────────────────────────────
# 結構特徵提取
# ──────────────────────────────────────────────

def extract_features(numbers):
    """提取單期開獎的結構特徵。"""
    nums = sorted(numbers)
    s = sum(nums)
    z1 = sum(1 for n in nums if 1 <= n <= 16)
    z2 = sum(1 for n in nums if 17 <= n <= 32)
    z3 = sum(1 for n in nums if 33 <= n <= 49)
    odd = sum(1 for n in nums if n % 2 == 1)
    even = PICK - odd
    consec = sum(1 for i in range(len(nums)-1) if nums[i+1] - nums[i] == 1)
    small = sum(1 for n in nums if n <= 25)   # 1-25
    large = PICK - small                        # 26-49
    return {
        'sum': s, 'z1': z1, 'z2': z2, 'z3': z3,
        'odd': odd, 'even': even, 'consec': consec,
        'small': small, 'large': large,
    }


def sum_tier(s, low_thr, high_thr):
    """sum 分層: LOW / MID / HIGH"""
    if s < low_thr:
        return 'LOW'
    if s > high_thr:
        return 'HIGH'
    return 'MID'


def zone_tier(z1, z2, z3):
    """區段分層: Z1H(Z1≥3) / Z3H(Z3≥3) / BAL"""
    if z1 >= 3:
        return 'Z1H'
    if z3 >= 3:
        return 'Z3H'
    return 'BAL'


def parity_tier(odd):
    """奇偶分層: ODH(odd≥4) / EVH(even≥4) / BAL"""
    if odd >= 4:
        return 'ODH'
    if odd <= 2:
        return 'EVH'
    return 'BAL'


def classify_draw(feat, sum_low, sum_high):
    st = sum_tier(feat['sum'], sum_low, sum_high)
    zt = zone_tier(feat['z1'], feat['z2'], feat['z3'])
    pt = parity_tier(feat['odd'])
    return (st, zt, pt)


# ──────────────────────────────────────────────
# Phase 0: 實證測試
# ──────────────────────────────────────────────

def phase0_empirical(draws):
    """全面實證: sum/zone/parity 轉移機率 + Lift。"""
    sums = [sum(d['numbers']) for d in draws]
    mean_s = np.mean(sums)
    std_s  = np.std(sums)
    low_thr  = mean_s - 0.5 * std_s
    high_thr = mean_s + 0.5 * std_s

    feats = [extract_features(d['numbers']) for d in draws]
    groups = [classify_draw(f, low_thr, high_thr) for f in feats]

    print(f"  Sum: mean={mean_s:.1f}, std={std_s:.1f}")
    print(f"  低和門檻 < {low_thr:.1f}, 高和門檻 > {high_thr:.1f}")

    # ── Sum 均值回歸 ──
    print("\n  [Sum 均值回歸]")
    # P(sum > mean | prev sum < mean - 0.5σ)
    for label, cond in [
        ('P(next_sum>mean | cur LOW)',  lambda g: g[0] == 'LOW'),
        ('P(next_sum<mean | cur HIGH)', lambda g: g[0] == 'HIGH'),
        ('P(next_sum=MID  | cur MID)',  lambda g: g[0] == 'MID'),
    ]:
        trials = hits = 0
        for i in range(len(groups)-1):
            if cond(groups[i]):
                trials += 1
                ns = sums[i+1]
                if 'LOW' in label and ns > mean_s:
                    hits += 1
                elif 'HIGH' in label and ns < mean_s:
                    hits += 1
                elif 'MID' in label and groups[i+1][0] == 'MID':
                    hits += 1
        base_p = 1/3
        rate = hits/trials if trials else 0
        lift = rate / base_p
        z = (hits - trials*base_p) / np.sqrt(trials*base_p*(1-base_p)) if trials > 0 else 0
        print(f"    {label}: {hits}/{trials} = {rate*100:.1f}%  "
              f"Lift={lift:.3f}x  z={z:.2f}")

    # ── Zone 轉移 ──
    print("\n  [Zone 轉移]")
    for cur_z in ['Z1H', 'Z3H', 'BAL']:
        trans = Counter()
        total = 0
        for i in range(len(groups)-1):
            if groups[i][1] == cur_z:
                trans[groups[i+1][1]] += 1
                total += 1
        if total == 0:
            continue
        base_p = 1/3
        print(f"    After {cur_z} (n={total}):", end="")
        for nz in ['Z1H', 'BAL', 'Z3H']:
            r = trans.get(nz, 0)/total
            lift = r / base_p
            print(f"  →{nz}: {r*100:.0f}%(L={lift:.2f})", end="")
        print()

    # ── Parity 轉移 ──
    print("\n  [Parity 轉移]")
    for cur_p in ['ODH', 'EVH', 'BAL']:
        trans = Counter()
        total = 0
        for i in range(len(groups)-1):
            if groups[i][2] == cur_p:
                trans[groups[i+1][2]] += 1
                total += 1
        if total == 0:
            continue
        base_p = 1/3
        print(f"    After {cur_p} (n={total}):", end="")
        for np_ in ['ODH', 'BAL', 'EVH']:
            r = trans.get(np_, 0)/total
            lift = r / base_p
            print(f"  →{np_}: {r*100:.0f}%(L={lift:.2f})", end="")
        print()

    # ── 條件頻率 Lift: 在「後繼」結構中各號碼出現率 vs 整體 ──
    print("\n  [條件頻率 Lift: 前期為 LOW sum → 下期各號碼出現率]")
    baseline_freq = Counter(n for d in draws for n in d['numbers'])
    total_draws = len(draws)
    cond_freq = Counter()
    cond_total = 0
    for i in range(len(groups)-1):
        if groups[i][0] == 'LOW':   # 前期低和
            cond_freq.update(draws[i+1]['numbers'])
            cond_total += 1
    if cond_total > 0:
        baseline_rate = PICK / MAX_NUM
        # 找出 Lift 最高的號碼
        lifts = []
        for n in range(1, MAX_NUM+1):
            cr = cond_freq.get(n, 0) / cond_total
            bl = baseline_freq.get(n, 0) / total_draws
            if bl > 0:
                lifts.append((n, cr/bl))
        lifts.sort(key=lambda x: -x[1])
        top_lifts = lifts[:10]
        print(f"    條件樣本: {cond_total} 期 (前期低和)")
        print(f"    前10高Lift號碼: {[(n, f'{l:.2f}x') for n,l in top_lifts]}")
        max_lift = max(l for _, l in lifts)
        print(f"    最高 Lift: {max_lift:.3f}x")
        avg_lift = np.mean([l for _, l in lifts])
        top5_avg = np.mean([l for _, l in lifts[:5]])
        print(f"    平均 Lift: {avg_lift:.3f}x  Top-5平均: {top5_avg:.3f}x")

    print("\n  [條件頻率 Lift: 前期為 Z1H → 下期各號碼出現率]")
    cond_freq2 = Counter()
    cond_total2 = 0
    for i in range(len(groups)-1):
        if groups[i][1] == 'Z1H':
            cond_freq2.update(draws[i+1]['numbers'])
            cond_total2 += 1
    if cond_total2 > 0:
        lifts2 = []
        for n in range(1, MAX_NUM+1):
            cr = cond_freq2.get(n, 0) / cond_total2
            bl = baseline_freq.get(n, 0) / total_draws
            if bl > 0:
                lifts2.append((n, cr/bl))
        lifts2.sort(key=lambda x: -x[1])
        print(f"    條件樣本: {cond_total2} 期 (前期Z1重)")
        print(f"    前10高Lift號碼: {[(n, f'{l:.2f}x') for n,l in lifts2[:10]]}")
        max_l2 = max(l for _, l in lifts2)
        print(f"    最高 Lift: {max_l2:.3f}x  (需 > 1.3x 才有實用意義)")

    return mean_s, std_s, low_thr, high_thr


# ──────────────────────────────────────────────
# Triple Strike (原版)
# ──────────────────────────────────────────────

def fourier_rhythm_bet(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    bs = {n: np.zeros(w) for n in range(1, MAX_NUM+1)}
    for idx, d in enumerate(h):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bs[n][idx] = 1
    sc = np.zeros(MAX_NUM+1)
    for n in range(1, MAX_NUM+1):
        bh = bs[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        ip = np.where(xf > 0)
        pxf, pyf = xf[ip], np.abs(yf[ip])
        if len(pyf) == 0:
            continue
        fv = pxf[np.argmax(pyf)]
        if fv == 0:
            continue
        period = 1 / fv
        if 2 < period < w/2:
            lh = np.where(bh == 1)[0][-1]
            sc[n] = 1.0 / (abs((w-1-lh) - period) + 1.0)
    return sorted((np.argsort(sc[1:])[::-1]+1)[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    cands = [n for n in range(1, MAX_NUM+1) if n not in exclude]
    return sorted(sorted(cands, key=lambda x: freq.get(x, 0))[:6])


def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    tg = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM+1):
        if n not in exclude:
            tg[n%10].append((n, freq.get(n, 0)))
    for t in tg:
        tg[t].sort(key=lambda x: x[1], reverse=True)
    selected, avt = [], sorted([t for t in range(10) if tg[t]],
                                key=lambda t: tg[t][0][1] if tg[t] else 0, reverse=True)
    ig = {t: 0 for t in range(10)}
    while len(selected) < 6:
        added = False
        for tail in avt:
            if len(selected) >= 6:
                break
            if ig[tail] < len(tg[tail]):
                num, _ = tg[tail][ig[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                ig[tail] += 1
        if not added:
            break
    if len(selected) < 6:
        rem = [n for n in range(1, MAX_NUM+1) if n not in selected and n not in exclude]
        rem.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(rem[:6-len(selected)])
    return sorted(selected[:6])


def generate_triple_strike(history):
    b1 = fourier_rhythm_bet(history)
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = tail_balance_bet(history, exclude=set(b1)|set(b2))
    return [b1, b2, b3]


# ──────────────────────────────────────────────
# 結構感知注 (Structural Reversion Bet)
# ──────────────────────────────────────────────

def structural_reversion_bet(history, exclude=None, window=300,
                              sum_low_thr=None, sum_high_thr=None):
    """
    結構回歸注:
    1. 分析上期結構 (sum tier, zone tier, parity tier)
    2. 在歷史中找到同族群下一期出現的號碼條件頻率
    3. 選出條件頻率最高的號碼 (排除 exclude)

    原理: 若上期低和，下期傾向中/高和 → 偏好 Z2/Z3 及大號
    """
    exclude = exclude or set()
    if len(history) < 2:
        cands = [n for n in range(1, MAX_NUM+1) if n not in exclude]
        return sorted(cands[:PICK])

    # 動態計算 sum 門檻 (使用歷史窗口)
    h_win = history[-window:] if len(history) >= window else history
    win_sums = [sum(d['numbers']) for d in h_win]
    mu = np.mean(win_sums)
    sg = np.std(win_sums)
    sl = sum_low_thr  if sum_low_thr  is not None else mu - 0.5*sg
    sh = sum_high_thr if sum_high_thr is not None else mu + 0.5*sg

    # 上期結構
    last_feat = extract_features(history[-1]['numbers'])
    last_group = classify_draw(last_feat, sl, sh)
    last_st, last_zt, last_pt = last_group

    # 在 h_win 中找同結構的「下一期」出現頻率
    cond_freq = Counter()
    cond_count = 0
    for i in range(len(h_win)-1):
        f = extract_features(h_win[i]['numbers'])
        g = classify_draw(f, sl, sh)
        if g[0] == last_st and g[1] == last_zt:   # sum + zone 相同
            cond_freq.update(h_win[i+1]['numbers'])
            cond_count += 1

    if cond_count < 5:
        # 條件樣本不足，退回整體頻率
        cond_freq = Counter(n for d in h_win for n in d['numbers'])

    cands = [(n, cond_freq.get(n, 0)) for n in range(1, MAX_NUM+1)
             if n not in exclude]
    cands.sort(key=lambda x: -x[1])
    return sorted([n for n, _ in cands[:PICK]])


def generate_ts3_structural(history):
    """TS3 (3注) + 結構回歸注4 (4注)"""
    ts3 = generate_triple_strike(history)
    used = set(n for b in ts3 for n in b)
    b4 = structural_reversion_bet(history, exclude=used)
    return ts3 + [b4]


# ──────────────────────────────────────────────
# 結構感知 Bet 2 版本 (替換 cold_numbers_bet)
# ──────────────────────────────────────────────

def structural_cold_bet(history, exclude=None, window=200):
    """
    結構感知冷號注:
    根據上期結構找「後繼開獎」中的冷號 (條件頻率最低)。
    """
    exclude = exclude or set()
    if len(history) < 5:
        return cold_numbers_bet(history, exclude=exclude)

    h_win = history[-window:] if len(history) >= window else history
    win_sums = [sum(d['numbers']) for d in h_win]
    mu, sg = np.mean(win_sums), np.std(win_sums)
    sl, sh = mu - 0.5*sg, mu + 0.5*sg

    last_feat = extract_features(history[-1]['numbers'])
    last_group = classify_draw(last_feat, sl, sh)
    last_st, last_zt = last_group[0], last_group[1]

    cond_freq = Counter()
    cond_count = 0
    for i in range(len(h_win)-1):
        f = extract_features(h_win[i]['numbers'])
        g = classify_draw(f, sl, sh)
        if g[0] == last_st and g[1] == last_zt:
            cond_freq.update(h_win[i+1]['numbers'])
            cond_count += 1

    if cond_count < 5:
        return cold_numbers_bet(history, window=100, exclude=exclude)

    cands = [n for n in range(1, MAX_NUM+1) if n not in exclude]
    cands.sort(key=lambda x: cond_freq.get(x, 0))   # ascending: coldest first
    return sorted(cands[:PICK])


def generate_ts3_structural_cold(history):
    """TS3 但 Bet2 改為結構感知冷號"""
    b1 = fourier_rhythm_bet(history)
    b2 = structural_cold_bet(history, exclude=set(b1))
    b3 = tail_balance_bet(history, exclude=set(b1)|set(b2))
    return [b1, b2, b3]


# ──────────────────────────────────────────────
# 回測引擎
# ──────────────────────────────────────────────

def run_backtest(draws, strategy_func, n_bets, n_periods):
    np.random.seed(SEED)
    baseline = BASELINES.get(n_bets, BASELINES[4])
    start_idx = max(len(draws) - n_periods, MIN_HISTORY)
    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0
    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        bets = strategy_func(history)
        best = max((len(set(b) & target) for b in bets), default=0)
        if best >= 3:
            hits[min(best, 6)] += 1
        total += 1
    m3p = sum(hits.values())
    wr = m3p / total if total else 0
    return {'total': total, 'm3_plus': m3p, 'win_rate': wr, 'edge': wr - baseline,
            'baseline': baseline}


def classify_decay(e150, e500, e1500):
    if e1500 > 0 and e500 > 0 and e150 > 0:
        return "ROBUST" if abs(e150-e1500) < 0.6 else "MODERATE_DECAY"
    if e1500 > 0 and e150 <= 0:
        return "LATE_BLOOMER"
    if e1500 <= 0 and e150 > 0:
        return "SHORT_MOMENTUM"
    return "INEFFECTIVE"


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print(f"大樂透: {len(draws)} 期  ({draws[0]['date']} ~ {draws[-1]['date']})")

    # ══════════════════════════════════════════
    # Phase 0: 實證
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  Phase 0: 結構特徵實證分析")
    print("=" * 72)
    mean_s, std_s, low_thr, high_thr = phase0_empirical(draws)

    # ══════════════════════════════════════════
    # Phase 1: 基準回測
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  Phase 1: 基準 Triple Strike 3注")
    print("=" * 72)
    base3 = {}
    for w in WINDOWS:
        t0 = time.time()
        r = run_backtest(draws, generate_triple_strike, 3, w)
        base3[w] = r
        print(f"  {w:4d}期: M3+={r['m3_plus']:3d}/{r['total']:4d} "
              f"({r['win_rate']*100:.2f}%)  Edge={r['edge']*100:+.2f}%  ({time.time()-t0:.1f}s)")

    # ══════════════════════════════════════════
    # Phase 2: 結構感知注4 (TS3 + 結構回歸)
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  Phase 2: TS3 + 結構回歸注4 (4注)")
    print("=" * 72)
    sg_res4 = {}
    for w in WINDOWS:
        t0 = time.time()
        r = run_backtest(draws, generate_ts3_structural, 4, w)
        sg_res4[w] = r
        e3 = base3[w]['edge'] * 100
        e4 = r['edge'] * 100
        delta = e4 - BASELINES[4]*100
        marginal = r['m3_plus'] - base3[w]['m3_plus']
        print(f"  {w:4d}期: M3+={r['m3_plus']:3d}/{r['total']:4d} "
              f"({r['win_rate']*100:.2f}%)  Edge={e4:+.2f}%  "
              f"vs3注Δ={marginal:+d}hits  ({time.time()-t0:.1f}s)")

    # ══════════════════════════════════════════
    # Phase 3: 結構感知 Bet2 替換 (3注版)
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  Phase 3: 結構感知冷號 Bet2 替換 (3注)")
    print("=" * 72)
    sg_res3 = {}
    for w in WINDOWS:
        t0 = time.time()
        r = run_backtest(draws, generate_ts3_structural_cold, 3, w)
        sg_res3[w] = r
        e3 = base3[w]['edge'] * 100
        e_new = r['edge'] * 100
        delta = e_new - e3
        print(f"  {w:4d}期: M3+={r['m3_plus']:3d}/{r['total']:4d} "
              f"({r['win_rate']*100:.2f}%)  Edge={e_new:+.2f}%  "
              f"Δ(vs基準)={delta:+.2f}%  ({time.time()-t0:.1f}s)")

    # ══════════════════════════════════════════
    # Phase 4: 結論
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  Phase 4: 結果對比 + 決策")
    print("=" * 72)

    strategies = [
        ("TS3 原版 3注", base3, 3),
        ("TS3+結構注4 (4注)", sg_res4, 4),
        ("TS3結構Bet2 (3注)", sg_res3, 3),
    ]

    print(f"\n{'策略':<26} {'150p':>8} {'500p':>8} {'1500p':>8} {'三窗口':>6} {'模式'}")
    print("-" * 72)
    for name, res, nb in strategies:
        e = {w: res[w]['edge']*100 for w in WINDOWS}
        ap = "✓" if all(e[w] > 0 for w in WINDOWS) else " "
        mode = classify_decay(e[150], e[500], e[1500])
        print(f"  {name:<24} {e[150]:>+7.2f}% {e[500]:>+7.2f}% {e[1500]:>+7.2f}%   {ap:<6} {mode}")

    # 判決
    print("\n  [判決]")
    for name, res, nb in strategies[1:]:
        e_new = res[1500]['edge']*100
        e_base = base3[1500]['edge']*100 if nb == 3 else BASELINES[4]*100
        delta = res[1500]['edge']*100 - e_base
        all_pos = all(res[w]['edge'] > 0 for w in WINDOWS)
        mode = classify_decay(
            res[150]['edge']*100, res[500]['edge']*100, res[1500]['edge']*100
        )

        if e_new > e_base + 0.10 and all_pos:
            verdict = "✅ 採納建議"
        elif e_new > e_base:
            verdict = "⚠️  微改善 (< 0.10%)，不顯著"
        else:
            verdict = "❌ 拒絕"

        print(f"  {name}: 1500p Edge={e_new:+.2f}%  Δ={delta:+.2f}%  {mode}  → {verdict}")

    print("=" * 72)


if __name__ == '__main__':
    main()
