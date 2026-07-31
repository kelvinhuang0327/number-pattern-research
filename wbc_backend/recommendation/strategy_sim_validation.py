"""
P3: strategy_sim_v2 Brier/ECE 驗證模組
純函式設計，無副作用，可測試。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass
class BrierECEResult:
    total_rows: int
    joined_rows: int
    missing_result_rows: int
    brier_score: float
    ece: float
    accuracy: float
    coverage_rate: float
    gate_status: str  # "PASS" or "FAIL"
    reasons: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_brier_score(probs: List[float], outcomes: List[int]) -> float:
    """計算 Brier Score，outcomes 為 0/1。空清單回傳 nan。"""
    n = len(probs)
    if n == 0:
        return float("nan")
    if len(probs) != len(outcomes):
        raise ValueError("probs 與 outcomes 長度不符")
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / n


def assign_probability_bin(prob: float, n_bins: int = 10) -> int:
    """
    將機率值分到對應 bin（0-indexed）。
    prob=1.0 歸入最後一個 bin。
    """
    if n_bins <= 0:
        raise ValueError("n_bins 必須 > 0")
    if prob < 0.0 or prob > 1.0:
        raise ValueError(f"機率值 {prob} 超出 [0, 1] 範圍")
    bin_idx = int(prob * n_bins)
    return min(bin_idx, n_bins - 1)


def calculate_ece(probs: List[float], outcomes: List[int], n_bins: int = 10) -> float:
    """
    計算 Expected Calibration Error（等寬分箱，10 bins）。
    空清單回傳 nan。
    """
    n = len(probs)
    if n == 0:
        return float("nan")
    if len(probs) != len(outcomes):
        raise ValueError("probs 與 outcomes 長度不符")

    # 分箱
    bins: Dict[int, List] = {i: {"probs": [], "outcomes": []} for i in range(n_bins)}
    for p, o in zip(probs, outcomes):
        b = assign_probability_bin(p, n_bins)
        bins[b]["probs"].append(p)
        bins[b]["outcomes"].append(o)

    ece = 0.0
    for b_data in bins.values():
        nb = len(b_data["probs"])
        if nb == 0:
            continue
        avg_conf = sum(b_data["probs"]) / nb
        avg_acc = sum(b_data["outcomes"]) / nb
        ece += (nb / n) * abs(avg_conf - avg_acc)
    return ece


def validate_marl_gate(
    brier: float,
    ece: float,
    brier_threshold: float = 0.25,
    ece_threshold: float = 0.12,
) -> dict:
    """
    MARL 決策閘。
    PASS 條件：brier < brier_threshold 且 ece < ece_threshold。
    回傳 dict：gate_status, brier, ece, reasons
    """
    reasons: List[str] = []
    if math.isnan(brier) or math.isnan(ece):
        reasons.append("brier 或 ece 為 nan，資料不足")
        return {"gate_status": "FAIL", "brier": brier, "ece": ece, "reasons": reasons}

    if brier >= brier_threshold:
        reasons.append(
            f"Brier Score {brier:.4f} >= 門檻 {brier_threshold}（過高）"
        )
    if ece >= ece_threshold:
        reasons.append(
            f"ECE {ece:.4f} >= 門檻 {ece_threshold}（校準不足）"
        )

    gate_status = "PASS" if not reasons else "FAIL"
    return {
        "gate_status": gate_status,
        "brier": brier,
        "ece": ece,
        "reasons": reasons,
    }


def summarize_by_walk_forward_fold(rows: List[dict]) -> List[dict]:
    """
    按 walk_forward_fold 分組統計。
    每折輸出：fold, games, recommendations, coverage, accuracy, brier, ece
    僅計算有 actual_home_win 欄位（非 None）的行。
    """
    from collections import defaultdict

    fold_data: Dict[int, dict] = defaultdict(
        lambda: {
            "games": 0,
            "recommendations": 0,
            "probs": [],
            "outcomes": [],
            "correct": 0,
        }
    )

    for row in rows:
        fold = row.get("walk_forward_fold", 0)
        fold_data[fold]["games"] += 1
        actual = row.get("actual_home_win")
        model_prob = row.get("model_prob")
        bet_side = row.get("bet_side", "HOME")

        if actual is not None and model_prob is not None:
            fold_data[fold]["recommendations"] += 1
            # 計算 HOME 視角機率 vs actual_home_win
            home_prob = model_prob if bet_side == "HOME" else 1.0 - model_prob
            fold_data[fold]["probs"].append(home_prob)
            fold_data[fold]["outcomes"].append(int(actual))
            if (bet_side == "HOME" and actual == 1) or (
                bet_side == "AWAY" and actual == 0
            ):
                fold_data[fold]["correct"] += 1

    result = []
    for fold in sorted(fold_data.keys()):
        fd = fold_data[fold]
        n_rec = fd["recommendations"]
        coverage = n_rec / fd["games"] if fd["games"] > 0 else 0.0
        accuracy = fd["correct"] / n_rec if n_rec > 0 else float("nan")
        brier = calculate_brier_score(fd["probs"], fd["outcomes"])
        ece = calculate_ece(fd["probs"], fd["outcomes"])
        result.append(
            {
                "fold": fold,
                "games": fd["games"],
                "recommendations": n_rec,
                "coverage": round(coverage, 4),
                "accuracy": round(accuracy, 4) if not math.isnan(accuracy) else None,
                "brier": round(brier, 4) if not math.isnan(brier) else None,
                "ece": round(ece, 4) if not math.isnan(ece) else None,
            }
        )
    return result


def compare_edge_thresholds(
    rows: List[dict],
    thresholds: List[float] = [0.01, 0.03, 0.05],
) -> List[dict]:
    """
    對不同 edge threshold 計算：
    threshold, n_recommended, coverage_rate, average_edge, average_kelly_fraction
    注意：不計算 proxy_price_roi（actual_home_win 不保證完整）。
    """
    total = len(rows)
    result = []
    for thresh in sorted(thresholds):
        subset = [r for r in rows if (r.get("edge") or 0.0) >= thresh]
        n = len(subset)
        avg_edge = sum(r.get("edge", 0.0) for r in subset) / n if n > 0 else float("nan")
        avg_kelly = (
            sum(r.get("kelly_fraction", 0.0) for r in subset) / n
            if n > 0
            else float("nan")
        )
        result.append(
            {
                "threshold": thresh,
                "n_recommended": n,
                "coverage_rate": round(n / total, 4) if total > 0 else 0.0,
                "average_edge": round(avg_edge, 4) if not math.isnan(avg_edge) else None,
                "average_kelly_fraction": round(avg_kelly, 4) if not math.isnan(avg_kelly) else None,
            }
        )
    return result


def build_brier_ece_result(
    rows_with_actual: List[dict],
    total_rows: int,
    joined_rows: int,
    missing_result_rows: int,
) -> BrierECEResult:
    """
    從帶有 actual_home_win 欄位的行計算完整 BrierECEResult。
    """
    probs = []
    outcomes = []
    correct = 0

    for row in rows_with_actual:
        model_prob = row.get("model_prob")
        actual = row.get("actual_home_win")
        bet_side = row.get("bet_side", "HOME")
        if model_prob is None or actual is None:
            continue
        home_prob = model_prob if bet_side == "HOME" else 1.0 - model_prob
        probs.append(home_prob)
        outcomes.append(int(actual))
        if (bet_side == "HOME" and actual == 1) or (bet_side == "AWAY" and actual == 0):
            correct += 1

    n = len(probs)
    brier = calculate_brier_score(probs, outcomes)
    ece = calculate_ece(probs, outcomes)
    accuracy = correct / n if n > 0 else float("nan")
    coverage_rate = joined_rows / total_rows if total_rows > 0 else 0.0

    gate = validate_marl_gate(brier, ece)
    return BrierECEResult(
        total_rows=total_rows,
        joined_rows=joined_rows,
        missing_result_rows=missing_result_rows,
        brier_score=brier,
        ece=ece,
        accuracy=accuracy,
        coverage_rate=coverage_rate,
        gate_status=gate["gate_status"],
        reasons=gate["reasons"],
    )
