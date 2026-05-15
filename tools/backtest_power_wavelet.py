#!/usr/bin/env python3
"""
P1-B: Wavelet vs Fourier 信號比較回測
=======================================
用 PyWavelets CWT 替換 scipy FFT 作為注1+2的排名基礎
目標: CWT可捕獲非平穩短期局部週期 (如 gap=1 的短頻突發)
多尺度分析: scale 4-64 (週期4~64期)

比較: PP3_FFT vs PP3_Wavelet
注: 若 pywt 未安裝則自動降級至基準比較
"""
import sys, os, json, numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)

try:
    import pywt
    HAS_PYWT = True
except ImportError:
    HAS_PYWT = False
    print("[WARN] pywt 未安裝，Wavelet分析將用 Morlet 近似替代")


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


def get_wavelet_scores(history, window=500):
    """
    多尺度 CWT 評分:
    對每個號碼的出現序列做 CWT，找最強週期的功率，
    結合末次出現gap計算「即將爆發」的分數。
    """
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

        centered = bh - np.mean(bh)
        gap_positions = np.where(bh == 1)[0]
        last_hit = gap_positions[-1]
        gap = (w - 1) - last_hit

        if HAS_PYWT:
            # CWT with Morlet wavelet, scales 4~64
            scales = np.arange(4, min(65, w//4))
            if len(scales) == 0:
                scores[n] = 0.0
                continue
            coeffs, freqs = pywt.cwt(centered, scales, 'morl')
            power = np.abs(coeffs) ** 2
            # 最強功率所在的尺度→對應週期
            max_idx = np.unravel_index(np.argmax(power), power.shape)
            best_scale = scales[max_idx[0]]
            best_period = best_scale  # Morlet的尺度近似等於週期
            scores[n] = 1.0 / (abs(gap - best_period) + 1.0)
        else:
            # 手動 Morlet近似: 用短窗口FFT做局部分析
            # 取最後 min(w,128) 期做FFT (局部化)
            local_w = min(w, 128)
            local_bh = centered[-local_w:]
            yf = fft(local_bh)
            xf = fftfreq(local_w, 1)
            idx_pos = np.where(xf > 0)
            pos_xf, pos_yf = xf[idx_pos], np.abs(yf[idx_pos])
            if len(pos_xf) == 0:
                scores[n] = 0.0
                continue
            peak_idx = np.argmax(pos_yf)
            freq_val = pos_xf[peak_idx]
            if freq_val == 0:
                scores[n] = 0.0
                continue
            period = 1 / freq_val
            scores[n] = 1.0 / (abs(gap - period) + 1.0)

    return scores


def build_pp3(history, score_fn, label=""):
    scores = score_fn(history)
    ranked = sorted(range(1, 39), key=lambda x: -scores.get(x, 0))
    bet1 = sorted(ranked[:6])
    bet2 = sorted(ranked[6:12])
    exclude = set(bet1) | set(bet2)
    echo = [n for n in history[-2]['numbers'] if n <= 38 and n not in exclude]
    freq100 = Counter([n for d in history[-100:] for n in d['numbers'] if n <= 38])
    remaining = sorted([n for n in range(1, 39) if n not in exclude and n not in echo],
                       key=lambda x: freq100.get(x, 0))
    bet3 = sorted((echo + remaining)[:6])
    return [bet1, bet2, bet3]


def predict_fft(history):
    return build_pp3(history, get_fourier_scores, "FFT")


def predict_wavelet(history):
    return build_pp3(history, get_wavelet_scores, "Wavelet")


def count_hits(bets, actual):
    return max(len(set(b) & set(actual)) for b in bets)


def calc_edge(hits_list, single_p=0.0387, n_bets=3):
    baseline = 1 - (1 - single_p) ** n_bets
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


def permutation_test(draws, window, predictor, n_perm=200, seed=42):
    rng = np.random.default_rng(seed)
    real_hits = run_backtest(draws, window, predictor)
    real_edge, _, _ = calc_edge(real_hits)
    start = max(100, len(draws) - window)
    idxs = list(range(start, len(draws)))
    perm_edges = []
    for _ in range(n_perm):
        shuffled = [draws[i] for i in rng.permutation(len(draws))]
        perm_hits = []
        for i in idxs:
            history = shuffled[:i]
            if len(history) < 100:
                continue
            actual = shuffled[i]['numbers']
            try:
                bets = predictor(history)
                perm_hits.append(count_hits(bets, actual))
            except Exception:
                perm_hits.append(0)
        pe, _, _ = calc_edge(perm_hits)
        perm_edges.append(pe)
    perm_p = np.mean(np.array(perm_edges) >= real_edge)
    return perm_p, real_edge, np.mean(perm_edges)


def mcnemar_test(hits_a, hits_b):
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
    print("  PP3: Fourier(FFT) vs Wavelet(CWT) 回測比較")
    print(f"  N={len(draws)}期, pywt={'可用' if HAS_PYWT else '不可用(使用近似)'}")
    print("=" * 70)

    results = {}
    for name, predictor in [("PP3_FFT", predict_fft),
                             ("PP3_Wavelet", predict_wavelet)]:
        print(f"\n[{name}]")
        row = {}
        for window in [150, 500, 1500]:
            hits = run_backtest(draws, window, predictor)
            edge, m3r, base = calc_edge(hits)
            row[window] = {'hits': hits, 'edge': edge, 'm3r': m3r}
            sign = "+" if edge >= 0 else ""
            print(f"  {window:4d}期: Edge={sign}{edge*100:.2f}%, M3+={m3r*100:.2f}% (base={base*100:.2f}%)")
        results[name] = row

    # McNemar
    hits_fft = run_backtest(draws, 1500, predict_fft)
    hits_wav = run_backtest(draws, 1500, predict_wavelet)
    n_min = min(len(hits_fft), len(hits_wav))
    mcn_p, net, n_disc = mcnemar_test(hits_fft[-n_min:], hits_wav[-n_min:])
    print(f"\n[McNemar Wavelet vs FFT (1500期)]:")
    print(f"  Wavelet新增={max(0,net)}, 損失={max(0,-net)}, 差={net:+d}")
    print(f"  McNemar p={mcn_p:.4f} {'✓ Wavelet顯著優' if mcn_p < 0.05 and net > 0 else '✗ 無顯著差異'}")

    # Perm test for Wavelet
    print(f"\n[Permutation Test Wavelet (50次, 加速版)...]")
    perm_p, real_e, shuffle_mean = permutation_test(draws, 1500, predict_wavelet, n_perm=50)
    print(f"  Perm p={perm_p:.4f}, real={real_e*100:.2f}%, shuffle={shuffle_mean*100:.2f}%")

    e_150 = results["PP3_Wavelet"][150]['edge']
    e_500 = results["PP3_Wavelet"][500]['edge']
    e_1500 = results["PP3_Wavelet"][1500]['edge']
    f_1500 = results["PP3_FFT"][1500]['edge']
    all_pos = e_150 > 0 and e_500 > 0 and e_1500 > 0
    verdict = "SIGNAL_DETECTED" if perm_p <= 0.05 else ("MARGINAL" if perm_p <= 0.10 else "NO_SIGNAL")

    print(f"\n{'='*70}")
    print(f"  [判定]")
    print(f"  PP3_FFT:     150={results['PP3_FFT'][150]['edge']*100:+.2f}%, 500={results['PP3_FFT'][500]['edge']*100:+.2f}%, 1500={f_1500*100:+.2f}%")
    print(f"  PP3_Wavelet: 150={e_150*100:+.2f}%, 500={e_500*100:+.2f}%, 1500={e_1500*100:+.2f}%")
    print(f"  三窗口全正: {'PASS' if all_pos else 'FAIL'}")
    print(f"  Perm: {verdict} (p={perm_p:.4f})")
    print(f"  vs FFT改善: {(e_1500-f_1500)*100:+.2f}%")
    print(f"  pywt: {'真實CWT' if HAS_PYWT else '近似局部FFT'}")

    out = {
        'strategy': 'pp3_wavelet_vs_fft',
        'has_pywt': HAS_PYWT,
        'draw_count': len(draws),
        'seed': SEED,
        'windows': {
            'fft': {w: {'edge': results['PP3_FFT'][w]['edge'], 'm3r': results['PP3_FFT'][w]['m3r']} for w in [150,500,1500]},
            'wavelet': {w: {'edge': results['PP3_Wavelet'][w]['edge'], 'm3r': results['PP3_Wavelet'][w]['m3r']} for w in [150,500,1500]}
        },
        'perm_p': perm_p,
        'mcnemar_p': mcn_p,
        'mcnemar_net': net,
        'verdict': verdict,
        'three_window': 'PASS' if all_pos else 'FAIL',
        'improvement_vs_fft': e_1500 - f_1500
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backtest_power_wavelet_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已儲存: {os.path.abspath(out_path)}")
    print("=" * 70)
    return out


if __name__ == "__main__":
    main()
