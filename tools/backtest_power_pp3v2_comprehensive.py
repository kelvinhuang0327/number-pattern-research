#!/usr/bin/env python3
"""
威力彩 PP3v2 綜合回測 — 三策略三窗口驗證
==========================================
基於115000019期檢討，測試三個改進方向：

  策略A: PP3-EchoBoost
    Fourier 打分時對 Lag-1 Echo 號碼加乘信心分
    假說：當期開獎號碼有明顯 lag-1 回聲特性，提升 Fourier 召回率

  策略B: PP3-Z3Gap
    Bet3 改為 Z3(26-38) 高 Gap 注入，取代 Echo/Cold
    假說：Z3 高 Gap 號碼回歸概率高於隨機冷號

  策略C: PP3v2 (Combined)
    策略A + 策略B 合體
    假說：兩個改進獨立正交，聯合可疊加 Edge

基準：PP3 baseline = 11.17% (M3+, 3注隨機期望)
PP3 已知 Edge：+2.30% (1500期)

回測框架：
  - 三窗口：150 / 500 / 1500 期
  - Permutation Test: N=200
  - Walk-forward (無數據洩漏)
  - 對比 PP3 baseline 以及 Random baseline
"""
import os
import sys
import json
import random
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from lottery_api.database import DatabaseManager

BASELINE_3BET = 11.17  # 威力彩 3注 M3+ 隨機基準
MAX_NUM = 38
PERM_N = 200
WINDOWS = [150, 500, 1500]

# ===========================================================
# 核心 Fourier 打分
# ===========================================================

def get_fourier_scores(history, window=500):
    """返回每個號碼的 Fourier 信心分（越高越接近主導週期）"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = np.array([1 if n in d['numbers'] else 0 for d in h_slice], dtype=float)
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        last_hit_idx = np.where(bh == 1)[0]
        if len(last_hit_idx) == 0:
            continue
        last_hit = last_hit_idx[-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores

def get_fourier_rank_plain(history, window=500):
    """原始 Fourier rank（對應現有 PP3 Bet1/Bet2）"""
    scores = get_fourier_scores(history, window)
    return np.argsort(scores)[::-1]

def get_fourier_rank_echo_boost(history, window=500, boost=1.5):
    """Lag-1 Echo Boost: Fourier 打分後，對 lag-1 號碼乘以 boost 係數"""
    scores = get_fourier_scores(history, window)
    # lag-1 echo: 上一期開獎號碼
    if len(history) >= 1:
        lag1 = history[-1]['numbers']
        for n in lag1:
            if 1 <= n <= MAX_NUM:
                scores[n] *= boost
    return np.argsort(scores)[::-1]

# ===========================================================
# Bet3 方案
# ===========================================================

def bet3_echo_cold(history, exclude):
    """原始 PP3 Bet3: Lag-2 Echo + Cold Fill"""
    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers'] if n <= MAX_NUM])
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    return sorted((echo_nums + remaining)[:6])

def bet3_z3_gap(history, exclude, lookback=30):
    """Z3 Gap 注入 Bet3: 選 Z3(26-38) 中 gap 最大的號碼"""
    z3_nums = [n for n in range(26, MAX_NUM + 1) if n not in exclude]
    if not z3_nums:
        # Z3 全被占用，fallback 到 cold
        return bet3_echo_cold(history, exclude)

    # 計算每個 Z3 號碼的 gap（距離上次出現的期數）
    recent = history[-lookback:] if len(history) >= lookback else history
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    L = len(recent)
    gaps = {}
    for n in z3_nums:
        if n in last_seen:
            gaps[n] = (L - 1) - last_seen[n]
        else:
            gaps[n] = L  # 從未出現，gap = 窗口長度

    z3_sorted = sorted(z3_nums, key=lambda x: -gaps[x])

    # 盡量取 Z3 高 Gap 號碼，不夠則用 all-domain gap 補足
    bet = z3_sorted[:6]
    if len(bet) < 6:
        non_z3 = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in set(bet)]
        non_z3_gaps = {}
        for n in non_z3:
            if n in last_seen:
                non_z3_gaps[n] = (L - 1) - last_seen[n]
            else:
                non_z3_gaps[n] = L
        non_z3_sorted = sorted(non_z3, key=lambda x: -non_z3_gaps[x])
        bet = sorted((bet + non_z3_sorted)[:6])
    return sorted(bet[:6])

# ===========================================================
# 三策略預測函數
# ===========================================================

def pp3_baseline(history):
    """原始 PP3（作為對照，驗證一致性）"""
    f_rank = get_fourier_rank_plain(history)
    idx = 0
    while idx < len(f_rank) and f_rank[idx] == 0:
        idx += 1
    bet1 = sorted(f_rank[idx:idx + 6].tolist())
    idx2 = idx + 6
    while idx2 < len(f_rank) and f_rank[idx2] == 0:
        idx2 += 1
    bet2 = sorted(f_rank[idx2:idx2 + 6].tolist())
    exclude = set(bet1) | set(bet2)
    bet3 = bet3_echo_cold(history, exclude)
    return [bet1, bet2, bet3]

def pp3_echo_boost(history, boost=1.5):
    """策略A: Fourier + Lag-1 Echo Boost"""
    f_rank = get_fourier_rank_echo_boost(history, boost=boost)
    idx = 0
    while idx < len(f_rank) and f_rank[idx] == 0:
        idx += 1
    bet1 = sorted(f_rank[idx:idx + 6].tolist())
    idx2 = idx + 6
    while idx2 < len(f_rank) and f_rank[idx2] == 0:
        idx2 += 1
    bet2 = sorted(f_rank[idx2:idx2 + 6].tolist())
    exclude = set(bet1) | set(bet2)
    bet3 = bet3_echo_cold(history, exclude)
    return [bet1, bet2, bet3]

def pp3_z3gap(history):
    """策略B: PP3 + Z3 Gap Bet3"""
    f_rank = get_fourier_rank_plain(history)
    idx = 0
    while idx < len(f_rank) and f_rank[idx] == 0:
        idx += 1
    bet1 = sorted(f_rank[idx:idx + 6].tolist())
    idx2 = idx + 6
    while idx2 < len(f_rank) and f_rank[idx2] == 0:
        idx2 += 1
    bet2 = sorted(f_rank[idx2:idx2 + 6].tolist())
    exclude = set(bet1) | set(bet2)
    bet3 = bet3_z3_gap(history, exclude)
    return [bet1, bet2, bet3]

def pp3_v2_combined(history, boost=1.5):
    """策略C: PP3v2 = Echo Boost Fourier + Z3 Gap Bet3"""
    f_rank = get_fourier_rank_echo_boost(history, boost=boost)
    idx = 0
    while idx < len(f_rank) and f_rank[idx] == 0:
        idx += 1
    bet1 = sorted(f_rank[idx:idx + 6].tolist())
    idx2 = idx + 6
    while idx2 < len(f_rank) and f_rank[idx2] == 0:
        idx2 += 1
    bet2 = sorted(f_rank[idx2:idx2 + 6].tolist())
    exclude = set(bet1) | set(bet2)
    bet3 = bet3_z3_gap(history, exclude)
    return [bet1, bet2, bet3]

# ===========================================================
# 回測引擎
# ===========================================================

def is_m3_plus(bets, actual_set):
    """任一注中3號以上 → M3+"""
    for bet in bets:
        if len(set(bet) & actual_set) >= 3:
            return True
    return False

def run_window_backtest(all_draws, func, window_size, label=""):
    """單窗口回測，返回 (hit_rate, edge, hits, total)"""
    n = len(all_draws)
    # 使用最新的 window_size 期，需要至少 warm-up=500 期歷史
    warmup = 500
    start = max(warmup, n - window_size)
    test_draws = all_draws[start:]
    hits = 0
    total = len(test_draws)

    for i in range(total):
        history = all_draws[:start + i]
        actual = set(test_draws[i]['numbers'])
        try:
            bets = func(history)
            if is_m3_plus(bets, actual):
                hits += 1
        except Exception:
            pass

    hit_rate = hits / total * 100 if total > 0 else 0
    edge = hit_rate - BASELINE_3BET
    return hit_rate, edge, hits, total

def permutation_test(all_draws, func, window_size, n_perm=PERM_N, observed_edge=None):
    """
    Permutation test: shuffle labels，計算 p-value
    H0: 策略無效（Edge ≤ 0）
    """
    warmup = 500
    n = len(all_draws)
    start = max(warmup, n - window_size)
    test_draws = all_draws[start:]
    total = len(test_draws)

    if observed_edge is None:
        hits = 0
        for i in range(total):
            history = all_draws[:start + i]
            actual = set(test_draws[i]['numbers'])
            try:
                bets = func(history)
                if is_m3_plus(bets, actual):
                    hits += 1
            except Exception:
                pass
        observed_edge = hits / total * 100 - BASELINE_3BET

    # 收集策略預測結果（固定預測，只 shuffle 答案）
    preds = []
    for i in range(total):
        history = all_draws[:start + i]
        try:
            bets = func(history)
            preds.append(bets)
        except Exception:
            preds.append([[]])

    actuals = [set(d['numbers']) for d in test_draws]

    # 記錄 observed hit indicator
    obs_hits_arr = [1 if is_m3_plus(preds[i], actuals[i]) else 0 for i in range(total)]
    obs_hit_rate = sum(obs_hits_arr) / total * 100
    obs_edge_check = obs_hit_rate - BASELINE_3BET

    exceed_count = 0
    for _ in range(n_perm):
        shuffled = actuals.copy()
        random.shuffle(shuffled)
        perm_hits = sum(1 for i in range(total) if is_m3_plus(preds[i], shuffled[i]))
        perm_edge = perm_hits / total * 100 - BASELINE_3BET
        if perm_edge >= obs_edge_check:
            exceed_count += 1

    p_value = exceed_count / n_perm
    return p_value, obs_edge_check

# ===========================================================
# 主程式
# ===========================================================

def main():
    print("=" * 70)
    print("  威力彩 PP3v2 綜合回測 — 三策略三窗口驗證")
    print("  基準: PP3 (+2.30%) vs Random (11.17%)")
    print("=" * 70)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"  載入 POWER_LOTTO: {len(all_draws)} 期 (截至 {all_draws[-1]['date']})\n")

    strategies = [
        ("PP3-Baseline",   pp3_baseline),
        ("PP3-EchoBoost",  pp3_echo_boost),
        ("PP3-Z3Gap",      pp3_z3gap),
        ("PP3v2-Combined", pp3_v2_combined),
    ]

    results = {}

    for name, func in strategies:
        print(f"\n{'─'*70}")
        print(f"  策略: {name}")
        print(f"{'─'*70}")
        window_results = {}
        for w in WINDOWS:
            actual_w = min(w, len(all_draws) - 500)
            if actual_w <= 0:
                print(f"  窗口 {w:4d}p: 資料不足，跳過")
                continue
            print(f"  窗口 {w:4d}p: 計算中...", end="", flush=True)
            hr, edge, hits, total = run_window_backtest(all_draws, func, actual_w)
            print(f" 命中率={hr:.2f}%  Edge={edge:+.2f}%  [{hits}/{total}]")
            window_results[w] = {"hit_rate": hr, "edge": edge, "hits": hits, "total": total}
        results[name] = window_results

    # Permutation Test（1500 期窗口，代表性最強）
    print(f"\n{'─'*70}")
    print("  Permutation Test (N=200, 窗口=1500期)")
    print(f"{'─'*70}")
    perm_results = {}
    for name, func in strategies:
        actual_w = min(1500, len(all_draws) - 500)
        if actual_w <= 0:
            continue
        obs_edge = results[name].get(1500, {}).get("edge", None) or \
                   results[name].get(min(WINDOWS, key=lambda x: abs(x - 1500)), {}).get("edge", 0)
        print(f"  {name:22s}: ", end="", flush=True)
        p_val, _ = permutation_test(all_draws, func, actual_w, n_perm=PERM_N, observed_edge=obs_edge)
        sig = "✅ SIGNIFICANT" if p_val < 0.05 else ("⚠️ MARGINAL" if p_val < 0.10 else "❌ NOT SIG")
        print(f"p={p_val:.3f}  {sig}")
        perm_results[name] = p_val

    # 三窗口一致性評估
    print(f"\n{'═'*70}")
    print("  三窗口一致性檢驗 (所有窗口 Edge > 0 才算 STABLE)")
    print(f"{'═'*70}")
    print(f"  {'策略':<22} {'150p':>8} {'500p':>8} {'1500p':>8} {'穩定性':<20} {'Perm p'}")
    print(f"  {'─'*22} {'─'*8} {'─'*8} {'─'*8} {'─'*20} {'─'*8}")

    final_results = {}
    for name, _ in strategies:
        wr = results.get(name, {})
        e150  = wr.get(150,  {}).get("edge", None)
        e500  = wr.get(500,  {}).get("edge", None)
        e1500 = wr.get(1500, {}).get("edge", None)
        p = perm_results.get(name, 1.0)

        def fmt(v):
            if v is None: return "  N/A "
            return f"{v:+.2f}%"

        all_pos = all(v is not None and v > 0 for v in [e150, e500, e1500])
        if all_pos and p < 0.05:
            stability = "✅ STABLE"
        elif all_pos and p < 0.10:
            stability = "⚠️ MARGINAL"
        elif all_pos:
            stability = "⚠️ WEAK (p≮0.10)"
        else:
            stability = "❌ INCONSISTENT"

        print(f"  {name:<22} {fmt(e150):>8} {fmt(e500):>8} {fmt(e1500):>8} {stability:<20} p={p:.3f}")
        final_results[name] = {
            "e150": e150, "e500": e500, "e1500": e1500,
            "perm_p": p, "stability": stability
        }

    # 決策輸出
    print(f"\n{'═'*70}")
    print("  決策摘要")
    print(f"{'═'*70}")
    for name, fr in final_results.items():
        stab = fr["stability"]
        print(f"  {name:<22}: {stab}")

    # 保存結果
    out = {
        "timestamp": str(np.datetime64("now")),
        "total_draws": len(all_draws),
        "baseline": BASELINE_3BET,
        "windows": WINDOWS,
        "perm_n": PERM_N,
        "strategies": final_results,
        "window_details": results,
        "perm_results": perm_results
    }
    out_path = os.path.join(project_root, "backtest_power_pp3v2_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已保存: {out_path}")
    print("=" * 70)

if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)
    main()
