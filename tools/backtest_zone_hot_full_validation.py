#!/usr/bin/env python3
"""
Zone Cascade Guard + Hot-Streak Override 完整標準驗證
=====================================================
依 CLAUDE.md 驗證標準：
  1. 三窗口 (150/500/1500) 全正
  2. 統計顯著性 z-score → p < 0.05
  3. Permutation Test (200 shuffles)
  4. Walk-Forward OOS (5-fold)
  5. Sharpe Ratio > 0
  6. McNemar Test (Guards vs NoGuards)
  7. 策略評分 Score = (ROI × Stability × Significance) ÷ Complexity
"""
import sys
import os
import math
import random
import numpy as np
from collections import Counter
from itertools import combinations
from datetime import datetime
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from numpy.fft import fft, fftfreq

# ================================================================
# 內嵌精簡 Coordinator (equal-weight, 可控 guards 開關)
# ================================================================

_ZONE_BOUNDS = {
    'BIG_LOTTO': [(1, 16), (17, 32), (33, 49)],
}


def _normalize(scores):
    if not scores:
        return scores
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    r = mx - mn
    if r == 0:
        return {n: 0.5 for n in scores}
    return {n: (v - mn) / r for n, v in scores.items()}


def _fourier_score(history, window=500, max_num=49):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, max_num + 1):
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


def _cold_score(history, window=100, max_num=49):
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    scores = {}
    for n in range(1, max_num + 1):
        scores[n] = float(len(recent) - last_seen.get(n, -1))
    mx = max(scores.values()) or 1.0
    return {n: s / mx for n, s in scores.items()}


def _neighbor_score(history, max_num=49):
    scores = {n: 0.0 for n in range(1, max_num + 1)}
    prev_nums = history[-1]['numbers']
    for pn in prev_nums:
        for delta in (-1, 0, 1):
            nn = pn + delta
            if 1 <= nn <= max_num:
                scores[nn] += 1.0 if delta == 0 else 0.7
    return scores


def _markov_score(history, window=30, max_num=49):
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                transitions[pn][nn] += 1
    scores = {n: 0.0 for n in range(1, max_num + 1)}
    for pn in history[-1]['numbers']:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] = scores.get(n, 0.0) + cnt / total
    return scores


def _consensus_score(history, max_num=49):
    s1 = _normalize(_cold_score(history, max_num=max_num))
    s2 = _normalize(_fourier_score(history, max_num=max_num))
    s3 = _normalize(_markov_score(history, max_num=max_num))
    s4 = _normalize(_neighbor_score(history, max_num=max_num))
    out = {}
    for n in range(1, max_num + 1):
        vals = [s1.get(n, 0), s2.get(n, 0), s3.get(n, 0), s4.get(n, 0)]
        out[n] = max(0.0, float(np.mean(vals)) - 0.5 * float(np.std(vals)))
    return out


AGENTS = {
    'fourier': lambda h: _fourier_score(h, window=500, max_num=49),
    'cold': lambda h: _cold_score(h, window=100, max_num=49),
    'neighbor': lambda h: _neighbor_score(h, max_num=49),
    'markov': lambda h: _markov_score(h, window=30, max_num=49),
    'consensus': lambda h: _consensus_score(h, max_num=49),
}


def zone_cascade_boost(scores, history):
    bounds = _ZONE_BOUNDS['BIG_LOTTO']
    prev_nums = set(history[-1]['numbers'])
    zone_counts = [sum(1 for n in prev_nums if lo <= n <= hi) for lo, hi in bounds]
    max_score = max(scores.values()) if scores else 1.0
    boosted = dict(scores)
    for i, (lo, hi) in enumerate(bounds):
        if zone_counts[i] == 0:
            boost = 0.12 * max_score
            for n in range(lo, hi + 1):
                boosted[n] = boosted.get(n, 0.0) + boost
        elif zone_counts[i] >= 4:
            penalty = 0.05 * max_score
            for n in range(lo, hi + 1):
                boosted[n] = max(0.0, boosted.get(n, 0.0) - penalty)
    return boosted


def hot_streak_boost(scores, history, max_num=49, bet_size=6):
    windows = [8, 10, 12, 15, 20, 30]
    p = bet_size / max_num
    max_z = {n: 0.0 for n in range(1, max_num + 1)}
    for w in windows:
        recent = history[-w:] if len(history) >= w else history
        n_draws = len(recent)
        if n_draws < 5:
            continue
        freq = Counter(n for d in recent for n in d['numbers'])
        expected = n_draws * p
        std = math.sqrt(n_draws * p * (1 - p))
        if std <= 0:
            continue
        for n in range(1, max_num + 1):
            z = (freq.get(n, 0) - expected) / std
            if z > max_z[n]:
                max_z[n] = z
    max_score = max(scores.values()) if scores else 1.0
    boosted = dict(scores)
    for n in range(1, max_num + 1):
        z = max_z[n]
        if z > 2.0:
            boost = (z - 2.0) * 0.06 * max_score
            boosted[n] = boosted.get(n, 0.0) + boost
    return boosted


def aggregate_and_predict(history, n_bets, use_guards):
    final = {n: 0.0 for n in range(1, 50)}
    w_each = 1.0 / len(AGENTS)
    for name, fn in AGENTS.items():
        raw = fn(history)
        norm = _normalize(raw)
        for n, s in norm.items():
            final[n] += w_each * s
    if use_guards:
        final = hot_streak_boost(final, history)
        final = zone_cascade_boost(final, history)
    ranked = sorted(final, key=lambda n: -final[n])
    bets = []
    for i in range(n_bets):
        s = i * 6
        e = s + 6
        if s >= len(ranked):
            break
        bets.append(sorted(ranked[s:e]))
    return bets


# ================================================================
# 回測引擎
# ================================================================

def run_backtest(history, n_bets, use_guards, start_idx):
    results = []
    for i in range(start_idx, len(history)):
        h = history[:i]
        actual = set(history[i]['numbers'])
        bets = aggregate_and_predict(h, n_bets, use_guards)
        best = 0
        for b in bets:
            m = len(set(b) & actual)
            if m > best:
                best = m
        results.append(best >= 3)
    return results


def edge_rate(results):
    if not results:
        return 0.0
    return sum(results) / len(results)


def z_score_and_p(rate, baseline, n):
    if n == 0:
        return 0.0, 1.0
    se = math.sqrt(baseline * (1 - baseline) / n)
    if se == 0:
        return 0.0, 1.0
    z = (rate - baseline) / se
    # one-sided p-value (via normal approximation)
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return z, p


def sharpe_ratio(rate, baseline):
    if rate <= 0:
        return 0.0
    edge = rate - baseline
    std = math.sqrt(rate * (1 - rate))
    if std == 0:
        return 0.0
    return edge / std


def three_window_edges(results, baseline):
    out = {}
    for name, w in [('150p', 150), ('500p', 500), ('1500p', 1500)]:
        if len(results) < w:
            out[name] = None
            continue
        rate = edge_rate(results[-w:])
        out[name] = (rate - baseline) * 100
    return out


# ================================================================
# Permutation Test
# ================================================================

def permutation_test(history, n_bets, use_guards, start_idx, real_edge,
                     n_perms=200, seed=42):
    rng = random.Random(seed)
    count_ge = 0
    for p_i in range(n_perms):
        # Shuffle the draw ordering (breaks temporal structure)
        shuffled = list(history)
        rng.shuffle(shuffled)
        results = run_backtest(shuffled, n_bets, use_guards, start_idx)
        perm_rate = edge_rate(results)
        if perm_rate >= real_edge:
            count_ge += 1
        if (p_i + 1) % 50 == 0:
            print(f'    perm {p_i+1}/{n_perms}  count_ge={count_ge}')
    perm_p = (count_ge + 1) / (n_perms + 1)
    return perm_p


# ================================================================
# Walk-Forward OOS
# ================================================================

def walk_forward_oos(history, n_bets, use_guards, n_folds=5, min_train=200):
    total = len(history)
    fold_size = (total - min_train) // n_folds
    oos_results = []
    for fold in range(n_folds):
        test_start = min_train + fold * fold_size
        test_end = min(test_start + fold_size, total)
        if test_start >= total:
            break
        results = []
        for i in range(test_start, test_end):
            h = history[:i]
            actual = set(history[i]['numbers'])
            bets = aggregate_and_predict(h, n_bets, use_guards)
            best = max(len(set(b) & actual) for b in bets)
            results.append(best >= 3)
        fold_rate = edge_rate(results)
        oos_results.append({
            'fold': fold + 1,
            'test_start': test_start,
            'test_end': test_end,
            'n': len(results),
            'rate': fold_rate,
        })
    return oos_results


# ================================================================
# McNemar Test
# ================================================================

def mcnemar_test(results_a, results_b):
    """Compare two boolean result lists. Returns chi2, p-value."""
    assert len(results_a) == len(results_b)
    b_c = 0  # A hit, B miss
    c_b = 0  # A miss, B hit
    for a, b in zip(results_a, results_b):
        if a and not b:
            b_c += 1
        elif b and not a:
            c_b += 1
    n = b_c + c_b
    if n == 0:
        return 0.0, 1.0
    chi2 = (abs(b_c - c_b) - 1) ** 2 / n
    # chi2 with 1 df
    p = 0.5 * math.erfc(math.sqrt(chi2 / 2))
    return chi2, p, b_c, c_b


# ================================================================
# 策略評分
# ================================================================

def strategy_score(edge, stability, p_value, complexity):
    roi = edge
    sig = -math.log10(max(p_value, 1e-10))
    return (roi * stability * sig) / complexity


# ================================================================
# Main
# ================================================================

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = sorted(db.get_all_draws(lottery_type='BIG_LOTTO'),
                     key=lambda x: (x['date'], x['draw']))
    total = len(history)
    print(f'BIG_LOTTO draws: {total}')
    print(f'Date range: {history[0]["date"]} ~ {history[-1]["date"]}')
    print()

    baselines = {2: 0.0369, 3: 0.0549}
    START_IDX = 200

    all_results = {}

    for n_bets in [2, 3]:
        bl = baselines[n_bets]
        print(f'{"=" * 70}')
        print(f'  {n_bets}-BET FULL VALIDATION')
        print(f'{"=" * 70}')
        print(f'  Baseline M3+ rate: {bl*100:.2f}%')
        print(f'  Metric: is_m3plus (best match >= 3)')
        print()

        # ---------- Run backtest (NoGuards / Guards) ----------
        print('[1] Running NoGuards backtest...')
        res_no = run_backtest(history, n_bets, False, START_IDX)
        rate_no = edge_rate(res_no)
        print(f'    Done. {sum(res_no)}/{len(res_no)} M3+ hits, rate={rate_no*100:.2f}%')

        print('[2] Running Guards backtest...')
        res_yes = run_backtest(history, n_bets, True, START_IDX)
        rate_yes = edge_rate(res_yes)
        print(f'    Done. {sum(res_yes)}/{len(res_yes)} M3+ hits, rate={rate_yes*100:.2f}%')
        print()

        # ---------- Three-Window Validation ----------
        print('[3] Three-Window Validation:')
        tw_no = three_window_edges(res_no, bl)
        tw_yes = three_window_edges(res_yes, bl)
        all_pos_no = True
        all_pos_yes = True
        print(f'  {"Window":>8s}  {"NoGuards":>10s}  {"Guards":>10s}')
        for w in ['150p', '500p', '1500p']:
            v_no = tw_no[w]
            v_yes = tw_yes[w]
            if v_no is not None and v_no <= 0:
                all_pos_no = False
            if v_yes is not None and v_yes <= 0:
                all_pos_yes = False
            s_no = f'{v_no:+.2f}%' if v_no is not None else 'N/A'
            s_yes = f'{v_yes:+.2f}%' if v_yes is not None else 'N/A'
            print(f'  {w:>8s}  {s_no:>10s}  {s_yes:>10s}')
        print(f'  Three-Window: NoGuards={"PASS" if all_pos_no else "FAIL"}  '
              f'Guards={"PASS" if all_pos_yes else "FAIL"}')
        print()

        # ---------- Z-score / p-value ----------
        print('[4] Statistical Significance:')
        z_no, p_no = z_score_and_p(rate_no, bl, len(res_no))
        z_yes, p_yes = z_score_and_p(rate_yes, bl, len(res_yes))
        print(f'  NoGuards: z={z_no:.3f}  p={p_no:.4f}  {"PASS" if p_no < 0.05 else "FAIL"}')
        print(f'  Guards:   z={z_yes:.3f}  p={p_yes:.4f}  {"PASS" if p_yes < 0.05 else "FAIL"}')
        print()

        # ---------- Sharpe Ratio ----------
        print('[5] Sharpe Ratio:')
        sr_no = sharpe_ratio(rate_no, bl)
        sr_yes = sharpe_ratio(rate_yes, bl)
        print(f'  NoGuards: {sr_no:.4f}  {"PASS" if sr_no > 0 else "FAIL"}')
        print(f'  Guards:   {sr_yes:.4f}  {"PASS" if sr_yes > 0 else "FAIL"}')
        print()

        # ---------- Permutation Test ----------
        print('[6] Permutation Test (200 shuffles, Guards):')
        perm_p = permutation_test(history, n_bets, True, START_IDX,
                                   rate_yes, n_perms=200, seed=42)
        print(f'  Perm p-value: {perm_p:.4f}  {"PASS" if perm_p < 0.05 else "FAIL"}')
        print()

        # ---------- Walk-Forward OOS ----------
        print('[7] Walk-Forward OOS (5-fold, Guards):')
        oos = walk_forward_oos(history, n_bets, True, n_folds=5, min_train=200)
        oos_rates = []
        for fold_info in oos:
            r = fold_info['rate']
            e = (r - bl) * 100
            oos_rates.append(r)
            print(f'  Fold {fold_info["fold"]}: n={fold_info["n"]} '
                  f'rate={r*100:.2f}% edge={e:+.2f}%')
        oos_avg = np.mean(oos_rates)
        oos_all_pos = all((r - bl) > 0 for r in oos_rates)
        print(f'  OOS avg rate: {oos_avg*100:.2f}% edge={((oos_avg-bl)*100):+.2f}%')
        print(f'  All folds positive: {"PASS" if oos_all_pos else "FAIL"}')
        print()

        # ---------- McNemar Test ----------
        print('[8] McNemar Test (Guards vs NoGuards):')
        chi2, mc_p, bc, cb = mcnemar_test(res_yes, res_no)
        print(f'  Guards-only hits: {cb}  NoGuards-only hits: {bc}')
        print(f'  chi2={chi2:.3f}  p={mc_p:.4f}')
        dir_txt = 'Guards better' if cb > bc else 'NoGuards better' if bc > cb else 'Equal'
        print(f'  Direction: {dir_txt}')
        print()

        # ---------- Strategy Score ----------
        edge_1500 = tw_yes.get('1500p')
        if edge_1500 is not None and edge_1500 > 0:
            stab_vals = [tw_yes[w] for w in ['150p', '500p', '1500p'] if tw_yes[w] is not None]
            if len(stab_vals) == 3:
                stability = 1 - min(abs(stab_vals[0] - stab_vals[2]) / max(abs(stab_vals[2]), 0.01), 1.0)
            else:
                stability = 0.5
            complexity = 5 * 6  # 5 agents × ~6 hyper-params
            s = strategy_score(edge_1500, stability, p_yes, complexity)
        else:
            stability = 0.0
            s = 0.0

        print('[9] Strategy Score:')
        print(f'  Edge(1500p): {edge_1500:+.2f}%' if edge_1500 is not None else '  Edge: N/A')
        print(f'  Stability: {stability:.3f}')
        print(f'  p-value: {p_yes:.4f}')
        print(f'  Complexity: 30')
        print(f'  Score: {s:.4f}')
        print()

        # ---------- VERDICT ----------
        checks = {
            'three_window': all_pos_yes,
            'significance': p_yes < 0.05,
            'permutation': perm_p < 0.05,
            'sharpe': sr_yes > 0,
        }
        pass_count = sum(checks.values())
        verdict = 'ADOPTED' if pass_count >= 4 else 'PROVISIONAL' if pass_count >= 3 else 'REJECTED'
        print(f'[VERDICT] {n_bets}-bet Zone Cascade + Hot-Streak Guards:')
        for name, ok in checks.items():
            print(f'  {name:>15s}: {"PASS" if ok else "FAIL"}')
        print(f'  OOS all positive: {"PASS" if oos_all_pos else "WARN"}')
        print(f'  → {verdict} ({pass_count}/4 mandatory checks passed)')
        print()

        all_results[f'{n_bets}bet'] = {
            'rate_no_guards': rate_no,
            'rate_guards': rate_yes,
            'edge_no_guards': (rate_no - bl) * 100,
            'edge_guards': (rate_yes - bl) * 100,
            'three_window_no': tw_no,
            'three_window_yes': tw_yes,
            'three_window_pass': all_pos_yes,
            'z_score': z_yes,
            'p_value': p_yes,
            'perm_p': perm_p,
            'sharpe': sr_yes,
            'oos_avg_edge': (oos_avg - bl) * 100,
            'oos_all_pos': oos_all_pos,
            'mcnemar_chi2': chi2,
            'mcnemar_p': mc_p,
            'strategy_score': s,
            'verdict': verdict,
        }

    # Save results
    out = {
        'timestamp': datetime.now().isoformat(),
        'description': 'Zone Cascade Guard + Hot-Streak Override Full Validation',
        'lottery_type': 'BIG_LOTTO',
        'total_draws': total,
        'start_idx': START_IDX,
        'results': all_results,
    }
    out_path = os.path.join(project_root, 'backtest_zone_hot_guards_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f'Full results saved to {out_path}')


if __name__ == '__main__':
    main()
