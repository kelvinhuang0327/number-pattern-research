"""
P51 — Monitoring Contract Revision Audit After P50 Stream Mismatch
Offline diagnostic only. No live API calls. No deployment proposal.
paper_only=True | diagnostic_only=True | promotion_freeze=True
"""

from __future__ import annotations

import json
import math
import pathlib
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Governance constants (locked from P45)
# ---------------------------------------------------------------------------
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
SIGMOID_K: float = 0.8
CLIP_EPS: float = 1e-7
BOOTSTRAP_SEED: int = 42
BOOTSTRAP_N: int = 5000
BATCH_SIZE: int = 100
STEP_SIZE: int = 50

# P48 alert thresholds (unchanged baseline)
ECE_WARN: float = 0.10
ECE_CRIT: float = 0.12
BRIER_WARN: float = 0.25
BRIER_CRIT: float = 0.27
EDGE_WARN_MEAN: float = 0.07
SAMPLE_LIMITED_N: int = 100

GOVERNANCE_FLAGS = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "p48_contract_overwritten": False,
    "p49_artifact_overwritten": False,
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT = pathlib.Path(__file__).parent.parent
BASE = _ROOT / "data/mlb_2025/derived"
JSONL_PATH = BASE / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------
def fip_signal_prob(x: float, k: float = 1.0) -> float:
    """Logistic sigmoid — P44-equivalent FIP signal probability."""
    try:
        return 1.0 / (1.0 + math.exp(-k * x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def platt_calibrate(raw_prob: float) -> float:
    """Apply Platt scaling with P45-locked constants."""
    raw_clipped = max(CLIP_EPS, min(1.0 - CLIP_EPS, raw_prob))
    log_odds = math.log(raw_clipped / (1.0 - raw_clipped))
    adj = PLATT_A * log_odds + PLATT_B
    try:
        return 1.0 / (1.0 + math.exp(-adj))
    except OverflowError:
        return 0.0 if adj < 0 else 1.0


def bootstrap_ci(
    values: list[float],
    seed: int = BOOTSTRAP_SEED,
    n_boot: int = BOOTSTRAP_N,
) -> tuple[float, float]:
    """Percentile bootstrap CI. Deterministic with fixed seed (numpy, matching P50)."""
    if not values:
        return (float("nan"), float("nan"))
    arr = np.array(values, dtype=float)
    n = len(arr)
    if n < 2:
        return (float(arr[0]), float(arr[0]))
    rng = np.random.default_rng(seed)
    boot_means = rng.choice(arr, size=(n_boot, n), replace=True).mean(axis=1)
    return (float(np.percentile(boot_means, 2.5)), float(np.percentile(boot_means, 97.5)))


def ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error, equal-width bins."""
    if not probs:
        return float("nan")
    bins: dict[int, list] = {i: ([], []) for i in range(n_bins)}
    for p, y in zip(probs, outcomes):
        b = min(int(p * n_bins), n_bins - 1)
        bins[b][0].append(p)
        bins[b][1].append(y)
    total = len(probs)
    err = 0.0
    for b in bins.values():
        ps, ys = b
        if not ps:
            continue
        err += (len(ps) / total) * abs(sum(ps) / len(ps) - sum(ys) / len(ys))
    return err


def brier(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------
# Locked constants from P50/P49
TIER_C_THRESH: float = 0.5  # |sp_fip_delta| >= 0.5 filter


def _load_json(path: str | Path) -> Any:
    with open(path) as f:
        return json.load(f)


def _load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_sources() -> dict[str, Any]:
    return {
        "p43": _load_json(_ROOT / "data/mlb_2025/derived/p43_strong_edge_closing_line_edge_summary.json"),
        "p44": _load_json(_ROOT / "data/mlb_2025/derived/p44_temporal_stability_summary.json"),
        "p48": _load_json(_ROOT / "data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json"),
        "p49": _load_json(_ROOT / "data/mlb_2025/derived/p49_offline_historical_monitoring_replay_summary.json"),
        "p50": _load_json(_ROOT / "data/mlb_2025/derived/p50_edge_drift_root_cause_audit_summary.json"),
        "p45": _load_json(_ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"),
        "p47": _load_json(_ROOT / "data/mlb_2025/derived/p47_calibration_synthesis_summary.json"),
    }


# ---------------------------------------------------------------------------
# Task P51.A — Revised Metric Ownership Matrix
# ---------------------------------------------------------------------------
def build_metric_ownership_matrix() -> list[dict]:
    """
    Assigns each monitoring metric to the correct probability stream
    and alert family, fixing the P49/P50 stream mismatch.
    """
    matrix = [
        # ---- Edge Monitoring ----
        {
            "metric_name": "side_aware_raw_edge",
            "metric_family": "EDGE_SIGNAL",
            "selected_probability_stream": "RAW_SIGMOID",
            "probability_source": "sigmoid(1.0 * sp_fip_delta) — FIP signal",
            "rationale": (
                "P43/P44 edge framework uses sigmoid(sp_fip_delta) as model probability. "
                "This is the canonical edge signal. P49 replaced this with trained ML "
                "model_home_prob (regularized toward 0.5), causing P50-confirmed stream mismatch. "
                "Revised contract restores FIP-signal edge for edge monitoring."
            ),
            "source_phase_reference": "P43, P44, P50 (fip_signal_side_aware_edge)",
            "allowed_alert_types": ["EDGE_SIGNAL_ALERT", "SAMPLE_ALERT"],
            "should_drive_monitoring_status": True,
            "edge_perspective": "SIDE_AWARE",
            "market_source": "embedded_no_vig",
            "ci_method": "bootstrap_5000_seed42",
            "warning_threshold": "mean_edge < 0.07",
            "critical_threshold": "CI_low <= 0",
        },
        # ---- Calibration Monitoring — ECE ----
        {
            "metric_name": "platt_ece",
            "metric_family": "CALIBRATION",
            "selected_probability_stream": "PLATT_CALIBRATED",
            "probability_source": (
                f"Platt scaling: A={PLATT_A}, B={PLATT_B} (locked from P45)"
            ),
            "rationale": (
                "ECE measures calibration accuracy; Platt-calibrated probabilities are "
                "more reliable than raw sigmoid for calibration metrics (P45/P47 conclusion). "
                "Do NOT use raw sigmoid for ECE — conflates edge signal with calibration quality."
            ),
            "source_phase_reference": "P45, P46, P47, P48",
            "allowed_alert_types": ["CALIBRATION_ALERT", "SAMPLE_ALERT"],
            "should_drive_monitoring_status": True,
            "warning_threshold": "rolling ECE > 0.10",
            "critical_threshold": "rolling ECE > 0.12",
        },
        # ---- Calibration Monitoring — Brier ----
        {
            "metric_name": "platt_brier",
            "metric_family": "CALIBRATION",
            "selected_probability_stream": "PLATT_CALIBRATED",
            "probability_source": (
                f"Platt scaling: A={PLATT_A}, B={PLATT_B} (locked from P45)"
            ),
            "rationale": (
                "Brier score decomposes into calibration + resolution components. "
                "Use Platt-calibrated probabilities consistent with ECE to avoid "
                "comparing incompatible probability scales."
            ),
            "source_phase_reference": "P45, P46, P47, P48",
            "allowed_alert_types": ["CALIBRATION_ALERT", "SAMPLE_ALERT"],
            "should_drive_monitoring_status": True,
            "warning_threshold": "rolling Brier > 0.25",
            "critical_threshold": "rolling Brier > 0.27",
        },
        # ---- Isotonic — Comparison Only ----
        {
            "metric_name": "isotonic_calibration",
            "metric_family": "CALIBRATION_COMPARISON",
            "selected_probability_stream": "ISOTONIC_CALIBRATED",
            "probability_source": "Isotonic regression (P46)",
            "rationale": (
                "P46 found Platt superior for this dataset. Isotonic retained for "
                "comparison only, not selected as monitoring baseline. P46 non-selection "
                "stands until future data contradicts it."
            ),
            "source_phase_reference": "P46",
            "allowed_alert_types": [],
            "should_drive_monitoring_status": False,
            "note": "COMPARISON_ONLY — not selected per P46",
        },
        # ---- Sample Alert ----
        {
            "metric_name": "batch_sample_size",
            "metric_family": "SAMPLE",
            "selected_probability_stream": "N/A",
            "probability_source": "N/A — count of games in batch",
            "rationale": (
                "Batch with n < 100 cannot reliably estimate edge CI or ECE. "
                "Sample limited status dominates WARNING. Does not dominate CRITICAL."
            ),
            "source_phase_reference": "P48",
            "allowed_alert_types": ["SAMPLE_ALERT"],
            "should_drive_monitoring_status": True,
            "sample_limited_threshold": f"batch_n < {SAMPLE_LIMITED_N}",
        },
        # ---- Data Gap Alert ----
        {
            "metric_name": "closing_line_data_availability",
            "metric_family": "DATA_GAP",
            "selected_probability_stream": "N/A",
            "probability_source": "N/A — data completeness check",
            "rationale": (
                "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) limits cross-year "
                "validation. For 2025-only replay this is not a blocker. "
                "DATA_GAP_BLOCKED dominates all other alert levels."
            ),
            "source_phase_reference": "P43, P48, P49, P50",
            "allowed_alert_types": ["DATA_GAP_ALERT"],
            "should_drive_monitoring_status": True,
            "blocked_condition": "closing_line_source_missing for target year",
            "note_2024_gap": "2024 gap is cross-year limitation — not blocker for 2025-only replay",
        },
    ]
    return matrix


# ---------------------------------------------------------------------------
# Task P51.B — Revised Alert Rules
# ---------------------------------------------------------------------------
def build_revised_alert_rules() -> dict:
    return {
        "edge": {
            "probability_stream": "RAW_SIGMOID (sigmoid(sp_fip_delta), side-aware)",
            "edge_perspective": "SIDE_AWARE",
            "market_source": "embedded_no_vig (prediction-time)",
            "ci_method": "bootstrap_5000_seed42",
            "warning_condition": f"rolling mean_edge < {EDGE_WARN_MEAN}",
            "critical_condition": "edge CI_low <= 0",
            "note": (
                "Threshold semantics validated against P44 monthly stability: "
                "all 6 months 2025-04 to 2025-09 have CI_low > 0 under fip_signal_side_aware_edge. "
                "P48 thresholds (0.07 warn, CI_crosses_zero crit) are appropriate for this stream."
            ),
        },
        "calibration": {
            "probability_stream": "PLATT_CALIBRATED",
            "ece_warning": ECE_WARN,
            "ece_critical": ECE_CRIT,
            "brier_warning": BRIER_WARN,
            "brier_critical": BRIER_CRIT,
            "note": "Thresholds unchanged from P48. Only stream assignment enforced.",
        },
        "sample": {
            "sample_limited_condition": f"batch_n < {SAMPLE_LIMITED_N}",
            "dominance": "SAMPLE_LIMITED dominates WARNING; does NOT dominate CRITICAL",
        },
        "data_gap": {
            "blocked_condition": "closing_line_source_missing for required year",
            "dominance": "DATA_GAP_BLOCKED dominates all alert levels",
            "note_2024": "2024 closing-line data gap remains unresolved (P43_BLOCKED_BY_DATA_GAP). 2025-only replay not blocked.",
        },
        "dominance_order": [
            "DATA_GAP_BLOCKED overrides all",
            "SAMPLE_LIMITED dominates WARNING (not CRITICAL)",
            "CRITICAL dominates WARNING in multi-category alerts",
            "MIXED_ALERTS when multiple metric families fire at same level",
            "MONITORING_OK when no alert fires",
        ],
        "key_change_from_p48": (
            "P49 used PLATT_CALIBRATED probability (model_home_prob after Platt) for EDGE monitoring. "
            "Revised contract assigns edge monitoring to RAW_SIGMOID (fip_signal_side_aware) "
            "and calibration monitoring to PLATT_CALIBRATED. These must NOT be swapped."
        ),
    }


# ---------------------------------------------------------------------------
# Compute revised status for a single batch
# ---------------------------------------------------------------------------
def _apply_revised_alert_rules(
    n: int,
    fip_edge_mean: float,
    fip_edge_ci_low: float,
    fip_edge_ci_high: float,
    platt_ece_val: float,
    platt_brier_val: float,
) -> dict:
    """Apply revised P51 contract alert rules to a batch."""
    alerts: list[str] = []
    edge_status = "MONITORING_OK"
    calibration_status = "MONITORING_OK"
    sample_status = "MONITORING_OK"

    if n < SAMPLE_LIMITED_N:
        sample_status = "SAMPLE_LIMITED"
        alerts.append(f"sample_limited: batch_n={n} < {SAMPLE_LIMITED_N}")

    # Edge (RAW_SIGMOID / fip_signal_side_aware)
    if not math.isnan(fip_edge_mean):
        if fip_edge_ci_low <= 0:
            edge_status = "EDGE_DRIFT_CRITICAL"
            alerts.append(f"edge_critical: CI crosses zero (ci_low={fip_edge_ci_low:.4f} <= 0)")
        elif fip_edge_mean < EDGE_WARN_MEAN:
            edge_status = "EDGE_DRIFT_WARNING"
            alerts.append(f"edge_warning: mean_edge={fip_edge_mean:.4f} < {EDGE_WARN_MEAN}")

    # Calibration (PLATT_CALIBRATED)
    if not math.isnan(platt_ece_val):
        if platt_ece_val > ECE_CRIT:
            calibration_status = "CALIBRATION_CRITICAL"
            alerts.append(f"ece_critical: ece={platt_ece_val:.4f} > {ECE_CRIT}")
        elif platt_ece_val > ECE_WARN:
            calibration_status = "CALIBRATION_WARNING"
            alerts.append(f"ece_warning: ece={platt_ece_val:.4f} > {ECE_WARN}")
    if not math.isnan(platt_brier_val):
        if platt_brier_val > BRIER_CRIT:
            alerts.append(f"brier_critical: brier={platt_brier_val:.4f} > {BRIER_CRIT}")
            if calibration_status != "CALIBRATION_CRITICAL":
                calibration_status = "CALIBRATION_CRITICAL"
        elif platt_brier_val > BRIER_WARN:
            if calibration_status == "MONITORING_OK":
                alerts.append(f"brier_warning: brier={platt_brier_val:.4f} > {BRIER_WARN}")
                calibration_status = "CALIBRATION_WARNING"

    # Dominance logic
    all_statuses = {edge_status, calibration_status}
    is_critical = any("CRITICAL" in s for s in all_statuses)
    is_warning = any("WARNING" in s for s in all_statuses)
    n_families_alerting = sum(1 for s in [edge_status, calibration_status] if s != "MONITORING_OK")

    if sample_status == "SAMPLE_LIMITED":
        if is_critical:
            final_status = "SAMPLE_LIMITED"  # sample limited but critical overrides for alert
            # Actually per spec: SAMPLE_LIMITED dominates WARNING not CRITICAL
            final_status = "EDGE_DRIFT_CRITICAL" if edge_status == "EDGE_DRIFT_CRITICAL" else (
                "CALIBRATION_CRITICAL" if calibration_status == "CALIBRATION_CRITICAL" else "SAMPLE_LIMITED"
            )
        else:
            final_status = "SAMPLE_LIMITED"
    elif is_critical:
        if n_families_alerting > 1 and is_warning:
            final_status = "MIXED_ALERTS"
        else:
            # Get the critical status
            if edge_status == "EDGE_DRIFT_CRITICAL" and calibration_status == "CALIBRATION_CRITICAL":
                final_status = "MIXED_ALERTS"
            elif edge_status == "EDGE_DRIFT_CRITICAL":
                final_status = "EDGE_DRIFT_CRITICAL"
            else:
                final_status = "CALIBRATION_CRITICAL"
    elif is_warning:
        if n_families_alerting > 1:
            final_status = "MIXED_ALERTS"
        elif edge_status == "EDGE_DRIFT_WARNING":
            final_status = "EDGE_DRIFT_WARNING"
        else:
            final_status = "CALIBRATION_WARNING"
    else:
        final_status = "MONITORING_OK"

    return {
        "edge_status": edge_status,
        "calibration_status": calibration_status,
        "sample_status": sample_status,
        "final_status": final_status,
        "alert_reasons": alerts,
    }


# ---------------------------------------------------------------------------
# Task P51.C — Build Tier C dataset for revised replay
# ---------------------------------------------------------------------------
def _side_aware_edge(model_home_prob: float, market_home_prob: float) -> float:
    """Side-aware edge — always positive for model-backed side (P44/P43 definition)."""
    if model_home_prob >= 0.5:
        return model_home_prob - market_home_prob
    else:
        return (1.0 - model_home_prob) - (1.0 - market_home_prob)


def build_tier_c_for_revised_replay() -> list[dict]:
    """
    Rebuild Tier C dataset with identical logic to P50's build_tier_c_dataset.
    sp_fip_delta is in row["p0_features"]["sp_fip_delta"].
    Filter: |sp_fip_delta| >= 0.5, market_home_prob_no_vig in (0,1),
            home_win not None, model_home_prob not None.
    """
    lines = JSONL_PATH.read_text().strip().split("\n")
    rows: list[dict] = []
    for line in lines:
        rec = json.loads(line)
        mkt = rec.get("market_home_prob_no_vig")
        hw = rec.get("home_win")
        mp = rec.get("model_home_prob")
        feats = rec.get("p0_features", {})
        sp_delta = feats.get("sp_fip_delta") if feats else None

        if mkt is None or hw is None or mp is None or sp_delta is None:
            continue
        if not (0 < mkt < 1):
            continue
        if abs(sp_delta) < TIER_C_THRESH:
            continue

        # FIP signal probability (P44-equivalent, k=1.0)
        fip_prob = fip_signal_prob(float(sp_delta), k=1.0)
        fip_edge = _side_aware_edge(fip_prob, float(mkt))

        # Platt calibration (for calibration metrics)
        platt_home_prob = platt_calibrate(float(mp))

        game_date = rec.get("game_date", "")
        rows.append({
            "game_date": game_date,
            "month": game_date[:7] if game_date else None,
            "home_win": int(hw),
            "sp_fip_delta": float(sp_delta),
            "fip_prob": fip_prob,
            "fip_edge": fip_edge,
            "market_home_prob_no_vig": float(mkt),
            "model_home_prob_raw": float(mp),
            "platt_home_prob": platt_home_prob,
        })

    rows.sort(key=lambda r: r["game_date"])
    return rows


# ---------------------------------------------------------------------------
# Apply revised contract to a batch of rows
# ---------------------------------------------------------------------------
def _compute_batch_metrics(rows: list[dict]) -> dict:
    fip_edges = [r["fip_edge"] for r in rows]
    platt_probs = [r["platt_home_prob"] for r in rows if not math.isnan(r["platt_home_prob"])]
    outcomes_platt = [r["home_win"] for r in rows if not math.isnan(r["platt_home_prob"])]
    outcomes_all = [r["home_win"] for r in rows]

    n = len(rows)
    fip_mean = sum(fip_edges) / n if fip_edges else float("nan")
    ci_low, ci_high = bootstrap_ci(fip_edges)
    pos_rate = sum(1 for e in fip_edges if e > 0) / n if fip_edges else float("nan")

    platt_ece_val = ece(platt_probs, outcomes_platt) if platt_probs else float("nan")
    platt_brier_val = brier(platt_probs, outcomes_platt) if platt_probs else float("nan")

    return {
        "n": n,
        "fip_edge_mean": round(fip_mean, 6),
        "fip_edge_ci_low": round(ci_low, 6),
        "fip_edge_ci_high": round(ci_high, 6),
        "fip_positive_edge_rate": round(pos_rate, 4),
        "platt_ece": round(platt_ece_val, 6),
        "platt_brier": round(platt_brier_val, 6),
    }


# ---------------------------------------------------------------------------
# Monthly revised replay
# ---------------------------------------------------------------------------
def run_monthly_revised_replay(
    tier_c: list[dict],
    p49_monthly_rows: list[dict],
) -> list[dict]:
    target_months = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]

    # Build month → p49 row lookup
    p49_by_month: dict[str, dict] = {}
    for row in p49_monthly_rows:
        bk = row.get("monthly_bucket") or row.get("batch_id", "")
        # batch_id like MONTHLY_202505 → 2025-05
        if bk and bk.startswith("MONTHLY_"):
            month = bk[8:12] + "-" + bk[12:14]
        elif bk and len(bk) == 7:
            month = bk
        else:
            month = bk
        p49_by_month[month] = row

    results: list[dict] = []
    for month in target_months:
        month_rows = [r for r in tier_c if r.get("month") == month]
        if not month_rows:
            continue

        metrics = _compute_batch_metrics(month_rows)
        status = _apply_revised_alert_rules(
            n=metrics["n"],
            fip_edge_mean=metrics["fip_edge_mean"],
            fip_edge_ci_low=metrics["fip_edge_ci_low"],
            fip_edge_ci_high=metrics["fip_edge_ci_high"],
            platt_ece_val=metrics["platt_ece"],
            platt_brier_val=metrics["platt_brier"],
        )

        p49_row = p49_by_month.get(month, {})
        old_status = p49_row.get("status", "UNKNOWN")
        old_alert_level = p49_row.get("alert_level", "UNKNOWN")

        status_changed = status["final_status"] != old_status
        reason_for_change = []
        if status_changed:
            if "CRITICAL" in old_status and "CRITICAL" not in status["final_status"]:
                reason_for_change.append(
                    "P49 CRITICAL was edge_ci_crosses_zero under PLATT_CALIBRATED home-perspective; "
                    "revised contract uses fip_signal_side_aware_edge (sigmoid(sp_fip_delta)) "
                    "where CI_low > 0"
                )
            elif "WARNING" in old_status and status["final_status"] == "MONITORING_OK":
                reason_for_change.append(
                    "P49 WARNING resolved under revised edge stream"
                )
            elif old_status == "SAMPLE_LIMITED" and status["final_status"] == "MONITORING_OK":
                reason_for_change.append(
                    "batch_n >= 100 — no alert under revised contract"
                )
            if not reason_for_change:
                reason_for_change.append(
                    f"Status changed from {old_status} to {status['final_status']} "
                    "under revised edge stream"
                )

        results.append({
            "month": month,
            "n": metrics["n"],
            "probability_stream_edge": "RAW_SIGMOID (fip_signal_side_aware)",
            "probability_stream_calibration": "PLATT_CALIBRATED",
            "fip_edge_mean": metrics["fip_edge_mean"],
            "fip_edge_ci_low": metrics["fip_edge_ci_low"],
            "fip_edge_ci_high": metrics["fip_edge_ci_high"],
            "fip_positive_edge_rate": metrics["fip_positive_edge_rate"],
            "platt_ece": metrics["platt_ece"],
            "platt_brier": metrics["platt_brier"],
            "edge_status": status["edge_status"],
            "calibration_status": status["calibration_status"],
            "sample_status": status["sample_status"],
            "final_status": status["final_status"],
            "alert_reasons": status["alert_reasons"],
            "old_p49_status": old_status,
            "old_p49_alert_level": old_alert_level,
            "old_p49_mean_edge": p49_row.get("mean_edge"),
            "old_p49_edge_ci_low": p49_row.get("edge_ci_low"),
            "old_p49_edge_ci_high": p49_row.get("edge_ci_high"),
            "status_changed": status_changed,
            "reason_for_change": reason_for_change,
        })

    return results


# ---------------------------------------------------------------------------
# Rolling revised replay
# ---------------------------------------------------------------------------
def run_rolling_revised_replay(
    tier_c: list[dict],
    p49_rolling_rows: list[dict],
) -> list[dict]:
    n_games = len(tier_c)
    results: list[dict] = []

    p49_by_batch: dict[str, dict] = {r["batch_id"]: r for r in p49_rolling_rows}

    seq = 0
    for start in range(0, n_games, STEP_SIZE):
        batch = tier_c[start : start + BATCH_SIZE]
        if len(batch) < 20:
            break  # skip tiny tail

        seq += 1
        start_date = batch[0]["game_date"]
        end_date = batch[-1]["game_date"]
        batch_id = f"ROLLING_{start_date.replace('-','')}_{end_date.replace('-','')}_{len(batch):04d}_REVISED"
        # Match to P49 batch by date range overlap
        p49_batch_id = f"ROLLING_{start_date.replace('-','')}_{end_date.replace('-','')}_{len(batch):03d}"
        # Try original P49 batch ID format
        p49_row = p49_by_batch.get(p49_batch_id, {})
        if not p49_row:
            # Try alternate format
            orig_id = f"ROLLING_{start_date.replace('-','')}_{end_date.replace('-','')}_{len(batch):04d}"
            p49_row = p49_by_batch.get(orig_id, {})
        if not p49_row:
            # Match by seq position
            p49_row = p49_rolling_rows[seq - 1] if seq - 1 < len(p49_rolling_rows) else {}

        metrics = _compute_batch_metrics(batch)
        status = _apply_revised_alert_rules(
            n=metrics["n"],
            fip_edge_mean=metrics["fip_edge_mean"],
            fip_edge_ci_low=metrics["fip_edge_ci_low"],
            fip_edge_ci_high=metrics["fip_edge_ci_high"],
            platt_ece_val=metrics["platt_ece"],
            platt_brier_val=metrics["platt_brier"],
        )

        old_status = p49_row.get("status", "UNKNOWN") if p49_row else "UNKNOWN"
        status_changed = status["final_status"] != old_status
        reason_for_change = []
        if status_changed and p49_row:
            if "CRITICAL" in old_status and "CRITICAL" not in status["final_status"]:
                reason_for_change.append(
                    "P49 CRITICAL alert was CI_crosses_zero under PLATT home-perspective; "
                    "fip_signal_side_aware CI_low > 0 under revised contract"
                )
            if not reason_for_change:
                reason_for_change.append(
                    f"Status changed from {old_status} to {status['final_status']} "
                    "under revised contract"
                )

        results.append({
            "batch_id": batch_id,
            "seq": seq,
            "start_date": start_date,
            "end_date": end_date,
            "n": metrics["n"],
            "probability_stream_edge": "RAW_SIGMOID (fip_signal_side_aware)",
            "probability_stream_calibration": "PLATT_CALIBRATED",
            "fip_edge_mean": metrics["fip_edge_mean"],
            "fip_edge_ci_low": metrics["fip_edge_ci_low"],
            "fip_edge_ci_high": metrics["fip_edge_ci_high"],
            "fip_positive_edge_rate": metrics["fip_positive_edge_rate"],
            "platt_ece": metrics["platt_ece"],
            "platt_brier": metrics["platt_brier"],
            "edge_status": status["edge_status"],
            "calibration_status": status["calibration_status"],
            "sample_status": status["sample_status"],
            "final_status": status["final_status"],
            "alert_reasons": status["alert_reasons"],
            "old_p49_status": old_status,
            "old_p49_batch_id": p49_row.get("batch_id", "N/A") if p49_row else "N/A",
            "old_p49_mean_edge": p49_row.get("mean_edge") if p49_row else None,
            "old_p49_edge_ci_low": p49_row.get("edge_ci_low") if p49_row else None,
            "old_p49_edge_ci_high": p49_row.get("edge_ci_high") if p49_row else None,
            "status_changed": status_changed,
            "reason_for_change": reason_for_change,
        })

    return results


# ---------------------------------------------------------------------------
# Classify P51
# ---------------------------------------------------------------------------
def classify_p51(
    monthly_results: list[dict],
    rolling_results: list[dict],
) -> str:
    qualifying_monthly = [r for r in monthly_results if r["n"] >= SAMPLE_LIMITED_N]
    qualifying_rolling = [r for r in rolling_results if r["n"] >= SAMPLE_LIMITED_N]

    monthly_critical = sum(1 for r in qualifying_monthly if "CRITICAL" in r["final_status"])
    rolling_critical = sum(1 for r in qualifying_rolling if "CRITICAL" in r["final_status"])

    if not qualifying_monthly and not qualifying_rolling:
        return "P51_SAMPLE_LIMITED"

    # Count how many changed from CRITICAL to non-CRITICAL
    monthly_resolved = sum(
        1 for r in qualifying_monthly
        if "CRITICAL" in r.get("old_p49_status", "") and "CRITICAL" not in r["final_status"]
    )
    rolling_resolved = sum(
        1 for r in qualifying_rolling
        if "CRITICAL" in r.get("old_p49_status", "") and "CRITICAL" not in r["final_status"]
    )

    if monthly_critical == 0 and rolling_critical == 0:
        return "P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC"
    elif monthly_critical > 0 or rolling_critical > 2:
        return "P51_REVISED_CONTRACT_STILL_CRITICAL_DIAGNOSTIC"
    else:
        if monthly_resolved > 0 or rolling_resolved > 3:
            return "P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC"
        return "P51_CONTRACT_REVISION_INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Build comparison summary
# ---------------------------------------------------------------------------
def _build_comparison(monthly: list[dict], rolling: list[dict]) -> dict:
    monthly_old = {
        "ok": sum(1 for r in monthly if r.get("old_p49_status") == "MONITORING_OK"),
        "warning": sum(1 for r in monthly if r.get("old_p49_status") in ("EDGE_DRIFT_WARNING", "CALIBRATION_WARNING", "MIXED_ALERTS")),
        "critical": sum(1 for r in monthly if r.get("old_p49_status") in ("EDGE_DRIFT_CRITICAL", "CALIBRATION_CRITICAL")),
        "sample_limited": sum(1 for r in monthly if r.get("old_p49_status") == "SAMPLE_LIMITED"),
    }
    monthly_new = {
        "ok": sum(1 for r in monthly if r["final_status"] == "MONITORING_OK"),
        "warning": sum(1 for r in monthly if r["final_status"] in ("EDGE_DRIFT_WARNING", "CALIBRATION_WARNING", "MIXED_ALERTS")),
        "critical": sum(1 for r in monthly if "CRITICAL" in r["final_status"]),
        "sample_limited": sum(1 for r in monthly if r["final_status"] == "SAMPLE_LIMITED"),
    }
    rolling_old = {
        "ok": 0,
        "warning": sum(1 for r in rolling if r.get("old_p49_status") in ("EDGE_DRIFT_WARNING", "CALIBRATION_WARNING", "MIXED_ALERTS")),
        "critical": sum(1 for r in rolling if r.get("old_p49_status") in ("EDGE_DRIFT_CRITICAL", "CALIBRATION_CRITICAL", "MIXED_ALERTS") and "CRITICAL" in r.get("old_p49_status", "")),
        "sample_limited": 0,
    }
    rolling_old["ok"] = len(rolling) - rolling_old["warning"] - rolling_old["critical"]
    rolling_new = {
        "ok": sum(1 for r in rolling if r["final_status"] == "MONITORING_OK"),
        "warning": sum(1 for r in rolling if r["final_status"] in ("EDGE_DRIFT_WARNING", "CALIBRATION_WARNING")),
        "critical": sum(1 for r in rolling if "CRITICAL" in r["final_status"]),
        "sample_limited": sum(1 for r in rolling if r["final_status"] == "SAMPLE_LIMITED"),
    }
    return {
        "monthly_old": monthly_old,
        "monthly_new": monthly_new,
        "rolling_old": rolling_old,
        "rolling_new": rolling_new,
        "monthly_false_critical_eliminated": max(0, monthly_old["critical"] - monthly_new["critical"]),
        "rolling_false_critical_eliminated": max(0, rolling_old["critical"] - rolling_new["critical"]),
        "monthly_status_changed_count": sum(1 for r in monthly if r.get("status_changed")),
        "rolling_status_changed_count": sum(1 for r in rolling if r.get("status_changed")),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    sources = _load_sources()
    p49 = sources["p49"]
    p50 = sources["p50"]

    p50_recap = {
        "final_classification": p50.get("final_classification"),
        "root_cause_primary": "Model probability stream mismatch: P49 used model_home_prob (ML, regularized toward 0.5); P44 used sigmoid(sp_fip_delta) (FIP signal, k=1.0).",
        "root_cause_secondary": "Edge perspective: P49 home-perspective (negative for away picks); P44 side-aware (always positive for model-backed side).",
        "root_cause_tertiary": "CI method: P49 normal approximation; P44 bootstrap(5000, seed=42).",
        "fip_signal_result": "fip_signal_side_aware_edge monthly_critical=0, rolling_critical=0 (per P50 Task B).",
    }

    # Task P51.A — Metric ownership matrix
    matrix = build_metric_ownership_matrix()

    # Task P51.B — Revised alert rules
    revised_rules = build_revised_alert_rules()

    # Build tier C for revised replay
    tier_c = build_tier_c_for_revised_replay()
    tier_c_n = len(tier_c)
    print(f"Tier C n={tier_c_n}")

    # Task P51.C — Monthly and rolling revised replay
    p49_monthly_rows = p49["monthly_replay"]["rows"]
    p49_rolling_rows = p49["rolling_replay"]["rows"]

    monthly_results = run_monthly_revised_replay(tier_c, p49_monthly_rows)
    rolling_results = run_rolling_revised_replay(tier_c, p49_rolling_rows)

    # Old vs new comparison
    comparison = _build_comparison(monthly_results, rolling_results)

    # Final classification
    final_classification = classify_p51(monthly_results, rolling_results)
    print(f"Final classification: {final_classification}")

    # Monthly summary
    qualifying = [r for r in monthly_results if r["n"] >= SAMPLE_LIMITED_N]
    monthly_summary = {
        "total_months": len(monthly_results),
        "qualifying_months_n_ge_100": len(qualifying),
        "sample_limited_months": len(monthly_results) - len(qualifying),
        "ok_count": sum(1 for r in monthly_results if r["final_status"] == "MONITORING_OK"),
        "warning_count": sum(1 for r in monthly_results if "WARNING" in r["final_status"]),
        "critical_count": sum(1 for r in monthly_results if "CRITICAL" in r["final_status"]),
        "sample_limited_count": sum(1 for r in monthly_results if r["final_status"] == "SAMPLE_LIMITED"),
    }
    rolling_summary = {
        "total_batches": len(rolling_results),
        "batch_size": BATCH_SIZE,
        "step_size": STEP_SIZE,
        "ok_count": sum(1 for r in rolling_results if r["final_status"] == "MONITORING_OK"),
        "warning_count": sum(1 for r in rolling_results if "WARNING" in r["final_status"]),
        "critical_count": sum(1 for r in rolling_results if "CRITICAL" in r["final_status"]),
        "sample_limited_count": sum(1 for r in rolling_results if r["final_status"] == "SAMPLE_LIMITED"),
        "avg_fip_edge_mean": round(
            sum(r["fip_edge_mean"] for r in rolling_results) / len(rolling_results), 6
        ) if rolling_results else None,
    }

    p51_summary = {
        "version": "P51_v1",
        "audit_date": "2026-05-26",
        "governance": GOVERNANCE_FLAGS,
        "source_artifacts": [
            "p43_strong_edge_closing_line_edge_summary.json",
            "p44_temporal_stability_summary.json",
            "p45_platt_recalibration_summary.json",
            "p47_calibration_synthesis_summary.json",
            "p48_monitoring_loop_contract_summary.json",
            "p49_offline_historical_monitoring_replay_summary.json",
            "p50_edge_drift_root_cause_audit_summary.json",
            "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
        ],
        "platt_coefficients": {
            "platt_a": PLATT_A,
            "platt_b": PLATT_B,
            "sigmoid_k": SIGMOID_K,
            "clip_eps": CLIP_EPS,
            "source": "P45 locked",
        },
        "tier_c_verification": {
            "n": tier_c_n,
            "expected_n": 535,
            "note": "Tier C = 2025 games with sp_fip_delta and market_home_prob_no_vig and home_win available",
        },
        "p50_root_cause_recap": p50_recap,
        "revised_metric_ownership_matrix": matrix,
        "revised_alert_rules": revised_rules,
        "old_vs_new_status_comparison": comparison,
        "monthly_replay_under_revised_contract": {
            "rows": monthly_results,
            "summary": monthly_summary,
        },
        "rolling_replay_under_revised_contract": {
            "rows": rolling_results,
            "summary": rolling_summary,
            "batch_params": {"batch_size": BATCH_SIZE, "step_size": STEP_SIZE},
        },
        "allowed_classifications": [
            "P51_REVISED_CONTRACT_REDUCES_FALSE_ALERTS_DIAGNOSTIC",
            "P51_REVISED_CONTRACT_STILL_CRITICAL_DIAGNOSTIC",
            "P51_CONTRACT_REVISION_INCONCLUSIVE",
            "P51_SAMPLE_LIMITED",
            "P51_BLOCKED_BY_MISSING_SOURCE",
        ],
        "final_classification": final_classification,
        "future_p52_recommendation": (
            "P52 should formally supersede P48/P49 contract artifacts if revised contract "
            "is validated. Do not overwrite P48/P49 until P52 authorization."
        ),
        "data_gap_2024_acknowledged": True,
        "data_gap_2024_note": (
            "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved. "
            "P51 replay covers 2025-only Tier C. Cross-year validation blocked pending 2024 data resolution."
        ),
        "limitations": [
            "2024 closing-line data gap REMAINS UNRESOLVED (P43_BLOCKED_BY_DATA_GAP)",
            f"Bootstrap CI uses numpy random with seed={BOOTSTRAP_SEED} — deterministic but not identical to P44 impl",
            "Market odds source: embedded prediction-time no-vig (not closing-line CSV used in P43/P44)",
            "Rolling batches generated from continuous sort by game_date — same as P49",
            "No live API calls made",
            "No runtime recommendation logic changed",
            "No production proposal",
            "P48 and P49 artifacts NOT overwritten",
        ],
        "framing_note": (
            "This is offline diagnostic audit only. "
            "No production usage proposed. No deployment recommendation. "
            "No profit or deployment readiness implied."
        ),
    }

    out_path = _ROOT / "data/mlb_2025/derived/p51_monitoring_contract_revision_summary.json"
    with open(out_path, "w") as f:
        json.dump(p51_summary, f, indent=2, default=str)
    print(f"Written: {out_path}")

    # Quick print for verification
    print(f"\nMonthly replay summary: {monthly_summary}")
    print(f"Rolling replay summary: {rolling_summary}")
    print(f"Old vs new comparison: {comparison}")
    print(f"\nMonthly rows:")
    for r in monthly_results:
        print(f"  {r['month']}: n={r['n']} fip_edge={r['fip_edge_mean']:.4f} "
              f"ci=[{r['fip_edge_ci_low']:.4f},{r['fip_edge_ci_high']:.4f}] "
              f"final={r['final_status']} old={r['old_p49_status']} changed={r['status_changed']}")
    print(f"\nRolling rows:")
    for r in rolling_results:
        print(f"  {r['batch_id']}: n={r['n']} fip_edge={r['fip_edge_mean']:.4f} "
              f"ci=[{r['fip_edge_ci_low']:.4f},{r['fip_edge_ci_high']:.4f}] "
              f"final={r['final_status']} old={r['old_p49_status']} changed={r['status_changed']}")


if __name__ == "__main__":
    main()
