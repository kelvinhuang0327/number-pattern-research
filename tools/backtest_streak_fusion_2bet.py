#!/usr/bin/env python3
"""
回測: Streak Boost + 多窗口Fusion 2注系統
策略設計:
  注1: 鄰域池(±1) + Streak Boost (5期連勝加分) Top-6
  注2: 多窗口Fusion (5期×0.5 + 20期×0.3 + 50期×0.2) + Zone Constraint Top-6

修正項目:
  - Streak Boost 解決 #22 類型連勝遺漏
  - 多窗口Fusion 解決 #47 類型短週期熱號遺漏
  - Zone Constraint (Z3>=3 後限制Z3最多2個)
  - Sum公式修正: 偏高時目標 [mu-0.5σ, mu+0.5σ]

標準回測: 150/500/1500期三窗口 + permutation test (1000次)
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
RANDOM_SEED = 42

# 基準 M3+命中率 (隨機2注)
BASELINE_2BET = 3.69  # %


def zone_of(n):
    if n <= 17: return 1
    elif n <= 33: return 2
    return 3


def streak_boost_neighbor_bet1(history, streak_window=5, streak_weight=0.4):
    """
    注1: 鄰域池(±1 of prev) + Streak Boost
    Streak Boost: 近streak_window期出現次數 × streak_weight 加入綜合得分
    Fourier(500期) + 0.5×Markov(30期) + streak_weight×Streak(5期)
    """
    prev_nums = history[-1]['numbers']

    # 鄰域池 ±1
    neighbor_pool = set()
    for n in prev_nums:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= MAX_NUM:
                neighbor_pool.add(nn)

    # Fourier (500期)
    h_slice = history[-500:] if len(history) >= 500 else history
    w = len(h_slice)
    f_scores = {}
    for num in range(1, MAX_NUM + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h_slice):
            if num in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            f_scores[num] = 0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            f_scores[num] = 0
            continue
        period = 1 / freq_val
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            f_scores[num] = 1.0 / (abs(gap - period) + 1.0)
        else:
            f_scores[num] = 0

    # Markov (30期)
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

    # Streak (近5期出現次數)
    streak_slice = history[-streak_window:] if len(history) >= streak_window else history
    streak_cnt = Counter(n for d in streak_slice for n in d['numbers'])

    # 綜合得分
    f_max = max(f_scores.values()) or 1
    mk_max = max(mk_scores.values()) or 1
    streak_max = max(streak_cnt.values()) or 1

    scored = {
        n: (f_scores.get(n, 0) / f_max
            + 0.5 * (mk_scores.get(n, 0) / mk_max)
            + streak_weight * (streak_cnt.get(n, 0) / streak_max))
        for n in neighbor_pool
    }
    ranked = sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)
    return sorted(ranked[:PICK])


def multi_window_zone_bet2(history, used=None, zone_max=2):
    """
    注2: 多窗口Fusion + Zone Constraint
    Hot score = 5期×0.5 + 20期×0.3 + 50期×0.2 (相對頻率)
    Zone Constraint: 若前期Z3>=3，則Z3號碼最多zone_max個
    """
    used = used or set()
    prev_nums = history[-1]['numbers']

    # 判斷前期Zone偏移
    prev_z3 = sum(1 for n in prev_nums if zone_of(n) == 3)
    apply_zone_constraint = (prev_z3 >= 3)

    # 多窗口熱度
    def hot_score(num, hist):
        w5  = hist[-5:]  if len(hist) >= 5  else hist
        w20 = hist[-20:] if len(hist) >= 20 else hist
        w50 = hist[-50:] if len(hist) >= 50 else hist
        cnt5  = sum(1 for d in w5  if num in d['numbers'])
        cnt20 = sum(1 for d in w20 if num in d['numbers'])
        cnt50 = sum(1 for d in w50 if num in d['numbers'])
        # 期望頻率歸一化
        e5, e20, e50 = 5*PICK/MAX_NUM, 20*PICK/MAX_NUM, 50*PICK/MAX_NUM
        return 0.5*(cnt5/e5) + 0.3*(cnt20/e20) + 0.2*(cnt50/e50)

    candidates = [n for n in range(1, MAX_NUM + 1) if n not in used]
    scored = {n: hot_score(n, history) for n in candidates}
    ranked = sorted(candidates, key=lambda n: scored[n], reverse=True)

    if apply_zone_constraint:
        # Zone Constraint: Z3 最多 zone_max 個
        bet2 = []
        z3_count = 0
        for n in ranked:
            if len(bet2) == PICK:
                break
            if zone_of(n) == 3:
                if z3_count < zone_max:
                    bet2.append(n)
                    z3_count += 1
            else:
                bet2.append(n)
    else:
        bet2 = ranked[:PICK]

    return sorted(bet2[:PICK])


def predict_2bet(history):
    """2注策略: 注1=Streak Boost鄰域 / 注2=多窗口Fusion+Zone"""
    bet1 = streak_boost_neighbor_bet1(history)
    used1 = set(bet1)
    bet2 = multi_window_zone_bet2(history, used=used1)
    return [bet1, bet2]


def match3_plus(predicted, actual):
    """是否 M3+（命中3個以上）"""
    return len(set(predicted) & set(actual)) >= 3


def edge_rate(hits, n):
    """Edge = 命中率 - 隨機基準 (M3+ 2注)"""
    return (hits / n * 100) - BASELINE_2BET if n > 0 else 0


def run_window_backtest(history, window):
    """單窗口回測"""
    if len(history) < window + 1:
        return None
    test_data = history[-(window + 1):]
    hits = 0
    for i in range(len(test_data) - 1):
        train = test_data[:i + 1]
        if len(train) < 50:
            continue
        actual = test_data[i + 1]['numbers']
        bets = predict_2bet(train)
        if any(match3_plus(b, actual) for b in bets):
            hits += 1
    total = window - sum(1 for i in range(len(test_data) - 1) if len(test_data[:i+1]) < 50)
    return hits, total, edge_rate(hits, total)


def permutation_test(history, window=1500, n_perm=1000, seed=RANDOM_SEED):
    """Permutation test: 策略 Edge vs 隨機 shuffle"""
    rng = np.random.RandomState(seed)
    test_data = history[-(window + 1):]

    # 真實策略命中
    real_hits = 0
    valid_n = 0
    for i in range(len(test_data) - 1):
        train = test_data[:i + 1]
        if len(train) < 50:
            continue
        actual = test_data[i + 1]['numbers']
        bets = predict_2bet(train)
        if any(match3_plus(b, actual) for b in bets):
            real_hits += 1
        valid_n += 1

    real_rate = real_hits / valid_n * 100 if valid_n > 0 else 0

    # 隨機基準
    perm_rates = []
    for _ in range(n_perm):
        perm_hits = 0
        for i in range(len(test_data) - 1):
            train = test_data[:i + 1]
            if len(train) < 50:
                continue
            actual = test_data[i + 1]['numbers']
            # 隨機2注
            rand_bets = [sorted(rng.choice(MAX_NUM, PICK, replace=False) + 1) for _ in range(2)]
            if any(match3_plus(b, actual) for b in rand_bets):
                perm_hits += 1
        perm_rates.append(perm_hits / valid_n * 100 if valid_n > 0 else 0)

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates)
    z = (real_rate - perm_mean) / (perm_std + 1e-10)
    p_val = np.mean([r >= real_rate for r in perm_rates])

    return {
        'real_rate': real_rate,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'z': z,
        'p_value': p_val,
        'real_hits': real_hits,
        'valid_n': valid_n,
    }


def main():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    history = sorted(history, key=lambda x: (x['date'], x['draw']))

    print('=' * 65)
    print('  大樂透 Streak Boost + 多窗口Fusion 2注系統 回測')
    print('  注1: 鄰域±1 + Streak Boost (5期連勝加分)')
    print('  注2: 多窗口Fusion (5×0.5+20×0.3+50×0.2) + Zone Constraint')
    print('=' * 65)
    print(f'  資料總期數: {len(history)} 期')
    print(f'  隨機基準 (2注 M3+): {BASELINE_2BET:.2f}%')
    print()

    # 三窗口回測
    results = {}
    for window in [150, 500, 1500]:
        print(f'  回測 {window} 期...', end='', flush=True)
        r = run_window_backtest(history, window)
        if r:
            hits, total, edge = r
            results[window] = {'hits': hits, 'total': total, 'rate': hits/total*100, 'edge': edge}
            sign = '+' if edge >= 0 else ''
            print(f'  {hits}/{total} = {hits/total*100:.2f}% | Edge {sign}{edge:.2f}%')
        else:
            print('  資料不足')

    print()
    # 三窗口一致性
    all_positive = all(results[w]['edge'] > 0 for w in [150, 500, 1500] if w in results)
    print(f'  三窗口全正: {"✅ YES" if all_positive else "❌ NO"}')

    # Permutation test (1500期)
    print()
    print('  Permutation test (1500期, 1000次)...', flush=True)
    perm = permutation_test(history, window=1500, n_perm=1000)
    print(f'  真實命中率: {perm["real_rate"]:.2f}% ({perm["real_hits"]}/{perm["valid_n"]})')
    print(f'  隨機均值:   {perm["perm_mean"]:.2f}% ± {perm["perm_std"]:.2f}%')
    print(f'  z-score:    {perm["z"]:.2f}')
    print(f'  p-value:    {perm["p_value"]:.4f}', end='  ')
    if perm['p_value'] <= 0.05:
        print('✅ SIGNAL DETECTED')
    elif perm['p_value'] <= 0.10:
        print('⚠️  MARGINAL')
    else:
        print('❌ NOT SIGNIFICANT')

    # Sharpe Ratio (用1500期)
    print()
    if 1500 in results:
        sharpe_approx = perm['z']
        print(f'  Sharpe Ratio (z-score proxy): {sharpe_approx:.2f}', end='  ')
        print('✅ > 0' if sharpe_approx > 0 else '❌ ≤ 0')

    # 判定
    print()
    print('=' * 65)
    edge_1500 = results.get(1500, {}).get('edge', -999)
    verdict = '✅ PASS — 建議採納' if (all_positive and perm['p_value'] <= 0.10 and edge_1500 > 0) else \
              '⚠️  MARGINAL — 需持續監控' if (edge_1500 > 0 and perm['p_value'] <= 0.15) else \
              '❌ REJECT'
    print(f'  最終判定: {verdict}')
    print('=' * 65)

    # 輸出結果 JSON
    import json
    output = {
        'strategy': 'streak_boost_fusion_2bet',
        'description': '注1:鄰域+StreakBoost / 注2:多窗口Fusion+ZoneConstraint',
        'windows': {str(w): {'hits': v['hits'], 'total': v['total'],
                              'rate': round(v['rate'], 4), 'edge': round(v['edge'], 4)}
                    for w, v in results.items()},
        'permutation': {k: round(v, 6) if isinstance(v, float) else v for k, v in perm.items()},
        'all_windows_positive': all_positive,
        'verdict': verdict,
        'baseline_2bet': BASELINE_2BET,
    }
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'backtest_streak_fusion_2bet_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'  結果已保存: {out_path}')


if __name__ == '__main__':
    main()
