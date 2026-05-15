#!/usr/bin/env python3
"""
=============================================================================
AdaptiveACB 跨彩種回測 — S1~S4 全階段驗證
=============================================================================
S1: ACB 1注回測 (威力彩 + 大樂透) + window sensitivity
S2: 特徵重要性矩陣 (10+ 特徵 × 3 彩種)
S3: 2注組合搜尋 (ACB + 正交信號)
S4: 3注組合搜尋 + 三窗口驗證 + permutation
=============================================================================
"""

import json, math, os, random, sys, time, warnings
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
import numpy as np
from scipy import stats as scipy_stats
from scipy.fft import fft, fftfreq

warnings.filterwarnings('ignore')

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager
from tools.adaptive_acb import AdaptiveACB

# ─── Constants ────────────────────────────────────────────────────
SEED = 42
LOTTERY_CONFIGS = {
    'POWER_LOTTO': {
        'max_num': 38, 'pick': 6,
        'p_single_m3': 0.0387,  # M3+ 單注基準
        'match_threshold': 3,    # M3+
        'label': '威力彩',
    },
    'BIG_LOTTO': {
        'max_num': 49, 'pick': 6,
        'p_single_m3': 0.0186,  # M3+ 單注基準
        'match_threshold': 3,    # M3+
        'label': '大樂透',
    },
    'DAILY_539': {
        'max_num': 39, 'pick': 5,
        'p_single_m3': 0.01004,  # M3+ 單注基準
        'p_single_m2': 0.1140,   # M2+ 單注基準
        'match_threshold': 2,    # M2+ (539 用 M2+)
        'label': '今彩539',
    },
}


def baseline_multi(p_single, n_bets):
    """N注至少1注命中的基準"""
    return 1 - (1 - p_single) ** n_bets


def get_numbers(draw):
    n = draw.get('numbers', [])
    if isinstance(n, str):
        n = json.loads(n)
    return list(n)


def load_data(lottery_type):
    db_path = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws(lottery_type)
    draws = sorted(raw, key=lambda x: (x['date'], x['draw']))
    return draws


# ─── 回測引擎 ─────────────────────────────────────────────────────
def backtest_nbets(predict_func, all_draws, lottery_type, n_bets,
                   test_periods=1500, seed=42, min_train=100):
    """
    通用 N 注回測引擎
    predict_func(hist) -> list of n_bets bets, each bet is sorted list
    """
    random.seed(seed)
    np.random.seed(seed)
    cfg = LOTTERY_CONFIGS[lottery_type]
    pick = cfg['pick']
    mt = cfg['match_threshold']

    if lottery_type == 'DAILY_539':
        p_single = cfg.get('p_single_m2', cfg['p_single_m3'])
    else:
        p_single = cfg['p_single_m3']
    bl = baseline_multi(p_single, n_bets)

    results = []
    for i in range(test_periods):
        tidx = len(all_draws) - test_periods + i
        if tidx < min_train:
            continue
        target = all_draws[tidx]
        hist = all_draws[:tidx]
        actual = set(get_numbers(target))

        try:
            bets = predict_func(hist)
            if not isinstance(bets[0], list):
                bets = [bets]  # 單注包裝
        except Exception as e:
            continue

        hit = any(len(set(bet) & actual) >= mt for bet in bets)
        per_bet_matches = [len(set(bet) & actual) for bet in bets]
        results.append({
            'hit': hit,
            'per_bet': per_bet_matches,
            'max_match': max(per_bet_matches),
        })

    total = len(results)
    if total == 0:
        return {'total': 0, 'hits': 0, 'rate': 0, 'edge': 0, 'baseline': bl}

    hits = sum(1 for r in results if r['hit'])
    rate = hits / total
    edge = rate - bl

    # z-test
    se = math.sqrt(bl * (1 - bl) / total) if total > 0 else 1e-10
    z = (rate - bl) / se if se > 0 else 0
    p_val = 1 - scipy_stats.norm.cdf(z)

    return {
        'total': total,
        'hits': hits,
        'rate': rate,
        'baseline': bl,
        'edge': edge,
        'z': z,
        'p': p_val,
        'avg_max_match': np.mean([r['max_match'] for r in results]),
        'results': results,
    }


def three_window(predict_func, all_draws, lottery_type, n_bets,
                 seed=42, min_train=100):
    """三窗口驗證 (150/500/1500)"""
    out = {}
    for period in [150, 500, 1500]:
        if len(all_draws) < period + min_train:
            continue
        r = backtest_nbets(predict_func, all_draws, lottery_type, n_bets,
                           period, seed, min_train)
        r.pop('results', None)
        out[period] = r
    return out


def permutation_test(predict_func, all_draws, lottery_type, n_bets,
                     test_periods=500, n_perms=200, seed=42, min_train=100):
    """Permutation test: 策略 vs 隨機 baseline"""
    cfg = LOTTERY_CONFIGS[lottery_type]
    pick = cfg['pick']
    max_num = cfg['max_num']
    mt = cfg['match_threshold']

    # Actual
    actual_r = backtest_nbets(predict_func, all_draws, lottery_type, n_bets,
                              test_periods, seed, min_train)
    actual_rate = actual_r['rate']

    # Random permutations
    perm_rates = []
    for i in range(n_perms):
        rng = random.Random(seed * 10000 + i)

        def random_predict(hist, _rng=rng, _n=n_bets, _p=pick, _m=max_num):
            bets = []
            for _ in range(_n):
                bets.append(sorted(_rng.sample(range(1, _m + 1), _p)))
            return bets

        r = backtest_nbets(random_predict, all_draws, lottery_type, n_bets,
                           test_periods, seed + i + 99999, min_train)
        perm_rates.append(r['rate'])

    pm = np.mean(perm_rates)
    ps = np.std(perm_rates, ddof=1) or 1e-10
    z = (actual_rate - pm) / ps
    p_emp = (np.sum(np.array(perm_rates) >= actual_rate) + 1) / (n_perms + 1)

    return {
        'actual_rate': actual_rate,
        'actual_hits': actual_r['hits'],
        'actual_total': actual_r['total'],
        'perm_mean': pm,
        'perm_std': ps,
        'z_score': z,
        'p_empirical': p_emp,
        'signal_edge': actual_rate - pm,
        'n_perms': n_perms,
    }


# ═══════════════════════════════════════════════════════════════════
#  S1: ACB 1注回測 + Window Sensitivity
# ═══════════════════════════════════════════════════════════════════

def s1_acb_single_bet(all_draws, lottery_type):
    """S1: ACB 1注回測"""
    cfg = LOTTERY_CONFIGS[lottery_type]
    print(f"\n{'='*70}")
    print(f"  S1: ACB 1注回測 — {cfg['label']} ({cfg['max_num']}選{cfg['pick']})")
    print(f"  數據: {len(all_draws)} 期")
    print(f"{'='*70}")

    acb = AdaptiveACB(lottery_type)

    def predict_1bet(hist):
        return [acb.predict(hist)]

    # 三窗口
    print("\n  [1] 三窗口驗證...")
    tw = three_window(predict_1bet, all_draws, lottery_type, 1)
    edges = {}
    for period in [150, 500, 1500]:
        if period not in tw:
            continue
        r = tw[period]
        marker = '★' if r['edge'] > 0 and r['p'] < 0.05 else ('+' if r['edge'] > 0 else '-')
        print(f"    {period}p: rate={r['rate']*100:.3f}% baseline={r['baseline']*100:.3f}% "
              f"edge={r['edge']*100:+.3f}% z={r['z']:.2f} p={r['p']:.4f} {marker}")
        edges[period] = r['edge']

    # 穩定性判定
    all_positive = all(edges.get(p, -1) > 0 for p in [150, 500, 1500] if p in tw)
    if all_positive:
        stability = 'STABLE'
    elif edges.get(1500, -1) > 0 and edges.get(150, 0) <= 0:
        stability = 'LATE_BLOOMER'
    elif all(e <= 0 for e in edges.values()):
        stability = 'INEFFECTIVE'
    else:
        stability = 'MIXED'
    print(f"    → 穩定性: {stability}")

    # Window sensitivity
    print("\n  [2] Window Sensitivity Sweep...")
    best_window = 100
    best_edge = -999
    for w in [30, 50, 80, 100, 150, 200, 300]:
        acb_w = AdaptiveACB(lottery_type, window=w)

        def predict_w(hist, _acb=acb_w):
            return [_acb.predict(hist)]

        r = backtest_nbets(predict_w, all_draws, lottery_type, 1, 1500, SEED, 100)
        marker = '★' if r['edge'] > best_edge and r['edge'] > 0 else ''
        print(f"    window={w:>3}: edge={r['edge']*100:+.3f}% z={r['z']:.2f} {marker}")
        if r['edge'] > best_edge:
            best_edge = r['edge']
            best_window = w

    print(f"    → 最佳 window = {best_window} (edge={best_edge*100:+.3f}%)")

    # Permutation test (使用最佳 window)
    print(f"\n  [3] Permutation Test (window={best_window}, 200次洗牌)...")
    acb_best = AdaptiveACB(lottery_type, window=best_window)

    def predict_best(hist, _acb=acb_best):
        return [_acb.predict(hist)]

    perm = permutation_test(predict_best, all_draws, lottery_type, 1,
                            test_periods=1500, n_perms=200, seed=SEED)
    print(f"    Actual rate: {perm['actual_rate']*100:.3f}%")
    print(f"    Perm mean:   {perm['perm_mean']*100:.3f}%")
    print(f"    Signal Edge: {perm['signal_edge']*100:+.3f}%")
    print(f"    z={perm['z_score']:.2f}  p={perm['p_empirical']:.4f}")

    passed = perm['signal_edge'] > 0 and perm['p_empirical'] < 0.05
    print(f"    → {'✅ PASS' if passed else '❌ FAIL'}")

    return {
        'lottery': lottery_type,
        'label': cfg['label'],
        'three_window': tw,
        'stability': stability,
        'best_window': best_window,
        'best_edge': best_edge,
        'permutation': perm,
        'passed': passed,
    }


# ═══════════════════════════════════════════════════════════════════
#  S2: 特徵重要性矩陣
# ═══════════════════════════════════════════════════════════════════

def _feature_freq_deficit(hist, max_num, pick, window=100):
    """純頻率赤字選號"""
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for n in range(1, max_num + 1):
        counter[n] = 0
    for d in recent:
        for n in get_numbers(d):
            counter[n] += 1
    expected = len(recent) * pick / max_num
    scores = {n: expected - counter[n] for n in range(1, max_num + 1)}
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:pick])


def _feature_gap_score(hist, max_num, pick, window=100):
    """純 gap score 選號"""
    recent = hist[-window:] if len(hist) >= window else hist
    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_numbers(d):
            last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, max_num + 1)}
    ranked = sorted(gaps, key=lambda x: -gaps[x])
    return sorted(ranked[:pick])


def _feature_cold(hist, max_num, pick, window=100):
    """冷號 (頻率最低)"""
    freq = Counter()
    for d in hist[-window:]:
        for n in get_numbers(d):
            freq[n] += 1
    cold = sorted(range(1, max_num + 1), key=lambda n: freq.get(n, 0))
    return sorted(cold[:pick])


def _feature_hot(hist, max_num, pick, window=50):
    """熱號 (近期頻率最高)"""
    freq = Counter()
    for d in hist[-window:]:
        for n in get_numbers(d):
            freq[n] += 1
    hot = sorted(range(1, max_num + 1), key=lambda n: -freq.get(n, 0))
    return sorted(hot[:pick])


def _feature_echo_lag2(hist, max_num, pick):
    """Lag-2 回聲 (2期前號碼優先)"""
    if len(hist) < 3:
        return sorted(random.sample(range(1, max_num + 1), pick))
    prev2 = set(get_numbers(hist[-2]))
    prev1 = set(get_numbers(hist[-1]))
    # Echo: 2期前出現但上期沒出現的號碼
    echo_candidates = list(prev2 - prev1)
    # 不足則用冷號補
    if len(echo_candidates) < pick:
        freq = Counter()
        for d in hist[-100:]:
            for n in get_numbers(d):
                freq[n] += 1
        rest = sorted([n for n in range(1, max_num + 1) if n not in echo_candidates],
                      key=lambda n: freq.get(n, 0))
        echo_candidates.extend(rest)
    return sorted(echo_candidates[:pick])


def _feature_fourier(hist, max_num, pick, window=500):
    """FFT 週期預測"""
    h = hist[-window:] if len(hist) >= window else hist
    w = len(h)
    scores = {}
    for n in range(1, max_num + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in get_numbers(d):
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        ip = np.where(xf > 0)
        py = np.abs(yf[ip])
        px = xf[ip]
        pk = np.argmax(py)
        fv = px[pk]
        if fv == 0:
            scores[n] = 0.0
            continue
        period = 1 / fv
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    return sorted(ranked[:pick])


def _feature_markov(hist, max_num, pick, window=30):
    """馬可夫轉移機率"""
    h = hist[-window:] if len(hist) >= window else hist
    trans = defaultdict(Counter)
    for i in range(1, len(h)):
        prev = get_numbers(h[i - 1])
        curr = get_numbers(h[i])
        for p in prev:
            for c in curr:
                trans[p][c] += 1
    # 最近一期的號碼
    last_nums = get_numbers(h[-1])
    scores = Counter()
    for p in last_nums:
        for n, cnt in trans[p].items():
            scores[n] += cnt
    ranked = sorted(range(1, max_num + 1), key=lambda n: -scores.get(n, 0))
    return sorted(ranked[:pick])


def _feature_deviation_hot(hist, max_num, pick, window=200):
    """偏差互補-熱 (超過期望頻率最多的號碼)"""
    recent = hist[-window:] if len(hist) >= window else hist
    counter = Counter()
    for d in recent:
        for n in get_numbers(d):
            counter[n] += 1
    expected = len(recent) * pick / max_num
    dev = {n: counter.get(n, 0) - expected for n in range(1, max_num + 1)}
    ranked = sorted(dev, key=lambda x: -dev[x])
    return sorted(ranked[:pick])


def _feature_tail_balance(hist, max_num, pick):
    """尾數平衡 (每個尾數至少出一個)"""
    if len(hist) < 1:
        return sorted(random.sample(range(1, max_num + 1), pick))
    # 計算最近期的尾數分佈，選出欠缺尾數
    freq = Counter()
    for d in hist[-50:]:
        for n in get_numbers(d):
            freq[n % 10] += 1
    # 找出頻率最低的尾數
    all_tails = list(range(10))
    under_tails = sorted(all_tails, key=lambda t: freq.get(t, 0))
    result = []
    for t in under_tails:
        candidates = [n for n in range(1, max_num + 1) if n % 10 == t and n not in result]
        if candidates:
            result.append(candidates[0])
        if len(result) >= pick:
            break
    # 補足
    if len(result) < pick:
        rest = [n for n in range(1, max_num + 1) if n not in result]
        result.extend(rest[:pick - len(result)])
    return sorted(result[:pick])


def _feature_neighbor(hist, max_num, pick):
    """鄰號 (上期號碼 ± 1~2)"""
    if len(hist) < 1:
        return sorted(random.sample(range(1, max_num + 1), pick))
    prev = get_numbers(hist[-1])
    neighbors = set()
    for n in prev:
        for d in [-2, -1, 1, 2]:
            nn = n + d
            if 1 <= nn <= max_num:
                neighbors.add(nn)
    neighbors -= set(prev)
    result = sorted(neighbors)
    if len(result) < pick:
        freq = Counter()
        for d in hist[-100:]:
            for n in get_numbers(d):
                freq[n] += 1
        rest = sorted([n for n in range(1, max_num + 1) if n not in result],
                      key=lambda n: freq.get(n, 0))
        result.extend(rest)
    return sorted(result[:pick])


def _feature_ema_cross(hist, max_num, pick, short_w=20, long_w=100):
    """EMA 交叉 (短期 EMA > 長期 EMA 的號碼)"""
    recent = hist[-long_w:] if len(hist) >= long_w else hist
    w = len(recent)
    scores = {}
    for n in range(1, max_num + 1):
        series = [1 if n in get_numbers(d) else 0 for d in recent]
        # Short EMA
        alpha_s = 2 / (short_w + 1)
        ema_s = series[0]
        for v in series[1:]:
            ema_s = alpha_s * v + (1 - alpha_s) * ema_s
        # Long EMA
        alpha_l = 2 / (long_w + 1)
        ema_l = series[0]
        for v in series[1:]:
            ema_l = alpha_l * v + (1 - alpha_l) * ema_l
        scores[n] = ema_s - ema_l  # 正=短期上升趨勢
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:pick])


def s2_feature_importance(all_draws_dict):
    """S2: 特徵重要性矩陣"""
    print(f"\n{'='*70}")
    print(f"  S2: 特徵重要性矩陣 (10+ 特徵 × 3 彩種)")
    print(f"{'='*70}")

    features = {
        'freq_deficit': lambda h, mx, pk: _feature_freq_deficit(h, mx, pk, 100),
        'gap_score':    lambda h, mx, pk: _feature_gap_score(h, mx, pk, 100),
        'cold_100':     lambda h, mx, pk: _feature_cold(h, mx, pk, 100),
        'hot_50':       lambda h, mx, pk: _feature_hot(h, mx, pk, 50),
        'echo_lag2':    lambda h, mx, pk: _feature_echo_lag2(h, mx, pk),
        'fourier_500':  lambda h, mx, pk: _feature_fourier(h, mx, pk, 500),
        'markov_30':    lambda h, mx, pk: _feature_markov(h, mx, pk, 30),
        'dev_hot_200':  lambda h, mx, pk: _feature_deviation_hot(h, mx, pk, 200),
        'tail_balance': lambda h, mx, pk: _feature_tail_balance(h, mx, pk),
        'neighbor':     lambda h, mx, pk: _feature_neighbor(h, mx, pk),
        'ema_cross':    lambda h, mx, pk: _feature_ema_cross(h, mx, pk),
        'ACB_100':      lambda h, mx, pk: AdaptiveACB(lottery_type=None, max_num=mx, pick=pk, window=100).predict(h),
    }

    matrix = {}
    for lt, draws in all_draws_dict.items():
        cfg = LOTTERY_CONFIGS[lt]
        mx = cfg['max_num']
        pk = cfg['pick']
        mt = cfg['match_threshold']

        if lt == 'DAILY_539':
            bl = cfg.get('p_single_m2', cfg['p_single_m3'])
        else:
            bl = cfg['p_single_m3']

        print(f"\n  ▸ {cfg['label']} ({mx}選{pk}, {len(draws)} 期)")
        print(f"    {'Feature':<16} {'Rate':>8} {'Baseline':>10} {'Edge':>8} {'z':>6} {'Status'}")
        print(f"    {'─'*60}")

        feat_results = {}
        for fname, ffunc in features.items():
            def predict_feat(hist, _ff=ffunc, _mx=mx, _pk=pk):
                return [_ff(hist, _mx, _pk)]

            r = backtest_nbets(predict_feat, draws, lt, 1, 1500, SEED, 100)
            edge = r['edge']
            status = '★' if edge > 0.01 else ('+' if edge > 0 else '-')
            print(f"    {fname:<16} {r['rate']*100:>7.3f}% {bl*100:>9.3f}%  {edge*100:>+7.3f}% {r['z']:>5.2f} {status}")
            feat_results[fname] = {
                'rate': r['rate'], 'edge': edge, 'z': r['z'],
            }

        matrix[lt] = feat_results

    return matrix


# ═══════════════════════════════════════════════════════════════════
#  S3: 2注組合搜尋
# ═══════════════════════════════════════════════════════════════════

def _build_feature_predictors(lottery_type):
    """建立所有可用的單注預測器"""
    cfg = LOTTERY_CONFIGS[lottery_type]
    mx = cfg['max_num']
    pk = cfg['pick']

    predictors = {
        'ACB':          lambda h: AdaptiveACB(lottery_type=None, max_num=mx, pick=pk, window=100).predict(h),
        'freq_deficit': lambda h: _feature_freq_deficit(h, mx, pk, 100),
        'cold':         lambda h: _feature_cold(h, mx, pk, 100),
        'fourier':      lambda h: _feature_fourier(h, mx, pk, 500),
        'echo_lag2':    lambda h: _feature_echo_lag2(h, mx, pk),
        'markov':       lambda h: _feature_markov(h, mx, pk, 30),
        'neighbor':     lambda h: _feature_neighbor(h, mx, pk),
        'dev_hot':      lambda h: _feature_deviation_hot(h, mx, pk, 200),
        'tail_balance': lambda h: _feature_tail_balance(h, mx, pk),
        'gap_score':    lambda h: _feature_gap_score(h, mx, pk, 100),
        'hot':          lambda h: _feature_hot(h, mx, pk, 50),
        'ema_cross':    lambda h: _feature_ema_cross(h, mx, pk),
    }
    return predictors


def s3_2bet_search(all_draws, lottery_type):
    """S3: 2注組合搜尋"""
    cfg = LOTTERY_CONFIGS[lottery_type]
    print(f"\n{'='*70}")
    print(f"  S3: 2注組合搜尋 — {cfg['label']}")
    print(f"{'='*70}")

    predictors = _build_feature_predictors(lottery_type)
    # ACB 必須包含，搜尋 ACB + X
    acb_key = 'ACB'
    other_keys = [k for k in predictors if k != acb_key]

    if lottery_type == 'DAILY_539':
        bl = baseline_multi(cfg.get('p_single_m2', cfg['p_single_m3']), 2)
    else:
        bl = baseline_multi(cfg['p_single_m3'], 2)

    results = []
    print(f"\n    2注基準: {bl*100:.3f}%")
    print(f"    {'Combo':<25} {'Rate':>8} {'Edge':>8} {'z':>6}")
    print(f"    {'─'*55}")

    for key in other_keys:
        combo_name = f"ACB+{key}"

        def predict_2bet(hist, _k=key):
            b1 = predictors[acb_key](hist)
            b2 = predictors[_k](hist)
            return [b1, b2]

        r = backtest_nbets(predict_2bet, all_draws, lottery_type, 2, 1500, SEED, 100)
        r.pop('results', None)
        status = '★' if r['edge'] > 0.01 else ('+' if r['edge'] > 0 else '-')
        print(f"    {combo_name:<25} {r['rate']*100:>7.3f}% {r['edge']*100:>+7.3f}% {r['z']:>5.2f} {status}")
        results.append({'combo': combo_name, **r})

    # 也測試所有非 ACB 的兩兩組合（找出最強對照組）
    print(f"\n    --- 對照組 (非ACB) ---")
    for k1, k2 in combinations(other_keys, 2):
        # 只測試有前景的組合
        if k1 not in ['fourier', 'cold', 'markov', 'neighbor', 'echo_lag2']:
            continue
        if k2 not in ['fourier', 'cold', 'markov', 'neighbor', 'echo_lag2', 'tail_balance']:
            continue
        combo_name = f"{k1}+{k2}"

        def predict_ctrl(hist, _k1=k1, _k2=k2):
            return [predictors[_k1](hist), predictors[_k2](hist)]

        r = backtest_nbets(predict_ctrl, all_draws, lottery_type, 2, 1500, SEED, 100)
        r.pop('results', None)
        status = '★' if r['edge'] > 0.01 else ('+' if r['edge'] > 0 else '-')
        print(f"    {combo_name:<25} {r['rate']*100:>7.3f}% {r['edge']*100:>+7.3f}% {r['z']:>5.2f} {status}")
        results.append({'combo': combo_name, **r})

    # 排序
    results.sort(key=lambda x: -x['edge'])
    best = results[0]
    print(f"\n    → 最佳2注: {best['combo']} (edge={best['edge']*100:+.3f}%, z={best['z']:.2f})")

    return results


# ═══════════════════════════════════════════════════════════════════
#  S4: 3注組合搜尋 + 驗證
# ═══════════════════════════════════════════════════════════════════

def s4_3bet_search(all_draws, lottery_type, top_2bet_results):
    """S4: 3注組合搜尋 (基於 2注最佳結果 + 第3信號)"""
    cfg = LOTTERY_CONFIGS[lottery_type]
    print(f"\n{'='*70}")
    print(f"  S4: 3注組合搜尋 — {cfg['label']}")
    print(f"{'='*70}")

    predictors = _build_feature_predictors(lottery_type)

    if lottery_type == 'DAILY_539':
        bl = baseline_multi(cfg.get('p_single_m2', cfg['p_single_m3']), 3)
    else:
        bl = baseline_multi(cfg['p_single_m3'], 3)

    # 取 2注 Top3 的組合作為基礎
    top_2bets = top_2bet_results[:3]

    results = []
    print(f"\n    3注基準: {bl*100:.3f}%")

    for base in top_2bets:
        base_keys = base['combo'].split('+')
        print(f"\n    --- 基於 {base['combo']} (2注 edge={base['edge']*100:+.3f}%) ---")
        print(f"    {'3rd Signal':<20} {'Rate':>8} {'Edge':>8} {'z':>6}")
        print(f"    {'─'*50}")

        for key in predictors:
            if key in base_keys:
                continue
            combo_name = f"{base['combo']}+{key}"

            def predict_3bet(hist, _bk=base_keys, _k=key):
                bets = [predictors[bk](hist) for bk in _bk]
                bets.append(predictors[_k](hist))
                return bets

            r = backtest_nbets(predict_3bet, all_draws, lottery_type, 3, 1500, SEED, 100)
            r.pop('results', None)
            status = '★' if r['edge'] > 0.01 else ('+' if r['edge'] > 0 else '-')
            print(f"    {key:<20} {r['rate']*100:>7.3f}% {r['edge']*100:>+7.3f}% {r['z']:>5.2f} {status}")
            results.append({'combo': combo_name, **r})

    results.sort(key=lambda x: -x['edge'])
    best = results[0]
    print(f"\n    → 最佳3注: {best['combo']} (edge={best['edge']*100:+.3f}%, z={best['z']:.2f})")

    # 三窗口驗證 Top3
    print(f"\n  [三窗口驗證 Top-3 組合]")
    validated = []
    for rank, combo_r in enumerate(results[:3], 1):
        combo_keys = combo_r['combo'].split('+')
        print(f"\n    #{rank}: {combo_r['combo']}")

        def predict_combo(hist, _keys=combo_keys):
            return [predictors[k](hist) for k in _keys]

        tw = three_window(predict_combo, all_draws, lottery_type, 3)
        tw_edges = {}
        for period in [150, 500, 1500]:
            if period not in tw:
                continue
            r = tw[period]
            marker = '★' if r['edge'] > 0 and r['p'] < 0.05 else ('+' if r['edge'] > 0 else '-')
            print(f"      {period}p: edge={r['edge']*100:+.3f}% z={r['z']:.2f} {marker}")
            tw_edges[period] = r['edge']

        all_pos = all(tw_edges.get(p, -1) > 0 for p in [150, 500, 1500] if p in tw)
        stability = 'STABLE' if all_pos else 'MIXED'
        print(f"      → {stability}")

        validated.append({
            'combo': combo_r['combo'],
            'three_window': tw,
            'stability': stability,
            '1500p_edge': tw_edges.get(1500, 0),
        })

    # Permutation test for the best STABLE combo
    stable_combos = [v for v in validated if v['stability'] == 'STABLE']
    if stable_combos:
        best_stable = max(stable_combos, key=lambda x: x['1500p_edge'])
        combo_keys = best_stable['combo'].split('+')
        print(f"\n  [Permutation Test: {best_stable['combo']}]")

        def predict_perm(hist, _keys=combo_keys):
            return [predictors[k](hist) for k in _keys]

        perm = permutation_test(predict_perm, all_draws, lottery_type, 3,
                                test_periods=1500, n_perms=200, seed=SEED)
        print(f"    Signal Edge: {perm['signal_edge']*100:+.3f}%")
        print(f"    z={perm['z_score']:.2f}  p={perm['p_empirical']:.4f}")
        passed = perm['signal_edge'] > 0 and perm['p_empirical'] < 0.05
        print(f"    → {'✅ PASS' if passed else '❌ FAIL'}")
        best_stable['permutation'] = perm
        best_stable['passed'] = passed
    else:
        print(f"\n  ⚠️ 無 STABLE 組合，跳過 permutation test")

    return results, validated


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    print("=" * 70)
    print("  AdaptiveACB 跨彩種全階段回測 (S1~S4)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 載入所有數據
    all_data = {}
    for lt in ['POWER_LOTTO', 'BIG_LOTTO', 'DAILY_539']:
        draws = load_data(lt)
        all_data[lt] = draws
        cfg = LOTTERY_CONFIGS[lt]
        print(f"  {cfg['label']}: {len(draws)} 期 ({draws[0]['date']} → {draws[-1]['date']})")

    report = {
        'timestamp': datetime.now().isoformat(),
        'stages': {},
    }

    # ════════════════════════════════════════════════════════════
    #  S1: ACB 1注回測 (威力彩 + 大樂透)
    # ════════════════════════════════════════════════════════════
    print(f"\n\n{'#'*70}")
    print(f"#  STAGE 1: ACB 1注回測")
    print(f"{'#'*70}")

    s1_results = {}
    for lt in ['POWER_LOTTO', 'BIG_LOTTO']:
        r = s1_acb_single_bet(all_data[lt], lt)
        s1_results[lt] = r
    report['stages']['S1'] = s1_results

    # ════════════════════════════════════════════════════════════
    #  S2: 特徵重要性矩陣
    # ════════════════════════════════════════════════════════════
    print(f"\n\n{'#'*70}")
    print(f"#  STAGE 2: 特徵重要性矩陣")
    print(f"{'#'*70}")

    s2_matrix = s2_feature_importance(all_data)
    report['stages']['S2'] = {
        lt: {fname: {'edge': fr['edge'], 'z': fr['z']}
             for fname, fr in feat.items()}
        for lt, feat in s2_matrix.items()
    }

    # ════════════════════════════════════════════════════════════
    #  S3: 2注組合搜尋
    # ════════════════════════════════════════════════════════════
    print(f"\n\n{'#'*70}")
    print(f"#  STAGE 3: 2注組合搜尋")
    print(f"{'#'*70}")

    s3_results = {}
    for lt in ['POWER_LOTTO', 'BIG_LOTTO']:
        r = s3_2bet_search(all_data[lt], lt)
        s3_results[lt] = [{k: v for k, v in x.items()}
                          for x in r[:10]]  # Top-10
    report['stages']['S3'] = s3_results

    # ════════════════════════════════════════════════════════════
    #  S4: 3注組合搜尋 + 驗證
    # ════════════════════════════════════════════════════════════
    print(f"\n\n{'#'*70}")
    print(f"#  STAGE 4: 3注組合搜尋 + 三窗口驗證")
    print(f"{'#'*70}")

    s4_results = {}
    for lt in ['POWER_LOTTO', 'BIG_LOTTO']:
        top_2bet = s3_results[lt]
        combos, validated = s4_3bet_search(all_data[lt], lt, top_2bet)
        s4_results[lt] = {
            'top_combos': [{k: v for k, v in x.items()} for x in combos[:10]],
            'validated': validated,
        }
    report['stages']['S4'] = s4_results

    # ════════════════════════════════════════════════════════════
    #  總結
    # ════════════════════════════════════════════════════════════
    elapsed = time.time() - t0
    print(f"\n\n{'='*70}")
    print(f"  全階段回測完成")
    print(f"  耗時: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"{'='*70}")

    # 綜合報告
    for lt in ['POWER_LOTTO', 'BIG_LOTTO']:
        cfg = LOTTERY_CONFIGS[lt]
        print(f"\n  ▸ {cfg['label']}:")

        # S1 結果
        s1 = s1_results[lt]
        print(f"    ACB 1注: window={s1['best_window']}, edge={s1['best_edge']*100:+.3f}%, "
              f"stability={s1['stability']}, perm={'PASS' if s1['passed'] else 'FAIL'}")

        # S3 最佳2注
        if lt in s3_results and s3_results[lt]:
            b2 = s3_results[lt][0]
            print(f"    最佳2注: {b2['combo']}, edge={b2['edge']*100:+.3f}%")

        # S4 最佳3注
        if lt in s4_results and s4_results[lt]['validated']:
            for v in s4_results[lt]['validated']:
                if v['stability'] == 'STABLE':
                    print(f"    最佳3注(STABLE): {v['combo']}, 1500p_edge={v['1500p_edge']*100:+.3f}%")
                    if 'permutation' in v:
                        print(f"      perm: signal_edge={v['permutation']['signal_edge']*100:+.3f}%, "
                              f"p={v['permutation']['p_empirical']:.4f}")
                    break

    # 保存結果
    out_path = os.path.join(_base, '..', 'backtest_adaptive_acb_full_results.json')
    # Clean non-serializable
    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean(v) for v in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(clean(report), f, ensure_ascii=False, indent=2)
    print(f"\n  結果已保存: {out_path}")


if __name__ == '__main__':
    main()
