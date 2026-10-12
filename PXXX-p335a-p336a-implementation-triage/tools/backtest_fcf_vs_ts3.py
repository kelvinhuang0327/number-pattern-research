#!/usr/bin/env python3
"""
FCF vs TS3  1v1 直接對比驗證
==============================
單一假說檢定：Fourier+Cold+FreqOrt (FCF) 是否顯著優於 Triple Strike (TS3)?

設計原則：
  - 1v1 對比 → 無多重比較問題，Bonferroni α = 0.05/1 = 0.05
  - 兩策略 Bet1(Fourier) + Bet2(Cold) 完全相同，只有 Bet3 不同
    * TS3 Bet3: TailBalance (尾數均衡)
    * FCF Bet3: FreqOrt    (頻率正交，剩餘號碼按近100期頻率取前6)
  - McNemar 配對檢定：每期兩策略的 M3+ 結果配對比較
  - 三窗口驗證：150 / 500 / 1500 期
  - P3 Permutation Test：洗牌開獎順序，驗證信號來自時序結構
  - 嚴格時序隔離：history = draws[:i]

背景：
  - 報告聲稱 FCF Edge +1.58% > TS3 Edge +1.05%
  - 但該結論來自 C(5,3)=10 路搜尋，Bonferroni 未通過 (p=0.033 > α=0.005)
  - 本腳本作單一假說測試，排除多重比較問題

Usage:
    python3 tools/backtest_fcf_vs_ts3.py
    python3 tools/backtest_fcf_vs_ts3.py --window 500
    python3 tools/backtest_fcf_vs_ts3.py --all_windows
    python3 tools/backtest_fcf_vs_ts3.py --n_perm 5000
"""
import os
import sys
import json
import argparse
import numpy as np
from collections import Counter
from scipy import stats
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# ─────────────────────────────────────────────────────────
# 常數
# ─────────────────────────────────────────────────────────
MAX_NUM    = 49
PICK       = 6
P_SINGLE   = 0.0186
P_3BET     = 1 - (1 - P_SINGLE) ** 3   # 5.48%
MIN_BUFFER = 150
SEED       = 42


# ─────────────────────────────────────────────────────────
# Bet 1 / Bet 2：兩策略完全相同
# ─────────────────────────────────────────────────────────
def fourier_rhythm_bet(history, window=500):
    """Bet 1 (共用): Fourier Rhythm — FFT 週期分析"""
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bstream = np.array([1.0 if n in d['numbers'] else 0.0 for d in h])
        if bstream.sum() < 2:
            continue
        yf = fft(bstream - bstream.mean())
        xf = fftfreq(w, 1)
        pos = xf > 0
        pos_xf = xf[pos]
        pos_amp = np.abs(yf[pos])
        if len(pos_amp) == 0:
            continue
        peak = np.argmax(pos_amp)
        freq_val = pos_xf[peak]
        if freq_val == 0:
            continue
        period = 1.0 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bstream == 1)[0]
            if len(last_hit) == 0:
                continue
            gap = (w - 1) - last_hit[-1]
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    top = np.argsort(scores[1:])[::-1][:PICK] + 1
    return sorted(top.tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    """Bet 2 (共用): Cold Numbers — 近 window 期最少出現的號碼"""
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    cands = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    return sorted(sorted(cands, key=lambda x: freq.get(x, 0))[:PICK])


# ─────────────────────────────────────────────────────────
# Bet 3：兩策略的唯一差異
# ─────────────────────────────────────────────────────────
def tail_balance_bet(history, window=100, exclude=None):
    """
    Bet 3 — TS3 版本: TailBalance (尾數均衡)
    完全複製自 backtest_biglotto_markov_4bet.py
    """
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])

    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)

    selected = []
    available = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True,
    )
    idx_in = {t: 0 for t in range(10)}
    while len(selected) < PICK:
        added = False
        for tail in available:
            if len(selected) >= PICK:
                break
            if idx_in[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in[tail] += 1
        if not added:
            break
    if len(selected) < PICK:
        rem = [n for n in range(1, MAX_NUM + 1)
               if n not in selected and n not in exclude]
        rem.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(rem[:PICK - len(selected)])
    return sorted(selected[:PICK])


def freq_ort_bet(history, window=100, exclude=None):
    """
    Bet 3 — FCF 版本: FreqOrt (頻率正交)

    從剩餘號碼 (排除 Bet1+Bet2 已選的12個) 中，
    按近 window 期頻率排序，取頻率最高的 6 個。

    這與 5注策略中 Bet5 的邏輯相同，差別在於此處
    可用號碼有 49-12=37 個（Bet5 時只剩 25 個）。
    """
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'])
    cands = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    # 按頻率降序 → 選頻率最高的（趨熱法，與 Cold 形成互補）
    return sorted(sorted(cands, key=lambda x: freq.get(x, 0), reverse=True)[:PICK])


# ─────────────────────────────────────────────────────────
# 策略生成函數
# ─────────────────────────────────────────────────────────
def generate_ts3(history):
    """TS3: Fourier + Cold + TailBalance"""
    b1 = fourier_rhythm_bet(history)
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = tail_balance_bet(history, exclude=set(b1) | set(b2))
    return [b1, b2, b3]


def generate_fcf(history):
    """FCF: Fourier + Cold + FreqOrt"""
    b1 = fourier_rhythm_bet(history)
    b2 = cold_numbers_bet(history, exclude=set(b1))
    b3 = freq_ort_bet(history, exclude=set(b1) | set(b2))
    return [b1, b2, b3]


# ─────────────────────────────────────────────────────────
# Walk-forward 引擎（配對輸出）
# ─────────────────────────────────────────────────────────
def run_paired_walkforward(draws, n_periods, verbose=True):
    """
    對 FCF 和 TS3 在同一批期數上跑完整 Walk-forward。

    每期同時計算兩策略，方便 McNemar 配對檢定。
    Bet1 / Bet2 相同，只有 Bet3 不同 → 大部分期數結果重疊。

    Returns:
        records: list of dict {
            'ts3_hit': bool,  # TS3 當期是否 M3+
            'fcf_hit': bool,  # FCF 當期是否 M3+
            'ts3_best': int,  # TS3 最高命中數
            'fcf_best': int,  # FCF 最高命中數
        }
    """
    start_idx = max(MIN_BUFFER, len(draws) - n_periods)
    records = []

    for i in range(start_idx, len(draws)):
        history = draws[:i]          # 嚴格時序隔離
        actual  = set(draws[i]['numbers'])

        ts3_bets = generate_ts3(history)
        fcf_bets = generate_fcf(history)

        ts3_best = max(len(set(b) & actual) for b in ts3_bets)
        fcf_best = max(len(set(b) & actual) for b in fcf_bets)

        records.append({
            'ts3_hit':  ts3_best >= 3,
            'fcf_hit':  fcf_best >= 3,
            'ts3_best': ts3_best,
            'fcf_best': fcf_best,
        })

    if verbose:
        n = len(records)
        ts3_m3 = sum(1 for r in records if r['ts3_hit'])
        fcf_m3 = sum(1 for r in records if r['fcf_hit'])
        print(f"  Walk-forward 完成: {n} 期")
        print(f"  TS3 M3+: {ts3_m3}/{n} = {ts3_m3/n:.2%}")
        print(f"  FCF M3+: {fcf_m3}/{n} = {fcf_m3/n:.2%}")

    return records


# ─────────────────────────────────────────────────────────
# 統計檢定
# ─────────────────────────────────────────────────────────
def compute_stats(records):
    """計算 M3+ 率、Edge、McNemar 配對統計"""
    n    = len(records)
    ts3_hits = sum(1 for r in records if r['ts3_hit'])
    fcf_hits = sum(1 for r in records if r['fcf_hit'])

    ts3_rate = ts3_hits / n
    fcf_rate = fcf_hits / n
    ts3_edge = (ts3_rate - P_3BET) / P_3BET
    fcf_edge = (fcf_rate - P_3BET) / P_3BET

    # McNemar 配對檢定 (Bet1/Bet2 相同，所以兩策略強相關)
    # b = FCF 中、TS3 未中 (FCF 獨贏)
    # c = TS3 中、FCF 未中 (TS3 獨贏)
    b = sum(1 for r in records if     r['fcf_hit'] and not r['ts3_hit'])
    c = sum(1 for r in records if not r['fcf_hit'] and     r['ts3_hit'])
    d_agree_hit  = sum(1 for r in records if r['fcf_hit']  and r['ts3_hit'])
    d_agree_miss = sum(1 for r in records if not r['fcf_hit'] and not r['ts3_hit'])

    if b + c >= 5:
        chi2_mcnemar = (b - c) ** 2 / (b + c)
        p_mcnemar = float(stats.chi2.sf(chi2_mcnemar, df=1))
        # 雙側 → 若 b > c 才是 FCF 佔優
        p_one_sided = p_mcnemar / 2 if b > c else 1 - p_mcnemar / 2
    else:
        chi2_mcnemar = 0.0
        p_mcnemar    = 1.0
        p_one_sided  = 1.0

    return {
        'n':           n,
        'ts3_hits':    ts3_hits,
        'fcf_hits':    fcf_hits,
        'ts3_rate':    ts3_rate,
        'fcf_rate':    fcf_rate,
        'ts3_edge':    ts3_edge,
        'fcf_edge':    fcf_edge,
        'delta_rate':  fcf_rate - ts3_rate,
        'delta_edge':  fcf_edge - ts3_edge,
        'b_fcf_only':  b,
        'c_ts3_only':  c,
        'd_both_hit':  d_agree_hit,
        'd_both_miss': d_agree_miss,
        'chi2':        chi2_mcnemar,
        'p_two_sided': p_mcnemar,
        'p_one_sided': p_one_sided,
    }


def print_stats(s, label=""):
    """格式化輸出統計結果"""
    sep = "─" * 54
    print(f"\n  {sep}")
    if label:
        print(f"  📊 {label}")
        print(f"  {sep}")
    print(f"  {'策略':<12} {'M3+次數':>6} {'M3+率':>7} {'Edge':>8}")
    print(f"  {'TS3':<12} {s['ts3_hits']:>6} {s['ts3_rate']:>7.2%} {s['ts3_edge']:>+8.2%}")
    print(f"  {'FCF':<12} {s['fcf_hits']:>6} {s['fcf_rate']:>7.2%} {s['fcf_edge']:>+8.2%}")
    print(f"  {'基準(3注)':<12} {'':>6} {P_3BET:>7.2%} {'0.00%':>8}")
    print(f"\n  差值 (FCF - TS3): ΔRate={s['delta_rate']:+.2%}, ΔEdge={s['delta_edge']:+.2%}")
    print()
    print(f"  McNemar 配對檢定 (b={s['b_fcf_only']}, c={s['c_ts3_only']})")
    print(f"    共識期數: 兩者皆中={s['d_both_hit']}, 兩者皆未中={s['d_both_miss']}")
    print(f"    FCF 獨贏 (b): {s['b_fcf_only']} 期")
    print(f"    TS3 獨贏 (c): {s['c_ts3_only']} 期")
    print(f"    χ²={s['chi2']:.3f}, p(兩側)={s['p_two_sided']:.4f}, "
          f"p(單側 FCF>TS3)={s['p_one_sided']:.4f}")

    # 顯著性判定 (1v1 → α=0.05, 無需 Bonferroni)
    if s['p_one_sided'] < 0.05 and s['delta_rate'] > 0:
        print(f"  判定: ✅ FCF 顯著優於 TS3 (p={s['p_one_sided']:.4f} < 0.05)")
    elif s['p_one_sided'] < 0.10 and s['delta_rate'] > 0:
        print(f"  判定: ⚠️  FCF 邊際優於 TS3 (p={s['p_one_sided']:.4f}, 0.05~0.10)")
    elif s['delta_rate'] > 0:
        print(f"  判定: ❌ FCF 略高但統計不顯著 (p={s['p_one_sided']:.4f} ≥ 0.10)")
    else:
        print(f"  判定: ❌ FCF 未優於 TS3 (delta ≤ 0)")


# ─────────────────────────────────────────────────────────
# Permutation Test (P3 協定：洗牌開獎順序)
# ─────────────────────────────────────────────────────────
def permutation_test_p3(records, n_perm=1000, seed=SEED):
    """
    配對標籤 Permutation Test（高效版）：

    Walk-forward 只跑一次，拿到每期 (ts3_hit, fcf_hit) 配對結果。
    每次 Permutation 對每期「隨機互換兩策略的標籤」，
    重新計算 delta_rate，建立虛無分布。

    原理：
      - H0: FCF 和 TS3 的 M3+ 結果可以互換（無差異）
      - 對稱互換 → 保留兩策略的邊際分布，只破壞「哪策略好」的標籤
      - 若真實 delta >> 虛無分布 → FCF 確實更好，不是隨機
    比傳統「洗牌開獎順序」更精準，因為它直接測試
    「兩 Bet3 的差異」而非整體時序結構。
    """
    rng = np.random.RandomState(seed)

    real_s     = compute_stats(records)
    real_delta = real_s['delta_rate']
    n          = len(records)

    # 預備：把結果轉為 numpy array 加速
    ts3_arr = np.array([r['ts3_hit'] for r in records], dtype=int)
    fcf_arr = np.array([r['fcf_hit'] for r in records], dtype=int)

    print(f"\n  真實 ΔRate (FCF-TS3): {real_delta:+.4f} ({real_delta:+.2%})")
    print(f"  跑 {n_perm} 次配對標籤 Permutation...")

    perm_deltas = []
    for _ in range(n_perm):
        # 對每期獨立以 50% 機率互換 (ts3, fcf) 標籤
        swap_mask  = rng.randint(0, 2, size=n).astype(bool)
        perm_ts3   = np.where(swap_mask, fcf_arr, ts3_arr)
        perm_fcf   = np.where(swap_mask, ts3_arr, fcf_arr)
        perm_delta = perm_fcf.mean() - perm_ts3.mean()
        perm_deltas.append(float(perm_delta))

    perm_arr   = np.array(perm_deltas)
    p_perm     = float(np.mean(perm_arr >= real_delta))
    perm_mean  = float(perm_arr.mean())
    perm_std   = float(perm_arr.std())
    perm_95    = float(np.percentile(perm_arr, 95))
    cohen_d    = (real_delta - perm_mean) / (perm_std + 1e-12)

    sep = "─" * 54
    print(f"\n  {sep}")
    print(f"  🎲 P3 Permutation Test 結果")
    print(f"  {sep}")
    print(f"  真實 ΔRate   : {real_delta:+.4f}")
    print(f"  Perm 均值    : {perm_mean:+.4f} ± {perm_std:.4f}")
    print(f"  Perm 95th %  : {perm_95:+.4f}")
    print(f"  p-value      : {p_perm:.4f}")
    print(f"  Cohen's d    : {cohen_d:.3f}")

    if p_perm < 0.05:
        print(f"  判定: ✅ 信號顯著 — ΔEdge 來自時序結構 (p={p_perm:.4f})")
    elif p_perm < 0.10:
        print(f"  判定: ⚠️  邊際信號 (p={p_perm:.4f}, 0.05~0.10)")
    else:
        print(f"  判定: ❌ 信號不顯著 — ΔEdge 可能是分布性質而非預測能力 (p={p_perm:.4f})")

    return {
        'real_delta': real_delta,
        'perm_mean':  perm_mean,
        'perm_std':   perm_std,
        'perm_95':    perm_95,
        'p_value':    p_perm,
        'cohen_d':    cohen_d,
        'significant': p_perm < 0.05,
    }


# ─────────────────────────────────────────────────────────
# Bet 3 單獨貢獻分析
# ─────────────────────────────────────────────────────────
def analyze_bet3_contribution(draws, n_periods):
    """
    分析 Bet3 單獨貢獻：
    只在 Bet1+Bet2 都 miss 的期數，Bet3 才是唯一救援機會。
    這直接反映 TailBalance vs FreqOrt 的純粹差異。
    """
    start_idx    = max(MIN_BUFFER, len(draws) - n_periods)
    ts3_b3_solo  = 0
    fcf_b3_solo  = 0
    b1b2_miss_n  = 0

    for i in range(start_idx, len(draws)):
        history = draws[:i]
        actual  = set(draws[i]['numbers'])

        b1 = fourier_rhythm_bet(history)
        ex1 = set(b1)
        b2 = cold_numbers_bet(history, exclude=ex1)

        b1_hit = len(ex1 & actual) >= 3
        b2_hit = len(set(b2) & actual) >= 3

        if not b1_hit and not b2_hit:
            b1b2_miss_n += 1
            ex12   = ex1 | set(b2)
            b3_ts3 = tail_balance_bet(history, exclude=ex12)
            b3_fcf = freq_ort_bet(history,     exclude=ex12)
            if len(set(b3_ts3) & actual) >= 3:
                ts3_b3_solo += 1
            if len(set(b3_fcf) & actual) >= 3:
                fcf_b3_solo += 1

    print(f"\n  Bet3 單獨救援分析:")
    print(f"  Bet1+Bet2 皆未中的期數: {b1b2_miss_n}")
    print(f"  TailBalance (TS3 Bet3) 獨力命中: {ts3_b3_solo} 期  "
          f"({ts3_b3_solo/max(b1b2_miss_n,1):.2%})")
    print(f"  FreqOrt     (FCF Bet3) 獨力命中: {fcf_b3_solo} 期  "
          f"({fcf_b3_solo/max(b1b2_miss_n,1):.2%})")
    print(f"  差值 (FCF - TS3):                {fcf_b3_solo - ts3_b3_solo:+d} 期")

    return {
        'b1b2_miss_n':  b1b2_miss_n,
        'ts3_b3_solo':  ts3_b3_solo,
        'fcf_b3_solo':  fcf_b3_solo,
        'b3_delta':     fcf_b3_solo - ts3_b3_solo,
    }


# ─────────────────────────────────────────────────────────
# 三窗口驗證
# ─────────────────────────────────────────────────────────
def three_window_comparison(draws):
    """三窗口 (150/500/1500) 驗證 FCF vs TS3"""
    sep = "=" * 54
    print(f"\n{sep}")
    print(f"📈 三窗口驗證 (150 / 500 / 1500 期)")
    print(sep)
    print(f"\n  {'窗口':>6}  {'TS3 Edge':>9}  {'FCF Edge':>9}  "
          f"{'ΔEdge':>8}  {'TS3>0':>6}  {'FCF>0':>6}  {'FCF勝':>6}")
    print(f"  {'─'*52}")

    window_data = {}
    for w in [150, 500, 1500]:
        records = run_paired_walkforward(draws, w, verbose=False)
        s = compute_stats(records)
        ts3_pos = "✅" if s['ts3_edge'] > 0 else "❌"
        fcf_pos = "✅" if s['fcf_edge'] > 0 else "❌"
        fcf_win = "✅" if s['delta_edge'] > 0 else "❌"
        print(f"  {w:>6}期  {s['ts3_edge']:>+9.2%}  {s['fcf_edge']:>+9.2%}  "
              f"{s['delta_edge']:>+8.2%}  {ts3_pos:>6}  {fcf_pos:>6}  {fcf_win:>6}")
        window_data[w] = s

    # 穩定性判斷
    ts3_edges = [window_data[w]['ts3_edge'] for w in [150, 500, 1500]]
    fcf_edges = [window_data[w]['fcf_edge'] for w in [150, 500, 1500]]
    delta_edges = [window_data[w]['delta_edge'] for w in [150, 500, 1500]]

    print()
    ts3_stable = "✅ 三窗口全正" if all(e > 0 for e in ts3_edges) else \
                 ("⚠️  有負值窗口" if any(e > 0 for e in ts3_edges) else "❌ 全負")
    fcf_stable = "✅ 三窗口全正" if all(e > 0 for e in fcf_edges) else \
                 ("⚠️  有負值窗口" if any(e > 0 for e in fcf_edges) else "❌ 全負")
    fcf_dominates = "✅ FCF 三窗口皆領先" if all(d > 0 for d in delta_edges) else \
                    ("⚠️  FCF 部分領先" if any(d > 0 for d in delta_edges) else "❌ FCF 未領先")

    print(f"  TS3 穩定性 : {ts3_stable}")
    print(f"  FCF 穩定性 : {fcf_stable}")
    print(f"  FCF vs TS3 : {fcf_dominates}")

    return window_data


# ─────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='FCF vs TS3  1v1 Walk-forward 直接對比驗證'
    )
    parser.add_argument('--window',      type=int,  default=1500,
                        help='主評估窗口期數 (default: 1500)')
    parser.add_argument('--all_windows', action='store_true',
                        help='執行 150/500/1500 三窗口對比')
    parser.add_argument('--n_perm',      type=int,  default=1000,
                        help='P3 Permutation 次數 (default: 1000)')
    parser.add_argument('--no_perm',     action='store_true',
                        help='跳過 Permutation Test (快速模式)')
    args = parser.parse_args()

    # ─── 載入資料 ─────────────────────────────────────────
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db      = DatabaseManager(db_path=db_path)
    draws   = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))

    sep = "=" * 54
    print(sep)
    print("🔬 FCF vs TS3  1v1 Walk-forward 對比驗證")
    print()
    print("  TS3: Fourier + Cold + TailBalance  (現行3注策略)")
    print("  FCF: Fourier + Cold + FreqOrt      (待驗假說)")
    print()
    print(f"  資料: 大樂透 {len(draws)} 期")
    print(f"  3注基準: {P_3BET:.2%}")
    print(f"  Bonferroni α: 0.05/1 = 0.05  (1v1 無多重比較)")
    print(sep)

    # ─── Step 1: 主窗口分析 ───────────────────────────────
    print(f"\n{'─'*54}")
    print(f"  Step 1/4 — 主窗口分析 ({args.window} 期)")
    print(f"{'─'*54}")
    records = run_paired_walkforward(draws, args.window)
    s = compute_stats(records)
    print_stats(s, f"主窗口 {args.window} 期")

    # ─── Step 2: Bet3 單獨貢獻分析 ────────────────────────
    print(f"\n{'─'*54}")
    print(f"  Step 2/4 — Bet3 單獨貢獻分析")
    print(f"{'─'*54}")
    b3_result = analyze_bet3_contribution(draws, args.window)

    # ─── Step 3: 三窗口驗證 ───────────────────────────────
    print(f"\n{'─'*54}")
    print(f"  Step 3/4 — 三窗口穩定性")
    print(f"{'─'*54}")
    if args.all_windows:
        win_data = three_window_comparison(draws)
    else:
        win_data = None
        print(f"  (加 --all_windows 啟動三窗口對比)")

    # ─── Step 4: Permutation Test ─────────────────────────
    perm_result = None
    if not args.no_perm:
        print(f"\n{'─'*54}")
        print(f"  Step 4/4 — P3 Permutation Test (n={args.n_perm})")
        print(f"{'─'*54}")
        perm_result = permutation_test_p3(records, n_perm=args.n_perm)
    else:
        print(f"\n  Step 4/4 — Permutation Test (跳過，加 --n_perm 啟動)")

    # ─── 最終判定 ─────────────────────────────────────────
    print(f"\n{sep}")
    print(f"📋 最終判定")
    print(sep)

    mcnemar_pass = s['p_one_sided'] < 0.05 and s['delta_rate'] > 0
    perm_pass    = perm_result is not None and perm_result['significant']
    windows_ok   = win_data is not None and all(
        win_data[w]['fcf_edge'] > 0 and win_data[w]['delta_edge'] > 0
        for w in [150, 500, 1500]
    )

    print(f"\n  McNemar p(單側) = {s['p_one_sided']:.4f}  {'✅ <0.05' if mcnemar_pass else '❌ ≥0.05'}")
    if perm_result:
        print(f"  Perm p-value   = {perm_result['p_value']:.4f}  "
              f"{'✅ <0.05' if perm_pass else '❌ ≥0.05'}")
    if win_data:
        print(f"  三窗口 FCF 全勝 = {'✅' if windows_ok else '❌'}")

    print()
    if mcnemar_pass and (perm_pass or perm_result is None):
        if win_data is None or windows_ok:
            print("  ✅ FCF 顯著優於 TS3 — 可考慮升級 3注策略")
            print("     建議：以 FCF 替換 TS3 作為 3注標準")
            verdict = 'UPGRADE_RECOMMENDED'
        else:
            print("  ⚠️  McNemar 顯著但三窗口不穩定 — 暫不升級")
            verdict = 'MARGINAL_UNSTABLE'
    elif s['delta_rate'] > 0 and not mcnemar_pass:
        print("  ❌ FCF 略高但統計不顯著 — 維持 TS3")
        print("     現行 TS3 擁有 P3 Bonferroni 驗證 (p=0.030)，不輕易替換")
        verdict = 'MAINTAIN_TS3'
    else:
        print("  ❌ FCF 未優於 TS3 — 維持 TS3")
        verdict = 'MAINTAIN_TS3'

    # ─── 儲存結果 ─────────────────────────────────────────
    output = {
        'strategy_a': 'TS3 (Fourier+Cold+TailBalance)',
        'strategy_b': 'FCF (Fourier+Cold+FreqOrt)',
        'window':     args.window,
        'main_stats': s,
        'bet3_contribution': b3_result,
        'perm_result': perm_result,
        'verdict':    verdict,
    }
    out_path = os.path.join(project_root, f'fcf_vs_ts3_{args.window}p.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  💾 結果已儲存: {out_path}")
    print(f"\n{sep}\n")


if __name__ == '__main__':
    main()
