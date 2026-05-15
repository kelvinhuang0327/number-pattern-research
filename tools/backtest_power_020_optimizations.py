#!/usr/bin/env python3
"""
威力彩 PP3v2 + 特別號CSN + Markov+Echo 2注 — 020期優化
=======================================================
Changes vs PP3v1:
  1. Fourier window 500 -> 100 (P0)
  2. PP3 bet2: Fourier次優 -> Deviation+Echo混合 (P1)
  3. 特別號 Cold Safety Net: Gap>=15 強制候選 (P0)
  4. 新增 Markov+Echo 2注策略 (P1)

回測驗證目標:
  - 1500期三窗口 (150/500/1500) Edge > baseline
  - Permutation test p < 0.05
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

MAX_NUM = 38
PICK = 6


# ========== 基礎工具 ==========

def fourier_scores(history, window=100):
    """Fourier 週期分數 (默認 w=100，020期優化)"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    if w < 10:
        return np.zeros(MAX_NUM + 1)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h_slice):
            if n in d['numbers']:
                bh[idx] = 1
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
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def deviation_echo_scores(history, dev_window=50, echo_lags=None):
    """Deviation + Echo 混合分數 (PP3v2 注2用)

    Deviation: 近50期頻率偏差 (捕捉高頻號)
    Echo: Lag-1/2/3 加權 (捕捉短期重複動量)
    """
    if echo_lags is None:
        echo_lags = {1: 1.5, 2: 2.0, 3: 1.0}

    recent = history[-dev_window:] if len(history) >= dev_window else history
    expected = len(recent) * PICK / MAX_NUM

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1

    scores = {}
    for n in range(1, MAX_NUM + 1):
        # Deviation component (normalize to ~[0,1])
        dev = (freq.get(n, 0) - expected) / max(expected, 1)
        # Echo component
        echo = 0.0
        for k, w in echo_lags.items():
            if len(history) >= k:
                if n in history[-k]['numbers']:
                    echo += w
        # Combined (dev weight=0.5, echo weight=0.5)
        scores[n] = dev * 0.5 + echo * 0.5

    return scores


def markov_scores(history, window=30):
    """Markov 轉移分數"""
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            if cn > MAX_NUM:
                continue
            if cn not in transitions:
                transitions[cn] = Counter()
            for nn in recent[i + 1]['numbers']:
                if nn <= MAX_NUM:
                    transitions[cn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        if pn > MAX_NUM:
            continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] += cnt / total
    return scores


def echo_scores(history, lag_weights=None):
    """Lag-k 回聲分數"""
    if lag_weights is None:
        lag_weights = {1: 1.5, 2: 2.0, 3: 1.0}
    scores = {}
    for n in range(1, MAX_NUM + 1):
        s = 0.0
        for k, w in lag_weights.items():
            if len(history) >= k and n in history[-k]['numbers']:
                s += w
        scores[n] = s
    return scores


# ========== PP3v2: 優化3注策略 ==========

def generate_pp3v2(history):
    """PP3v2: Fourier(w100) + Dev+Echo + Cold
    
    注1: Fourier(w=100) Top6 — 週期信號
    注2: Deviation+Echo混合 Top6 (排除注1) — 捕捉近期動量+重複
    注3: Cold numbers (排除注1+2) — 冷號補償
    """
    # 注1: Fourier (window=100)
    f_scores = fourier_scores(history, window=100)
    f_ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: f_scores[n], reverse=True)
    bet1 = sorted(f_ranked[:PICK])
    exclude1 = set(bet1)

    # 注2: Deviation+Echo (排除注1)
    de_scores = deviation_echo_scores(history, dev_window=50)
    de_candidates = [(n, de_scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude1]
    de_candidates.sort(key=lambda x: x[1], reverse=True)
    bet2 = sorted([n for n, _ in de_candidates[:PICK]])
    exclude2 = exclude1 | set(bet2)

    # 注3: Cold numbers (排除注1+2)
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1
    cold_candidates = [(n, freq.get(n, 0)) for n in range(1, MAX_NUM + 1) if n not in exclude2]
    cold_candidates.sort(key=lambda x: x[1])  # Coldest first
    bet3 = sorted([n for n, _ in cold_candidates[:PICK]])

    return [bet1, bet2, bet3]


# ========== PP3v2 + Ort: 優化5注策略 ==========

def generate_pp3v2_5bet(history):
    """PP3v2 + 正交2注 = 5注覆蓋"""
    bets_3 = generate_pp3v2(history)
    used = set()
    for b in bets_3:
        used.update(b)

    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM:
                freq[n] += 1

    leftover = [n for n in range(1, MAX_NUM + 1) if n not in used]
    leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)

    bet4 = sorted(leftover[:PICK])
    bet5 = sorted(leftover[PICK:PICK*2]) if len(leftover) >= PICK*2 else sorted(leftover[PICK:])

    return bets_3 + [bet4, bet5]


# ========== Markov+Echo 2注策略 ==========

def generate_markov_echo_2bet(history):
    """Markov+Echo 2注 (020期診斷最佳混合方案)
    
    注1: Markov(w30)+Echo混合 Top6
    注2: Fourier(w100) Top6 (排除注1，週期補償)
    """
    # 注1: Markov + Echo 混合
    mk_scores = markov_scores(history, window=30)
    ek_scores = echo_scores(history)

    # Normalize
    mk_max = max(mk_scores.values()) if mk_scores else 1
    ek_max = max(ek_scores.values()) if ek_scores else 1

    combined = {}
    for n in range(1, MAX_NUM + 1):
        mk_norm = mk_scores.get(n, 0) / mk_max if mk_max > 0 else 0
        ek_norm = ek_scores.get(n, 0) / ek_max if ek_max > 0 else 0
        combined[n] = mk_norm * 0.5 + ek_norm * 0.5

    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: combined[n], reverse=True)
    bet1 = sorted(ranked[:PICK])
    exclude = set(bet1)

    # 注2: Fourier(w=100) 正交
    f_scores = fourier_scores(history, window=100)
    f_candidates = [(n, f_scores[n]) for n in range(1, MAX_NUM + 1) if n not in exclude]
    f_candidates.sort(key=lambda x: x[1], reverse=True)
    bet2 = sorted([n for n, _ in f_candidates[:PICK]])

    return [bet1, bet2]


# ========== 特別號 Cold Safety Net ==========

def special_with_cold_safety_net(history, gap_threshold=15):
    """特別號預測 + Cold Safety Net
    
    V3 MAB 基礎上:
    - 如果某特別號 Gap >= threshold，強制納入候選
    - 避免極端冷號回歸時的遺漏
    """
    # 基礎 V3 預測
    try:
        sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))
        from models.special_predictor import PowerLottoSpecialPredictor
        rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
        sp = PowerLottoSpecialPredictor(rules)
        base_top = sp.predict_top_n(history, n=3)
    except Exception:
        # Fallback
        freq = Counter(d.get('special', 0) for d in history[-50:] if d.get('special'))
        base_top = [n for n, _ in freq.most_common(3)]

    # Cold Safety Net: 檢查 Gap>=threshold 的特別號
    last_seen = {}
    for i, d in enumerate(history):
        sp_val = d.get('special')
        if sp_val:
            last_seen[sp_val] = i
    current_idx = len(history)

    cold_specials = []
    for n in range(1, 9):
        gap = current_idx - last_seen.get(n, -1)
        if gap >= gap_threshold and n not in base_top:
            cold_specials.append((n, gap))

    # 如果有極冷特別號，替換 base_top 的最後一個
    if cold_specials:
        cold_specials.sort(key=lambda x: -x[1])  # 最冷的優先
        coldest = cold_specials[0][0]
        # 替換 top3 的第3名
        if coldest not in base_top:
            result = list(base_top[:2]) + [coldest]
        else:
            result = base_top
    else:
        result = base_top

    return result[:3]


# ========== 回測框架 ==========

def backtest_strategy(draws, strategy_fn, n_bets, label="", start_offset=100):
    """通用回測框架
    
    Args:
        draws: 全部歷史期數
        strategy_fn: 策略函數 history -> [bet1, bet2, ...]
        n_bets: 使用的注數
        label: 策略名稱
        start_offset: 從第幾期開始回測
    """
    total = len(draws)
    if total < start_offset + 100:
        print(f"  數據不足: {total} < {start_offset + 100}")
        return None

    results = []
    for i in range(start_offset, total):
        history = draws[:i]
        actual = set(draws[i]['numbers'][:6])
        actual_special = draws[i].get('special', 0)

        bets = strategy_fn(history)[:n_bets]
        
        # 計算命中
        all_predicted = set()
        for bet in bets:
            all_predicted.update(bet)
        
        hit_any = len(all_predicted & actual) > 0
        hit_count = len(all_predicted & actual)
        
        results.append({
            'hit_any': hit_any,
            'hit_count': hit_count,
            'n_bets': n_bets,
        })

    # 統計
    hit_rates = [r['hit_any'] for r in results]
    total_periods = len(results)
    
    # Random baseline for n_bets
    # P(hit>=1 in k bets of 6 from 38) = 1 - C(32,6)^k / C(38,6)^k
    # NOTE: This is P(at least 1 number hit across all bets combined).
    # For hit>=2 or hit>=3 edge, use a different baseline.
    from math import comb
    p_miss_1 = comb(MAX_NUM - PICK, PICK) / comb(MAX_NUM, PICK)
    baseline = 1 - p_miss_1 ** n_bets
    
    actual_rate = sum(hit_rates) / total_periods
    edge = actual_rate - baseline
    
    # 三窗口
    windows = {
        '150p': results[-150:] if len(results) >= 150 else results,
        '500p': results[-500:] if len(results) >= 500 else results,
        f'{total_periods}p': results,
    }
    
    window_results = {}
    for wname, wdata in windows.items():
        w_rate = sum(r['hit_any'] for r in wdata) / len(wdata)
        w_edge = w_rate - baseline
        window_results[wname] = {'rate': w_rate, 'edge': w_edge, 'n': len(wdata)}
    
    # Z-score
    import math
    se = math.sqrt(baseline * (1 - baseline) / total_periods)
    z = edge / se if se > 0 else 0
    
    return {
        'label': label,
        'n_bets': n_bets,
        'total_periods': total_periods,
        'actual_rate': actual_rate,
        'baseline': baseline,
        'edge': edge,
        'z_score': z,
        'windows': window_results,
        'results': results,
    }


def permutation_test(results, baseline, n_perms=1000):
    """Binomial test: P(observed hits or more | baseline rate)
    
    NOTE: Old version shuffled binary hits array, which doesn't change
    the mean → p always = 1.0 (BUG). Replaced with exact binomial test.
    """
    from scipy.stats import binomtest
    actual_hits = sum(r['hit_any'] for r in results)
    n = len(results)
    result = binomtest(actual_hits, n, baseline, alternative='greater')
    return result.pvalue


def run_full_backtest():
    """運行所有策略的完整回測"""
    from lottery_api.database import DatabaseManager
    
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    print(f"總期數: {len(draws)}")
    print(f"最新: {draws[-1]['draw']} ({draws[-1]['date']})")
    print("=" * 80)
    
    # ===== 策略列表 =====
    strategies = [
        # 現行策略 (baseline comparison)
        {
            'label': 'PP3v1 (現行 Fourier w500)',
            'fn': lambda h: generate_pp3v1_legacy(h),
            'bets': [2, 3],
        },
        # 新策略
        {
            'label': 'PP3v2 (Fourier w100 + Dev+Echo + Cold)',
            'fn': lambda h: generate_pp3v2(h),
            'bets': [2, 3],
        },
        # 新 Markov+Echo 2注
        {
            'label': 'Markov+Echo 2bet',
            'fn': lambda h: generate_markov_echo_2bet(h),
            'bets': [2],
        },
        # PP3v2 5注
        {
            'label': 'PP3v2 5bet (正交)',
            'fn': lambda h: generate_pp3v2_5bet(h),
            'bets': [5],
        },
        # 原版5注
        {
            'label': 'PP3v1 5bet (現行正交)',
            'fn': lambda h: generate_pp3v1_5bet_legacy(h),
            'bets': [5],
        },
    ]
    
    all_results = []
    
    for strat in strategies:
        for n_bets in strat['bets']:
            print(f"\n{'='*60}")
            print(f" 回測: {strat['label']} ({n_bets}注)")
            print(f"{'='*60}")
            
            result = backtest_strategy(
                draws, strat['fn'], n_bets,
                label=f"{strat['label']} ({n_bets}bet)",
                start_offset=500  # 確保足夠歷史
            )
            
            if result is None:
                continue
            
            # Permutation test
            perm_p = permutation_test(result['results'], result['baseline'], n_perms=1000)
            result['perm_p'] = perm_p
            
            # 輸出
            print(f"  策略: {result['label']}")
            print(f"  總期數: {result['total_periods']}")
            print(f"  命中率: {result['actual_rate']*100:.2f}% (baseline: {result['baseline']*100:.2f}%)")
            print(f"  Edge: {result['edge']*100:+.2f}%")
            print(f"  Z-score: {result['z_score']:.2f}")
            print(f"  Perm p: {perm_p:.3f}")
            print(f"  三窗口:")
            for wname, wr in result['windows'].items():
                status = "PASS" if wr['edge'] > 0 else "FAIL"
                print(f"    {wname}: rate={wr['rate']*100:.2f}%, edge={wr['edge']*100:+.2f}% [{status}]")
            
            all_results.append(result)
    
    # ===== 特別號 Cold Safety Net 回測 =====
    print(f"\n{'='*60}")
    print(f" 特別號回測: V3 vs V3+CSN (Cold Safety Net)")
    print(f"{'='*60}")
    
    sp_v3_hits = 0
    sp_csn_hits = 0
    sp_total = 0
    
    for i in range(500, len(draws)):
        history = draws[:i]
        actual_sp = draws[i].get('special', 0)
        if actual_sp == 0:
            continue
        sp_total += 1
        
        # V3
        try:
            from models.special_predictor import PowerLottoSpecialPredictor
            rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
            sp_pred = PowerLottoSpecialPredictor(rules)
            v3_top = sp_pred.predict_top_n(history, n=3)
        except Exception:
            freq = Counter(d.get('special', 0) for d in history[-50:] if d.get('special'))
            v3_top = [n for n, _ in freq.most_common(3)]
        
        if actual_sp in v3_top:
            sp_v3_hits += 1
        
        # V3 + CSN
        csn_top = special_with_cold_safety_net(history, gap_threshold=15)
        if actual_sp in csn_top:
            sp_csn_hits += 1
    
    sp_baseline = 3 / 8  # 3 from 8 = 37.5%
    v3_rate = sp_v3_hits / sp_total if sp_total > 0 else 0
    csn_rate = sp_csn_hits / sp_total if sp_total > 0 else 0
    
    print(f"  測試期數: {sp_total}")
    print(f"  隨機基準 (3/8): {sp_baseline*100:.1f}%")
    print(f"  V3 命中率: {v3_rate*100:.2f}% (edge={((v3_rate-sp_baseline)*100):+.2f}%)")
    print(f"  V3+CSN 命中率: {csn_rate*100:.2f}% (edge={((csn_rate-sp_baseline)*100):+.2f}%)")
    print(f"  CSN 增量: {((csn_rate-v3_rate)*100):+.2f}%")
    
    # ===== 總結 =====
    print(f"\n{'='*80}")
    print(f" 回測總結")
    print(f"{'='*80}")
    print(f"{'策略':<40} {'Edge':>8} {'Z':>6} {'perm':>6} {'150p':>8} {'500p':>8} {'全期':>8}")
    print("-" * 80)
    for r in all_results:
        w150 = r['windows'].get('150p', {}).get('edge', 0) * 100
        w500 = r['windows'].get('500p', {}).get('edge', 0) * 100
        w_all_key = [k for k in r['windows'] if k not in ('150p', '500p')][0]
        w_all = r['windows'][w_all_key]['edge'] * 100
        three_pass = all(r['windows'][k]['edge'] > 0 for k in r['windows'])
        marker = " PASS" if three_pass and r['perm_p'] < 0.05 else " FAIL"
        print(f"  {r['label']:<38} {r['edge']*100:>+7.2f}% {r['z_score']:>5.2f} {r['perm_p']:>5.3f} {w150:>+7.2f}% {w500:>+7.2f}% {w_all:>+7.2f}%{marker}")
    
    print(f"\n  特別號: V3+CSN edge={((csn_rate-sp_baseline)*100):+.2f}% (vs V3 {((v3_rate-sp_baseline)*100):+.2f}%)")
    
    return all_results


# ===== Legacy functions for comparison =====

def generate_pp3v1_legacy(history):
    """原版 PP3 (Fourier w=500) — 用於對比"""
    from scipy.fft import fft, fftfreq
    h_slice = history[-500:] if len(history) >= 500 else history
    w = len(h_slice)
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h_slice):
            if n in d['numbers']:
                bh[idx] = 1
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
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    f_rank = np.argsort(scores)[::-1]

    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0:
        idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())

    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0:
        idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())

    exclude = set(bet1) | set(bet2)
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    else:
        echo_nums = []
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers'] if n <= MAX_NUM])
    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])

    return [bet1, bet2, bet3]


def generate_pp3v1_5bet_legacy(history):
    """原版 5注正交 (Fourier w=500)"""
    bets_3 = generate_pp3v1_legacy(history)
    used = set()
    for b in bets_3:
        used.update(b)
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers'] if n <= MAX_NUM])
    leftover = [n for n in range(1, MAX_NUM + 1) if n not in used]
    leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
    bet4 = sorted(leftover[:PICK])
    bet5 = sorted(leftover[PICK:PICK*2]) if len(leftover) >= PICK*2 else sorted(leftover[PICK:])
    return bets_3 + [bet4, bet5]


if __name__ == "__main__":
    run_full_backtest()
