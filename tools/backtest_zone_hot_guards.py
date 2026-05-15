#!/usr/bin/env python3
"""
回測腳本：Zone Cascade Guard + Hot-Streak Override
===================================================
比較 Coordinator-Direct (with/without guards) 的 M3+ 命中率。
三窗口驗證：150 / 500 / 1500 期。
"""
import sys
import os
import json
import math
import random
import numpy as np
from collections import Counter
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager


# ========== 內嵌精簡策略（避免依賴外部模組的 RSM 權重） ==========

from numpy.fft import fft, fftfreq


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
        gap = len(recent) - last_seen.get(n, -1)
        scores[n] = float(gap)
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


# ========== Zone Cascade + Hot-Streak 邏輯 ==========

_ZONE_BOUNDS = {
    'BIG_LOTTO': [(1, 16), (17, 32), (33, 49)],
    'POWER_LOTTO': [(1, 13), (14, 26), (27, 38)],
}


def _zone_cascade_boost(scores, history, lottery_type):
    bounds = _ZONE_BOUNDS.get(lottery_type)
    if not bounds or not history:
        return scores
    prev_nums = set(history[-1]['numbers'])
    zone_counts = []
    for lo, hi in bounds:
        zone_counts.append(sum(1 for n in prev_nums if lo <= n <= hi))
    max_score = max(scores.values()) if scores else 1.0
    boosted = dict(scores)
    for i, (lo, hi) in enumerate(bounds):
        cnt = zone_counts[i]
        if cnt == 0:
            boost = 0.12 * max_score
            for n in range(lo, hi + 1):
                boosted[n] = boosted.get(n, 0.0) + boost
        elif cnt >= 4:
            penalty = 0.05 * max_score
            for n in range(lo, hi + 1):
                boosted[n] = max(0.0, boosted.get(n, 0.0) - penalty)
    return boosted


def _hot_streak_boost(scores, history, max_num=49, bet_size=6,
                       windows=None, z_threshold=2.0):
    if windows is None:
        windows = [8, 10, 12, 15, 20, 30]
    if len(history) < 10:
        return scores
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
        if z > z_threshold:
            boost = (z - z_threshold) * 0.06 * max_score
            boosted[n] = boosted.get(n, 0.0) + boost
    return boosted


# ========== Coordinator (精簡版) ==========

AGENTS_BL = {
    'fourier':   lambda h: _fourier_score(h, window=500, max_num=49),
    'cold':      lambda h: _cold_score(h, window=100, max_num=49),
    'neighbor':  lambda h: _neighbor_score(h, max_num=49),
    'markov':    lambda h: _markov_score(h, window=30, max_num=49),
    'consensus': lambda h: _consensus_score(h, max_num=49),
}


def _aggregate_scores(history, use_guards=False, lottery_type='BIG_LOTTO'):
    final = {n: 0.0 for n in range(1, 50)}
    w_each = 1.0 / len(AGENTS_BL)
    for name, fn in AGENTS_BL.items():
        raw = fn(history)
        norm = _normalize(raw)
        for n, s in norm.items():
            final[n] += w_each * s
    if use_guards:
        final = _hot_streak_boost(final, history, max_num=49, bet_size=6)
        final = _zone_cascade_boost(final, history, lottery_type)
    return final


def _predict_n_bets(history, n_bets, use_guards):
    scores = _aggregate_scores(history, use_guards=use_guards)
    ranked = sorted(scores, key=lambda n: -scores[n])
    bets = []
    for i in range(n_bets):
        start = i * 6
        end = start + 6
        if start >= len(ranked):
            break
        bets.append(sorted(ranked[start:end]))
    return bets


# ========== 回測主迴圈 ==========

def backtest(history, n_bets, use_guards, start_idx=200, label=''):
    results = []
    total = len(history) - start_idx
    for i in range(start_idx, len(history)):
        h_up_to = history[:i]
        actual = set(history[i]['numbers'])
        bets = _predict_n_bets(h_up_to, n_bets, use_guards)
        best_match = 0
        match_counts = []
        for b in bets:
            m = len(set(b) & actual)
            match_counts.append(m)
            if m > best_match:
                best_match = m
        results.append({
            'draw': history[i]['draw'],
            'best_match': best_match,
            'match_counts': match_counts,
            'is_m3plus': best_match >= 3,
            'is_m2plus': best_match >= 2,
        })
        if (i - start_idx) % 200 == 0:
            done = i - start_idx
            rate_so_far = sum(1 for r in results if r['is_m3plus']) / len(results) * 100 if results else 0
            print(f'  [{label}] {done}/{total} draws ... M3+ rate={rate_so_far:.2f}%')
    return results


def compute_edge(results, baseline, key='is_m3plus'):
    rate = sum(1 for r in results if r[key]) / len(results) if results else 0
    return rate, rate - baseline


def three_window_summary(results, baseline):
    """計算最後 150/500/1500 期的 edge"""
    windows = {'150p': 150, '500p': 500, '1500p': 1500}
    summary = {}
    for name, w in windows.items():
        if len(results) < w:
            summary[name] = {'rate': None, 'edge': None, 'n': len(results)}
            continue
        subset = results[-w:]
        rate, edge = compute_edge(subset, baseline)
        summary[name] = {'rate': rate * 100, 'edge': edge * 100, 'n': w}
    return summary


def random_baseline_edge(history, n_bets, n_trials=500, start_idx=200, seed=42):
    """隨機基準 M3+ 命中率"""
    rng = random.Random(seed)
    hits = 0
    total = 0
    for i in range(start_idx, len(history)):
        actual = set(history[i]['numbers'])
        best = 0
        for _ in range(n_bets):
            bet = rng.sample(range(1, 50), 6)
            m = len(set(bet) & actual)
            if m > best:
                best = m
        if best >= 3:
            hits += 1
        total += 1
    return hits / total if total > 0 else 0.0


def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = sorted(db.get_all_draws(lottery_type='BIG_LOTTO'),
                     key=lambda x: (x['date'], x['draw']))
    print(f'BIG_LOTTO total draws: {len(history)}')

    # Baselines
    bl_m3 = {2: 0.0369, 3: 0.0549}

    for n_bets in [2, 3]:
        print(f'\n{"="*60}')
        print(f'  {n_bets}-bet Backtest: Coordinator with Zone Cascade + Hot-Streak')
        print(f'{"="*60}')

        baseline = bl_m3[n_bets]
        print(f'  Baseline M3+: {baseline*100:.2f}%')

        # Without guards
        print(f'\n--- Without Guards ---')
        results_no = backtest(history, n_bets, use_guards=False,
                              start_idx=200, label=f'{n_bets}bet-noguard')
        sw_no = three_window_summary(results_no, baseline)
        rate_all_no, edge_all_no = compute_edge(results_no, baseline)
        print(f'  Overall: M3+ rate={rate_all_no*100:.2f}% edge={edge_all_no*100:+.2f}% ({len(results_no)} draws)')
        for w, s in sw_no.items():
            if s['rate'] is not None:
                print(f'  {w}: M3+ rate={s["rate"]:.2f}% edge={s["edge"]:+.2f}%')

        # With guards
        print(f'\n--- With Zone Cascade + Hot-Streak Guards ---')
        results_yes = backtest(history, n_bets, use_guards=True,
                               start_idx=200, label=f'{n_bets}bet-guards')
        sw_yes = three_window_summary(results_yes, baseline)
        rate_all_yes, edge_all_yes = compute_edge(results_yes, baseline)
        print(f'  Overall: M3+ rate={rate_all_yes*100:.2f}% edge={edge_all_yes*100:+.2f}% ({len(results_yes)} draws)')
        for w, s in sw_yes.items():
            if s['rate'] is not None:
                print(f'  {w}: M3+ rate={s["rate"]:.2f}% edge={s["edge"]:+.2f}%')

        # Diff
        print(f'\n--- Diff (Guards - NoGuards) ---')
        diff = (rate_all_yes - rate_all_no) * 100
        print(f'  Overall edge diff: {diff:+.2f}pp')
        for w in ['150p', '500p', '1500p']:
            if sw_yes[w]['rate'] is not None and sw_no[w]['rate'] is not None:
                d = sw_yes[w]['rate'] - sw_no[w]['rate']
                print(f'  {w}: {d:+.2f}pp')

        # Zone=0 specific analysis
        print(f'\n--- Zone=0 Subgroup Analysis ---')
        zone_bounds = [(1, 16), (17, 32), (33, 49)]
        z0_hits_no = 0
        z0_hits_yes = 0
        z0_total = 0
        for idx, (rno, ryes) in enumerate(zip(results_no, results_yes)):
            # The draw at start_idx + idx, previous draw is start_idx + idx - 1
            prev_draw_idx = 200 + idx - 1
            if prev_draw_idx < 0:
                continue
            prev_nums = history[prev_draw_idx]['numbers']
            has_zone0 = any(
                sum(1 for n in prev_nums if lo <= n <= hi) == 0
                for lo, hi in zone_bounds
            )
            if has_zone0:
                z0_total += 1
                if rno['is_m3plus']:
                    z0_hits_no += 1
                if ryes['is_m3plus']:
                    z0_hits_yes += 1
        if z0_total > 0:
            r_no = z0_hits_no / z0_total * 100
            r_yes = z0_hits_yes / z0_total * 100
            print(f'  Zone=0 draws: {z0_total}')
            print(f'  NoGuards M3+ in Zone=0: {z0_hits_no}/{z0_total} = {r_no:.2f}%')
            print(f'  Guards   M3+ in Zone=0: {z0_hits_yes}/{z0_total} = {r_yes:.2f}%')
            print(f'  Diff: {r_yes - r_no:+.2f}pp')

    # Save results
    out = {
        'timestamp': datetime.now().isoformat(),
        'description': 'Zone Cascade Guard + Hot-Streak Override backtest',
        'lottery_type': 'BIG_LOTTO',
        'total_draws': len(history),
    }
    out_path = os.path.join(project_root, 'backtest_zone_hot_guards_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'\nResults saved to {out_path}')


if __name__ == '__main__':
    main()
