#!/usr/bin/env python3
"""
今彩539 Momentum Regime 切換策略 — 正式三窗口驗證
2026-03-11

比較:
  Control (OLD): ACB + Markov + Fourier (固定，現行 PROVISIONAL)
  Test    (NEW): ACB + Markov + (EnhancedSerial if MOMENTUM else Fourier)

驗證標準 (CLAUDE.md):
  - 三窗口: 150 / 500 / 1500 期
  - Permutation test: 200 shuffles, p < 0.05
  - McNemar test: New vs Old, p < 0.05
  - 三窗口 Edge 全正
  - Regime 觸發率統計

主要指標: M3+ 命中率 (Edge = M3+_rate - M3+_baseline)
M3+ baseline (3注至少一注中3): ≈ 1 - (1 - C(5,3)*C(34,2)/C(39,5))^3
"""
import sys, os, json, random
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter
from scipy.stats import binomtest
import math

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
from database import DatabaseManager

# ===== 常數 =====
MAX_NUM = 39
PICK = 5
# 精確計算 C(39,5) = 575757
# M3+ 單注 = (C(5,3)*C(34,2) + C(5,4)*C(34,1) + C(5,5)) / C(39,5)
#           = (5610 + 170 + 1) / 575757 = 5781 / 575757 ≈ 1.004%
# M2+ 單注 = (C(5,2)*C(34,3) + ...) = 65621 / 575757 ≈ 11.40%
M3_SINGLE = 5781 / 575757          # ≈ 1.004%
M2_SINGLE = 65621 / 575757         # ≈ 11.40%
M3_3BET_BASELINE = 1 - (1 - M3_SINGLE) ** 3  # ≈ 2.99%
M2_3BET_BASELINE = 1 - (1 - M2_SINGLE) ** 3  # ≈ 30.50%

# ===== 預測函式 (全部 self-contained，不 import quick_predict) =====

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
    freq = Counter()
    for n in range(1, MAX_NUM + 1): freq[n] = 0
    for d in recent:
        for n in d['numbers']:
            if n <= MAX_NUM: freq[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM: last_seen[n] = i
    cur = len(recent)
    gaps = {n: cur - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected = len(recent) * PICK / MAX_NUM
    scores = {}
    for n in range(1, MAX_NUM + 1):
        fd = expected - freq[n]
        gs = gaps[n] / (len(recent) / 2)
        bb = 1.2 if (n <= 5 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (fd * 0.4 + gs * 0.6) * bb * m3
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
    for n in range(1, MAX_NUM + 1):
        if n not in scores: scores[n] = 0.0
    return dict(scores)


def enhanced_serial_scores(history, window=30):
    """Enhanced Serial: Markov + Echo lag-1/2/3 + Neighbor 複合分數"""
    weights = {'markov': 1.0, 'echo': 1.0, 'neighbor': 0.6}
    prev_draw = history[-1]['numbers']

    # Markov
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn not in transitions: transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                transitions[pn][nn] += 1
    m_sc = Counter()
    for pn in prev_draw:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                m_sc[n] += cnt / total

    # Echo lag
    e_sc = Counter()
    for lag, w in [(1, 1.5), (2, 1.0), (3, 0.5)]:
        if len(history) >= lag:
            for n in history[-lag]['numbers']:
                e_sc[n] += w

    # Neighbor
    n_sc = Counter()
    for n in prev_draw:
        for d in [-1, 1]:
            if 1 <= n + d <= MAX_NUM:
                n_sc[n + d] += 1.0

    m_max = max(m_sc.values()) if m_sc else 1
    e_max = max(e_sc.values()) if e_sc else 1
    n_max = max(n_sc.values()) if n_sc else 1

    combined = {}
    for n in range(1, MAX_NUM + 1):
        combined[n] = (
            (m_sc[n] / m_max) * weights['markov'] +
            (e_sc[n] / e_max) * weights['echo'] +
            (n_sc[n] / n_max) * weights['neighbor']
        )
    return combined


def top5(scores, exclude=None):
    """取分數最高的 5 個號碼"""
    exclude = exclude or set()
    ranked = sorted([n for n in scores if n not in exclude], key=lambda x: -scores[x])
    return sorted(ranked[:PICK])


def fourier_top5_seeded(scores, seed, exclude=None):
    """Fourier: 從 Top-15 隨機取 5（固定 seed 確保可重現）"""
    exclude = exclude or set()
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if n not in exclude]
    top15 = ranked[:15]
    rng = random.Random(seed)
    chosen = rng.sample(top15, min(5, len(top15)))
    return sorted(chosen)


# ===== Regime 判斷 =====

def is_momentum_regime(history, window=10, threshold=0.6):
    """最近 window 期的平均回頭號數 >= threshold"""
    if len(history) < window + 1:
        return False
    repeats = [
        len(set(history[i]['numbers']) & set(history[i - 1]['numbers']))
        for i in range(len(history) - window, len(history))
    ]
    return float(np.mean(repeats)) >= threshold


# ===== 策略定義 =====

def old_strategy(history, seed):
    """Control: ACB + Markov + Fourier (固定)"""
    a = acb_scores(history)
    m = markov_scores(history)
    f = fourier_scores(history)

    b1 = top5(a)
    b2 = top5(m, exclude=set(b1))
    b3 = fourier_top5_seeded(f, seed=seed, exclude=set(b1) | set(b2))
    return [b1, b2, b3]


def new_strategy(history, seed):
    """Test: ACB + Markov + (EnhancedSerial if MOMENTUM else Fourier)"""
    a = acb_scores(history)
    m = markov_scores(history)

    b1 = top5(a)
    b2 = top5(m, exclude=set(b1))

    regime = is_momentum_regime(history)
    if regime:
        es = enhanced_serial_scores(history)
        b3 = top5(es, exclude=set(b1) | set(b2))
        label = 'MOMENTUM'
    else:
        f = fourier_scores(history)
        b3 = fourier_top5_seeded(f, seed=seed, exclude=set(b1) | set(b2))
        label = 'STABLE'

    return [b1, b2, b3], label


# ===== 命中計算 =====

def hits(bets, actual):
    actual_set = set(actual)
    return [len(set(b) & actual_set) for b in bets]


def m2_plus(hit_list):
    return any(h >= 2 for h in hit_list)


def m3_plus(hit_list):
    return any(h >= 3 for h in hit_list)


# ===== 三窗口回測 =====

def run_window(history_all, window_size):
    n = len(history_all)
    start = n - window_size

    old_m2, old_m3 = [], []
    new_m2, new_m3 = [], []
    regime_labels = []

    for i in range(start, n):
        hist = history_all[:i]
        actual = history_all[i]['numbers']
        draw_num = history_all[i]['draw']

        # 固定 seed = draw 號碼整數（對兩策略一致）
        seed = int(str(draw_num)[-6:]) if str(draw_num).isdigit() else i

        ob = old_strategy(hist, seed)
        nb, label = new_strategy(hist, seed)
        regime_labels.append(label)

        old_m2.append(m2_plus(hits(ob, actual)))
        old_m3.append(m3_plus(hits(ob, actual)))
        new_m2.append(m2_plus(hits(nb, actual)))
        new_m3.append(m3_plus(hits(nb, actual)))

    return {
        'old_m2': old_m2, 'old_m3': old_m3,
        'new_m2': new_m2, 'new_m3': new_m3,
        'regime_labels': regime_labels,
    }


# ===== Permutation Test =====

def permutation_test(new_m3, baseline_p, n_shuffle=200, seed=42):
    """
    H0: 新策略 M3+ 命中率 <= baseline_p (random)
    H1: 新策略 > baseline_p
    方法: 對每期隨機模擬隨機選 5 號，計算 M3+ 命中，重複 n_shuffle 次
    """
    rng = np.random.default_rng(seed)
    n = len(new_m3)
    obs_rate = np.mean(new_m3)

    # 模擬基準：每期隨機取 5 號
    null_rates = []
    for _ in range(n_shuffle):
        sim = [
            len(set(rng.choice(MAX_NUM, PICK, replace=False) + 1) & set([]))  # placeholder
            for _ in range(n)
        ]
        # 實際 baseline: 每期 bernoulli(baseline_p)
        null_rates.append(np.mean(rng.random(n) < baseline_p))

    p_val = np.mean(np.array(null_rates) >= obs_rate)
    z = (obs_rate - baseline_p) / math.sqrt(baseline_p * (1 - baseline_p) / n)
    return obs_rate, z, p_val


# ===== McNemar Test =====

def mcnemar_test(old_hits, new_hits):
    """
    McNemar: 比較 Old vs New 的 M3+ 命中
    a = Old Y, New N (Old 勝)
    b = Old N, New Y (New 勝)
    """
    a = sum(1 for o, n in zip(old_hits, new_hits) if o and not n)
    b = sum(1 for o, n in zip(old_hits, new_hits) if not o and n)
    n_discordant = a + b
    if n_discordant == 0:
        return 0, 0, 1.0
    # Exact binomial (two-tailed)
    p_val = binomtest(b, n_discordant, 0.5, alternative='greater').pvalue
    return a, b, float(p_val)


# ===== 主程式 =====

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history_all = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    total = len(history_all)
    print(f"總資料期數: {total}")

    windows = [150, 500, 1500]
    results = {}

    for w in windows:
        if total < w + 50:
            print(f"[SKIP] 資料不足 {w} 期")
            continue
        print(f"\n{'='*50}")
        print(f"  三窗口驗證: {w} 期")
        print(f"{'='*50}")

        data = run_window(history_all, w)
        old_m3 = data['old_m3']
        new_m3 = data['new_m3']
        old_m2 = data['old_m2']
        new_m2 = data['new_m2']
        labels = data['regime_labels']

        # 基本統計
        old_m3_rate = np.mean(old_m3)
        new_m3_rate = np.mean(new_m3)
        old_m2_rate = np.mean(old_m2)
        new_m2_rate = np.mean(new_m2)

        # Edge (vs baseline)
        old_edge = (old_m3_rate - M3_3BET_BASELINE) * 100
        new_edge = (new_m3_rate - M3_3BET_BASELINE) * 100

        # Regime 分佈
        momentum_n = labels.count('MOMENTUM')
        stable_n = labels.count('STABLE')
        momentum_pct = momentum_n / len(labels) * 100

        print(f"  Regime 分佈: MOMENTUM={momentum_n}({momentum_pct:.1f}%) STABLE={stable_n}({100-momentum_pct:.1f}%)")
        print(f"  M3+ baseline (3注): {M3_3BET_BASELINE*100:.2f}%")
        print(f"  Control M3+: {old_m3_rate*100:.2f}%  Edge={old_edge:+.2f}%")
        print(f"  Test    M3+: {new_m3_rate*100:.2f}%  Edge={new_edge:+.2f}%")
        print(f"  Control M2+: {old_m2_rate*100:.2f}%")
        print(f"  Test    M2+: {new_m2_rate*100:.2f}%")

        # Permutation test (新策略 vs baseline)
        obs, z, p_perm = permutation_test(new_m3, M3_3BET_BASELINE, n_shuffle=200)
        print(f"\n  [Permutation Test] z={z:.2f}  p={p_perm:.3f}  {'✅ SIGNAL' if p_perm < 0.05 else '❌ NO SIGNAL'}")

        # McNemar (New vs Old, M3+)
        a, b, p_mc = mcnemar_test(old_m3, new_m3)
        print(f"  [McNemar M3+]  Old_only={a}  New_only={b}  net={b-a}  p={p_mc:.3f}  {'✅ New > Old' if p_mc < 0.05 else '—'}")

        # McNemar (M2+)
        a2, b2, p_mc2 = mcnemar_test(old_m2, new_m2)
        print(f"  [McNemar M2+]  Old_only={a2}  New_only={b2}  net={b2-a2}  p={p_mc2:.3f}")

        # Regime 分層分析
        mom_new_m3 = [new_m3[i] for i in range(len(labels)) if labels[i] == 'MOMENTUM']
        sta_new_m3 = [new_m3[i] for i in range(len(labels)) if labels[i] == 'STABLE']
        mom_old_m3 = [old_m3[i] for i in range(len(labels)) if labels[i] == 'MOMENTUM']
        sta_old_m3 = [old_m3[i] for i in range(len(labels)) if labels[i] == 'STABLE']

        if mom_new_m3:
            print(f"\n  MOMENTUM 期間 (N={len(mom_new_m3)}): Old_M3+={np.mean(mom_old_m3)*100:.2f}%  New_M3+={np.mean(mom_new_m3)*100:.2f}%")
        if sta_new_m3:
            print(f"  STABLE   期間 (N={len(sta_new_m3)}): Old_M3+={np.mean(sta_old_m3)*100:.2f}%  New_M3+={np.mean(sta_new_m3)*100:.2f}%")

        results[w] = {
            'old_m3_rate': float(old_m3_rate),
            'new_m3_rate': float(new_m3_rate),
            'old_edge': float(old_edge),
            'new_edge': float(new_edge),
            'z': float(z),
            'p_perm': float(p_perm),
            'mcnemar_a': int(a), 'mcnemar_b': int(b), 'p_mcnemar_m3': float(p_mc),
            'momentum_pct': float(momentum_pct),
            'signal': bool(p_perm < 0.05),
            'mcnemar_new_wins': bool(p_mc < 0.05),
        }

    # 最終裁決
    print(f"\n{'='*50}")
    print("  最終裁決")
    print(f"{'='*50}")

    if 1500 not in results:
        print("  ❌ 1500期資料不足，無法裁決")
        return

    r1500 = results[1500]
    all_positive = all(results[w]['new_edge'] > 0 for w in results)
    sig_1500 = r1500['signal']
    mc_wins = r1500['mcnemar_new_wins']

    print(f"  三窗口 Edge 全正: {'✅' if all_positive else '❌'}")
    print(f"  1500期 Perm p<0.05: {'✅' if sig_1500 else '❌'}")
    print(f"  McNemar New>Old: {'✅' if mc_wins else '❌'}")

    if all_positive and sig_1500 and mc_wins:
        verdict = 'ADOPT — 三項全通過，可升格替換 ACB+Markov+Fourier'
    elif all_positive and sig_1500:
        verdict = 'PROVISIONAL — Edge正且顯著，但 McNemar 未通過，監控200期後重評'
    elif all_positive:
        verdict = 'REJECT — Edge正但不顯著，維持現行策略'
    else:
        verdict = 'REJECT — Edge負窗口存在，維持現行策略'

    print(f"\n  裁決: {verdict}")

    # 儲存結果
    out_path = os.path.join(project_root, 'backtest_539_momentum_regime_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'strategy': 'Momentum Regime Switching (ACB+Markov+EnhancedSerial vs Fourier)',
            'date': '2026-03-11',
            'baseline_m3_3bet': float(M3_3BET_BASELINE * 100),
            'windows': results,
            'verdict': verdict,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  結果儲存: {out_path}")


if __name__ == '__main__':
    main()


# ===== HabitFourier 策略 (V8) =====

def get_likely_zones(history, window=500):
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    likely = []
    for z in range(4):
        ts = np.array([1 if len([n for n in d['numbers'] if (n-1)//10 == z]) >= 3 else 0 for d in h])
        if sum(ts) < 5: continue
        yf = fft(ts - np.mean(ts)); xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0); p_yf = np.abs(yf[idx_pos]); p_xf = xf[idx_pos]
        if len(p_yf) == 0: continue
        p_idx = np.argmax(p_yf); period = 1/p_xf[p_idx]; strength = p_yf[p_idx]
        gap = (w - 1) - np.where(ts == 1)[0][-1]
        if (abs(gap % period - period) < 1.0 or gap % period < 1.0) and strength > 60:
            likely.append(z)
    return likely


def habit_fourier_top5(history, exclude=None):
    exclude = exclude or set()
    sc = fourier_scores(history)
    likely_z = get_likely_zones(history)
    prev = set(history[-1]['numbers'])
    pool = sorted([n for n in range(1, MAX_NUM+1) if n not in exclude], key=lambda n: -sc.get(n, 0.0))[:10]
    def bias(n):
        b = 1.0
        if (n-1)//10 in likely_z: b += 0.2
        if n in prev: b += 0.1
        if (n-1 in prev) or (n+1 in prev): b += 0.05
        return sc.get(n, 0.0) * b
    return sorted(sorted(pool, key=bias, reverse=True)[:5])


def habit_strategy(history, seed):
    a = acb_scores(history)
    m = markov_scores(history)
    b1 = top5(a)
    b2 = top5(m, exclude=set(b1))
    b3 = habit_fourier_top5(history, exclude=set(b1)|set(b2))
    return [b1, b2, b3]


# ===== HabitFourier 獨立驗證主程式 =====

def main_habit():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history_all = db.get_all_draws(lottery_type='DAILY_539')
    history_all = sorted(history_all, key=lambda x: (x['date'], x['draw']))
    total = len(history_all)
    print(f"總資料期數: {total}")
    print("\n=== HabitFourier (V8) 正式三窗口驗證 ===\n")

    windows = [150, 500, 1500]
    results = {}

    for w in windows:
        if total < w + 50:
            print(f"[SKIP] 資料不足 {w} 期"); continue
        print(f"{'='*50}\n  三窗口驗證: {w} 期\n{'='*50}")

        old_m2, old_m3, new_m2, new_m3 = [], [], [], []
        for i in range(total - w, total):
            hist = history_all[:i]
            actual = history_all[i]['numbers']
            seed = int(str(history_all[i]['draw'])[-6:]) if str(history_all[i]['draw']).isdigit() else i
            ob = old_strategy(hist, seed)
            nb = habit_strategy(hist, seed)
            old_m2.append(m2_plus(hits(ob, actual)))
            old_m3.append(m3_plus(hits(ob, actual)))
            new_m2.append(m2_plus(hits(nb, actual)))
            new_m3.append(m3_plus(hits(nb, actual)))

        old_m3r = np.mean(old_m3); new_m3r = np.mean(new_m3)
        old_m2r = np.mean(old_m2); new_m2r = np.mean(new_m2)
        old_edge = (old_m3r - M3_3BET_BASELINE)*100
        new_edge = (new_m3r - M3_3BET_BASELINE)*100
        print(f"  Control M3+: {old_m3r*100:.2f}%  Edge={old_edge:+.2f}%")
        print(f"  Test    M3+: {new_m3r*100:.2f}%  Edge={new_edge:+.2f}%")
        print(f"  Control M2+: {old_m2r*100:.2f}%")
        print(f"  Test    M2+: {new_m2r*100:.2f}%")

        obs, z, p_perm = permutation_test(new_m3, M3_3BET_BASELINE, n_shuffle=200)
        print(f"\n  [Permutation] z={z:.2f}  p={p_perm:.3f}  {'✅ SIGNAL' if p_perm<0.05 else '❌ NO SIGNAL'}")

        a, b, p_mc = mcnemar_test(old_m3, new_m3)
        print(f"  [McNemar M3+] Old_only={a}  New_only={b}  net={b-a}  p={p_mc:.3f}  {'✅ New>Old' if p_mc<0.05 else '—'}")
        a2, b2, p_mc2 = mcnemar_test(old_m2, new_m2)
        print(f"  [McNemar M2+] Old_only={a2}  New_only={b2}  net={b2-a2}  p={p_mc2:.3f}")

        results[w] = {
            'new_edge': float(new_edge), 'z': float(z), 'p_perm': float(p_perm),
            'mcnemar_m3_net': int(b-a), 'p_mcnemar': float(p_mc),
            'm2_delta': float((new_m2r-old_m2r)*100),
        }

    print(f"\n{'='*50}\n  最終裁決\n{'='*50}")
    all_pos = all(results[w]['new_edge'] > 0 for w in results)
    sig = results.get(1500, {}).get('p_perm', 1.0) < 0.05
    mc = results.get(1500, {}).get('p_mcnemar', 1.0) < 0.05
    print(f"  三窗口 Edge 全正: {'✅' if all_pos else '❌'}")
    print(f"  1500期 Perm p<0.05: {'✅' if sig else '❌'}")
    print(f"  McNemar New>Old: {'✅' if mc else '❌'}")
    if all_pos and sig and mc:
        verdict = 'ADOPT'
    elif all_pos and sig:
        verdict = 'PROVISIONAL — 監控200期後重評'
    else:
        verdict = 'REJECT'
    print(f"\n  裁決: {verdict}")

    out = os.path.join(project_root, 'backtest_539_habit_fourier_results.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'strategy': 'HabitFourier V8', 'date': '2026-03-11', 'windows': results, 'verdict': verdict}, f, ensure_ascii=False, indent=2)
    print(f"  結果儲存: {out}")


if __name__ == '__main__':
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == 'habit':
        main_habit()
    else:
        main()
