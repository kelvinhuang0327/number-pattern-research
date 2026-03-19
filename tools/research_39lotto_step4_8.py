#!/usr/bin/env python3
"""
39樂合彩 v2 — STEP 4-8 全面研究級分析引擎
==========================================
STEP 4: 歷史回測 (Sharpe-like, cross-validation, 偏差, 變異數)
STEP 5: 隨機性檢定 (Chi2, KS, Runs, Autocorrelation, NIST-approx)
STEP 6: 過擬合檢測 (Random label test, Learning curve, CV variance)
STEP 7: 蒙地卡羅模擬 (100K次, 信賴區間, p-value)
STEP 8: 模型融合 (Voting, Stacking, Regime switching)

嚴格防數據洩漏: history = draws[:i], actual = draws[i]
"""

import json
import math
import sqlite3
import os
import sys
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
from scipy import stats as sp_stats
import copy

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_v2.db')

POOL = 39
PICK = 5

def comb(n, k):
    return math.comb(n, k)

BASELINE_GE2 = sum(comb(PICK, k) * comb(POOL-PICK, PICK-k) / comb(POOL, PICK) for k in range(2, PICK+1))
BASELINE_GE3 = sum(comb(PICK, k) * comb(POOL-PICK, PICK-k) / comb(POOL, PICK) for k in range(3, PICK+1))

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT draw, date, numbers FROM draws WHERE lottery_type='DAILY_539' ORDER BY date ASC, draw ASC")
    rows = cursor.fetchall()
    conn.close()
    return [{'draw': r[0], 'date': r[1], 'numbers': sorted(json.loads(r[2]))} for r in rows]

# ═══════════════════════════════════
#  策略庫
# ═══════════════════════════════════

def random_predict(history, rng, n=PICK):
    return sorted(rng.choice(range(1, POOL+1), size=n, replace=False).tolist())

def freq_predict(history, window=100, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    c = Counter()
    for d in recent:
        for num in d['numbers']: c[num] += 1
    return sorted([x[0] for x in c.most_common(n)])

def cold_predict(history, window=100, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    c = {num: 0 for num in range(1, POOL+1)}
    for d in recent:
        for num in d['numbers']: c[num] += 1
    return sorted([x[0] for x in sorted(c.items(), key=lambda x: x[1])[:n]])

def devecho_predict(history, window=100, n=PICK):
    if len(history) < 10: return list(range(1, n+1))
    recent = history[-window:] if len(history) >= window else history
    c = Counter()
    for num in range(1, POOL+1): c[num] = 0
    for d in recent:
        for num in d['numbers']: c[num] += 1
    expected = len(recent) * PICK / POOL
    scores = {num: c[num] - expected for num in range(1, POOL+1)}
    if len(history) >= 2:
        for num in history[-2]['numbers']:
            if num in scores: scores[num] *= 1.5
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def markov_predict(history, window=30, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 5: return list(range(1, n+1))
    T = np.zeros((POOL, POOL))
    for i in range(len(recent)-1):
        for a in recent[i]['numbers']:
            for b in recent[i+1]['numbers']:
                T[a-1][b-1] += 1
    rs = T.sum(axis=1, keepdims=True); rs[rs==0] = 1; T = T / rs
    scores = np.zeros(POOL)
    for num in recent[-1]['numbers']: scores += T[num-1]
    return sorted([int(idx+1) for idx in np.argsort(-scores)[:n]])

def fourier_predict(history, window=500, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 30: return list(range(1, n+1))
    scores = {}
    for num in range(1, POOL+1):
        s = np.array([1 if num in d['numbers'] else 0 for d in recent], dtype=float)
        fft = np.fft.rfft(s); pw = np.abs(fft)**2
        if len(pw) > 1:
            di = np.argmax(pw[1:]) + 1
            phase = np.angle(fft[di]); freq = di / len(s)
            pred = np.abs(fft[di]) * np.cos(2*np.pi*freq*len(s) + phase)
            scores[num] = s.mean() + 0.3 * pred / (len(s)**0.5)
        else: scores[num] = 0
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def bayesian_predict(history, alpha=1.0, window=200, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 5: return list(range(1, n+1))
    c = Counter()
    for d in recent:
        for num in d['numbers']: c[num] += 1
    total = sum(c.values())
    post = {num: (alpha + c.get(num, 0)) / (POOL*alpha + total) for num in range(1, POOL+1)}
    ranked = sorted(post.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def ema_predict(history, decay=0.05, n=PICK):
    if len(history) < 10: return list(range(1, n+1))
    scores = {num: 0.0 for num in range(1, POOL+1)}
    for i, d in enumerate(history[-200:]):
        w = np.exp(-decay * (min(200, len(history)) - i))
        for num in d['numbers']: scores[num] += w
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def gap_predict(history, window=300, n=PICK):
    if len(history) < 20: return list(range(1, n+1))
    recent = history[-window:] if len(history) >= window else history
    scores = {}
    for num in range(1, POOL+1):
        apps = [i for i, d in enumerate(recent) if num in d['numbers']]
        if len(apps) < 2: scores[num] = 1.0; continue
        gaps = [apps[i+1]-apps[i] for i in range(len(apps)-1)]
        avg = np.mean(gaps); curr = len(recent) - apps[-1]
        scores[num] = curr / avg if avg > 0 else 0
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def condentropy_predict(history, window=200, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 20: return list(range(1, n+1))
    scores = {}
    for num in range(1, POOL+1):
        s = [1 if num in d['numbers'] else 0 for d in recent]
        trans = {'00':0,'01':0,'10':0,'11':0}
        for i in range(1, len(s)): trans[f'{s[i-1]}{s[i]}'] += 1
        last = s[-1]
        t = trans[f'{last}0'] + trans[f'{last}1']
        scores[num] = trans[f'{last}1'] / t if t > 0 else 0.5
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def pairfreq_predict(history, window=200, n=PICK):
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 20: return list(range(1, n+1))
    pc = Counter()
    for d in recent:
        nums = d['numbers']
        for i in range(len(nums)):
            for j in range(i+1, len(nums)): pc[(nums[i], nums[j])] += 1
    ns = Counter()
    for (a,b), cnt in pc.most_common(50): ns[a] += cnt; ns[b] += cnt
    ranked = ns.most_common(n)
    result = [x[0] for x in ranked]
    if len(result) < n:
        rem = [x for x in range(1, POOL+1) if x not in result]
        result.extend(rem[:n-len(result)])
    return sorted(result[:n])

# ── 融合策略 STEP 8 ──

def voting_predict(history, n=PICK):
    """多數投票融合"""
    methods = [
        lambda h: fourier_predict(h, 500),
        lambda h: markov_predict(h, 30),
        lambda h: devecho_predict(h, 100),
        lambda h: freq_predict(h, 100),
        lambda h: bayesian_predict(h),
    ]
    votes = Counter()
    for m in methods:
        pred = m(history)
        for num in pred: votes[num] += 1
    return sorted([x[0] for x in votes.most_common(n)])

def weighted_voting_predict(history, n=PICK):
    """加權投票 (基準: Fourier 2x, Markov 1.5x, 其他 1x)"""
    methods_w = [
        (lambda h: fourier_predict(h, 500), 2.0),
        (lambda h: markov_predict(h, 30), 1.5),
        (lambda h: devecho_predict(h, 100), 1.0),
        (lambda h: freq_predict(h, 100), 1.0),
        (lambda h: bayesian_predict(h), 0.8),
    ]
    scores = Counter()
    for m, w in methods_w:
        pred = m(history)
        for num in pred: scores[num] += w
    return sorted([x[0] for x in scores.most_common(n)])

def stacking_predict(history, n=PICK):
    """Stacking: 第一層各方法產生分數，第二層取平均排序"""
    recent = history[-100:] if len(history) >= 100 else history
    if len(recent) < 30: return list(range(1, n+1))

    # 各方法產生 39 維分數
    all_scores = []

    # Freq scores
    c = Counter()
    for d in recent:
        for num in d['numbers']: c[num] += 1
    total = sum(c.values()) or 1
    all_scores.append({num: c.get(num, 0)/total for num in range(1, POOL+1)})

    # Gap scores (normalized)
    last_seen = {}
    for i, d in enumerate(recent):
        for num in d['numbers']: last_seen[num] = i
    curr = len(recent)
    gap_sc = {num: (curr - last_seen.get(num, -1))/max(curr, 1) for num in range(1, POOL+1)}
    # 反轉 gap — 高 gap 可能回歸
    all_scores.append(gap_sc)

    # Markov scores
    T = np.zeros((POOL, POOL))
    for i in range(len(recent)-1):
        for a in recent[i]['numbers']:
            for b in recent[i+1]['numbers']: T[a-1][b-1] += 1
    rs = T.sum(axis=1, keepdims=True); rs[rs==0] = 1; T = T / rs
    mk = np.zeros(POOL)
    if recent:
        for num in recent[-1]['numbers']: mk += T[num-1]
    all_scores.append({num: mk[num-1] for num in range(1, POOL+1)})

    # Meta layer: normalize each to [0,1] then average
    final = {num: 0 for num in range(1, POOL+1)}
    for sc in all_scores:
        vals = list(sc.values())
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx - mn > 0 else 1
        for num in range(1, POOL+1):
            final[num] += (sc[num] - mn) / rng

    ranked = sorted(final.items(), key=lambda x: -x[1])
    return sorted([x[0] for x in ranked[:n]])

def regime_predict(history, n=PICK):
    """Regime switching: 根據近期狀態選策略"""
    if len(history) < 50: return list(range(1, n+1))
    recent_50 = history[-50:]
    # 計算近期熵
    c = Counter()
    for d in recent_50:
        for num in d['numbers']: c[num] += 1
    total = sum(c.values()) or 1
    entropy = -sum((v/total) * np.log2(v/total) for v in c.values() if v > 0)
    max_entropy = np.log2(POOL)  # ~5.29

    ratio = entropy / max_entropy
    if ratio > 0.98:
        # 高熵 (分散) → 用 Markov
        return markov_predict(history, 30, n)
    elif ratio > 0.95:
        # 中熵 → Fourier
        return fourier_predict(history, 500, n)
    else:
        # 低熵 (集中) → 頻率
        return freq_predict(history, 50, n)


STRATEGIES = {
    # Baselines
    'B_Freq_w50':     lambda h: freq_predict(h, 50),
    'B_Freq_w100':    lambda h: freq_predict(h, 100),
    'B_Cold_w100':    lambda h: cold_predict(h, 100),
    # Core
    'S1_Fourier':     lambda h: fourier_predict(h, 500),
    'S2_DevEcho':     lambda h: devecho_predict(h, 100),
    'S3_Markov':      lambda h: markov_predict(h, 30),
    'S4_Bayesian':    lambda h: bayesian_predict(h),
    'S5_EMA':         lambda h: ema_predict(h, 0.05),
    'S6_Gap':         lambda h: gap_predict(h),
    'S7_CondEntropy': lambda h: condentropy_predict(h),
    'S8_PairFreq':    lambda h: pairfreq_predict(h),
    # Fusion (STEP 8)
    'F1_Voting':      voting_predict,
    'F2_WeightedVote': weighted_voting_predict,
    'F3_Stacking':    stacking_predict,
    'F4_Regime':      regime_predict,
}


def main():
    t0 = datetime.now()
    print("=" * 80)
    print("39樂合彩 v2 — STEP 4-8 研究級分析引擎")
    print(f"啟動: {t0.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    draws = load_draws()
    N = len(draws)
    print(f"\n資料: {N} 期 ({draws[0]['date']} ~ {draws[-1]['date']})")

    # ══════════════════════════════════
    # STEP 5: 隨機性檢定
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 5: 隨機性與統計檢定")
    print("═"*80)

    # 5.1 χ² 均勻性 (每個號碼)
    freq_all = Counter()
    for d in draws:
        for num in d['numbers']: freq_all[num] += 1
    obs = [freq_all.get(i, 0) for i in range(1, POOL+1)]
    exp_val = N * PICK / POOL
    chi2, p_chi2 = sp_stats.chisquare(obs, f_exp=[exp_val]*POOL)
    print(f"\n5.1 χ² 均勻性: χ²={chi2:.2f}, p={p_chi2:.6f} → {'❌ 均勻' if p_chi2 > 0.05 else '✅ 偏差'}")

    # 5.2 KS Test (各號碼的出現次數 vs 均勻分布)
    obs_arr = np.array(obs, dtype=float)
    obs_norm = obs_arr / obs_arr.sum()
    uniform = np.ones(POOL) / POOL
    # 用 CDF 形式做 KS
    obs_cdf = np.cumsum(obs_norm)
    uni_cdf = np.cumsum(uniform)
    ks_stat = np.max(np.abs(obs_cdf - uni_cdf))
    # Critical value for KS at α=0.05, n=39: 1.36/sqrt(39) ≈ 0.218
    ks_crit = 1.36 / np.sqrt(POOL)
    print(f"5.2 KS Test: D={ks_stat:.4f}, 臨界值(α=0.05)={ks_crit:.4f} → {'✅ 偏差' if ks_stat > ks_crit else '❌ 均勻'}")

    # 5.3 自相關檢測 (各號碼的出現序列)
    print(f"\n5.3 自相關檢測 (lag 1-5):")
    significant_autocorr = 0
    total_tests = 0
    for num in range(1, POOL+1):
        series = np.array([1 if num in d['numbers'] else 0 for d in draws], dtype=float)
        series_centered = series - series.mean()
        var = np.var(series_centered)
        if var == 0: continue
        for lag in range(1, 6):
            n_s = len(series_centered)
            acf = np.sum(series_centered[:n_s-lag] * series_centered[lag:]) / (n_s * var)
            ci = 1.96 / np.sqrt(n_s)
            total_tests += 1
            if abs(acf) > ci: significant_autocorr += 1

    bonf = 0.05 / total_tests
    print(f"  測試數: {total_tests} (39號碼 × 5 lags)")
    print(f"  |ACF| > 1.96/√N 的比例: {significant_autocorr}/{total_tests} = {significant_autocorr/total_tests*100:.2f}%")
    print(f"  期望假陽性率 (α=0.05): ~5.00%")
    print(f"  → {'✅ 有自相關' if significant_autocorr/total_tests > 0.10 else '❌ 無顯著自相關'}")

    # 5.4 Runs Test
    print(f"\n5.4 Runs Test (序列隨機性):")
    runs_results = []
    for num in range(1, POOL+1):
        series = [1 if num in d['numbers'] else 0 for d in draws]
        n1 = sum(series); n0 = len(series) - n1
        if n0 == 0 or n1 == 0: continue
        runs = 1
        for i in range(1, len(series)):
            if series[i] != series[i-1]: runs += 1
        # Expected runs and variance
        exp_runs = 1 + 2*n0*n1/(n0+n1)
        var_runs = 2*n0*n1*(2*n0*n1 - n0 - n1) / ((n0+n1)**2 * (n0+n1-1))
        if var_runs > 0:
            z_runs = (runs - exp_runs) / np.sqrt(var_runs)
            p_runs = 2 * (1 - sp_stats.norm.cdf(abs(z_runs)))
            runs_results.append((num, z_runs, p_runs))

    sig_runs = sum(1 for _, _, p in runs_results if p < 0.05)
    print(f"  顯著 (p<0.05): {sig_runs}/{len(runs_results)} 號碼")
    print(f"  期望假陽性: ~{0.05*len(runs_results):.1f}")
    print(f"  → {'✅ 非隨機' if sig_runs > 0.10*len(runs_results) else '❌ 符合隨機'}")

    # 5.5 NIST-approximate: Frequency (Monobit) test
    print(f"\n5.5 NIST 近似 - Monobit test (全序列):")
    all_bits = []
    for d in draws:
        for num in range(1, POOL+1):
            all_bits.append(1 if num in d['numbers'] else -1)
    S = sum(all_bits)
    n_bits = len(all_bits)
    s_obs = abs(S) / np.sqrt(n_bits)
    p_monobit = math.erfc(s_obs / np.sqrt(2))
    print(f"  S={S}, n={n_bits}, s_obs={s_obs:.4f}, p={p_monobit:.6f}")
    print(f"  → {'❌ 均勻' if p_monobit > 0.01 else '✅ 非均勻'}")

    # 5.6 Block Frequency Test (block=1000)
    block_size = 1000
    blocks = [all_bits[i:i+block_size] for i in range(0, n_bits-block_size+1, block_size)]
    chi2_block = 0
    for block in blocks:
        pi = sum(1 for b in block if b == 1) / block_size
        chi2_block += 4 * block_size * (pi - 0.5)**2
    p_block = 1 - sp_stats.chi2.cdf(chi2_block, len(blocks))
    print(f"\n5.6 NIST Block Frequency (block={block_size}):")
    print(f"  χ²={chi2_block:.4f}, blocks={len(blocks)}, p={p_block:.6f}")
    print(f"  → {'❌ 均勻' if p_block > 0.01 else '✅ 非均勻'}")

    # 隨機性總結
    print(f"\n{'─'*40}")
    print(f"STEP 5 總結: 39樂合彩隨機性檢定")
    print(f"  χ² 均勻性:    p={p_chi2:.4f} {'PASS' if p_chi2 > 0.05 else 'FAIL'}")
    print(f"  KS 均勻性:    D={ks_stat:.4f} {'PASS' if ks_stat < ks_crit else 'FAIL'}")
    print(f"  自相關:        {significant_autocorr/total_tests*100:.1f}% {'PASS' if significant_autocorr/total_tests < 0.10 else 'FAIL'}")
    print(f"  Runs test:    {sig_runs}/{len(runs_results)} {'PASS' if sig_runs < 0.10*len(runs_results) else 'FAIL'}")
    print(f"  NIST Monobit: p={p_monobit:.4f} {'PASS' if p_monobit > 0.01 else 'FAIL'}")
    print(f"  NIST Block:   p={p_block:.4f} {'PASS' if p_block > 0.01 else 'FAIL'}")
    randomness_tests_passed = sum([
        p_chi2 > 0.05, ks_stat < ks_crit,
        significant_autocorr/total_tests < 0.10,
        sig_runs < 0.10*len(runs_results),
        p_monobit > 0.01, p_block > 0.01
    ])
    print(f"  通過 {randomness_tests_passed}/6 項隨機性檢定")
    print(f"  結論: {'序列為隨機過程，無可利用的非隨機訊號' if randomness_tests_passed >= 5 else '存在部分非隨機結構'}")

    # ══════════════════════════════════
    # STEP 4: 歷史回測 (擴展指標)
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 4: 歷史回測引擎 (含 Sharpe-like ratio)")
    print("═"*80)

    TEST_PERIODS = 3000
    MIN_TRAIN = 200
    start_idx = max(MIN_TRAIN, N - TEST_PERIODS)

    results = {}

    for sname, sfn in STRATEGIES.items():
        hits_arr = []
        ge2_arr = []
        ge3_arr = []

        for i in range(start_idx, N):
            history = draws[:i]
            prediction = sfn(history)
            actual = set(draws[i]['numbers'])
            hits = len(set(prediction) & actual)
            hits_arr.append(hits)
            ge2_arr.append(1 if hits >= 2 else 0)
            ge3_arr.append(1 if hits >= 3 else 0)

        hits_arr = np.array(hits_arr)
        ge2_arr = np.array(ge2_arr)
        ge3_arr = np.array(ge3_arr)
        n_test = len(hits_arr)

        avg_hits = hits_arr.mean()
        hit_std = hits_arr.std()
        ge2_rate = ge2_arr.mean()
        ge3_rate = ge3_arr.mean()
        ge2_edge = ge2_rate - BASELINE_GE2
        ge3_edge = ge3_rate - BASELINE_GE3

        # Sharpe-like ratio: Edge / Std of rolling edge
        window_sharpe = 300
        rolling_edges = []
        for j in range(0, n_test - window_sharpe, window_sharpe // 2):
            chunk = ge2_arr[j:j+window_sharpe]
            rolling_edges.append(chunk.mean() - BASELINE_GE2)
        rolling_edges = np.array(rolling_edges) if rolling_edges else np.array([0])
        sharpe = rolling_edges.mean() / rolling_edges.std() if rolling_edges.std() > 0 else 0

        # 預測偏差 (bias): 平均命中 - 期望命中
        expected_hits = PICK * PICK / POOL  # E[hits] = 5×5/39 = 0.641
        bias = avg_hits - expected_hits

        # 長期期望值 per bet (基於 ≥2 edge)
        # 假設二合中獎 NT$100, 每注 NT$25
        ev_per_bet = ge2_edge * 100 - (1 - ge2_rate) * 0  # 簡化: 每注的 Edge × 回報
        # 更準確: EV = (ge2_rate × prize - cost) / cost
        # 不知具體獎金，用 edge 代替

        results[sname] = {
            'n_test': n_test,
            'avg_hits': avg_hits,
            'hit_std': hit_std,
            'ge2_rate': ge2_rate,
            'ge2_edge': ge2_edge,
            'ge3_rate': ge3_rate,
            'ge3_edge': ge3_edge,
            'sharpe': sharpe,
            'bias': bias,
            'variance': hit_std**2,
            'rolling_edge_mean': rolling_edges.mean(),
            'rolling_edge_std': rolling_edges.std(),
        }

    # 輸出
    print(f"\n回測期數: {N - start_idx} | 訓練起點: 期{start_idx}")
    print(f"\n{'策略':<20s} | {'AvgHit':>7s} | {'≥2 Rate':>8s} | {'≥2 Edge':>8s} | {'≥3 Edge':>8s} | {'Sharpe':>7s} | {'Bias':>7s} | {'Var':>6s}")
    print(f"{'─'*20} | {'─'*7} | {'─'*8} | {'─'*8} | {'─'*8} | {'─'*7} | {'─'*7} | {'─'*6}")

    sorted_results = sorted(results.items(), key=lambda x: -x[1]['ge2_edge'])
    for sname, r in sorted_results:
        marker = "✅" if r['ge2_edge'] > 0 else "❌"
        print(f"{sname:<20s} | {r['avg_hits']:7.4f} | {r['ge2_rate']*100:7.3f}% | {r['ge2_edge']*100:+7.3f}% | {r['ge3_edge']*100:+7.4f}% | {r['sharpe']:+7.3f} | {r['bias']:+7.4f} | {r['variance']:.4f} {marker}")

    # ══════════════════════════════════
    # STEP 6: 過擬合檢測
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 6: 過擬合檢測")
    print("═"*80)

    # 6.1 Random Label Test
    print(f"\n6.1 Random Label Test (打亂標籤後回測):")
    print(f"    若打亂後 edge 相近 → 原始 edge 是假信號")

    rng_rl = np.random.RandomState(42)
    TOP_STRATEGIES = ['S1_Fourier', 'S3_Markov', 'S2_DevEcho', 'F1_Voting', 'F2_WeightedVote']

    for sname in TOP_STRATEGIES:
        sfn = STRATEGIES[sname]
        # 打亂開獎號碼 (保留分布，破壞時序)
        shuffled_draws = copy.deepcopy(draws)
        numbers_pool = [d['numbers'] for d in shuffled_draws]
        rng_rl.shuffle(numbers_pool)
        for j, d in enumerate(shuffled_draws): d['numbers'] = numbers_pool[j]

        ge2_real = results[sname]['ge2_edge']

        ge2_rand = 0
        cnt = 0
        for i in range(start_idx, N):
            history = shuffled_draws[:i]
            prediction = sfn(history)
            actual = set(shuffled_draws[i]['numbers'])
            if len(set(prediction) & actual) >= 2: ge2_rand += 1
            cnt += 1
        edge_rand = ge2_rand / cnt - BASELINE_GE2

        overfit = abs(ge2_real - edge_rand) < abs(ge2_real) * 0.5
        print(f"    {sname:20s} | Real Edge={ge2_real*100:+.3f}% | Random Edge={edge_rand*100:+.3f}% | {'⚠️ 可能過擬合' if overfit else '✅ 非過擬合'}")

    # 6.2 Learning Curve (edge vs training data size)
    print(f"\n6.2 Learning Curve (訓練資料量 vs Edge):")
    for sname in ['S1_Fourier', 'S3_Markov']:
        sfn = STRATEGIES[sname]
        print(f"\n    {sname}:")
        for train_size in [200, 500, 1000, 2000, 3000, 5000]:
            if train_size >= N: continue
            test_start = train_size
            test_end = min(test_start + 500, N)
            ge2 = 0; cnt = 0
            for i in range(test_start, test_end):
                history = draws[:i]
                prediction = sfn(history)
                actual = set(draws[i]['numbers'])
                if len(set(prediction) & actual) >= 2: ge2 += 1
                cnt += 1
            if cnt > 0:
                edge = ge2/cnt - BASELINE_GE2
                print(f"      Train={train_size:5d} → Edge={edge*100:+.3f}% (test={cnt}期)")

    # 6.3 Cross-Validation Variance
    print(f"\n6.3 5-Fold 時序交叉驗證:")
    n_folds = 5
    fold_size = (N - MIN_TRAIN) // n_folds

    for sname in ['S1_Fourier', 'S3_Markov', 'S2_DevEcho', 'F1_Voting']:
        sfn = STRATEGIES[sname]
        fold_edges = []
        for fold in range(n_folds):
            f_start = MIN_TRAIN + fold * fold_size
            f_end = f_start + fold_size
            ge2 = 0; cnt = 0
            for i in range(f_start, min(f_end, N)):
                history = draws[:i]
                prediction = sfn(history)
                actual = set(draws[i]['numbers'])
                if len(set(prediction) & actual) >= 2: ge2 += 1
                cnt += 1
            if cnt > 0: fold_edges.append(ge2/cnt - BASELINE_GE2)

        fe = np.array(fold_edges)
        print(f"    {sname:20s} | Folds: {[f'{e*100:+.2f}%' for e in fe]} | Mean={fe.mean()*100:+.3f}% | Std={fe.std()*100:.3f}%")

    # ══════════════════════════════════
    # STEP 7: 蒙地卡羅模擬
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 7: 蒙地卡羅模擬 (100,000 次)")
    print("═"*80)

    MC_RUNS = 100000
    rng_mc = np.random.RandomState(42)

    # 7.1 隨機 baseline 精確計算
    mc_ge2 = 0; mc_ge3 = 0; mc_hits = []
    for _ in range(MC_RUNS):
        pred = sorted(rng_mc.choice(range(1, POOL+1), size=PICK, replace=False))
        actual_idx = rng_mc.randint(0, N)
        actual = draws[actual_idx]['numbers']
        h = len(set(pred) & set(actual))
        mc_hits.append(h)
        if h >= 2: mc_ge2 += 1
        if h >= 3: mc_ge3 += 1

    mc_ge2_rate = mc_ge2 / MC_RUNS
    mc_ge3_rate = mc_ge3 / MC_RUNS
    mc_hits = np.array(mc_hits)

    print(f"\n7.1 隨機 Baseline (Monte Carlo {MC_RUNS:,} 次):")
    print(f"    ≥2 Rate: {mc_ge2_rate*100:.4f}% (理論: {BASELINE_GE2*100:.4f}%)")
    print(f"    ≥3 Rate: {mc_ge3_rate*100:.4f}% (理論: {BASELINE_GE3*100:.4f}%)")
    print(f"    Avg Hits: {mc_hits.mean():.4f} (理論: {PICK*PICK/POOL:.4f})")

    # 7.2 每個策略 vs 隨機的統計檢定
    print(f"\n7.2 策略 vs 隨機 (Z-test + 信賴區間):")
    print(f"\n{'策略':<20s} | {'≥2 Rate':>8s} | {'Edge':>8s} | {'Z-score':>8s} | {'p-value':>10s} | {'95% CI':>20s} | 判定")
    print(f"{'─'*20} | {'─'*8} | {'─'*8} | {'─'*8} | {'─'*10} | {'─'*20} | {'─'*15}")

    for sname, r in sorted_results:
        rate = r['ge2_rate']
        edge = r['ge2_edge']
        n_t = r['n_test']
        # Z-test: H0: rate = BASELINE_GE2
        se = np.sqrt(BASELINE_GE2 * (1 - BASELINE_GE2) / n_t)
        z = edge / se if se > 0 else 0
        p = 2 * (1 - sp_stats.norm.cdf(abs(z)))  # 雙尾
        # 95% CI for rate
        se_rate = np.sqrt(rate * (1 - rate) / n_t)
        ci_low = rate - 1.96 * se_rate
        ci_high = rate + 1.96 * se_rate

        sig = ""
        if p < 0.001: sig = "✅✅✅"
        elif p < 0.01: sig = "✅✅"
        elif p < 0.05: sig = "✅"
        else: sig = "❌ n.s."

        print(f"{sname:<20s} | {rate*100:7.3f}% | {edge*100:+7.3f}% | {z:+8.3f} | {p:10.6f} | [{ci_low*100:.2f}%, {ci_high*100:.2f}%] | {sig}")

    # 7.3 多注策略 MC
    print(f"\n7.3 多注策略 Monte Carlo 比較:")
    multi_configs = [
        ('2bet_Fourier+Markov', [STRATEGIES['S1_Fourier'], STRATEGIES['S3_Markov']]),
        ('3bet_F+M+DevE', [STRATEGIES['S1_Fourier'], STRATEGIES['S3_Markov'], STRATEGIES['S2_DevEcho']]),
    ]
    for mname, methods in multi_configs:
        n_bets = len(methods)
        bl = 1 - (1 - BASELINE_GE2)**n_bets
        ge2 = 0; cnt = 0
        for i in range(start_idx, N):
            history = draws[:i]
            actual = set(draws[i]['numbers'])
            best = 0
            for m in methods:
                hits = len(set(m(history)) & actual)
                best = max(best, hits)
            if best >= 2: ge2 += 1
            cnt += 1
        rate = ge2/cnt
        edge = rate - bl
        se = np.sqrt(bl*(1-bl)/cnt)
        z = edge/se if se > 0 else 0
        p = 2*(1-sp_stats.norm.cdf(abs(z)))
        print(f"    {mname:<25s} | Rate={rate*100:.3f}% | Baseline={bl*100:.3f}% | Edge={edge*100:+.3f}% | z={z:+.2f} | p={p:.4f}")

    # ══════════════════════════════════
    # STEP 8 Summary
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 8: 模型融合結果彙整")
    print("═"*80)

    fusion_methods = ['F1_Voting', 'F2_WeightedVote', 'F3_Stacking', 'F4_Regime']
    print(f"\n{'融合方法':<20s} | {'≥2 Edge':>8s} | {'≥3 Edge':>8s} | {'Sharpe':>7s} | {'vs 最佳單模型':>15s}")
    print(f"{'─'*20} | {'─'*8} | {'─'*8} | {'─'*7} | {'─'*15}")
    best_single_edge = max(r['ge2_edge'] for sname, r in results.items() if not sname.startswith('F'))
    for sname in fusion_methods:
        r = results[sname]
        vs_best = "✅ 優於" if r['ge2_edge'] > best_single_edge else "❌ 未超越"
        print(f"{sname:<20s} | {r['ge2_edge']*100:+7.3f}% | {r['ge3_edge']*100:+7.4f}% | {r['sharpe']:+7.3f} | {vs_best}")

    # ══════════════════════════════════
    # STEP 9: 最終排名
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 9: 最終排名系統")
    print("═"*80)

    # 計算綜合分數
    final_ranking = []
    for sname, r in results.items():
        # 綜合分: 0.4×edge_z + 0.3×sharpe + 0.2×stability + 0.1×consistency
        se = np.sqrt(BASELINE_GE2 * (1-BASELINE_GE2) / r['n_test'])
        z = r['ge2_edge'] / se if se > 0 else 0
        p = 2 * (1 - sp_stats.norm.cdf(abs(z)))

        # 穩定度: |sharpe|
        stability = abs(r['sharpe'])

        # 過擬合判定
        is_overfit = r['ge2_edge'] > 0 and p > 0.10

        composite = 0.4 * max(0, z) + 0.3 * max(0, r['sharpe']) + 0.2 * stability + 0.1 * (1 if r['ge2_edge'] > 0 else 0)

        final_ranking.append({
            'name': sname,
            'ge2_rate': r['ge2_rate'],
            'ge2_edge': r['ge2_edge'],
            'sharpe': r['sharpe'],
            'z_score': z,
            'p_value': p,
            'stability': stability,
            'overfit': is_overfit,
            'composite': composite,
            'recommend': '★' if r['ge2_edge'] > 0 and p < 0.10 and not is_overfit else ''
        })

    final_ranking.sort(key=lambda x: -x['composite'])

    print(f"\n{'#':>2s} | {'方法':<20s} | {'命中率':>8s} | {'Edge':>8s} | {'Sharpe':>7s} | {'Z':>6s} | {'p-value':>8s} | {'過擬合':>6s} | {'推薦度':>6s}")
    print(f"{'─'*2} | {'─'*20} | {'─'*8} | {'─'*8} | {'─'*7} | {'─'*6} | {'─'*8} | {'─'*6} | {'─'*6}")

    for i, r in enumerate(final_ranking):
        of_mark = "⚠️" if r['overfit'] else "✅"
        sig_mark = ""
        if r['p_value'] < 0.01: sig_mark = "★★★"
        elif r['p_value'] < 0.05: sig_mark = "★★"
        elif r['p_value'] < 0.10: sig_mark = "★"
        else: sig_mark = "—"

        print(f"{i+1:2d} | {r['name']:<20s} | {r['ge2_rate']*100:7.3f}% | {r['ge2_edge']*100:+7.3f}% | {r['sharpe']:+7.3f} | {r['z_score']:+6.2f} | {r['p_value']:8.4f} | {of_mark:<6s} | {sig_mark}")

    # ══════════════════════════════════
    # STEP 10: 最終結論
    # ══════════════════════════════════
    print("\n" + "═"*80)
    print("STEP 10: 研究級最終結論")
    print("═"*80)

    # 找出通過所有門檻的策略
    passing = [r for r in final_ranking if r['ge2_edge'] > 0 and r['p_value'] < 0.05]

    print(f"\n① 是否存在真正可提升中獎率的方法？")
    if passing:
        print(f"   有條件的是 — {len(passing)} 個方法在 p<0.05 下有正 Edge:")
        for r in passing:
            print(f"     • {r['name']}: Edge={r['ge2_edge']*100:+.3f}%, p={r['p_value']:.4f}")
    else:
        sig_01 = [r for r in final_ranking if r['ge2_edge'] > 0 and r['p_value'] < 0.10]
        if sig_01:
            print(f"   邊界 — {len(sig_01)} 個方法在 p<0.10 下有弱訊號:")
            for r in sig_01:
                print(f"     • {r['name']}: Edge={r['ge2_edge']*100:+.3f}%, p={r['p_value']:.4f}")
        else:
            print(f"   否 — 沒有任何方法達到統計顯著水準 (p<0.10)")

    print(f"\n② 最佳策略:")
    if final_ranking:
        best = final_ranking[0]
        print(f"   {best['name']} (Edge={best['ge2_edge']*100:+.3f}%, Sharpe={best['sharpe']:+.3f}, p={best['p_value']:.4f})")

    print(f"\n③ 若不存在有效方法，原因:")
    print(f"   • 隨機性檢定: {randomness_tests_passed}/6 項通過 — 39樂合彩序列本質上是隨機過程")
    print(f"   • 條件熵: MI(X_t, X_{{t-1}}) ≈ 0.0001 — 幾乎無時序依賴")
    print(f"   • 樣本空間: C(39,5)=575,757 組合 — 每注覆蓋不足 0.0002%")
    print(f"   • P3 Shuffle: 最佳 p=0.085 — 時序破壞後 edge 幾乎不變")

    print(f"\n④ 心理錯覺方法 (偽規律):")
    illusions = [r for r in final_ranking if r['ge2_edge'] > 0 and r['p_value'] > 0.20]
    for r in illusions[:5]:
        print(f"     • {r['name']}: 看似 Edge={r['ge2_edge']*100:+.3f}% 但 p={r['p_value']:.4f} (不顯著)")

    print(f"\n⑤ 已被統計否證的方法:")
    disproved = [r for r in final_ranking if r['ge2_edge'] < 0]
    for r in disproved:
        print(f"     ✖ {r['name']}: Edge={r['ge2_edge']*100:+.3f}% (比隨機差)")

    # 時間
    elapsed = (datetime.now() - t0).total_seconds()
    print(f"\n{'═'*80}")
    print(f"完成。耗時: {elapsed:.1f} 秒")
    print(f"{'═'*80}")

    # 保存
    output = {
        'meta': {
            'steps': '4-8',
            'total_draws': N,
            'test_periods': N - start_idx,
            'baselines': {'ge2': BASELINE_GE2, 'ge3': BASELINE_GE3},
            'randomness_tests_passed': randomness_tests_passed,
            'timestamp': datetime.now().isoformat()
        },
        'randomness': {
            'chi2_p': p_chi2,
            'ks_stat': ks_stat,
            'autocorr_significant_pct': significant_autocorr/total_tests,
            'runs_significant': sig_runs,
            'nist_monobit_p': p_monobit,
            'nist_block_p': float(p_block)
        },
        'rankings': [{k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                      for k, v in r.items()} for r in final_ranking]
    }
    out_path = os.path.join(os.path.dirname(__file__), '..', 'research_39lotto_step4_8.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"💾 {out_path}")


if __name__ == '__main__':
    main()
