#!/usr/bin/env python3
"""
大樂透 Meta-Bet 多域交疊注 回測
=================================
研究動機：
  115000025 期 6個目標號碼分屬三個不同信號域：
    [28,31] ← Fourier, [19,27] ← Cold, [12,22] ← Markov
  若設計一個「融合三域信號的 Meta-Bet」，是否能在下注數不增加的情況下
  捕捉到這些「跨域號碼」？

策略設計：
  版本A (Multi-Domain Overlap):
    計算 Fourier / Cold / Markov 三個信號的全部49號排名
    選取同時進入至少2個域 Top-30 的號碼
    從這些交疊候選中選 Top-6（按合併分數排序）

  版本B (Ensemble Score Fusion):
    將三個域的原始分數歸一化至 [0,1]
    合併分數 = (fourier_norm + cold_norm + markov_norm) / 3
    直接選合併分數最高的 Top-6（從排除注1-5後的剩餘號碼）

實驗1: 用 Meta-Bet 取代 5注中的注5（頻率正交），比較 5注系統性能
實驗2: Meta-Bet 作為額外的第6注（6注系統），比較邊際貢獻
實驗3: 用 Meta-Bet 取代注3（Tail Balance），比較 3注系統性能

三窗口驗證: 150 / 500 / 1500 期
McNemar 顯著性檢定

Usage:
    python3 tools/backtest_meta_bet.py
"""
import os
import sys
import time
import numpy as np
from collections import Counter
from itertools import combinations as _icombs
from scipy.fft import fft, fftfreq
from scipy.stats import norm as scipy_norm

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

MAX_NUM = 49
PICK = 6
SEED = 42
_SUM_WIN = 300

P_SINGLE = 0.0186
BASELINES = {
    1: P_SINGLE,
    2: 1 - (1 - P_SINGLE) ** 2,
    3: 1 - (1 - P_SINGLE) ** 3,
    4: 1 - (1 - P_SINGLE) ** 4,
    5: 1 - (1 - P_SINGLE) ** 5,
    6: 1 - (1 - P_SINGLE) ** 6,
}

WINDOWS = [150, 500, 1500]
MIN_HISTORY_BUFFER = 150


# ============================================================
# Core Signal Functions (synced with validated strategies)
# ============================================================
def _sum_target(history):
    h = history[-_SUM_WIN:] if len(history) >= _SUM_WIN else history
    sums = [sum(d['numbers']) for d in h]
    mu, sg = np.mean(sums), np.std(sums)
    last_s = sum(history[-1]['numbers'])
    if last_s < mu - 0.5 * sg:
        return mu, mu + sg
    if last_s > mu + 0.5 * sg:
        return mu - sg, mu
    return mu - 0.5 * sg, mu + 0.5 * sg


def fourier_scores_all(history, window=500):
    """計算所有49個號碼的 Fourier 原始分數 (不選號，只返回分數向量)"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
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
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores  # scores[1..49]


def cold_scores_all(history, window=100):
    """計算冷號分數 (頻率越低 = 分數越高)"""
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    max_freq = max(freq.values()) if freq else 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        scores[n] = max_freq - freq.get(n, 0)  # 越冷分數越高
    return scores


def markov_scores_all(history, markov_window=30):
    """計算 Markov 轉移分數 (從前期各號的轉移概率)"""
    if len(history) < 2:
        return np.zeros(MAX_NUM + 1)

    window = min(markov_window, len(history))
    recent = history[-window:]
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i]['numbers']
        next_nums = recent[i + 1]['numbers']
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1

    last_draw_nums = history[-1]['numbers']
    scores = np.zeros(MAX_NUM + 1)
    for prev_num in last_draw_nums:
        for n in range(1, MAX_NUM + 1):
            scores[n] += transitions.get((prev_num, n), 0)
    return scores


def normalize_scores(scores):
    """將分數向量歸一化至 [0,1]"""
    vals = scores[1:]  # 1..49
    mn, mx = vals.min(), vals.max()
    if mx == mn:
        return np.zeros_like(scores)
    norm = np.zeros_like(scores, dtype=float)
    norm[1:] = (vals - mn) / (mx - mn)
    return norm


# ============================================================
# Triple Strike v2 Components (for building base bets 1-5)
# ============================================================
def fourier_rhythm_bet(history, window=500):
    scores = fourier_scores_all(history, window)
    sorted_idx = np.argsort(scores[1:])[::-1] + 1
    return sorted(sorted_idx[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None, pool_size=12):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))

    if len(history) < 2 or pool_size <= 6:
        return sorted(sorted_cold[:6])

    pool = sorted_cold[:pool_size]
    tlo, thi = _sum_target(history)
    tmid = (tlo + thi) / 2.0
    best_combo, best_dist, best_in_range = None, float('inf'), False
    for combo in _icombs(pool, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in_range or dist < best_dist):
            best_combo, best_dist, best_in_range = combo, dist, True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo, best_dist = combo, dist
    return sorted(best_combo) if best_combo else sorted(pool[:6])


def tail_balance_bet(history, window=100, exclude=None):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for t in tail_groups:
        tail_groups[t].sort(key=lambda x: x[1], reverse=True)
    selected = []
    available_tails = sorted(
        [t for t in range(10) if tail_groups[t]],
        key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0,
        reverse=True
    )
    idx_in_group = {t: 0 for t in range(10)}
    while len(selected) < 6:
        added = False
        for tail in available_tails:
            if len(selected) >= 6:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break
    if len(selected) < 6:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])
    return sorted(selected[:6])


def markov_orthogonal_bet(history, exclude=None, markov_window=30):
    exclude = exclude or set()
    scores = markov_scores_all(history, markov_window)
    candidates = [(n, scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:PICK]]
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])
    return sorted(selected[:PICK])


def frequency_orthogonal_bet(history, exclude=None, window=100):
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    candidates.sort(key=lambda x: freq.get(x, 0), reverse=True)
    return sorted(candidates[:PICK])


# ============================================================
# Meta-Bet: 多域交疊注
# ============================================================
def meta_bet_overlap(history, exclude=None,
                     top_n=30, fourier_window=500,
                     cold_window=100, markov_window=30):
    """
    版本A: Multi-Domain Overlap
    選取同時進入 Fourier/Cold/Markov 至少2個域 Top-N 的號碼。
    若候選不足6個，以合併分數補充。

    Args:
        top_n: 每個域的 Top-N 門檻 (預設30，約61% 覆蓋率)
    """
    exclude = exclude or set()

    f_scores = fourier_scores_all(history, fourier_window)
    c_scores = cold_scores_all(history, cold_window)
    m_scores = markov_scores_all(history, markov_window)

    f_norm = normalize_scores(f_scores)
    c_norm = normalize_scores(c_scores)
    m_norm = normalize_scores(m_scores)

    # 各域排名 (1=最高)
    all_nums = list(range(1, MAX_NUM + 1))
    f_rank = {n: r for r, n in enumerate(
        sorted(all_nums, key=lambda x: -f_scores[x]), 1)}
    c_rank = {n: r for r, n in enumerate(
        sorted(all_nums, key=lambda x: -c_scores[x]), 1)}
    m_rank = {n: r for r, n in enumerate(
        sorted(all_nums, key=lambda x: -m_scores[x]), 1)}

    # 計算每個號碼進入 Top-N 的域數量
    candidates = []
    for n in range(1, MAX_NUM + 1):
        if n in exclude:
            continue
        domains_in_top = sum([
            1 if f_rank[n] <= top_n else 0,
            1 if c_rank[n] <= top_n else 0,
            1 if m_rank[n] <= top_n else 0,
        ])
        meta_score = (f_norm[n] + c_norm[n] + m_norm[n]) / 3
        candidates.append((n, domains_in_top, meta_score,
                            f_rank[n], c_rank[n], m_rank[n]))

    # 優先選：進入≥2個域 Top-N 的號碼，按合併分數排序
    tier1 = [(n, s) for (n, d, s, fr, cr, mr) in candidates if d >= 2]
    tier1.sort(key=lambda x: -x[1])

    selected = [n for n, _ in tier1[:PICK]]

    # 不足6個時補充：按合併分數降序
    if len(selected) < PICK:
        tier2 = [(n, s) for (n, d, s, fr, cr, mr) in candidates if n not in selected]
        tier2.sort(key=lambda x: -x[1])
        selected.extend(n for n, _ in tier2[:PICK - len(selected)])

    return sorted(selected[:PICK])


def meta_bet_ensemble(history, exclude=None,
                      fourier_window=500, cold_window=100, markov_window=30,
                      w_fourier=1.0, w_cold=1.0, w_markov=1.0):
    """
    版本B: Ensemble Score Fusion
    三個域分數歸一化後加權求和，選合併分數最高的 Top-6。
    """
    exclude = exclude or set()

    f_scores = fourier_scores_all(history, fourier_window)
    c_scores = cold_scores_all(history, cold_window)
    m_scores = markov_scores_all(history, markov_window)

    f_norm = normalize_scores(f_scores)
    c_norm = normalize_scores(c_scores)
    m_norm = normalize_scores(m_scores)

    candidates = []
    for n in range(1, MAX_NUM + 1):
        if n in exclude:
            continue
        meta = (w_fourier * f_norm[n] + w_cold * c_norm[n] + w_markov * m_norm[n])
        candidates.append((n, meta))

    candidates.sort(key=lambda x: -x[1])
    selected = [n for n, _ in candidates[:PICK]]
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1)
                     if n not in exclude and n not in selected]
        selected.extend(remaining[:PICK - len(selected)])
    return sorted(selected[:PICK])


# ============================================================
# Strategy Generators
# ============================================================
def gen_5bet_original(history):
    """原始5注 (基準線)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    used3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used3)
    used4 = used3 | set(bet4)
    bet5 = frequency_orthogonal_bet(history, exclude=used4)
    return [bet1, bet2, bet3, bet4, bet5]


def gen_5bet_meta_overlap(history):
    """5注：注5改為 Meta-Bet Overlap (取代頻率正交)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    used3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used3)
    used4 = used3 | set(bet4)
    bet5 = meta_bet_overlap(history, exclude=used4)
    return [bet1, bet2, bet3, bet4, bet5]


def gen_5bet_meta_ensemble(history):
    """5注：注5改為 Meta-Bet Ensemble (取代頻率正交)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    used3 = set(bet1) | set(bet2) | set(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used3)
    used4 = used3 | set(bet4)
    bet5 = meta_bet_ensemble(history, exclude=used4)
    return [bet1, bet2, bet3, bet4, bet5]


def gen_6bet_with_meta(history):
    """6注：在原始5注基礎上增加 Meta-Bet 作為第6注"""
    base5 = gen_5bet_original(history)
    used5 = set(n for b in base5 for n in b)
    bet6 = meta_bet_overlap(history, exclude=used5)
    return base5 + [bet6]


def gen_3bet_meta_overlap(history):
    """3注：注3改為 Meta-Bet Overlap (取代 Tail Balance)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    used2 = set(bet1) | set(bet2)
    bet3 = meta_bet_overlap(history, exclude=used2)
    return [bet1, bet2, bet3]


def gen_3bet_original(history):
    """原始3注 Triple Strike (基準)"""
    bet1 = fourier_rhythm_bet(history)
    bet2 = cold_numbers_bet(history, exclude=set(bet1))
    bet3 = tail_balance_bet(history, exclude=set(bet1) | set(bet2))
    return [bet1, bet2, bet3]


# ============================================================
# Backtest Engine
# ============================================================
def run_backtest(draws, strategy_func, n_bets, n_periods, seed=42, label=""):
    np.random.seed(seed)
    baseline = BASELINES.get(n_bets, BASELINES[1])
    start_idx = len(draws) - n_periods
    if start_idx < MIN_HISTORY_BUFFER:
        start_idx = MIN_HISTORY_BUFFER

    hits_3plus = 0
    total = 0
    per_bet_hits = [0] * n_bets

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        try:
            bets = strategy_func(history)
        except Exception:
            total += 1
            continue

        best_match = 0
        for b_idx, b in enumerate(bets):
            mc = len(set(b) & target)
            if mc > best_match:
                best_match = mc
            if mc >= 3:
                per_bet_hits[b_idx] += 1

        if best_match >= 3:
            hits_3plus += 1
        total += 1

    if total == 0:
        return None

    rate = hits_3plus / total
    edge = (rate - baseline) / baseline * 100
    z = (rate - baseline) / np.sqrt(baseline * (1 - baseline) / total)
    p = 2 * (1 - scipy_norm.cdf(abs(z)))

    return {
        'label': label,
        'n_periods': n_periods,
        'actual': total,
        'hits': hits_3plus,
        'rate': rate,
        'baseline': baseline,
        'edge': edge,
        'z': z,
        'p': p,
        'per_bet_hits': per_bet_hits,
    }


def mcnemar_test(draws, func_a, func_b, n_periods):
    """McNemar 檢定兩個策略的差異"""
    start_idx = max(len(draws) - n_periods, MIN_HISTORY_BUFFER)
    b_wins = 0  # B 命中但 A 沒命中
    a_wins = 0  # A 命中但 B 沒命中
    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        try:
            bets_a = func_a(history)
            bets_b = func_b(history)
        except Exception:
            continue
        hit_a = any(len(set(b) & target) >= 3 for b in bets_a)
        hit_b = any(len(set(b) & target) >= 3 for b in bets_b)
        if hit_b and not hit_a:
            b_wins += 1
        elif hit_a and not hit_b:
            a_wins += 1

    total_disc = a_wins + b_wins
    if total_disc == 0:
        return 0, 1.0, a_wins, b_wins
    chi2 = (abs(a_wins - b_wins) - 1) ** 2 / total_disc if total_disc > 0 else 0
    from scipy.stats import chi2 as chi2_dist
    p = 1 - chi2_dist.cdf(chi2, df=1)
    return chi2, p, a_wins, b_wins


def print_result(r):
    if r is None:
        print("  [Error: 無法計算]")
        return
    sig = "***" if r['p'] < 0.01 else ("**" if r['p'] < 0.05 else ("*" if r['p'] < 0.10 else ""))
    print(f"  {r['label']:40s} | M3+: {r['hits']:4d}/{r['actual']:5d} "
          f"= {r['rate']:.4f} | 基準: {r['baseline']:.4f} "
          f"| Edge: {r['edge']:+.2f}% | z={r['z']:+.2f} {sig}")


def run_experiment(title, draws, func_a, func_b, n_bets_a, n_bets_b, label_a, label_b):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

    results_a = {}
    results_b = {}

    for w in WINDOWS:
        print(f"\n  --- {w}期窗口 ---")
        ra = run_backtest(draws, func_a, n_bets_a, w, label=label_a)
        rb = run_backtest(draws, func_b, n_bets_b, w, label=label_b)
        print_result(ra)
        print_result(rb)
        if ra and rb:
            diff = rb['edge'] - ra['edge']
            print(f"  {'差異 (B-A)':40s} | Edge差: {diff:+.2f}%")
        results_a[w] = ra
        results_b[w] = rb

    # McNemar (對1500期窗口)
    chi2, p_val, a_wins, b_wins = mcnemar_test(draws, func_a, func_b, 1500)
    print(f"\n  McNemar (1500期): χ²={chi2:.2f}, p={p_val:.4f} "
          f"(A_only={a_wins}, B_only={b_wins})")

    return results_a, results_b


def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))
    print(f"\n資料載入: {len(draws)} 期大樂透")
    print(f"回測設計: 三窗口 {WINDOWS}, seed={SEED}")
    t_start = time.time()

    # ---- 實驗1: 5注 — 注5 Meta-Overlap vs 原始頻率正交 ----
    ra1, rb1 = run_experiment(
        "實驗1: 5注 — 注5改為 Meta-Bet Overlap vs 原始頻率正交",
        draws,
        gen_5bet_original, gen_5bet_meta_overlap,
        5, 5,
        "原始5注 (注5=Freq Orthogonal)",
        "Meta5注 (注5=Meta Overlap   )"
    )

    # ---- 實驗2: 5注 — 注5 Meta-Ensemble vs 原始頻率正交 ----
    ra2, rb2 = run_experiment(
        "實驗2: 5注 — 注5改為 Meta-Bet Ensemble vs 原始頻率正交",
        draws,
        gen_5bet_original, gen_5bet_meta_ensemble,
        5, 5,
        "原始5注 (注5=Freq Orthogonal)",
        "Meta5注 (注5=Meta Ensemble  )"
    )

    # ---- 實驗3: 6注 — 原始5注 + 額外 Meta-Bet ----
    ra3, rb3 = run_experiment(
        "實驗3: 6注 = 原始5注 + 第6注 Meta-Bet (邊際貢獻)",
        draws,
        gen_5bet_original, gen_6bet_with_meta,
        5, 6,
        "原始5注",
        "6注 (5注+Meta Overlap       )"
    )

    # ---- 實驗4: 3注 — 注3改為 Meta-Bet vs 原始 Tail Balance ----
    ra4, rb4 = run_experiment(
        "實驗4: 3注 — 注3改為 Meta-Bet Overlap vs 原始 Tail Balance",
        draws,
        gen_3bet_original, gen_3bet_meta_overlap,
        3, 3,
        "原始3注 (注3=Tail Balance   )",
        "Meta3注 (注3=Meta Overlap   )"
    )

    elapsed = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  摘要 — Meta-Bet 多域交疊注 回測結果")
    print(f"{'='*70}")

    summary_data = [
        ("實驗1 注5 Overlap    ", ra1, rb1, 5, 5),
        ("實驗2 注5 Ensemble   ", ra2, rb2, 5, 5),
        ("實驗3 第6注 Overlap  ", ra3, rb3, 5, 6),
        ("實驗4 注3 Overlap    ", ra4, rb4, 3, 3),
    ]

    print(f"\n  {'實驗':22s} {'窗口':>6s} {'A Edge':>8s} {'B Edge':>8s} {'差異':>8s} {'判定'}")
    print(f"  {'-'*65}")

    for title, ra_d, rb_d, na, nb in summary_data:
        for w in WINDOWS:
            ra = ra_d.get(w)
            rb = rb_d.get(w)
            if ra and rb:
                diff = rb['edge'] - ra['edge']
                verdict = "✓改善" if diff > 0.3 else ("✗退步" if diff < -0.3 else "≈持平")
                print(f"  {title:22s} {w:>6d}p "
                      f"{ra['edge']:>+7.2f}% {rb['edge']:>+7.2f}% {diff:>+7.2f}% {verdict}")
        print()

    print(f"\n  回測耗時: {elapsed:.1f}s")

    # 最終判定
    print(f"\n{'='*70}")
    print(f"  最終判定")
    print(f"{'='*70}")

    # 實驗1 1500p 結論
    r1500_a = ra1.get(1500)
    r1500_b1 = rb1.get(1500)
    r1500_b2 = rb2.get(1500)
    r1500_b3 = rb3.get(1500)
    r1500_b4 = rb4.get(1500)
    r1500_a4 = ra4.get(1500)

    if r1500_b1 and r1500_a:
        d1 = r1500_b1['edge'] - r1500_a['edge']
        print(f"\n  注5 Overlap (vs Freq): 1500p Edge差 = {d1:+.2f}%")
        if d1 > 0.3:
            print(f"  → ✓ Meta-Bet Overlap 優於頻率正交，建議採納")
        elif d1 < -0.3:
            print(f"  → ✗ Meta-Bet Overlap 不如頻率正交，不採納")
        else:
            print(f"  → ≈ 差異在統計噪音範圍內，不採納（保持原版）")

    if r1500_b2 and r1500_a:
        d2 = r1500_b2['edge'] - r1500_a['edge']
        print(f"\n  注5 Ensemble (vs Freq): 1500p Edge差 = {d2:+.2f}%")
        if d2 > 0.3:
            print(f"  → ✓ Meta-Bet Ensemble 優於頻率正交，建議採納")
        else:
            print(f"  → ✗/≈ 不採納（差異 {d2:+.2f}%）")

    if r1500_b3 and r1500_a:
        d3 = r1500_b3['edge'] - r1500_a['edge']
        print(f"\n  第6注 Meta邊際 (vs 5注): 1500p Edge差 = {d3:+.2f}%")
        if d3 > 0.3:
            print(f"  → ✓ 增加第6注 Meta-Bet 有邊際 Edge，可考慮")
        else:
            print(f"  → ✗/≈ 第6注邊際不顯著（{d3:+.2f}%）")

    if r1500_b4 and r1500_a4:
        d4 = r1500_b4['edge'] - r1500_a4['edge']
        print(f"\n  3注 Meta注3 (vs TailBalance): 1500p Edge差 = {d4:+.2f}%")
        if d4 > 0.3:
            print(f"  → ✓ Meta-Bet 注3 優於 Tail Balance，Task 3 值得深入")
        else:
            print(f"  → ✗/≈ 注3 Meta-Bet 不優於 Tail Balance（{d4:+.2f}%）")

    print()


if __name__ == "__main__":
    main()
