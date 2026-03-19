#!/usr/bin/env python3
"""
今彩539 ExtremeCol + Conditional Fourier 驗證回測
2026-03-10

115000060/115000061 雙期檢討後的改進方案：
  P0: ExtremeCol(gap≥25) — 解決38號(gap=33)極端冷號的捕捉
  P1: Conditional Fourier — Fourier弱時切換LagEcho，解決32號(lag-2)被Fourier佔位

回測五策略:
  S1: ExtremeCol_1bet             — gap≥25 極端冷獨立校準
  S2: MidFreq_ExtremeCol_2bet     — ★主要假設（假設性4/5覆蓋的基礎）
  S3: ACB_ExtremeCol_2bet         — 替代組合 vs MidFreq+ACB (ADOPTED +5.06%)
  S4: ACB_Markov_ExtremeCol_3bet  — 替代3注 vs AMF (PROVISIONAL +6.10%)
  S5: ACB_Markov_CondFourier_3bet — ★Conditional Fourier/LagEcho 自適應3注

驗證協議:
  - 三窗口 150/500/1500 period walk-forward
  - Permutation test 200次 (label-shuffle)
  - McNemar vs 現行冠軍
  - 晉級門檻: STABLE + perm_p < 0.05
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
EXTREME_THRESHOLD = 25  # P0: 極端冷定義（vs 舊 ColdBurst 的15）
LAG_WEIGHTS = {1: 0.5, 2: 2.0, 3: 1.0}
FOURIER_THRESHOLDS = [0.25, 0.30, 0.35, 0.40]  # P1: 測試多個門檻

random.seed(42)
np.random.seed(42)


# ===================================================================
# 評分函數（與 backtest_539_lag_burst.py 一致）
# ===================================================================

def fourier_scores_539(history, window=500):
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
    if lag_weights is None:
        lag_weights = LAG_WEIGHTS
    scores = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for k, w in lag_weights.items():
        if len(history) >= k:
            for n in history[-k]['numbers']:
                if 1 <= n <= MAX_NUM:
                    scores[n] += w
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'] if n <= MAX_NUM)
    max_freq = max(freq.values()) if freq else 1
    for n in range(1, MAX_NUM + 1):
        scores[n] += (freq.get(n, 0) / max_freq) * 0.1
    return scores


def extreme_cold_scores_539(history, threshold_gap=EXTREME_THRESHOLD, window=100):
    """極端冷號分數 — gap≥25 才有分數（vs ColdBurst 的 gap≥15）

    115000061 診斷：38號 gap=33 是極端冷，threshold=15 時有5-7個號碼
    滿足條件（無區分度），threshold=25 時通常只有1-3個（稀有事件）。
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
    filtered = [n for n in range(1, MAX_NUM + 1) if n not in exclude]
    if min_score is not None:
        filtered = [n for n in filtered if scores.get(n, 0) > min_score]
    return sorted(filtered, key=lambda x: -scores.get(x, 0))


def _fill_bet(scored_ranked, need, fallback_history, used_set):
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
# 現行冠軍（McNemar 基準）
# ===================================================================

def pred_midfreq_acb_2bet_ref(history):
    """MidFreq+ACB 2注 (ADOPTED 基準)"""
    mf_sc = midfreq_scores_539(history)
    bet1 = sorted(_ranked_excl(mf_sc, set())[:PICK])
    a_sc = acb_scores_539(history)
    excl = set(bet1)
    bet2 = _fill_bet(_ranked_excl(a_sc, excl), PICK, history, excl)
    return [bet1, bet2]


def pred_acb_markov_fourier_3bet_ref(history):
    """ACB+Markov+Fourier 3注 (PROVISIONAL 冠軍)"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)
    m_sc = markov_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(m_sc, excl), PICK, history, excl)
    excl2 = excl | set(bet2)
    f_sc = fourier_scores_539(history)
    bet3 = _fill_bet(_ranked_excl(f_sc, excl2, min_score=0), PICK, history, excl2)
    return [bet1, bet2, bet3]


# ===================================================================
# P0: ExtremeCol 策略（gap≥25 極端冷）
# ===================================================================

def pred_extremecol_1bet(history):
    """S1: ExtremeCol 單注 — gap≥25 極端冷獨立校準"""
    ec_sc = extreme_cold_scores_539(history)
    # 當無 gap≥25 號碼時退回 ACB
    if max(ec_sc.values()) == 0:
        ec_sc = acb_scores_539(history)
    ranked = _ranked_excl(ec_sc, set())
    return [sorted(ranked[:PICK])]


def pred_midfreq_extremecol_2bet(history):
    """S2: MidFreq + ExtremeCol 2注 (★主要假設)

    假設性覆蓋：115000061 → MidFreq=[12,15] + ExtremeCol=[07,38] = 4/5
    MidFreq 捕捉均值回歸區，ExtremeCol 捕捉極端冷區，天然正交。
    """
    mf_sc = midfreq_scores_539(history)
    bet1 = sorted(_ranked_excl(mf_sc, set())[:PICK])
    excl = set(bet1)
    ec_sc = extreme_cold_scores_539(history)
    if max(ec_sc.values()) == 0:
        ec_sc = acb_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(ec_sc, excl), PICK, history, excl)
    return [bet1, bet2]


def pred_acb_extremecol_2bet(history):
    """S3: ACB + ExtremeCol 2注"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)
    ec_sc = extreme_cold_scores_539(history)
    if max(ec_sc.values()) == 0:
        ec_sc = acb_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(ec_sc, excl), PICK, history, excl)
    return [bet1, bet2]


def pred_acb_markov_extremecol_3bet(history):
    """S4: ACB + Markov + ExtremeCol 3注"""
    a_sc = acb_scores_539(history)
    bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
    excl = set(bet1)
    m_sc = markov_scores_539(history)
    bet2 = _fill_bet(_ranked_excl(m_sc, excl), PICK, history, excl)
    excl2 = excl | set(bet2)
    ec_sc = extreme_cold_scores_539(history)
    if max(ec_sc.values()) == 0:
        ec_sc = acb_scores_539(history)
    bet3 = _fill_bet(_ranked_excl(ec_sc, excl2), PICK, history, excl2)
    return [bet1, bet2, bet3]


# ===================================================================
# P1: Conditional Fourier 策略
# ===================================================================

def _make_condfourier_pred(fourier_threshold):
    """工廠函數: 生成指定 Fourier 門檻的 Conditional 3注 pred"""
    def pred_func(history):
        a_sc = acb_scores_539(history)
        bet1 = sorted(_ranked_excl(a_sc, set())[:PICK])
        excl = set(bet1)

        m_sc = markov_scores_539(history)
        bet2 = _fill_bet(_ranked_excl(m_sc, excl), PICK, history, excl)
        excl2 = excl | set(bet2)

        # Conditional: Fourier 信號強度判定
        f_sc = fourier_scores_539(history)
        max_f = max(f_sc.values()) if f_sc else 0

        if max_f > fourier_threshold:
            # 信號強 → 使用 Fourier
            bet3 = _fill_bet(_ranked_excl(f_sc, excl2, min_score=0), PICK, history, excl2)
        else:
            # 信號弱 → 切換 LagEcho
            l_sc = lag_echo_scores_539(history)
            bet3 = _fill_bet(_ranked_excl(l_sc, excl2), PICK, history, excl2)

        return [bet1, bet2, bet3]

    pred_func.__name__ = f'pred_cond_fourier_{fourier_threshold}'
    pred_func.__doc__ = f'ACB+Markov+CondFourier(thresh={fourier_threshold}) 3注'
    return pred_func


# ===================================================================
# 回測引擎
# ===================================================================

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=1,
                 match_threshold=2, verbose=False):
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
            assert len(bets) == n_bets, f"bets={len(bets)} expected={n_bets}"
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
        'hits': hits, 'total': total, 'rate': rate,
        'baseline': baseline, 'edge': edge, 'z': z,
        'hit_details': hit_details,
    }


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=1,
                          match_threshold=2, n_perm=200):
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
        'real_rate': real_rate, 'perm_mean': perm_mean,
        'perm_std': float(perm_std), 'signal_edge': signal_edge,
        'perm_z': perm_z, 'p_value': p_value, 'n_perm': n_perm,
    }


def mcnemar_test(details_a, details_b):
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
        'both_hit': both_hit, 'a_only': a_only, 'b_only': b_only,
        'both_miss': both_miss, 'chi2': round(chi2, 4),
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


def run_strategy(name, func, n_bets, all_draws, run_perm=True):
    print(f"\n  --- {name} ---")
    window_results = {}
    for periods in [150, 500, 1500]:
        r = backtest_539(func, all_draws, periods, n_bets, match_threshold=2)
        window_results[periods] = r
        star = ' *' if r['edge'] > 0 else ''
        print(f"    {periods:4d}p: rate={r['rate']:.2f}%  edge={r['edge']:+.2f}%  z={r['z']:.2f}{star}")

    e150 = window_results[150]['edge']
    e500 = window_results[500]['edge']
    e1500 = window_results[1500]['edge']
    stab = stability_label(e150, e500, e1500)
    print(f"    Stability: {stab}")

    perm_p, signal_edge = None, None
    if run_perm and e1500 > 0:
        print(f"    Permutation test (200x)...")
        pr = permutation_test_539(func, all_draws, 1500, n_bets, n_perm=200)
        perm_p = round(pr['p_value'], 4)
        signal_edge = round(pr['signal_edge'], 2)
        sig = '**' if perm_p < 0.01 else ('*' if perm_p < 0.05 else '')
        print(f"    Perm p={perm_p:.4f}{sig}  signal_edge={signal_edge:+.2f}%")
    elif e1500 <= 0:
        print(f"    1500p edge<=0, skip Perm")

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


# ===================================================================
# 主程式
# ===================================================================

def main():
    t0 = time.time()

    db = DatabaseManager(db_path=os.path.join(
        project_root, 'lottery_api', 'data', 'lottery_v2.db'
    ))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"Loaded {len(all_draws)} draws (latest: {all_draws[-1]['draw']})")

    strategies = {}

    # ===== P0: ExtremeCol 策略 =====
    print("\n" + "=" * 70)
    print("  P0: ExtremeCol (gap>=25)")
    print("=" * 70)

    strategies['ExtremeCol_1bet'] = run_strategy(
        'S1: ExtremeCol_1bet', pred_extremecol_1bet, 1, all_draws
    )
    strategies['MidFreq_ExtremeCol_2bet'] = run_strategy(
        'S2: MidFreq_ExtremeCol_2bet', pred_midfreq_extremecol_2bet, 2, all_draws
    )
    strategies['ACB_ExtremeCol_2bet'] = run_strategy(
        'S3: ACB_ExtremeCol_2bet', pred_acb_extremecol_2bet, 2, all_draws
    )
    strategies['ACB_Markov_ExtremeCol_3bet'] = run_strategy(
        'S4: ACB_Markov_ExtremeCol_3bet', pred_acb_markov_extremecol_3bet, 3, all_draws
    )

    # ===== P1: Conditional Fourier =====
    print("\n" + "=" * 70)
    print("  P1: Conditional Fourier / LagEcho")
    print("=" * 70)

    # 測試多個 Fourier 門檻
    best_cond = None
    best_cond_edge = -999
    for ft in FOURIER_THRESHOLDS:
        name = f'CondFourier_{ft}_3bet'
        fn = _make_condfourier_pred(ft)
        result = run_strategy(f'S5-{ft}: ACB_Markov_CondFourier', fn, 3, all_draws,
                              run_perm=False)  # 先不跑perm，選最佳後再跑
        strategies[name] = result
        if result['edge_1500p'] > best_cond_edge:
            best_cond_edge = result['edge_1500p']
            best_cond = ft

    # 最佳門檻跑完整 Permutation
    if best_cond is not None and best_cond_edge > 0:
        best_name = f'CondFourier_{best_cond}_3bet'
        print(f"\n  Best threshold={best_cond} (edge={best_cond_edge:+.2f}%), run Perm...")
        fn = _make_condfourier_pred(best_cond)
        full_result = run_strategy(
            f'S5-BEST: CondFourier_{best_cond}', fn, 3, all_draws, run_perm=True
        )
        strategies[best_name] = full_result  # 覆蓋先前結果

    # ===== 基準（McNemar 用）=====
    print("\n  --- Reference champions (McNemar) ---")
    ref_2bet = backtest_539(pred_midfreq_acb_2bet_ref, all_draws, 1500, 2)
    ref_3bet = backtest_539(pred_acb_markov_fourier_3bet_ref, all_draws, 1500, 3)
    print(f"    MidFreq+ACB 2bet:        edge={ref_2bet['edge']:+.2f}%")
    print(f"    ACB+Markov+Fourier 3bet: edge={ref_3bet['edge']:+.2f}%")

    # ===== McNemar =====
    print("\n  --- McNemar ---")
    mcnemar_results = {}

    # S2 vs MidFreq+ACB
    mc = mcnemar_test(
        strategies['MidFreq_ExtremeCol_2bet']['_hit_details_1500'],
        ref_2bet['hit_details']
    )
    mcnemar_results['S2_vs_MidFreq_ACB'] = mc
    print(f"    S2 vs MidFreq+ACB: a={mc['a_only']} b={mc['b_only']} "
          f"chi2={mc['chi2']:.3f} p={mc['p_value']:.4f} W={mc['winner']}")

    # S3 vs MidFreq+ACB
    mc = mcnemar_test(
        strategies['ACB_ExtremeCol_2bet']['_hit_details_1500'],
        ref_2bet['hit_details']
    )
    mcnemar_results['S3_vs_MidFreq_ACB'] = mc
    print(f"    S3 vs MidFreq+ACB: a={mc['a_only']} b={mc['b_only']} "
          f"chi2={mc['chi2']:.3f} p={mc['p_value']:.4f} W={mc['winner']}")

    # S4 vs AMF 3bet
    mc = mcnemar_test(
        strategies['ACB_Markov_ExtremeCol_3bet']['_hit_details_1500'],
        ref_3bet['hit_details']
    )
    mcnemar_results['S4_vs_AMF'] = mc
    print(f"    S4 vs AMF 3bet:    a={mc['a_only']} b={mc['b_only']} "
          f"chi2={mc['chi2']:.3f} p={mc['p_value']:.4f} W={mc['winner']}")

    # Best CondFourier vs AMF 3bet
    if best_cond is not None:
        best_name = f'CondFourier_{best_cond}_3bet'
        mc = mcnemar_test(
            strategies[best_name]['_hit_details_1500'],
            ref_3bet['hit_details']
        )
        mcnemar_results['S5_best_vs_AMF'] = mc
        print(f"    S5({best_cond}) vs AMF: a={mc['a_only']} b={mc['b_only']} "
              f"chi2={mc['chi2']:.3f} p={mc['p_value']:.4f} W={mc['winner']}")

    # ===== 晉級判定 =====
    print("\n  --- Verdict ---")
    for name, s in strategies.items():
        e = s['edge_1500p']
        p = s['perm_p']
        stab = s['stability']
        if stab == 'STABLE' and p is not None and p < 0.05:
            verdict = 'CANDIDATE (STABLE + perm OK)'
        elif stab == 'STABLE' and p is not None and p < 0.1:
            verdict = 'BORDERLINE (need more data)'
        elif e <= 0:
            verdict = 'REJECT (edge<=0)'
        elif p is None:
            verdict = f'PENDING perm (edge={e:+.2f}%)'
        else:
            verdict = f'REJECT (perm_p={p})'
        print(f"    {name:<35}: {verdict}")

    # ===== 清理 & 輸出 =====
    for s in strategies.values():
        s.pop('_hit_details_1500', None)

    elapsed = time.time() - t0
    save_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(all_draws),
        'elapsed_seconds': round(elapsed, 1),
        'script': 'backtest_539_extreme_adaptive.py',
        'extreme_threshold': EXTREME_THRESHOLD,
        'fourier_thresholds_tested': FOURIER_THRESHOLDS,
        'best_fourier_threshold': best_cond,
        'champion_reference': {
            'ACB_Markov_Fourier_3bet': {'edge_1500p': round(ref_3bet['edge'], 2)},
            'MidFreq_ACB_2bet': {'edge_1500p': round(ref_2bet['edge'], 2)},
        },
        'strategies': strategies,
        'mcnemar': mcnemar_results,
    }

    output_path = os.path.join(project_root, 'backtest_539_extreme_adaptive_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

    print(f"\n  Results saved: {output_path}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == '__main__':
    main()
