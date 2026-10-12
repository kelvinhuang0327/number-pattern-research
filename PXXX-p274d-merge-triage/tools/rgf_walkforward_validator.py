#!/usr/bin/env python3
"""
RGF Walk-forward Validator
==========================
Regime-Gated Formula (RGF) 正確的滾動驗證腳本

設計原則:
  1. Walk-forward: t 時刻 GMM 只用 history[:t] 訓練 (無未來洩漏)
  2. GMM 每 RETRAIN_FREQ 期重訓一次，使用最近 GMM_TRAIN_WINDOW 期的特徵
  3. Permutation Test (n=1000): 洗牌狀態標籤，驗證信號非隨機
  4. Bonferroni 校正: 校正所有 State × Formula 多重比較
  5. 三窗口驗證: 150/500/1500 期

關鍵決策 (對比原始 in-sample GMM 研究):
  - 原始研究: GMM 在全部資料上訓練 → 未來洩漏 (錯誤)
  - 本腳本:  GMM 每期只看 history[:t] → 嚴格時序隔離 (正確)
  - Bonferroni α = 0.05 / (N_STATES × N_FORMULAS)
  - State 1 只有 ~89 期樣本 → SE 很大，需謹慎解讀

Usage:
    python3 tools/rgf_walkforward_validator.py
    python3 tools/rgf_walkforward_validator.py --lottery POWER_LOTTO
    python3 tools/rgf_walkforward_validator.py --eval_window 500 --n_perm 1000
    python3 tools/rgf_walkforward_validator.py --three_windows  # 150/500/1500 全跑
"""
import os
import sys
import json
import argparse
import time
import numpy as np
from collections import Counter, defaultdict
from scipy import stats
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

try:
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("⚠️  sklearn 未安裝，GMM 分類將退化為單一 State (0)")

from lottery_api.database import DatabaseManager

# ─────────────────────────────────────────────────────────
# 全局參數
# ─────────────────────────────────────────────────────────
LOTTERY_PARAMS = {
    'BIG_LOTTO':   {'max_num': 49, 'p_single': 0.0186, 'name': '大樂透'},
    'POWER_LOTTO': {'max_num': 38, 'p_single': 0.0387, 'name': '威力彩'},
}

N_STATES     = 3       # GMM 狀態數
PICK         = 6       # 每注號碼數

# GMM 訓練設定
GMM_BURN_IN        = 200   # 最少需要幾期才開始分類 (在 burn-in 內不分類)
GMM_TRAIN_WINDOW   = 500   # GMM 訓練用最近幾期的特徵向量
GMM_RETRAIN_FREQ   = 50    # 每幾期重訓一次 GMM (Walk-forward 代價與精度的折衷)
REGIME_FEAT_WINDOW = 20    # 提取當前 regime 特徵用幾期

# 原子特徵窗口
FREQ_WINDOW   = 100   # 頻率計算窗口
MARKOV_WINDOW = 30    # Markov 轉移矩陣窗口 (與已驗證的 TS3+Markov(w=30) 一致)


# ─────────────────────────────────────────────────────────
# 1. 原子特徵 (三個維度的號碼得分向量)
# ─────────────────────────────────────────────────────────
def compute_freq_score(history, max_num, window=FREQ_WINDOW):
    """近 window 期頻率 → 高頻號碼分數高"""
    recent = history[-window:] if len(history) >= window else history
    cnt = Counter(n for d in recent for n in d['numbers'])
    total = len(recent)
    return np.array([cnt.get(n, 0) / max(total, 1) for n in range(1, max_num + 1)])


def compute_gap_neg_score(history, max_num):
    """缺席期數 → 越久未出現分數越高 (均值回歸假設)"""
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers']:
            last_seen[n] = i
    t = len(history)
    gap = np.array([t - last_seen.get(n, 0) for n in range(1, max_num + 1)],
                   dtype=float)
    # 歸一化到 [0, 1]
    g_max = gap.max()
    return gap / (g_max + 1e-9)


def compute_markov_score(history, max_num, window=MARKOV_WINDOW):
    """
    Markov 轉移分數 (與 backtest_biglotto_markov_4bet.py 完全相同的實作)

    建立一階 Markov 轉移矩陣 (前期 → 本期)。
    根據最後一期開獎號碼，計算每個號碼的轉移期望分數。
    """
    if len(history) < 2:
        return np.ones(max_num, dtype=float) / max_num

    recent = history[-window:] if len(history) >= window else history

    # 建立轉移計數
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev_nums = recent[i]['numbers']
        next_nums = recent[i + 1]['numbers']
        for p in prev_nums:
            for n in next_nums:
                transitions[(p, n)] += 1

    # 根據最後一期計算分數
    last_nums = history[-1]['numbers']
    scores = np.zeros(max_num + 1, dtype=float)
    for p in last_nums:
        for n in range(1, max_num + 1):
            scores[n] += transitions.get((p, n), 0)

    score_vec = scores[1:]  # 1-indexed → 0-indexed array
    total = score_vec.sum()
    return score_vec / (total + 1e-9)


# ─────────────────────────────────────────────────────────
# 2. 公式庫 (6 種候選公式)
# 每個公式輸入 (freq, gap_neg, markov) 向量，輸出得分向量
# ─────────────────────────────────────────────────────────
FORMULAS = {
    'freq_x_gap':    lambda f, g, m: f * g,
    'freq_x_markov': lambda f, g, m: f * m,
    'gap_x_markov':  lambda f, g, m: g * m,
    'freq_add_gap':  lambda f, g, m: f + g,
    'freq_add_markov': lambda f, g, m: f + m,
    'freq_only':     lambda f, g, m: f,          # 基準線 (原始頻率)
}

N_FORMULAS = len(FORMULAS)
FORMULA_NAMES = list(FORMULAS.keys())


def top6_from_scores(scores, max_num):
    """從得分向量取 Top 6 號碼 (1-indexed)"""
    return set(np.argsort(scores)[-6:] + 1)


# ─────────────────────────────────────────────────────────
# 3. Regime 特徵提取 (只用 history[-window:])
# ─────────────────────────────────────────────────────────
def extract_regime_features(history, max_num, window=REGIME_FEAT_WINDOW):
    """
    提取 4 維 Regime 特徵向量，描述當前市場狀態。
    只使用 history[-window:] — 無未來洩漏。

    Features:
      f0: Zone Entropy  — 7個區間的資訊熵 (高=分散, 低=聚集)
      f1: Mean Volatility — 近期均值波動率
      f2: Avg Gap       — 平均缺席期數 (高=整體Gap壓力大)
      f3: Repeat Rate   — 前後兩期共同號碼數 (高=近期數字重複率高)
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 5:
        return None

    zone_size = max(1, max_num // 7)

    # f0: Zone Entropy
    all_nums = [n for d in recent for n in d['numbers']]
    zone_cnt = Counter(min((n - 1) // zone_size, 6) for n in all_nums)
    total = len(all_nums)
    probs = [c / total for c in zone_cnt.values() if c > 0]
    entropy = -sum(p * np.log(p + 1e-12) for p in probs)

    # f1: Mean Volatility
    means = [np.mean(d['numbers']) for d in recent]
    volatility = float(np.std(means))

    # f2: Avg Gap (以 window 內每個出現號碼的最後出現距離)
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    t = len(recent)
    avg_gap = float(np.mean([t - v for v in last_seen.values()])) if last_seen else 0.0

    # f3: Repeat Rate (前後期共現平均數)
    repeats = []
    for i in range(1, len(recent)):
        prev = set(recent[i - 1]['numbers'])
        curr = set(recent[i]['numbers'])
        repeats.append(len(prev & curr))
    avg_repeat = float(np.mean(repeats)) if repeats else 0.0

    return np.array([entropy, volatility, avg_gap, avg_repeat], dtype=float)


# ─────────────────────────────────────────────────────────
# 4. Walk-forward GMM 分類器
# ─────────────────────────────────────────────────────────
class WalkForwardGMM:
    """
    Walk-forward GMM 分類器。

    每 retrain_freq 期重新訓練一次，只用 history[:t] 內的特徵向量。
    設計要點:
      - 訓練集: t 時刻前 gmm_train_window 期的 regime 特徵 (逐期計算)
      - 每期特徵 features[i] 只使用 history[:i] 計算 → 無未來洩漏
      - 用 StandardScaler 歸一化後餵入 GMM
    """
    def __init__(self, n_states=N_STATES, retrain_freq=GMM_RETRAIN_FREQ,
                 train_window=GMM_TRAIN_WINDOW):
        self.n_states     = n_states
        self.retrain_freq = retrain_freq
        self.train_window = train_window
        self.gmm          = None
        self.scaler       = StandardScaler() if HAS_SKLEARN else None
        self._last_retrain = -9999
        self._precomputed  = {}   # t → feature_vec (緩存以避免重複計算)

    def _get_feature(self, history, max_num, t):
        """取第 t 步的 regime 特徵 (緩存)"""
        if t not in self._precomputed:
            f = extract_regime_features(history[:t], max_num)
            self._precomputed[t] = f
        return self._precomputed[t]

    def maybe_retrain(self, all_draws, max_num, t):
        """如果需要，重訓 GMM (Walk-forward)"""
        if not HAS_SKLEARN:
            return
        if t - self._last_retrain < self.retrain_freq:
            return
        if t < GMM_BURN_IN:
            return

        # 收集訓練樣本: 最近 train_window 個時間點的特徵
        train_t_range = range(max(GMM_BURN_IN, t - self.train_window), t)
        X_train = []
        for ti in train_t_range:
            f = self._get_feature(all_draws, max_num, ti)
            if f is not None:
                X_train.append(f)

        if len(X_train) < self.n_states * 5:
            return  # 樣本不足，跳過

        X = np.array(X_train)
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)

        try:
            gmm = GaussianMixture(
                n_components=self.n_states,
                random_state=42,
                n_init=5,
                max_iter=200,
            )
            gmm.fit(X_scaled)
            self.gmm = gmm
            self._last_retrain = t
        except Exception:
            pass  # 訓練失敗保留舊 GMM

    def predict_state(self, history, max_num, t):
        """預測 t 時刻的 regime state (0, 1, 2, ... 或 -1=未知)"""
        if not HAS_SKLEARN or self.gmm is None:
            return 0  # 退化為單一狀態

        feat = extract_regime_features(history, max_num)
        if feat is None:
            return 0

        try:
            feat_scaled = self.scaler.transform(feat.reshape(1, -1))
            return int(self.gmm.predict(feat_scaled)[0])
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────
# 5. Walk-forward 主驗證迴圈
# ─────────────────────────────────────────────────────────
def run_walkforward(draws, max_num, eval_window=1500, verbose=True):
    """
    完全正確的 Walk-forward 驗證。

    對每個 t in [start_idx, len(draws)):
      1. history = draws[:t]  (嚴格時序隔離)
      2. 用 history 重訓 / 預測 GMM state
      3. 計算 freq / gap_neg / markov 特徵
      4. 對每個公式 → 選 top6 → 計算命中數

    Args:
        draws:       時序排列 (舊→新) 的開獎記錄列表
        max_num:     號碼上限 (大樂透=49, 威力彩=38)
        eval_window: 評估期數 (從最後往回算)
        verbose:     是否列印進度

    Returns:
        list of dicts: 每期的 {draw_idx, state, formula_hits}
    """
    start_idx = max(GMM_BURN_IN, len(draws) - eval_window)
    total_eval = len(draws) - start_idx

    if verbose:
        print(f"\n  📊 Walk-forward 範圍: draws[{start_idx}:{len(draws)}] = {total_eval} 期")
        print(f"  GMM 重訓頻率: 每 {GMM_RETRAIN_FREQ} 期 | 訓練窗口: {GMM_TRAIN_WINDOW} 期")

    wf_gmm = WalkForwardGMM()
    results = []
    t_start = time.time()

    for t in range(start_idx, len(draws)):
        history = draws[:t]   # 嚴格: 不含 t
        actual  = set(draws[t]['numbers'])

        # Step A: Walk-forward GMM 重訓 + 分類
        wf_gmm.maybe_retrain(draws, max_num, t)
        state = wf_gmm.predict_state(history, max_num, t)

        # Step B: 計算原子特徵
        freq    = compute_freq_score(history, max_num)
        gap_neg = compute_gap_neg_score(history, max_num)
        markov  = compute_markov_score(history, max_num)

        # Step C: 每個公式 → top6 → 命中數
        formula_hits = {}
        for fname, func in FORMULAS.items():
            scores = func(freq, gap_neg, markov)
            top6   = top6_from_scores(scores, max_num)
            formula_hits[fname] = len(top6 & actual)

        results.append({
            'draw_idx':     t,
            'state':        state,
            'formula_hits': formula_hits,
        })

        if verbose and (t - start_idx + 1) % 200 == 0:
            elapsed = time.time() - t_start
            done    = t - start_idx + 1
            eta     = elapsed / done * (total_eval - done)
            print(f"  進度: {done}/{total_eval} 期 | "
                  f"已用 {elapsed:.1f}s | 預計剩餘 {eta:.1f}s")

    if verbose:
        print(f"  ✅ Walk-forward 完成，共 {len(results)} 期 (耗時 {time.time()-t_start:.1f}s)")

    return results


# ─────────────────────────────────────────────────────────
# 6. 統計分析模組
# ─────────────────────────────────────────────────────────
def m3plus_rate(hits_list):
    """計算 M3+ (命中 ≥ 3 個) 比率"""
    if not hits_list:
        return 0.0
    return sum(1 for h in hits_list if h >= 3) / len(hits_list)


def baseline_n_bets(p_single, n=1):
    """P(N注至少一注 M3+) = 1 - (1-p1)^N"""
    return 1.0 - (1.0 - p_single) ** n


def compute_edge(rate, p_single, n_bets=1):
    """Edge = (actual_rate - baseline) / baseline"""
    baseline = baseline_n_bets(p_single, n_bets)
    if baseline <= 0:
        return 0.0
    return (rate - baseline) / baseline


def analyze_by_state(results, p_single, header="State × Formula 分析"):
    """
    對每個 State × Formula 組合計算:
      - 樣本數 n
      - M3+ 命中率
      - Edge
      - 單側二項檢定 p-value (actual >= baseline?)
      - Bonferroni 校正標記

    Returns:
        findings: list of dicts
    """
    # 匯總每個 (state, formula) 的命中列表
    bucket = defaultdict(lambda: defaultdict(list))
    for r in results:
        s = r['state']
        for fname, hits in r['formula_hits'].items():
            bucket[s][fname].append(hits)

    all_states = sorted(s for s in bucket if s != -1)
    n_comparisons = len(all_states) * N_FORMULAS
    bonferroni_alpha = 0.05 / max(n_comparisons, 1)
    baseline_1bet    = baseline_n_bets(p_single, 1)

    sep = "=" * 62
    print(f"\n{sep}")
    print(f"📊 {header}")
    print(f"   Bonferroni α = 0.05 / {n_comparisons} = {bonferroni_alpha:.4f}")
    print(f"   1注 M3+ 基準 = {baseline_1bet:.2%}")
    print(sep)

    state_sizes = {s: len(next(iter(bucket[s].values()))) for s in all_states}
    print("  State 樣本分佈:", {s: state_sizes[s] for s in all_states})

    findings = []
    for state in all_states:
        print(f"\n  [State {state}]  n={state_sizes[state]:4d} 期")
        print(f"  {'公式':<22} {'n':>5} {'M3+':>7} {'Edge':>8} {'p-val':>8} {'校正後':>8}")
        print("  " + "-" * 60)

        for fname in FORMULA_NAMES:
            hits_list = bucket[state][fname]
            n         = len(hits_list)
            rate      = m3plus_rate(hits_list)
            edge      = compute_edge(rate, p_single, 1)

            # 單側二項檢定: H1: rate > baseline
            k = sum(1 for h in hits_list if h >= 3)
            if n > 0:
                try:
                    btest = stats.binomtest(k, n, baseline_1bet, alternative='greater')
                    p_val = btest.pvalue
                except AttributeError:
                    # scipy < 1.7 fallback
                    p_val = float(stats.binom_test(k, n, baseline_1bet,
                                                   alternative='greater'))
            else:
                p_val = 1.0

            sig_raw  = "*"   if p_val < 0.05          else ""
            sig_bonf = "✅★" if p_val < bonferroni_alpha else ""
            sig_str  = sig_bonf or sig_raw or "  "

            print(f"  {fname:<22} {n:>5d} {rate:>7.2%} {edge:>+8.2%} "
                  f"{p_val:>8.4f} {sig_str}")

            findings.append({
                'state':        state,
                'formula':      fname,
                'n':            n,
                'rate':         rate,
                'edge':         edge,
                'p_value':      p_val,
                'sig_bonferroni': p_val < bonferroni_alpha,
                'sig_raw':      p_val < 0.05,
            })

    # 全局 freq_only 基準行 (不分 state)
    all_freq_hits = [r['formula_hits']['freq_only'] for r in results]
    global_freq_rate = m3plus_rate(all_freq_hits)
    global_freq_edge = compute_edge(global_freq_rate, p_single)
    print(f"\n  [全局基準] freq_only: n={len(all_freq_hits)}, "
          f"M3+={global_freq_rate:.2%}, Edge={global_freq_edge:+.2%}")

    return findings, bonferroni_alpha


# ─────────────────────────────────────────────────────────
# 7. Permutation Test
# ─────────────────────────────────────────────────────────
def permutation_test(results, state, formula, p_single, n_perm=1000, seed=42):
    """
    Permutation Test: 隨機洗牌 State 標籤。

    虛無假設 H0: State 標籤與公式命中數無關。
    若真實 Edge >> Permutation 分佈均值，則拒絕 H0，確認 Regime 信號存在。

    注意: 這裡洗牌的是「state 分配」，保留每期的命中數不變。
    若真實 Edge 在 Permutation 分佈的 95th 百分位以上，p < 0.05。
    """
    real_hits = [r['formula_hits'][formula] for r in results if r['state'] == state]
    n_target  = len(real_hits)

    if n_target < 10:
        print(f"\n  ⚠️  Permutation Test 跳過: State {state} 樣本 n={n_target} < 10")
        return None

    real_rate = m3plus_rate(real_hits)
    real_edge = compute_edge(real_rate, p_single)

    all_states = [r['state'] for r in results]
    all_hits   = [r['formula_hits'][formula] for r in results]

    rng        = np.random.RandomState(seed)
    perm_edges = []

    for _ in range(n_perm):
        shuffled = rng.permutation(all_states)
        perm_hits = [all_hits[i] for i, s in enumerate(shuffled) if s == state]
        if perm_hits:
            perm_rate = m3plus_rate(perm_hits)
            perm_edges.append(compute_edge(perm_rate, p_single))

    perm_edges = np.array(perm_edges)
    p_perm     = float(np.mean(perm_edges >= real_edge))
    perm_mean  = float(np.mean(perm_edges))
    perm_std   = float(np.std(perm_edges))
    perm_95    = float(np.percentile(perm_edges, 95))

    sep = "-" * 50
    print(f"\n  {sep}")
    print(f"  🎲 Permutation Test (n={n_perm})")
    print(f"     State {state} × {formula}")
    print(f"  {sep}")
    print(f"  樣本數       : {n_target}")
    print(f"  真實 Edge    : {real_edge:+.2%}")
    print(f"  Perm 均值    : {perm_mean:+.2%} ± {perm_std:.2%}")
    print(f"  Perm 95th %  : {perm_95:+.2%}")
    print(f"  p-value      : {p_perm:.4f}")

    if p_perm < 0.05:
        print(f"  判定 : ✅ 信號顯著 (p={p_perm:.4f} < 0.05)")
        print(f"         Regime 分類提供了有效的額外信息")
    else:
        print(f"  判定 : ❌ 信號不顯著 (p={p_perm:.4f} ≥ 0.05)")
        print(f"         State 標籤可能是隨機噪音，不採納")

    return {
        'state':     state,
        'formula':   formula,
        'n_target':  n_target,
        'real_edge': real_edge,
        'perm_mean': perm_mean,
        'perm_std':  perm_std,
        'perm_95':   perm_95,
        'p_value':   p_perm,
        'significant': p_perm < 0.05,
    }


# ─────────────────────────────────────────────────────────
# 8. 三窗口驗證
# ─────────────────────────────────────────────────────────
def three_window_summary(draws, max_num, p_single, state, formula):
    """
    三窗口穩定性驗證 (150 / 500 / 1500 期)。
    對每個窗口重跑完整的 walk-forward，只取指定 state × formula 的結果。
    """
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"📈 三窗口驗證: State {state} × {formula}")
    print(sep)

    windows = [150, 500, 1500]
    window_results = {}

    for w in windows:
        r_list = run_walkforward(draws, max_num, eval_window=w, verbose=False)
        hits   = [r['formula_hits'][formula] for r in r_list if r['state'] == state]
        if hits:
            rate = m3plus_rate(hits)
            edge = compute_edge(rate, p_single)
            window_results[w] = {'n': len(hits), 'rate': rate, 'edge': edge}
            sign = "✅" if edge > 0 else "❌"
            print(f"  {w:5d} 期: n={len(hits):4d}, M3+={rate:.2%}, Edge={edge:+.2%} {sign}")
        else:
            window_results[w] = None
            print(f"  {w:5d} 期: ⚠️  State {state} 樣本不足")

    # 穩定性判斷
    valid_edges = [v['edge'] for v in window_results.values() if v is not None]
    if not valid_edges:
        print("\n  判定: ❓ 無足夠數據")
        pattern = 'INSUFFICIENT_DATA'
    elif all(e > 0 for e in valid_edges):
        print("\n  判定: ✅ 三窗口全正 → STABLE / ACCELERATING")
        pattern = 'STABLE'
    elif valid_edges[-1] > 0 >= valid_edges[0]:
        print("\n  判定: ⚠️  長期正但短期負 → LATE_BLOOMER (需謹慎)")
        pattern = 'LATE_BLOOMER'
    elif valid_edges[0] > 0 >= valid_edges[-1]:
        print("\n  判定: ❌ 短期正但長期負 → SHORT_MOMENTUM (拒絕)")
        pattern = 'SHORT_MOMENTUM'
    else:
        print("\n  判定: ❌ 長期 Edge 為負 → 拒絕採納")
        pattern = 'NEGATIVE'

    return window_results, pattern


# ─────────────────────────────────────────────────────────
# 9. 統計顯著性摘要
# ─────────────────────────────────────────────────────────
def print_significance_summary(findings, bonferroni_alpha):
    """列印哪些 State × Formula 組合達到 Bonferroni 顯著"""
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"🏆 顯著性摘要 (Bonferroni α={bonferroni_alpha:.4f})")
    print(sep)

    sig_bonf  = [f for f in findings if f['sig_bonferroni'] and f['edge'] > 0]
    sig_raw   = [f for f in findings if f['sig_raw'] and f['edge'] > 0 and not f['sig_bonferroni']]
    all_pos   = [f for f in findings if f['edge'] > 0]

    if sig_bonf:
        print(f"\n  ✅★ Bonferroni 顯著 (p < {bonferroni_alpha:.4f}) + Edge > 0:")
        for f in sorted(sig_bonf, key=lambda x: -x['edge']):
            print(f"     State {f['state']} × {f['formula']:<22} "
                  f"Edge={f['edge']:+.2%}, p={f['p_value']:.4f}, n={f['n']}")
    else:
        print(f"\n  ❌ 無 Bonferroni 顯著的正 Edge 組合")

    if sig_raw:
        print(f"\n  ⚠️  僅 p < 0.05 (未通過 Bonferroni) + Edge > 0:")
        for f in sorted(sig_raw, key=lambda x: -x['edge']):
            print(f"     State {f['state']} × {f['formula']:<22} "
                  f"Edge={f['edge']:+.2%}, p={f['p_value']:.4f}, n={f['n']}")

    if not sig_bonf and not sig_raw and all_pos:
        print(f"\n  ℹ️  僅 Edge > 0 (統計不顯著):")
        best = max(all_pos, key=lambda x: x['edge'])
        print(f"     最佳: State {best['state']} × {best['formula']}, "
              f"Edge={best['edge']:+.2%}, p={best['p_value']:.4f}, n={best['n']}")

    print()


# ─────────────────────────────────────────────────────────
# 10. 主程式
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='RGF Walk-forward Validator — 正確的 Regime-Gated Formula 驗證'
    )
    parser.add_argument('--lottery',     default='BIG_LOTTO',
                        choices=['BIG_LOTTO', 'POWER_LOTTO'],
                        help='彩票種類 (default: BIG_LOTTO)')
    parser.add_argument('--eval_window', type=int, default=1500,
                        help='評估期數 (default: 1500, 建議值: 150/500/1500)')
    parser.add_argument('--n_states',    type=int, default=N_STATES,
                        help=f'GMM 狀態數 (default: {N_STATES})')
    parser.add_argument('--n_perm',      type=int, default=1000,
                        help='Permutation Test 次數 (default: 1000, 最低建議: 500)')
    parser.add_argument('--three_windows', action='store_true',
                        help='對最佳組合進行 150/500/1500 期三窗口驗證')
    parser.add_argument('--no_perm',     action='store_true',
                        help='跳過 Permutation Test (快速模式)')
    parser.add_argument('--output',      default=None,
                        help='結果 JSON 輸出路徑 (default: auto)')
    args = parser.parse_args()

    params = LOTTERY_PARAMS[args.lottery]
    max_num  = params['max_num']
    p_single = params['p_single']
    name     = params['name']

    print("=" * 62)
    print(f"🔬 RGF Walk-forward Validator")
    print(f"   彩票: {name} ({args.lottery})")
    print(f"   GMM 狀態數: {args.n_states} | 評估期: {args.eval_window}")
    print(f"   Permutation: {args.n_perm} 次 | 公式數: {N_FORMULAS}")
    print(f"   sklearn 可用: {HAS_SKLEARN}")
    print("=" * 62)

    # 載入資料
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    if not os.path.exists(db_path):
        # fallback
        db_path = os.path.join(project_root, 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    draws_raw = db.get_all_draws(lottery_type=args.lottery)

    # get_all_draws 回傳最新→最舊，reverse 為舊→新 (與其他 backtest 腳本一致)
    draws = list(reversed(draws_raw))
    print(f"\n  資料: {len(draws)} 期 | 最早: {draws[0].get('date','?')} | 最新: {draws[-1].get('date','?')}")

    if len(draws) < GMM_BURN_IN + 50:
        print(f"❌ 資料不足 ({len(draws)} 期 < {GMM_BURN_IN + 50} 期)")
        return

    # ─── Step 1: Walk-forward 驗證 ───────────────────────
    print(f"\n{'─'*62}")
    print(f"  Step 1/4 — Walk-forward (eval_window={args.eval_window})")
    print(f"{'─'*62}")
    results = run_walkforward(draws, max_num, eval_window=args.eval_window, verbose=True)

    # 狀態分佈
    state_cnt = Counter(r['state'] for r in results)
    print(f"\n  State 分佈: {dict(sorted(state_cnt.items()))}")
    for s, cnt in sorted(state_cnt.items()):
        pct = cnt / len(results) * 100
        print(f"    State {s}: {cnt:4d} 期 ({pct:.1f}%)")

    # ─── Step 2: 統計分析 ────────────────────────────────
    print(f"\n{'─'*62}")
    print(f"  Step 2/4 — 統計分析 + Bonferroni 校正")
    print(f"{'─'*62}")
    findings, bonferroni_alpha = analyze_by_state(results, p_single)
    print_significance_summary(findings, bonferroni_alpha)

    # ─── Step 3: Permutation Test ─────────────────────────
    perm_results = {}
    if not args.no_perm:
        print(f"\n{'─'*62}")
        print(f"  Step 3/4 — Permutation Test (n={args.n_perm})")
        print(f"{'─'*62}")

        # 找出所有 Edge > 0 的組合進行 Permutation Test
        # 優先: Bonferroni 顯著 > 原始顯著 > Edge 最大
        positive_findings = [f for f in findings if f['edge'] > 0]
        if positive_findings:
            # 取 Edge 最大的 top-3 進行 Permutation Test
            top_candidates = sorted(positive_findings, key=lambda x: -x['edge'])[:3]
            for cand in top_candidates:
                key = f"state{cand['state']}_{cand['formula']}"
                perm_results[key] = permutation_test(
                    results, cand['state'], cand['formula'],
                    p_single, n_perm=args.n_perm
                )
        else:
            print("\n  ℹ️  無 Edge > 0 的組合，跳過 Permutation Test")

    # ─── Step 4: 三窗口驗證 ──────────────────────────────
    three_win_results = {}
    if args.three_windows:
        print(f"\n{'─'*62}")
        print(f"  Step 4/4 — 三窗口穩定性驗證 (150/500/1500 期)")
        print(f"{'─'*62}")

        # 選出最佳組合 (若有 Permutation 顯著則優先)
        sig_perm = [k for k, v in perm_results.items() if v and v.get('significant')]
        if sig_perm:
            best_key = max(sig_perm, key=lambda k: perm_results[k]['real_edge'])
            best = perm_results[best_key]
            best_state, best_formula = best['state'], best['formula']
        elif findings:
            best_f = max(findings, key=lambda x: x['edge'])
            best_state, best_formula = best_f['state'], best_f['formula']
        else:
            best_state, best_formula = 0, 'freq_only'

        three_win_results, pattern = three_window_summary(
            draws, max_num, p_single, best_state, best_formula
        )
    else:
        print(f"\n  Step 4/4 — 三窗口驗證 (跳過，加 --three_windows 啟動)")

    # ─── 最終結論 ─────────────────────────────────────────
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"📋 最終結論")
    print(sep)

    sig_bonf = [f for f in findings if f['sig_bonferroni'] and f['edge'] > 0]
    sig_perm_pass = [k for k, v in perm_results.items() if v and v.get('significant')]

    if sig_bonf and sig_perm_pass:
        print(f"\n  ✅ RGF 假說初步成立 — 但需完成三窗口驗證才能採納")
        print(f"     Bonferroni 顯著: {len(sig_bonf)} 組")
        print(f"     Permutation 顯著: {len(sig_perm_pass)} 組")
        print(f"     下一步: python3 tools/rgf_walkforward_validator.py --three_windows")
        verdict = 'PRELIMINARY_PASS'
    elif sig_perm_pass:
        print(f"\n  ⚠️  Permutation 顯著但未通過 Bonferroni — 可能存在信號，需謹慎")
        print(f"     建議: 增加 --n_perm 5000 重跑確認")
        verdict = 'MARGINAL'
    else:
        print(f"\n  ❌ RGF 假說不成立 — 無統計顯著的 Regime 效應")
        print(f"     Regime 分類對預測無顯著幫助，不建議採納")
        print(f"     保留現有已驗證策略 (BL 5注 Edge +1.77%, PL 3注 Edge +2.30%)")
        verdict = 'REJECTED'

    if args.three_windows:
        pattern_str = three_win_results.get('pattern', '') if isinstance(three_win_results, dict) else ''
        if pattern_str in ('SHORT_MOMENTUM', 'NEGATIVE'):
            print(f"\n  ❌ 三窗口確認為 {pattern_str} — 最終否決")
            verdict = 'REJECTED_THREE_WINDOW'
        elif pattern_str == 'STABLE' and verdict == 'PRELIMINARY_PASS':
            print(f"\n  ✅ 三窗口 STABLE — 通過完整驗證，可進入生產評估")
            verdict = 'PASSED_ALL_CHECKS'

    # ─── 儲存結果 ─────────────────────────────────────────
    output_path = args.output or os.path.join(
        project_root,
        f'rgf_walkforward_{args.lottery}_{args.eval_window}p.json'
    )
    output_data = {
        'lottery':      args.lottery,
        'eval_window':  args.eval_window,
        'n_draws_eval': len(results),
        'n_states':     args.n_states,
        'n_perm':       args.n_perm,
        'state_dist':   dict(sorted(state_cnt.items())),
        'findings':     findings,
        'perm_results': {k: v for k, v in perm_results.items() if v},
        'verdict':      verdict,
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  💾 結果已儲存: {output_path}")
    print(f"\n{'='*62}\n")


if __name__ == '__main__':
    main()
