#!/usr/bin/env python3
"""
P2: MAB 注選擇器 (Bet-Level Thompson Sampling Bandit)
======================================================
將 MAB 應用在「注配置」層面，而非號碼層面。

框架:
  每個注策略 = 一個 arm:
    Arm-A: Fourier注 (PP3注1風格)
    Arm-B: Fourier注2 (PP3注2風格)
    Arm-C: Echo/Cold注 (PP3注3風格)
    Arm-D: Cold+Sum注 (偏差互補風格)
    Arm-E: FreqOrt注 (5注正交注3/4風格)

Thompson Sampling:
  每個 arm 維護 Beta(α, β) 分佈
  α += 1 當命中 M3+
  β += 1 當未命中
  每次預測: 從每個 arm 採樣, 選 top-3 arm 作為本期組合

比較: MAB注選擇器 vs PP3原版 vs 固定5注

回測: 從 burn-in 期(200期)後開始
"""
import sys, os, json, numpy as np
from collections import Counter, deque
from scipy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)
MAB_SEED_RNG = np.random.default_rng(SEED)


def get_fourier_scores(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    scores = {}
    for n in range(1, 39):
        bh = np.zeros(w)
        for idx, d in enumerate(h_slice):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf, pos_yf = xf[idx_pos], np.abs(yf[idx_pos])
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


def arm_fourier_a(history, exclude=None):
    """Arm-A: Fourier Top 6"""
    if exclude is None:
        exclude = set()
    scores = get_fourier_scores(history)
    ranked = [n for n in sorted(range(1, 39), key=lambda x: -scores.get(x, 0)) if n not in exclude]
    return sorted(ranked[:6])


def arm_fourier_b(history, exclude=None):
    """Arm-B: Fourier rank 7-12"""
    if exclude is None:
        exclude = set()
    scores = get_fourier_scores(history)
    ranked = [n for n in sorted(range(1, 39), key=lambda x: -scores.get(x, 0)) if n not in exclude]
    return sorted(ranked[6:12]) if len(ranked) >= 12 else sorted(ranked[:6])


def arm_echo_cold(history, exclude=None):
    """Arm-C: Echo(lag-2∪lag-3) + Cold"""
    if exclude is None:
        exclude = set()
    echo = set()
    if len(history) >= 2:
        echo |= set(n for n in history[-2]['numbers'] if n <= 38 and n not in exclude)
    if len(history) >= 3:
        echo |= set(n for n in history[-3]['numbers'] if n <= 38 and n not in exclude)
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = sorted([n for n in range(1, 39) if n not in exclude and n not in echo],
                       key=lambda x: freq100.get(x, 0))
    pool = sorted(echo) + remaining
    return sorted(pool[:6])


def arm_cold_sum(history, exclude=None):
    """Arm-D: Cold(100期) + Sum-Constraint [mu-0.5σ, mu+0.5σ]"""
    if exclude is None:
        exclude = set()
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    all_sums = [sum(d['numbers']) for d in history[-500:]]
    mu, sigma = np.mean(all_sums), np.std(all_sums)
    lo, hi = mu - 0.5 * sigma, mu + 0.5 * sigma

    cold_ranked = sorted([n for n in range(1, 39) if n not in exclude],
                         key=lambda x: freq100.get(x, 0))[:14]

    from itertools import combinations
    best = None
    best_dist = float('inf')
    center = (lo + hi) / 2
    for combo in combinations(cold_ranked, min(6, len(cold_ranked))):
        s = sum(combo)
        if lo <= s <= hi:
            dist = abs(s - center)
            if dist < best_dist:
                best_dist = dist
                best = sorted(combo)
    if best is None:
        best = sorted(cold_ranked[:6])
    return best


def arm_freq_ort(history, exclude=None):
    """Arm-E: Freq Orthogonal residual"""
    if exclude is None:
        exclude = set()
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    freq_ranked = sorted([n for n in range(1, 39) if n not in exclude],
                         key=lambda x: -freq100.get(x, 0))
    return sorted(freq_ranked[:6])


ALL_ARMS = {
    'A_fourier1': arm_fourier_a,
    'B_fourier2': arm_fourier_b,
    'C_echo_cold': arm_echo_cold,
    'D_cold_sum': arm_cold_sum,
    'E_freq_ort': arm_freq_ort,
}


class ThompsonMABSelector:
    def __init__(self, arms, window=None):
        self.arms = list(arms.keys())
        self.arm_fns = arms
        self.alpha = {a: 1.0 for a in self.arms}  # successes + 1
        self.beta = {a: 1.0 for a in self.arms}   # failures + 1
        self.window = window  # sliding window (None=全歷史)
        self.history = deque(maxlen=window)

    def sample_and_select(self, n_bets=3, rng=None):
        """Thompson Sampling: 選出 top-n arm"""
        if rng is None:
            rng = MAB_SEED_RNG
        samples = {a: rng.beta(self.alpha[a], self.beta[a]) for a in self.arms}
        selected = sorted(self.arms, key=lambda a: -samples[a])[:n_bets]
        return selected

    def update(self, arm, hit):
        """更新 arm 的 Beta 參數"""
        if hit:
            self.alpha[arm] += 1
        else:
            self.beta[arm] += 1
        self.history.append({'arm': arm, 'hit': hit})

    def get_probs(self):
        return {a: self.alpha[a] / (self.alpha[a] + self.beta[a]) for a in self.arms}


def predict_mab(history, selector, n_bets=3, rng=None):
    """使用MAB選擇注配置"""
    selected_arms = selector.sample_and_select(n_bets=n_bets, rng=rng)
    bets = []
    used = set()
    for arm_name in selected_arms:
        arm_fn = ALL_ARMS[arm_name]
        bet = arm_fn(history, exclude=used)
        bets.append((arm_name, bet))
        used |= set(bet)
    return bets


def count_hits(bets_with_arms, actual):
    """bets_with_arms = [(arm_name, bet), ...]"""
    return max(len(set(b) & set(actual)) for _, b in bets_with_arms)


def count_hits_per_arm(bets_with_arms, actual):
    return {arm: len(set(b) & set(actual)) for arm, b in bets_with_arms}


def calc_edge(hits_list, single_p=0.0387, n_bets=3):
    baseline = 1 - (1 - single_p) ** n_bets
    m3r = sum(1 for h in hits_list if h >= 3) / len(hits_list)
    return m3r - baseline, m3r, baseline


def predict_pp3_fixed(history):
    """PP3固定注配置基準"""
    scores = get_fourier_scores(history)
    ranked = sorted(range(1, 39), key=lambda x: -scores.get(x, 0))
    bet1 = sorted(ranked[:6])
    bet2 = sorted(ranked[6:12])
    exclude = set(bet1) | set(bet2)
    echo = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = sorted([n for n in range(1, 39) if n not in exclude and n not in echo],
                       key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo + remaining)[:6])
    return [('A_fourier1', bet1), ('B_fourier2', bet2), ('C_echo_cold', bet3)]


def run_mab_backtest(draws, window=1500, burn_in=200, n_bets=3):
    """MAB滾動回測: burn-in期後開始統計"""
    rng = np.random.default_rng(SEED)
    selector = ThompsonMABSelector(ALL_ARMS)
    hits = []
    arm_selections = Counter()
    arm_success = Counter()

    start = max(burn_in, len(draws) - window)

    for i in range(burn_in, len(draws)):
        history = draws[:i]
        if len(history) < 100:
            continue
        actual = draws[i]['numbers']
        bets = predict_mab(history, selector, n_bets=n_bets, rng=rng)
        h = count_hits(bets, actual)
        h_per_arm = count_hits_per_arm(bets, actual)

        # 更新選擇器
        for arm_name, bet in bets:
            arm_h = h_per_arm[arm_name]
            selector.update(arm_name, arm_h >= 3)
            arm_selections[arm_name] += 1
            if arm_h >= 3:
                arm_success[arm_name] += 1

        if i >= start:
            hits.append(h)

    return hits, selector, arm_selections, arm_success


def run_pp3_backtest(draws, window=1500, min_history=100):
    hits = []
    start = max(min_history, len(draws) - window)
    for i in range(start, len(draws)):
        history = draws[:i]
        if len(history) < min_history:
            continue
        actual = draws[i]['numbers']
        bets = predict_pp3_fixed(history)
        hits.append(count_hits(bets, actual))
    return hits


def mcnemar_test(hits_a, hits_b):
    n_min = min(len(hits_a), len(hits_b))
    hits_a, hits_b = hits_a[-n_min:], hits_b[-n_min:]
    a_only = sum(1 for a, b in zip(hits_a, hits_b) if a >= 3 and b < 3)
    b_only = sum(1 for a, b in zip(hits_a, hits_b) if b >= 3 and a < 3)
    net = a_only - b_only
    n = a_only + b_only
    if n == 0:
        return 1.0, 0, 0
    from scipy.stats import binom
    p = 2 * binom.cdf(min(a_only, b_only), n, 0.5)
    return p, net, n


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))

    print("=" * 70)
    print("  P2: MAB 注選擇器 (Thompson Sampling Bet-Level)")
    print(f"  N={len(draws)}期, seed={SEED}, burn_in=200")
    print("=" * 70)

    # MAB回測 (3注, window=1500)
    print("\n[MAB 3注 回測...]")
    mab_hits_1500, selector, arm_sel, arm_suc = run_mab_backtest(draws, window=1500, burn_in=200, n_bets=3)
    mab_hits_500, _, _, _ = run_mab_backtest(draws, window=500, burn_in=200, n_bets=3)
    mab_hits_150, _, _, _ = run_mab_backtest(draws, window=150, burn_in=200, n_bets=3)

    print("\n[PP3 固定注配置 基準回測...]")
    pp3_hits_1500 = run_pp3_backtest(draws, window=1500)
    pp3_hits_500 = run_pp3_backtest(draws, window=500)
    pp3_hits_150 = run_pp3_backtest(draws, window=150)

    print(f"\n[結果比較]:")
    for name, h150, h500, h1500 in [
        ("PP3_fixed", pp3_hits_150, pp3_hits_500, pp3_hits_1500),
        ("MAB_3bet", mab_hits_150, mab_hits_500, mab_hits_1500),
    ]:
        e150, m150, _ = calc_edge(h150)
        e500, m500, _ = calc_edge(h500)
        e1500, m1500, base = calc_edge(h1500)
        print(f"  {name}:")
        print(f"    150p: Edge={e150*100:+.2f}% (M3+={m150*100:.2f}%)")
        print(f"    500p: Edge={e500*100:+.2f}% (M3+={m500*100:.2f}%)")
        print(f"    1500p: Edge={e1500*100:+.2f}% (M3+={m1500*100:.2f}%, base={base*100:.2f}%)")

    # Arm選擇分佈
    total_sel = sum(arm_sel.values())
    print(f"\n[MAB Arm選擇分佈 (burn-in後)]:")
    for arm in ALL_ARMS:
        sel = arm_sel.get(arm, 0)
        suc = arm_suc.get(arm, 0)
        prob = suc / sel if sel > 0 else 0
        print(f"  {arm}: 選{sel}次 ({sel/total_sel*100:.1f}%), 成功率={prob*100:.1f}%")

    # Beta後驗
    print(f"\n[最終 Beta分佈 (α,β)]:")
    for arm in ALL_ARMS:
        a, b = selector.alpha[arm], selector.beta[arm]
        print(f"  {arm}: α={a:.1f}, β={b:.1f}, P={a/(a+b)*100:.1f}%")

    # McNemar
    mcn_p, net, _ = mcnemar_test(mab_hits_1500, pp3_hits_1500)
    print(f"\n[McNemar MAB vs PP3 (1500期)]:")
    print(f"  MAB新增={max(0,net)}, 損失={max(0,-net)}, 差={net:+d}")
    print(f"  McNemar p={mcn_p:.4f} {'✓ 顯著' if mcn_p < 0.05 else '✗ 不顯著'}")

    e_mab = calc_edge(mab_hits_1500)[0]
    e_pp3 = calc_edge(pp3_hits_1500)[0]
    e_150_mab = calc_edge(mab_hits_150)[0]
    e_500_mab = calc_edge(mab_hits_500)[0]
    all_pos = e_150_mab > 0 and e_500_mab > 0 and e_mab > 0

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  MAB 三窗口全正: {'PASS' if all_pos else 'FAIL'}")
    print(f"  MAB vs PP3 改善: {(e_mab-e_pp3)*100:+.2f}%")
    print(f"  McNemar: net={net:+d}, p={mcn_p:.4f}")

    out = {
        'strategy': 'mab_thompson_bet_selector',
        'draw_count': len(draws),
        'seed': SEED,
        'burn_in': 200,
        'n_bets': 3,
        'windows': {
            'mab': {'150': calc_edge(mab_hits_150)[0], '500': calc_edge(mab_hits_500)[0], '1500': e_mab},
            'pp3': {'150': calc_edge(pp3_hits_150)[0], '500': calc_edge(pp3_hits_500)[0], '1500': e_pp3},
        },
        'arm_selection': dict(arm_sel),
        'arm_success': dict(arm_suc),
        'final_beta': {arm: {'alpha': selector.alpha[arm], 'beta': selector.beta[arm]} for arm in ALL_ARMS},
        'mcnemar_p': mcn_p,
        'mcnemar_net': net,
        'three_window': 'PASS' if all_pos else 'FAIL',
        'improvement_vs_pp3': e_mab - e_pp3
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest_power_mab_selector_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: {os.path.abspath(out_path)}")
    print("=" * 70)
    return out


if __name__ == "__main__":
    main()
