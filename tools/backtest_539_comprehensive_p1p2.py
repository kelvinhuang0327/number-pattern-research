#!/usr/bin/env python3
"""
今彩539 綜合回測：P1 + P2 行動項目
====================================
2026-03-14 LLM Research Board 決議

P1-1: Parity-gap detector (全偶/全奇 gap≥100 → boost)
P1-2: Consensus top2-voting (取各 agent 最高分而非 mean-0.5σ)
P1-3: Zone-reversion 信號量化 (極端 zone 後回歸)
P1-4: MidFreq+ACB_b8 2-bet McNemar 驗證
P2-1: Markov+Weibull 正交 2-bet
P2-2: FFT window 300 vs 500 對比

標準驗證：三窗口(150/500/1500) + Permutation 200次 + McNemar vs baseline
"""
import sys, os, json, random, time
import numpy as np
from collections import Counter
from numpy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

MAX_NUM = 39
PICK = 5
BASELINES_M2 = {1: 11.40, 2: 21.54, 3: 30.50}
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# ============================================================
# Core backtest engine (reuse proven framework)
# ============================================================

def backtest_539(predict_func, all_draws, test_periods=1500, n_bets=2, min_hist=100):
    hits, total = 0, 0
    hit_details = []
    for i in range(test_periods):
        idx = len(all_draws) - test_periods + i
        if idx < min_hist:
            hit_details.append(0)
            continue
        hist = all_draws[:idx]
        actual = set(all_draws[idx]['numbers'][:PICK])
        try:
            bets = predict_func(hist)
            hit = any(len(set(b) & actual) >= 2 for b in bets)
            hit_details.append(1 if hit else 0)
            if hit: hits += 1
            total += 1
        except Exception:
            hit_details.append(0)
            total += 1
    rate = hits / total * 100 if total > 0 else 0
    baseline = BASELINES_M2[n_bets]
    edge = rate - baseline
    p0 = baseline / 100
    se = np.sqrt(p0 * (1 - p0) / total) if total > 0 else 1
    z = (rate / 100 - p0) / se if se > 0 else 0
    return {'hits': hits, 'total': total, 'rate': rate,
            'baseline': baseline, 'edge': edge, 'z': z,
            'hit_details': hit_details}


def three_window_test(predict_func, all_draws, n_bets):
    results = {}
    for w in [150, 500, 1500]:
        if len(all_draws) < w + 100:
            results[w] = None
            continue
        results[w] = backtest_539(predict_func, all_draws, w, n_bets)
    return results


def permutation_test_539(predict_func, all_draws, test_periods=1500, n_bets=2, n_perm=200):
    real = backtest_539(predict_func, all_draws, test_periods, n_bets)
    real_rate = real['rate']
    target_indices = [len(all_draws) - test_periods + i
                      for i in range(test_periods)
                      if len(all_draws) - test_periods + i >= 100]
    all_actuals = [set(all_draws[idx]['numbers'][:PICK]) for idx in target_indices]
    perm_rates = []
    for p in range(n_perm):
        shuffled = list(all_actuals)
        rng = random.Random(p * 7919 + 42)
        rng.shuffle(shuffled)
        hits, total = 0, 0
        for i, idx in enumerate(target_indices):
            hist = all_draws[:idx]
            try:
                bets = predict_func(hist)
                if any(len(set(b) & shuffled[i]) >= 2 for b in bets):
                    hits += 1
                total += 1
            except Exception:
                total += 1
        if total > 0:
            perm_rates.append(hits / total * 100)
    count_exceed = sum(1 for pr in perm_rates if pr >= real_rate)
    p_value = (count_exceed + 1) / (n_perm + 1)
    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1
    return {
        'real_rate': real_rate,
        'perm_mean': perm_mean,
        'signal_edge': real_rate - perm_mean,
        'perm_z': (real_rate - perm_mean) / perm_std if perm_std > 0 else 0,
        'p_value': p_value,
        'count_exceed': count_exceed,
        'n_perm': n_perm,
    }


def mcnemar_test(hits_a, hits_b):
    n01 = sum(1 for a, b in zip(hits_a, hits_b) if a == 0 and b == 1)
    n10 = sum(1 for a, b in zip(hits_a, hits_b) if a == 1 and b == 0)
    if n01 + n10 == 0:
        return {'n01': 0, 'n10': 0, 'p': 1.0, 'sig': False}
    from scipy.stats import binomtest
    try:
        p = binomtest(n10, n01 + n10, 0.5).pvalue
    except Exception:
        p = 1.0
    return {'n01': n01, 'n10': n10, 'p': p, 'sig': p < 0.05}


# ============================================================
# Scoring functions
# ============================================================

def acb_scores(history, window=100, boundary_threshold=8):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter(n for d in recent for n in d['numbers'] if 1 <= n <= MAX_NUM)
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                last_seen[n] = i
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        fd = expected - counter.get(n, 0)
        gap = (len(recent) - last_seen.get(n, -1)) / (len(recent) / 2)
        bb = 1.2 if (n <= boundary_threshold or n >= 35) else 1.0
        scores[n] = (fd * 0.4 + gap * 0.6) * bb
    return scores


def midfreq_scores(history, window=100):
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d['numbers'] if 1 <= n <= MAX_NUM)
    expected = len(recent) * PICK / MAX_NUM
    max_dist = max(abs(freq.get(n, 0) - expected) for n in range(1, MAX_NUM + 1))
    if max_dist == 0: max_dist = 1
    return {n: max_dist - abs(freq.get(n, 0) - expected) for n in range(1, MAX_NUM + 1)}


def markov_scores(history, window=30):
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                transitions[pn][nn] += 1
    scores = Counter()
    if recent:
        last_nums = recent[-1]['numbers']
        for pn in last_nums:
            if pn in transitions:
                total = sum(transitions[pn].values())
                for nn, cnt in transitions[pn].items():
                    scores[nn] += cnt / total
    return {n: scores.get(n, 0) for n in range(1, MAX_NUM + 1)}


def fourier_scores(history, window=500):
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
        if len(pos_yf) == 0:
            scores[n] = 0.0
            continue
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        last_appear = np.where(bh == 1)[0]
        last_idx = last_appear[-1] if len(last_appear) > 0 else -1
        expected_gap = 1.0 / freq_val
        actual_gap = w - 1 - last_idx
        scores[n] = 1.0 / (abs(actual_gap - expected_gap) + 1.0)
    return scores


def weibull_gap_scores(history, window=300):
    """Weibull gap hazard scoring"""
    h = history[-window:] if len(history) >= window else history
    scores = {}
    for n in range(1, MAX_NUM + 1):
        gaps = []
        current_gap = 0
        for d in h:
            if n in d['numbers']:
                if current_gap > 0:
                    gaps.append(current_gap)
                current_gap = 0
            else:
                current_gap += 1
        # Current ongoing gap
        if not gaps:
            scores[n] = current_gap / (len(h) / 2) if len(h) > 0 else 0
            continue
        mean_gap = np.mean(gaps)
        std_gap = np.std(gaps) if len(gaps) > 1 else mean_gap * 0.5
        cv = std_gap / mean_gap if mean_gap > 0 else 1
        # Weibull shape from CV
        k = max(cv ** (-1.086), 0.5) if cv > 0 else 1.5
        lam = mean_gap
        # Hazard rate at current gap
        t = current_gap
        if lam > 0 and t > 0:
            hazard = (k / lam) * ((t / lam) ** (k - 1))
        else:
            hazard = 0
        # Pressure boost
        pressure = current_gap / mean_gap if mean_gap > 0 else 0
        score = hazard * (1 + 0.25 * max(pressure - 0.8, 0))
        scores[n] = score
    return scores


# ============================================================
# Strategy functions
# ============================================================

def _top_n(scores, n=5, exclude=None):
    exclude = exclude or set()
    ranked = sorted([k for k in scores if k not in exclude], key=lambda x: -scores[x])
    return sorted(ranked[:n])


# --- Baselines ---
def baseline_acb_1bet(history):
    return [_top_n(acb_scores(history))]

def baseline_midfreq_acb_2bet(history):
    bet1 = _top_n(midfreq_scores(history))
    bet2 = _top_n(acb_scores(history), exclude=set(bet1))
    return [bet1, bet2]

def baseline_acb_markov_fourier_3bet(history):
    bet1 = _top_n(acb_scores(history))
    bet2 = _top_n(markov_scores(history), exclude=set(bet1))
    excl = set(bet1) | set(bet2)
    bet3 = _top_n(fourier_scores(history), exclude=excl)
    return [bet1, bet2, bet3]


# --- P1-1: Parity-gap detector ---
def _parity_gap(history):
    """Count gaps since last all-even and all-odd draws"""
    even_gap = 999
    odd_gap = 999
    for i in range(len(history) - 1, -1, -1):
        nums = history[i]['numbers'][:PICK]
        if all(n % 2 == 0 for n in nums):
            even_gap = len(history) - 1 - i
            break
    for i in range(len(history) - 1, -1, -1):
        nums = history[i]['numbers'][:PICK]
        if all(n % 2 == 1 for n in nums):
            odd_gap = len(history) - 1 - i
            break
    return even_gap, odd_gap


def parity_gap_acb_1bet(history):
    """ACB with parity-gap boost: if all-even gap >= 100, boost even numbers"""
    scores = acb_scores(history)
    even_gap, odd_gap = _parity_gap(history)
    if even_gap >= 100:
        for n in range(1, MAX_NUM + 1):
            if n % 2 == 0:
                scores[n] *= 1.15
    if odd_gap >= 100:
        for n in range(1, MAX_NUM + 1):
            if n % 2 == 1:
                scores[n] *= 1.15
    return [_top_n(scores)]


def parity_gap_midfreq_acb_2bet(history):
    """2-bet with parity-gap boost"""
    mf = midfreq_scores(history)
    ac = acb_scores(history)
    even_gap, odd_gap = _parity_gap(history)
    if even_gap >= 100:
        for n in range(1, MAX_NUM + 1):
            if n % 2 == 0:
                mf[n] *= 1.15
                ac[n] *= 1.15
    if odd_gap >= 100:
        for n in range(1, MAX_NUM + 1):
            if n % 2 == 1:
                mf[n] *= 1.15
                ac[n] *= 1.15
    bet1 = _top_n(mf)
    bet2 = _top_n(ac, exclude=set(bet1))
    return [bet1, bet2]


# --- P1-2: Top2-voting consensus ---
def _top2_voting_scores(history):
    """Instead of mean-0.5σ, take top-2 agent scores for each number"""
    agents = {
        'acb': acb_scores(history),
        'midfreq': midfreq_scores(history),
        'fourier': fourier_scores(history),
        'markov': markov_scores(history),
    }
    # Normalize each agent to [0, 1]
    normed = {}
    for name, sc in agents.items():
        vals = list(sc.values())
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx > mn else 1
        normed[name] = {n: (sc[n] - mn) / rng for n in sc}

    # For each number, take mean of top-2 agent scores
    combined = {}
    for n in range(1, MAX_NUM + 1):
        agent_scores = sorted([normed[a].get(n, 0) for a in normed], reverse=True)
        combined[n] = np.mean(agent_scores[:2])  # top-2 mean
    return combined


def top2_voting_1bet(history):
    return [_top_n(_top2_voting_scores(history))]

def top2_voting_2bet(history):
    scores = _top2_voting_scores(history)
    ranked = sorted(scores, key=lambda x: -scores[x])
    bet1 = sorted(ranked[:5])
    bet2 = sorted(ranked[5:10])
    return [bet1, bet2]

def top2_voting_3bet(history):
    scores = _top2_voting_scores(history)
    ranked = sorted(scores, key=lambda x: -scores[x])
    bet1 = sorted(ranked[:5])
    bet2 = sorted(ranked[5:10])
    bet3 = sorted(ranked[10:15])
    return [bet1, bet2, bet3]


# --- P1-3: Zone-reversion ---
def _zone_extreme(history, lookback=1):
    """Check if recent draw had extreme zone pattern"""
    if len(history) < lookback:
        return False, None
    last = history[-1]['numbers'][:PICK]
    z1 = sum(1 for n in last if 1 <= n <= 13)
    z2 = sum(1 for n in last if 14 <= n <= 26)
    z3 = sum(1 for n in last if 27 <= n <= 39)
    # Extreme: any zone has 0 or 4+ numbers
    extreme = (z1 >= 4 or z2 >= 4 or z3 >= 4 or z1 == 0 or z2 == 0 or z3 == 0)
    deficit_zone = None
    if z1 == 0: deficit_zone = 'Z1'
    elif z2 == 0: deficit_zone = 'Z2'
    elif z3 == 0: deficit_zone = 'Z3'
    elif z1 >= 4: deficit_zone = 'Z2Z3'  # opposite zones are deficit
    elif z2 >= 4: deficit_zone = 'Z1Z3'
    elif z3 >= 4: deficit_zone = 'Z1Z2'
    return extreme, deficit_zone


def zone_reversion_acb_2bet(history):
    """ACB 2bet with zone-reversion boost after extreme zone draws"""
    mf = midfreq_scores(history)
    ac = acb_scores(history)
    extreme, deficit = _zone_extreme(history)
    if extreme and deficit:
        zone_ranges = {'Z1': (1, 13), 'Z2': (14, 26), 'Z3': (27, 39)}
        boost_zones = []
        if deficit in zone_ranges:
            boost_zones = [deficit]
        else:
            # deficit like 'Z2Z3' means boost Z2 and Z3
            boost_zones = [z for z in ['Z1', 'Z2', 'Z3'] if z in deficit]
        for z in boost_zones:
            lo, hi = zone_ranges[z]
            for n in range(lo, hi + 1):
                mf[n] *= 1.20
                ac[n] *= 1.20
    bet1 = _top_n(mf)
    bet2 = _top_n(ac, exclude=set(bet1))
    return [bet1, bet2]


# --- P1-4: MidFreq+ACB_b8 2bet (already deployed, verify McNemar) ---
def midfreq_acb_b8_2bet(history):
    bet1 = _top_n(midfreq_scores(history))
    bet2 = _top_n(acb_scores(history, boundary_threshold=8), exclude=set(bet1))
    return [bet1, bet2]


# --- P2-1: Markov+Weibull 正交 2-bet ---
def markov_weibull_2bet(history):
    bet1 = _top_n(markov_scores(history))
    bet2 = _top_n(weibull_gap_scores(history), exclude=set(bet1))
    return [bet1, bet2]


# --- P2-2: FFT window 300 vs 500 ---
def fourier_w300_3bet(history):
    bet1 = _top_n(acb_scores(history))
    bet2 = _top_n(markov_scores(history), exclude=set(bet1))
    excl = set(bet1) | set(bet2)
    bet3 = _top_n(fourier_scores(history, window=300), exclude=excl)
    return [bet1, bet2, bet3]


# ============================================================
# Main
# ============================================================

def main():
    t_start = time.time()
    print("=" * 72)
    print(" 今彩539 綜合回測: P1 + P2 行動項目")
    print(" 日期: 2026-03-14 | LLM Research Board")
    print("=" * 72)

    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))
    all_draws = [d for d in all_draws if d.get('numbers')]
    print(f"\n  資料: {len(all_draws)} 期")
    if all_draws:
        print(f"  最新: {all_draws[-1]['draw']} ({all_draws[-1].get('date', 'N/A')})")

    # Strategy matrix
    strategies = [
        # Baselines
        ('Baseline_ACB_1bet',              baseline_acb_1bet,              1),
        ('Baseline_MidFreq+ACB_2bet',      baseline_midfreq_acb_2bet,     2),
        ('Baseline_AMF_3bet',              baseline_acb_markov_fourier_3bet, 3),
        # P1-1: Parity-gap
        ('P1_ParityGap_ACB_1bet',          parity_gap_acb_1bet,           1),
        ('P1_ParityGap_MF+ACB_2bet',       parity_gap_midfreq_acb_2bet,   2),
        # P1-2: Top2-voting
        ('P1_Top2Vote_1bet',               top2_voting_1bet,              1),
        ('P1_Top2Vote_2bet',               top2_voting_2bet,              2),
        ('P1_Top2Vote_3bet',               top2_voting_3bet,              3),
        # P1-3: Zone-reversion
        ('P1_ZoneRev_MF+ACB_2bet',         zone_reversion_acb_2bet,       2),
        # P1-4: MidFreq+ACB_b8
        ('P1_MF+ACB_b8_2bet',             midfreq_acb_b8_2bet,           2),
        # P2-1: Markov+Weibull
        ('P2_Markov+Weibull_2bet',         markov_weibull_2bet,           2),
        # P2-2: Fourier w300
        ('P2_AMF_w300_3bet',               fourier_w300_3bet,             3),
    ]

    all_results = {}

    for name, func, n_bets in strategies:
        print(f"\n{'─' * 60}")
        print(f" {name} ({n_bets}注)")
        print(f"{'─' * 60}")

        # Three-window test
        windows = three_window_test(func, all_draws, n_bets)
        all_positive = True
        for w, r in sorted(windows.items()):
            if r:
                ok = '+' if r['edge'] > 0 else '-'
                print(f"  {w:4d}p: rate={r['rate']:.2f}% edge={r['edge']:+.2f}% z={r['z']:.2f} [{ok}]")
                if r['edge'] <= 0:
                    all_positive = False
            else:
                all_positive = False

        # Permutation test (1500p)
        perm = permutation_test_539(func, all_draws, 1500, n_bets)
        sig = 'SIG' if perm['p_value'] < 0.05 else 'ns'
        print(f"  Perm: signal={perm['signal_edge']:+.2f}% z={perm['perm_z']:.2f} p={perm['p_value']:.3f} [{sig}]")

        # Sharpe (300p)
        r300 = windows.get(500, None) or windows.get(1500, None)
        sharpe = 0
        if r300 and r300['edge'] > 0 and r300['total'] > 0:
            p0 = r300['baseline'] / 100
            se = np.sqrt(p0 * (1 - p0) / r300['total'])
            sharpe = (r300['rate'] / 100 - p0) / se if se > 0 else 0

        verdict = 'PASS' if (all_positive and perm['p_value'] < 0.05) else 'FAIL'
        print(f"  Verdict: {verdict} | Sharpe500p={sharpe:.3f}")

        all_results[name] = {
            'n_bets': n_bets,
            'windows': {str(k): {'edge': v['edge'], 'rate': v['rate'], 'z': v['z']} if v else None
                        for k, v in windows.items()},
            'perm_p': perm['p_value'],
            'perm_z': perm['perm_z'],
            'signal_edge': perm['signal_edge'],
            'all_positive': all_positive,
            'sharpe': sharpe,
            'verdict': verdict,
            'hit_details': windows.get(1500, {}).get('hit_details', []) if windows.get(1500) else [],
        }

    # ============================================================
    # McNemar comparisons
    # ============================================================
    print(f"\n{'=' * 72}")
    print(" McNemar 對比測試")
    print(f"{'=' * 72}")

    mcnemar_pairs = [
        ('Baseline_ACB_1bet', 'P1_ParityGap_ACB_1bet'),
        ('Baseline_MidFreq+ACB_2bet', 'P1_ParityGap_MF+ACB_2bet'),
        ('Baseline_MidFreq+ACB_2bet', 'P1_MF+ACB_b8_2bet'),
        ('Baseline_MidFreq+ACB_2bet', 'P1_ZoneRev_MF+ACB_2bet'),
        ('Baseline_MidFreq+ACB_2bet', 'P1_Top2Vote_2bet'),
        ('Baseline_MidFreq+ACB_2bet', 'P2_Markov+Weibull_2bet'),
        ('Baseline_AMF_3bet', 'P1_Top2Vote_3bet'),
        ('Baseline_AMF_3bet', 'P2_AMF_w300_3bet'),
        ('Baseline_ACB_1bet', 'P1_Top2Vote_1bet'),
    ]

    mcnemar_results = {}
    for a_name, b_name in mcnemar_pairs:
        a_hits = all_results.get(a_name, {}).get('hit_details', [])
        b_hits = all_results.get(b_name, {}).get('hit_details', [])
        if a_hits and b_hits and len(a_hits) == len(b_hits):
            mc = mcnemar_test(a_hits, b_hits)
            direction = 'B>A' if mc['n01'] > mc['n10'] else 'A>B' if mc['n10'] > mc['n01'] else 'TIE'
            sig_mark = 'SIG' if mc['sig'] else 'ns'
            net = mc['n10'] - mc['n01']
            print(f"  {a_name} vs {b_name}")
            print(f"    n01={mc['n01']} n10={mc['n10']} net={net:+d} p={mc['p']:.3f} [{sig_mark}] {direction}")
            mcnemar_results[f"{a_name}_vs_{b_name}"] = {
                'n01': mc['n01'], 'n10': mc['n10'],
                'net': net, 'p': mc['p'], 'sig': mc['sig'], 'direction': direction
            }

    # ============================================================
    # Summary table
    # ============================================================
    print(f"\n{'=' * 72}")
    print(" 總結排名")
    print(f"{'=' * 72}")

    # Group by n_bets
    for nb in [1, 2, 3]:
        strats = [(name, r) for name, r in all_results.items() if r['n_bets'] == nb]
        if not strats:
            continue
        print(f"\n  === {nb}注策略 ===")
        strats.sort(key=lambda x: -(x[1].get('windows', {}).get('1500', {}) or {'edge': -99}).get('edge', -99) if isinstance((x[1].get('windows', {}).get('1500', {})), dict) else -99)

        for name, r in strats:
            w150 = r['windows'].get('150', {})
            w500 = r['windows'].get('500', {})
            w1500 = r['windows'].get('1500', {})
            e150 = f"{w150['edge']:+.2f}%" if w150 else "N/A"
            e500 = f"{w500['edge']:+.2f}%" if w500 else "N/A"
            e1500 = f"{w1500['edge']:+.2f}%" if w1500 else "N/A"
            print(f"  {name:<35} 150p={e150:>8} 500p={e500:>8} 1500p={e1500:>8} perm_p={r['perm_p']:.3f} → {r['verdict']}")

    # ============================================================
    # Gate decision
    # ============================================================
    print(f"\n{'=' * 72}")
    print(" 閘門判決 (5-Stage Gate)")
    print(f"{'=' * 72}")

    for name, r in all_results.items():
        s1 = r['all_positive']
        s2 = r['perm_p'] < 0.05
        s4 = r['sharpe'] > 0
        s5 = True  # No trend data in offline backtest
        verdict_detail = f"S1={'P' if s1 else 'F'} S2={'P' if s2 else 'F'} S4={'P' if s4 else 'F'}"
        final = 'DEPLOY' if (s1 and s2 and s4) else 'OBSERVE' if s1 else 'REJECT'
        print(f"  {name:<35} {verdict_detail} → {final}")

    # Save results
    elapsed = time.time() - t_start
    save_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_draws': len(all_draws),
        'elapsed_seconds': round(elapsed, 1),
        'strategies': {k: {kk: vv for kk, vv in v.items() if kk != 'hit_details'}
                       for k, v in all_results.items()},
        'mcnemar': mcnemar_results,
    }
    out_path = os.path.join(project_root, 'backtest_539_comprehensive_p1p2_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2,
                  default=lambda o: bool(o) if isinstance(o, np.bool_) else
                  float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    print(f"\n  結果儲存: {out_path}")
    print(f"  耗時: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
