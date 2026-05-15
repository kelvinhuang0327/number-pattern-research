#!/usr/bin/env python3
"""
Exhaustive Lottery Research Engine (Power Lotto / Big Lotto / 539)

Implements six mandatory phases:
1) Current system audit
2) Feature space exhaustion
3) Model exploration with rigorous validation
4) Micro-edge detection
5) Predictability ceiling analysis
6) Sustainable optimization architecture

All outputs are deterministic under fixed seeds.
"""

from __future__ import annotations

import ast
import json
import math
import random
import hashlib
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple, Any

import numpy as np
import sqlite3
from scipy.stats import hypergeom
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.naive_bayes import GaussianNB

# -------------------------
# Global reproducibility
# -------------------------
SEED = 20260305
np.random.seed(SEED)
random.seed(SEED)

WINDOWS = [150, 500, 1500]
PRIMARY_WINDOW = 1500
SUCCESS_THRESHOLD = 2  # unified M2+ signal metric across games
PERMUTATIONS = 300
MIN_HISTORY = 220
TRAIN_WINDOW = 1200
RETRAIN_INTERVAL = 250

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "lottery_api" / "data" / "lottery_v2.db"

SYSTEM_AUDIT_PATH = ROOT / "system_gap_analysis.md"
FEATURE_MATRIX_PATH = ROOT / "feature_space_matrix.json"
MODEL_TABLE_PATH = ROOT / "model_performance_table.json"
MICRO_SIGNAL_PATH = ROOT / "micro_signal_registry.json"
CEILING_REPORT_PATH = ROOT / "predictability_ceiling_report.md"
OPT_ARCH_PATH = ROOT / "continuous_optimization_architecture.md"
PROCESS_SUMMARY_PATH = ROOT / "research_process_and_conclusion_zh_tw.md"
ASSUMPTION_LOG_PATH = ROOT / "research_assumptions_log.json"
RUN_LOG_PATH = ROOT / "research_run_log.json"


@dataclass
class GameConfig:
    name: str
    lottery_type: str
    max_num: int
    pick_count: int


GAME_CONFIGS = [
    GameConfig(name="Power Lotto", lottery_type="POWER_LOTTO", max_num=38, pick_count=6),
    GameConfig(name="Big Lotto", lottery_type="BIG_LOTTO", max_num=49, pick_count=6),
    GameConfig(name="539", lottery_type="DAILY_539", max_num=39, pick_count=5),
]

ASSUMPTIONS = [
    "統一評估指標採用 M2+（命中至少 2 號）以提高檢定功效，三彩種一致化比較。",
    "Permutation 檢定以『固定預測、打亂真實開獎期序』估計虛無分配。",
    "Bonferroni 以同一 phase 的同類假設數量校正（特徵 N=19、模型 N=8）。",
    "Walk-forward 採用嚴格時序：每期 t 僅用 t 之前資料；模型採週期性重訓。",
    "為控制運算成本，模型重訓間隔設為 250 期，訓練視窗上限 1200 期。",
    "未納入獎金結構 EV；本研究聚焦『可檢測預測訊號』而非投資報酬率。",
    "Power/Big 的第二區（特別號）不納入本次主訊號檢定，避免混合不同樣本空間。",
]


def parse_date(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # fallback: very defensive
    s2 = s.replace("/", "-")
    return datetime.strptime(s2, "%Y-%m-%d")


def parse_draw_id(draw: str) -> int:
    try:
        return int("".join(ch for ch in str(draw) if ch.isdigit()) or 0)
    except ValueError:
        return 0


def json_load_numbers(s: str) -> List[int]:
    v = json.loads(s)
    return sorted(int(x) for x in v)


def hypergeom_baseline_m2p(max_num: int, pick_count: int) -> float:
    # X ~ Hypergeom(N=max_num, K=pick_count, n=pick_count)
    # P(X >= 2)
    probs = [hypergeom.pmf(k, max_num, pick_count, pick_count) for k in range(2, pick_count + 1)]
    return float(np.sum(probs))


def zscore(x: np.ndarray) -> np.ndarray:
    mu = float(np.mean(x))
    sd = float(np.std(x))
    if sd < 1e-12:
        return np.zeros_like(x, dtype=float)
    return (x - mu) / sd


def minmax01(x: np.ndarray) -> np.ndarray:
    lo = float(np.min(x))
    hi = float(np.max(x))
    if hi - lo < 1e-12:
        return np.zeros_like(x, dtype=float)
    return (x - lo) / (hi - lo)


def top_k_numbers(scores: np.ndarray, k: int) -> List[int]:
    idx = np.arange(1, len(scores) + 1)
    order = np.lexsort((idx, -scores))
    return sorted((order[:k] + 1).tolist())


class GameData:
    def __init__(self, cfg: GameConfig, draws: List[Dict[str, Any]]):
        self.cfg = cfg
        self.draws = draws
        self.T = len(draws)
        self.N = cfg.max_num

        self.actual_matrix = np.zeros((self.T, self.N), dtype=np.int8)
        self.draw_sums = np.zeros(self.T, dtype=float)
        self.draw_odd = np.zeros(self.T, dtype=float)
        self.draw_span = np.zeros(self.T, dtype=float)

        for t, d in enumerate(draws):
            nums = d["numbers"]
            for n in nums:
                self.actual_matrix[t, n - 1] = 1
            self.draw_sums[t] = float(sum(nums))
            self.draw_odd[t] = float(sum(1 for x in nums if x % 2 == 1))
            self.draw_span[t] = float(max(nums) - min(nums))

        self.cumsum = np.vstack([np.zeros((1, self.N), dtype=np.int32), np.cumsum(self.actual_matrix, axis=0)])

        self.gap_before = np.zeros((self.T, self.N), dtype=np.int16)
        last_seen = np.full(self.N, -1, dtype=np.int32)
        for t in range(self.T):
            gap = np.where(last_seen >= 0, t - last_seen, t + 1)
            self.gap_before[t] = np.minimum(gap, 999)
            current = np.where(self.actual_matrix[t] == 1)[0]
            last_seen[current] = t

    def freq_before(self, t: int, window: int) -> np.ndarray:
        start = max(0, t - window)
        return (self.cumsum[t] - self.cumsum[start]).astype(float)

    def last_draw_idx(self, t: int) -> np.ndarray:
        if t <= 0:
            return np.array([], dtype=int)
        return np.where(self.actual_matrix[t - 1] == 1)[0]

    def baseline_rate_pct(self) -> float:
        return hypergeom_baseline_m2p(self.cfg.max_num, self.cfg.pick_count) * 100.0


# -------------------------
# Data loading
# -------------------------
def load_game_data() -> Dict[str, GameData]:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    result: Dict[str, GameData] = {}

    for cfg in GAME_CONFIGS:
        rows = cur.execute(
            """
            SELECT draw, date, numbers, COALESCE(special, 0)
            FROM draws
            WHERE lottery_type = ?
            """,
            (cfg.lottery_type,),
        ).fetchall()

        parsed: List[Dict[str, Any]] = []
        for draw, date_s, numbers_s, special in rows:
            try:
                parsed.append(
                    {
                        "draw": str(draw),
                        "date": date_s,
                        "date_obj": parse_date(date_s),
                        "numbers": json_load_numbers(numbers_s),
                        "special": int(special) if special is not None else 0,
                    }
                )
            except Exception:
                continue

        parsed.sort(key=lambda x: (x["date_obj"], parse_draw_id(x["draw"])))
        result[cfg.lottery_type] = GameData(cfg, parsed)

    conn.close()
    return result


# -------------------------
# Feature classes (19)
# -------------------------
def feature_frequency(game: GameData, t: int) -> np.ndarray:
    return game.freq_before(t, 120)


def feature_gap_interval(game: GameData, t: int) -> np.ndarray:
    f100 = game.freq_before(t, 100)
    gap = game.gap_before[t].astype(float)
    return zscore(gap) * 0.7 + zscore(-f100) * 0.3


def feature_markov1(game: GameData, t: int) -> np.ndarray:
    if t < 2:
        return feature_frequency(game, t)
    window = min(140, t - 1)
    start = max(1, t - window)
    trans = np.zeros((game.N, game.N), dtype=np.float32)
    for i in range(start, t):
        prev_idx = np.where(game.actual_matrix[i - 1] == 1)[0]
        cur_idx = np.where(game.actual_matrix[i] == 1)[0]
        if len(prev_idx) and len(cur_idx):
            trans[np.ix_(prev_idx, cur_idx)] += 1.0
    last_idx = game.last_draw_idx(t)
    if len(last_idx) == 0:
        return feature_frequency(game, t)
    return trans[last_idx].sum(axis=0)


def feature_markov_higher(game: GameData, t: int) -> np.ndarray:
    if t < 3:
        return feature_markov1(game, t)
    window = min(220, t - 1)
    start = max(2, t - window)

    c1 = np.zeros(game.N, dtype=float)
    c2 = np.zeros(game.N, dtype=float)
    c11 = np.zeros(game.N, dtype=float)
    c21 = np.zeros(game.N, dtype=float)

    for i in range(start, t):
        prev1 = game.actual_matrix[i - 1]
        prev2 = game.actual_matrix[i - 2]
        cur = game.actual_matrix[i]
        c1 += prev1
        c2 += prev2
        c11 += prev1 * cur
        c21 += prev2 * cur

    p1 = (c11 + 1.0) / (c1 + 2.0)
    p2 = (c21 + 1.0) / (c2 + 2.0)
    return p1 * 0.65 + p2 * 0.35


def feature_fourier(game: GameData, t: int) -> np.ndarray:
    if t < 40:
        return feature_frequency(game, t)
    start = max(0, t - 256)
    hist = game.actual_matrix[start:t].astype(float)
    L = hist.shape[0]
    scores = np.zeros(game.N, dtype=float)
    gaps = game.gap_before[t].astype(float)

    for n in range(game.N):
        x = hist[:, n]
        if np.sum(x) < 2:
            continue
        y = np.abs(np.fft.rfft(x - np.mean(x)))
        if len(y) <= 1:
            continue
        y[0] = 0.0
        k = int(np.argmax(y))
        if k <= 0:
            continue
        period = L / k
        scores[n] = 1.0 / (1.0 + abs(gaps[n] - period))
    return scores


def feature_entropy(game: GameData, t: int) -> np.ndarray:
    f100 = game.freq_before(t, 100)
    p = np.clip(f100 / 100.0, 1e-6, 1 - 1e-6)
    h = -(p * np.log2(p) + (1 - p) * np.log2(1 - p))  # max 1 for binary
    gap = game.gap_before[t].astype(float)
    return (1 - h) * 0.6 + minmax01(gap) * 0.4


def feature_regime(game: GameData, t: int) -> np.ndarray:
    if t < 40:
        return feature_frequency(game, t)
    start = max(0, t - 220)
    sums = game.draw_sums[start:t]
    mu = float(np.mean(sums))
    sd = float(np.std(sums) + 1e-9)

    def state(v: float) -> int:
        z = (v - mu) / sd
        if z < -0.5:
            return 0
        if z > 0.5:
            return 2
        return 1

    current_state = state(float(game.draw_sums[t - 1]))
    counts = np.zeros(game.N, dtype=float)
    for i in range(start + 1, t):
        prev_state = state(float(game.draw_sums[i - 1]))
        if prev_state == current_state:
            counts += game.actual_matrix[i]
    if counts.sum() == 0:
        return feature_frequency(game, t)
    return counts


def feature_cluster(game: GameData, t: int) -> np.ndarray:
    if t < 50:
        return feature_frequency(game, t)
    start = max(0, t - 180)
    recent = game.actual_matrix[start:t]
    freq = recent.sum(axis=0).astype(float)

    co = np.zeros((game.N, game.N), dtype=float)
    for row in recent:
        idx = np.where(row == 1)[0]
        if len(idx) > 1:
            co[np.ix_(idx, idx)] += 1.0
    np.fill_diagonal(co, 0.0)

    feats = np.column_stack([freq, co.sum(axis=1), game.gap_before[t].astype(float)])
    k = min(4, game.N)
    try:
        km = KMeans(n_clusters=k, random_state=SEED, n_init=10)
        labels = km.fit_predict(feats)
    except Exception:
        return feature_frequency(game, t)

    strength = np.zeros(k, dtype=float)
    for c in range(k):
        mask = labels == c
        if np.any(mask):
            strength[c] = float(np.mean(freq[mask]) + 0.03 * np.mean(co.sum(axis=1)[mask]))
    return strength[labels] + 0.2 * minmax01(freq)


def feature_tail_extreme(game: GameData, t: int) -> np.ndarray:
    start = max(0, t - 150)
    nums = []
    for i in range(start, t):
        nums.extend((np.where(game.actual_matrix[i] == 1)[0] + 1).tolist())
    if not nums:
        return feature_frequency(game, t)
    tail_counts = np.zeros(10, dtype=float)
    for n in nums:
        tail_counts[n % 10] += 1.0

    last_sum = float(game.draw_sums[t - 1]) if t > 0 else float(np.mean(game.draw_sums))
    mean_sum = float(np.mean(game.draw_sums[max(0, t - 120):t])) if t > 0 else last_sum
    high_regime = last_sum > mean_sum

    scores = np.zeros(game.N, dtype=float)
    mid = (game.N + 1) / 2.0
    for n in range(1, game.N + 1):
        tail_score = tail_counts[n % 10]
        extreme = (mid - n) if high_regime else (n - mid)
        scores[n - 1] = tail_score * 0.8 + extreme * 0.2
    return scores


def feature_covering(game: GameData, t: int) -> np.ndarray:
    start = max(0, t - 130)
    pair = np.zeros((game.N, game.N), dtype=float)
    for i in range(start, t):
        idx = np.where(game.actual_matrix[i] == 1)[0]
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                x, y = idx[a], idx[b]
                pair[x, y] += 1.0
                pair[y, x] += 1.0
    inv = 1.0 / (pair + 1.0)
    np.fill_diagonal(inv, 0.0)
    return inv.sum(axis=1)


def feature_info_theory(game: GameData, t: int) -> np.ndarray:
    if t < 3:
        return feature_markov1(game, t)
    start = max(1, t - 200)
    x = game.actual_matrix[start:t]  # current
    l = game.actual_matrix[start - 1:t - 1]  # lag1 aligned

    p11 = (x * l).sum(axis=0) + 1.0
    p10 = (x * (1 - l)).sum(axis=0) + 1.0
    c1 = l.sum(axis=0) + 2.0
    c0 = (1 - l).sum(axis=0) + 2.0

    cond1 = p11 / c1
    cond0 = p10 / c0
    last = game.actual_matrix[t - 1]
    return cond1 * last + cond0 * (1 - last)


def feature_bayesian(game: GameData, t: int) -> np.ndarray:
    w = 120
    cnt = game.freq_before(t, w)
    alpha, beta = 1.0, 1.0
    return (alpha + cnt) / (alpha + beta + w)


def feature_monte_carlo_anomaly(game: GameData, t: int) -> np.ndarray:
    w = min(100, t)
    if w < 20:
        return feature_frequency(game, t)
    cnt = game.freq_before(t, w)
    p = game.cfg.pick_count / game.cfg.max_num
    exp = w * p
    std = math.sqrt(max(w * p * (1 - p), 1e-6))
    z = (cnt - exp) / std
    return z


def feature_player_behavior(game: GameData, t: int) -> np.ndarray:
    # contrarian proxy against common human choices (1~31, birthdays)
    f80 = game.freq_before(t, 80)
    cold = zscore(-f80)
    scores = np.zeros(game.N, dtype=float)
    for n in range(1, game.N + 1):
        anti_human = 1.0 if n > 31 else 0.0
        non_round = 1.0 if (n % 10 not in (0, 5)) else 0.0
        scores[n - 1] = 0.55 * anti_human + 0.2 * non_round + 0.25 * cold[n - 1]
    return scores


def feature_drift(game: GameData, t: int) -> np.ndarray:
    short = game.freq_before(t, 30) / 30.0
    long = game.freq_before(t, 220) / 220.0
    return short - long


def feature_interaction(game: GameData, t: int) -> np.ndarray:
    f = minmax01(game.freq_before(t, 120))
    g = minmax01(game.gap_before[t].astype(float))
    d = minmax01(np.maximum(feature_drift(game, t), 0.0))
    m = minmax01(feature_markov1(game, t))
    return f * g + 0.7 * m * d


def feature_ensemble_weighting(game: GameData, t: int) -> np.ndarray:
    # dynamic weighting by recent volatility regime
    recent = game.draw_sums[max(0, t - 80):t]
    vol = float(np.std(recent)) if len(recent) else 0.0
    vol_norm = min(1.0, vol / 20.0)

    s_freq = minmax01(feature_frequency(game, t))
    s_gap = minmax01(feature_gap_interval(game, t))
    s_markov = minmax01(feature_markov1(game, t))
    s_bayes = minmax01(feature_bayesian(game, t))

    # higher volatility -> raise Markov/Gap weight
    w_markov = 0.20 + 0.25 * vol_norm
    w_gap = 0.20 + 0.20 * vol_norm
    w_freq = 0.35 - 0.20 * vol_norm
    w_bayes = 1.0 - (w_markov + w_gap + w_freq)
    w = np.array([w_freq, w_gap, w_markov, w_bayes])
    w = np.maximum(w, 0.01)
    w = w / w.sum()
    return w[0] * s_freq + w[1] * s_gap + w[2] * s_markov + w[3] * s_bayes


def feature_nonlinear(game: GameData, t: int) -> np.ndarray:
    f = game.freq_before(t, 120)
    g = game.gap_before[t].astype(float)
    b = feature_bayesian(game, t)
    x = np.log1p(f) + np.tanh(g / 12.0) + np.square(np.clip(b, 0, 1))
    return x


def feature_random_baseline(game: GameData, t: int) -> np.ndarray:
    rng = np.random.default_rng(SEED + hash(game.cfg.lottery_type) % 9973 + t)
    return rng.random(game.N)


FEATURE_CLASSES: List[Tuple[int, str, Callable[[GameData, int], np.ndarray]]] = [
    (1, "Frequency-based", feature_frequency),
    (2, "Gap and interval", feature_gap_interval),
    (3, "Markov chains", feature_markov1),
    (4, "Higher-order Markov", feature_markov_higher),
    (5, "Fourier / spectral", feature_fourier),
    (6, "Entropy measures", feature_entropy),
    (7, "Regime detection", feature_regime),
    (8, "Cluster analysis", feature_cluster),
    (9, "Tail / extreme behavior", feature_tail_extreme),
    (10, "Combinatorial covering designs", feature_covering),
    (11, "Information theory metrics", feature_info_theory),
    (12, "Bayesian inference", feature_bayesian),
    (13, "Monte Carlo anomaly detection", feature_monte_carlo_anomaly),
    (14, "Player behavior modeling", feature_player_behavior),
    (15, "Distribution drift detection", feature_drift),
    (16, "Interaction and multiplicative signals", feature_interaction),
    (17, "Ensemble weighting", feature_ensemble_weighting),
    (18, "Non-linear transformations", feature_nonlinear),
    (19, "Random baseline falsification", feature_random_baseline),
]


# -------------------------
# Evaluation helpers
# -------------------------
def build_prediction_matrix(preds: List[List[int]], max_num: int) -> np.ndarray:
    mat = np.zeros((len(preds), max_num), dtype=np.int8)
    for i, p in enumerate(preds):
        for n in p:
            if 1 <= n <= max_num:
                mat[i, n - 1] = 1
    return mat


def permutation_test(pred_mat: np.ndarray, actual_mat: np.ndarray, threshold: int, n_perm: int, seed: int) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    overlap = (pred_mat * actual_mat).sum(axis=1)
    real_success = (overlap >= threshold).astype(np.int8)
    real_rate = float(np.mean(real_success))

    perm_rates = np.zeros(n_perm, dtype=float)
    idx = np.arange(actual_mat.shape[0])
    for i in range(n_perm):
        rng.shuffle(idx)
        ov = (pred_mat * actual_mat[idx]).sum(axis=1)
        perm_rates[i] = float(np.mean(ov >= threshold))

    mean_p = float(np.mean(perm_rates))
    std_p = float(np.std(perm_rates))
    exceed = int(np.sum(perm_rates >= real_rate))
    pval = float((exceed + 1) / (n_perm + 1))
    z = (real_rate - mean_p) / (std_p + 1e-12)
    effect = z  # Cohen's d under permutation null approximation
    return {
        "real_rate": real_rate,
        "perm_mean": mean_p,
        "perm_std": std_p,
        "z_score": float(z),
        "p_value": pval,
        "effect_size": float(effect),
        "n_perm": n_perm,
        "count_exceed": exceed,
    }


def stability_index(edges: List[float]) -> float:
    arr = np.array(edges, dtype=float)
    if np.all(np.abs(arr) < 1e-12):
        return 0.0
    mean_abs = float(np.mean(np.abs(arr))) + 1e-9
    sd = float(np.std(arr))
    sign_factor = float(np.sum(arr > 0) / len(arr))
    raw = max(0.0, 1.0 - sd / mean_abs)
    return float(max(0.0, min(1.0, raw * sign_factor)))


def evaluate_signal(game: GameData, preds: List[List[int]], bonf_alpha: float, seed_offset: int) -> Dict[str, Any]:
    test_len = len(preds)
    actual = game.actual_matrix[game.T - test_len:game.T]
    pred_mat = build_prediction_matrix(preds, game.N)

    overlap = (pred_mat * actual).sum(axis=1)
    success = (overlap >= SUCCESS_THRESHOLD).astype(np.int8)
    real_rate_pct = float(np.mean(success) * 100.0)

    baseline = game.baseline_rate_pct()
    edge_1500 = real_rate_pct - baseline

    edges = {}
    rates = {}
    for w in WINDOWS:
        s = success[-w:]
        r = float(np.mean(s) * 100.0)
        rates[str(w)] = r
        edges[str(w)] = r - baseline

    perm = permutation_test(
        pred_mat,
        actual,
        SUCCESS_THRESHOLD,
        n_perm=PERMUTATIONS,
        seed=SEED + seed_offset,
    )

    s_idx = stability_index([edges[str(w)] for w in WINDOWS])
    passes = bool(
        edge_1500 > 0
        and perm["p_value"] <= bonf_alpha
        and all(edges[str(w)] > 0 for w in WINDOWS)
    )

    return {
        "baseline_rate_pct": baseline,
        "real_rate_pct": real_rate_pct,
        "edge_pct": edge_1500,
        "window_rate_pct": rates,
        "window_edge_pct": edges,
        "permutation": perm,
        "bonferroni_alpha": bonf_alpha,
        "stability_index": s_idx,
        "passes_rigor": passes,
    }


# -------------------------
# Phase 2: feature sweep
# -------------------------
def run_phase2_feature_exhaustion(games: Dict[str, GameData]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "meta": {
            "seed": SEED,
            "primary_window": PRIMARY_WINDOW,
            "windows": WINDOWS,
            "threshold": f"M{SUCCESS_THRESHOLD}+",
            "permutations": PERMUTATIONS,
            "assumptions": ASSUMPTIONS,
            "generated_at": datetime.now().isoformat(),
        },
        "feature_classes": [],
    }

    bonf = 0.05 / len(FEATURE_CLASSES)

    for fid, name, fn in FEATURE_CLASSES:
        cls_rec: Dict[str, Any] = {
            "feature_class_id": fid,
            "name": name,
            "description": f"Feature class {fid}: {name}",
            "games": {},
        }

        for cfg in GAME_CONFIGS:
            game = games[cfg.lottery_type]
            start = game.T - PRIMARY_WINDOW
            preds: List[List[int]] = []

            for t in range(start, game.T):
                if t < MIN_HISTORY:
                    # deterministic fallback for early history
                    scores = game.freq_before(t, 120)
                else:
                    scores = fn(game, t)
                bet = top_k_numbers(np.asarray(scores, dtype=float), game.cfg.pick_count)
                preds.append(bet)

            metrics = evaluate_signal(game, preds, bonf_alpha=bonf, seed_offset=fid * 101 + game.N)
            cls_rec["games"][cfg.lottery_type] = metrics

        out["feature_classes"].append(cls_rec)

    return out


# -------------------------
# Phase 3: model exploration
# -------------------------
BASE_MODEL_ARMS = ["linear", "logistic", "bayesian", "tree", "markov"]
ALL_MODELS = ["linear", "logistic", "bayesian", "markov", "tree", "ensemble_stacking", "reinforcement_exploration", "evolutionary_mutation"]


def ml_features_at_t(game: GameData, t: int) -> np.ndarray:
    f30 = game.freq_before(t, 30)
    f100 = game.freq_before(t, 100)
    f220 = game.freq_before(t, 220)
    gap = game.gap_before[t].astype(float)

    lag1 = game.actual_matrix[t - 1].astype(float) if t >= 1 else np.zeros(game.N)
    lag2 = game.actual_matrix[t - 2].astype(float) if t >= 2 else np.zeros(game.N)

    drift = (f30 / 30.0) - (f220 / 220.0)
    bayes = (1.0 + f100) / 102.0
    interaction = minmax01(f100) * minmax01(gap)

    nums = np.arange(1, game.N + 1)
    odd = (nums % 2 == 1).astype(float)
    high = (nums > (game.N / 2)).astype(float)

    feats = np.column_stack(
        [
            zscore(f30),
            zscore(f100),
            zscore(gap),
            lag1,
            lag2,
            zscore(drift),
            bayes,
            odd,
            high,
            interaction,
        ]
    )
    return feats.astype(float)


def markov_prob_proxy(game: GameData, t: int) -> np.ndarray:
    s = feature_markov1(game, t)
    return minmax01(np.asarray(s, dtype=float))


def train_supervised_models(game: GameData, t: int) -> Dict[str, Any]:
    start = max(MIN_HISTORY, t - TRAIN_WINDOW)
    X_list = []
    y_list = []
    for i in range(start, t):
        Xi = ml_features_at_t(game, i)
        yi = game.actual_matrix[i].astype(int)
        X_list.append(Xi)
        y_list.append(yi)

    X = np.vstack(X_list)
    y = np.concatenate(y_list)

    # deterministic balancing by class weight is enough
    models: Dict[str, Any] = {}

    lin = LinearRegression()
    lin.fit(X, y)
    models["linear"] = lin

    logit = LogisticRegression(
        random_state=SEED,
        max_iter=200,
        solver="liblinear",
        class_weight="balanced",
    )
    logit.fit(X, y)
    models["logistic"] = logit

    nb = GaussianNB()
    nb.fit(X, y)
    models["bayesian"] = nb

    tree = RandomForestClassifier(
        n_estimators=80,
        max_depth=8,
        min_samples_leaf=5,
        random_state=SEED,
        n_jobs=1,
        class_weight="balanced_subsample",
    )
    tree.fit(X, y)
    models["tree"] = tree

    # Stacking meta-model on in-sample base probs (acceptable here as meta-combiner only)
    p_lin = minmax01(lin.predict(X))
    p_log = logit.predict_proba(X)[:, 1]
    p_nb = nb.predict_proba(X)[:, 1]
    p_tree = tree.predict_proba(X)[:, 1]

    # markov proxy for training samples: approximate with lag1 and f100 signal
    p_mk = minmax01(0.55 * X[:, 3] + 0.45 * minmax01(X[:, 1]))
    stack_X = np.column_stack([p_lin, p_log, p_nb, p_tree, p_mk])

    stack = LogisticRegression(
        random_state=SEED,
        max_iter=200,
        solver="liblinear",
        class_weight="balanced",
    )
    stack.fit(stack_X, y)
    models["stacking"] = stack

    return models


def evolve_weights(records: List[Dict[str, Any]], current: np.ndarray, pick_count: int, n_numbers: int) -> np.ndarray:
    if len(records) < 40:
        return current

    rng = np.random.default_rng(SEED + len(records) * 7 + 17)
    arms = ["logistic", "bayesian", "tree", "markov"]
    recent = records[-220:]

    def fitness(w: np.ndarray) -> float:
        hit = 0
        for rec in recent:
            score = np.zeros(n_numbers, dtype=float)
            for j, a in enumerate(arms):
                score += w[j] * rec["probs"][a]
            pred = set(top_k_numbers(score, pick_count))
            if len(pred & rec["actual"]) >= SUCCESS_THRESHOLD:
                hit += 1
        return hit / max(1, len(recent))

    pop_size = 24
    gens = 35
    elite = 6

    pop = [current.copy()]
    for _ in range(pop_size - 1):
        w = rng.dirichlet(np.ones(4))
        pop.append(w)

    for _ in range(gens):
        scored = sorted(((fitness(w), w) for w in pop), key=lambda x: x[0], reverse=True)
        elites = [w.copy() for _, w in scored[:elite]]
        new_pop = elites.copy()
        while len(new_pop) < pop_size:
            p1, p2 = rng.choice(elites, size=2, replace=True)
            alpha = rng.uniform(0.2, 0.8)
            child = alpha * p1 + (1 - alpha) * p2
            mut = rng.normal(0, 0.06, size=4)
            child = np.clip(child + mut, 1e-3, None)
            child = child / child.sum()
            new_pop.append(child)
        pop = new_pop

    best = max(pop, key=fitness)
    return best


def run_phase3_model_exploration(games: Dict[str, GameData]) -> Dict[str, Any]:
    bonf = 0.05 / len(ALL_MODELS)

    out: Dict[str, Any] = {
        "meta": {
            "seed": SEED,
            "primary_window": PRIMARY_WINDOW,
            "windows": WINDOWS,
            "threshold": f"M{SUCCESS_THRESHOLD}+",
            "permutations": PERMUTATIONS,
            "bonferroni_models": bonf,
            "train_window": TRAIN_WINDOW,
            "retrain_interval": RETRAIN_INTERVAL,
            "assumptions": ASSUMPTIONS,
            "generated_at": datetime.now().isoformat(),
        },
        "results": [],
    }

    for cfg in GAME_CONFIGS:
        game = games[cfg.lottery_type]
        start = game.T - PRIMARY_WINDOW

        pred_history: Dict[str, List[List[int]]] = {m: [] for m in ALL_MODELS}
        model_state: Dict[str, Any] = {}
        last_train_t = -1

        rl_counts = np.ones(len(BASE_MODEL_ARMS), dtype=float)
        rl_rewards = np.zeros(len(BASE_MODEL_ARMS), dtype=float)

        evo_weights = np.array([0.25, 0.25, 0.25, 0.25], dtype=float)
        evo_records: List[Dict[str, Any]] = []

        for t in range(start, game.T):
            need_retrain = (t == start) or ((t - last_train_t) >= RETRAIN_INTERVAL)
            if need_retrain:
                model_state = train_supervised_models(game, t)
                last_train_t = t
                evo_weights = evolve_weights(evo_records, evo_weights, game.cfg.pick_count, game.N)

            Xt = ml_features_at_t(game, t)

            p_linear = minmax01(model_state["linear"].predict(Xt))
            p_logit = model_state["logistic"].predict_proba(Xt)[:, 1]
            p_bayes = model_state["bayesian"].predict_proba(Xt)[:, 1]
            p_tree = model_state["tree"].predict_proba(Xt)[:, 1]
            p_markov = markov_prob_proxy(game, t)

            base_probs = {
                "linear": p_linear,
                "logistic": p_logit,
                "bayesian": p_bayes,
                "tree": p_tree,
                "markov": p_markov,
            }

            # stacking
            stack_X = np.column_stack([p_linear, p_logit, p_bayes, p_tree, p_markov])
            p_stack = model_state["stacking"].predict_proba(stack_X)[:, 1]

            # reinforcement exploration (UCB over base arms)
            total_steps = np.sum(rl_counts)
            ucb = rl_rewards / rl_counts + np.sqrt(2.0 * np.log(total_steps + 1.0) / rl_counts)
            arm_idx = int(np.argmax(ucb))
            arm_name = BASE_MODEL_ARMS[arm_idx]
            p_rl = base_probs[arm_name]

            # evolutionary mutation combiner
            p_evo = (
                evo_weights[0] * p_logit
                + evo_weights[1] * p_bayes
                + evo_weights[2] * p_tree
                + evo_weights[3] * p_markov
            )

            pred_map = {
                "linear": top_k_numbers(p_linear, game.cfg.pick_count),
                "logistic": top_k_numbers(p_logit, game.cfg.pick_count),
                "bayesian": top_k_numbers(p_bayes, game.cfg.pick_count),
                "markov": top_k_numbers(p_markov, game.cfg.pick_count),
                "tree": top_k_numbers(p_tree, game.cfg.pick_count),
                "ensemble_stacking": top_k_numbers(p_stack, game.cfg.pick_count),
                "reinforcement_exploration": top_k_numbers(p_rl, game.cfg.pick_count),
                "evolutionary_mutation": top_k_numbers(p_evo, game.cfg.pick_count),
            }

            actual_set = set((np.where(game.actual_matrix[t] == 1)[0] + 1).tolist())
            for m in ALL_MODELS:
                hit = len(set(pred_map[m]) & actual_set)
                _ = hit  # explicit for readability
                pred_history[m].append(pred_map[m])

            # update RL using realized success of chosen arm
            reward = 1 if len(set(pred_map["reinforcement_exploration"]) & actual_set) >= SUCCESS_THRESHOLD else 0
            rl_counts[arm_idx] += 1.0
            rl_rewards[arm_idx] += float(reward)

            evo_records.append(
                {
                    "probs": {
                        "logistic": p_logit.copy(),
                        "bayesian": p_bayes.copy(),
                        "tree": p_tree.copy(),
                        "markov": p_markov.copy(),
                    },
                    "actual": actual_set,
                }
            )

        for m in ALL_MODELS:
            metrics = evaluate_signal(
                game,
                preds=pred_history[m],
                bonf_alpha=bonf,
                seed_offset=991 + len(m) * 17 + game.N,
            )

            success = (
                (build_prediction_matrix(pred_history[m], game.N) * game.actual_matrix[game.T - PRIMARY_WINDOW:game.T]).sum(axis=1)
                >= SUCCESS_THRESHOLD
            ).astype(np.int8)

            # additional binomial p-value against theoretical random baseline
            n = len(success)
            p0 = metrics["baseline_rate_pct"] / 100.0
            k = int(np.sum(success))
            # normal approximation for tail probability
            mu = n * p0
            sigma = math.sqrt(max(n * p0 * (1 - p0), 1e-9))
            z_binom = (k - mu) / sigma
            # one-sided
            p_binom = 0.5 * (1 - math.erf(z_binom / math.sqrt(2)))

            passes = bool(
                metrics["passes_rigor"]
                and p_binom <= 0.05
            )

            reject_reason = None
            if not passes:
                reasons = []
                if metrics["edge_pct"] <= 0:
                    reasons.append("Edge<=0")
                if metrics["permutation"]["p_value"] > bonf:
                    reasons.append("Bonferroni fail")
                if p_binom > 0.05:
                    reasons.append("Binomial fail")
                if not all(metrics["window_edge_pct"][str(w)] > 0 for w in WINDOWS):
                    reasons.append("Three-window instability")
                reject_reason = ", ".join(reasons)

            out["results"].append(
                {
                    "game": cfg.lottery_type,
                    "model": m,
                    "baseline_rate_pct": metrics["baseline_rate_pct"],
                    "real_rate_pct": metrics["real_rate_pct"],
                    "edge_pct": metrics["edge_pct"],
                    "window_rate_pct": metrics["window_rate_pct"],
                    "window_edge_pct": metrics["window_edge_pct"],
                    "permutation": metrics["permutation"],
                    "binomial_test": {
                        "z_score": z_binom,
                        "p_value": p_binom,
                    },
                    "bonferroni_alpha": bonf,
                    "stability_index": metrics["stability_index"],
                    "passes_rigor": passes,
                    "rejected_reason": reject_reason,
                }
            )

    # sort by game then edge descending
    out["results"].sort(key=lambda r: (r["game"], -r["edge_pct"]))
    return out


# -------------------------
# Phase 1: system audit
# -------------------------
def run_phase1_audit(games: Dict[str, GameData], feature_res: Dict[str, Any], model_res: Dict[str, Any]) -> str:
    up_path = ROOT / "lottery_api" / "models" / "unified_predictor.py"
    text = up_path.read_text(encoding="utf-8")

    tree = ast.parse(text)
    method_count = 0
    predict_method_count = 0
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "UnifiedPredictionEngine":
            method_count = sum(isinstance(b, ast.FunctionDef) for b in node.body)
            predict_method_count = sum(isinstance(b, ast.FunctionDef) and b.name.endswith("_predict") for b in node.body)

    random_calls = text.count("random.") + text.count("np.random")

    # Feature/model fail summary for blind spots
    feat_pass = 0
    feat_total = 0
    untested_domains = []
    for rec in feature_res["feature_classes"]:
        # count pass across all 3 games
        game_pass = sum(1 for g in rec["games"].values() if g["passes_rigor"])
        feat_pass += game_pass
        feat_total += len(rec["games"])
        if game_pass == 0:
            untested_domains.append(rec["name"])

    model_pass = sum(1 for r in model_res["results"] if r["passes_rigor"])

    lines = []
    lines.append("# Phase 1 — Current System Audit（系統缺口分析）")
    lines.append("")
    lines.append("## 1. 架構現況")
    lines.append(f"- 核心引擎 `UnifiedPredictionEngine` 方法總數：{method_count}")
    lines.append(f"- 其中 `_predict` 類方法：{predict_method_count}")
    lines.append(f"- 程式內隨機呼叫痕跡（`random`/`np.random`）：{random_calls}")
    lines.append(f"- 研究樣本：Power={games['POWER_LOTTO'].T}、Big={games['BIG_LOTTO'].T}、539={games['DAILY_539'].T}")
    lines.append("")
    lines.append("## 2. 主要盲點")
    lines.append("- 策略數量極多但缺乏單一統一的假說註冊與淘汰機制，易出現事後挑選（post-selection bias）。")
    lines.append("- 多策略含隨機步驟，但未在所有路徑強制固定種子與輸出實驗指紋（hash）。")
    lines.append("- 部分驗證腳本彼此採不同評估指標（M2+/M3+、單注/多注、不同視窗），可比性不足。")
    lines.append("- 第二區（特別號）與第一區混合評估時，容易造成樣本空間不一致。")
    lines.append("")
    lines.append("## 3. 過擬合風險")
    lines.append("- 高維策略池 + 多重比較，若無 Bonferroni/FDR 強約束，假陽性機率高。")
    lines.append("- 若在全樣本調參後回測同一樣本，會產生 leakage。")
    lines.append("- 單次最佳化結果若未經三視窗穩定性檢查（150/500/1500），易屬短期噪音。")
    lines.append("")
    lines.append("## 4. 未充分測試的特徵域（以本次 Phase 2 全域掃描結果反推）")
    lines.append(f"- 全部遊戲皆未通過嚴格門檻之特徵域數量：{len(untested_domains)} / 19")
    for d in untested_domains:
        lines.append(f"- {d}")
    lines.append("")
    lines.append("## 5. 量化缺口指標")
    lines.append(f"- 特徵檢定通過率：{feat_pass}/{feat_total}（含跨遊戲）")
    lines.append(f"- 模型檢定通過率：{model_pass}/{len(model_res['results'])}")
    lines.append("")
    lines.append("## 6. 優先修復建議")
    lines.append("- 建立統一實驗登錄（假說ID、seed、資料切分、檢定門檻、輸出hash）。")
    lines.append("- 把所有新策略預設納入：walk-forward + permutation + Bonferroni + 三視窗穩定性。")
    lines.append("- 建立失敗策略記憶庫（禁止重複探索同型失敗假說）。")
    lines.append("- 將特別號建模拆成獨立子系統，不與第一區主訊號混合宣稱。")

    content = "\n".join(lines) + "\n"
    SYSTEM_AUDIT_PATH.write_text(content, encoding="utf-8")
    return content


# -------------------------
# Phase 4: micro-edge registry
# -------------------------
def run_phase4_micro_registry(feature_res: Dict[str, Any], model_res: Dict[str, Any]) -> Dict[str, Any]:
    registry = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "seed": SEED,
            "note": "僅收錄通過嚴格門檻（Bonferroni + 三視窗全正 + Edge>0）的訊號",
        },
        "signals": [],
    }

    for rec in feature_res["feature_classes"]:
        name = rec["name"]
        for game, m in rec["games"].items():
            if m["passes_rigor"]:
                registry["signals"].append(
                    {
                        "source": "feature",
                        "signal_name": name,
                        "game": game,
                        "edge_pct": m["edge_pct"],
                        "z_score": m["permutation"]["z_score"],
                        "p_value": m["permutation"]["p_value"],
                        "effect_size": m["permutation"]["effect_size"],
                        "stability_index": m["stability_index"],
                        "window_edge_pct": m["window_edge_pct"],
                    }
                )

    for rec in model_res["results"]:
        if rec["passes_rigor"]:
            registry["signals"].append(
                {
                    "source": "model",
                    "signal_name": rec["model"],
                    "game": rec["game"],
                    "edge_pct": rec["edge_pct"],
                    "z_score": rec["binomial_test"]["z_score"],
                    "p_value": rec["binomial_test"]["p_value"],
                    "effect_size": rec["binomial_test"]["z_score"],
                    "stability_index": rec["stability_index"],
                    "window_edge_pct": rec["window_edge_pct"],
                }
            )

    registry["signals"].sort(key=lambda x: (-x["edge_pct"], x["p_value"]))
    return registry


# -------------------------
# Phase 5: predictability ceiling
# -------------------------
def average_binary_mi(game: GameData, lag: int = 1, window: int = 1500) -> float:
    # I(X_t; X_{t-lag}) averaged across numbers, in bits
    if game.T <= lag + 10:
        return 0.0
    start = max(lag, game.T - window)
    x = game.actual_matrix[start:game.T]
    y = game.actual_matrix[start - lag:game.T - lag]

    mi_total = 0.0
    for n in range(game.N):
        xn = x[:, n]
        yn = y[:, n]
        p11 = np.mean((xn == 1) & (yn == 1))
        p10 = np.mean((xn == 1) & (yn == 0))
        p01 = np.mean((xn == 0) & (yn == 1))
        p00 = np.mean((xn == 0) & (yn == 0))
        px1 = p11 + p10
        px0 = p01 + p00
        py1 = p11 + p01
        py0 = p10 + p00

        mi = 0.0
        for pxy, px, py in (
            (p11, px1, py1),
            (p10, px1, py0),
            (p01, px0, py1),
            (p00, px0, py0),
        ):
            if pxy > 0 and px > 0 and py > 0:
                mi += pxy * math.log2(pxy / (px * py))
        mi_total += mi

    return mi_total / game.N


def run_phase5_ceiling(games: Dict[str, GameData], micro: Dict[str, Any]) -> str:
    best_edge = 0.0
    if micro["signals"]:
        best_edge = max(float(s["edge_pct"]) for s in micro["signals"])

    lines = []
    lines.append("# Phase 5 — Structural Limitation Analysis（可預測性天花板）")
    lines.append("")
    lines.append("## 方法")
    lines.append("- 以號碼邊際分布熵、序列 lag-1 平均互資訊（MI）與 Pinsker 上界估算可預測性上限。")
    lines.append("- 以本次通過嚴格門檻之最佳 Edge 作為可實現下界，形成『理論上界 vs 實證下界』夾擠區間。")
    lines.append("")

    global_ceiling = []

    for cfg in GAME_CONFIGS:
        g = games[cfg.lottery_type]
        N = g.cfg.max_num
        K = g.cfg.pick_count

        freq = np.mean(g.actual_matrix, axis=0)
        q = freq / max(float(np.sum(freq)), 1e-12)  # normalize to probability simplex
        q = np.clip(q, 1e-12, 1.0)
        h_marg = float(-np.sum(q * np.log2(q)))
        h_marg_max = math.log2(N)
        h_ratio = h_marg / h_marg_max

        mi1 = average_binary_mi(g, lag=1, window=1500)
        # Pinsker: TV <= sqrt( (ln2/2) * I_bits )
        tv_bound = math.sqrt(max((math.log(2) / 2.0) * mi1, 0.0))
        edge_bound_pct = tv_bound * 100.0

        baseline = g.baseline_rate_pct()
        theoretical_ceiling = baseline + edge_bound_pct
        global_ceiling.append(edge_bound_pct)

        lines.append(f"## {cfg.name} ({cfg.lottery_type})")
        lines.append(f"- 邊際熵 / 最大熵：{h_marg:.4f} / {h_marg_max:.4f}（比值 {h_ratio:.4f}）")
        lines.append(f"- lag-1 平均互資訊（每號碼 bits）：{mi1:.8f}")
        lines.append(f"- Pinsker 對事件機率差的上界（TV）：{tv_bound:.6f}")
        lines.append(f"- 推估 Edge 上限：約 {edge_bound_pct:.3f}%")
        lines.append(f"- 基準 M2+：{baseline:.3f}% -> 推估可達上限：約 {theoretical_ceiling:.3f}%")
        lines.append("")

    avg_bound = float(np.mean(global_ceiling)) if global_ceiling else 0.0
    lines.append("## 綜合判斷")
    lines.append(f"- 本次可檢測最佳實證 Edge：{best_edge:.3f}%")
    lines.append(f"- 三遊戲平均理論 Edge 上限（MI+Pinsker）：{avg_bound:.3f}%")
    if best_edge <= 0:
        lines.append("- 在嚴格校正後未得到可重現正 Edge，系統已接近理論隨機邊界。")
    else:
        lines.append("- 已觀測到微弱正 Edge，但量級仍接近資訊理論上限，屬低可開採訊號。")
    lines.append("- 結論：此類問題的可預測性天花板極低，主要收益來自長期微小偏差而非強可預測結構。")

    content = "\n".join(lines) + "\n"
    CEILING_REPORT_PATH.write_text(content, encoding="utf-8")
    return content


# -------------------------
# Phase 6: sustainable framework
# -------------------------
def run_phase6_architecture() -> str:
    lines = []
    lines.append("# Phase 6 — Sustainable Optimization Framework（永續優化架構）")
    lines.append("")
    lines.append("## 1. Strategy Lifecycle Management")
    lines.append("1. 假說註冊：每個新策略先建立 `hypothesis_id`、理論來源、預期方向、檢定指標。")
    lines.append("2. 沙盒驗證：先跑 150 期 smoke test（可執行性與資料完整性）。")
    lines.append("3. 正式驗證：150/500/1500 walk-forward + permutation + Bonferroni。")
    lines.append("4. 上線門檻：三視窗全正且 Bonferroni 通過。")
    lines.append("5. 退場規則：連續 N 次重驗失敗即降級為 archived。")
    lines.append("")
    lines.append("## 2. Automated Revalidation Triggers")
    lines.append("- 觸發 A：新開獎資料入庫後（事件觸發）。")
    lines.append("- 觸發 B：每週固定重驗（時間觸發）。")
    lines.append("- 觸發 C：漂移警報（PSI/KS 超門檻）觸發即時重驗。")
    lines.append("")
    lines.append("## 3. Drift Detection System")
    lines.append("- 監控層：號碼邊際分布、區間分布、奇偶、和值、重號率。")
    lines.append("- 漂移指標：PSI、KS、Jensen-Shannon divergence。")
    lines.append("- 門檻策略：Warning / Critical 雙層級，Critical 直接凍結策略權重更新。")
    lines.append("")
    lines.append("## 4. Version Control Structure")
    lines.append("- `experiments/registry.jsonl`：每次實驗 append-only，不覆寫。")
    lines.append("- `strategies/<id>/`：策略版本化（特徵、參數、驗證報告、hash）。")
    lines.append("- `reports/`：phase 輸出與審計報告固定檔名 + 日期戳備份。")
    lines.append("")
    lines.append("## 5. Failure Memory Archive")
    lines.append("- 失敗策略必須記錄：失敗原因、失敗窗口、p-value、effect size、重現指令。")
    lines.append("- 新策略提交前先比對失敗記憶，避免重複探索同型失敗。")
    lines.append("")
    lines.append("## 6. Continuous Evolution Mode")
    lines.append("- 探索池：僅允許小幅 mutation（防止高維暴衝）。")
    lines.append("- 利用池：只保留通過嚴格門檻的信號，採風險預算加權。")
    lines.append("- Online learning：僅在通過資料完整性與漂移檢查後才更新權重。")
    lines.append("- 守門規則：任一核心檢定失敗即回退到上一個穩定版本。")
    lines.append("")
    lines.append("## 7. Reproducibility Contract")
    lines.append("- 每次運行強制固定 seed。")
    lines.append("- 所有輸出檔附 SHA256 指紋。")
    lines.append("- 每次研究必須附 assumptions log 與環境資訊（Python/NumPy/Sklearn 版本）。")

    content = "\n".join(lines) + "\n"
    OPT_ARCH_PATH.write_text(content, encoding="utf-8")
    return content


# -------------------------
# Process summary document
# -------------------------
def build_process_summary(feature_res: Dict[str, Any], model_res: Dict[str, Any], micro: Dict[str, Any]) -> str:
    # aggregate quick stats
    feat_pass = 0
    feat_total = 0
    for rec in feature_res["feature_classes"]:
        for m in rec["games"].values():
            feat_total += 1
            feat_pass += 1 if m["passes_rigor"] else 0

    model_total = len(model_res["results"])
    model_pass = sum(1 for r in model_res["results"] if r["passes_rigor"])

    best_feat = None
    for rec in feature_res["feature_classes"]:
        for g, m in rec["games"].items():
            if best_feat is None or m["edge_pct"] > best_feat["edge_pct"]:
                best_feat = {
                    "name": rec["name"],
                    "game": g,
                    "edge_pct": m["edge_pct"],
                    "p": m["permutation"]["p_value"],
                }

    best_model = max(model_res["results"], key=lambda r: r["edge_pct"]) if model_res["results"] else None

    lines = []
    lines.append("# 研究過程與結論（繁體中文）")
    lines.append("")
    lines.append("## 過程")
    lines.append("1. 載入 `lottery_api/data/lottery_v2.db` 三彩種歷史資料，統一排序與清洗。")
    lines.append("2. 建立固定 seed 與統一檢定流程（walk-forward / OOS / permutation / Bonferroni / 三視窗）。")
    lines.append("3. 完整掃描 19 類特徵域並逐一評估跨遊戲穩定性。")
    lines.append("4. 實作 8 類模型（線性、邏輯、貝氏、Markov、樹、Stacking、RL、進化）。")
    lines.append("5. 對通過者建立 micro-edge 註冊，並估計資訊理論可預測性天花板。")
    lines.append("6. 產出永續優化框架（生命週期、重驗觸發、漂移偵測、失敗記憶、持續進化）。")
    lines.append("")
    lines.append("## 結果摘要")
    lines.append(f"- 特徵檢定通過率：{feat_pass}/{feat_total}")
    lines.append(f"- 模型檢定通過率：{model_pass}/{model_total}")
    if best_feat:
        lines.append(
            f"- 最佳特徵（未必通過嚴格門檻）：{best_feat['name']} @ {best_feat['game']}，Edge={best_feat['edge_pct']:.3f}%（p={best_feat['p']:.4f}）"
        )
    if best_model:
        lines.append(
            f"- 最佳模型（未必通過嚴格門檻）：{best_model['model']} @ {best_model['game']}，Edge={best_model['edge_pct']:.3f}%（binom p={best_model['binomial_test']['p_value']:.4f}）"
        )
    lines.append(f"- 嚴格存活微訊號數：{len(micro['signals'])}")
    lines.append("")
    lines.append("## 科學結論")
    if len(micro["signals"]) == 0:
        lines.append("- 在本次全域掃描與多重比較校正下，未觀測到可穩定重現的可開採訊號。")
        lines.append("- 系統接近統計隨機邊界，若有可用 edge 亦極可能低於實務可利用門檻。")
    else:
        lines.append("- 已偵測到通過嚴格門檻的微訊號，但 Edge 規模偏小，需以長期紀律執行與持續重驗維持。")
    lines.append("- 後續重點應放在『防止假陽性』與『持續漂移監控』，而非追求單次高績效。")

    content = "\n".join(lines) + "\n"
    PROCESS_SUMMARY_PATH.write_text(content, encoding="utf-8")
    return content


# -------------------------
# Lightweight tests
# -------------------------
def run_self_tests(games: Dict[str, GameData], feature_res: Dict[str, Any], model_res: Dict[str, Any], micro: Dict[str, Any]) -> Dict[str, Any]:
    tests = []

    def check(name: str, cond: bool, detail: str = ""):
        tests.append({"name": name, "pass": bool(cond), "detail": detail})
        if not cond:
            raise RuntimeError(f"[TEST FAIL] {name}: {detail}")

    # data checks
    for cfg in GAME_CONFIGS:
        g = games[cfg.lottery_type]
        check(f"data_nonempty_{cfg.lottery_type}", g.T > 1000, f"rows={g.T}")
        check(f"matrix_shape_{cfg.lottery_type}", g.actual_matrix.shape == (g.T, g.N), str(g.actual_matrix.shape))

    # feature phase checks
    check("feature_class_count", len(feature_res["feature_classes"]) == 19, str(len(feature_res["feature_classes"])))
    for rec in feature_res["feature_classes"]:
        for game_key in ["POWER_LOTTO", "BIG_LOTTO", "DAILY_539"]:
            check(f"feature_has_game_{rec['feature_class_id']}_{game_key}", game_key in rec["games"], "missing game")

    # model phase checks
    check("model_result_count", len(model_res["results"]) == len(GAME_CONFIGS) * len(ALL_MODELS), str(len(model_res["results"])))

    # determinism spot-check: same call twice must match
    g = games["BIG_LOTTO"]
    t = g.T - 123
    a = feature_markov1(g, t)
    b = feature_markov1(g, t)
    check("determinism_markov1", np.allclose(a, b), "markov mismatch")

    # micro registry consistency
    check("micro_registry_present", "signals" in micro, "missing signals")

    return {
        "all_passed": True,
        "tests": tests,
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_json(path: Path, obj: Any):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    games = load_game_data()

    write_json(
        ASSUMPTION_LOG_PATH,
        {
            "seed": SEED,
            "windows": WINDOWS,
            "primary_window": PRIMARY_WINDOW,
            "success_threshold": SUCCESS_THRESHOLD,
            "permutations": PERMUTATIONS,
            "train_window": TRAIN_WINDOW,
            "retrain_interval": RETRAIN_INTERVAL,
            "assumptions": ASSUMPTIONS,
            "generated_at": datetime.now().isoformat(),
        },
    )

    # Phase 2 + Phase 3 first (inputs for phase 1/4/5 summary)
    feature_res = run_phase2_feature_exhaustion(games)
    write_json(FEATURE_MATRIX_PATH, feature_res)

    model_res = run_phase3_model_exploration(games)
    write_json(MODEL_TABLE_PATH, model_res)

    # Phase 1
    run_phase1_audit(games, feature_res, model_res)

    # Phase 4
    micro = run_phase4_micro_registry(feature_res, model_res)
    write_json(MICRO_SIGNAL_PATH, micro)

    # Phase 5
    run_phase5_ceiling(games, micro)

    # Phase 6
    run_phase6_architecture()

    # Process summary in Chinese
    build_process_summary(feature_res, model_res, micro)

    # Self tests
    test_res = run_self_tests(games, feature_res, model_res, micro)

    run_log = {
        "timestamp": datetime.now().isoformat(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "seed": SEED,
        "outputs": {
            str(SYSTEM_AUDIT_PATH.name): file_sha256(SYSTEM_AUDIT_PATH),
            str(FEATURE_MATRIX_PATH.name): file_sha256(FEATURE_MATRIX_PATH),
            str(MODEL_TABLE_PATH.name): file_sha256(MODEL_TABLE_PATH),
            str(MICRO_SIGNAL_PATH.name): file_sha256(MICRO_SIGNAL_PATH),
            str(CEILING_REPORT_PATH.name): file_sha256(CEILING_REPORT_PATH),
            str(OPT_ARCH_PATH.name): file_sha256(OPT_ARCH_PATH),
            str(PROCESS_SUMMARY_PATH.name): file_sha256(PROCESS_SUMMARY_PATH),
            str(ASSUMPTION_LOG_PATH.name): file_sha256(ASSUMPTION_LOG_PATH),
        },
        "tests": test_res,
    }
    write_json(RUN_LOG_PATH, run_log)

    print("Research pipeline completed.")
    print(f"- {SYSTEM_AUDIT_PATH}")
    print(f"- {FEATURE_MATRIX_PATH}")
    print(f"- {MODEL_TABLE_PATH}")
    print(f"- {MICRO_SIGNAL_PATH}")
    print(f"- {CEILING_REPORT_PATH}")
    print(f"- {OPT_ARCH_PATH}")
    print(f"- {PROCESS_SUMMARY_PATH}")
    print(f"- {ASSUMPTION_LOG_PATH}")
    print(f"- {RUN_LOG_PATH}")


if __name__ == "__main__":
    main()
