#!/usr/bin/env python3
"""
POWER_LOTTO WATCH downgrade / replacement validation (2026-04-23)
=================================================================

Scope:
1. Re-validate WATCH target `fourier_rhythm_3bet` on 150 / 500 / 1500 OOS windows.
2. Run failure-aware rolling stability on 5 non-overlapping 300-draw slices.
3. Re-check the only allowed alternative `pp3_freqort_3bet` (existing B-plan only)
   against `pp3_freqort_4bet` and against `fourier_rhythm_3bet` for promotion gates.
4. Emit orchestrator-ready JSON / Markdown artifacts without touching production state.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from tools.power_fourier_rhythm import fourier_rhythm_predict
from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
from tools.validate_power_pp3_freqort_3bet import candidate_b_score_blend

SEED = 42
N_PERM = 200
MIN_HISTORY = 100
MAX_NUM = 38
PICK = 6
MATCH_TH = 3
WINDOW_SPECS = {"recent_150": 150, "recent_500": 500, "recent_1500": 1500}
ROLLING_SLICE_LENGTH = 300
ROLLING_SLICE_COUNT = 5

DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
LEAKAGE_TOOL = os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")
RESULT_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_watch_downgrade_decision_20260423.json",
)
MARKDOWN_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_watch_downgrade_decision_20260423.md",
)
DIAG_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_watch_downgrade_diagnostics_20260423.json",
)
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)
CHANGED_FILES = [
    "analysis/results/power_watch_downgrade_decision_20260423.json",
    "analysis/results/power_watch_downgrade_decision_20260423.md",
    "analysis/results/power_watch_downgrade_diagnostics_20260423.json",
    "tools/validate_power_watch_downgrade_decision_20260423.py",
    "tests/test_power_watch_downgrade_decision_20260423.py",
    "wiki/games/power_lotto.md",
    "wiki/lessons/key_lessons.md",
    "memory/lessons.md",
]

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINE_1BET = P_SINGLE
BASELINE_3BET = 1 - (1 - P_SINGLE) ** 3
BASELINE_4BET = 1 - (1 - P_SINGLE) ** 4


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
    return sorted(desc_draws, key=lambda row: (row["date"], row["draw"]))


def load_stage0_metrics() -> Dict:
    with open(STAGE0_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["POWER_LOTTO"]["strategies"]


def validate_no_leakage(target_draw: Dict, history: Sequence[Dict]) -> None:
    if not history:
        return
    last = history[-1]
    if (last["date"], last["draw"]) >= (target_draw["date"], target_draw["draw"]):
        raise ValueError(
            f"Data leakage: history tail {last['draw']} >= target {target_draw['draw']}"
        )


def run_leakage_check() -> Dict:
    proc = subprocess.run(
        [sys.executable, LEAKAGE_TOOL],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    passed = proc.returncode == 0 and "✅ 所有測試案例通過" in proc.stdout
    return {
        "status": "PASS" if passed else "FAIL",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def fourier_3bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return fourier_rhythm_predict(list(history), n_bets=3, window=500)


def pp3_freqort_3bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return candidate_b_score_blend(list(history))


def pp3_freqort_4bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return generate_orthogonal_5bet(list(history))[:4]


def bernoulli_sharpe(hit_rate: float, edge: float) -> float:
    variance = max(hit_rate * (1.0 - hit_rate), 1e-9)
    return edge / math.sqrt(variance)


def evaluate_strategy(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
    num_bets: int,
) -> List[Dict]:
    records = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        bets = predictor(history)
        actual = set(target["numbers"])
        per_bet_hits = []
        for bet_idx in range(num_bets):
            hit = len(set(bets[bet_idx]) & actual) >= MATCH_TH
            per_bet_hits.append(bool(hit))
        overall_hit = any(per_bet_hits)
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "actual": target["numbers"],
                "bets": [sorted(bet) for bet in bets[:num_bets]],
                "per_bet_hits": per_bet_hits,
                "hit": overall_hit,
            }
        )
    return records


def _max_drawdown_from_returns(excess_returns: Sequence[float]) -> Tuple[float, int]:
    cumulative = np.cumsum(np.array(excess_returns, dtype=float))
    running_peak = np.maximum.accumulate(np.concatenate(([0.0], cumulative[:-1] if len(cumulative) else [])))
    if len(cumulative) == 0:
        return 0.0, 0

    max_drawdown = 0.0
    max_drawdown_draws = 0
    peak_idx = 0
    current_peak = 0.0
    for idx, value in enumerate(cumulative):
        if value >= current_peak:
            current_peak = value
            peak_idx = idx
            continue
        drawdown = current_peak - value
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_draws = idx - peak_idx
    return max_drawdown, max_drawdown_draws


def summarize_records(records: Sequence[Dict], baseline: float, num_bets: int) -> Dict:
    periods = len(records)
    hits = sum(1 for row in records if row["hit"])
    hit_rate = hits / periods if periods else 0.0
    edge = hit_rate - baseline
    excess_returns = [1.0 - baseline if row["hit"] else -baseline for row in records]
    max_drawdown, max_drawdown_draws = _max_drawdown_from_returns(excess_returns)

    per_bet_hit_rates = []
    per_bet_edges = []
    if periods:
        for bet_idx in range(num_bets):
            bet_rate = sum(row["per_bet_hits"][bet_idx] for row in records) / periods
            per_bet_hit_rates.append(bet_rate)
            per_bet_edges.append(bet_rate - BASELINE_1BET)

    return {
        "periods": periods,
        "hits": hits,
        "hit_rate": round(hit_rate, 6),
        "hit_rate_pct": round(hit_rate * 100.0, 2),
        "win_rate": round(hit_rate, 6),
        "win_rate_pct": round(hit_rate * 100.0, 2),
        "edge": round(edge, 6),
        "edge_pct": round(edge * 100.0, 2),
        "sharpe_bernoulli": round(bernoulli_sharpe(hit_rate, edge), 4),
        "max_drawdown": round(max_drawdown, 6),
        "max_drawdown_pct_points": round(max_drawdown * 100.0, 2),
        "max_drawdown_draws": int(max_drawdown_draws),
        "per_bet_hit_rates": [round(rate, 6) for rate in per_bet_hit_rates],
        "per_bet_hit_rate_pct": [round(rate * 100.0, 2) for rate in per_bet_hit_rates],
        "per_bet_edges": [round(edge_i, 6) for edge_i in per_bet_edges],
        "per_bet_edge_pct": [round(edge_i * 100.0, 2) for edge_i in per_bet_edges],
        "start_draw": records[0]["draw"] if records else None,
        "end_draw": records[-1]["draw"] if records else None,
    }


def fixed_prediction_permutation(
    records: Sequence[Dict],
    baseline: float,
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    actuals = np.zeros((len(records), MAX_NUM), dtype=bool)
    for row_idx, rec in enumerate(records):
        for number in rec["actual"]:
            actuals[row_idx, number - 1] = True

    def eval_edge(actual_matrix: np.ndarray) -> Tuple[int, float, float]:
        hits = 0
        for i, rec in enumerate(records):
            hit = any(
                sum(actual_matrix[i, number - 1] for number in bet) >= MATCH_TH
                for bet in rec["bets"]
            )
            hits += int(hit)
        rate = hits / len(records) if records else 0.0
        return hits, rate, rate - baseline

    real_hits, real_rate, real_edge = eval_edge(actuals)

    rng = np.random.RandomState(seed)
    shuffle_edges = []
    exceed = 0
    for _ in range(n_perm):
        shuffled = actuals[rng.permutation(len(records))]
        _, _, shuffle_edge = eval_edge(shuffled)
        shuffle_edges.append(shuffle_edge)
        if shuffle_edge >= real_edge:
            exceed += 1

    shuffle_mean = float(np.mean(shuffle_edges)) if shuffle_edges else 0.0
    shuffle_std = float(np.std(shuffle_edges)) if shuffle_edges else 1e-9
    denom = shuffle_std if shuffle_std > 1e-9 else 1e-9
    p_emp = (exceed + 1) / (n_perm + 1)
    cohens_d = (real_edge - shuffle_mean) / denom

    return {
        "n_oos": len(records),
        "n_perm": n_perm,
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


def summarize_strategy_windows(
    records: Sequence[Dict],
    baseline: float,
    num_bets: int,
) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    windows = {}
    permutation = {}
    for name, size in WINDOW_SPECS.items():
        subset = list(records[-size:])
        windows[name] = summarize_records(subset, baseline, num_bets)
        permutation[name] = fixed_prediction_permutation(subset, baseline, N_PERM, SEED)
    return windows, permutation


def rolling_slice_bundle(
    records: Sequence[Dict],
    baseline: float,
    num_bets: int,
    slice_length: int = ROLLING_SLICE_LENGTH,
) -> List[Dict]:
    bundles = []
    slice_count = len(records) // slice_length
    for idx in range(slice_count):
        chunk = list(records[idx * slice_length : (idx + 1) * slice_length])
        summary = summarize_records(chunk, baseline, num_bets)
        perm = fixed_prediction_permutation(chunk, baseline, N_PERM, SEED)
        bundles.append(
            {
                "slice_id": f"slice_{idx + 1}",
                "slice_order": idx + 1,
                "periods": slice_length,
                "start_draw": chunk[0]["draw"],
                "end_draw": chunk[-1]["draw"],
                "summary": summary,
                "permutation": perm,
            }
        )
    return bundles


def summarize_rolling_slices(slices: Sequence[Dict]) -> Dict:
    edge_nonpositive = [sl["summary"]["edge"] <= 0 for sl in slices]
    perm_fail = [sl["permutation"]["p_emp"] >= 0.05 for sl in slices]
    d_fail = [sl["permutation"]["cohens_d"] <= 1.0 for sl in slices]

    def longest_run(flags: Sequence[bool]) -> int:
        best = 0
        current = 0
        for flag in flags:
            if flag:
                current += 1
                best = max(best, current)
            else:
                current = 0
        return best

    return {
        "slice_count": len(slices),
        "slice_length": ROLLING_SLICE_LENGTH,
        "positive_edge_slices": sum(1 for sl in slices if sl["summary"]["edge"] > 0),
        "nonpositive_edge_slices": sum(edge_nonpositive),
        "permutation_pass_slices": sum(1 for sl in slices if sl["permutation"]["p_emp"] < 0.05),
        "permutation_fail_slices": sum(perm_fail),
        "permutation_fail_ratio": round(sum(perm_fail) / len(slices), 3) if slices else 0.0,
        "cohens_d_fail_slices": sum(d_fail),
        "cohens_d_fail_ratio": round(sum(d_fail) / len(slices), 3) if slices else 0.0,
        "consecutive_nonpositive_edge_slices": longest_run(edge_nonpositive),
        "consecutive_permutation_fail_slices": longest_run(perm_fail),
        "latest_slice": {
            "slice_id": slices[-1]["slice_id"] if slices else None,
            "edge_pct": slices[-1]["summary"]["edge_pct"] if slices else None,
            "permutation_p": slices[-1]["permutation"]["p_emp"] if slices else None,
            "cohens_d": slices[-1]["permutation"]["cohens_d"] if slices else None,
        },
    }


def marginal_efficiency(
    candidate_edge: float,
    reference_edge: float,
    candidate_bets: int,
    reference_bets: int,
) -> Dict:
    edge_retention_pct = (candidate_edge / reference_edge * 100.0) if reference_edge > 0 else 0.0
    per_bet_efficiency_pct = (
        (candidate_edge / candidate_bets) / (reference_edge / reference_bets) * 100.0
        if reference_edge > 0
        else 0.0
    )
    return {
        "edge_retention_pct": round(edge_retention_pct, 2),
        "per_bet_efficiency_pct": round(per_bet_efficiency_pct, 2),
        "pass": per_bet_efficiency_pct > 80.0,
    }


def build_efficiency_block(
    candidate_windows: Dict[str, Dict],
    reference_windows: Dict[str, Dict],
) -> Dict[str, Dict]:
    return {
        name: marginal_efficiency(candidate_windows[name]["edge"], reference_windows[name]["edge"], 3, 4)
        for name in WINDOW_SPECS
    }


def build_not_triggered_mcnemar(reasons: Sequence[str]) -> Dict:
    reason = ", ".join(reason for reason in reasons if reason) or "preconditions not satisfied"
    return {
        "status": "NOT_TRIGGERED",
        "reason": reason,
        "p_value": None,
        "net": None,
        "pass": False,
    }


def mcnemar_from_records(candidate_records: Sequence[Dict], reference_records: Sequence[Dict]) -> Dict:
    candidate_hits = [bool(row["hit"]) for row in candidate_records]
    reference_hits = [bool(row["hit"]) for row in reference_records]
    a = sum(1 for c, r in zip(candidate_hits, reference_hits) if c and r)
    b = sum(1 for c, r in zip(candidate_hits, reference_hits) if c and not r)
    c = sum(1 for c, r in zip(candidate_hits, reference_hits) if not c and r)
    d = sum(1 for c, r in zip(candidate_hits, reference_hits) if not c and not r)
    discordant = b + c
    if discordant == 0:
        return {
            "status": "IDENTICAL",
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "discordant": 0,
            "chi2": 0.0,
            "p_value": 1.0,
            "net": 0,
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
        "pass": p_value < 0.05,
    }


def classify_candidate_status(
    windows: Dict[str, Dict],
    permutation: Dict[str, Dict],
    efficiency: Dict[str, Dict],
    leakage_status: str,
    mcnemar: Dict,
) -> Tuple[str, List[str]]:
    blockers = []
    edge_pass = all(windows[name]["edge"] > 0 for name in WINDOW_SPECS)
    perm_pass = all(permutation[name]["p_emp"] < 0.05 for name in WINDOW_SPECS)
    d_pass = all(permutation[name]["cohens_d"] > 1.0 for name in WINDOW_SPECS)
    efficiency_pass = all(efficiency[name]["pass"] for name in WINDOW_SPECS)
    leakage_pass = leakage_status == "PASS"

    if not leakage_pass:
        blockers.append("leakage check failed")
    for name in WINDOW_SPECS:
        if windows[name]["edge"] <= 0:
            blockers.append(f"{name} edge <= 0")
        if permutation[name]["p_emp"] >= 0.05:
            blockers.append(f"{name} permutation p >= 0.05")
        if permutation[name]["cohens_d"] <= 1.0:
            blockers.append(f"{name} Cohen's d <= 1.0")
        if not efficiency[name]["pass"]:
            blockers.append(f"{name} per-bet efficiency <= 80%")

    if edge_pass and perm_pass and d_pass and efficiency_pass and leakage_pass:
        if mcnemar.get("pass"):
            return "PASS", []
        blockers.append("McNemar p >= 0.05")
        return "WATCH", blockers

    if edge_pass and leakage_pass:
        return "WATCH", blockers
    return "REJECT", blockers


def determine_downgrade_action(
    target_windows: Dict[str, Dict],
    target_perm: Dict[str, Dict],
    rolling_summary: Dict,
) -> Dict:
    standard_perm_fail_windows = sum(
        1 for name in WINDOW_SPECS if target_perm[name]["p_emp"] >= 0.05
    )
    standard_nonpositive_windows = sum(
        1 for name in WINDOW_SPECS if target_windows[name]["edge"] <= 0
    )
    thresholds = {
        "slice_scheme": {
            "choice": "5x300_non_overlapping",
            "reason": (
                "5x300 covers the full latest 1500 OOS horizon while giving finer failure detection "
                "than 3x500 and still leaves >400 prior draws before the oldest slice."
            ),
        },
        "remove_from_main_watch": {
            "consecutive_nonpositive_edge_slices_min": 2,
            "nonpositive_edge_slices_min": 3,
            "standard_nonpositive_windows_min": 1,
        },
        "downweight_watch_priority": {
            "permutation_fail_ratio_min": 0.8,
            "cohens_d_fail_ratio_min": 0.8,
            "standard_permutation_fail_windows_min": 2,
        },
    }

    remove_reasons = []
    if rolling_summary["consecutive_nonpositive_edge_slices"] >= 2:
        remove_reasons.append(">=2 consecutive 300p slices with edge <= 0")
    if rolling_summary["nonpositive_edge_slices"] >= 3:
        remove_reasons.append(">=3/5 slices with edge <= 0")
    if standard_nonpositive_windows >= 1:
        remove_reasons.append("150/500/1500 has non-positive edge window")

    if remove_reasons:
        return {
            "status": "REJECT",
            "action": "REMOVE_FROM_MAIN_WATCH",
            "triggered": True,
            "trigger_reasons": remove_reasons,
            "thresholds": thresholds,
            "observed": {
                "standard_perm_fail_windows": standard_perm_fail_windows,
                "standard_nonpositive_windows": standard_nonpositive_windows,
                **rolling_summary,
            },
        }

    downweight_reasons = []
    if rolling_summary["permutation_fail_ratio"] >= 0.8:
        downweight_reasons.append(">=80% rolling slices fail permutation p < 0.05")
    if rolling_summary["cohens_d_fail_ratio"] >= 0.8:
        downweight_reasons.append(">=80% rolling slices fail Cohen's d > 1.0")
    if standard_perm_fail_windows >= 2:
        downweight_reasons.append(">=2 standard windows fail permutation gate")

    if downweight_reasons:
        return {
            "status": "WATCH",
            "action": "DOWNWEIGHT_WATCH_PRIORITY",
            "triggered": True,
            "trigger_reasons": downweight_reasons,
            "thresholds": thresholds,
            "observed": {
                "standard_perm_fail_windows": standard_perm_fail_windows,
                "standard_nonpositive_windows": standard_nonpositive_windows,
                **rolling_summary,
            },
        }

    return {
        "status": "WATCH",
        "action": "KEEP_CURRENT_WATCH_PRIORITY",
        "triggered": False,
        "trigger_reasons": [],
        "thresholds": thresholds,
        "observed": {
            "standard_perm_fail_windows": standard_perm_fail_windows,
            "standard_nonpositive_windows": standard_nonpositive_windows,
            **rolling_summary,
        },
    }


def select_planner_recommendation(target_action: str, candidate_status: str) -> str:
    if target_action == "DOWNWEIGHT_WATCH_PRIORITY" and candidate_status != "PASS":
        return (
            "POWER_LOTTO 新 Layer-1 3bet 訊號家族探索：避開 WQ / midfreq regime-gate / special V3-V4 / "
            "現有 PP3-FreqOrt 重排，直接尋找非同家族替代主線。"
        )
    if target_action == "REMOVE_FROM_MAIN_WATCH" and candidate_status != "PASS":
        return "POWER_LOTTO 重建 3bet 主監控池：優先新訊號源，不再延伸現有 WATCH 家族。"
    if candidate_status == "PASS":
        return "針對通過前置閘門的替代策略執行正式 replace-review 與部署前 McNemar。"
    return "維持現況監控，等待更多資料後複查。"


def build_completed_markdown(payload: Dict) -> str:
    target = payload["windows"]
    candidate = payload["candidate_windows"]
    candidate_eff = payload["efficiency"]["candidate_vs_pp3_freqort_4bet"]
    lines = [
        "# POWER_LOTTO WATCH downgrade decision (2026-04-23)",
        "",
        f"- Final status: **{payload['status']}**",
        f"- Target strategy: `{payload['target_strategy']}`",
        f"- Downgrade action: **{payload['decision_action']}**",
        f"- Replacement decision: **{payload['replacement_decision']}**",
        (
            f"- Target 150/500/1500 Edge: {target['recent_150']['edge_pct']:+.2f}% / "
            f"{target['recent_500']['edge_pct']:+.2f}% / {target['recent_1500']['edge_pct']:+.2f}%"
        ),
        (
            f"- Target 150/500/1500 permutation p: {payload['permutation']['target']['recent_150']['p_emp']:.4f} / "
            f"{payload['permutation']['target']['recent_500']['p_emp']:.4f} / "
            f"{payload['permutation']['target']['recent_1500']['p_emp']:.4f}"
        ),
        (
            f"- Rolling 5x300 target summary: {payload['rolling_oos_summary']['target']['summary']['positive_edge_slices']}/5 slices edge>0, "
            f"perm fail ratio={payload['rolling_oos_summary']['target']['summary']['permutation_fail_ratio']:.2f}, "
            f"max consecutive non-positive slices={payload['rolling_oos_summary']['target']['summary']['consecutive_nonpositive_edge_slices']}"
        ),
        (
            f"- Candidate `{payload['alternative_candidate']}` status: **{payload['candidate_status']}** "
            f"(150/500/1500 Edge {candidate['recent_150']['edge_pct']:+.2f}% / "
            f"{candidate['recent_500']['edge_pct']:+.2f}% / {candidate['recent_1500']['edge_pct']:+.2f}%)"
        ),
        (
            f"- Candidate efficiency vs `{payload['reference_strategy']}`: "
            f"{candidate_eff['recent_150']['per_bet_efficiency_pct']:.1f}% / "
            f"{candidate_eff['recent_500']['per_bet_efficiency_pct']:.1f}% / "
            f"{candidate_eff['recent_1500']['per_bet_efficiency_pct']:.1f}%"
        ),
        (
            "- McNemar: "
            + (
                f"p={payload['mcnemar']['p_value']:.4f}, net={payload['mcnemar']['net']:+d}"
                if payload["mcnemar"]["status"] == "COMPUTED"
                else f"{payload['mcnemar']['status']} ({payload['mcnemar']['reason']})"
            )
        ),
        f"- Leakage check: {payload['leakage_check']['status']}",
        f"- Planner recommendation: {payload['planner_recommendation']}",
        f"- Handoff notes: {payload['handoff_notes']}",
    ]
    return "\n".join(lines)


def build_payload() -> Tuple[Dict, Dict]:
    draws = load_draws()
    stage0 = load_stage0_metrics()
    total_draws = len(draws)
    recent_1500_indices = list(range(max(MIN_HISTORY, total_draws - 1500), total_draws))
    if len(recent_1500_indices) != 1500:
        raise ValueError("Expected exactly 1500 OOS targets for latest POWER_LOTTO window")

    target_records = evaluate_strategy(draws, recent_1500_indices, fourier_3bet_predictor, 3)
    candidate_records = evaluate_strategy(draws, recent_1500_indices, pp3_freqort_3bet_predictor, 3)
    reference_records = evaluate_strategy(draws, recent_1500_indices, pp3_freqort_4bet_predictor, 4)

    target_windows, target_perm = summarize_strategy_windows(target_records, BASELINE_3BET, 3)
    candidate_windows, candidate_perm = summarize_strategy_windows(candidate_records, BASELINE_3BET, 3)
    reference_windows, reference_perm = summarize_strategy_windows(reference_records, BASELINE_4BET, 4)

    target_slices = rolling_slice_bundle(target_records, BASELINE_3BET, 3)
    candidate_slices = rolling_slice_bundle(candidate_records, BASELINE_3BET, 3)
    reference_slices = rolling_slice_bundle(reference_records, BASELINE_4BET, 4)

    efficiency = {
        "candidate_vs_pp3_freqort_4bet": build_efficiency_block(candidate_windows, reference_windows),
        "target_vs_pp3_freqort_4bet": build_efficiency_block(target_windows, reference_windows),
    }

    leakage_check = run_leakage_check()
    candidate_gate_reasons = []
    if not all(candidate_windows[name]["edge"] > 0 for name in WINDOW_SPECS):
        candidate_gate_reasons.append("edge gate not fully passed")
    if not all(candidate_perm[name]["p_emp"] < 0.05 for name in WINDOW_SPECS):
        candidate_gate_reasons.append("permutation p gate not fully passed")
    if not all(candidate_perm[name]["cohens_d"] > 1.0 for name in WINDOW_SPECS):
        candidate_gate_reasons.append("Cohen's d gate not fully passed")
    if not all(efficiency["candidate_vs_pp3_freqort_4bet"][name]["pass"] for name in WINDOW_SPECS):
        candidate_gate_reasons.append("per-bet efficiency gate not fully passed")
    if leakage_check["status"] != "PASS":
        candidate_gate_reasons.append("leakage gate failed")

    if candidate_gate_reasons:
        mcnemar = build_not_triggered_mcnemar(candidate_gate_reasons)
    else:
        mcnemar = mcnemar_from_records(candidate_records, target_records)

    candidate_status, candidate_blockers = classify_candidate_status(
        candidate_windows,
        candidate_perm,
        efficiency["candidate_vs_pp3_freqort_4bet"],
        leakage_check["status"],
        mcnemar,
    )
    rolling_summary_target = summarize_rolling_slices(target_slices)
    rolling_summary_candidate = summarize_rolling_slices(candidate_slices)
    rolling_summary_reference = summarize_rolling_slices(reference_slices)
    downgrade_policy = determine_downgrade_action(target_windows, target_perm, rolling_summary_target)

    planner_recommendation = select_planner_recommendation(
        downgrade_policy["action"],
        candidate_status,
    )
    replacement_decision = "DO_NOT_REPLACE" if candidate_status != "PASS" else "ELIGIBLE_FOR_REVIEW"
    handoff_notes = (
        "updated wiki/games/power_lotto.md and wiki/lessons/key_lessons.md"
        if downgrade_policy["action"] != "KEEP_CURRENT_WATCH_PRIORITY"
        else "wiki 無需更新"
    )

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "status": downgrade_policy["status"],
        "decision_action": downgrade_policy["action"],
        "replacement_decision": replacement_decision,
        "target_strategy": "fourier_rhythm_3bet",
        "alternative_candidate": "pp3_freqort_3bet",
        "reference_strategy": "pp3_freqort_4bet",
        "seed": SEED,
        "n_perm": N_PERM,
        "db_query": DB_QUERY,
        "draw_count_total": total_draws,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "baseline": "analysis/results/stage0_baseline.json",
            "target_predictor": "tools/power_fourier_rhythm.py",
            "alternative_predictor": "tools/validate_power_pp3_freqort_3bet.py:candidate_b_score_blend",
            "reference_predictor": "tools/predict_power_orthogonal_5bet.py",
            "leakage_check": "tools/verify_no_data_leakage.py",
        },
        "baseline_reference": {
            "m3_plus_baseline_pct": round(BASELINE_3BET * 100.0, 2),
            "m4_plus_baseline_pct": round(BASELINE_4BET * 100.0, 2),
            "stage0_fourier_rhythm_3bet_edge_pct": stage0["fourier_rhythm_3bet"]["edge_pct"],
            "stage0_fourier_rhythm_3bet_sharpe": stage0["fourier_rhythm_3bet"]["sharpe_bernoulli"],
            "stage0_pp3_freqort_4bet_edge_pct": stage0["pp3_freqort_4bet"]["edge_pct"],
            "stage0_pp3_freqort_4bet_sharpe": stage0["pp3_freqort_4bet"]["sharpe_bernoulli"],
        },
        "windows": target_windows,
        "candidate_windows": candidate_windows,
        "reference_windows": reference_windows,
        "rolling_oos_summary": {
            "slice_design": downgrade_policy["thresholds"]["slice_scheme"],
            "target": {
                "strategy": "fourier_rhythm_3bet",
                "slices": target_slices,
                "summary": rolling_summary_target,
            },
            "candidate": {
                "strategy": "pp3_freqort_3bet",
                "slices": candidate_slices,
                "summary": rolling_summary_candidate,
            },
            "reference": {
                "strategy": "pp3_freqort_4bet",
                "slices": reference_slices,
                "summary": rolling_summary_reference,
            },
        },
        "permutation": {
            "target": target_perm,
            "candidate": candidate_perm,
            "reference": reference_perm,
        },
        "cohens_d": {
            "target": {name: target_perm[name]["cohens_d"] for name in WINDOW_SPECS},
            "candidate": {name: candidate_perm[name]["cohens_d"] for name in WINDOW_SPECS},
            "reference": {name: reference_perm[name]["cohens_d"] for name in WINDOW_SPECS},
        },
        "efficiency": efficiency,
        "leakage_check": leakage_check,
        "mcnemar": mcnemar,
        "candidate_status": candidate_status,
        "candidate_blockers": candidate_blockers,
        "downgrade_policy": downgrade_policy,
        "planner_recommendation": planner_recommendation,
        "task_result_json": {
            "target_status": downgrade_policy["status"],
            "target_action": downgrade_policy["action"],
            "candidate_status": candidate_status,
            "replacement_decision": replacement_decision,
            "planner_recommendation": planner_recommendation,
        },
        "changed_files_list": CHANGED_FILES,
        "handoff_notes": handoff_notes,
    }
    payload["completed_markdown"] = build_completed_markdown(payload)

    diagnostics = {
        "generated_at": payload["generated_at"],
        "lottery_type": payload["lottery_type"],
        "target_records_window_1500": {
            "periods": len(target_records),
            "start_draw": target_records[0]["draw"],
            "end_draw": target_records[-1]["draw"],
        },
        "candidate_records_window_1500": {
            "periods": len(candidate_records),
            "start_draw": candidate_records[0]["draw"],
            "end_draw": candidate_records[-1]["draw"],
        },
        "reference_records_window_1500": {
            "periods": len(reference_records),
            "start_draw": reference_records[0]["draw"],
            "end_draw": reference_records[-1]["draw"],
        },
        "target_slice_metrics": target_slices,
        "candidate_slice_metrics": candidate_slices,
        "reference_slice_metrics": reference_slices,
        "candidate_gate_reasons": candidate_gate_reasons,
        "candidate_blockers": candidate_blockers,
        "downgrade_policy": downgrade_policy,
    }
    return payload, diagnostics


def save_outputs(payload: Dict, diagnostics: Dict) -> None:
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(DIAG_PATH, "w", encoding="utf-8") as handle:
        json.dump(diagnostics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(MARKDOWN_PATH, "w", encoding="utf-8") as handle:
        handle.write(payload["completed_markdown"])
        handle.write("\n")


def main() -> None:
    payload, diagnostics = build_payload()
    save_outputs(payload, diagnostics)
    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(MARKDOWN_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(DIAG_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
