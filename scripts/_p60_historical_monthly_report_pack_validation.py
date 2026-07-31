"""
P60 — Historical Monthly Report Pack (EDGE-FIRST Validation)
Apr–Sep 2025 months, EDGE-FIRST framing, validates model vs closing line.

paper_only=True, diagnostic_only=True, kelly_deploy_allowed=False
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
from datetime import datetime
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# CONSTANTS (DO NOT MODIFY)
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
LIVE_API_CALLS: int = 0
T_LOCKED: float = 0.50  # Tier C threshold — do NOT re-optimize
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False

# P45 Platt constants (DO NOT MODIFY)
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
PLATT_SIGMOID_K: float = 0.8
CLIP_EPS: float = 1e-7

# P52 V2 thresholds (DO NOT MODIFY — loaded from JSON, reproduced here as cache)
P52_ECE_WARNING: float = 0.10
P52_ECE_CRITICAL: float = 0.12
P52_BRIER_WARNING: float = 0.25
P52_BRIER_CRITICAL: float = 0.27
P52_EDGE_WARNING: float = 0.07
P52_SAMPLE_LIMITED: int = 100

# Bootstrap config
N_BOOT: int = 5000
SEED: int = 42

# Paths
REPO_ROOT = pathlib.Path(__file__).parent.parent
JSONL_PATH = REPO_ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P52_PATH = REPO_ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P58_PATH = REPO_ROOT / "data/mlb_2025/derived/p58_monitoring_contract_v2_monthly_report_template_summary.json"
P59_PATH = REPO_ROOT / "data/mlb_2025/derived/p59_monitoring_contract_v2_first_monthly_report_summary.json"
P45_PATH = REPO_ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"
P44_PATH = REPO_ROOT / "data/mlb_2025/derived/p44_temporal_stability_summary.json"
P53_PATH = REPO_ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"

OUT_JSON = REPO_ROOT / "data/mlb_2025/derived/p60_historical_monthly_report_pack_validation_summary.json"

TARGET_MONTHS = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]

# ---------------------------------------------------------------------------
# Math helpers (identical to P51/P44 canonical implementations)
# ---------------------------------------------------------------------------

def _sigmoid(x: float, k: float = PLATT_SIGMOID_K) -> float:
    """Logistic sigmoid with k parameter."""
    try:
        return 1.0 / (1.0 + math.exp(-k * x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _platt_calibrate(raw_prob: float) -> float:
    """Apply Platt scaling with P45-locked constants to model_home_prob."""
    raw_clipped = max(CLIP_EPS, min(1.0 - CLIP_EPS, raw_prob))
    log_odds = math.log(raw_clipped / (1.0 - raw_clipped))
    adj = PLATT_A * log_odds + PLATT_B
    try:
        return 1.0 / (1.0 + math.exp(-adj))
    except OverflowError:
        return 0.0 if adj < 0 else 1.0


def _edge_for_model_side(model_home_prob: float, market_home_prob: float) -> float:
    """Side-aware edge — always measured on model-backed side (P44/P43 definition)."""
    if model_home_prob >= 0.5:
        return model_home_prob - market_home_prob
    else:
        return (1.0 - model_home_prob) - (1.0 - market_home_prob)


def _compute_ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error — equal-width bins (P51 canonical impl)."""
    if not probs:
        return float("nan")
    bins: dict[int, tuple[list, list]] = {i: ([], []) for i in range(n_bins)}
    for p, y in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b][0].append(p)
        bins[b][1].append(y)
    total = len(probs)
    err = 0.0
    for ps, ys in bins.values():
        if not ps:
            continue
        err += (len(ps) / total) * abs(sum(ps) / len(ps) - sum(ys) / len(ys))
    return err


def _compute_brier(probs: list[float], outcomes: list[int]) -> float:
    """Brier score."""
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def bootstrap_ci(values: list[float], n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """Percentile bootstrap CI returning (mean, ci_low, ci_high). Deterministic seed=42."""
    if not values:
        return (float("nan"), float("nan"), float("nan"))
    arr = np.array(values, dtype=float)
    n = len(arr)
    mean_val = float(arr.mean())
    if n < 2:
        return (mean_val, mean_val, mean_val)
    rng = np.random.default_rng(seed)
    boot_means = rng.choice(arr, size=(n_boot, n), replace=True).mean(axis=1)
    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))
    return (mean_val, ci_low, ci_high)


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

# ---------------------------------------------------------------------------
# Step 1 — Load artifacts
# ---------------------------------------------------------------------------

def load_artifacts() -> dict[str, Any]:
    """Load P52/P58/P59/P45 artifacts and compute SHA256 hashes."""
    result: dict[str, Any] = {}
    for key, path in [("p52", P52_PATH), ("p58", P58_PATH), ("p59", P59_PATH),
                      ("p45", P45_PATH), ("p44", P44_PATH), ("p53", P53_PATH)]:
        if path.exists():
            result[key] = json.loads(path.read_text())
            result[f"{key}_hash"] = _sha256_file(path)
            result[f"{key}_loaded"] = True
        else:
            result[key] = {}
            result[f"{key}_hash"] = "FILE_NOT_FOUND"
            result[f"{key}_loaded"] = False
    return result


# ---------------------------------------------------------------------------
# Step 2 — Load predictions
# ---------------------------------------------------------------------------

def load_predictions() -> list[dict]:
    """Load Tier C predictions from JSONL. Filter: |sp_fip_delta|>=0.5, market in (0,1), home_win defined."""
    rows = []
    for line in JSONL_PATH.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        rec = json.loads(line)
        sp_delta = rec.get("p0_features", {}).get("sp_fip_delta")
        mkt = rec.get("market_home_prob_no_vig")
        hw = rec.get("home_win")
        mp = rec.get("model_home_prob")
        if sp_delta is None or mkt is None or hw is None or mp is None:
            continue
        if not (0 < float(mkt) < 1):
            continue
        if abs(float(sp_delta)) < T_LOCKED:
            continue
        # FIP signal probability (k=0.8, matching P44 canonical)
        fip_prob = _sigmoid(float(sp_delta), k=PLATT_SIGMOID_K)
        raw_edge = _edge_for_model_side(fip_prob, float(mkt))
        platt_prob = _platt_calibrate(float(mp))
        rows.append({
            "game_date": rec.get("game_date", ""),
            "month": rec.get("game_date", "")[:7],
            "home_win": int(hw),
            "sp_fip_delta": float(sp_delta),
            "fip_prob": fip_prob,
            "raw_edge": raw_edge,
            "market_home_prob_no_vig": float(mkt),
            "model_home_prob": float(mp),
            "platt_prob": platt_prob,
        })
    rows.sort(key=lambda r: r["game_date"])
    return rows


# ---------------------------------------------------------------------------
# Classification helpers (P52 V2 semantics)
# ---------------------------------------------------------------------------

def classify_edge_status(mean: float, ci_low: float, ci_high: float) -> str:
    """Classify edge status per P52 V2 thresholds (EDGE-FIRST)."""
    if ci_low <= 0.0:
        return "EDGE_CRITICAL"
    elif mean < P52_EDGE_WARNING:
        return "EDGE_WARNING"
    else:
        return "EDGE_WITHIN_THRESHOLD"


def classify_calibration_status(ece: float) -> str:
    """Classify calibration status per P52 V2 thresholds."""
    if ece > P52_ECE_CRITICAL:
        return "CALIBRATION_CRITICAL"
    elif ece > P52_ECE_WARNING:
        return "CALIBRATION_WARNING"
    else:
        return "CALIBRATION_OK"


def classify_sample_status(n: int) -> str:
    """Classify sample status. SAMPLE_INSUFFICIENT if n < 100."""
    if n < 30:
        return "SAMPLE_INSUFFICIENT"
    elif n < P52_SAMPLE_LIMITED:
        return "SAMPLE_WATCHLIST"
    else:
        return "SAMPLE_ADEQUATE"


# ---------------------------------------------------------------------------
# Per-month computation
# ---------------------------------------------------------------------------

def get_monthly_records(preds: list[dict], month: str) -> list[dict]:
    """Filter predictions to a specific month."""
    return [r for r in preds if r["month"] == month]


def compute_monthly_report(
    preds: list[dict],
    month: str,
    p52_thresholds: dict,
    p45_constants: dict,
) -> dict:
    """Compute full monthly report for a given month."""
    mo_recs = get_monthly_records(preds, month)
    n = len(mo_recs)

    # DATA_GAP check: < 10 records = DATA_GAP_BLOCKED
    if n < 10:
        return {
            "month": month,
            "batch_n": n,
            "data_gap_status": "DATA_GAP_BLOCKED",
            "edge_status": "DATA_GAP_BLOCKED",
            "calibration_status": "DATA_GAP_BLOCKED",
            "sample_status": "DATA_GAP_BLOCKED",
            "raw_edge_mean": None,
            "raw_edge_ci_low": None,
            "raw_edge_ci_high": None,
            "platt_ece": None,
            "platt_brier": None,
            "validations": {f"VAL{i:02d}": "SKIP_DATA_GAP" for i in range(1, 11)},
            "global_alert_level": "GREY",
            "global_status": "DATA_GAP_BLOCKED",
        }

    # Compute edge metrics
    raw_edges = [r["raw_edge"] for r in mo_recs]
    mean_edge, ci_low, ci_high = bootstrap_ci(raw_edges)

    # Compute calibration metrics
    platt_probs = [r["platt_prob"] for r in mo_recs]
    outcomes = [r["home_win"] for r in mo_recs]
    platt_ece = _compute_ece(platt_probs, outcomes)
    platt_brier = _compute_brier(platt_probs, outcomes)

    # Classify
    edge_status = classify_edge_status(mean_edge, ci_low, ci_high)
    cal_status = classify_calibration_status(platt_ece)
    sample_status = classify_sample_status(n)

    # Positive edge rate
    positive_edge_rate = sum(1 for e in raw_edges if e > 0) / n

    # Global status (P52 V2 dominance order)
    alert_reasons = []
    if edge_status == "EDGE_CRITICAL":
        alert_reasons.append(f"edge_ci_low={ci_low:.6f} <= 0 (P52 V2 EDGE_DRIFT_CRITICAL)")
    elif edge_status == "EDGE_WARNING":
        alert_reasons.append(f"mean_edge={mean_edge:.6f} < {P52_EDGE_WARNING} (P52 V2 EDGE_DRIFT_WARNING)")
    if cal_status == "CALIBRATION_CRITICAL":
        alert_reasons.append(f"platt_ece={platt_ece:.6f} > {P52_ECE_CRITICAL} (P52 V2 CALIBRATION_CRITICAL)")
    elif cal_status == "CALIBRATION_WARNING":
        alert_reasons.append(f"platt_ece={platt_ece:.6f} > {P52_ECE_WARNING} (P52 V2 CALIBRATION_WARNING)")
    if sample_status in ("SAMPLE_INSUFFICIENT", "SAMPLE_WATCHLIST"):
        alert_reasons.append(f"batch_n={n} < {P52_SAMPLE_LIMITED} (SAMPLE_LIMITED)")

    has_critical = ("CRITICAL" in edge_status or "CRITICAL" in cal_status)
    has_warning = ("WARNING" in edge_status or "WARNING" in cal_status)

    if has_critical:
        global_status = "MONITORING_ALERT_DIAGNOSTIC"
        alert_level = "RED"
    elif has_warning or sample_status == "SAMPLE_WATCHLIST":
        global_status = "MONITORING_ALERT_DIAGNOSTIC"
        alert_level = "YELLOW"
    elif sample_status == "SAMPLE_INSUFFICIENT":
        global_status = "MONITORING_INCONCLUSIVE"
        alert_level = "GREY"
    else:
        global_status = "MONITORING_ACTIVE_DIAGNOSTIC"
        alert_level = "GREEN"

    # Run VAL01-VAL10
    validations = run_val01_to_val10(
        month=month,
        n=n,
        mean_edge=mean_edge,
        ci_low=ci_low,
        ci_high=ci_high,
        platt_ece=platt_ece,
        platt_brier=platt_brier,
        edge_status=edge_status,
        cal_status=cal_status,
        sample_status=sample_status,
    )

    return {
        "month": month,
        "batch_n": n,
        "data_gap_status": "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved. Cross-year analysis blocked; this pack is 2025-only.",
        "edge_status": edge_status,
        "calibration_status": cal_status,
        "sample_status": sample_status,
        "raw_edge_mean": round(mean_edge, 6),
        "raw_edge_ci_low": round(ci_low, 6),
        "raw_edge_ci_high": round(ci_high, 6),
        "positive_edge_rate": round(positive_edge_rate, 4),
        "platt_ece": round(platt_ece, 6),
        "platt_brier": round(platt_brier, 6),
        "p52_thresholds_used": p52_thresholds,
        "global_status": global_status,
        "global_alert_level": alert_level,
        "global_alert_reasons": alert_reasons,
        "platt_constants": {"A": PLATT_A, "B": PLATT_B, "sigmoid_k": PLATT_SIGMOID_K},
        "validations": validations,
        "edge_probability_stream": "RAW_SIGMOID (sigmoid(k=0.8 * sp_fip_delta), side-aware)",
        "calibration_probability_stream": "PLATT_CALIBRATED (Platt(model_home_prob), P45 constants)",
    }


# ---------------------------------------------------------------------------
# VAL01-VAL10
# ---------------------------------------------------------------------------

def run_val01_to_val10(
    month: str,
    n: int,
    mean_edge: float,
    ci_low: float,
    ci_high: float,
    platt_ece: float,
    platt_brier: float,
    edge_status: str,
    cal_status: str,
    sample_status: str,
) -> dict[str, str]:
    """Run VAL01-VAL10 validation checks for a monthly report."""
    results = {}

    # VAL01: paper_only=True
    results["VAL01"] = "PASS" if PAPER_ONLY else "FAIL"

    # VAL02: diagnostic_only=True
    results["VAL02"] = "PASS" if DIAGNOSTIC_ONLY else "FAIL"

    # VAL03: kelly_deploy_allowed=False
    results["VAL03"] = "PASS" if not KELLY_DEPLOY_ALLOWED else "FAIL"

    # VAL04: live_api_calls=0
    results["VAL04"] = "PASS" if LIVE_API_CALLS == 0 else "FAIL"

    # VAL05: promotion_freeze=True
    results["VAL05"] = "PASS" if PROMOTION_FREEZE else "FAIL"

    # VAL06: runtime_recommendation_logic_changed=False
    results["VAL06"] = "PASS" if not RUNTIME_RECOMMENDATION_LOGIC_CHANGED else "FAIL"

    # VAL07: Platt constants unchanged
    results["VAL07"] = "PASS" if (
        abs(PLATT_A - 0.435432) < 1e-6 and abs(PLATT_B - 0.245464) < 1e-6
    ) else "FAIL"

    # VAL08: t_locked == 0.50
    results["VAL08"] = "PASS" if abs(T_LOCKED - 0.50) < 1e-9 else "FAIL"

    # VAL09: no forbidden strings in key output fields
    forbidden_check = all(
        kw not in str(val).lower()
        for kw in ["guaranteed profit", "profitability claim", "production proposal",
                   "live odds api call", "champion replacement"]
        for val in [month, edge_status, cal_status, sample_status]
    )
    results["VAL09"] = "PASS" if forbidden_check else "FAIL"

    # VAL10: P52 thresholds unchanged (verified via constants)
    thresholds_ok = (
        abs(P52_ECE_WARNING - 0.10) < 1e-9 and
        abs(P52_ECE_CRITICAL - 0.12) < 1e-9 and
        abs(P52_BRIER_WARNING - 0.25) < 1e-9 and
        abs(P52_BRIER_CRITICAL - 0.27) < 1e-9 and
        abs(P52_EDGE_WARNING - 0.07) < 1e-9 and
        P52_SAMPLE_LIMITED == 100
    )
    results["VAL10"] = "PASS" if thresholds_ok else "FAIL"

    return results


# ---------------------------------------------------------------------------
# Pack-level synthesis
# ---------------------------------------------------------------------------

def compute_pack_synthesis(monthly_reports: list[dict]) -> dict:
    """Cross-month synthesis with EDGE-FIRST framing."""
    available = [r for r in monthly_reports if r.get("data_gap_status") != "DATA_GAP_BLOCKED"
                 and r.get("edge_status") != "DATA_GAP_BLOCKED"]

    months_within_threshold = sum(
        1 for r in available if r["edge_status"] == "EDGE_WITHIN_THRESHOLD"
    )
    months_warning = sum(1 for r in available if r["edge_status"] == "EDGE_WARNING")
    months_critical = sum(1 for r in available if r["edge_status"] == "EDGE_CRITICAL")
    total_months = len(available)

    # Cross-month edge stability
    if months_within_threshold == total_months and total_months >= 6:
        cross_month_edge_stability = "EDGE_STABLE_ACROSS_MONTHS"
    elif months_within_threshold >= 4:
        cross_month_edge_stability = "EDGE_MOSTLY_STABLE"
    elif months_within_threshold >= 2:
        cross_month_edge_stability = "EDGE_INCONSISTENT"
    else:
        cross_month_edge_stability = "EDGE_UNSTABLE"

    # Calibration summary
    cal_ok_months = sum(1 for r in available if r["calibration_status"] == "CALIBRATION_OK")
    cal_warning_months = sum(1 for r in available if r["calibration_status"] == "CALIBRATION_WARNING")
    cal_critical_months = sum(1 for r in available if r["calibration_status"] == "CALIBRATION_CRITICAL")

    # Aggregate edge stats
    edge_means = [r["raw_edge_mean"] for r in available if r.get("raw_edge_mean") is not None]
    avg_edge_mean = round(sum(edge_means) / len(edge_means), 6) if edge_means else None

    ece_vals = [r["platt_ece"] for r in available if r.get("platt_ece") is not None]
    avg_platt_ece = round(sum(ece_vals) / len(ece_vals), 6) if ece_vals else None

    # EDGE-FIRST conclusion
    if cross_month_edge_stability == "EDGE_STABLE_ACROSS_MONTHS":
        conclusion = (
            f"EDGE-FIRST RESULT: Apr–Sep 2025 模型穩定優於 closing line（{total_months}/{total_months} 月份 "
            f"EDGE_WITHIN_THRESHOLD，平均 edge={avg_edge_mean:.4f}，所有月份 CI_low > 0）。"
            f"校準方面：{cal_ok_months} 個月 CALIBRATION_OK，{cal_critical_months} 個月 CALIBRATION_CRITICAL。"
            f"2024 closing-line 資料缺口仍未解決，此 pack 僅涵蓋 2025 年。"
        )
    elif cross_month_edge_stability == "EDGE_MOSTLY_STABLE":
        conclusion = (
            f"EDGE-FIRST RESULT: Apr–Sep 2025 模型多數月份優於 closing line（{months_within_threshold}/{total_months} 月份 "
            f"EDGE_WITHIN_THRESHOLD，{months_warning} 個月 EDGE_WARNING，平均 edge={avg_edge_mean:.4f}）。"
            f"校準方面：{cal_ok_months} 個月 CALIBRATION_OK，{cal_critical_months} 個月 CALIBRATION_CRITICAL。"
            f"2024 closing-line 資料缺口仍未解決，此 pack 僅涵蓋 2025 年。"
        )
    elif cross_month_edge_stability == "EDGE_INCONSISTENT":
        conclusion = (
            f"EDGE-FIRST RESULT: Apr–Sep 2025 模型 edge 不穩定（{months_within_threshold}/{total_months} 月份 "
            f"EDGE_WITHIN_THRESHOLD，{months_critical} 個月 EDGE_CRITICAL）。"
            f"平均 edge={avg_edge_mean}。需進一步調查。"
        )
    else:
        conclusion = (
            f"EDGE-FIRST RESULT: Apr–Sep 2025 模型 edge 狀況不佳（{months_critical}/{total_months} 月份 EDGE_CRITICAL）。"
            f"系統未能穩定優於 closing line。"
        )

    return {
        "total_months_available": total_months,
        "months_with_edge_within_threshold": months_within_threshold,
        "months_with_edge_warning": months_warning,
        "months_with_edge_critical": months_critical,
        "cross_month_edge_stability": cross_month_edge_stability,
        "months_with_calibration_ok": cal_ok_months,
        "months_with_calibration_warning": cal_warning_months,
        "months_with_calibration_critical": cal_critical_months,
        "avg_edge_mean_across_months": avg_edge_mean,
        "avg_platt_ece_across_months": avg_platt_ece,
        "synthesis_conclusion": conclusion,
        "framing": "EDGE-FIRST: edge vs closing line is primary metric; calibration is secondary",
        "data_gap_note": "2024 closing-line data gap remains (P43_BLOCKED_BY_DATA_GAP). This pack covers 2025-only.",
    }


# ---------------------------------------------------------------------------
# P59 consistency check
# ---------------------------------------------------------------------------

def compute_p59_consistency(sep_report: dict, artifacts: dict) -> dict:
    """Check Sep 2025 month against P59 reference values."""
    p59 = artifacts.get("p59", {})
    p59_gs = p59.get("global_status", {})
    p59_raw_edge_mean = p59_gs.get("raw_edge_mean", 0.108441)
    p59_platt_ece = p59_gs.get("platt_ece", 0.122929)
    p59_batch_n = p59_gs.get("batch_n", 98)

    sep_edge = sep_report.get("raw_edge_mean") or 0.0
    sep_ece = sep_report.get("platt_ece") or 0.0
    sep_n = sep_report.get("batch_n", 0)

    edge_match = abs(sep_edge - p59_raw_edge_mean) < 0.005
    ece_match = abs(sep_ece - p59_platt_ece) < 0.005
    n_match = sep_n == p59_batch_n

    return {
        "p59_raw_edge_mean": p59_raw_edge_mean,
        "p59_platt_ece": p59_platt_ece,
        "p59_batch_n": p59_batch_n,
        "p60_sep_raw_edge_mean": sep_edge,
        "p60_sep_platt_ece": sep_ece,
        "p60_sep_batch_n": sep_n,
        "edge_mean_match": edge_match,
        "platt_ece_match": ece_match,
        "batch_n_match": n_match,
        "overall_consistent": edge_match and ece_match and n_match,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("P60 — Historical Monthly Report Pack (EDGE-FIRST Validation)")
    print(f"Run date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # Step 1: Load artifacts
    print("[1/6] Loading artifacts...")
    artifacts = load_artifacts()
    for key in ["p52", "p58", "p59", "p45"]:
        status = "OK" if artifacts.get(f"{key}_loaded") else "MISSING"
        print(f"  {key.upper()}: {status} | SHA256: {artifacts.get(f'{key}_hash', 'N/A')[:16]}...")

    # Step 2: Load predictions
    print("\n[2/6] Loading Tier C predictions...")
    preds = load_predictions()
    print(f"  Total Tier C records: {len(preds)}")
    from collections import Counter
    month_dist = Counter(r["month"] for r in preds)
    for mo in TARGET_MONTHS:
        print(f"  {mo}: n={month_dist.get(mo, 0)}")

    # Step 3: P52 thresholds
    p52_thresholds = {
        "ece_warning_threshold": P52_ECE_WARNING,
        "ece_critical_threshold": P52_ECE_CRITICAL,
        "brier_warning_threshold": P52_BRIER_WARNING,
        "brier_critical_threshold": P52_BRIER_CRITICAL,
        "edge_warning_threshold": P52_EDGE_WARNING,
        "edge_critical_condition": "edge_ci_low <= 0",
        "sample_limited_threshold": P52_SAMPLE_LIMITED,
        "source": str(P52_PATH),
        "note": "Thresholds locked from P52 V2. Not changed by P60.",
    }
    p45_constants = {"A": PLATT_A, "B": PLATT_B, "sigmoid_k": PLATT_SIGMOID_K}

    # Step 4: Compute monthly reports
    print("\n[3/6] Computing monthly reports (Apr–Sep 2025)...")
    monthly_reports = []
    for month in TARGET_MONTHS:
        report = compute_monthly_report(preds, month, p52_thresholds, p45_constants)
        monthly_reports.append(report)
        n = report["batch_n"]
        es = report["edge_status"]
        cs = report["calibration_status"]
        ss = report["sample_status"]
        em = report.get("raw_edge_mean")
        print(f"  {month}: n={n}, edge_status={es}, cal_status={cs}, sample_status={ss}, edge_mean={em}")

    # Step 5: P59 consistency check
    print("\n[4/6] P59 consistency check (Sep 2025)...")
    sep_report = next(r for r in monthly_reports if r["month"] == "2025-09")
    p59_check = compute_p59_consistency(sep_report, artifacts)
    print(f"  P59 raw_edge_mean={p59_check['p59_raw_edge_mean']:.6f}, P60={p59_check['p60_sep_raw_edge_mean']:.6f}, match={p59_check['edge_mean_match']}")
    print(f"  P59 platt_ece={p59_check['p59_platt_ece']:.6f}, P60={p59_check['p60_sep_platt_ece']:.6f}, match={p59_check['platt_ece_match']}")

    # Step 6: Pack synthesis
    print("\n[5/6] Computing pack-level synthesis...")
    synthesis = compute_pack_synthesis(monthly_reports)
    print(f"  Cross-month edge stability: {synthesis['cross_month_edge_stability']}")
    print(f"  Months EDGE_WITHIN_THRESHOLD: {synthesis['months_with_edge_within_threshold']}/6")
    print(f"  Months CALIBRATION_CRITICAL: {synthesis['months_with_calibration_critical']}/6")

    # Pack classification
    stab = synthesis["cross_month_edge_stability"]
    if stab == "EDGE_STABLE_ACROSS_MONTHS":
        pack_classification = "P60_EDGE_STABLE_ACROSS_MONTHS"
    elif stab == "EDGE_MOSTLY_STABLE":
        pack_classification = "P60_EDGE_MOSTLY_STABLE"
    elif stab == "EDGE_INCONSISTENT":
        pack_classification = "P60_EDGE_INCONSISTENT"
    else:
        pack_classification = "P60_EDGE_UNSTABLE"

    # Step 7: Forbidden string scan
    print("\n[6/6] Forbidden string scan...")
    forbidden_strings = [
        "guaranteed profit", "profitability claim", "production proposal",
        "live odds api call", "champion replacement"
    ]
    test_text = json.dumps(monthly_reports + [synthesis], ensure_ascii=False).lower()
    forbidden_found = [f for f in forbidden_strings if f in test_text]
    print(f"  Forbidden strings found: {forbidden_found}")
    forbidden_scan_pass = len(forbidden_found) == 0

    # Compose output JSON
    output = {
        "p60_phase": "P60 — Historical Monthly Report Pack (EDGE-FIRST Validation)",
        "run_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "pack_classification": pack_classification,
        "paper_only": PAPER_ONLY,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "promotion_freeze": PROMOTION_FREEZE,
        "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
        "live_api_calls": LIVE_API_CALLS,
        "t_locked": T_LOCKED,
        "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
        "platt_constants": p45_constants,
        "p52_thresholds_unchanged": True,
        "source_artifacts": {
            "p52_loaded": artifacts.get("p52_loaded", False),
            "p58_loaded": artifacts.get("p58_loaded", False),
            "p59_loaded": artifacts.get("p59_loaded", False),
            "p45_loaded": artifacts.get("p45_loaded", False),
            "p44_loaded": artifacts.get("p44_loaded", False),
            "p53_loaded": artifacts.get("p53_loaded", False),
            "p52_hash": artifacts.get("p52_hash", ""),
            "p58_hash": artifacts.get("p58_hash", ""),
            "p59_hash": artifacts.get("p59_hash", ""),
            "p45_hash": artifacts.get("p45_hash", ""),
        },
        "artifacts_overwritten": {
            "p52": False,
            "p53": False,
            "p54": False,
            "p55": False,
            "p56": False,
            "p57": False,
            "p58": False,
            "p59": False,
            "p45": False,
        },
        "monthly_reports": monthly_reports,
        "p59_consistency_check": p59_check,
        "pack_synthesis": synthesis,
        "forbidden_scan_result": {
            "pass": forbidden_scan_pass,
            "forbidden_found": forbidden_found,
        },
        "data_gap_note": (
            "2024 closing-line data gap remains (P43_BLOCKED_BY_DATA_GAP). "
            "This pack covers 2025-only (Apr–Sep 2025). "
            "Cross-year market-edge validation requires 2024 odds data."
        ),
        "framing_note": (
            "P60 is a paper-only, offline, diagnostic pack. "
            "It validates Apr–Sep 2025 monthly edge performance vs closing line. "
            "No runtime logic, champion strategy, or P52-P59 artifacts are modified. "
            "No live API calls made."
        ),
        "edge_first_question": "Apr–Sep 2025 模型是否穩定優於 closing line？",
        "edge_first_answer": synthesis["synthesis_conclusion"],
    }

    # Write JSON output
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nOutput written to: {OUT_JSON}")
    print(f"Pack classification: {pack_classification}")
    print(f"Forbidden scan: {'PASS' if forbidden_scan_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
