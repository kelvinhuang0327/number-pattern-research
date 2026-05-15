#!/usr/bin/env python3
"""
POWER_LOTTO PP3 + MidFreq orthogonal feature family V2 research (2026-04-23)
===========================================================================

Goal:
1. Explore a new PP3 + MidFreq orthogonal family that is explicitly outside:
   - special V3/V4 same-family reorder
   - midfreq 2bet regime-gate retries
   - WQ P2-1 reruns
2. Validate at least six history-only candidates on 150 / 500 / 1500 OOS windows.
3. Record edge, permutation p, Cohen's d, per-bet marginal efficiency, leakage,
   and conditional 500p McNemar only for full-gate passers.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from tools.backtest_power_4bet import build_pp3
from tools.power_fourier_rhythm import fourier_rhythm_predict
from tools.power_midfreq_fourier import _midfreq_scores
from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

SEED = 42
N_PERM = 200
MIN_HISTORY = 200
MAX_NUM = 38
PICK = 6
MATCH_TH = 3
DATE_TAG = "20260423"
DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
LEAKAGE_TOOL = os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
RESULT_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    f"power_pp3_midfreq_orthogonal_v2_{DATE_TAG}.json",
)
DIAG_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    f"power_pp3_midfreq_orthogonal_v2_diagnostics_{DATE_TAG}.json",
)
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINES = {n: 1 - (1 - P_SINGLE) ** n for n in range(1, 6)}


def now_iso_taipei() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="milliseconds")


def parse_numbers(raw) -> List[int]:
    if isinstance(raw, list):
        return [int(n) for n in raw]
    if isinstance(raw, str):
        return [int(n) for n in ast.literal_eval(raw)]
    raise TypeError(f"Unsupported numbers payload: {type(raw)!r}")


def load_draws() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(DB_QUERY, ("POWER_LOTTO",)).fetchall()
    finally:
        conn.close()

    desc_draws = [
        {
            "draw": row["draw"],
            "date": row["date"],
            "numbers": parse_numbers(row["numbers"]),
            "special": row["special"],
            "lottery_type": row["lottery_type"],
        }
        for row in rows
    ]
    return sorted(desc_draws, key=lambda d: (d["date"], d["draw"]))


def load_stage0_metrics() -> Dict:
    with open(STAGE0_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["POWER_LOTTO"]["strategies"]


def normalize_map(values: Dict[int, float], reverse: bool = False) -> Dict[int, float]:
    arr = np.array(list(values.values()), dtype=float)
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if hi - lo <= 1e-12:
        return {key: 0.5 for key in values}
    if reverse:
        return {key: (hi - val) / (hi - lo) for key, val in values.items()}
    return {key: (val - lo) / (hi - lo) for key, val in values.items()}


def bernoulli_sharpe(hit_rate: float, edge: float) -> float:
    variance = max(hit_rate * (1.0 - hit_rate), 1e-9)
    return edge / math.sqrt(variance)


def validate_no_leakage(target_draw: Dict, history: Sequence[Dict]) -> None:
    if not history:
        return
    last = history[-1]
    if (last["date"], last["draw"]) >= (target_draw["date"], target_draw["draw"]):
        raise ValueError(
            f"Data leakage: history tail {last['draw']} >= target {target_draw['draw']}"
        )


def recent_frequency_map(history: Sequence[Dict], window: int) -> Dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d["numbers"][:PICK] if n <= MAX_NUM)
    return {n: float(freq.get(n, 0)) for n in range(1, MAX_NUM + 1)}


def gap_map(history: Sequence[Dict], window: int = 120) -> Dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for idx, draw in enumerate(recent):
        for n in draw["numbers"][:PICK]:
            if 1 <= n <= MAX_NUM:
                last_seen[n] = idx
    length = len(recent)
    raw = {
        n: float((length - 1) - last_seen[n]) if n in last_seen else float(length)
        for n in range(1, MAX_NUM + 1)
    }
    return normalize_map(raw)


def compute_phase_maps(history: Sequence[Dict], window: int = 500) -> Tuple[Dict[int, float], Dict[int, float]]:
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    neutral = {n: 0.5 for n in range(1, MAX_NUM + 1)}
    if w < 50:
        return neutral, neutral

    phases = {}
    strength = {}
    for n in range(1, MAX_NUM + 1):
        bh = np.array([1.0 if n in d["numbers"][:PICK] else 0.0 for d in h], dtype=float)
        if bh.sum() < 2:
            phases[n] = 0.5
            strength[n] = 0.0
            continue
        yf = np.fft.fft(bh - np.mean(bh))
        xf = np.fft.fftfreq(w, 1.0)
        pos_idx = np.where(xf > 0)[0]
        if len(pos_idx) == 0:
            phases[n] = 0.5
            strength[n] = 0.0
            continue
        pos_xf = xf[pos_idx]
        pos_yf = np.abs(yf[pos_idx])
        peak_idx = int(np.argmax(pos_yf))
        freq_val = float(pos_xf[peak_idx])
        if freq_val <= 0:
            phases[n] = 0.5
            strength[n] = 0.0
            continue
        period = 1.0 / freq_val
        hits = np.where(bh == 1)[0]
        last_hit = int(hits[-1])
        gap = (w - 1) - last_hit
        phase = float((gap % period) / period) if period > 1e-9 else 0.5
        phases[n] = phase
        strength[n] = float(pos_yf[peak_idx])

    base_bets, _, _, _, _, _ = build_pp3(list(history))
    core_nums = sorted(set().union(*map(set, base_bets[:2])))
    angles = np.array([2 * np.pi * phases[n] for n in core_nums], dtype=float)
    core_angle = float(np.angle(np.mean(np.exp(1j * angles))))
    if core_angle < 0:
        core_angle += 2 * np.pi
    core_phase = core_angle / (2 * np.pi)

    phase_div = {}
    for n in range(1, MAX_NUM + 1):
        dist = abs(phases[n] - core_phase)
        circular = min(dist, 1.0 - dist)
        phase_div[n] = circular / 0.5 if 0.5 > 1e-9 else 0.5

    return normalize_map(phase_div), normalize_map(strength)


def pp3_strata_map(history: Sequence[Dict]) -> Dict[int, float]:
    bets, used, _, f_ranked, _, _ = build_pp3(list(history))
    ranked_all = [int(n) for n in f_ranked if 1 <= int(n) <= MAX_NUM]
    residual = [n for n in ranked_all if n not in used]
    bet1, bet2, bet3 = [set(bet) for bet in bets]
    strata = {}
    residual_top6 = set(residual[:6])
    residual_next6 = set(residual[6:12])
    residual_rest = set(residual[12:])
    for n in range(1, MAX_NUM + 1):
        if n in bet1:
            strata[n] = 1.0
        elif n in bet2:
            strata[n] = 0.85
        elif n in bet3:
            strata[n] = 0.68
        elif n in residual_top6:
            strata[n] = 0.52
        elif n in residual_next6:
            strata[n] = 0.36
        elif n in residual_rest:
            strata[n] = 0.22
        else:
            strata[n] = 0.22
    return strata


def midfreq_windows(history: Sequence[Dict]) -> Dict[str, Dict[int, float]]:
    return {
        "mf80": normalize_map(_midfreq_scores(list(history), window=80)),
        "mf160": normalize_map(_midfreq_scores(list(history), window=160)),
        "mf320": normalize_map(_midfreq_scores(list(history), window=320)),
    }


def rank_positions(score_map: Dict[int, float]) -> Dict[int, int]:
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda n: (-score_map[n], n))
    return {n: idx for idx, n in enumerate(ranked)}


def residual_stability_map(mf_maps: Dict[str, Dict[int, float]]) -> Dict[int, float]:
    raw = {}
    for n in range(1, MAX_NUM + 1):
        values = [mf_maps[key][n] for key in ("mf80", "mf160", "mf320")]
        raw[n] = 1.0 - float(np.std(values))
    return normalize_map(raw)


def consistency_guard_map(mf_maps: Dict[str, Dict[int, float]]) -> Dict[int, float]:
    ranks = {key: rank_positions(score_map) for key, score_map in mf_maps.items()}
    raw = {}
    for n in range(1, MAX_NUM + 1):
        positions = [ranks[key][n] / (MAX_NUM - 1) for key in ("mf80", "mf160", "mf320")]
        raw[n] = 1.0 - float(np.std(positions))
    return normalize_map(raw)


def feature_bundle(history: Sequence[Dict]) -> Dict:
    mf_maps = midfreq_windows(history)
    phase_div, phase_strength = compute_phase_maps(history, window=500)
    cold100 = normalize_map(recent_frequency_map(history, 100), reverse=True)
    gap120 = gap_map(history, window=120)
    strata = pp3_strata_map(history)
    stability = residual_stability_map(mf_maps)
    consistency = consistency_guard_map(mf_maps)
    return {
        **mf_maps,
        "pp3_strata": strata,
        "stability": stability,
        "consistency": consistency,
        "phase_divergence": phase_div,
        "phase_strength": phase_strength,
        "cold100": cold100,
        "gap120": gap120,
    }


CANDIDATE_FAMILIES = [
    {
        "family": "residual_strata",
        "score_name": "pp3_midfreq_residual_strata",
        "formula": (
            "0.42*mf160 + 0.24*pp3_strata + 0.18*stability + "
            "0.10*consistency + 0.06*phase_divergence"
        ),
        "weights": {
            "mf160": 0.42,
            "pp3_strata": 0.24,
            "stability": 0.18,
            "consistency": 0.10,
            "phase_divergence": 0.06,
        },
        "thesis": (
            "Use coarse PP3 residual strata plus MidFreq stability to fill the orthogonal slot "
            "without copying fourier residual ranking."
        ),
    },
    {
        "family": "stability_phase",
        "score_name": "pp3_midfreq_stability_phase",
        "formula": (
            "0.28*mf80 + 0.24*mf320 + 0.22*stability + "
            "0.16*phase_divergence + 0.10*cold100"
        ),
        "weights": {
            "mf80": 0.28,
            "mf320": 0.24,
            "stability": 0.22,
            "phase_divergence": 0.16,
            "cold100": 0.10,
        },
        "thesis": (
            "Reward numbers that stay mid-frequency across short/long windows, then use phase "
            "divergence only as an orthogonal tie-breaker."
        ),
    },
    {
        "family": "consistency_guard",
        "score_name": "pp3_midfreq_consistency_guard",
        "formula": (
            "0.34*mf160 + 0.24*consistency + 0.18*stability + "
            "0.14*phase_divergence + 0.10*pp3_strata"
        ),
        "weights": {
            "mf160": 0.34,
            "consistency": 0.24,
            "stability": 0.18,
            "phase_divergence": 0.14,
            "pp3_strata": 0.10,
        },
        "thesis": (
            "Penalize cross-window rank drift first, then keep only enough PP3 residual context "
            "to avoid collapsing back into the old Fourier order."
        ),
    },
]


def combine_features(bundle: Dict, weights: Dict[str, float]) -> Dict[int, float]:
    raw = {
        n: sum(weights[name] * bundle[name][n] for name in weights)
        for n in range(1, MAX_NUM + 1)
    }
    return normalize_map(raw)


def top6(scores: Dict[int, float], exclude: Sequence[int]) -> List[int]:
    excluded = set(exclude)
    ranked = sorted(
        (n for n in range(1, MAX_NUM + 1) if n not in excluded),
        key=lambda n: (-scores[n], n),
    )
    return sorted(ranked[:PICK])


def ticket_score(ticket: Sequence[int], score_map: Dict[int, float]) -> float:
    return float(np.mean([score_map[n] for n in ticket]))


def build_candidate4(history: Sequence[Dict], family: Dict) -> Tuple[List[List[int]], Dict]:
    base_bets, used, _, _, _, _ = build_pp3(list(history))
    bundle = feature_bundle(history)
    score_map = combine_features(bundle, family["weights"])
    bet4 = top6(score_map, used)
    meta = {
        "score_map": score_map,
        "feature_bundle": bundle,
        "bet4": bet4,
        "bet4_score": round(ticket_score(bet4, score_map), 6),
    }
    return base_bets + [bet4], meta


def predictor_4bet_factory(family: Dict) -> Callable[[Sequence[Dict]], List[List[int]]]:
    def predictor(history: Sequence[Dict]) -> List[List[int]]:
        bets, _ = build_candidate4(history, family)
        return bets

    return predictor


def predictor_3bet_factory(family: Dict) -> Callable[[Sequence[Dict]], List[List[int]]]:
    def predictor(history: Sequence[Dict]) -> List[List[int]]:
        bets4, meta = build_candidate4(history, family)
        score_map = meta["score_map"]
        core_scores = [(idx, ticket_score(bet, score_map)) for idx, bet in enumerate(bets4[:3])]
        keep = sorted(core_scores, key=lambda row: (row[1], -row[0]), reverse=True)[:2]
        keep_indices = sorted(idx for idx, _ in keep)
        return [bets4[idx] for idx in keep_indices] + [bets4[3]]

    return predictor


def fourier_3bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return fourier_rhythm_predict(list(history), n_bets=3, window=500)


def pp3_freqort_4bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return generate_orthogonal_5bet(list(history))[:4]


def evaluate_targets(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    records = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        bets = predictor(history)
        actual = set(target["numbers"])
        per_bet_hits = [len(set(bet) & actual) >= MATCH_TH for bet in bets]
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "bets": bets,
                "actual": target["numbers"],
                "per_bet_hits": per_bet_hits,
                "hit": any(per_bet_hits),
            }
        )
    return {
        "records": records,
        "hits": sum(1 for row in records if row["hit"]),
        "periods": len(records),
    }


def summarize_window(evaluation: Dict, n_bets: int) -> Dict:
    periods = evaluation["periods"]
    hits = evaluation["hits"]
    hit_rate = hits / periods if periods else 0.0
    edge = hit_rate - BASELINES[n_bets]
    per_bet_hit_rates = []
    per_bet_edges = []
    if periods:
        for bet_idx in range(n_bets):
            rate = sum(row["per_bet_hits"][bet_idx] for row in evaluation["records"]) / periods
            per_bet_hit_rates.append(rate)
            per_bet_edges.append(rate - BASELINES[1])
    strongest = max(per_bet_hit_rates) if per_bet_hit_rates else 0.0
    weakest = min(per_bet_hit_rates) if per_bet_hit_rates else 0.0
    efficiency_pct = (weakest / strongest * 100.0) if strongest > 0 else 0.0
    return {
        "periods": periods,
        "hits": hits,
        "hit_rate": round(hit_rate, 6),
        "hit_rate_pct": round(hit_rate * 100.0, 2),
        "edge": round(edge, 6),
        "edge_pct": round(edge * 100.0, 2),
        "sharpe_bernoulli": round(bernoulli_sharpe(hit_rate, edge), 4),
        "per_bet_hit_rates": [round(rate, 6) for rate in per_bet_hit_rates],
        "per_bet_hit_rate_pct": [round(rate * 100.0, 2) for rate in per_bet_hit_rates],
        "per_bet_edges": [round(e_i, 6) for e_i in per_bet_edges],
        "per_bet_edge_pct": [round(e_i * 100.0, 2) for e_i in per_bet_edges],
        "per_bet_marginal_efficiency_pct": round(efficiency_pct, 2),
        "per_bet_marginal_efficiency_pass": efficiency_pct > 80.0,
        "start_draw": evaluation["records"][0]["draw"],
        "end_draw": evaluation["records"][-1]["draw"],
    }


def fixed_prediction_permutation(
    records: Sequence[Dict],
    baseline: float,
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    actuals = np.zeros((len(records), MAX_NUM), dtype=bool)
    for row_idx, rec in enumerate(records):
        for n in rec["actual"]:
            actuals[row_idx, n - 1] = True

    def eval_edge(actual_matrix: np.ndarray) -> Tuple[int, float, float]:
        hits = 0
        for i, rec in enumerate(records):
            is_hit = any(
                sum(actual_matrix[i, num - 1] for num in bet) >= MATCH_TH
                for bet in rec["bets"]
            )
            hits += int(is_hit)
        rate = hits / len(records) if records else 0.0
        return hits, rate, rate - baseline

    real_hits, real_rate, real_edge = eval_edge(actuals)
    rng = np.random.RandomState(seed)
    shuffle_edges = []
    exceed = 0
    for _ in range(n_perm):
        shuffled = actuals[rng.permutation(len(records))]
        _, _, s_edge = eval_edge(shuffled)
        shuffle_edges.append(s_edge)
        if s_edge >= real_edge:
            exceed += 1

    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges))
    denom = shuffle_std if shuffle_std > 1e-9 else 1e-9
    p_emp = (exceed + 1) / (n_perm + 1)
    cohens_d = (real_edge - shuffle_mean) / denom
    return {
        "n_oos": len(records),
        "real_hits": real_hits,
        "real_rate": round(real_rate, 6),
        "real_rate_pct": round(real_rate * 100.0, 2),
        "real_edge": round(real_edge, 6),
        "real_edge_pct": round(real_edge * 100.0, 2),
        "shuffle_mean": round(shuffle_mean, 6),
        "shuffle_mean_pct": round(shuffle_mean * 100.0, 2),
        "shuffle_std": round(shuffle_std, 6),
        "shuffle_std_pct": round(shuffle_std * 100.0, 2),
        "p_emp": round(p_emp, 4),
        "cohens_d": round(cohens_d, 3),
        "z_score": round(cohens_d, 3),
        "verdict": (
            "SIGNAL_DETECTED"
            if p_emp < 0.05
            else ("MARGINAL" if p_emp < 0.10 else "NO_SIGNAL")
        ),
    }


def mcnemar_against_reference(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    candidate_predictor: Callable[[Sequence[Dict]], List[List[int]]],
    reference_predictor: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    cand_hits = []
    ref_hits = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        actual = set(target["numbers"])
        cand_bets = candidate_predictor(history)
        ref_bets = reference_predictor(history)
        cand_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in cand_bets))
        ref_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in ref_bets))

    b = sum(1 for c, r in zip(cand_hits, ref_hits) if c and not r)
    c = sum(1 for c, r in zip(cand_hits, ref_hits) if not c and r)
    a = sum(1 for c, r in zip(cand_hits, ref_hits) if c and r)
    d = sum(1 for c, r in zip(cand_hits, ref_hits) if not c and not r)
    discordant = b + c
    if discordant == 0:
        return {
            "status": "IDENTICAL",
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "discordant": discordant,
            "chi2": 0.0,
            "p_value": 1.0,
            "net": 0,
            "replace_recommendation": "keep",
            "pass": False,
        }

    chi2_val = (abs(b - c) - 1) ** 2 / discordant
    p_value = float(1.0 - chi2.cdf(chi2_val, df=1))
    return {
        "status": "COMPUTED",
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "discordant": discordant,
        "chi2": round(float(chi2_val), 4),
        "p_value": round(p_value, 4),
        "net": b - c,
        "replace_recommendation": "replace" if p_value < 0.05 and b > c else "keep",
        "pass": p_value < 0.05 and b > c,
    }


def run_leakage_check() -> Dict:
    proc = subprocess.run(
        [sys.executable, LEAKAGE_TOOL],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = "PASS" if proc.returncode == 0 and "✅ 所有測試案例通過" in proc.stdout else "FAIL"
    return {
        "status": status,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def orthogonality_snapshot(draws: Sequence[Dict], family: Dict) -> Dict:
    sample_indices = list(range(max(MIN_HISTORY, len(draws) - 500), len(draws), 10))
    spearman_vals = []
    jaccard_vals = []
    phase_vals = []
    top_numbers = Counter()
    for idx in sample_indices:
        history = draws[:idx]
        bets, meta = build_candidate4(history, family)
        score_map = meta["score_map"]
        bundle = meta["feature_bundle"]
        used = set().union(*map(set, bets[:3]))
        residual = [n for n in range(1, MAX_NUM + 1) if n not in used]
        residual_scores = np.array([score_map[n] for n in residual], dtype=float)
        strata_scores = np.array([bundle["pp3_strata"][n] for n in residual], dtype=float)
        if residual_scores.std() > 1e-9 and strata_scores.std() > 1e-9:
            spearman_vals.append(
                float(
                    np.corrcoef(
                        np.argsort(np.argsort(residual_scores)),
                        np.argsort(np.argsort(strata_scores)),
                    )[0, 1]
                )
            )
        top_nums = top6(score_map, used)
        for n in top_nums:
            top_numbers[n] += 1
        jaccard_vals.append(len(set(top_nums) & used) / len(set(top_nums) | used))
        phase_vals.append(float(np.mean([bundle["phase_divergence"][n] for n in top_nums])))
    return {
        "mean_rank_correlation_vs_pp3_strata": round(float(np.mean(spearman_vals)) if spearman_vals else 0.0, 4),
        "mean_jaccard_vs_pp3_core": round(float(np.mean(jaccard_vals)) if jaccard_vals else 0.0, 4),
        "mean_phase_divergence_top6": round(float(np.mean(phase_vals)) if phase_vals else 0.0, 4),
        "most_common_top_numbers": [n for n, _ in top_numbers.most_common(10)],
    }


def sample_feature_rows(draws: Sequence[Dict], family: Dict) -> Dict:
    history = draws[:-1]
    bets, meta = build_candidate4(history, family)
    bundle = meta["feature_bundle"]
    score_map = meta["score_map"]
    used = set().union(*map(set, bets[:3]))
    candidates = sorted(
        (n for n in range(1, MAX_NUM + 1) if n not in used),
        key=lambda n: (-score_map[n], n),
    )[:10]
    rows = []
    for n in candidates:
        row = {"number": n, "final_score": round(score_map[n], 6)}
        for key in family["weights"]:
            row[key] = round(bundle[key][n], 6)
        rows.append(row)
    return {
        "pp3_core": bets[:3],
        "candidate_bet4": bets[3],
        "top_residual_numbers": rows,
    }


def candidate_blockers(candidate: Dict) -> List[Dict]:
    blockers = []
    for window_name in ("recent_150", "recent_500", "recent_1500"):
        win = candidate["windows"][window_name]
        perm = candidate["permutation_tests"][window_name]
        if win["edge"] <= 0:
            blockers.append(
                {
                    "window": window_name,
                    "gate": "edge_positive",
                    "value": win["edge_pct"],
                    "fail_margin": round(abs(win["edge_pct"]), 2),
                    "message": f"{window_name}: edge={win['edge_pct']:+.2f}% <= 0",
                }
            )
        if perm["p_emp"] >= 0.05:
            blockers.append(
                {
                    "window": window_name,
                    "gate": "permutation",
                    "value": perm["p_emp"],
                    "fail_margin": round(perm["p_emp"] - 0.05, 4),
                    "message": f"{window_name}: permutation p={perm['p_emp']:.4f} >= 0.05",
                }
            )
        if perm["cohens_d"] <= 1.0:
            blockers.append(
                {
                    "window": window_name,
                    "gate": "cohens_d",
                    "value": perm["cohens_d"],
                    "fail_margin": round(1.0 - perm["cohens_d"], 3),
                    "message": f"{window_name}: Cohen's d={perm['cohens_d']:.3f} <= 1.0",
                }
            )
        if not win["per_bet_marginal_efficiency_pass"]:
            blockers.append(
                {
                    "window": window_name,
                    "gate": "per_bet_efficiency",
                    "value": win["per_bet_marginal_efficiency_pct"],
                    "fail_margin": round(80.0 - win["per_bet_marginal_efficiency_pct"], 2),
                    "message": (
                        f"{window_name}: per-bet efficiency="
                        f"{win['per_bet_marginal_efficiency_pct']:.1f}% <= 80%"
                    ),
                }
            )
    if candidate["leakage_check"] != "PASS":
        blockers.append(
            {
                "window": "all",
                "gate": "leakage",
                "value": candidate["leakage_check"],
                "fail_margin": 1.0,
                "message": "all: leakage check failed",
            }
        )
    blockers.sort(key=lambda row: row["fail_margin"], reverse=True)
    return blockers[:3]


def verdict_for_candidate(candidate: Dict) -> str:
    windows = candidate["windows"]
    perms = candidate["permutation_tests"]
    edge_pass = all(windows[name]["edge"] > 0 for name in windows)
    perm_pass = all(perms[name]["p_emp"] < 0.05 for name in perms)
    d_pass = all(perms[name]["cohens_d"] > 1.0 for name in perms)
    efficiency_pass = all(windows[name]["per_bet_marginal_efficiency_pass"] for name in windows)
    leakage_pass = candidate["leakage_check"] == "PASS"
    if edge_pass and perm_pass and d_pass and efficiency_pass and leakage_pass:
        return "PASS_TO_MCNEMAR"
    if edge_pass and (
        any(perms[name]["p_emp"] < 0.10 for name in perms)
        or any(perms[name]["cohens_d"] > 0.8 for name in perms)
    ):
        return "WATCH"
    return "REJECT"


def overall_family_verdict(candidates: Sequence[Dict]) -> str:
    verdicts = {cand["verdict"] for cand in candidates}
    if "PASS_TO_MCNEMAR" in verdicts:
        return "PASS_TO_MCNEMAR"
    if "WATCH" in verdicts:
        return "WATCH"
    return "REJECT"


def build_completed_markdown(payload: Dict) -> str:
    best = payload["best_candidate"]
    lines = [
        "# POWER_LOTTO PP3 + MidFreq orthogonal V2 validation (2026-04-23)",
        "",
        f"- Family verdict: **{payload['family_verdict']}**",
        f"- Best candidate: `{best['name']}` ({best['num_bets']}bet, **{best['verdict']}**)",
        (
            f"- Best 150/500/1500 Edge: {best['windows']['recent_150']['edge_pct']:+.2f}% / "
            f"{best['windows']['recent_500']['edge_pct']:+.2f}% / "
            f"{best['windows']['recent_1500']['edge_pct']:+.2f}%"
        ),
        (
            f"- Best 150/500/1500 perm p: {best['permutation_tests']['recent_150']['p_emp']:.4f} / "
            f"{best['permutation_tests']['recent_500']['p_emp']:.4f} / "
            f"{best['permutation_tests']['recent_1500']['p_emp']:.4f}"
        ),
        (
            f"- Best 150/500/1500 Cohen's d: "
            f"{best['permutation_tests']['recent_150']['cohens_d']:.3f} / "
            f"{best['permutation_tests']['recent_500']['cohens_d']:.3f} / "
            f"{best['permutation_tests']['recent_1500']['cohens_d']:.3f}"
        ),
        (
            f"- Best per-bet efficiency: {best['windows']['recent_150']['per_bet_marginal_efficiency_pct']:.1f}% / "
            f"{best['windows']['recent_500']['per_bet_marginal_efficiency_pct']:.1f}% / "
            f"{best['windows']['recent_1500']['per_bet_marginal_efficiency_pct']:.1f}%"
        ),
        f"- Leakage check: {payload['leakage_check']['status']}",
        (
            "- Failure-aware scope note: this round does **not** rerun Winning Quality P2-1, "
            "special V3/V4 reorder, or midfreq regime-gate tweaks because those families are "
            "already documented as blocked / rejected in trusted wiki + lessons; V2 only tests a "
            "new PP3+MidFreq orthogonal feature family."
        ),
    ]
    if payload["pass_to_mcnemar"]:
        lines.append("- PASS_TO_MCNEMAR candidates:")
        for cand in payload["pass_to_mcnemar"]:
            lines.append(
                f"  - `{cand['name']}` vs `{cand['mcnemar']['reference_strategy']}`: "
                f"p={cand['mcnemar']['p_value']:.4f}, recommendation={cand['mcnemar']['replace_recommendation']}"
            )
    else:
        lines.append("- No candidate cleared all gates; McNemar not triggered.")
        lines.append("- Top blockers:")
        for blocker in payload["global_top_blockers"]:
            lines.append(f"  - {blocker['candidate']}: {blocker['message']}")
    return "\n".join(lines)


def main() -> None:
    draws = load_draws()
    total_draws = len(draws)
    stage0 = load_stage0_metrics()
    windows = {
        "recent_150": list(range(max(MIN_HISTORY, total_draws - 150), total_draws)),
        "recent_500": list(range(max(MIN_HISTORY, total_draws - 500), total_draws)),
        "recent_1500": list(range(max(MIN_HISTORY, total_draws - 1500), total_draws)),
    }

    leakage_check = run_leakage_check()

    reference_windows = {
        "fourier_rhythm_3bet": {
            name: summarize_window(evaluate_targets(draws, indices, fourier_3bet_predictor), 3)
            for name, indices in windows.items()
        },
        "pp3_freqort_4bet": {
            name: summarize_window(evaluate_targets(draws, indices, pp3_freqort_4bet_predictor), 4)
            for name, indices in windows.items()
        },
    }

    candidates = []
    diagnostics = {
        "generated_at": now_iso_taipei(),
        "strategy_family": "power_pp3_midfreq_orthogonal_v2",
        "seed": SEED,
        "n_perm": N_PERM,
        "windows": list(windows.keys()),
        "candidate_diagnostics": {},
        "failure_aware_scope": {
            "not_rerun_wq": "Winning Quality P2-1 is intentionally skipped because the trusted backlog says this round must avoid repeated non-research blockers.",
            "not_rerun_special": "special V3/V4 same-family reorder is REJECT in trusted sources, so V2 does not retry that family.",
            "not_rerun_regime_gate": "midfreq 2bet regime gate is REJECT in trusted sources, so V2 avoids any same-family micro-tuning.",
        },
    }

    specs = []
    for family in CANDIDATE_FAMILIES:
        specs.append(
            {
                "name": f"{family['score_name']}_4bet",
                "family": family,
                "num_bets": 4,
                "reference_strategy": "pp3_freqort_4bet",
                "reference_predictor": pp3_freqort_4bet_predictor,
                "predictor": predictor_4bet_factory(family),
                "selection_rule": "PP3 base bets1-3 + new orthogonal bet4 from residual score map",
            }
        )
        specs.append(
            {
                "name": f"{family['score_name']}_3bet",
                "family": family,
                "num_bets": 3,
                "reference_strategy": "fourier_rhythm_3bet",
                "reference_predictor": fourier_3bet_predictor,
                "predictor": predictor_3bet_factory(family),
                "selection_rule": "Keep the two strongest PP3 core tickets under the new score map, then force-include the new orthogonal ticket as bet3",
            }
        )

    for spec in specs:
        evals = {
            window_name: evaluate_targets(draws, indices, spec["predictor"])
            for window_name, indices in windows.items()
        }
        summaries = {
            window_name: summarize_window(evals[window_name], spec["num_bets"])
            for window_name in windows
        }
        permutation_tests = {
            window_name: fixed_prediction_permutation(
                evals[window_name]["records"],
                BASELINES[spec["num_bets"]],
                N_PERM,
                SEED,
            )
            for window_name in windows
        }
        incumbent_vs_candidate = {
            window_name: {
                "candidate_edge_pct": summaries[window_name]["edge_pct"],
                "reference_edge_pct": reference_windows[spec["reference_strategy"]][window_name]["edge_pct"],
                "delta_edge_pct": round(
                    summaries[window_name]["edge_pct"]
                    - reference_windows[spec["reference_strategy"]][window_name]["edge_pct"],
                    2,
                ),
            }
            for window_name in windows
        }
        candidate = {
            "name": spec["name"],
            "num_bets": spec["num_bets"],
            "family": spec["family"]["family"],
            "formula": spec["family"]["formula"],
            "weights": spec["family"]["weights"],
            "thesis": spec["family"]["thesis"],
            "selection_rule": spec["selection_rule"],
            "reference_strategy": spec["reference_strategy"],
            "windows": summaries,
            "permutation_tests": permutation_tests,
            "reference_comparison": incumbent_vs_candidate,
            "leakage_check": leakage_check["status"],
        }
        candidate["verdict"] = verdict_for_candidate(candidate)
        if candidate["verdict"] == "PASS_TO_MCNEMAR":
            candidate["mcnemar"] = {
                **mcnemar_against_reference(
                    draws,
                    windows["recent_500"],
                    spec["predictor"],
                    spec["reference_predictor"],
                ),
                "reference_strategy": spec["reference_strategy"],
            }
        else:
            candidate["mcnemar"] = {
                "status": "SKIPPED",
                "reason": "full validation gates not passed",
                "reference_strategy": spec["reference_strategy"],
                "replace_recommendation": "keep",
                "pass": False,
            }
        candidate["top_blockers"] = candidate_blockers(candidate)
        candidates.append(candidate)

        diagnostics["candidate_diagnostics"][spec["name"]] = {
            "family": spec["family"]["family"],
            "num_bets": spec["num_bets"],
            "orthogonality_snapshot": orthogonality_snapshot(draws, spec["family"]),
            "sample_feature_rows": sample_feature_rows(draws, spec["family"]),
            "top_blockers": candidate["top_blockers"],
        }

    pass_to_mcnemar = [cand for cand in candidates if cand["verdict"] == "PASS_TO_MCNEMAR"]
    best_candidate = sorted(
        candidates,
        key=lambda cand: (
            cand["verdict"] == "PASS_TO_MCNEMAR",
            cand["verdict"] == "WATCH",
            cand["windows"]["recent_500"]["edge"],
            cand["permutation_tests"]["recent_500"]["cohens_d"],
        ),
        reverse=True,
    )[0]
    global_top_blockers = []
    for cand in candidates:
        for blocker in cand["top_blockers"]:
            global_top_blockers.append({"candidate": cand["name"], **blocker})
    global_top_blockers.sort(key=lambda row: row["fail_margin"], reverse=True)

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "strategy_family": "power_pp3_midfreq_orthogonal_v2",
        "seed": SEED,
        "n_perm": N_PERM,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "baseline": "analysis/results/stage0_baseline.json",
            "pp3_builder": "tools/backtest_power_4bet.py",
            "fourier_reference": "tools/power_fourier_rhythm.py",
            "pp3_freqort_reference": "tools/predict_power_orthogonal_5bet.py",
            "midfreq_reference": "tools/power_midfreq_fourier.py",
            "leakage_check": "tools/verify_no_data_leakage.py",
            "diagnostics": os.path.relpath(DIAG_PATH, PROJECT_ROOT),
        },
        "db_query": DB_QUERY,
        "draw_count_total": total_draws,
        "baselines": {str(n): round(BASELINES[n] * 100.0, 4) for n in BASELINES},
        "incumbent_reference": {
            "fourier_rhythm_3bet_stage0_edge_pct": stage0["fourier_rhythm_3bet"]["edge_pct"],
            "pp3_freqort_4bet_stage0_edge_pct": stage0["pp3_freqort_4bet"]["edge_pct"],
            "reference_windows": reference_windows,
        },
        "failure_aware_scope": diagnostics["failure_aware_scope"],
        "leakage_check": leakage_check,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "best_candidate": best_candidate,
        "pass_to_mcnemar": pass_to_mcnemar,
        "family_verdict": overall_family_verdict(candidates),
        "global_top_blockers": global_top_blockers[:5],
        "summary": {
            "candidate_verdicts": {cand["name"]: cand["verdict"] for cand in candidates},
            "pass_to_mcnemar_count": len(pass_to_mcnemar),
            "watch_count": sum(1 for cand in candidates if cand["verdict"] == "WATCH"),
            "reject_count": sum(1 for cand in candidates if cand["verdict"] == "REJECT"),
        },
        "changed_files_list": [
            "tools/research_power_pp3_midfreq_orthogonal_v2.py",
            f"analysis/results/power_pp3_midfreq_orthogonal_v2_{DATE_TAG}.json",
            f"analysis/results/power_pp3_midfreq_orthogonal_v2_diagnostics_{DATE_TAG}.json",
        ],
    }
    payload["completed_markdown"] = build_completed_markdown(payload)
    payload["task_result_json"] = {
        "strategy_family": payload["strategy_family"],
        "family_verdict": payload["family_verdict"],
        "candidate_verdicts": payload["summary"]["candidate_verdicts"],
        "pass_to_mcnemar": [
            {
                "name": cand["name"],
                "reference_strategy": cand["mcnemar"]["reference_strategy"],
                "p_value": cand["mcnemar"].get("p_value"),
                "replace_recommendation": cand["mcnemar"]["replace_recommendation"],
            }
            for cand in pass_to_mcnemar
        ],
        "top_blockers": [
            {"candidate": row["candidate"], "message": row["message"]}
            for row in payload["global_top_blockers"]
        ],
        "leakage_check": leakage_check["status"],
    }

    os.makedirs(os.path.dirname(DIAG_PATH), exist_ok=True)
    with open(DIAG_PATH, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(DIAG_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
