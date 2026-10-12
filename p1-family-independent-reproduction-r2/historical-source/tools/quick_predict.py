#!/usr/bin/env python3
"""
快速預測腳本 - 供 /predict 命令使用
用法: python3 tools/quick_predict.py [彩票類型] [注數]

策略對照 (2026-03-05 更新):
  今彩539 3注: ACB + Markov + Fourier (PROVISIONAL)
"""
import sys
import os
import random
import argparse
import json
import numpy as np
from datetime import datetime
from numpy.fft import fft, fftfreq
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager


# ========== 尾數多樣性約束 (L54/032期 P0 行動項) ==========

def enforce_tail_diversity(bets, max_same_tail, max_num, history, window=100):
    if not history:
        return bets
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            if n <= max_num:
                freq[n] += 1
    all_used = set()
    for bet in bets:
        all_used.update(bet.get('numbers', []))
    result = []
    for bet in bets:
        nums = list(bet.get('numbers', []))
        changed = _fix_tail_diversity(nums, max_same_tail, max_num, freq, all_used)
        new_bet = dict(bet)
        new_bet['numbers'] = sorted(changed)
        result.append(new_bet)
        all_used.update(changed)
    return result


def _fix_tail_diversity(nums, max_same_tail, max_num, freq, global_used):
    nums = list(nums)
    max_iterations = 10
    for _ in range(max_iterations):
        tail_groups = {}
        for n in nums:
            tail = n % 10
            tail_groups.setdefault(tail, []).append(n)
        violations = {t: ns for t, ns in tail_groups.items() if len(ns) > max_same_tail}
        if not violations:
            break
        worst_tail = max(violations, key=lambda t: len(violations[t]))
        offenders = violations[worst_tail]
        offenders_sorted = sorted(offenders, key=lambda n: freq.get(n, 0))
        to_remove = offenders_sorted[0]
        nums.remove(to_remove)
        current_tails = Counter(n % 10 for n in nums)
        candidates = []
        for n in range(1, max_num + 1):
            if n in set(nums) or n in global_used:
                continue
            if current_tails.get(n % 10, 0) >= max_same_tail:
                continue
            candidates.append(n)
        if candidates:
            best = max(candidates, key=lambda n: freq.get(n, 0))
            nums.append(best)
        else:
            nums.append(to_remove)
            break
    return nums


def _coordinator_bets(lottery_type, history, num_bets, mode='direct'):
    """
    RSM 加權多代理聚合（2注/3注優先）。
    回傳 list[{'numbers': [...]}]；失敗時回傳 None 讓上層 fallback。
    """
    try:
        from lottery_api.engine.strategy_coordinator import coordinator_predict
        c_bets, desc = coordinator_predict(lottery_type, history, n_bets=num_bets, mode=mode)
        if not c_bets:
            return None, None
        wrapped = [{'numbers': sorted(b)} for b in c_bets]
        return wrapped, desc
    except Exception:
        return None, None



def _coordinator_verified_text(lottery_type, num_bets):
    """Coordinator 模式下，從 strategy_states 摘要同注數的最佳長窗 edge。"""
    try:
        p = os.path.join(project_root, 'lottery_api', 'data', f'strategy_states_{lottery_type}.json')
        if not os.path.exists(p):
            return 'RSM-weighted ensemble (no state file)'
        states = json.load(open(p, 'r', encoding='utf-8'))
        cands = [s for s in states.values() if int(s.get('num_bets', 0)) == int(num_bets)]
        if not cands:
            return 'RSM-weighted ensemble'
        best = max(cands, key=lambda s: float(s.get('edge_300p', -9)))
        edge = float(best.get('edge_300p', 0.0)) * 100
        sharpe = float(best.get('sharpe_300p', 0.0))
        return f"RSM-weighted ensemble | ref best={best.get('name')} edge300={edge:+.2f}% sharpe={sharpe:.3f}"
    except Exception:
        return 'RSM-weighted ensemble'


# 彩票類型對照
LOTTERY_MAP = {
    '大樂透': 'BIG_LOTTO', 'biglotto': 'BIG_LOTTO', 'big': 'BIG_LOTTO',
    '威力彩': 'POWER_LOTTO', 'power': 'POWER_LOTTO',
    '今彩539': 'DAILY_539', '539': 'DAILY_539', 'daily': 'DAILY_539',
}

DEFAULT_CONFIG = {
    'BIG_LOTTO': {'bets': 5, 'cost': 250},
    'POWER_LOTTO': {'bets': 2, 'cost': 200},
    'DAILY_539': {'bets': 3, 'cost': 150},
}

STRATEGY_INFO = {
    'BIG_LOTTO': {
        2: {'strategy': 'Regime Fourier+Cold +尾數約束', 'edge': '+1.58%', 'verified': '1500期 STABLE MODERATE_DECAY'},
        3: {'strategy': 'TS3+Regime +尾數約束', 'edge': '+1.52%', 'verified': '1500期 STABLE perm p=0.005'},
        4: {'strategy': 'P1+偏差互補 +尾數約束', 'edge': '+2.17%', 'verified': '1500期 z=3.24 p=0.010'},
        5: {'strategy': 'P1+偏差互補+Sum均值約束 +尾數約束', 'edge': '+3.04%', 'verified': '1500期 ROBUST perm p=0.000'},
    },
    'POWER_LOTTO': {
        2: {'strategy': 'Fourier Rhythm',       'edge': '+1.08%', 'verified': '1500期 STABLE'},
        3: {'strategy': 'Power Precision (fourier_rhythm_3bet)', 'edge': '+3.16%', 'verified': '1500期 STABLE z=2.74 perm p=0.045'},
        4: {'strategy': 'PP3+FreqOrt',          'edge': '+3.07%', 'verified': '1500期 STABLE perm p=0.000'},
        5: {'strategy': '正交 5注 (orthogonal)', 'edge': '+2.42%', 'verified': '1500期 STABLE'},
    },
    'DAILY_539': {
        1: {'strategy': 'ACB 異常捕捉',          'edge': '+3.60%', 'verified': '1500期 STABLE z=3.66 p=0.005 ADOPTED'},
        2: {'strategy': 'MidFreq+ACB 正交2注',   'edge': '+8.79%', 'verified': '1500期 STABLE z=4.77 p=0.005 ADOPTED'},
        3: {'strategy': 'ACB+Markov+MidFreq 3注','edge': '+8.83%', 'verified': '1500期 STABLE z=5.41 p=0.005 ADOPTED'},
        5: {'strategy': 'F4Cold 5注',            'edge': '+6.28%', 'verified': '1500期 STABLE PROVISIONAL'},
    },
}

LOTTERY_NAMES = {'BIG_LOTTO': '大樂透', 'POWER_LOTTO': '威力彩', 'DAILY_539': '今彩539'}
BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 5: 8.96},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60},
    'DAILY_539': {1: 11.40, 2: 21.54, 3: 30.50, 4: 38.43, 5: 45.39},
}

# ========== 輔助函數 (大樂透/威力彩) ==========

def _bl_fourier_scores(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, 50):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']: bh[idx] = 1
        if sum(bh) < 2: scores[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0); pos_yf = np.abs(yf[idx_pos]); pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf); freq_val = pos_xf[peak_idx]
        if freq_val == 0: scores[n] = 0.0; continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else: scores[n] = 0.0
    return scores

def _bl_markov_scores(history, window=30):
    recent = history[-window:]
    transitions = {}
    for i in range(len(recent) - 1):
        for cn in recent[i]['numbers']:
            if cn not in transitions: transitions[cn] = Counter()
            for nn in recent[i + 1]['numbers']: transitions[cn][nn] += 1
    prev_nums = history[-1]['numbers']
    scores = Counter()
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items(): scores[n] += cnt / total
    return scores

def _bl_cold_sum_fixed(history, exclude=None, pool_size=12):
    exclude = exclude or set()
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    candidates = sorted([n for n in range(1, 50) if n not in exclude], key=lambda x: freq.get(x, 0))
    pool = candidates[:pool_size]
    sums = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums), np.std(sums)
    tlo, thi = mu - 0.5 * sg, mu + 0.5 * sg
    best, best_dist, best_in = None, float('inf'), False
    for combo in combinations(pool, 6):
        s = sum(combo); in_range = (tlo <= s <= thi); dist = abs(s - mu)
        if in_range and (not best_in or dist < best_dist):
            best, best_dist, best_in = combo, dist, True
        elif not in_range and not best_in and dist < best_dist:
            best, best_dist = combo, dist
    return sorted(best if best else pool[:6])

def _bl_dev_complement_2bet(history, exclude=None, window=50):
    exclude = exclude or set()
    recent = history[-window:]; expected = len(recent) * 6 / 49
    freq = Counter(n for d in recent for n in d['numbers'])
    hot, cold = [], []
    for n in range(1, 50):
        if n in exclude: continue
        dev = freq.get(n, 0) - expected
        if dev > 1: hot.append((n, dev))
        elif dev < -1: cold.append((n, abs(dev)))
    hot.sort(key=lambda x: -x[1]); cold.sort(key=lambda x: -x[1])
    bet1 = [n for n, _ in hot[:6]]
    used = set(bet1) | exclude
    if len(bet1) < 6:
        mid = sorted([n for n in range(1, 50) if n not in used], key=lambda n: abs(freq.get(n, 0)-expected))
        for n in mid: 
            if len(bet1) < 6: bet1.append(n); used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < 6: bet2.append(n); used.add(n)
    if len(bet2) < 6:
        for n in range(1, 50):
            if n not in used and len(bet2) < 6: bet2.append(n); used.add(n)
    return sorted(bet1[:6]), sorted(bet2[:6])

def _bl_bet5_sum_conditional(history, pool):
    if len(pool) <= 6: return sorted(pool[:6])
    sums = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums), np.std(sums)
    last_s = sum(history[-1]['numbers'])
    if last_s < mu - 0.5 * sg: tlo, thi = mu, mu + sg
    elif last_s > mu + 0.5 * sg: tlo, thi = mu - sg, mu
    else: tlo, thi = mu - 0.5 * sg, mu + 0.5 * sg
    freq = Counter(n for d in history[-100:] for n in d['numbers']); expected = len(history[-100:]) * 6 / 49
    pool_cand = sorted(pool, key=lambda n: abs(freq.get(n, 0) - expected))[:18]
    best, best_dist = None, float('inf')
    for combo in combinations(pool_cand, 6):
        s = sum(combo); dist = abs(s - (tlo+thi)/2)
        if dist < best_dist: best, best_dist = combo, dist
    return sorted(best if best else pool_cand[:6])

def biglotto_regime_2bet(history):
    from tools.predict_biglotto_regime import generate_regime_2bet
    return [{'numbers': b} for b in generate_regime_2bet(history)]

def biglotto_triple_strike(history):
    from tools.predict_biglotto_regime import generate_ts3_regime
    return [{'numbers': b} for b in generate_ts3_regime(history)]

def biglotto_p1_deviation_5bet(history):
    prev_nums = history[-1]['numbers']; neighbor_pool = set()
    for n in prev_nums:
        for d in [-1, 0, 1]:
            nn = n+d
            if 1<=nn<=49: neighbor_pool.add(nn)
    f_scores = _bl_fourier_scores(history, window=500); mk_scores = _bl_markov_scores(history, window=30)
    f_max, mk_max = max(f_scores.values()) or 1, max(mk_scores.values()) or 1
    scored = {n: f_scores.get(n,0)/f_max + 0.5*(mk_scores.get(n,0)/mk_max) for n in neighbor_pool}
    ranked = sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)
    bet1 = sorted(ranked[:6]); used = set(bet1)
    bet2 = _bl_cold_sum_fixed(history, exclude=used); used.update(bet2)
    bet3, bet4 = _bl_dev_complement_2bet(history, exclude=used); used.update(bet3); used.update(bet4)
    bet5 = _bl_bet5_sum_conditional(history, [n for n in range(1, 50) if n not in used])
    return [{'numbers': bet1}, {'numbers': bet2}, {'numbers': bet3}, {'numbers': bet4}, {'numbers': bet5}]

def power_fourier_rhythm_2bet(history):
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    return [{'numbers': b} for b in fourier_rhythm_predict(history, n_bets=2, window=500)]

def power_precision_3bet(history):
    from tools.predict_power_precision_3bet import generate_power_precision_3bet
    return [{'numbers': b} for b in generate_power_precision_3bet(history)]

def power_4bet_freqort(history):
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
    return [{'numbers': b} for b in generate_orthogonal_5bet(history)[:4]]

def power_5bet_orthogonal(history):
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
    return [{'numbers': b} for b in generate_orthogonal_5bet(history)]

def power_special_v3(history):
    try:
        from models.special_predictor import PowerLottoSpecialPredictor
        sp = PowerLottoSpecialPredictor({'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8})
        return sp.predict_top_n(history, n=3)
    except: return [n for n, _ in Counter(d.get('special', 0) for d in history[-50:]).most_common(3)]


# ========== 今彩539策略 ==========

def _539_fourier_scores(history, window=500):
    h = history[-window:]; w = len(h)
    scores = {}
    for n in range(1, 40):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']: bh[idx] = 1
        if sum(bh) < 2: scores[n] = 0.0; continue
        yf = fft(bh - np.mean(bh)); xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0); pos_yf = np.abs(yf[idx_pos]); pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf); freq_val = pos_xf[peak_idx]
        if freq_val == 0: scores[n] = 0.0; continue
        scores[n] = 1.0 / (abs((len(h)-1-np.where(bh==1)[0][-1]) - (1/freq_val)) + 1.0)
    return scores

def _539_acb_bet(history, exclude=None, window=100):
    exclude = exclude or set(); recent = history[-window:]
    counter = Counter(n for d in recent for n in d['numbers'])
    last_seen = {n: i for i, d in enumerate(recent) for n in d['numbers']}
    expected_freq = len(recent) * 5 / 39; scores = {}
    for n in range(1, 40):
        if n in exclude: continue
        scores[n] = ((expected_freq - counter.get(n, 0)) * 0.4 + (len(recent) - last_seen.get(n, -1)) / (len(recent)/2) * 0.6) * (1.2 if n <= 8 or n >= 35 else 1.0)
    ranked = sorted(scores, key=lambda x: -scores[x])
    result = ranked[:5]
    return sorted(result)

def _539_markov_bet(history, exclude=None, window=30):
    exclude = exclude or set(); recent = history[-window:]
    transitions = {}
    for i in range(len(recent)-1):
        for pn in recent[i]['numbers']:
            if pn not in transitions: transitions[pn] = Counter()
            for nn in recent[i+1]['numbers']: transitions[pn][nn] += 1
    scores = Counter()
    for pn in history[-1]['numbers']:
        trans = transitions.get(pn, Counter()); total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                if n not in exclude: scores[n] += cnt / total
    ranked = sorted(scores, key=lambda x: -scores[x])
    return sorted(ranked[:5])

def _539_midfreq_bet(history, exclude=None, window=100):
    exclude = exclude or set(); recent = history[-window:]; expected = len(recent) * 5 / 39
    freq = Counter(n for d in recent for n in d['numbers'])
    candidates = sorted([n for n in range(1,40) if n not in exclude], key=lambda x: abs(freq.get(x, 0) - expected))
    return sorted(candidates[:5])


def _detect_cold_phase(history, window=50, baseline=0.0896):
    """
    偵測大樂透 p1_dev_sum5bet 是否處於冷期。
    資料優先順序：
      1. predictions_BIG_LOTTO.jsonl resolved 記錄（≥50 期）
      2. rolling_monitor_BIG_LOTTO.json + DB 新增期補算（最準確）
      3. strategy_states edge_150p 估算
      4. insufficient_data fallback
    回傳 (is_cold: bool, cold_severity: float)
      is_cold = True 當 rolling_50p_edge < 0
    冷期退出: 最近兩個連續 50p 窗口 edge > 0 → consecutive_positive_windows=2
    """
    monitor_path = os.path.join(project_root, 'data', 'rolling_monitor_BIG_LOTTO.json')
    status_path = os.path.join(project_root, 'data', 'cold_phase_status.json')
    pred_log_path = os.path.join(project_root, 'lottery_api', 'data', 'predictions_BIG_LOTTO.jsonl')
    states_path = os.path.join(project_root, 'lottery_api', 'data', 'strategy_states_BIG_LOTTO.json')

    def _write_status(status_dict):
        try:
            with open(status_path, 'w', encoding='utf-8') as _f:
                json.dump(status_dict, _f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _edge_to_status(rolling_edge, records_all, source_label):
        """Compute consecutive windows and write status."""
        is_cold = rolling_edge < 0
        consecutive_pos = 0
        if rolling_edge > 0:
            consecutive_pos = 1
            if len(records_all) >= 2 * window:
                prev_w = records_all[-2 * window:-window]
                prev_hr = sum(1 for r in prev_w if r.get('is_m3plus')) / window
                if (prev_hr - baseline) > 0:
                    consecutive_pos = 2

        cold_since_draw = None
        if is_cold:
            try:
                if os.path.exists(status_path):
                    prev_status = json.load(open(status_path))
                    if prev_status.get('is_cold') and prev_status.get('cold_since_draw'):
                        cold_since_draw = prev_status['cold_since_draw']
            except Exception:
                pass
            if cold_since_draw is None:
                last_w = records_all[-window:]
                cold_since_draw = last_w[0].get('draw_id') or last_w[0].get('period')

        _write_status({
            'lottery': 'BIG_LOTTO',
            'is_cold': is_cold,
            'rolling_50p_edge': round(rolling_edge * 100, 2),
            'cold_since_draw': cold_since_draw if is_cold else None,
            'consecutive_positive_windows': consecutive_pos,
            'last_updated': datetime.now().strftime('%Y/%m/%d'),
            'data_source': source_label,
        })
        return is_cold, rolling_edge

    # ── Priority 1: predictions_BIG_LOTTO.jsonl resolved records ───────────
    try:
        if os.path.exists(pred_log_path):
            p1_resolved = []
            with open(pred_log_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if 'p1_dev_sum5bet' in rec.get('strategy', '') and rec.get('is_m3plus') is not None:
                        p1_resolved.append(rec)
            if len(p1_resolved) >= window:
                last_w = p1_resolved[-window:]
                hit_rate = sum(1 for r in last_w if r.get('is_m3plus')) / window
                rolling_edge = hit_rate - baseline
                return _edge_to_status(rolling_edge, p1_resolved, 'predictions_jsonl')
    except Exception:
        pass

    # ── Priority 2: rolling_monitor + fresh DB computation ─────────────────
    try:
        with open(monitor_path) as f:
            monitor = json.load(f)
        mon_records = monitor.get('records', {}).get('p1_dev_sum5bet', [])
        if len(mon_records) >= window:
            mon_draw_ids = {str(r['draw_id']) for r in mon_records}
            # Find draws in history newer than monitor's last entry (integer compare)
            last_mon_draw_int = int(mon_records[-1]['draw_id'])
            new_draws = [d for d in history if int(d['draw']) > last_mon_draw_int]
            extended = list(mon_records)
            if new_draws:
                # Run strategy for each missing draw (anti-leakage: history up to draw)
                all_draws_sorted = sorted(history, key=lambda x: (x['date'], x['draw']))
                for target_draw in new_draws:
                    if str(target_draw['draw']) in mon_draw_ids:
                        continue
                    draw_idx = next(
                        (i for i, d in enumerate(all_draws_sorted) if str(d['draw']) == str(target_draw['draw'])),
                        None
                    )
                    if draw_idx is None or draw_idx < 50:
                        continue
                    hist_up_to = all_draws_sorted[:draw_idx]
                    try:
                        bets_wrapped = biglotto_p1_deviation_5bet(hist_up_to)
                        bet_lists = [b['numbers'] for b in bets_wrapped]
                        actual = target_draw['numbers']
                        match_counts = [sum(1 for n in bet if n in actual) for bet in bet_lists]
                        best_match = max(match_counts) if match_counts else 0
                        extended.append({
                            'draw_id': str(target_draw['draw']),
                            'date': target_draw['date'],
                            'actual': actual,
                            'match_counts': match_counts,
                            'best_match': best_match,
                            'is_m3plus': best_match >= 3,
                            'is_m2plus': best_match >= 2,
                            'num_bets': len(bet_lists),
                        })
                    except Exception:
                        pass

            last_w = extended[-window:]
            hit_rate = sum(1 for r in last_w if r.get('is_m3plus')) / window
            rolling_edge = hit_rate - baseline
            src = 'rolling_monitor+fresh' if new_draws else 'rolling_monitor'
            return _edge_to_status(rolling_edge, extended, src)
    except Exception:
        pass

    # ── Priority 3: strategy_states edge_150p ──────────────────────────────
    try:
        if os.path.exists(states_path):
            states = json.load(open(states_path))
            p1_state = states.get('p1_dev_sum5bet', {})
            edge_150 = p1_state.get('edge_150p')
            if edge_150 is not None:
                rolling_edge = float(edge_150)
                is_cold = rolling_edge < 0
                _write_status({
                    'lottery': 'BIG_LOTTO',
                    'is_cold': is_cold,
                    'rolling_50p_edge': round(rolling_edge * 100, 2),
                    'cold_since_draw': None,
                    'consecutive_positive_windows': 0 if is_cold else 1,
                    'last_updated': datetime.now().strftime('%Y/%m/%d'),
                    'data_source': 'strategy_states_150p_estimate',
                    'note': 'estimated from 150p window, 50p data unavailable',
                })
                return is_cold, rolling_edge
    except Exception:
        pass

    # ── Priority 4: insufficient_data ──────────────────────────────────────
    _write_status({
        'lottery': 'BIG_LOTTO',
        'is_cold': False,
        'rolling_50p_edge': None,
        'cold_since_draw': None,
        'consecutive_positive_windows': 0,
        'last_updated': datetime.now().strftime('%Y/%m/%d'),
        'insufficient_data': True,
    })
    return False, 0.0



def predict_biglotto(history, rules, num_bets=5, use_coordinator=True, coord_mode='direct'):
    from tools.rsm_bootstrap import get_big_lotto_strategies_inline, DEPLOYED_STRATEGY_KEYS

    # 冷期偵測（警示層，不阻止預測）
    is_cold, cold_severity = _detect_cold_phase(history)
    if is_cold:
        print(f'\n  \033[91m\033[1m[COLD PHASE]\033[0m 近50期 edge={cold_severity * 100:+.2f}%，建議暫緩投注')
    else:
        # 冷期退出偵測
        try:
            status_path = os.path.join(project_root, 'data', 'cold_phase_status.json')
            _status = json.load(open(status_path))
            if _status.get('consecutive_positive_windows', 0) >= 2:
                print(f'\n  \033[92m\033[1m[COLD PHASE EXIT]\033[0m 連續2個50期窗口 edge>0，冷期已退出')
        except Exception:
            pass

    _fns = {c['name']: c['predict_func'] for c in get_big_lotto_strategies_inline()}
    strategy_key = DEPLOYED_STRATEGY_KEYS['BIG_LOTTO'].get(num_bets, 'p1_dev_sum5bet')
    raw = _fns[strategy_key](history)
    bets = [{'numbers': sorted(b)} for b in raw]
    return enforce_tail_diversity(bets, 2, 49, history), strategy_key

def predict_power(history, rules, num_bets=2, use_coordinator=True, coord_mode='direct'):
    sp = power_special_v3(history)[0]
    from tools.rsm_bootstrap import get_power_lotto_strategies_inline, DEPLOYED_STRATEGY_KEYS
    _fns = {c['name']: c['predict_func'] for c in get_power_lotto_strategies_inline()}
    if num_bets == 2 and use_coordinator:
        bets, desc = _coordinator_bets('POWER_LOTTO', history, 2, mode=coord_mode)
        if bets is not None:
            for b in bets: b['special'] = sp
            return enforce_tail_diversity(bets, 2, 38, history), desc
    strategy_key = DEPLOYED_STRATEGY_KEYS['POWER_LOTTO'].get(num_bets, 'orthogonal_5bet')
    raw = _fns[strategy_key](history)
    bets = [{'numbers': sorted(b)} for b in raw]
    for b in bets: b['special'] = sp
    return bets, strategy_key

def predict_539(history, rules, num_bets=3, use_coordinator=True, coord_mode='direct'):
    from tools.rsm_bootstrap import get_daily_539_strategies_inline, DEPLOYED_STRATEGY_KEYS
    _fns = {c['name']: c['predict_func'] for c in get_daily_539_strategies_inline()}
    if use_coordinator and num_bets in (2, 3):
        bets, desc = _coordinator_bets('DAILY_539', history, num_bets, mode=coord_mode)
        if bets is not None:
            return enforce_tail_diversity(bets, 2, 39, history), desc
    strategy_key = DEPLOYED_STRATEGY_KEYS['DAILY_539'].get(num_bets, 'acb_markov_midfreq_3bet')
    raw = _fns[strategy_key](history)
    bets = [{'numbers': sorted(b)} for b in raw]
    return bets, strategy_key

# ========== Main ==========

def get_next_draw_number(history):
    last = str(history[-1]['draw'])
    return last[:-3] + f"{int(last[-3:])+1:03d}"

def format_numbers(numbers): return ', '.join([f'{n:02d}' for n in sorted(numbers)])

def print_prediction(lottery_type, bets, strategy, history, num_bets):
    name = LOTTERY_NAMES.get(lottery_type, lottery_type)
    next_draw = get_next_draw_number(history)
    if strategy.startswith('Coordinator-'):
        verified_text = _coordinator_verified_text(lottery_type, num_bets)
    else:
        verified_text = STRATEGY_INFO.get(lottery_type, {}).get(num_bets, {}).get('verified', 'TBD')
    print(f"\n============================================================\n  {name} {next_draw} 期預測報告\n============================================================")
    print(f"  上期開獎: {history[-1]['draw']} - {format_numbers(history[-1]['numbers'])}")
    print(f"------------------------------------------------------------\n  預測號碼 ({num_bets}注):\n")
    for i, b in enumerate(bets, 1):
        print(f"  注{i}: {format_numbers(b['numbers'])}" + (f" | 特別號: {int(b['special']):02d}" if 'special' in b else ""))
    print(f"------------------------------------------------------------\n  策略: {strategy}\n  驗證: {verified_text}\n============================================================\n")


def _print_gate_summary(lottery_type):
    try:
        from tools.ev_gate import evaluate_jackpot_gate, format_gate_line, format_stage2_line

        gate = evaluate_jackpot_gate(lottery_type)
        print(f"  EV Gate: {format_gate_line(gate)}")
        print(f"  Stage2:  {format_stage2_line(gate)}")
        print(
            f"  Kelly:   fraction={gate.get('kelly_fraction', 0):.3f} "
            f"recommended_bets={gate.get('recommended_bet_count')} "
            f"after_gate={gate.get('n_bets_after_gate')}"
        )
    except Exception:
        pass

def _log_prediction_safe(lt, period, strat, nb, bets):
    """靜默呼叫 PredictionLogger，失敗不影響主流程"""
    try:
        from lottery_api.engine.prediction_logger import get_logger
        logger = get_logger()
        bet_lists = [b['numbers'] for b in bets]
        specials = [int(b['special']) for b in bets if 'special' in b] or None
        is_new = logger.log_prediction(lt, period, strat, nb, bet_lists, specials)
        if is_new:
            print(f"  [LOG] 預測已記錄 → {lt} {period} ({strat})")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('lottery', nargs='?', default='all')
    parser.add_argument('bets', nargs='?', type=int, default=None)
    parser.add_argument('--coord-mode', choices=['direct', 'hybrid'], default='direct',
                        help='Coordinator 模式 (僅 2注/3注生效)')
    parser.add_argument('--no-coordinator', action='store_true',
                        help='關閉 Coordinator，強制使用原單策略')
    args = parser.parse_args()
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    l_types = ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'] if args.lottery == 'all' else [LOTTERY_MAP.get(args.lottery.lower(), args.lottery.upper())]
    for lt in l_types:
        try:
            h = sorted(db.get_all_draws(lottery_type=lt), key=lambda x: (x['date'], x['draw']))
            if len(h) < 50: continue
            nb = args.bets or DEFAULT_CONFIG.get(lt, {}).get('bets', 3)
            use_coord = not args.no_coordinator
            if lt == 'BIG_LOTTO':
                bets, strat = predict_biglotto(h, {}, nb, use_coordinator=use_coord, coord_mode=args.coord_mode)
            elif lt == 'POWER_LOTTO':
                bets, strat = predict_power(h, {}, nb, use_coordinator=use_coord, coord_mode=args.coord_mode)
            else:
                bets, strat = predict_539(h, {}, nb, use_coordinator=use_coord, coord_mode=args.coord_mode)
            next_period = get_next_draw_number(h)
            print_prediction(lt, bets, strat, h, nb)
            # Track B: Player Behavior / Split-Risk Advisory
            try:
                from analysis.player_behavior import analyze_tickets
                from analysis.player_behavior.reporting import format_advisory_cli
                pb_result = analyze_tickets(bets, lt)
                if pb_result and pb_result.get('bets'):
                    print(format_advisory_cli(pb_result))
            except Exception:
                pass  # Advisory module failure never blocks prediction
            _print_gate_summary(lt)
            _log_prediction_safe(lt, next_period, strat, nb, bets)
        except Exception as e: print(f"Error {lt}: {e}"); import traceback; traceback.print_exc()

    # Phase 2: LLM 自動分析（非阻塞，失敗不影響預測輸出）
    try:
        from lottery_api.engine.llm_analyzer import LLMAnalyzer, _load_strategy_states
        analyzer = LLMAnalyzer()
        for lt in l_types:
            states = _load_strategy_states(lt)
            if states:
                result = analyzer.analyze_rsm(lt, states, trigger='auto')
                if result:
                    lt_name = {'BIG_LOTTO': '大樂透', 'POWER_LOTTO': '威力彩', 'DAILY_539': '今彩539'}.get(lt, lt)
                    print(f"\n[LLM/{analyzer.get_provider()}] {lt_name}: {result.splitlines()[0]}")
    except Exception:
        pass

if __name__ == '__main__':
    main()
