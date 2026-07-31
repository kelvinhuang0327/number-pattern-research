"""
Phase 42: MLB Calibration Repair Module
========================================
Evaluates probability calibration methods on Phase 39 persisted prediction
rows using time-aware cross-validation (no data leakage) and Phase 41
metrics SSOT.

Supported calibration methods:
  - identity     : raw model probability (baseline, no calibration)
  - binwise      : bin-wise empirical calibration (fit on train only)
  - platt        : logistic regression scaling (sklearn required)
  - isotonic     : isotonic regression (sklearn required)
  - market_blend : alpha * model_p + (1-alpha) * market_p, alpha ∈ [0..1]

Hard Rules:
  - Do NOT modify production model.
  - Do NOT create CANDIDATE_PATCH.
  - Do NOT call external API / LLM.
  - Do NOT bypass BSS Safety Gate.
  - Do NOT fabricate model probabilities.
  - Do NOT use same-fold calibration and evaluation.
  - Do NOT random shuffle for time-aware splits.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from wbc_backend.evaluation.metrics import (
    brier_score as _brier_score,
    brier_skill_score as _bss,
    log_loss_score as _log_loss,
    expected_calibration_error as _ece,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow

logger = logging.getLogger(__name__)

# ── sklearn availability ──────────────────────────────────────────────────────
_SKLEARN_AVAILABLE: bool
try:
    import sklearn  # noqa: F401
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

# ── Constants ─────────────────────────────────────────────────────────────────
_MIN_ROWS: int = 50           # minimum total valid rows to attempt calibration
_MIN_TRAIN_N: int = 30        # minimum rows in each train fold
_MIN_TEST_N: int = 20         # minimum rows in each test fold
_BLEND_ALPHAS: list[float] = [round(a * 0.1, 1) for a in range(11)]  # 0.0 … 1.0
_ALL_METHODS: list[str] = ["identity", "binwise", "platt", "isotonic", "market_blend"]


# ══════════════════════════════════════════════════════════════════════════════
# § Classification
# ══════════════════════════════════════════════════════════════════════════════

class CalibrationClassification:
    """
    Classification codes for calibration repair outcome.
    These are string constants (not enum) for JSON-serialization simplicity.
    """
    CALIBRATION_REPAIR_HELPFUL = "CALIBRATION_REPAIR_HELPFUL"
    CALIBRATION_REPAIR_HELPFUL_BUT_NOT_SUFFICIENT = (
        "CALIBRATION_REPAIR_HELPFUL_BUT_NOT_SUFFICIENT"
    )
    MARKET_ONLY_BEST = "MARKET_ONLY_BEST"
    CALIBRATION_REPAIR_NOT_HELPFUL = "CALIBRATION_REPAIR_NOT_HELPFUL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    RAW_MODEL_PROB_MISSING = "RAW_MODEL_PROB_MISSING"
    SKLEARN_UNAVAILABLE = "SKLEARN_UNAVAILABLE"


# ══════════════════════════════════════════════════════════════════════════════
# § Data Structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FoldDef:
    """Metadata for a single time-aware split."""
    fold_id: int
    train_start: str           # game_date of first train row
    train_end: str             # game_date of last train row
    test_start: str            # game_date of first test row
    test_end: str              # game_date of last test row
    train_n: int
    test_n: int


@dataclass
class FoldResult:
    """
    Per-fold, per-method calibration metrics.
    All metric values computed via wbc_backend.evaluation.metrics (Phase 41 SSOT).
    """
    fold_id: int
    method: str                          # e.g. "identity", "platt", "market_blend_a0.3"
    alpha: Optional[float]               # non-None only for market_blend variants
    sample_size: int
    # Brier
    model_brier: float                   # raw model Brier (no calibration)
    calibrated_brier: float              # after calibration
    market_brier: float                  # market baseline Brier
    # BSS
    raw_bss: Optional[float]             # None if market_brier == 0
    calibrated_bss: Optional[float]
    # Log-loss
    raw_log_loss: float
    calibrated_log_loss: float
    market_log_loss: float
    # ECE
    raw_ece: float
    calibrated_ece: float


@dataclass
class CalibrationReport:
    """
    Aggregated result of the calibration repair evaluation.
    JSON-serializable via to_dict().
    """
    classification: str              # CalibrationClassification constant
    input_path: str
    row_count: int
    n_splits: int
    fold_defs: list[FoldDef] = field(default_factory=list)
    methods_evaluated: list[str] = field(default_factory=list)
    fold_results: list[FoldResult] = field(default_factory=list)
    # Best method (lowest pooled calibrated Brier)
    best_method: str = ""
    best_alpha: Optional[float] = None   # non-None if best_method == "market_blend"
    # Overall (pooled across all test folds)
    raw_brier_overall: float = 0.0
    calibrated_brier_overall: float = 0.0
    market_brier_overall: float = 0.0
    raw_bss_overall: Optional[float] = None
    calibrated_bss_overall: Optional[float] = None
    raw_ece_overall: float = 0.0
    calibrated_ece_overall: float = 0.0
    # Per-method overall summary (method_key → metrics dict)
    method_summaries: dict = field(default_factory=dict)
    # Safety
    patch_gate_eligible: bool = False    # True if calibrated_bss_overall >= 0
    bss_gate: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    timestamp_utc: str = ""

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict representation."""
        return asdict(self)


# ══════════════════════════════════════════════════════════════════════════════
# § Time-Aware Splits (Task 3)
# ══════════════════════════════════════════════════════════════════════════════

def make_time_aware_splits(
    rows: list[PredictionRow],
    n_splits: int = 5,
    min_train_n: int = _MIN_TRAIN_N,
    min_test_n: int = _MIN_TEST_N,
) -> list[tuple[list[PredictionRow], list[PredictionRow]]]:
    """
    Create time-aware expanding-window train/test splits.

    Rules:
    - Rows sorted by (game_date, prediction_time_utc) — ascending.
    - Train window expands with each fold (no future leakage).
    - Test window always strictly after all train rows.
    - Folds with train_n < min_train_n or test_n < min_test_n are skipped.
    - No random shuffle is applied at any point.

    Returns:
        list of (train_rows, test_rows) — may be shorter than n_splits if
        some folds have insufficient data.
    """
    if not rows:
        return []

    sorted_rows = sorted(
        rows,
        key=lambda r: (r.game_date or "", r.prediction_time_utc or ""),
    )

    n = len(sorted_rows)
    block_size = n // (n_splits + 1)
    if block_size < 1:
        return []

    splits: list[tuple[list[PredictionRow], list[PredictionRow]]] = []

    for i in range(n_splits):
        # Expanding train: always [0 .. train_end_idx)
        train_end_idx = (i + 1) * block_size
        test_start_idx = train_end_idx
        test_end_idx = min(test_start_idx + block_size, n)

        train_rows = sorted_rows[:train_end_idx]
        test_rows = sorted_rows[test_start_idx:test_end_idx]

        if len(train_rows) < min_train_n or len(test_rows) < min_test_n:
            logger.debug(
                "Fold %d skipped: train_n=%d, test_n=%d",
                i + 1, len(train_rows), len(test_rows),
            )
            continue

        splits.append((train_rows, test_rows))

    return splits


# ══════════════════════════════════════════════════════════════════════════════
# § Calibration Appliers (Task 4) — fit on train only, apply to test
# ══════════════════════════════════════════════════════════════════════════════

def _apply_identity(
    train_probs: list[float],
    train_labels: list[int],
    test_probs: list[float],
) -> list[float]:
    """Identity: return raw model probabilities unchanged (baseline)."""
    return list(test_probs)


def _apply_binwise(
    train_probs: list[float],
    train_labels: list[int],
    test_probs: list[float],
    n_bins: int = 10,
) -> list[float]:
    """
    Bin-wise calibration.

    Fit (on train only): map each probability bin → empirical outcome rate.
    Fallback: if a bin has zero train samples, use global train outcome rate.
    Apply (on test only): replace each prob with its bin's empirical rate.
    """
    global_rate = float(sum(train_labels) / len(train_labels)) if train_labels else 0.5

    bin_rates: dict[int, float] = {}
    for bin_idx in range(n_bins):
        lo = bin_idx / n_bins
        hi = (bin_idx + 1) / n_bins
        in_bin = [
            y for p, y in zip(train_probs, train_labels)
            if lo <= p < hi or (bin_idx == n_bins - 1 and p == 1.0)
        ]
        bin_rates[bin_idx] = float(sum(in_bin) / len(in_bin)) if in_bin else global_rate

    calibrated: list[float] = []
    for p in test_probs:
        bin_idx = min(int(p * n_bins), n_bins - 1)
        calibrated.append(bin_rates[bin_idx])
    return calibrated


def _apply_platt(
    train_probs: list[float],
    train_labels: list[int],
    test_probs: list[float],
) -> list[float]:
    """
    Platt scaling via logistic regression.

    Fit on train fold; predict_proba on test fold.
    Raises ImportError if sklearn is not available.
    """
    from sklearn.linear_model import LogisticRegression  # type: ignore[import]

    X_train = [[p] for p in train_probs]
    X_test = [[p] for p in test_probs]
    lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=500)
    lr.fit(X_train, train_labels)
    return [float(prob[1]) for prob in lr.predict_proba(X_test)]


def _apply_isotonic(
    train_probs: list[float],
    train_labels: list[int],
    test_probs: list[float],
) -> list[float]:
    """
    Isotonic regression calibration.

    Fit on train fold; predict on test fold (clipped to [0, 1]).
    Raises ImportError if sklearn is not available.
    """
    from sklearn.isotonic import IsotonicRegression  # type: ignore[import]

    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(train_probs, train_labels)
    return [max(0.0, min(1.0, float(p))) for p in ir.predict(test_probs)]


def _apply_market_blend(
    test_probs: list[float],
    test_market_probs: list[float],
    alpha: float,
) -> list[float]:
    """
    Market blend: calibrated_p = alpha * model_p + (1 - alpha) * market_p.

    alpha=0.0 → pure market probability
    alpha=1.0 → pure model probability
    """
    return [
        alpha * m + (1.0 - alpha) * mk
        for m, mk in zip(test_probs, test_market_probs)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# § Metric Computation Helper
# ══════════════════════════════════════════════════════════════════════════════

def _compute_fold_result(
    *,
    fold_id: int,
    method: str,
    alpha: Optional[float],
    model_probs: list[float],
    calibrated_probs: list[float],
    market_probs: list[float],
    labels: list[int],
) -> FoldResult:
    """
    Compute all metrics for one fold using metrics.py SSOT.
    Never called with train data mixed into the test arrays.
    """
    mb = _brier_score(model_probs, labels)
    cb = _brier_score(calibrated_probs, labels)
    mkb = _brier_score(market_probs, labels)
    raw_bss = _bss(mb, mkb)
    cal_bss = _bss(cb, mkb)
    raw_ll = _log_loss(model_probs, labels)
    cal_ll = _log_loss(calibrated_probs, labels)
    mkt_ll = _log_loss(market_probs, labels)
    raw_ece_val = _ece(model_probs, labels)["ece"]
    cal_ece_val = _ece(calibrated_probs, labels)["ece"]

    return FoldResult(
        fold_id=fold_id,
        method=method,
        alpha=alpha,
        sample_size=len(labels),
        model_brier=round(mb, 6),
        calibrated_brier=round(cb, 6),
        market_brier=round(mkb, 6),
        raw_bss=round(raw_bss, 6) if raw_bss is not None else None,
        calibrated_bss=round(cal_bss, 6) if cal_bss is not None else None,
        raw_log_loss=round(raw_ll, 6),
        calibrated_log_loss=round(cal_ll, 6),
        market_log_loss=round(mkt_ll, 6),
        raw_ece=round(raw_ece_val, 6),
        calibrated_ece=round(cal_ece_val, 6),
    )


def _accumulate(
    pool: dict,
    key: str,
    model: list[float],
    calibrated: list[float],
    market: list[float],
    labels: list[int],
) -> None:
    """Accumulate pooled arrays for overall metric computation."""
    if key not in pool:
        pool[key] = {"model": [], "calibrated": [], "market": [], "labels": []}
    pool[key]["model"].extend(model)
    pool[key]["calibrated"].extend(calibrated)
    pool[key]["market"].extend(market)
    pool[key]["labels"].extend(labels)


# ══════════════════════════════════════════════════════════════════════════════
# § Main Entry Point (Tasks 2–6)
# ══════════════════════════════════════════════════════════════════════════════

def run_calibration_repair(
    rows: list[PredictionRow],
    methods: Optional[list[str]] = None,
    n_splits: int = 5,
    input_path: str = "",
) -> CalibrationReport:
    """
    Evaluate calibration repair on persisted Phase 39 prediction rows.

    Args:
        rows:       list of PredictionRow from load_prediction_rows().
        methods:    subset of _ALL_METHODS to evaluate (None = all).
        n_splits:   number of time-aware walk-forward folds.
        input_path: human-readable path for the report.

    Returns:
        CalibrationReport with classification, metrics, BSS Safety Gate result.

    Hard guarantees:
        - Calibration fit only on train fold.
        - Evaluation only on test fold (strict OOS).
        - All metrics computed via wbc_backend.evaluation.metrics.
        - No production model is modified.
        - No CANDIDATE_PATCH is created.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if methods is None:
        methods = list(_ALL_METHODS)

    report = CalibrationReport(
        classification=CalibrationClassification.CALIBRATION_REPAIR_NOT_HELPFUL,
        input_path=input_path,
        row_count=len(rows),
        n_splits=n_splits,
        methods_evaluated=list(methods),
        timestamp_utc=now_utc,
    )

    # ── Guard: RAW_MODEL_PROB_MISSING ─────────────────────────────────────────
    valid_rows = [r for r in rows if r.model_home_prob >= 0.0]
    if not valid_rows:
        report.classification = CalibrationClassification.RAW_MODEL_PROB_MISSING
        report.notes.append(
            "RAW_MODEL_PROB_MISSING: no rows have a valid model_home_prob (>= 0)."
        )
        return report

    # ── Guard: INSUFFICIENT_DATA ──────────────────────────────────────────────
    if len(valid_rows) < _MIN_ROWS:
        report.classification = CalibrationClassification.INSUFFICIENT_DATA
        report.notes.append(
            f"INSUFFICIENT_DATA: {len(valid_rows)} valid rows < minimum {_MIN_ROWS}."
        )
        return report

    report.row_count = len(valid_rows)

    # ── Guard: SKLEARN_UNAVAILABLE ────────────────────────────────────────────
    sklearn_needed = any(m in methods for m in ("platt", "isotonic"))
    if sklearn_needed and not _SKLEARN_AVAILABLE:
        report.classification = CalibrationClassification.SKLEARN_UNAVAILABLE
        report.notes.append(
            "SKLEARN_UNAVAILABLE: sklearn is required for platt/isotonic "
            "but could not be imported."
        )
        return report

    # ── Time-aware splits ─────────────────────────────────────────────────────
    splits = make_time_aware_splits(valid_rows, n_splits=n_splits)
    if not splits:
        report.classification = CalibrationClassification.INSUFFICIENT_DATA
        report.notes.append(
            f"INSUFFICIENT_DATA: could not create any valid folds "
            f"from {len(valid_rows)} rows with n_splits={n_splits}."
        )
        return report

    for i, (train_rows, test_rows) in enumerate(splits):
        report.fold_defs.append(FoldDef(
            fold_id=i + 1,
            train_start=train_rows[0].game_date,
            train_end=train_rows[-1].game_date,
            test_start=test_rows[0].game_date,
            test_end=test_rows[-1].game_date,
            train_n=len(train_rows),
            test_n=len(test_rows),
        ))

    # ── Per-fold per-method evaluation ───────────────────────────────────────
    pool: dict = {}           # method_key → pooled arrays
    all_fold_results: list[FoldResult] = []

    for fold_id, (train_rows, test_rows) in enumerate(splits, start=1):
        train_probs = [r.model_home_prob for r in train_rows]
        train_labels = [r.home_win for r in train_rows]
        test_probs = [r.model_home_prob for r in test_rows]
        test_mkt = [r.market_home_prob_no_vig for r in test_rows]
        test_labels = [r.home_win for r in test_rows]

        for method in methods:
            if method == "identity":
                cal = _apply_identity(train_probs, train_labels, test_probs)
                _record(
                    all_fold_results, pool, fold_id, "identity", None,
                    test_probs, cal, test_mkt, test_labels,
                )

            elif method == "binwise":
                try:
                    cal = _apply_binwise(train_probs, train_labels, test_probs)
                    _record(
                        all_fold_results, pool, fold_id, "binwise", None,
                        test_probs, cal, test_mkt, test_labels,
                    )
                except Exception as exc:
                    logger.warning("binwise fold %d failed: %s", fold_id, exc)
                    report.notes.append(f"binwise fold {fold_id} error: {exc}")

            elif method == "platt":
                try:
                    cal = _apply_platt(train_probs, train_labels, test_probs)
                    _record(
                        all_fold_results, pool, fold_id, "platt", None,
                        test_probs, cal, test_mkt, test_labels,
                    )
                except ImportError:
                    logger.warning("platt: sklearn ImportError on fold %d", fold_id)
                    report.notes.append(f"platt fold {fold_id}: sklearn ImportError")
                except Exception as exc:
                    logger.warning("platt fold %d failed: %s", fold_id, exc)
                    report.notes.append(f"platt fold {fold_id} error: {exc}")

            elif method == "isotonic":
                try:
                    cal = _apply_isotonic(train_probs, train_labels, test_probs)
                    _record(
                        all_fold_results, pool, fold_id, "isotonic", None,
                        test_probs, cal, test_mkt, test_labels,
                    )
                except ImportError:
                    logger.warning("isotonic: sklearn ImportError on fold %d", fold_id)
                    report.notes.append(f"isotonic fold {fold_id}: sklearn ImportError")
                except Exception as exc:
                    logger.warning("isotonic fold %d failed: %s", fold_id, exc)
                    report.notes.append(f"isotonic fold {fold_id} error: {exc}")

            elif method == "market_blend":
                for alpha in _BLEND_ALPHAS:
                    cal = _apply_market_blend(test_probs, test_mkt, alpha)
                    mk = f"market_blend_a{alpha:.1f}"
                    _record(
                        all_fold_results, pool, fold_id, mk, alpha,
                        test_probs, cal, test_mkt, test_labels,
                    )

    report.fold_results = all_fold_results

    if not pool:
        report.classification = CalibrationClassification.INSUFFICIENT_DATA
        report.notes.append("No fold results were produced (all folds failed).")
        return report

    # ── Overall (pooled) metrics per method ───────────────────────────────────
    method_overall: dict[str, dict] = {}
    for mk, data in pool.items():
        if not data["labels"]:
            continue
        mb = _brier_score(data["model"], data["labels"])
        cb = _brier_score(data["calibrated"], data["labels"])
        mkb = _brier_score(data["market"], data["labels"])
        raw_bss_v = _bss(mb, mkb)
        cal_bss_v = _bss(cb, mkb)
        r_ece = _ece(data["model"], data["labels"])["ece"]
        c_ece = _ece(data["calibrated"], data["labels"])["ece"]
        method_overall[mk] = {
            "model_brier": round(mb, 6),
            "calibrated_brier": round(cb, 6),
            "market_brier": round(mkb, 6),
            "raw_bss": round(raw_bss_v, 6) if raw_bss_v is not None else None,
            "calibrated_bss": round(cal_bss_v, 6) if cal_bss_v is not None else None,
            "raw_ece": round(r_ece, 6),
            "calibrated_ece": round(c_ece, 6),
            "sample_size": len(data["labels"]),
        }

    report.method_summaries = method_overall

    # ── Find best method ──────────────────────────────────────────────────────
    best_key = min(method_overall, key=lambda k: method_overall[k]["calibrated_brier"])
    best_overall = method_overall[best_key]

    # Raw baseline from identity (or fallback)
    id_overall = method_overall.get("identity", best_overall)
    raw_ece_overall = id_overall["raw_ece"]
    raw_bss_overall = id_overall["raw_bss"]
    raw_brier_overall = id_overall["model_brier"]

    best_cal_bss: Optional[float] = best_overall["calibrated_bss"]
    best_cal_ece: float = best_overall["calibrated_ece"]
    ece_improved = best_cal_ece < raw_ece_overall

    # Decode best_method / best_alpha
    best_alpha: Optional[float] = None
    best_simple_method = best_key
    if best_key.startswith("market_blend_a"):
        try:
            best_alpha = float(best_key.split("market_blend_a", 1)[1])
        except (ValueError, IndexError):
            pass
        best_simple_method = "market_blend"

    # ── Classification (Task 5) ───────────────────────────────────────────────
    if best_simple_method == "market_blend" and (best_alpha is None or best_alpha < 0.2):
        classification = CalibrationClassification.MARKET_ONLY_BEST
    elif best_cal_bss is not None and best_cal_bss >= 0.0 and ece_improved:
        classification = CalibrationClassification.CALIBRATION_REPAIR_HELPFUL
    elif ece_improved:
        classification = CalibrationClassification.CALIBRATION_REPAIR_HELPFUL_BUT_NOT_SUFFICIENT
    else:
        classification = CalibrationClassification.CALIBRATION_REPAIR_NOT_HELPFUL

    # ── BSS Safety Gate (Task 6) ──────────────────────────────────────────────
    from orchestrator.bss_safety_gate import evaluate_bss_gate

    gate_bss = best_cal_bss if best_cal_bss is not None else -1.0
    gate_result = evaluate_bss_gate(
        bss=gate_bss,
        model_brier=best_overall["calibrated_brier"],
        baseline_brier=best_overall["market_brier"],
        task_kind="metric_repair",
    )

    patch_gate_eligible = best_cal_bss is not None and best_cal_bss >= 0.0

    # ── Fill report ───────────────────────────────────────────────────────────
    report.classification = classification
    report.best_method = best_simple_method
    report.best_alpha = best_alpha
    report.raw_brier_overall = raw_brier_overall
    report.calibrated_brier_overall = best_overall["calibrated_brier"]
    report.market_brier_overall = best_overall["market_brier"]
    report.raw_bss_overall = raw_bss_overall
    report.calibrated_bss_overall = best_cal_bss
    report.raw_ece_overall = raw_ece_overall
    report.calibrated_ece_overall = best_cal_ece
    report.patch_gate_eligible = patch_gate_eligible
    report.bss_gate = {
        "bss": gate_result.bss,
        "baseline": gate_result.baseline,
        "model_brier": gate_result.model_brier,
        "bss_negative": gate_result.bss_negative,
        "task_kind": gate_result.task_kind,
        "allowed": gate_result.allowed,
        "block_reason": gate_result.block_reason,
        "recommendation": gate_result.recommendation,
    }

    if patch_gate_eligible:
        report.notes.append(
            "PATCH_GATE_RECHECK_ELIGIBLE: calibrated BSS >= 0. "
            "However, this script does NOT create a CANDIDATE_PATCH."
        )
    else:
        bss_str = f"{best_cal_bss:+.1%}" if best_cal_bss is not None else "N/A"
        report.notes.append(
            f"calibrated BSS={bss_str} < 0 — patch gate locked. "
            "Allowed next steps: METRIC_REPAIR, FEATURE_REPAIR_INVESTIGATION, "
            "DATA_REPAIR, COLLECT_MORE_DATA."
        )

    logger.info(
        "[Phase42] classification=%s | best=%s (alpha=%s) | "
        "raw_bss=%s | cal_bss=%s | raw_ece=%.4f | cal_ece=%.4f",
        classification,
        best_simple_method,
        best_alpha,
        f"{raw_bss_overall:+.4f}" if raw_bss_overall is not None else "N/A",
        f"{best_cal_bss:+.4f}" if best_cal_bss is not None else "N/A",
        raw_ece_overall,
        best_cal_ece,
    )

    return report


# ══════════════════════════════════════════════════════════════════════════════
# § Internal Helper
# ══════════════════════════════════════════════════════════════════════════════

def _record(
    results: list[FoldResult],
    pool: dict,
    fold_id: int,
    method_key: str,
    alpha: Optional[float],
    model_probs: list[float],
    calibrated_probs: list[float],
    market_probs: list[float],
    labels: list[int],
) -> None:
    """Compute and store FoldResult, plus accumulate pooled data."""
    fr = _compute_fold_result(
        fold_id=fold_id,
        method=method_key,
        alpha=alpha,
        model_probs=model_probs,
        calibrated_probs=calibrated_probs,
        market_probs=market_probs,
        labels=labels,
    )
    results.append(fr)
    _accumulate(pool, method_key, model_probs, calibrated_probs, market_probs, labels)
