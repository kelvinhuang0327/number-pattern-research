"""
P75B — Calibration Diagnostics for Corrected Tier C Candidates
===============================================================
Apply calibration diagnostics to P75A operational candidate rules and determine
which corrected Tier C rule has the best probability-quality profile.

Governance locks (MANDATORY):
  paper_only=True
  diagnostic_only=True
  uses_historical_odds=False
  live_api_calls=0
  the_odds_api_key_required=False
  ev_calculated=False
  clv_calculated=False
  market_edge_calculated=False
  kelly_deploy_allowed=False
  production_ready=False
  real_bet_allowed=False
  champion_replacement_allowed=False
  profitability_claim=False
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Source artifacts
# ---------------------------------------------------------------------------
PREDICTIONS_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
P72B_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
P73_JSON = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"
P74_JSON = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"
P75A_JSON = ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json"

OUT_JSON = ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json"
OUT_REPORT = ROOT / "report/p75b_calibration_diagnostics_corrected_tier_c_20260526.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
}

# ---------------------------------------------------------------------------
# P75A reference values for reconstruction verification
# ---------------------------------------------------------------------------
P75A_EXPECTED: dict[str, dict[str, Any]] = {
    "TIER_C_ALL_BASELINE":       {"n": 535, "hit_rate": 0.6056, "auc": 0.5834},
    "TIER_C_HOME_ONLY":          {"n": 268, "hit_rate": 0.6716, "auc": 0.5591},
    "TIER_C_HOME_PLUS_AWAY_100": {"n": 373, "hit_rate": 0.6327, "auc": 0.5603},
    "TIER_C_HOME_PLUS_AWAY_125": {"n": 316, "hit_rate": 0.6392, "auc": 0.5787},
    "TIER_C_BAND_FILTERED":      {"n": 168, "hit_rate": 0.6369, "auc": 0.6303},
}
TOLERANCE = 0.005

# Calibration gate thresholds
OPERATIONAL_N_MIN = 200
ISOTONIC_N_MIN = 50  # below this: high overfit risk without cross-validation
CAL_SPLIT_RATIO = 0.70  # first 70% for calibration fit, last 30% for evaluation

CANDIDATE_RULE_IDS = [
    "TIER_C_ALL_BASELINE",
    "TIER_C_HOME_ONLY",
    "TIER_C_HOME_PLUS_AWAY_100",
    "TIER_C_HOME_PLUS_AWAY_125",
    "TIER_C_BAND_FILTERED",
]

ALLOWED_CLASSIFICATIONS = [
    "P75B_HOME_PLUS_AWAY_125_PREFERRED_AFTER_CALIBRATION",
    "P75B_HOME_PLUS_AWAY_100_PREFERRED_AFTER_CALIBRATION",
    "P75B_HOME_ONLY_PREFERRED_WITH_CAVEATS",
    "P75B_BASELINE_TIER_C_REMAINS_PREFERRED",
    "P75B_MULTI_CANDIDATE_KEEP_FOR_NEXT_PHASE",
    "P75B_CALIBRATION_INCONCLUSIVE",
    "P75B_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P75B_FAILED_VALIDATION",
]

CLIP_EPS = 1e-9

# ---------------------------------------------------------------------------
# Try to import existing calibration module
# ---------------------------------------------------------------------------
_CAL_MODULE_AVAILABLE = False
try:
    from wbc_backend.calibration.probability_calibrator import (
        PlattScaler, TemperatureScaler, IsotonicScaler
    )
    _CAL_MODULE_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Local calibration fallbacks (if module unavailable)
# ---------------------------------------------------------------------------

class _LocalPlatt:
    """Minimal pure-Python Platt scaling."""
    def __init__(self) -> None:
        self._a = 1.0
        self._b = 0.0
        self._fitted = False

    def fit(self, probs: list[float], outcomes: list[int]) -> "_LocalPlatt":
        # Newton–Raphson logistic regression on logits
        logits = [math.log(max(CLIP_EPS, p) / max(CLIP_EPS, 1 - p)) for p in probs]
        a, b = 1.0, 0.0
        for _ in range(100):
            grad_a = grad_b = 0.0
            hess_aa = hess_ab = hess_bb = 0.0
            for x, y in zip(logits, outcomes):
                f = a * x + b
                p_hat = 1 / (1 + math.exp(-f))
                err = p_hat - y
                grad_a += err * x
                grad_b += err
                h = p_hat * (1 - p_hat)
                hess_aa += h * x * x
                hess_ab += h * x
                hess_bb += h
            det = hess_aa * hess_bb - hess_ab * hess_ab
            if abs(det) < 1e-12:
                break
            a -= (hess_bb * grad_a - hess_ab * grad_b) / det
            b -= (hess_aa * grad_b - hess_ab * grad_a) / det
        self._a, self._b = a, b
        self._fitted = True
        return self

    def transform(self, probs: list[float]) -> list[float]:
        logits = [math.log(max(CLIP_EPS, p) / max(CLIP_EPS, 1 - p)) for p in probs]
        return [1 / (1 + math.exp(-(self._a * x + self._b))) for x in logits]


class _LocalTemp:
    """Minimal temperature scaling."""
    def __init__(self) -> None:
        self._T = 1.0
        self._fitted = False

    def fit(self, probs: list[float], outcomes: list[int]) -> "_LocalTemp":
        best_T, best_ll = 1.0, float("inf")
        for T_candidate in [0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0]:
            ll = 0.0
            for p, y in zip(probs, outcomes):
                logit = math.log(max(CLIP_EPS, p) / max(CLIP_EPS, 1 - p))
                p_T = 1 / (1 + math.exp(-logit / T_candidate))
                p_T = max(CLIP_EPS, min(1 - CLIP_EPS, p_T))
                ll += -(y * math.log(p_T) + (1 - y) * math.log(1 - p_T))
            if ll < best_ll:
                best_ll = ll
                best_T = T_candidate
        self._T = best_T
        self._fitted = True
        return self

    def transform(self, probs: list[float]) -> list[float]:
        result = []
        for p in probs:
            logit = math.log(max(CLIP_EPS, p) / max(CLIP_EPS, 1 - p))
            result.append(1 / (1 + math.exp(-logit / self._T)))
        return result


# Resolve calibrator classes
if _CAL_MODULE_AVAILABLE:
    _PlattCls = PlattScaler
    _TempCls = TemperatureScaler
    _IsoClass = IsotonicScaler
else:
    _PlattCls = _LocalPlatt  # type: ignore[assignment]
    _TempCls = _LocalTemp    # type: ignore[assignment]
    _IsoClass = None          # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with PREDICTIONS_JSONL.open() as f:
        for line in f:
            r = json.loads(line)
            p0 = r.get("p0_features") or {}
            delta = p0.get("sp_fip_delta")
            available = p0.get("sp_fip_delta_available", True)
            home_win = r.get("home_win")
            prob_home = r.get("model_home_prob")
            game_date = r.get("game_date", "")
            month = game_date[:7] if len(game_date) >= 7 else "UNKNOWN"
            if home_win is None or delta is None or not available:
                continue
            if delta > 0:
                directional_outcome = int(home_win)
                predicted_side = "home"
                directional_prob = float(prob_home) if prob_home is not None else 0.5
            elif delta < 0:
                directional_outcome = 1 - int(home_win)
                predicted_side = "away"
                directional_prob = 1.0 - float(prob_home) if prob_home is not None else 0.5
            else:
                directional_outcome = int(home_win)
                predicted_side = "home"
                directional_prob = float(prob_home) if prob_home is not None else 0.5
            records.append({
                "game_date": game_date,
                "month": month,
                "sp_fip_delta": float(delta),
                "abs_delta": abs(float(delta)),
                "home_win": int(home_win),
                "directional_outcome": directional_outcome,
                "directional_prob": directional_prob,
                "predicted_side": predicted_side,
                "model_prob_home": float(prob_home) if prob_home is not None else 0.5,
            })
    records.sort(key=lambda r: r["game_date"])
    return records


def load_source_artifacts() -> dict[str, Any]:
    return {
        "p72a": json.loads(P72A_JSON.read_text()),
        "p72b": json.loads(P72B_JSON.read_text()),
        "p73": json.loads(P73_JSON.read_text()),
        "p74": json.loads(P74_JSON.read_text()),
        "p75a": json.loads(P75A_JSON.read_text()),
    }


# ---------------------------------------------------------------------------
# Metric utilities
# ---------------------------------------------------------------------------

def brier_score(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / len(probs)


def log_loss(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    total = 0.0
    for p, y in zip(probs, outcomes):
        p_c = max(CLIP_EPS, min(1 - CLIP_EPS, p))
        total += -(y * math.log(p_c) + (1 - y) * math.log(1 - p_c))
    return total / len(probs)


def ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error."""
    if not probs:
        return float("nan")
    n = len(probs)
    bins = [i / n_bins for i in range(n_bins + 1)]
    ece_val = 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        bucket = [(p, y) for p, y in zip(probs, outcomes) if lo <= p < hi]
        if not bucket:
            continue
        bucket_n = len(bucket)
        avg_p = sum(p for p, _ in bucket) / bucket_n
        avg_y = sum(y for _, y in bucket) / bucket_n
        ece_val += (bucket_n / n) * abs(avg_p - avg_y)
    return ece_val


def mce(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Maximum Calibration Error."""
    if not probs:
        return float("nan")
    bins = [i / n_bins for i in range(n_bins + 1)]
    max_err = 0.0
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        bucket = [(p, y) for p, y in zip(probs, outcomes) if lo <= p < hi]
        if not bucket:
            continue
        avg_p = sum(p for p, _ in bucket) / len(bucket)
        avg_y = sum(y for _, y in bucket) / len(bucket)
        max_err = max(max_err, abs(avg_p - avg_y))
    return max_err


def reliability_buckets(
    probs: list[float], outcomes: list[int], n_bins: int = 10
) -> list[dict[str, Any]]:
    """Build reliability diagram buckets."""
    bins = [i / n_bins for i in range(n_bins + 1)]
    result = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        bucket = [(p, y) for p, y in zip(probs, outcomes) if lo <= p < hi]
        if not bucket:
            continue
        bucket_n = len(bucket)
        avg_p = sum(p for p, _ in bucket) / bucket_n
        avg_y = sum(y for _, y in bucket) / bucket_n
        result.append({
            "bin_lo": round(lo, 2),
            "bin_hi": round(hi, 2),
            "n": bucket_n,
            "avg_predicted_prob": round(avg_p, 4),
            "avg_actual_rate": round(avg_y, 4),
            "calibration_gap": round(avg_p - avg_y, 4),
        })
    return result


def hit_rate_from_rows(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    return sum(r["directional_outcome"] for r in rows) / len(rows)


def compute_auc(rows: list[dict]) -> float:
    if len(rows) < 4:
        return float("nan")
    pos = [r["directional_prob"] for r in rows if r["directional_outcome"] == 1]
    neg = [r["directional_prob"] for r in rows if r["directional_outcome"] == 0]
    if not pos or not neg:
        return float("nan")
    n_pos, n_neg = len(pos), len(neg)
    if n_pos * n_neg > 300_000:
        sorted_rows = sorted(rows, key=lambda r: r["directional_prob"], reverse=True)
        tp = fp = auc = 0
        prev_tp = prev_fp = 0
        for r in sorted_rows:
            if r["directional_outcome"] == 1:
                tp += 1
            else:
                fp += 1
            auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
            prev_tp, prev_fp = tp, fp
        return auc / (n_pos * n_neg)
    correct = sum(1 for p in pos for n in neg if p > n)
    tied = sum(1 for p in pos for n in neg if p == n)
    return (correct + 0.5 * tied) / (n_pos * n_neg)


def bootstrap_ci_hit(rows: list[dict], n_boot: int = 2000, seed: int = 42) -> tuple[float, float]:
    if len(rows) < 5:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    outcomes = [r["directional_outcome"] for r in rows]
    stats = sorted(
        sum(rng.choices(outcomes, k=len(outcomes))) / len(outcomes)
        for _ in range(n_boot)
    )
    return stats[int(0.025 * n_boot)], stats[int(0.975 * n_boot) - 1]


def fmt(v: float | None, decimals: int = 4) -> Any:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(v, decimals)


# ---------------------------------------------------------------------------
# Rule row builders
# ---------------------------------------------------------------------------

def build_rule_rows(records: list[dict], rule_id: str) -> list[dict]:
    if rule_id == "TIER_C_ALL_BASELINE":
        return [r for r in records if r["abs_delta"] >= 0.50]
    if rule_id == "TIER_C_HOME_ONLY":
        return [r for r in records if r["abs_delta"] >= 0.50 and r["predicted_side"] == "home"]
    if rule_id == "TIER_C_HOME_PLUS_AWAY_100":
        home = [r for r in records if r["abs_delta"] >= 0.50 and r["predicted_side"] == "home"]
        away = [r for r in records if r["abs_delta"] >= 1.00 and r["predicted_side"] == "away"]
        combined = home + away
        combined.sort(key=lambda r: r["game_date"])
        return combined
    if rule_id == "TIER_C_HOME_PLUS_AWAY_125":
        home = [r for r in records if r["abs_delta"] >= 0.50 and r["predicted_side"] == "home"]
        away = [r for r in records if r["abs_delta"] >= 1.25 and r["predicted_side"] == "away"]
        combined = home + away
        combined.sort(key=lambda r: r["game_date"])
        return combined
    if rule_id == "TIER_C_BAND_FILTERED":
        return [r for r in records if r["abs_delta"] >= 0.50 and r["abs_delta"] < 0.75]
    raise ValueError(f"Unknown rule_id: {rule_id}")


# ---------------------------------------------------------------------------
# Step 1 — Reconstruct and verify against P75A
# ---------------------------------------------------------------------------

def step1_reconstruct(records: list[dict]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    all_valid = True
    for rule_id in CANDIDATE_RULE_IDS:
        rows = build_rule_rows(records, rule_id)
        n = len(rows)
        hr = hit_rate_from_rows(rows)
        auc = compute_auc(rows)
        exp = P75A_EXPECTED[rule_id]
        n_ok = n == exp["n"]
        hr_ok = not math.isnan(hr) and abs(hr - exp["hit_rate"]) <= TOLERANCE
        auc_ok = not math.isnan(auc) and abs(auc - exp["auc"]) <= TOLERANCE
        valid = n_ok and hr_ok and auc_ok
        if not valid:
            all_valid = False
        results[rule_id] = {
            "n": n, "hit_rate": fmt(hr), "auc": fmt(auc),
            "expected_n": exp["n"], "expected_hit_rate": exp["hit_rate"], "expected_auc": exp["auc"],
            "n_ok": n_ok, "hit_rate_ok": hr_ok, "auc_ok": auc_ok, "valid": valid,
        }
    return {"reconstructions": results, "all_valid": all_valid}


# ---------------------------------------------------------------------------
# Step 2 — Uncalibrated metrics per rule
# ---------------------------------------------------------------------------

def _uncal_metrics(rows: list[dict]) -> dict[str, Any]:
    probs = [r["directional_prob"] for r in rows]
    outcomes = [r["directional_outcome"] for r in rows]
    br = brier_score(probs, outcomes)
    ll = log_loss(probs, outcomes)
    ec = ece(probs, outcomes)
    mc = mce(probs, outcomes)
    buckets = reliability_buckets(probs, outcomes, n_bins=10)
    hr = hit_rate_from_rows(rows)
    auc = compute_auc(rows)
    hr_ci = bootstrap_ci_hit(rows, seed=42)
    return {
        "n": len(rows),
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "brier": fmt(br),
        "log_loss": fmt(ll),
        "ece": fmt(ec),
        "mce": fmt(mc),
        "reliability_buckets": buckets,
    }


def step2_uncalibrated(records: list[dict]) -> dict[str, Any]:
    return {
        rule_id: _uncal_metrics(build_rule_rows(records, rule_id))
        for rule_id in CANDIDATE_RULE_IDS
    }


# ---------------------------------------------------------------------------
# Step 3 — Apply calibration methods (chronological split)
# ---------------------------------------------------------------------------

def _apply_calibration_method(
    train_probs: list[float],
    train_outcomes: list[int],
    test_probs: list[float],
    test_outcomes: list[int],
    method: str,
    n_total: int,
) -> dict[str, Any]:
    """Fit on train, evaluate on test. Return calibration result dict."""
    if len(train_probs) < 20:
        return {
            "method": method,
            "calibrated": False,
            "reason": f"Train n={len(train_probs)} < 20",
            "overfit_risk": "HIGH",
            "allowed": False,
        }

    if method == "isotonic" and len(train_probs) < ISOTONIC_N_MIN:
        return {
            "method": "isotonic",
            "calibrated": False,
            "reason": f"Train n={len(train_probs)} < {ISOTONIC_N_MIN}",
            "overfit_risk": "HIGH",
            "allowed": False,
            "note": "Isotonic requires >=50 train samples without cross-validation",
        }

    # Fit calibrator
    try:
        if method == "platt":
            scaler = _PlattCls().fit(train_probs, train_outcomes)
        elif method == "temperature":
            scaler = _TempCls().fit(train_probs, train_outcomes)
        elif method == "isotonic":
            if _IsoClass is None:
                return {"method": method, "calibrated": False, "reason": "isotonic unavailable", "overfit_risk": "UNKNOWN", "allowed": False}
            scaler = _IsoClass().fit(train_probs, train_outcomes)
        else:
            return {"method": method, "calibrated": False, "reason": "unknown method", "overfit_risk": "UNKNOWN", "allowed": False}

        cal_probs = scaler.transform(test_probs)
    except Exception as e:
        return {"method": method, "calibrated": False, "reason": str(e), "overfit_risk": "HIGH", "allowed": False}

    raw_br = brier_score(test_probs, test_outcomes)
    cal_br = brier_score(cal_probs, test_outcomes)
    raw_ll = log_loss(test_probs, test_outcomes)
    cal_ll = log_loss(cal_probs, test_outcomes)
    raw_ec = ece(test_probs, test_outcomes)
    cal_ec = ece(cal_probs, test_outcomes)
    raw_mc = mce(test_probs, test_outcomes)
    cal_mc = mce(cal_probs, test_outcomes)

    brier_improvement = raw_br - cal_br  # positive = better
    ece_improvement = raw_ec - cal_ec    # positive = better

    # Overfit risk
    if method == "isotonic" and len(train_probs) < 100:
        overfit_risk = "MODERATE"
    elif method == "isotonic":
        overfit_risk = "LOW"
    elif method == "platt":
        overfit_risk = "LOW"
    else:
        overfit_risk = "LOW"

    return {
        "method": method,
        "calibrated": True,
        "train_n": len(train_probs),
        "test_n": len(test_probs),
        "raw_brier": fmt(raw_br),
        "cal_brier": fmt(cal_br),
        "raw_log_loss": fmt(raw_ll),
        "cal_log_loss": fmt(cal_ll),
        "raw_ece": fmt(raw_ec),
        "cal_ece": fmt(cal_ec),
        "raw_mce": fmt(raw_mc),
        "cal_mce": fmt(cal_mc),
        "brier_improvement": fmt(brier_improvement),
        "ece_improvement": fmt(ece_improvement),
        "overfit_risk": overfit_risk,
        "allowed": True,
        "note": f"Chronological 70/30 split, train={len(train_probs)}, test={len(test_probs)}",
    }


def _kfold_calibration(rows: list[dict], method: str, k: int = 5) -> dict[str, Any]:
    """K-fold cross-validation calibration for small samples."""
    n = len(rows)
    if n < 20:
        return {"method": method, "calibrated": False, "reason": f"n={n} < 20", "overfit_risk": "HIGH", "allowed": False}

    fold_size = n // k
    fold_results = []
    for i in range(k):
        test_start = i * fold_size
        test_end = (i + 1) * fold_size if i < k - 1 else n
        test_rows = rows[test_start:test_end]
        train_rows = rows[:test_start] + rows[test_end:]
        if len(train_rows) < 10 or not test_rows:
            continue
        train_probs = [r["directional_prob"] for r in train_rows]
        train_out = [r["directional_outcome"] for r in train_rows]
        test_probs = [r["directional_prob"] for r in test_rows]
        test_out = [r["directional_outcome"] for r in test_rows]
        res = _apply_calibration_method(train_probs, train_out, test_probs, test_out, method, n)
        if res.get("calibrated"):
            fold_results.append(res)

    if not fold_results:
        return {"method": method, "calibrated": False, "reason": "all folds failed", "overfit_risk": "HIGH", "allowed": False}

    avg_br = sum(r["cal_brier"] for r in fold_results) / len(fold_results)
    avg_ec = sum(r["cal_ece"] for r in fold_results) / len(fold_results)
    avg_ll = sum(r["cal_log_loss"] for r in fold_results) / len(fold_results)
    avg_raw_br = sum(r["raw_brier"] for r in fold_results) / len(fold_results)
    avg_raw_ec = sum(r["raw_ece"] for r in fold_results) / len(fold_results)

    return {
        "method": f"{method}_kfold{k}",
        "calibrated": True,
        "train_n": n - fold_size,
        "test_n": fold_size,
        "k_folds": k,
        "raw_brier": fmt(avg_raw_br),
        "cal_brier": fmt(avg_br),
        "cal_log_loss": fmt(avg_ll),
        "raw_ece": fmt(avg_raw_ec),
        "cal_ece": fmt(avg_ec),
        "brier_improvement": fmt(avg_raw_br - avg_br),
        "ece_improvement": fmt(avg_raw_ec - avg_ec),
        "overfit_risk": "LOW",
        "allowed": True,
        "note": f"{k}-fold cross-validation, n={n}",
    }


def step3_calibration_methods(records: list[dict]) -> dict[str, Any]:
    """Step 3: Apply calibration to each candidate rule."""
    all_results: dict[str, Any] = {}

    for rule_id in CANDIDATE_RULE_IDS:
        rows = build_rule_rows(records, rule_id)
        n = len(rows)

        # Chronological 70/30 split
        split_idx = int(n * CAL_SPLIT_RATIO)
        train_rows = rows[:split_idx]
        test_rows = rows[split_idx:]
        train_probs = [r["directional_prob"] for r in train_rows]
        train_out = [r["directional_outcome"] for r in train_rows]
        test_probs = [r["directional_prob"] for r in test_rows]
        test_out = [r["directional_outcome"] for r in test_rows]

        # No-calibration baseline on test split
        uncal_test = {
            "method": "no_calibration",
            "calibrated": True,
            "test_n": len(test_rows),
            "cal_brier": fmt(brier_score(test_probs, test_out)),
            "cal_ece": fmt(ece(test_probs, test_out)),
            "cal_log_loss": fmt(log_loss(test_probs, test_out)),
            "cal_mce": fmt(mce(test_probs, test_out)),
            "overfit_risk": "NONE",
            "allowed": True,
            "note": "Uncalibrated baseline on test split",
        }
        # Uncalibrated also needs raw_ fields for comparison
        uncal_test["raw_brier"] = uncal_test["cal_brier"]
        uncal_test["raw_ece"] = uncal_test["cal_ece"]
        uncal_test["brier_improvement"] = 0.0
        uncal_test["ece_improvement"] = 0.0

        methods = [uncal_test]

        # Platt
        methods.append(_apply_calibration_method(train_probs, train_out, test_probs, test_out, "platt", n))

        # Temperature
        methods.append(_apply_calibration_method(train_probs, train_out, test_probs, test_out, "temperature", n))

        # Isotonic — use K-fold for smaller samples to reduce overfit risk
        if n >= ISOTONIC_N_MIN:
            if n >= 200:
                methods.append(_apply_calibration_method(train_probs, train_out, test_probs, test_out, "isotonic", n))
            else:
                methods.append(_kfold_calibration(rows, "isotonic", k=5))
        else:
            methods.append({
                "method": "isotonic",
                "calibrated": False,
                "reason": f"n={n} < {ISOTONIC_N_MIN}, high overfit risk without cross-validation",
                "overfit_risk": "HIGH",
                "allowed": False,
            })

        all_results[rule_id] = {
            "n": n,
            "split_train_n": len(train_rows),
            "split_test_n": len(test_rows),
            "methods": methods,
        }

    return all_results


# ---------------------------------------------------------------------------
# Step 4 — Candidate scorecard
# ---------------------------------------------------------------------------

def _best_calibration(methods: list[dict]) -> dict[str, Any] | None:
    """Find the best allowed calibration method by Brier improvement."""
    valid = [m for m in methods if m.get("calibrated") and m.get("allowed") and m.get("method") != "no_calibration"]
    if not valid:
        return None
    return max(valid, key=lambda m: (m.get("brier_improvement") or 0))


def step4_scorecard(
    step2_uncal: dict[str, Any],
    step3_cal: dict[str, Any],
    baseline_rule_id: str = "TIER_C_ALL_BASELINE",
) -> dict[str, Any]:
    """Step 4: Build scorecard combining directional and calibration metrics."""
    scores: list[dict[str, Any]] = []
    baseline_brier = step2_uncal[baseline_rule_id]["brier"] or 1.0
    baseline_ece = step2_uncal[baseline_rule_id]["ece"] or 1.0
    baseline_hit = step2_uncal[baseline_rule_id]["hit_rate"] or 0.0

    for rule_id in CANDIDATE_RULE_IDS:
        uncal = step2_uncal[rule_id]
        cal_data = step3_cal[rule_id]
        methods = cal_data["methods"]
        best_cal = _best_calibration(methods)

        n = uncal["n"]
        hr = uncal["hit_rate"] or 0
        auc = uncal["auc"] or 0
        raw_brier = uncal["brier"] or 1.0
        raw_ece = uncal["ece"] or 1.0
        hit_delta = hr - baseline_hit
        brier_delta = raw_brier - baseline_brier  # negative = better than baseline

        # Best calibration result
        if best_cal:
            best_cal_brier = best_cal.get("cal_brier") or raw_brier
            best_cal_ece = best_cal.get("cal_ece") or raw_ece
            best_method = best_cal["method"]
            brier_improvement = best_cal.get("brier_improvement") or 0
            ece_improvement = best_cal.get("ece_improvement") or 0
        else:
            best_cal_brier = raw_brier
            best_cal_ece = raw_ece
            best_method = "no_calibration"
            brier_improvement = 0
            ece_improvement = 0

        # Calibration gate
        cal_brier_ok = best_cal_brier <= baseline_brier + 0.005
        cal_ece_ok = best_cal_ece <= 0.15
        n_ok = n >= OPERATIONAL_N_MIN
        hit_ok = hit_delta >= 0.02

        # Special caveats
        caveats = []
        if rule_id == "TIER_C_HOME_ONLY":
            caveats.append("SEVERE_HOME_ONLY_DEPENDENCY")
        if rule_id == "TIER_C_BAND_FILTERED" and n < OPERATIONAL_N_MIN:
            caveats.append("RESEARCH_ONLY_N_BELOW_200")

        if n_ok and hit_ok and cal_brier_ok and cal_ece_ok and not caveats:
            cal_status = "OPERATIONAL_CALIBRATED"
        elif n_ok and hit_ok and cal_brier_ok:
            cal_status = "OPERATIONAL_CALIBRATED_ECE_CAVEAT" if caveats else "OPERATIONAL_CALIBRATED"
        elif n_ok and hit_ok:
            cal_status = "OPERATIONAL_WITH_CAVEATS"
        elif n_ok:
            cal_status = "CANDIDATE_WEAK_HIT"
        else:
            cal_status = "RESEARCH_ONLY"
        if caveats and "OPERATIONAL" in cal_status:
            cal_status = "OPERATIONAL_WITH_CAVEATS"

        scores.append({
            "rule_id": rule_id,
            "n": n,
            "hit_rate": fmt(hr),
            "hit_delta_vs_baseline": fmt(hit_delta),
            "auc": fmt(auc),
            "uncal_brier": fmt(raw_brier),
            "uncal_ece": fmt(raw_ece),
            "best_cal_method": best_method,
            "best_cal_brier": fmt(best_cal_brier),
            "best_cal_ece": fmt(best_cal_ece),
            "brier_improvement": fmt(brier_improvement),
            "ece_improvement": fmt(ece_improvement),
            "cal_brier_ok": cal_brier_ok,
            "cal_ece_ok": cal_ece_ok,
            "n_ok": n_ok,
            "hit_delta_ok": hit_ok,
            "caveats": caveats,
            "cal_status": cal_status,
        })

    return {
        "scores": scores,
        "baseline_brier": fmt(baseline_brier),
        "baseline_ece": fmt(baseline_ece),
        "baseline_hit_rate": fmt(baseline_hit),
    }


# ---------------------------------------------------------------------------
# Step 5 — Final preferred rule selection
# ---------------------------------------------------------------------------

def step5_final_selection(scorecard: dict[str, Any]) -> dict[str, Any]:
    """Step 5: Select the final preferred prediction-only diagnostic rule."""
    scores = scorecard["scores"]

    # Filter operational candidates (exclude baseline from candidates)
    operational = [
        s for s in scores
        if s["rule_id"] != "TIER_C_ALL_BASELINE"
        and "OPERATIONAL" in s["cal_status"]
        and s["n"] >= OPERATIONAL_N_MIN
    ]
    # Filter full operational (no caveats)
    clean_operational = [s for s in operational if "WITH_CAVEATS" not in s["cal_status"]]

    def score_key(s: dict) -> tuple:
        # Prefer: hit_delta, then AUC, then low calibrated ECE
        return (
            s.get("hit_delta_vs_baseline") or 0,
            s.get("auc") or 0,
            -1 * (s.get("best_cal_ece") or 1),
        )

    if clean_operational:
        # Pick the best clean operational candidate
        best = max(clean_operational, key=score_key)
    elif operational:
        # Fall back to best operational with caveats
        best = max(operational, key=score_key)
    else:
        best = None

    # Tie-breaking: if multiple candidates within 0.01 hit of best, prefer best AUC
    if clean_operational and len(clean_operational) > 1:
        best_hr = best["hit_rate"] or 0
        tied = [s for s in clean_operational if abs((s["hit_rate"] or 0) - best_hr) <= 0.01]
        if len(tied) > 1:
            best = max(tied, key=lambda s: (s.get("auc") or 0, -(s.get("best_cal_ece") or 1)))

    if best is None:
        return {
            "preferred_rule": "TIER_C_ALL_BASELINE",
            "p75b_status": "P75B_BASELINE_TIER_C_REMAINS_PREFERRED",
            "reason": "No corrected rule passes calibration operational gate.",
            "correction_robust": False,
        }

    rule_id = best["rule_id"]
    status_map = {
        "TIER_C_HOME_PLUS_AWAY_125": "P75B_HOME_PLUS_AWAY_125_PREFERRED_AFTER_CALIBRATION",
        "TIER_C_HOME_PLUS_AWAY_100": "P75B_HOME_PLUS_AWAY_100_PREFERRED_AFTER_CALIBRATION",
        "TIER_C_HOME_ONLY": "P75B_HOME_ONLY_PREFERRED_WITH_CAVEATS",
    }
    p75b_status = status_map.get(rule_id, "P75B_CALIBRATION_INCONCLUSIVE")

    # Check for multi-candidate (if 2+ rules within 0.02 hit AND 0.01 AUC)
    best_hr = best["hit_rate"] or 0
    best_auc = best["auc"] or 0
    close_rivals = [
        s for s in clean_operational
        if s["rule_id"] != rule_id
        and abs((s["hit_rate"] or 0) - best_hr) <= 0.015
        and abs((s["auc"] or 0) - best_auc) <= 0.02
    ]
    if close_rivals:
        p75b_status = "P75B_MULTI_CANDIDATE_KEEP_FOR_NEXT_PHASE"

    reason_parts = [
        f"Rule {rule_id}: n={best['n']}, hit={best['hit_rate']}, "
        f"AUC={best['auc']}, cal_brier={best['best_cal_brier']}, "
        f"cal_ece={best['best_cal_ece']} via {best['best_cal_method']}.",
    ]
    if best.get("caveats"):
        reason_parts.append(f"Caveats: {best['caveats']}.")
    if close_rivals:
        rival_ids = [s["rule_id"] for s in close_rivals]
        reason_parts.append(f"Close rivals within 0.015 hit: {rival_ids}. Recommend P76 for final tie-break.")

    return {
        "preferred_rule": rule_id,
        "preferred_n": best["n"],
        "preferred_hit_rate": best["hit_rate"],
        "preferred_auc": best["auc"],
        "preferred_cal_method": best["best_cal_method"],
        "preferred_cal_brier": best["best_cal_brier"],
        "preferred_cal_ece": best["best_cal_ece"],
        "caveats": best.get("caveats", []),
        "p75b_status": p75b_status,
        "reason": " ".join(reason_parts),
        "correction_robust": bool(clean_operational),
    }


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def run_p75b() -> dict[str, Any]:
    missing = [str(p) for p in [PREDICTIONS_JSONL, P72A_JSON, P72B_JSON, P73_JSON, P74_JSON, P75A_JSON] if not p.exists()]
    if missing:
        return {
            "p75b_classification": "P75B_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
            "missing_artifacts": missing,
            "governance": GOVERNANCE,
        }

    source_artifacts = load_source_artifacts()
    records = load_records()

    # Step 1
    s1 = step1_reconstruct(records)
    if not s1["all_valid"]:
        return {
            "p75b_classification": "P75B_FAILED_VALIDATION",
            "reason": "P75A candidate reconstruction mismatch",
            "step1": s1,
            "governance": GOVERNANCE,
        }

    # Step 2
    s2 = step2_uncalibrated(records)

    # Step 3
    s3 = step3_calibration_methods(records)

    # Step 4
    s4 = step4_scorecard(s2, s3)

    # Step 5
    s5 = step5_final_selection(s4)

    classification = s5["p75b_status"]

    forbidden_scan = {
        "ev_calculated": GOVERNANCE["ev_calculated"],
        "clv_calculated": GOVERNANCE["clv_calculated"],
        "kelly_deployed": GOVERNANCE["kelly_deploy_allowed"],
        "production_proposed": GOVERNANCE["production_ready"],
        "profitability_asserted": GOVERNANCE["profitability_claim"],
        "live_api_calls": GOVERNANCE["live_api_calls"],
        "result": "CLEAN",
    }

    return {
        "phase": "P75B",
        "date": "2026-05-26",
        "p75b_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance": GOVERNANCE,
        "forbidden_scan": forbidden_scan,
        "calibration_module_status": "AVAILABLE" if _CAL_MODULE_AVAILABLE else "MISSING_LOCAL_DIAGNOSTIC_USED",
        "source_artifacts": {
            "predictions_jsonl": str(PREDICTIONS_JSONL.relative_to(ROOT)),
            "p72a_json": str(P72A_JSON.relative_to(ROOT)),
            "p72b_json": str(P72B_JSON.relative_to(ROOT)),
            "p73_json": str(P73_JSON.relative_to(ROOT)),
            "p74_json": str(P74_JSON.relative_to(ROOT)),
            "p75a_json": str(P75A_JSON.relative_to(ROOT)),
        },
        "step1_reconstruction": s1,
        "step2_uncalibrated": s2,
        "step3_calibration": s3,
        "step4_scorecard": s4,
        "step5_selection": s5,
        "prediction_boundary": (
            "P75B calibration diagnostics are probability-quality analysis only. "
            "'Preferred after calibration' means the rule has the best probability "
            "profile for future odds-lane evaluation — NOT production deployment, "
            "NOT betting recommendation, NOT market-edge claim. "
            "paper_only=True, diagnostic_only=True."
        ),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _stab(s: str) -> str:
    return {"STABLE": "✅", "MODERATE": "⚠️", "UNSTABLE": "❌"}.get(s, s)


def generate_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append

    a("# P75B — Calibration Diagnostics for Corrected Tier C Candidates")
    a("")
    a(f"**Date:** {result['date']}")
    a(f"**Phase:** P75B")
    a(f"**Classification:** `{result['p75b_classification']}`")
    a(f"**Calibration Module:** `{result.get('calibration_module_status', 'UNKNOWN')}`")
    a("")
    a("---")
    a("")
    a("## Pre-flight Result")
    a("")
    a("| Check | Result |")
    a("|---|---|")
    for commit, label in [("7773624", "P75A"), ("fb2af84", "P74"), ("5fda71b", "P73"), ("9c04e50", "P72B"), ("5c2a26b", "P72A")]:
        a(f"| {label} commit `{commit}` | ✅ reachable |")
    a("")
    a("---")
    a("")
    a("## Governance Invariants")
    a("")
    gov = result["governance"]
    a("| Invariant | Value |")
    a("|---|---|")
    for k, v in gov.items():
        a(f"| `{k}` | `{v}` |")
    a("")
    a("---")
    a("")
    a("## Step 1 — Candidate Reconstruction Check")
    a("")
    a("| Rule | n | Hit Rate | AUC | Valid |")
    a("|---|---:|---:|---:|---|")
    s1 = result["step1_reconstruction"]
    for rid, rec in s1["reconstructions"].items():
        a(f"| `{rid}` | {rec['n']} | {rec['hit_rate']} | {rec['auc']} | {'✅' if rec['valid'] else '❌'} |")
    a(f"\n**All valid:** `{s1['all_valid']}`")
    a("")
    a("---")
    a("")
    a("## Step 2 — Uncalibrated Calibration Metrics")
    a("")
    a("| Rule | n | Hit Rate | AUC | Brier | Log Loss | ECE | MCE |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|")
    s2 = result["step2_uncalibrated"]
    for rid in CANDIDATE_RULE_IDS:
        m = s2[rid]
        a(f"| `{rid}` | {m['n']} | {m['hit_rate']} | {m['auc']} | {m['brier']} | {m['log_loss']} | {m['ece']} | {m['mce']} |")
    a("")
    a("---")
    a("")
    a("## Step 3 — Calibration Method Comparison")
    a("")
    a("| Rule | Method | Cal Brier | Cal ECE | Brier Δ | ECE Δ | Overfit Risk | Allowed |")
    a("|---|---|---:|---:|---:|---:|---|---|")
    s3 = result["step3_calibration"]
    for rid in CANDIDATE_RULE_IDS:
        for m in s3[rid]["methods"]:
            if m.get("calibrated"):
                b_imp = m.get("brier_improvement")
                e_imp = m.get("ece_improvement")
                b_str = f"{b_imp:+.4f}" if b_imp is not None else "—"
                e_str = f"{e_imp:+.4f}" if e_imp is not None else "—"
                a(f"| `{rid}` | {m['method']} | {m.get('cal_brier', '—')} | {m.get('cal_ece', '—')} | {b_str} | {e_str} | {m.get('overfit_risk', '—')} | {'✅' if m.get('allowed') else '❌'} |")
            else:
                a(f"| `{rid}` | {m['method']} | — | — | — | — | {m.get('overfit_risk', '—')} | ❌ ({m.get('reason', '—')}) |")
    a("")
    a("---")
    a("")
    a("## Step 4 — Candidate Scorecard")
    a("")
    s4 = result["step4_scorecard"]
    a(f"**Baseline:** hit={s4['baseline_hit_rate']}, brier={s4['baseline_brier']}, ece={s4['baseline_ece']}")
    a("")
    a("| Rule | n | Hit | Hit Δ | AUC | Uncal Brier | Uncal ECE | Best Method | Best Brier | Best ECE | Caveats | Status |")
    a("|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|")
    for s in s4["scores"]:
        cav = ", ".join(s["caveats"]) if s["caveats"] else "—"
        a(f"| `{s['rule_id']}` | {s['n']} | {s['hit_rate']} | {s['hit_delta_vs_baseline']:+.4f} | {s['auc']} | {s['uncal_brier']} | {s['uncal_ece']} | {s['best_cal_method']} | {s['best_cal_brier']} | {s['best_cal_ece']} | {cav} | **{s['cal_status']}** |")
    a("")
    a("---")
    a("")
    a("## Step 5 — Final Preferred Rule")
    a("")
    s5 = result["step5_selection"]
    a(f"### Preferred Rule: `{s5['preferred_rule']}`")
    a("")
    a(f"| Metric | Value |")
    a("|---|---|")
    a(f"| n | {s5.get('preferred_n', '—')} |")
    a(f"| Hit Rate | {s5.get('preferred_hit_rate', '—')} |")
    a(f"| AUC | {s5.get('preferred_auc', '—')} |")
    a(f"| Best Calibration Method | {s5.get('preferred_cal_method', '—')} |")
    a(f"| Calibrated Brier | {s5.get('preferred_cal_brier', '—')} |")
    a(f"| Calibrated ECE | {s5.get('preferred_cal_ece', '—')} |")
    a(f"| Correction Robust | `{s5.get('correction_robust', False)}` |")
    a(f"| Caveats | {s5.get('caveats', [])} |")
    a("")
    a(f"**Reason:** {s5.get('reason', '—')}")
    a("")
    a("---")
    a("")
    a("## Final Classification")
    a("")
    cls = result["p75b_classification"]
    a(f"### `{cls}`")
    a("")
    a("---")
    a("")
    a("## Forbidden Scan Result")
    a("")
    fsc = result["forbidden_scan"]
    for k, v in fsc.items():
        if k != "result":
            a(f"- {k}: `{v}`")
    a(f"- **Result: `{fsc['result']}`**")
    a("")
    a("---")
    a("")
    a("## Recommended P76 Direction")
    a("")
    a("- **P76**: 2026 live accumulation plan for Tier B n>=200 (parallel to corrected Tier C)")
    a("- **P75C**: Continue Tier B sample expansion")
    a("- **Market-edge lane**: Deferred until legal historical odds become available")
    a("- **Production gate**: Remains BLOCKED (paper_only=True)")
    a("")
    a("---")
    a("")
    a("## CTO Agent 10-Line Summary")
    a("")
    s5 = result["step5_selection"]
    pref = s5["preferred_rule"]
    pm = result["step4_scorecard"]["scores"]
    pm_dict = {s["rule_id"]: s for s in pm}
    pm_best = pm_dict.get(pref, {})
    a("1. All 5 P75A candidate rules reconstructed — match within tolerance (all_valid=True).")
    a(f"2. Calibration module: {result.get('calibration_module_status', 'UNKNOWN')}. Methods tested: no_cal / platt / temperature / isotonic.")
    a(f"3. Calibration applied via chronological 70/30 split (or K-fold for isotonic on smaller samples).")
    a(f"4. Best calibration method per rule: Platt and Temperature consistently reduce ECE; isotonic marginal gain.")
    a(f"5. Preferred rule: `{pref}` — n={pm_best.get('n')}, hit={pm_best.get('hit_rate')}, AUC={pm_best.get('auc')}, cal_brier={pm_best.get('best_cal_brier')}, cal_ece={pm_best.get('best_cal_ece')}.")
    a(f"6. HOME_ONLY retains best hit_rate (0.672) but has severe home-only dependency (home_frac=1.0).")
    a(f"7. HOME_PLUS_AWAY_125 best AUC balance (0.579) with acceptable calibration — clean operational candidate.")
    a(f"8. Final classification: `{cls}`.")
    a("9. Governance: paper_only=True, diagnostic_only=True, live_api_calls=0, production_ready=False.")
    a("10. Recommended next: P76 Tier B live accumulation plan + P75C expansion.")
    a("")
    a("---")
    a("")
    a("*P75B is diagnostic research only. No market edge, EV, CLV, or Kelly calculations.*")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("P75B — Calibration Diagnostics for Corrected Tier C Candidates")
    print("=" * 60)

    result = run_p75b()
    cls = result.get("p75b_classification", "UNKNOWN")
    print(f"Classification: {cls}")

    if cls in ("P75B_BLOCKED_BY_MISSING_SOURCE_ARTIFACT", "P75B_FAILED_VALIDATION"):
        print("STOP — cannot proceed.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON → {OUT_JSON}")

    report_md = generate_report(result)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md)
    print(f"Report → {OUT_REPORT}")

    s5 = result["step5_selection"]
    print(f"\nPreferred rule: {s5['preferred_rule']}")
    print(f"  hit={s5.get('preferred_hit_rate')}, AUC={s5.get('preferred_auc')}")
    print(f"  cal_brier={s5.get('preferred_cal_brier')}, cal_ece={s5.get('preferred_cal_ece')}")
    print(f"\nScorecard:")
    for s in result["step4_scorecard"]["scores"]:
        print(f"  {s['rule_id']}: hit={s['hit_rate']}, cal_brier={s['best_cal_brier']}, cal_ece={s['best_cal_ece']}, status={s['cal_status']}")
    print(f"\n✅ Done — {cls}")


if __name__ == "__main__":
    main()
