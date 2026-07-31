"""P2 — Baseline strategy ROI significance testing.

提供 bootstrap CI、paired test vs 0、paired test between strategies、fold-level
stability 等統計工具。所有計算排除 ambiguous_doubleheader=True 紀錄。

硬性約束：
- paper_only 永遠 True
- 不偽造 outcome
- n < 30 → 回傳 insufficient_sample sentinel
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

INSUFFICIENT_SAMPLE = "insufficient_sample"
MIN_SAMPLE = 30


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _eligible(records: List[dict]) -> List[dict]:
    """過濾出可進入 PnL 的紀錄。"""
    out = []
    for r in records:
        if r.get("ambiguous_doubleheader") is True:
            continue
        if r.get("pnl_eligible") is False:
            continue
        # 必須有 actual outcome
        if r.get("selected_side_win") is None:
            continue
        # 必須有 odds 計算的 stake / payout
        if r.get("stake_unit") is None:
            continue
        out.append(r)
    return out


def _american_to_decimal(am: float) -> float:
    if am is None:
        return 1.0
    if am >= 0:
        return 1.0 + am / 100.0
    return 1.0 + 100.0 / abs(am)


def _record_pnl_units(r: dict) -> float:
    """單筆紀錄相對於 stake_unit 的真實 PnL（單位：bankroll fraction）。
    win → stake*(decimal-1); lose → -stake
    """
    stake = float(r.get("stake_unit", 0.0) or 0.0)
    if stake <= 0:
        return 0.0
    side = (r.get("side") or r.get("bet_side") or "").upper()
    if side == "HOME":
        odds = r.get("home_ml_odds")
    elif side == "AWAY":
        odds = r.get("away_ml_odds")
    else:
        return 0.0
    if odds is None:
        return 0.0
    dec = _american_to_decimal(float(odds))
    win = int(r.get("selected_side_win") or 0) == 1
    return stake * (dec - 1.0) if win else -stake


def _record_pnl_ev_proxy(r: dict) -> float:
    """EV-proxy（基於 model_prob，非真實 outcome）— 僅供對照，不可用於決策。"""
    return float(r.get("ev", 0.0) or 0.0) * float(r.get("stake_unit", 0.0) or 0.0)


def _roi(records: List[dict]) -> Tuple[float, float, float, int]:
    """
    回傳 (roi, total_pnl, total_stake, n)
    roi = total_pnl / total_stake
    """
    n = len(records)
    total_pnl = 0.0
    total_stake = 0.0
    for r in records:
        stake = float(r.get("stake_unit", 0.0) or 0.0)
        total_stake += stake
        total_pnl += _record_pnl_units(r)
    roi = total_pnl / total_stake if total_stake > 0 else 0.0
    return roi, total_pnl, total_stake, n


# ══════════════════════════════════════════════════════════════════════════════
# Bootstrap CI for ROI
# ══════════════════════════════════════════════════════════════════════════════

def bootstrap_roi_ci(
    records: List[dict],
    n_boot: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict:
    """
    Bootstrap ROI 的 (point estimate, ci_low, ci_high)。
    n < MIN_SAMPLE → 回傳 insufficient_sample sentinel。
    """
    eligible = _eligible(records)
    n = len(eligible)
    if n < MIN_SAMPLE:
        return {
            "status": INSUFFICIENT_SAMPLE,
            "n": n,
            "min_required": MIN_SAMPLE,
        }
    roi, total_pnl, total_stake, _ = _roi(eligible)
    rng = random.Random(seed)
    boot_rois: List[float] = []
    indices = list(range(n))
    for _ in range(n_boot):
        sample = [eligible[rng.choice(indices)] for _ in range(n)]
        r_roi, _, _, _ = _roi(sample)
        boot_rois.append(r_roi)
    boot_rois.sort()
    alpha = (1.0 - ci) / 2.0
    lo = boot_rois[int(alpha * n_boot)]
    hi = boot_rois[int((1.0 - alpha) * n_boot) - 1]
    return {
        "status": "ok",
        "roi": round(roi, 6),
        "ci_low": round(lo, 6),
        "ci_high": round(hi, 6),
        "n": n,
        "total_pnl": round(total_pnl, 6),
        "total_stake": round(total_stake, 6),
        "n_boot": n_boot,
        "ci_level": ci,
        "paper_only": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Paired test vs zero
# ══════════════════════════════════════════════════════════════════════════════

def paired_test_vs_zero(records: List[dict], n_boot: int = 10000, seed: int = 42) -> Dict:
    """
    Bootstrap-based 雙尾 p-value: H0 true ROI = 0。
    n < MIN_SAMPLE → insufficient_sample。
    """
    eligible = _eligible(records)
    n = len(eligible)
    if n < MIN_SAMPLE:
        return {"status": INSUFFICIENT_SAMPLE, "n": n, "min_required": MIN_SAMPLE}

    roi_obs, _, _, _ = _roi(eligible)
    # 中心化 PnL，使 H0 成立（mean PnL per stake = 0）
    pnls = [_record_pnl_units(r) for r in eligible]
    stakes = [float(r.get("stake_unit", 0.0) or 0.0) for r in eligible]
    total_stake = sum(stakes)
    if total_stake <= 0:
        return {"status": INSUFFICIENT_SAMPLE, "n": n, "reason": "zero_total_stake"}
    mean_pnl_per_stake = sum(pnls) / total_stake
    # 對每筆做 demean：pnl_centered = pnl - stake * mean
    centered = [p - s * mean_pnl_per_stake for p, s in zip(pnls, stakes)]

    rng = random.Random(seed)
    indices = list(range(n))
    count_extreme = 0
    for _ in range(n_boot):
        sample_idx = [rng.choice(indices) for _ in range(n)]
        boot_pnl = sum(centered[i] for i in sample_idx)
        boot_stake = sum(stakes[i] for i in sample_idx)
        boot_roi = boot_pnl / boot_stake if boot_stake > 0 else 0.0
        if abs(boot_roi) >= abs(roi_obs):
            count_extreme += 1
    p_value = (count_extreme + 1) / (n_boot + 1)  # 加 1 避免 p=0
    return {
        "status": "ok",
        "roi_observed": round(roi_obs, 6),
        "p_value": round(p_value, 6),
        "n": n,
        "n_boot": n_boot,
        "h0": "true_roi_equals_zero",
        "paper_only": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Paired test between strategies
# ══════════════════════════════════════════════════════════════════════════════

def paired_test_strategies(records_a: List[dict], records_b: List[dict], n_boot: int = 10000, seed: int = 42) -> Dict:
    """
    H0: ROI_a == ROI_b。Bootstrap 雙尾。
    若任一邊 < MIN_SAMPLE → insufficient_sample。
    """
    a = _eligible(records_a)
    b = _eligible(records_b)
    if len(a) < MIN_SAMPLE or len(b) < MIN_SAMPLE:
        return {
            "status": INSUFFICIENT_SAMPLE,
            "n_a": len(a),
            "n_b": len(b),
            "min_required": MIN_SAMPLE,
        }
    roi_a, _, _, _ = _roi(a)
    roi_b, _, _, _ = _roi(b)
    diff_obs = roi_a - roi_b
    rng = random.Random(seed)
    ia, ib = list(range(len(a))), list(range(len(b)))
    cnt = 0
    for _ in range(n_boot):
        sa = [a[rng.choice(ia)] for _ in range(len(a))]
        sb = [b[rng.choice(ib)] for _ in range(len(b))]
        ra, _, _, _ = _roi(sa)
        rb, _, _, _ = _roi(sb)
        if abs(ra - rb) >= abs(diff_obs):
            cnt += 1
    # 注意：這是 percentile-style，未做 center；保守版本
    p_value = (cnt + 1) / (n_boot + 1)
    return {
        "status": "ok",
        "roi_a": round(roi_a, 6),
        "roi_b": round(roi_b, 6),
        "diff": round(diff_obs, 6),
        "p_value": round(p_value, 6),
        "n_a": len(a),
        "n_b": len(b),
        "paper_only": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Fold-level stability
# ══════════════════════════════════════════════════════════════════════════════

def fold_level_stability(records: List[dict]) -> Dict:
    """
    依 walk_forward_fold 分組，回傳 per-fold ROI 與整體 Sharpe-like。
    """
    eligible = _eligible(records)
    if len(eligible) < MIN_SAMPLE:
        return {"status": INSUFFICIENT_SAMPLE, "n": len(eligible), "min_required": MIN_SAMPLE}
    by_fold: Dict[int, List[dict]] = {}
    for r in eligible:
        f = r.get("walk_forward_fold")
        if f is None:
            continue
        by_fold.setdefault(int(f), []).append(r)
    per_fold = []
    fold_rois = []
    for f, rows in sorted(by_fold.items()):
        roi, pnl, stake, n = _roi(rows)
        per_fold.append({
            "fold": f,
            "n_bets": n,
            "roi": round(roi, 6),
            "total_pnl": round(pnl, 6),
            "total_stake": round(stake, 6),
        })
        fold_rois.append(roi)
    sharpe = None
    if len(fold_rois) >= 2:
        mu = statistics.mean(fold_rois)
        sd = statistics.pstdev(fold_rois)
        sharpe = (mu / sd) if sd > 0 else None
    return {
        "status": "ok",
        "n_folds": len(per_fold),
        "per_fold": per_fold,
        "fold_roi_mean": round(statistics.mean(fold_rois), 6) if fold_rois else None,
        "fold_roi_std": round(statistics.pstdev(fold_rois), 6) if fold_rois else None,
        "fold_sharpe": round(sharpe, 6) if sharpe is not None else None,
        "paper_only": True,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Hit rate & max drawdown
# ══════════════════════════════════════════════════════════════════════════════

def hit_rate(records: List[dict]) -> Optional[float]:
    eligible = _eligible(records)
    if not eligible:
        return None
    wins = sum(1 for r in eligible if int(r.get("selected_side_win") or 0) == 1)
    return round(wins / len(eligible), 6)


def max_drawdown(records: List[dict]) -> Optional[float]:
    eligible = _eligible(records)
    if not eligible:
        return None
    # 依 game_date 與 game_id 排序累積 PnL
    ordered = sorted(eligible, key=lambda r: (r.get("game_date", ""), r.get("game_id", "")))
    cum = 0.0
    peak = 0.0
    dd = 0.0
    for r in ordered:
        cum += _record_pnl_units(r)
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    return round(dd, 6)


# ══════════════════════════════════════════════════════════════════════════════
# Edge filter helper
# ══════════════════════════════════════════════════════════════════════════════

def filter_by_min_edge(records: List[dict], min_edge: float) -> List[dict]:
    """fixed-edge 策略：只保留 edge >= min_edge 的紀錄。"""
    return [r for r in records if float(r.get("edge", 0.0) or 0.0) >= min_edge]


# ══════════════════════════════════════════════════════════════════════════════
# All-in-one runner
# ══════════════════════════════════════════════════════════════════════════════

def run_significance_suite(
    records: List[dict],
    edge_thresholds: List[float],
    n_boot: int = 10000,
    seed: int = 42,
) -> Dict:
    """
    對多個 fixed_edge_*pct 策略一次跑 bootstrap CI + paired test vs zero + fold stability。
    """
    out: Dict[str, dict] = {}
    for thr in edge_thresholds:
        name = f"fixed_edge_{int(round(thr * 100))}pct"
        sub = filter_by_min_edge(records, thr)
        ci = bootstrap_roi_ci(sub, n_boot=n_boot, seed=seed)
        pv = paired_test_vs_zero(sub, n_boot=n_boot, seed=seed)
        stab = fold_level_stability(sub)
        entry = {
            "min_edge": thr,
            "n_after_filter": len(sub),
            "bootstrap_ci": ci,
            "paired_vs_zero": pv,
            "fold_stability": stab,
            "hit_rate": hit_rate(sub),
            "max_drawdown": max_drawdown(sub),
            "paper_only": True,
        }
        # significance flag
        if ci.get("status") == "ok" and pv.get("status") == "ok":
            entry["significant_at_5pct"] = bool(pv["p_value"] < 0.05 and ci["ci_low"] > 0)
        else:
            entry["significant_at_5pct"] = None
        out[name] = entry
    return out
