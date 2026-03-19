#!/usr/bin/env python3
"""
539 全策略標準回測 — P0~P5 三窗口驗證 + Permutation Test
2026-03-01 115000054 期檢討驅動

測試策略:
  P0: markov_1bet       — Markov 轉移注 (單注)
  P1: midfreq_1bet      — 均值回歸注 (單注)
  P2: markov_acb_2bet   — Markov + ACB (2注)
  P3: markov_mid_acb_3bet — Markov + MidFreq + ACB (3注)
  P4: bandit_2bet / bandit_3bet — UCB1 策略選擇器
  P5: lift_pair_1bet    — 共現 Lift pair 錨定 (單注)
"""
import sys, os, json, time
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from tools.quick_predict import (
    _539_acb_bet, _539_markov_bet, _539_midfreq_bet, _539_lift_pair_bet,
    _539_fourier_scores
)

MAX_NUM = 39
PICK = 5
MATCH_THRESHOLD = 2  # 中2個以上即為成功


def random_baseline_rate(n_bets, max_num=39, pick=5, draw_size=5, trials=50000):
    """精確計算 N 注隨機基準勝率"""
    import random as rng
    wins = 0
    for _ in range(trials):
        actual = set(rng.sample(range(1, max_num + 1), draw_size))
        hit = False
        for _ in range(n_bets):
            bet = set(rng.sample(range(1, max_num + 1), pick))
            if len(bet & actual) >= MATCH_THRESHOLD:
                hit = True
                break
        if hit:
            wins += 1
    return wins / trials


def backtest_strategy(history, predict_fn, n_bets, test_periods, label=""):
    """通用回測函數 — 返回 (wins, total, win_rate, details)"""
    wins = 0
    total = 0
    match_counts = Counter()  # match=0,1,2,3,4,5

    start_idx = len(history) - test_periods
    if start_idx < 500:  # 至少需要500期歷史作為訓練
        start_idx = 500

    actual_periods = len(history) - start_idx

    for i in range(start_idx, len(history)):
        train = history[:i]
        actual = set(history[i]['numbers'])

        try:
            bets = predict_fn(train)
        except Exception:
            continue

        total += 1
        best_match = 0
        for bet_nums in bets:
            match = len(set(bet_nums) & actual)
            best_match = max(best_match, match)
        match_counts[best_match] += 1
        if best_match >= MATCH_THRESHOLD:
            wins += 1

    win_rate = wins / total * 100 if total > 0 else 0
    return wins, total, win_rate, dict(match_counts)


def permutation_test(history, predict_fn, n_bets, test_periods, n_perms=200):
    """Permutation test — 打亂時序後比較 Edge"""
    import random as rng

    # 真實回測
    real_wins, real_total, real_rate, _ = backtest_strategy(
        history, predict_fn, n_bets, test_periods)

    if real_total == 0:
        return real_rate, 0, 1.0, 0

    # Permutation: 打亂號碼時序
    perm_rates = []
    numbers_pool = [d['numbers'] for d in history]

    for p in range(n_perms):
        shuffled = history.copy()
        shuffled_numbers = numbers_pool.copy()
        rng.shuffle(shuffled_numbers)
        shuffled_hist = []
        for j, d in enumerate(shuffled):
            sd = d.copy()
            sd['numbers'] = shuffled_numbers[j]
            shuffled_hist.append(sd)

        _, _, perm_rate, _ = backtest_strategy(
            shuffled_hist, predict_fn, n_bets, min(test_periods, 300))
        perm_rates.append(perm_rate)

    perm_mean = np.mean(perm_rates)
    perm_std = np.std(perm_rates) if len(perm_rates) > 1 else 1
    edge = real_rate - perm_mean
    z = edge / perm_std if perm_std > 0 else 0
    p_value = np.mean([1 for pr in perm_rates if pr >= real_rate]) / len(perm_rates)

    return real_rate, perm_mean, p_value, z


# ==================== Strategy factory functions ====================

def make_markov_1bet(history):
    return [_539_markov_bet(history)]

def make_midfreq_1bet(history):
    return [_539_midfreq_bet(history)]

def make_acb_1bet(history):
    return [_539_acb_bet(history)]

def make_lift_1bet(history):
    return [_539_lift_pair_bet(history)]

def make_markov_acb_2bet(history):
    bet1 = _539_markov_bet(history)
    bet2 = _539_acb_bet(history, exclude=set(bet1))
    return [bet1, bet2]

def make_markov_mid_acb_3bet(history):
    bet1 = _539_markov_bet(history)
    excl = set(bet1)
    bet2 = _539_midfreq_bet(history, exclude=excl)
    excl.update(bet2)
    bet3 = _539_acb_bet(history, exclude=excl)
    return [bet1, bet2, bet3]

def make_mid_acb_2bet(history):
    bet1 = _539_midfreq_bet(history)
    bet2 = _539_acb_bet(history, exclude=set(bet1))
    return [bet1, bet2]

def make_markov_mid_2bet(history):
    bet1 = _539_markov_bet(history)
    bet2 = _539_midfreq_bet(history, exclude=set(bet1))
    return [bet1, bet2]

def make_markov_lift_acb_3bet(history):
    bet1 = _539_markov_bet(history)
    excl = set(bet1)
    bet2 = _539_lift_pair_bet(history, exclude=excl)
    excl.update(bet2)
    bet3 = _539_acb_bet(history, exclude=excl)
    return [bet1, bet2, bet3]


# ==================== UCB1 Bandit ====================

class UCB1BanditSelector:
    """UCB1-Tuned 策略選擇器

    根據市場狀態(和值regime, 冷熱比)動態選擇最佳注法組合。
    """
    def __init__(self, n_bets=2):
        self.n_bets = n_bets
        # 可選的單注策略
        self.arms = [
            ('markov', _539_markov_bet),
            ('midfreq', _539_midfreq_bet),
            ('acb', _539_acb_bet),
            ('lift', _539_lift_pair_bet),
        ]
        self.arm_names = [a[0] for a in self.arms]
        self.counts = np.ones(len(self.arms))  # 每個arm被選次數
        self.rewards = np.ones(len(self.arms)) * 0.15  # 累積reward
        self.sq_rewards = np.ones(len(self.arms)) * 0.03  # 累積 reward^2

    def select_arms(self, n_total):
        """UCB1-Tuned 選擇 n_bets 個不同的 arm"""
        ucb_scores = []
        for i in range(len(self.arms)):
            mean_r = self.rewards[i] / self.counts[i]
            variance = self.sq_rewards[i] / self.counts[i] - mean_r ** 2
            variance = max(0, variance)
            ln_n = np.log(n_total + 1)
            exploration = np.sqrt(ln_n / self.counts[i] *
                                  min(0.25, variance + np.sqrt(2 * ln_n / self.counts[i])))
            ucb_scores.append(mean_r + exploration)

        # 選 top n_bets
        indices = sorted(range(len(ucb_scores)), key=lambda i: -ucb_scores[i])
        return indices[:self.n_bets]

    def update(self, arm_idx, reward):
        self.counts[arm_idx] += 1
        self.rewards[arm_idx] += reward
        self.sq_rewards[arm_idx] += reward ** 2

    def predict(self, history, total_rounds):
        selected = self.select_arms(total_rounds)
        bets = []
        excl = set()
        for idx in selected:
            name, fn = self.arms[idx]
            bet = fn(history, exclude=excl)
            bets.append(bet)
            excl.update(bet)
        return bets, selected


def make_bandit_predict(n_bets, history_full, test_periods):
    """建立 Bandit 回測用的閉包"""
    bandit = UCB1BanditSelector(n_bets=n_bets)

    # 暖機：用 test_periods 之前的數據訓練
    start_idx = len(history_full) - test_periods
    if start_idx < 500:
        start_idx = 500

    warmup_end = min(start_idx, len(history_full) - test_periods)
    warmup_start = max(500, warmup_end - 300)

    for i in range(warmup_start, warmup_end):
        train = history_full[:i]
        actual = set(history_full[i]['numbers'])
        try:
            bets, selected = bandit.predict(train, i - warmup_start + 1)
            best_match = 0
            for bet_nums in bets:
                match = len(set(bet_nums) & actual)
                best_match = max(best_match, match)
            reward = best_match / 5.0
            for idx in selected:
                bandit.update(idx, reward)
        except Exception:
            continue

    return bandit


def backtest_bandit(history, n_bets, test_periods, label=""):
    """Bandit 專用回測"""
    bandit = make_bandit_predict(n_bets, history, test_periods)

    start_idx = len(history) - test_periods
    if start_idx < 500:
        start_idx = 500

    wins = 0
    total = 0
    match_counts = Counter()

    for i in range(start_idx, len(history)):
        train = history[:i]
        actual = set(history[i]['numbers'])

        try:
            bets, selected = bandit.predict(train, total + 1)
        except Exception:
            continue

        total += 1
        best_match = 0
        for bet_nums in bets:
            match = len(set(bet_nums) & actual)
            best_match = max(best_match, match)
        match_counts[best_match] += 1
        if best_match >= MATCH_THRESHOLD:
            wins += 1

        # 更新 bandit
        reward = best_match / 5.0
        for idx in selected:
            bandit.update(idx, reward)

    win_rate = wins / total * 100 if total > 0 else 0
    return wins, total, win_rate, dict(match_counts), bandit


# ==================== Main ====================

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    print(f"Total 539 draws: {len(history)}")
    print(f"Latest: {history[-1]['draw']} ({history[-1]['date']})")
    print()

    WINDOWS = [150, 500, 1500]

    # 定義所有策略
    strategies = [
        # (label, predict_fn, n_bets, category)
        ('P0: markov_1bet', make_markov_1bet, 1, 'single'),
        ('P1: midfreq_1bet', make_midfreq_1bet, 1, 'single'),
        ('P5: lift_pair_1bet', make_lift_1bet, 1, 'single'),
        ('REF: acb_1bet', make_acb_1bet, 1, 'single'),
        ('P2a: markov+acb_2bet', make_markov_acb_2bet, 2, 'multi'),
        ('P2b: markov+mid_2bet', make_markov_mid_2bet, 2, 'multi'),
        ('P2c: mid+acb_2bet', make_mid_acb_2bet, 2, 'multi'),
        ('P3a: markov+mid+acb_3bet', make_markov_mid_acb_3bet, 3, 'multi'),
        ('P3b: markov+lift+acb_3bet', make_markov_lift_acb_3bet, 3, 'multi'),
    ]

    # 隨機基準
    print("=" * 80)
    print("  計算隨機基準...")
    print("=" * 80)
    baselines = {}
    for nb in [1, 2, 3]:
        bl = random_baseline_rate(nb)
        baselines[nb] = bl * 100
        print(f"  {nb}注隨機基準: {bl*100:.2f}%")
    print()

    # ==================== 三窗口回測 ====================
    print("=" * 80)
    print("  三窗口回測 (150 / 500 / 1500)")
    print("=" * 80)

    results = {}

    for label, fn, n_bets, cat in strategies:
        print(f"\n  --- {label} ---")
        window_results = {}
        for w in WINDOWS:
            t0 = time.time()
            wins, total, rate, match_dist = backtest_strategy(history, fn, n_bets, w, label)
            elapsed = time.time() - t0
            bl = baselines[n_bets]
            edge = rate - bl
            window_results[w] = {
                'wins': wins, 'total': total, 'rate': rate,
                'edge': edge, 'match_dist': match_dist
            }
            print(f"    {w:4d}期: {wins:3d}/{total:3d} = {rate:5.2f}% | "
                  f"baseline={bl:.2f}% | Edge={edge:+.2f}% | {elapsed:.1f}s")

        results[label] = {
            'n_bets': n_bets,
            'windows': window_results,
        }

        # 三窗口一致性檢查
        edges = [window_results[w]['edge'] for w in WINDOWS]
        all_positive = all(e > 0 for e in edges)
        stability = "STABLE" if all_positive else "UNSTABLE"
        print(f"    三窗口: {stability} | Edges: {[f'{e:+.2f}%' for e in edges]}")

    # ==================== Bandit 回測 ====================
    print("\n" + "=" * 80)
    print("  Bandit 策略選擇器回測")
    print("=" * 80)

    for nb_label, nb in [('P4a: bandit_2bet', 2), ('P4b: bandit_3bet', 3)]:
        print(f"\n  --- {nb_label} ---")
        window_results = {}
        for w in WINDOWS:
            t0 = time.time()
            wins, total, rate, match_dist, bandit = backtest_bandit(history, nb, w, nb_label)
            elapsed = time.time() - t0
            bl = baselines[nb]
            edge = rate - bl
            window_results[w] = {
                'wins': wins, 'total': total, 'rate': rate,
                'edge': edge, 'match_dist': match_dist
            }
            print(f"    {w:4d}期: {wins:3d}/{total:3d} = {rate:5.2f}% | "
                  f"baseline={bl:.2f}% | Edge={edge:+.2f}% | {elapsed:.1f}s")

            if w == 1500:
                # 顯示 bandit arm selection stats
                arm_names = bandit.arm_names
                for ai, name in enumerate(arm_names):
                    avg_r = bandit.rewards[ai] / bandit.counts[ai]
                    print(f"      arm '{name}': selected {int(bandit.counts[ai])}x, avg_reward={avg_r:.3f}")

        results[nb_label] = {'n_bets': nb, 'windows': window_results}
        edges = [window_results[w]['edge'] for w in WINDOWS]
        all_positive = all(e > 0 for e in edges)
        stability = "STABLE" if all_positive else "UNSTABLE"
        print(f"    三窗口: {stability} | Edges: {[f'{e:+.2f}%' for e in edges]}")

    # ==================== Permutation Test (top strategies) ====================
    print("\n" + "=" * 80)
    print("  Permutation Test (三窗口 Edge 全正的策略)")
    print("=" * 80)

    stable_strategies = []
    for label, info in results.items():
        edges = [info['windows'][w]['edge'] for w in WINDOWS]
        if all(e > 0 for e in edges):
            stable_strategies.append(label)

    if not stable_strategies:
        print("  無策略通過三窗口一致性檢查，對 Top3 做 permutation test")
        # 取 1500期 Edge 最高的 top3
        ranked = sorted(results.items(), key=lambda x: -x[1]['windows'][1500]['edge'])
        stable_strategies = [label for label, _ in ranked[:3]]

    for label in stable_strategies:
        info = results[label]
        n_bets = info['n_bets']
        # 找對應 predict_fn
        pred_fn = None
        for sl, fn, nb, cat in strategies:
            if sl == label:
                pred_fn = fn
                break

        if pred_fn is None:
            # Bandit — skip permutation for now
            print(f"\n  {label}: Bandit策略跳過標準 permutation (內建自適應)")
            continue

        print(f"\n  {label} (n_perms=200, test=300期)...")
        t0 = time.time()
        real_rate, perm_mean, p_value, z_score = permutation_test(
            history, pred_fn, n_bets, test_periods=300, n_perms=200)
        elapsed = time.time() - t0
        edge = real_rate - perm_mean
        verdict = "SIGNAL" if p_value < 0.05 else "NO SIGNAL"
        print(f"    Real={real_rate:.2f}% | Perm={perm_mean:.2f}% | "
              f"Edge={edge:+.2f}% | z={z_score:.2f} | p={p_value:.3f} | "
              f"{verdict} | {elapsed:.1f}s")

        results[label]['permutation'] = {
            'real_rate': real_rate, 'perm_mean': perm_mean,
            'p_value': p_value, 'z_score': z_score, 'verdict': verdict
        }

    # ==================== Summary ====================
    print("\n" + "=" * 80)
    print("  FINAL SUMMARY")
    print("=" * 80)

    print(f"\n  {'策略':<35} {'注數':>4} {'150p':>8} {'500p':>8} {'1500p':>8} {'穩定性':>8} {'Perm':>8}")
    print("  " + "-" * 85)

    for label, info in sorted(results.items(), key=lambda x: -x[1]['windows'][1500]['edge']):
        n = info['n_bets']
        e150 = info['windows'][150]['edge']
        e500 = info['windows'][500]['edge']
        e1500 = info['windows'][1500]['edge']
        edges = [e150, e500, e1500]
        stab = "STABLE" if all(e > 0 for e in edges) else "UNSTABLE"
        perm = info.get('permutation', {})
        perm_str = f"p={perm.get('p_value', 'N/A')}" if perm else "N/A"
        print(f"  {label:<35} {n:>4} {e150:>+7.2f}% {e500:>+7.2f}% "
              f"{e1500:>+7.2f}% {stab:>8} {perm_str:>8}")

    # Save results
    output = {
        'test_date': '2026-03-01',
        'trigger': '115000054期檢討',
        'total_draws': len(history),
        'baselines': baselines,
        'results': {}
    }
    for label, info in results.items():
        output['results'][label] = {
            'n_bets': info['n_bets'],
            'windows': {str(w): {
                'rate': info['windows'][w]['rate'],
                'edge': info['windows'][w]['edge'],
                'wins': info['windows'][w]['wins'],
                'total': info['windows'][w]['total'],
            } for w in WINDOWS},
            'permutation': info.get('permutation', None)
        }

    with open(os.path.join(project_root, 'backtest_539_p0p5_results.json'), 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: backtest_539_p0p5_results.json")


if __name__ == '__main__':
    main()
