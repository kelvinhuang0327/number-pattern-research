#!/usr/bin/env python3
"""
威力彩 4注策略回測
==================
研究目標: PP3 (3注) → 4注，填補 Edge +2.23%→+3.53% 的跳躍缺口

基準 (PP3 已知):
  注1: Fourier rank 1-6 (window=500)
  注2: Fourier rank 7-12
  注3: Echo(N-2期) + Cold(100期最冷，排除注1+2)
  使用 18 個號碼，剩餘 20 個號碼可用

三個候選第4注:
  A. FreqOrt   — 剩餘20號中按100期頻率取Top-6
  B. ACB-Power — score=(freq_deficit×0.4+gap_score×0.6)×boundary×mod3
  C. FourierResidual — 剩餘20號中重新計算Fourier分數取Top-6

採納標準:
  - 三窗口 Edge 全正 (STABLE)
  - perm p < 0.05
  - McNemar vs PP3 3注: A_only > B_only (方向正確)
"""
import sys, os, json
import numpy as np
from collections import Counter
from scipy.stats import binom

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)

MAX_NUM = 38
PICK = 6
P_SINGLE = 0.0387  # M3+ 單注機率 (已驗證)


# ============================================================
# 向量化 Fourier（批次計算全部38號，比逐號快10x）
# ============================================================

def get_fourier_scores_vec(history, window=500):
    """向量化 Fourier 分數計算（返回 scores dict）"""
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    # 建立 (38, w) bitstream 矩陣
    mat = np.zeros((MAX_NUM, w), dtype=np.float32)
    for idx, d in enumerate(h):
        for n in d['numbers']:
            if 1 <= n <= MAX_NUM:
                mat[n - 1, idx] = 1.0

    # 向量化 FFT
    means = mat.mean(axis=1, keepdims=True)
    centered = mat - means
    yf = np.fft.rfft(centered, axis=1)          # (38, w//2+1)
    xf = np.fft.rfftfreq(w, 1.0)                # (w//2+1,)
    pos_idx = xf > 0
    pos_yf = np.abs(yf[:, pos_idx])             # (38, n_pos)
    pos_xf = xf[pos_idx]                         # (n_pos,)

    peak_idxs = np.argmax(pos_yf, axis=1)        # (38,)
    freq_vals = pos_xf[peak_idxs]                # (38,)

    scores = {}
    for i in range(MAX_NUM):
        n = i + 1
        if mat[i].sum() < 2 or freq_vals[i] == 0:
            scores[n] = 0.0
            continue
        period = 1.0 / freq_vals[i]
        hits = np.where(mat[i] == 1)[0]
        last_hit = int(hits[-1])
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def get_gaps(history):
    gaps = {}
    for n in range(1, MAX_NUM + 1):
        for i in range(len(history) - 1, -1, -1):
            if n in history[i]['numbers']:
                gaps[n] = len(history) - 1 - i
                break
        else:
            gaps[n] = len(history)
    return gaps


# ============================================================
# PP3 基礎構建（複用給所有4注策略）
# ============================================================

def build_pp3(history):
    f_scores = get_fourier_scores_vec(history)
    f_ranked = sorted(range(1, MAX_NUM + 1), key=lambda x: -f_scores.get(x, 0))

    bet1 = sorted(f_ranked[:6])
    bet2 = sorted(f_ranked[6:12])
    exclude = set(bet1) | set(bet2)

    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= MAX_NUM])

    echo_nums = []
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]

    remaining = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    remaining.sort(key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo_nums + remaining)[:6])

    used = set(bet1) | set(bet2) | set(bet3)
    leftover_by_freq = sorted(
        [n for n in range(1, MAX_NUM + 1) if n not in used],
        key=lambda x: -freq100.get(x, 0)
    )
    return [bet1, bet2, bet3], used, leftover_by_freq, f_ranked, f_scores, freq100


# ============================================================
# 三個候選第4注策略
# ============================================================

def predict_pp3(history):
    bets, _, _, _, _, _ = build_pp3(history)
    return bets


def predict_pp3_freqort(history):
    """A. FreqOrt: 剩餘20號按頻率取Top-6"""
    bets, used, leftover_by_freq, _, _, _ = build_pp3(history)
    bet4 = sorted(leftover_by_freq[:6])
    return bets + [bet4]


def predict_pp3_acb(history):
    """B. ACB-Power: 異常捕捉評分"""
    bets, used, _, _, _, freq100 = build_pp3(history)

    window = 100
    recent = history[-window:] if len(history) >= window else history
    current = len(recent)
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            if n <= MAX_NUM:
                last_seen[n] = i
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, MAX_NUM + 1)}
    expected = len(recent) * PICK / MAX_NUM

    acb_scores = {}
    half = len(recent) / 2
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        fd = expected - freq100.get(n, 0)
        gs = gaps[n] / half
        bnd = 1.2 if (n <= 4 or n >= 35) else 1.0
        m3 = 1.1 if n % 3 == 0 else 1.0
        acb_scores[n] = (fd * 0.4 + gs * 0.6) * bnd * m3

    candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in used],
                        key=lambda x: -acb_scores.get(x, 0))
    bet4 = sorted(candidates[:6])
    return bets + [bet4]


def predict_pp3_fourier_residual(history):
    """C. Fourier殘差: 剩餘20號中重新按Fourier排名"""
    bets, used, _, _, f_scores, _ = build_pp3(history)
    candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in used],
                        key=lambda x: -f_scores.get(x, 0))
    bet4 = sorted(candidates[:6])
    return bets + [bet4]


def predict_ort5(history):
    """5注正交 (上界參考)"""
    bets, used, leftover_by_freq, _, _, freq100 = build_pp3(history)
    bet4 = sorted(leftover_by_freq[:6])
    used4 = used | set(bet4)
    leftover2 = sorted(
        [n for n in range(1, MAX_NUM + 1) if n not in used4],
        key=lambda x: -freq100.get(x, 0)
    )
    bet5 = sorted(leftover2[:6])
    return bets + [bet4, bet5]


# ============================================================
# 回測引擎
# ============================================================

def count_hits(bets, actual):
    return max(len(set(b) & set(actual)) for b in bets)


def calc_edge(hits_list, n_bets):
    baseline = 1 - (1 - P_SINGLE) ** n_bets
    m3r = sum(1 for h in hits_list if h >= 3) / len(hits_list)
    return m3r - baseline, m3r, baseline


def run_backtest(draws, window, predictor, min_history=100):
    hits = []
    start = max(min_history, len(draws) - window)
    for i in range(start, len(draws)):
        history = draws[:i]
        actual = draws[i]['numbers']
        try:
            bets = predictor(history)
            hits.append(count_hits(bets, actual))
        except Exception:
            hits.append(0)
    return hits


def permutation_test(draws, window, predictor, n_bets, n_perm=100, seed=42):
    """permutation test — 預設100次（3策略共300次）"""
    rng = np.random.default_rng(seed)
    real_hits = run_backtest(draws, window, predictor)
    real_edge, _, _ = calc_edge(real_hits, n_bets)
    start = max(100, len(draws) - window)
    idxs = list(range(start, len(draws)))
    perm_edges = []
    draw_arr = np.array(draws, dtype=object)
    for _ in range(n_perm):
        shuffled = draw_arr[rng.permutation(len(draws))].tolist()
        ph = []
        for i in idxs:
            history = shuffled[:i]
            if len(history) < 100:
                continue
            actual = shuffled[i]['numbers']
            try:
                bets = predictor(history)
                ph.append(count_hits(bets, actual))
            except Exception:
                ph.append(0)
        pe, _, _ = calc_edge(ph, n_bets)
        perm_edges.append(pe)
    perm_p = float(np.mean(np.array(perm_edges) >= real_edge))
    return perm_p, real_edge, float(np.mean(perm_edges))


def mcnemar_test(hits_a, hits_b, threshold=3):
    n = min(len(hits_a), len(hits_b))
    a = hits_a[-n:]
    b = hits_b[-n:]
    a_only = sum(1 for x, y in zip(a, b) if x >= threshold and y < threshold)
    b_only = sum(1 for x, y in zip(a, b) if y >= threshold and x < threshold)
    net = a_only - b_only
    disc = a_only + b_only
    if disc == 0:
        return 1.0, 0, 0
    p = float(2 * binom.cdf(min(a_only, b_only), disc, 0.5))
    return p, net, disc


# ============================================================
# 主程式
# ============================================================

def main():
    import time
    t0 = time.time()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))

    print("=" * 72)
    print("  威力彩 4注策略研究回測")
    print(f"  N={len(draws)}期, seed={SEED}")
    print("=" * 72)

    strategies = {
        'PP3':              (predict_pp3, 3),
        'PP3+FreqOrt':      (predict_pp3_freqort, 4),
        'PP3+ACB':          (predict_pp3_acb, 4),
        'PP3+FourierResid': (predict_pp3_fourier_residual, 4),
        'Ort5':             (predict_ort5, 5),
    }

    # ── 三窗口回測 ──
    results = {}
    for name, (pred, nb) in strategies.items():
        print(f"\n[{name}]  (n_bets={nb})")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, pred)
            edge, m3r, base = calc_edge(hits, nb)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r, 'base': base}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%  M3+={m3r*100:.2f}%  base={base*100:.2f}%")
        results[name] = row
    print(f"\n  三窗口完成 ({time.time()-t0:.1f}s)")

    # ── Permutation tests (100次) ──
    print("\n" + "=" * 72)
    print("  Permutation Tests (1500期, 100次)")
    print("=" * 72)
    perm_results = {}
    for name in ['PP3+FreqOrt', 'PP3+ACB', 'PP3+FourierResid']:
        pred, nb = strategies[name]
        print(f"  [{name}]...", flush=True)
        pp, re, sm = permutation_test(draws, 1500, pred, nb, n_perm=100)
        verdict = "SIGNAL_DETECTED" if pp <= 0.05 else ("MARGINAL" if pp <= 0.10 else "NO_SIGNAL")
        print(f"  perm_p={pp:.4f}  real={re*100:.2f}%  shuffle={sm*100:.2f}%  → {verdict}")
        perm_results[name] = {'perm_p': pp, 'real_edge': re, 'shuffle_mean': sm, 'verdict': verdict}
    print(f"  perm完成 ({time.time()-t0:.1f}s)")

    # ── McNemar ──
    print("\n" + "=" * 72)
    print("  McNemar: 4注 vs PP3 3注 / vs Ort5 (1500期)")
    print("=" * 72)
    hits_pp3 = run_backtest(draws, 1500, predict_pp3)
    hits_ort5 = run_backtest(draws, 1500, predict_ort5)
    mcn_results = {}
    for name in ['PP3+FreqOrt', 'PP3+ACB', 'PP3+FourierResid']:
        pred, nb = strategies[name]
        hits_4 = run_backtest(draws, 1500, pred)
        p_vs_pp3, net_vs_pp3, disc_pp3 = mcnemar_test(hits_4, hits_pp3)
        p_vs_ort5, net_vs_ort5, disc_ort5 = mcnemar_test(hits_4, hits_ort5)
        print(f"\n  [{name}]")
        print(f"  vs PP3: net={net_vs_pp3:+d} ({disc_pp3}discordant) p={p_vs_pp3:.4f}  {'✓ 方向正確' if net_vs_pp3 > 0 else '✗ 方向錯誤'}")
        print(f"  vs Ort5: net={net_vs_ort5:+d} ({disc_ort5}discordant) p={p_vs_ort5:.4f}")
        mcn_results[name] = {
            'vs_pp3':  {'net': net_vs_pp3, 'disc': disc_pp3,  'p': p_vs_pp3},
            'vs_ort5': {'net': net_vs_ort5, 'disc': disc_ort5, 'p': p_vs_ort5},
        }

    # ── 判定摘要 ──
    print("\n" + "=" * 72)
    print("  判定摘要")
    print("=" * 72)
    print(f"\n  {'策略':<22} {'150p':>8} {'500p':>8} {'1500p':>8} {'三窗':>6} {'perm_p':>8}  {'判定'}")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*8}  {'-'*14}")

    for ref_name in ['PP3', 'Ort5']:
        r = results[ref_name]
        e = [r[w]['edge'] * 100 for w in [150, 500, 1500]]
        all_pos = all(x > 0 for x in e)
        print(f"  {ref_name:<22} {e[0]:>+7.2f}% {e[1]:>+7.2f}% {e[2]:>+7.2f}% {'PASS' if all_pos else 'FAIL':>6}   {'—':>7}  (參考)")

    adopted = []
    for name in ['PP3+FreqOrt', 'PP3+ACB', 'PP3+FourierResid']:
        r = results[name]
        e = [r[w]['edge'] * 100 for w in [150, 500, 1500]]
        all_pos = all(x > 0 for x in e)
        pv = perm_results[name]
        net_vs_pp3 = mcn_results[name]['vs_pp3']['net']
        pass_perm = pv['perm_p'] <= 0.05
        pass_dir = net_vs_pp3 > 0
        if all_pos and pass_perm and pass_dir:
            vstr = "✅ PASS"
            adopted.append(name)
        elif all_pos and pv['perm_p'] <= 0.10 and pass_dir:
            vstr = "⚠️  MARGINAL"
        else:
            vstr = "❌ REJECT"
        print(f"  {name:<22} {e[0]:>+7.2f}% {e[1]:>+7.2f}% {e[2]:>+7.2f}% {'PASS' if all_pos else 'FAIL':>6}  {pv['perm_p']:>7.4f}  {vstr}")

    print(f"\n  通過策略: {adopted if adopted else '無'}")
    print(f"  總耗時: {time.time()-t0:.1f}s")

    # ── 儲存結果 ──
    out = {
        'strategy': 'power_lotto_4bet_research',
        'draw_count': len(draws),
        'seed': SEED,
        'p_single': P_SINGLE,
        'strategies': {
            name: {
                'n_bets': strategies[name][1],
                'windows': {
                    str(w): {'edge': results[name][w]['edge'],
                             'm3r':  results[name][w]['m3r'],
                             'base': results[name][w]['base']}
                    for w in [150, 500, 1500]
                },
                'perm': perm_results.get(name),
                'mcnemar': mcn_results.get(name),
            }
            for name in strategies
        },
        'adopted': adopted,
    }

    out_path = os.path.join(project_root, 'backtest_power_4bet_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: {out_path}")
    print("=" * 72)
    return out


if __name__ == '__main__':
    main()
