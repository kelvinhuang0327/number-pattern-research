#!/usr/bin/env python3
"""
今彩539 Lag-Echo + ColdBurst 驗證回測
2026-03-08

115000060 期（15,17,18,34,36）檢討後，針對三個信號缺口設計新機制：
  - Lag-k 回聲：17 號 Lag-2 miss（系統盲點）
  - 冷號群聚：18、34 gap=18 雙冷同期回補

回測四策略:
  S1: LagEcho_1bet             — Lag-k 信號獨立校準
  S2: ACB_LagEcho_2bet         — 挑戰 MidFreq+ACB (ADOPTED +5.06%)
  S3: ACB_Markov_LagEcho_3bet  — 主要決策: 挑戰 ACB+Markov+Fourier (PROVISIONAL +6.43%)
  S4: ACB_LagEcho_ColdBurst_3bet — 全覆蓋組合: ACB + 回聲 + 爆發

驗證協議 (與 backtest_539_rrf_complete.py 完全一致):
  - 三窗口 150 / 500 / 1500 期 walk-forward，無資料洩漏
  - Permutation test 200 次 (label-shuffle)
  - McNemar 配對比較 vs 現行冠軍
  - 晉級門檻: STABLE + perm_p < 0.05

Lag 權重 (lag_weights):
  {1: 0.5, 2: 2.0, 3: 1.0}
  lag-1 低 (Markov 已覆蓋)，lag-2 主信號，lag-3 輔助

ColdBurst 門檻: threshold_gap=15 (≈ 1.9x 期望 gap 7.8)
"""
import sys, os, json, time, random
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

# ===== 常數 =====
BASELINES_M2 = {1: 11.40, 2: 21.54, 3: 30.50, 4: 38.43, 5: 45.39}
MAX_NUM = 39
PICK = 5
LAG_WEIGHTS = {1: 0.5, 2: 2.0, 3: 1.0}
BURST_THRESHOLD = 15
BURST_MIN_COUNT = 3

random.seed(42)
np.random.seed(42)


# ===================================================================
# 評分函數 (與 backtest_539_rrf_complete.py 一致，自包含避免 import 循環)
# ===================================================================

def fourier_scores_539(history, window=500):
    """Fourier 週期分數"""
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM + 1):
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
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def acb_scores_539(history, window=100):
    """ACB 異常捕捉分數"""
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        freq_deficit = expected - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * bb * m3
    return scores


def markov_scores_539(history, window=30):
    """Markov 轉移分數"""
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn > MAX_NUM:
                continue
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                if nn <= MAX_NUM:
                    transitions[pn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        if pn > MAX_NUM:
            continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for nn, cnt in trans.items():
                scores[nn] += cnt / total
    for n in range(1, MAX_NUM + 1):
        if n not in scores:
            scores[n] = 0.0
    return dict(scores)


def midfreq_scores_539(history, window=100):
    """MidFreq 均值回歸分數"""
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for n in range(1, MAX_NUM + 1):
        freq[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1
    expected = len(recent) * PICK / MAX_NUM
    max_dist = max(abs(freq[n] - expected) for n in range(1, MAX_NUM + 1))
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = max_dist - abs(freq[n] - expected)
    return scores


def lag_echo_scores_539(history, lag_weights=None):
    """Lag-k 回聲分數

    理論: 號碼在 k 期前出現後，有高於隨機的機率在本期再出現。
    lag-2 是主要盲點（Markov 僅覆蓋 lag-1 轉移，ACB 排斥近期號碼）。
    """
    if lag_weights is None:
        lag_weights = LAG_WEIGHTS
    scores = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for k, w in lag_weights.items():
        if len(history) >= k:
            for n in history[-k]['numbers']:
                if 1 <= n <= MAX_NUM:
                    scores[n] += w
    # 頻率 tiebreaker（scale=0.1）
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'] if n <= MAX_NUM)
    max_freq = max(freq.values()) if freq else 1
    for n in range(1, MAX_NUM + 1):
        scores[n] += (freq.get(n, 0) / max_freq) * 0.1
    return scores


def cold_burst_scores_539(history, threshold_gap=BURST_THRESHOLD, window=100):
    """冷號群聚爆發分數

    gap >= threshold_gap 的號碼使用 ACB 分數，其餘為 0。
    設計目標：精確捕捉深冷號（如 gap=18 的 18 和 34 號）。
    """
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    acb = acb_scores_539(history, window=window)
    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = acb[n] if gaps[n] >= threshold_gap else 0.0
    return scores


# ===================================================================
# 工具函數
# ===================================================================

def _ranked_excl(scores, exclude, min_score=None):
    """從 scores 中排除 exclude，按分數降序，可選 min_score 過濾"""
    filtered = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    if min_score is not None:
        filtered = [n for n in filtered if scores.get(n, 0) > min_score]
    return sorted(filtered, key=lambda x: -scores.get(x, 0))


def _fill_bet(scored_ranked, need, fallback_history, used_set):
    """取前 need 個，不足時用近期頻率補足"""
    result = list(scored_ranked[:need])
    if len(result) < need:
        freq = Counter(n for d in fallback_history[-100:] for n in d['numbers'] if n <= MAX_NUM)
        used = used_set | set(result)
        for n in sorted(range(1, MAX_NUM + 1), key=lambda x: -freq.get(x, 0)):
            if n not in used:
                result.append(n)
                if len(result) >= need:
                    break
    return sorted(result[:need])


# ===================================================================
# 現行冠軍（基準，McNemar 對比用）
# ===================================================================

def pred_midfreq_acb_2bet_ref(history):
    """MidFreq+ACB 2注 (ADOPTED 基準，Edge +5.06%)"""
    mf_sc = midfreq_scores_539(history)
    bet1 = sorted(_ranked_excl(mf_sc, set())[:PICK])
    a_sc = acb_scores_539(history)
    excl = set(bet1)
    bet2 = _fill_bet(_ranked_excl(a_sc, excl), PICK, history, excl)
    return [bet1, bet2]


def pred_acb_markov_fourier_3bet_ref(history):
    """ACB+Markov+Fourier 3注 (PROVISIONAL 冠軍，Edge +6.43%)"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)

    m_sc = markov_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(m_sc, excl), PICK, history, excl)
    excl2 = excl | set(bet2)

    f_sc = fourier_scores_539(history)
    bet3_ranked = _ranked_excl(f_sc, excl2, min_score=0)
    bet3 = _fill_bet(bet3_ranked, PICK, history, excl2)
    return [bet1, bet2, bet3]


# ===================================================================
# 四個新策略
# ===================================================================

def pred_lag_echo_1bet(history):
    """S1: LagEcho 單注 — Lag-k 信號獨立校準"""
    l_sc = lag_echo_scores_539(history)
    ranked = _ranked_excl(l_sc, set())
    return [sorted(ranked[:PICK])]


def pred_acb_lag_2bet(history):
    """S2: ACB + LagEcho 正交2注 — 挑戰 MidFreq+ACB (ADOPTED)"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)

    l_sc = lag_echo_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(l_sc, excl), PICK, history, excl)
    return [bet1, bet2]


def pred_acb_markov_lag_3bet(history):
    """S3: ACB + Markov + LagEcho 正交3注 — 主要決策，挑戰 PROVISIONAL 冠軍"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)

    m_sc = markov_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(m_sc, excl), PICK, history, excl)
    excl2 = excl | set(bet2)

    l_sc = lag_echo_scores_539(history)
    bet3 = _fill_bet(_ranked_excl(l_sc, excl2), PICK, history, excl2)
    return [bet1, bet2, bet3]


def pred_acb_lag_coldburst_3bet(history):
    """S4: ACB + LagEcho + ColdBurst 正交3注 — 全覆蓋組合"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)

    l_sc = lag_echo_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(l_sc, excl), PICK, history, excl)
    excl2 = excl | set(bet2)

    cb_sc = cold_burst_scores_539(history)
    # 若無 burst 號碼（全為 0），退回 ACB 分數（確保注不退化）
    if max(cb_sc.values()) == 0:
        cb_sc = a_sc
    bet3 = _fill_bet(_ranked_excl(cb_sc, excl2), PICK, history, excl2)
    return [bet1, bet2, bet3]


# ===================================================================
# 回測引擎（逐字複製自 backtest_539_rrf_complete.py）
# ===================================================================

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=1,
                 match_threshold=2, verbose=False):
    """539 通用回測 (M2+ 基準)"""
    hits = 0
    total = 0
    hit_details = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 100:
            hit_details.append(0)
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'][:PICK])

        try:
            bets = predict_func(hist)
            assert len(bets) == n_bets, f"Expected {n_bets} bets, got {len(bets)}"
            hit = any(len(set(bet) & actual) >= match_threshold for bet in bets)
            if hit:
                hits += 1
                hit_details.append(1)
            else:
                hit_details.append(0)
            total += 1
        except Exception as e:
            if verbose:
                print(f"  idx={target_idx}: {e}")
            hit_details.append(0)
            total += 1

    rate = hits / total * 100 if total > 0 else 0
    baseline = BASELINES_M2.get(n_bets, BASELINES_M2[1])
    edge = rate - baseline

    p0 = baseline / 100
    if total > 0 and p0 > 0:
        se = np.sqrt(p0 * (1 - p0) / total)
        z = (hits / total - p0) / se if se > 0 else 0
    else:
        z = 0

    return {
        'hits': hits,
        'total': total,
        'rate': rate,
        'baseline': baseline,
        'edge': edge,
        'z': z,
        'hit_details': hit_details,
    }


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=1,
                          match_threshold=2, n_perm=200):
    """539 Permutation test (label-shuffle)"""
    real = backtest_539(predict_func, all_draws, test_periods, n_bets, match_threshold)
    real_rate = real['rate']

    target_indices = []
    for i in range(test_periods):
        idx = len(all_draws) - test_periods + i
        if idx >= 100:
            target_indices.append(idx)

    all_actuals = [set(all_draws[idx]['numbers'][:PICK]) for idx in target_indices]
    perm_rates = []

    for p in range(n_perm):
        shuffled = list(all_actuals)
        rng = random.Random(p * 7919 + 42)
        rng.shuffle(shuffled)

        hits = 0
        total = 0
        for i, idx in enumerate(target_indices):
            hist = all_draws[:idx]
            actual = shuffled[i]
            try:
                bets = predict_func(hist)
                hit = any(len(set(bet) & actual) >= match_threshold for bet in bets)
                if hit:
                    hits += 1
                total += 1
            except Exception:
                total += 1

        if total > 0:
            perm_rates.append(hits / total * 100)

    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    p_value = (count_exceed + 1) / (n_perm + 1)
    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1.0
    signal_edge = real_rate - perm_mean
    perm_z = signal_edge / perm_std if perm_std > 0 else 0

    return {
        'real_rate': real_rate,
        'perm_mean': perm_mean,
        'perm_std': float(perm_std),
        'signal_edge': signal_edge,
        'perm_z': perm_z,
        'p_value': p_value,
        'n_perm': n_perm,
    }


def mcnemar_test(details_a, details_b):
    """McNemar 配對檢定"""
    assert len(details_a) == len(details_b), \
        f"Length mismatch: {len(details_a)} vs {len(details_b)}"
    both_hit = sum(1 for a, b in zip(details_a, details_b) if a and b)
    a_only = sum(1 for a, b in zip(details_a, details_b) if a and not b)
    b_only = sum(1 for a, b in zip(details_a, details_b) if not a and b)
    both_miss = sum(1 for a, b in zip(details_a, details_b) if not a and not b)

    n_disc = a_only + b_only
    if n_disc == 0:
        chi2, p = 0.0, 1.0
    else:
        chi2 = (a_only - b_only) ** 2 / n_disc
        from scipy.stats import chi2 as chi2_dist
        p = 1 - chi2_dist.cdf(chi2, df=1)

    return {
        'both_hit': both_hit,
        'a_only': a_only,
        'b_only': b_only,
        'both_miss': both_miss,
        'chi2': round(chi2, 4),
        'p_value': round(p, 4),
        'winner': 'A' if a_only > b_only else ('B' if b_only > a_only else 'TIE'),
        'net': a_only - b_only,
    }


def stability_label(e150, e500, e1500):
    if all(x > 0 for x in [e150, e500, e1500]):
        return 'STABLE'
    elif e1500 < 0:
        return 'SHORT_MOMENTUM' if (e150 > 0 or e500 > 0) else 'INEFFECTIVE'
    elif e150 < 0 and e1500 > 0:
        return 'LATE_BLOOMER'
    else:
        return 'MIXED'


# ===================================================================
# 主程式
# ===================================================================

def run_strategy(name, func, n_bets, all_draws, run_perm=True):
    """標準三窗口 + Permutation 完整流程"""
    print(f"\n  --- {name} ---")
    window_results = {}
    for periods in [150, 500, 1500]:
        r = backtest_539(func, all_draws, periods, n_bets, match_threshold=2)
        window_results[periods] = r
        star = '★' if r['edge'] > 0 else ''
        print(f"    {periods:4d}p: rate={r['rate']:.2f}%  edge={r['edge']:+.2f}%  z={r['z']:.2f}{star}")

    e150 = window_results[150]['edge']
    e500 = window_results[500]['edge']
    e1500 = window_results[1500]['edge']
    stab = stability_label(e150, e500, e1500)
    print(f"    穩定性: {stab}")

    perm_p, signal_edge = None, None
    if run_perm and e1500 > 0:
        print(f"    執行 Permutation test (200次)...")
        pr = permutation_test_539(func, all_draws, 1500, n_bets, n_perm=200)
        perm_p = round(pr['p_value'], 4)
        signal_edge = round(pr['signal_edge'], 2)
        sig = '★★' if perm_p < 0.01 else ('★' if perm_p < 0.05 else '')
        print(f"    Perm p={perm_p:.4f}{sig}  signal_edge={signal_edge:+.2f}%")
    elif e1500 <= 0:
        print(f"    1500p edge<=0，跳過 Permutation")

    return {
        'n_bets': n_bets,
        'edge_150p': round(e150, 2),
        'edge_500p': round(e500, 2),
        'edge_1500p': round(e1500, 2),
        'rate_1500p': round(window_results[1500]['rate'], 2),
        'z_1500p': round(window_results[1500]['z'], 2),
        'perm_p': perm_p,
        'signal_edge': signal_edge,
        'stability': stab,
        '_hit_details_1500': window_results[1500]['hit_details'],
    }


def main():
    t0 = time.time()

    db = DatabaseManager(db_path=os.path.join(
        project_root, 'lottery_api', 'data', 'lottery_v2.db'
    ))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"載入 {len(all_draws)} 期 539 資料")
    print(f"最新期: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")

    strategies = {}

    print("\n" + "=" * 70)
    print("  新策略回測：Lag-Echo + ColdBurst")
    print("=" * 70)

    strategies['LagEcho_1bet'] = run_strategy(
        'S1: LagEcho_1bet', pred_lag_echo_1bet, 1, all_draws
    )
    strategies['ACB_LagEcho_2bet'] = run_strategy(
        'S2: ACB_LagEcho_2bet', pred_acb_lag_2bet, 2, all_draws
    )
    strategies['ACB_Markov_LagEcho_3bet'] = run_strategy(
        'S3: ACB_Markov_LagEcho_3bet', pred_acb_markov_lag_3bet, 3, all_draws
    )
    strategies['ACB_LagEcho_ColdBurst_3bet'] = run_strategy(
        'S4: ACB_LagEcho_ColdBurst_3bet', pred_acb_lag_coldburst_3bet, 3, all_draws
    )

    # ==== 基準 (McNemar 用) ====
    print("\n  --- 基準 (現行冠軍 hit_details，McNemar 用) ---")
    ref_2bet = backtest_539(pred_midfreq_acb_2bet_ref, all_draws, 1500, 2)
    ref_3bet = backtest_539(pred_acb_markov_fourier_3bet_ref, all_draws, 1500, 3)
    print(f"    MidFreq+ACB 2注:         edge={ref_2bet['edge']:+.2f}%  (ref +5.06%)")
    print(f"    ACB+Markov+Fourier 3注:  edge={ref_3bet['edge']:+.2f}%  (ref +6.43%)")

    # ==== McNemar ====
    print("\n  --- McNemar 配對比較 ---")
    mcnemar_results = {}

    mc_s2 = mcnemar_test(
        strategies['ACB_LagEcho_2bet']['_hit_details_1500'],
        ref_2bet['hit_details']
    )
    mcnemar_results['S2_vs_MidFreq_ACB'] = mc_s2
    print(f"    S2 vs MidFreq+ACB:   a_only={mc_s2['a_only']} b_only={mc_s2['b_only']}"
          f"  chi2={mc_s2['chi2']:.3f}  p={mc_s2['p_value']:.4f}  winner={mc_s2['winner']}")

    mc_s3 = mcnemar_test(
        strategies['ACB_Markov_LagEcho_3bet']['_hit_details_1500'],
        ref_3bet['hit_details']
    )
    mcnemar_results['S3_vs_ACB_Markov_Fourier'] = mc_s3
    print(f"    S3 vs AMF 3注:       a_only={mc_s3['a_only']} b_only={mc_s3['b_only']}"
          f"  chi2={mc_s3['chi2']:.3f}  p={mc_s3['p_value']:.4f}  winner={mc_s3['winner']}")

    mc_s4 = mcnemar_test(
        strategies['ACB_LagEcho_ColdBurst_3bet']['_hit_details_1500'],
        ref_3bet['hit_details']
    )
    mcnemar_results['S4_vs_ACB_Markov_Fourier'] = mc_s4
    print(f"    S4 vs AMF 3注:       a_only={mc_s4['a_only']} b_only={mc_s4['b_only']}"
          f"  chi2={mc_s4['chi2']:.3f}  p={mc_s4['p_value']:.4f}  winner={mc_s4['winner']}")

    # ==== 晉級判定 ====
    print("\n  --- 晉級判定 ---")
    for name, s in strategies.items():
        e = s['edge_1500p']
        p = s['perm_p']
        stab = s['stability']
        if stab == 'STABLE' and p is not None and p < 0.05:
            verdict = 'PROVISIONAL/ADOPTED 候選'
        elif stab == 'STABLE' and p is not None and p < 0.1:
            verdict = '邊緣，需更多期觀察'
        elif e <= 0:
            verdict = 'REJECT (edge<=0)'
        else:
            verdict = f'REJECT (perm_p={p}，未達門檻)' if p is not None else 'REJECT (edge<=0，未跑perm)'
        print(f"    {name:<35}: {verdict}")

    # ==== 清理 hit_details（節省 JSON 空間）====
    for s in strategies.values():
        s.pop('_hit_details_1500', None)

    # ==== 輸出 JSON ====
    elapsed = time.time() - t0
    save_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(all_draws),
        'elapsed_seconds': round(elapsed, 1),
        'script': 'backtest_539_lag_burst.py',
        'lag_weights_used': {str(k): v for k, v in LAG_WEIGHTS.items()},
        'burst_threshold': BURST_THRESHOLD,
        'burst_min_count': BURST_MIN_COUNT,
        'champion_reference': {
            'ACB_Markov_Fourier_3bet': {'edge_1500p': 6.43, 'perm_p': 0.005},
            'MidFreq_ACB_2bet': {'edge_1500p': 5.06, 'perm_p': 0.005},
        },
        'strategies': strategies,
        'mcnemar': mcnemar_results,
    }

    output_path = os.path.join(project_root, 'backtest_539_lag_burst_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

    print(f"\n  結果已存: {output_path}")
    print(f"  耗時: {elapsed:.1f} 秒")
    print("=" * 70)


if __name__ == '__main__':
    main()
