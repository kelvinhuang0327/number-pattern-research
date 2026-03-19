#!/usr/bin/env python3
"""
並行雙注架構回測
============================================================
核心理念: 每注完全獨立，不共享 used 排除集

注A (獨立短期熱號):
  多窗口Fusion熱度: 5期×0.5 + 20期×0.3 + 50期×0.2
  純熱號 Top-6 (不排除任何號碼)
  目標: 捕捉 #22/#47 類型短期動量信號

注B (獨立鄰域+Sum修正冷號):
  注1 = 鄰域±1 Fourier+Markov Top-6
  注2 = Sum修正冷號 [mu-0.5σ, mu+0.5σ]
  純D方案，完全獨立，不看注A選了什麼

對照:
  - 單注A (純熱號)
  - 單注B1 (純鄰域)
  - 單注B2 (純冷號)
  - 舊串行2注 (注1鄰域→排除→注2冷號) — 基準 D方案
  - 新並行2注 (注A+注B1 or 注A+注B2)
  - 最優2注組合搜索

標準: 1500期三窗口 + permutation test (1000次)
"""
import sys, os
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter, defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from database import DatabaseManager

MAX_NUM = 49
PICK = 6
BASELINE_1BET = 1.86   # M3+ 單注隨機基準
BASELINE_2BET = 3.69   # M3+ 2注隨機基準
RANDOM_SEED = 42


# =========================================================
# 基礎選號函數 (全部獨立，不接受 used 參數)
# =========================================================

def bet_short_hot(history):
    """
    短期熱號注: 多窗口Fusion Top-6
    5期×0.5 + 20期×0.3 + 50期×0.2 (相對頻率)
    完全獨立 — 不排除任何號碼
    """
    w5  = history[-5:]  if len(history) >= 5  else history
    w20 = history[-20:] if len(history) >= 20 else history
    w50 = history[-50:] if len(history) >= 50 else history
    e5   = len(w5)  * PICK / MAX_NUM
    e20  = len(w20) * PICK / MAX_NUM
    e50  = len(w50) * PICK / MAX_NUM

    scored = {}
    for num in range(1, MAX_NUM + 1):
        c5  = sum(1 for d in w5  if num in d['numbers'])
        c20 = sum(1 for d in w20 if num in d['numbers'])
        c50 = sum(1 for d in w50 if num in d['numbers'])
        scored[num] = 0.5*(c5/e5) + 0.3*(c20/e20) + 0.2*(c50/e50)

    ranked = sorted(range(1, MAX_NUM+1), key=lambda n: scored[n], reverse=True)
    return sorted(ranked[:PICK])


def bet_neighbor_fourier(history):
    """
    鄰域注: ±1 Fourier+Markov Top-6
    完全獨立 — 不排除任何號碼
    """
    prev_nums = history[-1]['numbers']
    neighbor_pool = set()
    for n in prev_nums:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbor_pool.add(nn)

    h_slice = history[-500:] if len(history) >= 500 else history
    w = len(h_slice)
    f_scores = {}
    for num in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, dd in enumerate(h_slice):
            if num in dd['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            f_scores[num] = 0; continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            f_scores[num] = 0; continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            f_scores[num] = 1.0 / (abs(gap - period) + 1.0)
        else:
            f_scores[num] = 0

    mk_window = min(30, len(history) - 1)
    recent_mk = history[-mk_window:]
    transitions = defaultdict(Counter)
    for i in range(len(recent_mk) - 1):
        for cn in recent_mk[i]['numbers']:
            for nn in recent_mk[i + 1]['numbers']:
                transitions[cn][nn] += 1
    mk_scores = Counter()
    for pn in prev_nums:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                mk_scores[n] += cnt / total

    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_scores.values()) or 1
    scored = {n: (f_scores.get(n,0)/f_max + 0.5*(mk_scores.get(n,0)/mk_max))
              for n in neighbor_pool}
    ranked = sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)
    return sorted(ranked[:PICK])


def bet_cold_sum_fixed(history, exclude=None):
    """
    Sum修正冷號注: 統一目標 [mu-0.5σ, mu+0.5σ]
    exclude: 可選排除集（用於串行模式對比）
    """
    exclude = exclude or set()
    candidates = [n for n in range(1, MAX_NUM+1) if n not in exclude]
    freq = Counter(n for d in history[-100:] for n in d['numbers'])
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    pool = sorted_cold[:12]

    sums = [sum(d['numbers']) for d in history[-300:]]
    mu, sg = np.mean(sums), np.std(sums)
    tlo, thi = mu - 0.5*sg, mu + 0.5*sg
    tmid = mu

    best_combo, best_dist, best_in_range = None, float('inf'), False
    for combo in combinations(pool, 6):
        s = sum(combo)
        in_range = (tlo <= s <= thi)
        dist = abs(s - tmid)
        if in_range and (not best_in_range or dist < best_dist):
            best_combo, best_dist, best_in_range = combo, dist, True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo, best_dist = combo, dist
    return sorted(best_combo if best_combo else pool[:6])


# =========================================================
# 組合策略定義
# =========================================================

def strat_serial_D(hist):
    """串行 D 方案 (現有系統): 注1鄰域 → 排除 → 注2冷號"""
    b1 = bet_neighbor_fourier(hist)
    b2 = bet_cold_sum_fixed(hist, exclude=set(b1))
    return [b1, b2]

def strat_parallel_hot_neighbor(hist):
    """並行 A: 熱號注 + 鄰域注 (各自獨立)"""
    ba = bet_short_hot(hist)
    bb = bet_neighbor_fourier(hist)
    return [ba, bb]

def strat_parallel_hot_cold(hist):
    """並行 B: 熱號注 + 冷號注 (各自獨立，冷號不排除熱號)"""
    ba = bet_short_hot(hist)
    bb = bet_cold_sum_fixed(hist, exclude=set())
    return [ba, bb]

def strat_single_hot(hist):
    """單注: 純短期熱號"""
    return [bet_short_hot(hist)]

def strat_single_neighbor(hist):
    """單注: 純鄰域"""
    return [bet_neighbor_fourier(hist)]

def strat_single_cold(hist):
    """單注: 純冷號 (Sum修正)"""
    return [bet_cold_sum_fixed(hist)]


# =========================================================
# 回測引擎
# =========================================================

def match3p(pred, actual):
    return len(set(pred) & set(actual)) >= 3

def run_window(history, strat_fn, window):
    test = history[-(window+1):]
    hits, total = 0, 0
    for i in range(len(test)-1):
        train = test[:i+1]
        if len(train) < 50: continue
        actual = test[i+1]['numbers']
        bets = strat_fn(train)
        if any(match3p(b, actual) for b in bets):
            hits += 1
        total += 1
    n_bets = len(strat_fn(history[-51:]))
    baseline = BASELINE_2BET if n_bets >= 2 else BASELINE_1BET
    edge = (hits/total*100 - baseline) if total > 0 else 0
    return hits, total, hits/total*100 if total > 0 else 0, edge

def permutation_test(history, strat_fn, window=1500, n_perm=1000):
    rng = np.random.RandomState(RANDOM_SEED)
    test = history[-(window+1):]
    n_bets = len(strat_fn(history[-51:]))
    baseline = BASELINE_2BET if n_bets >= 2 else BASELINE_1BET

    real_hits, valid_n = 0, 0
    for i in range(len(test)-1):
        train = test[:i+1]
        if len(train) < 50: continue
        actual = test[i+1]['numbers']
        if any(match3p(b, actual) for b in strat_fn(train)):
            real_hits += 1
        valid_n += 1
    real_rate = real_hits/valid_n*100

    perm_rates = []
    for _ in range(n_perm):
        ph = 0
        for i in range(len(test)-1):
            train = test[:i+1]
            if len(train) < 50: continue
            actual = test[i+1]['numbers']
            rand_bets = [sorted((rng.choice(MAX_NUM, PICK, replace=False)+1).tolist())
                         for _ in range(n_bets)]
            if any(match3p(b, actual) for b in rand_bets):
                ph += 1
        perm_rates.append(ph/valid_n*100)

    pm, ps = np.mean(perm_rates), np.std(perm_rates)
    z = (real_rate - pm) / (ps + 1e-10)
    pv = np.mean([r >= real_rate for r in perm_rates])
    return real_hits, valid_n, real_rate, pm, ps, z, pv, baseline


def main():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    history = sorted(history, key=lambda x: (x['date'], x['draw']))

    print('=' * 68)
    print('  大樂透 並行雙注架構研究')
    print('  理念: 每注完全獨立，不共享排除集，消除交互抵消')
    print('=' * 68)
    print(f'  資料: {len(history)} 期  |  1注基準: {BASELINE_1BET}%  |  2注基準: {BASELINE_2BET}%')
    print()

    strategies = {
        '單注A: 短期熱號(5/20/50期Fusion)': strat_single_hot,
        '單注B1: 鄰域Fourier+Markov':        strat_single_neighbor,
        '單注B2: 冷號Sum修正':                strat_single_cold,
        '串行2注 [基準D]: 鄰域→排除→冷號':   strat_serial_D,
        '並行2注 [熱號+鄰域]: 各自獨立':      strat_parallel_hot_neighbor,
        '並行2注 [熱號+冷號]: 各自獨立':      strat_parallel_hot_cold,
    }

    print(f'  {"策略":<38}  {"150p":>7}  {"500p":>7}  {"1500p":>7}  {"全正"}')
    print('  ' + '-' * 64)
    results = {}
    for name, fn in strategies.items():
        row = []
        for w in [150, 500, 1500]:
            h, t, rate, edge = run_window(history, fn, w)
            row.append((h, t, rate, edge))
        results[name] = row
        e150, e500, e1500 = row[0][3], row[1][3], row[2][3]
        all_pos = '✅' if all(e > 0 for e in [e150, e500, e1500]) else '❌'
        print(f'  {name:<38}  {e150:+6.2f}%  {e500:+6.2f}%  {e1500:+6.2f}%  {all_pos}')

    # ===== Permutation test on top candidates =====
    print()
    print('=' * 68)
    print('  Permutation Test (1500期, 1000次)')
    print('=' * 68)

    # 過濾三窗口全正的策略進行 perm test
    perm_targets = {k: v for k, v in strategies.items()
                    if all(results[k][i][3] > 0 for i in range(3))}
    # 總是包含基準D
    perm_targets['串行2注 [基準D]: 鄰域→排除→冷號'] = strat_serial_D

    perm_results = {}
    for name, fn in perm_targets.items():
        print(f'\n  {name}')
        print('  計算中...', end='', flush=True)
        hits, n, rr, pm, ps, z, pv, bl = permutation_test(history, fn)
        edge = rr - bl
        perm_results[name] = (hits, n, rr, pm, ps, z, pv, bl, edge)
        sig = '✅ SIGNAL' if pv<=0.05 else '⚠️ MARGINAL' if pv<=0.10 else '❌ N/S'
        print(f'  命中率={rr:.2f}% ({hits}/{n}) Edge={edge:+.2f}%')
        print(f'  z={z:.2f} p={pv:.4f} {sig}  |  random均值={pm:.2f}%±{ps:.2f}%')

    # ===== 最終排名 =====
    print()
    print('=' * 68)
    print('  最終排名 (1500期 Edge, perm通過的策略)')
    print('=' * 68)
    ranked = sorted(perm_results.items(),
                    key=lambda x: x[1][8], reverse=True)  # sort by edge
    for rank, (name, (hits, n, rr, pm, ps, z, pv, bl, edge)) in enumerate(ranked, 1):
        sig = '✅' if pv<=0.05 else '⚠️' if pv<=0.10 else '❌'
        print(f'  #{rank} {sig} {name}')
        print(f'     Edge={edge:+.2f}% | z={z:.2f} | p={pv:.4f}')

    # ===== 儲存結果 =====
    import json
    output = {
        'windows': {
            name: {str(w): {'edge': round(results[name][i][3], 4)}
                   for i, w in enumerate([150, 500, 1500])}
            for name in strategies
        },
        'permutation': {
            name: {'edge': round(v[8], 4), 'z': round(v[5], 4),
                   'p_value': round(v[6], 4), 'hits': v[0], 'n': v[1]}
            for name, v in perm_results.items()
        }
    }
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'backtest_parallel_2bet_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n  結果已保存: {out_path}')


if __name__ == '__main__':
    main()
