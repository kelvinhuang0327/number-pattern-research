"""
大樂透 6注策略回測
==================
研究第6注是否能超過幾何基準，為現有5注策略提供有效補充。

三種 Bet6 方法（全部從注1-5剩餘號碼池中選取）：
  A. Zone Balance: Z1/Z2/Z3 各取2個，按100期頻率排序
  B. Residual Hot: 剩餘池按頻率降序 Top-6
  C. Residual Cold: 剩餘池按頻率升序 Top-6

評估標準:
  - 6注 Edge > 10.65% (6注隨機基準)
  - McNemar net > 0 (vs 5注)
  - z-score p < 0.05
"""
import sys
import os
import json
import math
import random
import numpy as np
from collections import Counter
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import biglotto_p1_deviation_5bet, enforce_tail_diversity

MAX_NUM = 49
P_SINGLE = 0.0186
BASELINES = {
    5: 1 - (1 - P_SINGLE) ** 5,
    6: 1 - (1 - P_SINGLE) ** 6,
}
WINDOWS = [150, 500, 1500]
MIN_BUF = 200
SEED = 42
N_PERM = 200

ZONES = {
    'Z1': list(range(1, 17)),
    'Z2': list(range(17, 33)),
    'Z3': list(range(33, 50)),
}


def _freq(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    return Counter(n for d in recent for n in d['numbers'])


def bet6_zone_balance(remaining, history):
    freq = _freq(history)
    rem_set = set(remaining)
    pools = {z: sorted([n for n in nums if n in rem_set], key=lambda x: -freq.get(x, 0))
             for z, nums in ZONES.items()}
    selected = []
    needs = {'Z1': 2, 'Z2': 2, 'Z3': 2}
    for z, pool in pools.items():
        take = min(needs[z], len(pool))
        selected.extend(pool[:take])
        needs[z] -= take
    deficit = sum(needs.values())
    if deficit > 0:
        extra = sorted([n for n in remaining if n not in selected], key=lambda x: -freq.get(x, 0))
        selected.extend(extra[:deficit])
    return sorted(selected[:6])


def bet6_residual_hot(remaining, history):
    freq = _freq(history)
    return sorted(sorted(remaining, key=lambda x: -freq.get(x, 0))[:6])


def bet6_residual_cold(remaining, history):
    freq = _freq(history)
    return sorted(sorted(remaining, key=lambda x: freq.get(x, 0))[:6])


BET6_METHODS = {
    'zone_balance': bet6_zone_balance,
    'residual_hot': bet6_residual_hot,
    'residual_cold': bet6_residual_cold,
}


def m3plus(bet, actual_set):
    return len(set(bet) & actual_set) >= 3


def _norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2))) / 2


def edge_stats(hits, n, baseline):
    rate = hits / n if n else 0
    edge = rate - baseline
    z = edge / math.sqrt(baseline * (1 - baseline) / n) if n > 0 else 0
    p = (1 - _norm_cdf(abs(z))) * 2
    return {'n': n, 'hits': hits, 'rate': round(rate*100, 3),
            'edge': round(edge*100, 3), 'z': round(z, 3), 'p': round(p, 4)}


def mcnemar_test(a_hits, b_hits):
    a_only = sum(1 for a, b in zip(a_hits, b_hits) if a and not b)
    b_only = sum(1 for a, b in zip(a_hits, b_hits) if b and not a)
    n_disc = a_only + b_only
    if n_disc == 0:
        return {'a_only': 0, 'b_only': 0, 'chi2': 0, 'p': 1.0, 'net': 0}
    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_disc
    import scipy.stats as st
    p = 1 - st.chi2.cdf(chi2, df=1)
    return {'a_only': a_only, 'b_only': b_only,
            'chi2': round(chi2, 3), 'p': round(p, 4), 'net': a_only - b_only}


def permutation_test(hits, n_perm, baseline):
    actual_edge = sum(hits) / len(hits) - baseline
    count = 0
    arr = list(hits)
    for _ in range(n_perm):
        random.shuffle(arr)
        if (sum(arr) / len(arr) - baseline) >= actual_edge:
            count += 1
    return round(count / n_perm, 4)


def run_backtest(history):
    total = len(history)
    print(f"  總期數: {total}，OOS: {total - MIN_BUF} 期", flush=True)

    hits5 = []
    hits6 = {m: [] for m in BET6_METHODS}

    for i in range(MIN_BUF, total):
        train = history[:i]
        actual = set(history[i]['numbers'])

        try:
            bets = biglotto_p1_deviation_5bet(train)
            bets = enforce_tail_diversity(bets, max_same_tail=2,
                                          max_num=49, history=train)
            bets_nums = [b['numbers'] for b in bets]
        except Exception:
            hits5.append(False)
            for m in BET6_METHODS:
                hits6[m].append(False)
            continue

        hit5 = any(m3plus(b, actual) for b in bets_nums)
        hits5.append(hit5)

        used = set(n for b in bets_nums for n in b)
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in used]

        for name, fn in BET6_METHODS.items():
            try:
                b6 = fn(remaining, train)
                hit6 = hit5 or m3plus(b6, actual)
            except Exception:
                hit6 = hit5
            hits6[name].append(hit6)

        if (i - MIN_BUF) % 500 == 0:
            print(f"  ... {i - MIN_BUF}/{total - MIN_BUF}", flush=True)

    return hits5, hits6


def print_report(hits5, hits6):
    n = len(hits5)
    bl5, bl6 = BASELINES[5], BASELINES[6]

    print(f"\n{'='*70}")
    print(f"  大樂透 6注策略研究報告  OOS={n}期")
    print(f"  5注基準={bl5*100:.2f}%  6注基準={bl6*100:.2f}%  差={( bl6-bl5)*100:.2f}%")
    print(f"{'='*70}")

    print(f"\n  ── 5注 基線（對照） ──")
    for w in WINDOWS:
        h = hits5[-w:] if len(hits5) >= w else hits5
        s = edge_stats(sum(h), len(h), bl5)
        print(f"    {w:>5}p  edge={s['edge']:>+6.2f}%  z={s['z']:>+5.2f}  p={s['p']:.4f}")

    all_results = {}
    for method, h6_all in hits6.items():
        print(f"\n  ── Bet6: {method} ──")
        w_results = {}
        for w in WINDOWS:
            h = h6_all[-w:] if len(h6_all) >= w else h6_all
            s = edge_stats(sum(h), len(h), bl6)
            flag = '▲' if s['edge'] > 0 else '▼'
            print(f"    {w:>5}p  edge={s['edge']:>+6.2f}%  z={s['z']:>+5.2f}  p={s['p']:.4f}  {flag}")
            w_results[w] = s

        nmc = min(1500, len(h6_all))
        mc = mcnemar_test(h6_all[-nmc:], hits5[-nmc:])
        print(f"    McNemar(1500p): 6注獨贏={mc['a_only']} 5注獨贏={mc['b_only']} net={mc['net']} p={mc['p']:.4f}")

        h_perm = h6_all[-1500:] if len(h6_all) >= 1500 else h6_all
        perm_p = permutation_test(h_perm, N_PERM, bl6)
        print(f"    Perm(N={N_PERM}): p={perm_p}")

        e1500 = w_results.get(1500, w_results.get(500, {})).get('edge', -999)
        verdict = 'PASS ✅' if (e1500 > 0 and mc['net'] > 0 and perm_p < 0.05) else 'FAIL ❌'
        print(f"    → {verdict}  (edge_1500={e1500:+.2f}% net={mc['net']} perm_p={perm_p})")

        all_results[method] = {
            'windows': {str(w): s for w, s in w_results.items()},
            'mcnemar': mc, 'perm_p': perm_p, 'verdict': verdict,
        }

    print(f"\n{'='*70}")
    return all_results


if __name__ == '__main__':
    random.seed(SEED)
    np.random.seed(SEED)

    db = DatabaseManager(db_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'lottery_api', 'data', 'lottery_v2.db'))

    print("\n[BIG_LOTTO] 載入歷史資料...", end=' ', flush=True)
    history = sorted(db.get_all_draws(lottery_type='BIG_LOTTO'),
                     key=lambda x: (x['date'], x['draw']))
    print(f"{len(history)} 期")
    print("[BIG_LOTTO] 執行回測...", flush=True)

    hits5, hits6 = run_backtest(history)
    results = print_report(hits5, hits6)

    out = {
        'lottery': 'BIG_LOTTO', 'n_oos': len(hits5),
        'baseline_5bet': round(BASELINES[5]*100, 3),
        'baseline_6bet': round(BASELINES[6]*100, 3),
        'results': results,
    }
    with open('backtest_biglotto_6bet_results.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n結果已存至 backtest_biglotto_6bet_results.json")
