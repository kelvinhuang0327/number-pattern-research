#!/usr/bin/env python3
"""
今彩539 P1+偏差互補 2注/3注回測
=================================
研究問題：將大樂透成功的 P1鄰號+冷號+偏差互補 架構移植到539，
         是否也有統計顯著 Edge？

策略結構：
  注1: P1 鄰號  (上期 ±1 鄰域 → Fourier+Markov 排名 Top-5)
  注2: 偏差互補 Cold (排除注1 → 近50期最冷號 Top-5)
  注3: 偏差互補 Hot  (排除注1+2 → 近50期最熱號 Top-5) [3注版本]

對照組：
  - 隨機 2注/3注 基準
  - Fourier4+Cold 5注 (已驗證 PROVISIONAL +1.35%)

驗證：
  - 三窗口：150 / 500 / 1500 期
  - Permutation test：N=2000
  - McNemar：P1 注1 vs 偏差互補 注2 互補率

Usage:
    python3 tools/backtest_539_p1_deviation.py
"""
import os, sys, time, random, json
import numpy as np
from math import comb
from collections import Counter, defaultdict
from itertools import combinations as _icombs
from scipy.fft import fft, fftfreq
from scipy.stats import norm as scipy_norm

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager

# ── Constants ──────────────────────────────────────────────────────
MAX_NUM = 39
PICK    = 5
SEED    = 42
N_PERM  = 2000
WINDOWS = [150, 500, 1500]
MIN_BUF = 500  # Fourier needs 500 periods warmup

# ── Baselines (hypergeometric, any-hit) ────────────────────────────
C39_5   = comb(39, 5)   # 575757
def _p_ge3_single():
    return sum(comb(5,k)*comb(34,5-k) for k in range(3,6)) / C39_5
P_GE3_1 = _p_ge3_single()   # ~0.01004
BASELINES = {
    1: P_GE3_1,
    2: 1 - (1 - P_GE3_1)**2,
    3: 1 - (1 - P_GE3_1)**3,
    5: 1 - (1 - P_GE3_1)**5,
}

def get_numbers(draw):
    nums = draw.get('numbers', [])
    if isinstance(nums, str):
        import json as _j
        nums = _j.loads(nums)
    return list(nums)


# ── Signal Functions ────────────────────────────────────────────────

def fourier_scores(hist, window=500):
    h = hist[-window:] if len(hist) >= window else hist
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in get_numbers(d):
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0; continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        ip = np.where(xf > 0)
        py = np.abs(yf[ip]); px = xf[ip]
        pk = np.argmax(py); fv = px[pk]
        if fv == 0:
            scores[n] = 0.0; continue
        period = 1 / fv
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0.0
    return scores


def markov_scores(hist, window=30):
    recent = hist[-window:] if len(hist) >= window else hist
    trans = defaultdict(Counter)
    for i in range(len(recent) - 1):
        for cn in get_numbers(recent[i]):
            for nn in get_numbers(recent[i+1]):
                trans[cn][nn] += 1
    prev = get_numbers(hist[-1])
    sc = Counter()
    for pn in prev:
        t = trans.get(pn, Counter())
        tot = sum(t.values())
        if tot > 0:
            for n, c in t.items():
                sc[n] += c / tot
    return sc


def deviation_scores(hist, window=50):
    """偏差互補：hot(正偏差) 和 cold(負偏差) 各自排名"""
    recent = hist[-window:] if len(hist) > window else hist
    total  = len(recent)
    expected = total * PICK / MAX_NUM
    freq = Counter(n for d in recent for n in get_numbers(d))
    hot, cold = [], []
    for n in range(1, MAX_NUM + 1):
        dev = freq.get(n, 0) - expected
        if dev > 0.5:
            hot.append((n, dev))
        elif dev < -0.5:
            cold.append((n, abs(dev)))
    hot.sort(key=lambda x: -x[1])
    cold.sort(key=lambda x: -x[1])
    return hot, cold


# ── Strategy Functions ───────────────────────────────────────────────

def bet_p1_neighbor(hist, exclude=None):
    """注1: P1 鄰號 — 上期 ±1 鄰域 → Fourier+Markov 排名 Top-5"""
    exclude = exclude or set()
    prev = get_numbers(hist[-1])
    pool = set()
    for n in prev:
        for d in (-1, 0, 1):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                pool.add(nn)
    pool -= exclude

    fs = fourier_scores(hist, 500)
    mk = markov_scores(hist, 30)
    f_max = max(fs.values()) or 1
    mk_max = max(mk.values()) or 1
    ranked = sorted(pool,
                    key=lambda n: fs.get(n,0)/f_max + 0.5*mk.get(n,0)/mk_max,
                    reverse=True)
    return sorted(ranked[:PICK])


def bet_dev_cold(hist, exclude=None):
    """注2: 偏差互補 Cold — 近50期最冷號 Top-5 (排除 exclude)"""
    exclude = exclude or set()
    _, cold = deviation_scores(hist, 50)
    result = [n for n, _ in cold if n not in exclude]
    if len(result) < PICK:
        freq = Counter(n for d in hist[-50:] for n in get_numbers(d))
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: freq.get(x,0)):
            if n not in exclude and n not in result:
                result.append(n)
            if len(result) >= PICK:
                break
    return sorted(result[:PICK])


def bet_dev_hot(hist, exclude=None):
    """注3: 偏差互補 Hot — 近50期最熱號 Top-5 (排除 exclude)"""
    exclude = exclude or set()
    hot, _ = deviation_scores(hist, 50)
    result = [n for n, _ in hot if n not in exclude]
    if len(result) < PICK:
        freq = Counter(n for d in hist[-50:] for n in get_numbers(d))
        for n in sorted(range(1, MAX_NUM+1), key=lambda x: -freq.get(x,0)):
            if n not in exclude and n not in result:
                result.append(n)
            if len(result) >= PICK:
                break
    return sorted(result[:PICK])


def strategy_2bet(hist):
    """2注: P1鄰號 + 偏差互補Cold"""
    b1 = bet_p1_neighbor(hist)
    b2 = bet_dev_cold(hist, exclude=set(b1))
    return [b1, b2]


def strategy_3bet(hist):
    """3注: P1鄰號 + 偏差互補Cold + 偏差互補Hot"""
    b1 = bet_p1_neighbor(hist)
    used = set(b1)
    b2 = bet_dev_cold(hist, exclude=used)
    used |= set(b2)
    b3 = bet_dev_hot(hist, exclude=used)
    return [b1, b2, b3]


def strategy_2bet_p1only(hist):
    """對照: P1鄰號 單注（分析互補性用）"""
    return [bet_p1_neighbor(hist)]


def strategy_2bet_cold_only(hist):
    """對照: 偏差互補Cold 單注（分析互補性用）"""
    return [bet_dev_cold(hist)]


# ── Precompute ───────────────────────────────────────────────────────

def precompute(draws, start_idx):
    N = len(draws) - start_idx
    print(f"  預計算 {N} 期...", end='', flush=True)
    t0 = time.time()

    targets   = []
    hits_2bet = []
    hits_3bet = []
    hits_b1   = []   # P1 注1 單獨命中
    hits_b2   = []   # Cold 注2 單獨命中

    for i in range(start_idx, len(draws)):
        tgt = frozenset(get_numbers(draws[i]))
        hist = draws[:i]
        targets.append(tgt)
        try:
            b2 = strategy_2bet(hist)
            b3 = b2 + [bet_dev_hot(hist, exclude=set(b2[0])|set(b2[1]))]
            h2 = any(len(frozenset(b) & tgt) >= 3 for b in b2)
            h3 = any(len(frozenset(b) & tgt) >= 3 for b in b3)
            h_b1 = len(frozenset(b2[0]) & tgt) >= 3
            h_b2 = len(frozenset(b2[1]) & tgt) >= 3
        except Exception:
            h2 = h3 = h_b1 = h_b2 = False

        hits_2bet.append(h2)
        hits_3bet.append(h3)
        hits_b1.append(h_b1)
        hits_b2.append(h_b2)

    print(f" 完成 ({time.time()-t0:.1f}s)")
    return targets, hits_2bet, hits_3bet, hits_b1, hits_b2


# ── Stats ────────────────────────────────────────────────────────────

def calc_edge(hits_arr, n_periods, n_bets, label=""):
    N = len(hits_arr)
    start = max(0, N - n_periods)
    chunk = hits_arr[start:]
    hits = sum(chunk); total = len(chunk)
    if total == 0: return None
    base = BASELINES[n_bets]
    rate = hits / total
    edge = rate - base
    z = edge / np.sqrt(base*(1-base)/total)
    p = 2*(1 - scipy_norm.cdf(abs(z)))
    return dict(label=label, hits=hits, total=total,
                rate=rate, base=base, edge_abs=edge*100, z=z, p=p)


def pr(r):
    if not r: return
    sig = "***" if r['p']<0.01 else "**" if r['p']<0.05 else "*" if r['p']<0.10 else ""
    print(f"  {r['label']:<36s} {r['hits']:4d}/{r['total']:5d} "
          f"= {r['rate']:.4f}  基準={r['base']:.4f}  "
          f"Edge={r['edge_abs']:+.2f}%  z={r['z']:+.2f}{sig}")


def permutation_test(hits_arr, n_periods, n_bets, n_perm=N_PERM, seed=SEED):
    """對 hits_arr (bool array) 做 permutation test：shuffle labels vs 實際"""
    N = len(hits_arr)
    start = max(0, N - n_periods)
    chunk = np.array(hits_arr[start:], dtype=float)
    actual_rate = chunk.mean()
    base = BASELINES[n_bets]
    actual_edge = (actual_rate - base) * 100

    rng = np.random.default_rng(seed)
    rand_edges = []
    for _ in range(n_perm):
        shuffled = rng.permutation(chunk)
        rand_edges.append((shuffled.mean() - base) * 100)

    rand_arr = np.array(rand_edges)
    perm_p = np.mean(rand_arr >= actual_edge)
    return dict(
        actual_edge=actual_edge,
        rand_mean=rand_arr.mean(),
        rand_std=rand_arr.std(),
        perm_p=perm_p,
        signal='SIGNAL DETECTED' if perm_p<=0.05 else 'MARGINAL' if perm_p<=0.10 else 'NOISE',
        n_perm=n_perm,
    )


def mcnemar(hits_a, hits_b, n_periods):
    """McNemar: b vs a 互補率"""
    from scipy.stats import chi2 as chi2d
    N = len(hits_a)
    start = max(0, N - n_periods)
    a = hits_a[start:]; b = hits_b[start:]
    b_wins = sum(1 for ha, hb in zip(a, b) if hb and not ha)
    a_wins = sum(1 for ha, hb in zip(a, b) if ha and not hb)
    both   = sum(1 for ha, hb in zip(a, b) if ha and hb)
    disc = a_wins + b_wins
    if disc == 0: return 0, 1.0, a_wins, b_wins, both
    chi2 = (abs(a_wins - b_wins)-1)**2 / disc
    p = 1 - chi2d.cdf(chi2, df=1)
    return chi2, p, a_wins, b_wins, both


# ── Main ─────────────────────────────────────────────────────────────

def main():
    np.random.seed(SEED)
    db_path = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = sorted(db.get_all_draws('DAILY_539'),
                   key=lambda x: (x['date'], x['draw']))
    print(f"\n今彩539 P1+偏差互補 2注/3注回測")
    print(f"資料: {len(draws)} 期  seed={SEED}")
    print(f"1注 M3+ 基準: {P_GE3_1*100:.3f}%  "
          f"2注: {BASELINES[2]*100:.3f}%  "
          f"3注: {BASELINES[3]*100:.3f}%  "
          f"5注: {BASELINES[5]*100:.3f}%")
    t0 = time.time()

    start_idx = max(len(draws) - 1500, MIN_BUF)
    targets, hits_2, hits_3, hits_b1, hits_b2 = precompute(draws, start_idx)

    # ── 三窗口 ──────────────────────────────────────────────────────
    print(f"\n{'='*68}")
    print(f"  三窗口 Edge 比較")
    print(f"{'='*68}")

    results = {w: {} for w in WINDOWS}
    for w in WINDOWS:
        print(f"\n--- {w}期窗口 ---")
        r2 = calc_edge(hits_2, w, 2, "P1鄰號+DevCold 2注")
        r3 = calc_edge(hits_3, w, 3, "P1鄰號+DevCold+DevHot 3注")
        rb1= calc_edge(hits_b1, w, 1, "  [注1] P1鄰號 單獨")
        rb2= calc_edge(hits_b2, w, 1, "  [注2] DevCold 單獨")
        for r in [r2, r3, rb1, rb2]:
            pr(r)
        results[w] = {'2注': r2, '3注': r3, 'b1': rb1, 'b2': rb2}

    # ── 摘要表 ────────────────────────────────────────────────────
    print(f"\n{'='*68}")
    print(f"  三窗口摘要")
    print(f"{'='*68}")
    print(f"  {'策略':<28s} {'150p':>8s} {'500p':>8s} {'1500p':>8s}  模式")
    print(f"  {'-'*63}")
    for key in ['2注', '3注']:
        edges = [results[w].get(key, {}).get('edge_abs', 0) for w in WINDOWS]
        if all(e > 0 for e in edges):       mode = "ROBUST ✓"
        elif edges[2]>0 and edges[0]<0:    mode = "LATE_BLOOMER"
        elif edges[0]>0 and edges[2]<0:    mode = "SHORT_MOMENTUM"
        else:                               mode = "MIXED"
        lbl = "P1+DevCold 2注" if key == '2注' else "P1+DevCold+DevHot 3注"
        print(f"  {lbl:<28s} {edges[0]:>+7.2f}% {edges[1]:>+7.2f}% {edges[2]:>+7.2f}%  {mode}")

    # ── McNemar 互補率 ───────────────────────────────────────────
    print(f"\n{'='*68}")
    print(f"  McNemar 互補率 (1500期)")
    print(f"{'='*68}")
    chi2_val, p_mc, a_w, b_w, both = mcnemar(hits_b1, hits_b2, 1500)
    print(f"  P1注1 vs DevCold注2:")
    print(f"  兩者皆中={both}  注1獨贏={a_w}  注2獨贏={b_w}  χ²={chi2_val:.2f}  p={p_mc:.4f}")
    total_mc = sum(hits_b1[-1500:]) + sum(hits_b2[-1500:]) - both
    compl_ratio = (a_w + b_w) / max(total_mc, 1)
    print(f"  互補率 (獨贏比例): {compl_ratio:.1%}  "
          f"{'★ 高互補 — 合注有益' if compl_ratio > 0.6 else '互補性一般'}")

    # ── Permutation test ─────────────────────────────────────────
    print(f"\n{'='*68}")
    print(f"  Permutation Test (1500期, n={N_PERM})")
    print(f"{'='*68}")
    print(f"  (注意: Bonferroni α=0.05/2={0.05/2:.3f}，需 perm_p≤0.025)")
    print()

    for key, hits_arr, n_bets in [
        ("P1+DevCold 2注",       hits_2, 2),
        ("P1+DevCold+Hot 3注",   hits_3, 3),
        ("[注1] P1鄰號 單獨",    hits_b1, 1),
        ("[注2] DevCold 單獨",   hits_b2, 1),
    ]:
        pr_r = permutation_test(hits_arr, 1500, n_bets, N_PERM, SEED)
        print(f"  {key:<30s}  Edge={pr_r['actual_edge']:+.3f}%  "
              f"隨機均值={pr_r['rand_mean']:+.3f}%  "
              f"perm_p={pr_r['perm_p']:.4f}  {pr_r['signal']}")

    # ── 對比 5注 Fourier4+Cold ───────────────────────────────────
    print(f"\n{'='*68}")
    print(f"  與現有5注策略對比 (參考)")
    print(f"{'='*68}")
    print(f"  5注 Fourier4+Cold (已驗證 PROVISIONAL):")
    print(f"    Edge +1.35%, 1500期 ROBUST, perm p=0.030")
    r2_1500 = results[1500].get('2注', {})
    r3_1500 = results[1500].get('3注', {})
    print(f"  2注 P1+DevCold:")
    print(f"    Edge {r2_1500.get('edge_abs', 0):+.2f}%, "
          f"cost=2注 vs 5注(節省60%成本)")
    print(f"  3注 P1+DevCold+Hot:")
    print(f"    Edge {r3_1500.get('edge_abs', 0):+.2f}%, "
          f"cost=3注 vs 5注(節省40%成本)")

    # ── 結論 ────────────────────────────────────────────────────
    print(f"\n{'='*68}")
    print(f"  研究結論")
    print(f"{'='*68}")

    edges_2 = [results[w].get('2注', {}).get('edge_abs', 0) for w in WINDOWS]
    edges_3 = [results[w].get('3注', {}).get('edge_abs', 0) for w in WINDOWS]

    perm_2 = permutation_test(hits_2, 1500, 2, 200, SEED)  # quick 200-iter check
    perm_3 = permutation_test(hits_3, 1500, 3, 200, SEED)

    def verdict(edges, perm_p, n):
        robust = all(e > 0 for e in edges)
        if robust and perm_p <= 0.025:
            return f"✅ {n}注 PASS — 三窗口全正 + perm p={perm_p:.3f} SIGNAL DETECTED"
        elif robust and perm_p <= 0.05:
            return f"✅ {n}注 PROVISIONAL — 三窗口全正 + perm p={perm_p:.3f} (Bonferroni邊界)"
        elif robust and perm_p <= 0.10:
            return f"⚠️  {n}注 MARGINAL — 三窗口全正但 perm p={perm_p:.3f}"
        elif robust:
            return f"❌ {n}注 NOISE — 三窗口全正但 perm p={perm_p:.3f}"
        else:
            return f"❌ {n}注 FAIL — 三窗口未全正"

    print(f"  {verdict(edges_2, perm_2['perm_p'], 2)}")
    print(f"  {verdict(edges_3, perm_3['perm_p'], 3)}")
    print(f"\n  耗時: {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
