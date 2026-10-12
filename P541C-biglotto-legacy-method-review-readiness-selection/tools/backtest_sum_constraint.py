#!/usr/bin/env python3
"""
Portfolio Sum-Range Constraint — 1500期驗證
============================================
核心設計：
  不在個號層面做條件頻率篩選，而在「注組合層面」
  利用 sum 均值回歸信號 (Lift=1.495x, z=8.93) 引導最終選號。

機制：
  1. 根據前期 sum 分層 → 預測下期 sum 目標範圍
     - 前期 LOW  (sum < mean-0.5σ) → 下期目標: [mean, mean+σ]
     - 前期 HIGH (sum > mean+0.5σ) → 下期目標: [mean-σ, mean]
     - 前期 MID                    → 下期目標: [mean-0.5σ, mean+0.5σ]

  2. 每注先生成 top-k 候選池（保留原始信號強度排序）
  3. 從候選池中枚舉 C(k,6) 組合，選出 sum 最接近目標中點的組合

  Triple Strike 完整流程（保留正交原則）：
    Bet1 pool → sum-select → bet1_set
    Bet2 pool (exclude bet1_set) → sum-select → bet2_set
    Bet3 pool (exclude bet1_set+bet2_set) → sum-select → bet3_set

Grid Search：
  pool_size = [8, 10, 12, 15]
  apply_to  = ["all", "bet2_only", "bet1_only"]

基準：Triple Strike 3注 (1500p Edge +1.06%)

用法：
    python3 tools/backtest_sum_constraint.py
"""
import os, sys, time
import numpy as np
from collections import Counter
from itertools import combinations as icombs
from scipy.fft import fft, fftfreq

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
SUM_WIN = 300          # 用於計算動態 mean/std 的歷史窗口


# ──────────────────────────────────────────────
# Sum 目標範圍計算
# ──────────────────────────────────────────────

def compute_sum_target(history, window=SUM_WIN):
    """
    根據前期 sum 層級，計算下期預期 sum 目標範圍。
    返回 (target_low, target_high, tier)。
    """
    h = history[-window:] if len(history) >= window else history
    sums = [sum(d['numbers']) for d in h]
    mu  = np.mean(sums)
    sg  = np.std(sums)

    last_sum = sum(history[-1]['numbers'])

    if last_sum < mu - 0.5 * sg:      # LOW
        tlo, thi, tier = mu,            mu + sg,         'LOW'
    elif last_sum > mu + 0.5 * sg:    # HIGH
        tlo, thi, tier = mu - sg,       mu,              'HIGH'
    else:                              # MID
        tlo, thi, tier = mu - 0.5*sg,  mu + 0.5*sg,     'MID'

    return tlo, thi, tier


# ──────────────────────────────────────────────
# 組合 Sum 選取（從 pool 中枚舉找最接近的）
# ──────────────────────────────────────────────

def sum_select_from_pool(pool, target_low, target_high, n=6):
    """
    從 pool 中選 n 個號碼，使其 sum 最接近 [target_low, target_high] 中點。
    若無法完全落在範圍內，選距中點最近的組合。
    C(|pool|, 6): 8→28, 10→210, 12→924, 15→5005
    """
    pool = list(pool)
    if len(pool) < n:
        return sorted(pool)

    target_mid = (target_low + target_high) / 2.0
    best_combo = None
    best_dist  = float('inf')
    best_in_range = False

    for combo in icombs(pool, n):
        s = sum(combo)
        in_range = (target_low <= s <= target_high)
        dist = abs(s - target_mid)

        # 優先落在範圍內；同樣在範圍內則選最近中點
        if in_range and (not best_in_range or dist < best_dist):
            best_combo, best_dist, best_in_range = combo, dist, True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo, best_dist = combo, dist

    return sorted(best_combo) if best_combo else sorted(pool[:n])


# ──────────────────────────────────────────────
# 原始信號生成（取 top-k pool）
# ──────────────────────────────────────────────

def fourier_pool(history, window=500, pool_size=12):
    """Fourier Rhythm: top pool_size 候選 (FFT 分數最高)"""
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
    ranked = (np.argsort(sc[1:])[::-1]+1).tolist()
    return ranked[:pool_size]


def cold_pool(history, window=100, exclude=None, pool_size=12):
    """Cold Numbers: pool_size 個最冷號碼候選"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    cands = [n for n in range(1, MAX_NUM+1) if n not in exclude]
    return sorted(cands, key=lambda x: freq.get(x, 0))[:pool_size]


def tail_pool(history, window=100, exclude=None, pool_size=12):
    """Tail Balance: pool_size 個候選 (尾數均衡優先)"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    tg = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM+1):
        if n not in exclude:
            tg[n%10].append((n, freq.get(n, 0)))
    for t in tg:
        tg[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    avt = sorted([t for t in range(10) if tg[t]],
                  key=lambda t: tg[t][0][1] if tg[t] else 0, reverse=True)
    ig = {t: 0 for t in range(10)}
    while len(selected) < pool_size:
        added = False
        for tail in avt:
            if len(selected) >= pool_size:
                break
            if ig[tail] < len(tg[tail]):
                num, _ = tg[tail][ig[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                ig[tail] += 1
        if not added:
            break
    if len(selected) < pool_size:
        rem = [n for n in range(1, MAX_NUM+1) if n not in selected and n not in exclude]
        rem.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(rem[:pool_size-len(selected)])
    return selected[:pool_size]


# ──────────────────────────────────────────────
# Triple Strike 原版 (Fallback)
# ──────────────────────────────────────────────

def ts_original(history):
    b1 = sorted((np.argsort(np.zeros(MAX_NUM+1))[::-1]+1)[:6].tolist())  # placeholder

    # Fourier
    fp = fourier_pool(history, pool_size=6)
    b1 = fp

    cp = cold_pool(history, exclude=set(b1), pool_size=6)
    b2 = cp

    tp = tail_pool(history, exclude=set(b1)|set(b2), pool_size=6)
    b3 = tp

    return [b1, b2, b3]


def generate_triple_strike(history):
    b1 = fourier_pool(history, pool_size=6)
    b2 = cold_pool(history, exclude=set(b1), pool_size=6)
    b3 = tail_pool(history, exclude=set(b1)|set(b2), pool_size=6)
    return [b1, b2, b3]


# ──────────────────────────────────────────────
# Sum-Constrained Triple Strike
# ──────────────────────────────────────────────

def generate_ts_sum_constrained(history, pool_size=12, apply_to='all'):
    """
    Sum-Constrained Triple Strike。
    apply_to: 'all'       → 所有三注都 sum-constrain
              'bet1_only' → 只約束注1 (Fourier)
              'bet2_only' → 只約束注2 (Cold)
    """
    if len(history) < 2:
        return generate_triple_strike(history)

    tlo, thi, tier = compute_sum_target(history)

    # --- Bet 1 ---
    fp = fourier_pool(history, pool_size=pool_size)
    if apply_to in ('all', 'bet1_only'):
        b1 = sum_select_from_pool(fp, tlo, thi)
    else:
        b1 = sorted(fp[:6])

    # --- Bet 2 ---
    cp = cold_pool(history, exclude=set(b1), pool_size=pool_size)
    if apply_to in ('all', 'bet2_only'):
        b2 = sum_select_from_pool(cp, tlo, thi)
    else:
        b2 = sorted(cp[:6])

    # --- Bet 3 ---
    tp = tail_pool(history, exclude=set(b1)|set(b2), pool_size=pool_size)
    if apply_to in ('all',):
        b3 = sum_select_from_pool(tp, tlo, thi)
    else:
        b3 = sorted(tp[:6])

    return [b1, b2, b3]


# ──────────────────────────────────────────────
# 回測引擎
# ──────────────────────────────────────────────

def run_backtest(draws, strategy_func, n_periods, **kwargs):
    np.random.seed(SEED)
    baseline = BASELINES[3]
    start_idx = max(len(draws) - n_periods, MIN_HISTORY)
    hits = {3: 0, 4: 0, 5: 0, 6: 0}
    total = 0
    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        bets = strategy_func(history, **kwargs)
        best = max((len(set(b) & target) for b in bets), default=0)
        if best >= 3:
            hits[min(best, 6)] += 1
        total += 1
    m3p = sum(hits.values())
    wr  = m3p / total if total else 0
    return {'total': total, 'm3_plus': m3p, 'win_rate': wr,
            'edge': wr - baseline, 'baseline': baseline}


def classify(e150, e500, e1500):
    if e1500 > 0 and e500 > 0 and e150 > 0:
        return "ROBUST" if abs(e150-e1500) < 0.6 else "MODERATE_DECAY"
    if e1500 > 0 and e150 <= 0:
        return "LATE_BLOOMER"
    if e1500 <= 0 and e150 > 0:
        return "SHORT_MOMENTUM"
    return "INEFFECTIVE"


# ──────────────────────────────────────────────
# 診斷：sum 命中率統計
# ──────────────────────────────────────────────

def diagnose_sum_hit_rate(draws, strategy_func, n_periods=1500, **kwargs):
    """計算各 tier 下的 sum 命中率 (預測 sum 是否落在目標範圍)。"""
    start_idx = max(len(draws) - n_periods, MIN_HISTORY)
    tier_stats = {'LOW': [0,0], 'HIGH': [0,0], 'MID': [0,0]}

    for i in range(start_idx, len(draws)):
        history = draws[:i]
        if len(history) < 2:
            continue
        tlo, thi, tier = compute_sum_target(history)
        actual_sum = sum(draws[i]['numbers'])
        bets = strategy_func(history, **kwargs)
        for b in bets:
            in_range = (tlo <= sum(b) <= thi)
            tier_stats[tier][1] += 1
            if in_range:
                tier_stats[tier][0] += 1

    print("  [Sum 範圍命中率 per tier]")
    for tier, (hits, total) in tier_stats.items():
        rate = hits/total*100 if total else 0
        print(f"    {tier}: {hits}/{total} = {rate:.1f}%")

    print("  [實際 sum 落在目標範圍的比率 (前 1500 期)]")
    actual_in = {'LOW': [0,0], 'HIGH': [0,0], 'MID': [0,0]}
    for i in range(start_idx, len(draws)):
        history = draws[:i]
        if len(history) < 2:
            continue
        tlo, thi, tier = compute_sum_target(history)
        asum = sum(draws[i]['numbers'])
        actual_in[tier][1] += 1
        if tlo <= asum <= thi:
            actual_in[tier][0] += 1
    for tier, (h, t) in actual_in.items():
        rate = h/t*100 if t else 0
        print(f"    實際 {tier}: {h}/{t} = {rate:.1f}%")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print(f"大樂透: {len(draws)} 期  ({draws[0]['date']} ~ {draws[-1]['date']})")

    # ══════════════════════════════════════════
    # 基準
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  基準: Triple Strike 原版 (pool=6, no constraint)")
    print("=" * 72)
    base_res = {}
    for w in WINDOWS:
        t0 = time.time()
        r = run_backtest(draws, generate_triple_strike, w)
        base_res[w] = r
        print(f"  {w:4d}期: M3+={r['m3_plus']:3d}/{r['total']:4d} "
              f"Edge={r['edge']*100:+.2f}%  ({time.time()-t0:.1f}s)")

    base_e = {w: base_res[w]['edge']*100 for w in WINDOWS}

    # ══════════════════════════════════════════
    # 診斷: sum 目標範圍實際命中率
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  診斷: Sum 目標範圍統計")
    print("=" * 72)
    diagnose_sum_hit_rate(
        draws,
        lambda h, **kw: generate_ts_sum_constrained(h, pool_size=12, apply_to='all'),
        n_periods=1500
    )

    # ══════════════════════════════════════════
    # Grid Search
    # ══════════════════════════════════════════
    POOL_SIZES  = [8, 10, 12, 15]
    APPLY_MODES = ['all', 'bet2_only', 'bet1_only']

    configs = [(ps, am) for ps in POOL_SIZES for am in APPLY_MODES]
    total_cfg = len(configs)

    print(f"\n" + "=" * 72)
    print(f"  Grid Search: {total_cfg} 組配置 × {len(WINDOWS)} 窗口")
    print("=" * 72)
    print(f"\n{'配置':<22} {'150p':>8} {'500p':>8} {'1500p':>8} "
          f"{'Δ1500':>7} {'三窗口':>6} {'模式'}")
    print("-" * 72)

    grid_results = []
    for ci, (ps, am) in enumerate(configs, 1):
        label = f"pool={ps} {am}"
        fn = lambda h, p=ps, a=am: generate_ts_sum_constrained(h, pool_size=p, apply_to=a)
        res = {}
        t0 = time.time()
        for w in WINDOWS:
            res[w] = run_backtest(draws, fn, w)

        e = {w: res[w]['edge']*100 for w in WINDOWS}
        d1500 = e[1500] - base_e[1500]
        ap = "✓" if all(e[w] > 0 for w in WINDOWS) else " "
        mode = classify(e[150], e[500], e[1500])
        elapsed = time.time() - t0

        print(f"  {label:<20} {e[150]:>+7.2f}% {e[500]:>+7.2f}% "
              f"{e[1500]:>+7.2f}%  {d1500:>+6.2f}%  {ap:<6} {mode}  ({elapsed:.1f}s)")

        grid_results.append({'label': label, 'ps': ps, 'am': am,
                             'e': e, 'delta': d1500, 'all_pos': ap=='✓',
                             'mode': mode, 'res': res})

    # ══════════════════════════════════════════
    # 結論
    # ══════════════════════════════════════════
    print("\n" + "=" * 72)
    print("  最終結論")
    print("=" * 72)

    sorted_g = sorted(grid_results, key=lambda x: -x['e'][1500])
    best = sorted_g[0]

    print(f"\n  基準 (pool=6, 無約束):")
    print(f"    150p={base_e[150]:+.2f}%  500p={base_e[500]:+.2f}%  1500p={base_e[1500]:+.2f}%")
    print(f"    模式: {classify(base_e[150], base_e[500], base_e[1500])}")

    print(f"\n  【Top-5 配置 (by 1500p Edge)】")
    for i, r in enumerate(sorted_g[:5], 1):
        ap_mark = " ★三窗口全正" if r['all_pos'] else ""
        print(f"  #{i}: {r['label']:<20} 150p={r['e'][150]:+.2f}%  "
              f"500p={r['e'][500]:+.2f}%  1500p={r['e'][1500]:+.2f}%  "
              f"{r['mode']}{ap_mark}")

    improved     = sum(1 for r in grid_results if r['e'][1500] > base_e[1500])
    improved_all = sum(1 for r in grid_results if r['all_pos'] and r['e'][1500] > base_e[1500])
    print(f"\n  1500p Edge 改善: {improved}/{total_cfg} 組")
    print(f"  三窗口全正且改善: {improved_all}/{total_cfg} 組")

    print(f"\n  最佳: {best['label']}")
    print(f"    Δ1500 = {best['delta']:+.2f}%  模式: {best['mode']}")

    if best['e'][1500] > base_e[1500] + 0.10 and best['all_pos']:
        verdict = "✅ 採納建議"
        advice  = (f"  → 建議修改 predict_biglotto_triple_strike.py:\n"
                   f"     pool_size={best['ps']}, apply_to='{best['am']}'")
    elif best['e'][1500] > base_e[1500]:
        verdict = "⚠️  改善不足 0.10%，不採納"
        advice  = "  → 信號有效但幅度不足"
    else:
        verdict = "❌ 拒絕: Sum Constraint 無效"
        advice  = "  → sum 均值回歸無法在個注層面提升選號品質"

    print(f"\n  判決: {verdict}")
    print(advice)
    print("=" * 72)


if __name__ == '__main__':
    main()
