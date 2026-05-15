#!/usr/bin/env python3
"""
今彩539 全面回測 v2 — 優化版 (預測快取 + 高效 permutation)

回測策略:
  S1: 單注 (ACB, Markov, RRF)
  S2: 2注 (MidFreq+ACB, ACB+Markov, ACB+Fourier, RRF, ACB-heavy, ACB+MK-heavy)
  S3: 3注 (F4Cold, RRF, ACB+Markov+Fourier, P3a)
  S4: Permutation test (快取版)
  S5: McNemar 配對比較
  S6: 總排名

基準 (539 M2+):
  1注=11.40%, 2注=21.54%, 3注=30.50%
"""
import sys, os, json, time, random
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

BASELINES_M2 = {1: 11.40, 2: 21.54, 3: 30.50, 4: 38.43, 5: 45.39}
MAX_NUM = 39
PICK = 5

# ===== 預測方法 =====

def fourier_scores(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM+1):
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

def acb_scores(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, MAX_NUM+1): counter[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM: counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM: last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM+1)}
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM+1):
        freq_deficit = expected - counter[n]
        gap_score = gaps[n] / (len(recent) / 2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * bb * m3
    return scores

def markov_scores(history, window=30):
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn > MAX_NUM: continue
            if pn not in transitions: transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                if nn <= MAX_NUM: transitions[pn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        if pn > MAX_NUM: continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for nn, cnt in trans.items():
                scores[nn] += cnt / total
    for n in range(1, MAX_NUM+1):
        if n not in scores: scores[n] = 0.0
    return dict(scores)

def midfreq_scores(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for n in range(1, MAX_NUM+1): freq[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM: freq[n] += 1
    expected = len(recent) * PICK / MAX_NUM
    max_dist = max(abs(freq[n] - expected) for n in range(1, MAX_NUM+1))
    scores = {}
    for n in range(1, MAX_NUM+1):
        scores[n] = max_dist - abs(freq[n] - expected)
    return scores


# ===== 排名器 =====

def get_rankings(history):
    f_sc = fourier_scores(history)
    a_sc = acb_scores(history)
    m_sc = markov_scores(history)
    mf_sc = midfreq_scores(history)
    return {
        'fourier': sorted(f_sc, key=lambda x: -f_sc[x]),
        'acb':     sorted(a_sc, key=lambda x: -a_sc[x]),
        'markov':  sorted(m_sc, key=lambda x: -m_sc[x]),
        'midfreq': sorted(mf_sc, key=lambda x: -mf_sc[x]),
    }


def rrf_ranked(rankings, methods=None, k=60, weights=None):
    """RRF ranked list"""
    if methods is None: methods = list(rankings.keys())
    if weights is None: weights = {m: 1.0 for m in methods}
    sc = Counter()
    for m in methods:
        for rank, n in enumerate(rankings[m]):
            sc[n] += weights.get(m, 1.0) / (k + rank + 1)
    return sorted(sc, key=lambda x: -sc[x])


# ===== 策略定義 =====

def pick_top(ranked, exclude, count=PICK):
    out = []
    for n in ranked:
        if n in exclude: continue
        out.append(n)
        if len(out) >= count: break
    return sorted(out)


STRATEGIES = {}


def register(name, n_bets):
    def dec(f):
        STRATEGIES[name] = (f, n_bets)
        return f
    return dec


@register('ACB_1bet', 1)
def s_acb_1(rankings):
    return [pick_top(rankings['acb'], set())]

@register('Markov_1bet', 1)
def s_markov_1(rankings):
    return [pick_top(rankings['markov'], set())]

@register('RRF_1bet', 1)
def s_rrf_1(rankings):
    return [pick_top(rrf_ranked(rankings), set())]

@register('MidFreq_ACB_2bet', 2)
def s_mf_acb_2(rankings):
    b1 = pick_top(rankings['midfreq'], set())
    b2 = pick_top(rankings['acb'], set(b1))
    return [b1, b2]

@register('ACB_Markov_2bet', 2)
def s_acb_mk_2(rankings):
    b1 = pick_top(rankings['acb'], set())
    b2 = pick_top(rankings['markov'], set(b1))
    return [b1, b2]

@register('ACB_Fourier_2bet', 2)
def s_acb_f_2(rankings):
    b1 = pick_top(rankings['acb'], set())
    b2 = pick_top(rankings['fourier'], set(b1))
    return [b1, b2]

@register('RRF_2bet', 2)
def s_rrf_2(rankings):
    r = rrf_ranked(rankings)
    b1 = pick_top(r, set())
    b2 = pick_top(r, set(b1))
    return [b1, b2]

@register('RRF_ACBheavy_2bet', 2)
def s_rrf_ah_2(rankings):
    r = rrf_ranked(rankings, weights={'fourier':1, 'acb':2, 'markov':1, 'midfreq':1})
    b1 = pick_top(r, set())
    b2 = pick_top(r, set(b1))
    return [b1, b2]

@register('RRF_ACB_MK_heavy_2bet', 2)
def s_rrf_amh_2(rankings):
    r = rrf_ranked(rankings, weights={'fourier':0.5, 'acb':2.0, 'markov':1.5, 'midfreq':0.5})
    b1 = pick_top(r, set())
    b2 = pick_top(r, set(b1))
    return [b1, b2]

@register('F4Cold_3bet', 3)
def s_f4cold_3(rankings):
    ranked = rankings['fourier']
    b1 = sorted(ranked[0:5])
    b2 = sorted(ranked[5:10])
    b3 = sorted(ranked[10:15])
    return [b1, b2, b3]

@register('RRF_3bet', 3)
def s_rrf_3(rankings):
    r = rrf_ranked(rankings)
    b1 = pick_top(r, set())
    b2 = pick_top(r, set(b1))
    b3 = pick_top(r, set(b1)|set(b2))
    return [b1, b2, b3]

@register('ACB_Markov_Fourier_3bet', 3)
def s_amf_3(rankings):
    b1 = pick_top(rankings['acb'], set())
    b2 = pick_top(rankings['markov'], set(b1))
    b3 = pick_top(rankings['fourier'], set(b1)|set(b2))
    return [b1, b2, b3]

@register('P3a_MK_MF_ACB_3bet', 3)
def s_p3a_3(rankings):
    b1 = pick_top(rankings['markov'], set())
    b2 = pick_top(rankings['midfreq'], set(b1))
    b3 = pick_top(rankings['acb'], set(b1)|set(b2))
    return [b1, b2, b3]


# ===== 回測引擎 (快取版) =====

def run_backtest(all_draws, test_periods, strategy_names=None, match_threshold=2):
    """
    Walk-forward backtest with prediction caching.
    Returns: {strategy_name: {periods: {hits, total, rate, edge, z, hit_details}}}
    """
    if strategy_names is None:
        strategy_names = list(STRATEGIES.keys())

    # 預分配結果
    results = {name: {} for name in strategy_names}

    for periods in [150, 500, 1500]:
        tp = min(periods, test_periods)
        # 初始化
        for name in strategy_names:
            results[name][periods] = {'hits': 0, 'total': 0, 'details': []}

        for i in range(tp):
            target_idx = len(all_draws) - tp + i
            if target_idx < 100:
                for name in strategy_names:
                    results[name][periods]['details'].append(0)
                continue

            hist = all_draws[:target_idx]
            actual = set(all_draws[target_idx]['numbers'][:PICK])

            # 計算一次排名，所有策略共用
            rankings = get_rankings(hist)

            for name in strategy_names:
                fn, n_bets = STRATEGIES[name]
                try:
                    bets = fn(rankings)
                    hit = any(len(set(b) & actual) >= match_threshold for b in bets)
                except Exception:
                    hit = False
                if hit:
                    results[name][periods]['hits'] += 1
                    results[name][periods]['details'].append(1)
                else:
                    results[name][periods]['details'].append(0)
                results[name][periods]['total'] += 1

        # 計算統計
        for name in strategy_names:
            r = results[name][periods]
            _, n_bets = STRATEGIES[name]
            r['n_bets'] = n_bets
            baseline = BASELINES_M2.get(n_bets, BASELINES_M2[1])
            r['baseline'] = baseline
            r['rate'] = r['hits'] / r['total'] * 100 if r['total'] > 0 else 0
            r['edge'] = r['rate'] - baseline
            p0 = baseline / 100
            se = np.sqrt(p0 * (1 - p0) / r['total']) if r['total'] > 0 and p0 > 0 else 1
            r['z'] = (r['hits'] / r['total'] - p0) / se if se > 0 and r['total'] > 0 else 0

    return results


def permutation_test_cached(all_draws, test_periods, strategy_names=None,
                            match_threshold=2, n_perm=200):
    """
    Permutation test — 預測只計算一次，打亂開獎號碼重新比對。
    比原版快 n_perm 倍。
    """
    if strategy_names is None:
        strategy_names = list(STRATEGIES.keys())

    tp = min(test_periods, 1500)

    # Phase 1: 計算所有期的預測 (只一次)
    print("    快取預測中...")
    cached_bets = {name: [] for name in strategy_names}
    target_indices = []
    actuals = []

    for i in range(tp):
        target_idx = len(all_draws) - tp + i
        if target_idx < 100:
            for name in strategy_names:
                cached_bets[name].append(None)
            continue

        target_indices.append(i)
        actual = set(all_draws[target_idx]['numbers'][:PICK])
        actuals.append(actual)

        hist = all_draws[:target_idx]
        rankings = get_rankings(hist)

        for name in strategy_names:
            fn, n_bets = STRATEGIES[name]
            try:
                bets = fn(rankings)
            except:
                bets = []
            cached_bets[name].append(bets)

    # Phase 2: 真實命中率
    real_hits = {}
    for name in strategy_names:
        hits = 0
        total = 0
        for idx_i, i in enumerate(target_indices):
            bets = cached_bets[name][i]
            if bets is None: continue
            actual = actuals[idx_i]
            if any(len(set(b) & actual) >= match_threshold for b in bets):
                hits += 1
            total += 1
        real_hits[name] = (hits, total)

    # Phase 3: Permutation (只打亂 actuals)
    print(f"    Permutation {n_perm} 次...")
    perm_rates = {name: [] for name in strategy_names}

    for p in range(n_perm):
        shuffled = list(actuals)
        rng = random.Random(p * 7919 + 42)
        rng.shuffle(shuffled)

        for name in strategy_names:
            hits = 0
            total = 0
            for idx_i, i in enumerate(target_indices):
                bets = cached_bets[name][i]
                if bets is None: continue
                actual = shuffled[idx_i]
                if any(len(set(b) & actual) >= match_threshold for b in bets):
                    hits += 1
                total += 1
            rate = hits / total * 100 if total > 0 else 0
            perm_rates[name].append(rate)

    # Phase 4: 統計
    results = {}
    for name in strategy_names:
        hits, total = real_hits[name]
        real_rate = hits / total * 100 if total > 0 else 0
        pr = perm_rates[name]
        perm_mean = np.mean(pr)
        perm_std = np.std(pr) if len(pr) > 1 else 1
        count_exceed = sum(1 for r in pr if r >= real_rate)
        p_value = (count_exceed + 1) / (n_perm + 1)
        signal_edge = real_rate - perm_mean
        perm_z = signal_edge / perm_std if perm_std > 0 else 0
        results[name] = {
            'real_rate': real_rate,
            'perm_mean': perm_mean,
            'perm_std': perm_std,
            'signal_edge': signal_edge,
            'perm_z': perm_z,
            'p_value': p_value,
            'n_perm': n_perm,
        }
    return results


def mcnemar_test(details_a, details_b):
    assert len(details_a) == len(details_b)
    a_only = sum(1 for a, b in zip(details_a, details_b) if a and not b)
    b_only = sum(1 for a, b in zip(details_a, details_b) if not a and b)
    both_hit = sum(1 for a, b in zip(details_a, details_b) if a and b)
    both_miss = sum(1 for a, b in zip(details_a, details_b) if not a and not b)
    n_disc = a_only + b_only
    if n_disc == 0:
        chi2, p = 0, 1.0
    else:
        chi2 = (a_only - b_only) ** 2 / n_disc
        # Approximate p-value using normal CDF
        p = 2 * (1 - 0.5 * (1 + np.math.erf(np.sqrt(chi2 / 2))))
    return {
        'both_hit': both_hit, 'a_only': a_only, 'b_only': b_only,
        'both_miss': both_miss, 'chi2': chi2, 'p_value': p,
        'winner': 'A' if a_only > b_only else ('B' if b_only > a_only else 'TIE'),
    }


# ===== 主程式 =====

def main():
    start = time.time()

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    print(f"✅ 載入 {len(all_draws)} 期 539 資料")
    print(f"   最新期: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")

    strategy_names = list(STRATEGIES.keys())

    # ===== S1-S3: 三窗口回測 (共用排名計算) =====
    print("\n" + "=" * 80)
    print("  S1-S3: 全策略三窗口回測 (150/500/1500p, M2+)")
    print("=" * 80)

    bt_start = time.time()
    results = run_backtest(all_draws, 1500, strategy_names)
    bt_elapsed = time.time() - bt_start
    print(f"  ⏱️ 回測耗時: {bt_elapsed:.1f} 秒")

    # 分類顯示
    cats = [
        ("單注 (1-bet)", [n for n in strategy_names if STRATEGIES[n][1] == 1]),
        ("2注 (2-bet)",  [n for n in strategy_names if STRATEGIES[n][1] == 2]),
        ("3注 (3-bet)",  [n for n in strategy_names if STRATEGIES[n][1] == 3]),
    ]

    for cat_name, names in cats:
        print(f"\n  === {cat_name} ===")
        for name in names:
            print(f"\n  --- {name} ---")
            for periods in [150, 500, 1500]:
                r = results[name][periods]
                marker = '★' if r['edge'] > 0 else ''
                print(f"  {periods:4d}p: M2+={r['hits']}/{r['total']} ({r['rate']:.2f}%) "
                      f"bl={r['baseline']:.2f}% Edge={r['edge']:+.2f}% z={r['z']:.2f} {marker}")
            e = [results[name][p]['edge'] for p in [150, 500, 1500]]
            if all(x > 0 for x in e):
                stab = "✅ STABLE"
            elif e[2] < 0:
                stab = "❌ SHORT_MOM" if e[0] > 0 or e[1] > 0 else "❌ INEFFECTIVE"
            elif e[0] < 0 and e[2] > 0:
                stab = "⚠️ LATE_BLOOMER"
            else:
                stab = "⚠️ MIXED"
            print(f"  穩定性: {stab}")

    # ===== S4: Permutation Test =====
    print("\n" + "=" * 80)
    print("  S4: Permutation Test (200 iterations, 1500期, 快取版)")
    print("=" * 80)

    # 只測 1500p edge > 0 的策略
    perm_candidates = [n for n in strategy_names if results[n][1500]['edge'] > 0]
    print(f"  候選策略: {len(perm_candidates)} 個 (1500p Edge > 0)")

    perm_start = time.time()
    perm_results = permutation_test_cached(all_draws, 1500, perm_candidates)
    perm_elapsed = time.time() - perm_start
    print(f"  ⏱️ Permutation 耗時: {perm_elapsed:.1f} 秒")

    for name in perm_candidates:
        pr = perm_results[name]
        sig = '★★' if pr['p_value'] < 0.01 else ('★' if pr['p_value'] < 0.05 else '')
        print(f"  {name:<35}: Real={pr['real_rate']:.2f}% Perm={pr['perm_mean']:.2f}% "
              f"SigEdge={pr['signal_edge']:+.2f}% z={pr['perm_z']:.2f} p={pr['p_value']:.3f} {sig}")

    # ===== S5: McNemar 配對比較 =====
    print("\n" + "=" * 80)
    print("  S5: McNemar 配對比較 (1500期)")
    print("=" * 80)

    for n_bets_val, cat_label in [(1, "1注"), (2, "2注"), (3, "3注")]:
        names_cat = [n for n in strategy_names if STRATEGIES[n][1] == n_bets_val]
        if len(names_cat) < 2:
            continue
        best = max(names_cat, key=lambda n: results[n][1500]['edge'])
        print(f"\n  === {cat_label} McNemar (基準: {best}, Edge={results[best][1500]['edge']:+.2f}%) ===")
        for name in names_cat:
            if name == best: continue
            mn = mcnemar_test(results[best][1500]['details'], results[name][1500]['details'])
            sig = '★' if mn['p_value'] < 0.05 else ''
            print(f"  {best} vs {name}: A_only={mn['a_only']} B_only={mn['b_only']} "
                  f"χ²={mn['chi2']:.2f} p={mn['p_value']:.4f} Winner={mn['winner']} {sig}")

    # ===== S6: 總排名 =====
    print("\n" + "=" * 80)
    print("  S6: 全策略 1500期總排名")
    print("=" * 80)

    rankings_list = []
    for name in strategy_names:
        _, nb = STRATEGIES[name]
        r1500 = results[name][1500]
        e150 = results[name][150]['edge']
        e500 = results[name][500]['edge']
        pr = perm_results.get(name, {})
        rankings_list.append({
            'name': name, 'n_bets': nb,
            'rate': r1500['rate'], 'edge': r1500['edge'], 'z': r1500['z'],
            'e150': e150, 'e500': e500,
            'perm_p': pr.get('p_value'), 'sig_edge': pr.get('signal_edge'),
        })

    rankings_list.sort(key=lambda x: -x['edge'])

    hdr = f"  {'策略':<35} | {'注':>2} | {'Edge1500':>9} | {'z':>5} | {'E150':>6} | {'E500':>6} | {'Perm_p':>7} | {'SigEdge':>8} | {'穩定':>12}"
    print(hdr)
    print("  " + "-" * len(hdr))

    for m in rankings_list:
        e_all = [m['e150'], m['e500'], m['edge']]
        stab = "STABLE" if all(x > 0 for x in e_all) else (
            "LATE_BLOOM" if e_all[0] < 0 and e_all[2] > 0 else (
            "SHORT_MOM" if e_all[2] < 0 and (e_all[0] > 0 or e_all[1] > 0) else (
            "INEFFECTIVE" if e_all[2] < 0 else "MIXED")))
        pp = f"{m['perm_p']:.3f}" if m['perm_p'] is not None else "N/A"
        se = f"{m['sig_edge']:+.2f}%" if m['sig_edge'] is not None else "N/A"
        sig = ''
        if m['perm_p'] is not None:
            sig = ' ★★' if m['perm_p'] < 0.01 else (' ★' if m['perm_p'] < 0.05 else '')
        print(f"  {m['name']:<35} | {m['n_bets']:>2} | {m['edge']:>+8.2f}% | {m['z']:>5.2f} | {m['e150']:>+5.2f}% | {m['e500']:>+5.2f}% | {pp:>7}{sig} | {se:>8} | {stab:>12}")

    # ===== 結論 =====
    print("\n" + "=" * 80)
    print("  結論: 推薦策略")
    print("=" * 80)

    for nb in [1, 2, 3]:
        names_nb = [m for m in rankings_list if m['n_bets'] == nb]
        if not names_nb: continue
        best_m = names_nb[0]
        stab = all(x > 0 for x in [best_m['e150'], best_m['e500'], best_m['edge']])
        perm_ok = best_m['perm_p'] is not None and best_m['perm_p'] < 0.05
        qualified = stab and perm_ok
        status = "✅ QUALIFIED" if qualified else ("⚠️ PARTIAL" if stab or perm_ok else "❌ UNQUALIFIED")
        print(f"\n  {nb}注最佳: {best_m['name']}")
        print(f"    Edge(1500p): {best_m['edge']:+.2f}%, z={best_m['z']:.2f}")
        print(f"    三窗口: {best_m['e150']:+.2f}% / {best_m['e500']:+.2f}% / {best_m['edge']:+.2f}%")
        pp = f"{best_m['perm_p']:.3f}" if best_m['perm_p'] is not None else "N/A"
        print(f"    Permutation: p={pp}")
        print(f"    評定: {status}")

    # ===== 儲存 =====
    elapsed = time.time() - start
    save = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(all_draws),
        'elapsed': elapsed,
        'strategies': {},
    }
    for m in rankings_list:
        save['strategies'][m['name']] = {
            'n_bets': m['n_bets'],
            'edge_150p': round(m['e150'], 2),
            'edge_500p': round(m['e500'], 2),
            'edge_1500p': round(m['edge'], 2),
            'z_1500p': round(m['z'], 2),
            'rate_1500p': round(m['rate'], 2),
            'perm_p': round(m['perm_p'], 3) if m['perm_p'] is not None else None,
            'signal_edge': round(m['sig_edge'], 2) if m['sig_edge'] is not None else None,
        }

    out_path = os.path.join(project_root, 'backtest_539_rrf_complete.json')
    with open(out_path, 'w') as f:
        json.dump(save, f, indent=2, ensure_ascii=False)

    print(f"\n  ✅ 結果已存: {out_path}")
    print(f"  ⏱️ 總耗時: {elapsed:.1f} 秒")
    print("=" * 80)


if __name__ == '__main__':
    main()
