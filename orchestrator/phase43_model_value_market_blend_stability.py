"""
Phase 43: Model Value & Market Blend Stability Audit
======================================================
Validates whether market_blend α=0.4's +0.28% BSS (from Phase 42A) is a
stable signal or fold/sample/bootstrap noise.

Hard Rules:
  - Do NOT modify production model.
  - Do NOT create CANDIDATE_PATCH.
  - Do NOT call external API / LLM.
  - Do NOT bypass BSS Safety Gate.
  - Do NOT use best-per-fold alpha as production proof.
  - Bootstrap CI crossing zero → NOT_SIGNIFICANT.
  - All metrics delegate to wbc_backend.evaluation.metrics (SSOT).
"""
from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    log_loss_score,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

FIXED_ALPHA = 0.4          # Production-candidate blend alpha from Phase 42A
_BLEND_ALPHAS = [round(a * 0.1, 1) for a in range(11)]   # 0.0 … 1.0
_N_BOOTSTRAP = 1000
_BOOTSTRAP_SEED = 42
_MIN_FOLD_N = 30
_CI_LEVEL = 0.95


# ─────────────────────────────────────────────────────────────────────────────
# §1  Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FoldStabilityRow:
    """Per-fold stability metrics comparing raw model / market / blend."""
    fold_id: str
    n: int
    date_start: str
    date_end: str
    # Brier scores
    raw_brier: float
    market_brier: float
    blend_brier: float        # α = FIXED_ALPHA
    # BSS vs market
    raw_bss: float
    blend_bss: float
    # ECE
    raw_ece: float
    blend_ece: float
    # Per-fold best alpha (DIAGNOSTIC ONLY — not production proof)
    best_alpha_per_fold: float
    best_alpha_brier: float
    diagnostic_only: bool = True   # always True — guard against misuse


@dataclass
class BootstrapResult:
    """Bootstrap confidence interval for delta Brier vs market."""
    label: str                # e.g. "raw_vs_market", "blend_vs_market"
    n_samples: int
    n_bootstrap: int
    mean_delta_brier: float   # negative = improvement (lower brier)
    ci_lower: float           # 5th percentile of bootstrap distribution
    ci_upper: float           # 95th percentile of bootstrap distribution
    prob_improvement: float   # fraction of bootstrap samples with delta < 0
    # Significance classification
    significant: bool         # True iff CI does not cross 0
    significance_label: str   # "SIGNIFICANT" | "NOT_SIGNIFICANT"


@dataclass
class SegmentResult:
    """Model value assessment for a single segment slice."""
    segment_type: str         # "month" | "odds_bucket" | "confidence_bucket" | "disagreement_bucket"
    segment_label: str        # e.g. "2025-06", "high_odds", "high_confidence", "high_disagreement"
    n: int
    raw_brier: float
    market_brier: float
    blend_brier: float
    raw_bss: float
    blend_bss: float
    raw_ece: float
    blend_ece: float
    value_classification: str  # "NO_VALUE" | "WEAK_VALUE" | "CONDITIONAL_VALUE" | "STABLE_VALUE"


@dataclass
class GateRecommendation:
    """Final gate recommendation with reasoning."""
    recommendation: str       # one of the 5 gate actions
    reasoning: list[str] = field(default_factory=list)
    # Hard guards
    candidate_patch_created: bool = False   # always False in this phase
    bootstrap_significant: bool = False
    fold_stable: bool = False
    has_stable_value_segment: bool = False


@dataclass
class Phase43AuditReport:
    """Complete Phase 43 audit report."""
    # Config
    input_path: str = ""
    row_count: int = 0
    n_splits: int = 5
    fixed_alpha: float = FIXED_ALPHA
    n_bootstrap: int = _N_BOOTSTRAP
    # Fold stability
    fold_results: list[FoldStabilityRow] = field(default_factory=list)
    folds_with_positive_blend_bss: int = 0
    folds_with_positive_raw_bss: int = 0
    fold_stability_label: str = ""   # "STABLE" | "UNSTABLE" | "MIXED"
    # Bootstrap
    bootstrap_raw_vs_market: Optional[BootstrapResult] = None
    bootstrap_blend_vs_market: Optional[BootstrapResult] = None
    # Segment analysis
    segment_results: list[SegmentResult] = field(default_factory=list)
    segment_value_summary: dict[str, str] = field(default_factory=dict)
    # Overall metrics
    overall_raw_brier: float = 0.0
    overall_market_brier: float = 0.0
    overall_blend_brier: float = 0.0
    overall_raw_bss: float = 0.0
    overall_blend_bss: float = 0.0
    overall_raw_ece: float = 0.0
    overall_blend_ece: float = 0.0
    # Gate
    gate: GateRecommendation = field(default_factory=lambda: GateRecommendation(recommendation="PENDING"))
    # Meta
    notes: list[str] = field(default_factory=list)
    timestamp_utc: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# §2  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _blend(model_p: float, market_p: float, alpha: float) -> float:
    """calibrated = alpha * model_p + (1 - alpha) * market_p"""
    return alpha * model_p + (1.0 - alpha) * market_p


def _blend_probs(
    model_probs: list[float],
    market_probs: list[float],
    alpha: float,
) -> list[float]:
    return [_blend(m, k, alpha) for m, k in zip(model_probs, market_probs)]


def _value_class(raw_bss: float, blend_bss: float, n: int) -> str:
    """Classify segment model value."""
    if n < _MIN_FOLD_N:
        return "NO_VALUE"
    if blend_bss >= 0.02:
        return "STABLE_VALUE"
    if blend_bss >= 0.005:
        return "CONDITIONAL_VALUE"
    if blend_bss >= 0.0:
        return "WEAK_VALUE"
    return "NO_VALUE"


# ─────────────────────────────────────────────────────────────────────────────
# §3  Time-aware splits
# ─────────────────────────────────────────────────────────────────────────────

def _sort_rows(rows: list[PredictionRow]) -> list[PredictionRow]:
    """Sort rows by game_date then prediction_time_utc (no shuffle)."""
    return sorted(rows, key=lambda r: (r.game_date, r.prediction_time_utc or ""))


def make_time_aware_folds(
    rows: list[PredictionRow],
    n_splits: int = 5,
) -> list[tuple[list[PredictionRow], list[PredictionRow]]]:
    """
    Build time-aware expanding-window folds.

    Returns list of (train, test) tuples.
    Test fold is always strictly after train fold (no lookahead).
    """
    rows = _sort_rows(rows)
    n = len(rows)
    window = n // (n_splits + 1)
    folds: list[tuple[list[PredictionRow], list[PredictionRow]]] = []

    for w in range(n_splits):
        train_end = (w + 1) * window
        test_start = train_end
        test_end = min(test_start + window, n)
        train = rows[:train_end]
        test = rows[test_start:test_end]
        if len(train) >= _MIN_FOLD_N and len(test) >= _MIN_FOLD_N:
            folds.append((train, test))

    return folds


# ─────────────────────────────────────────────────────────────────────────────
# §4  Fold-level stability audit
# ─────────────────────────────────────────────────────────────────────────────

def compute_fold_stability(
    rows: list[PredictionRow],
    n_splits: int = 5,
    alpha: float = FIXED_ALPHA,
) -> list[FoldStabilityRow]:
    """
    Compute per-fold metrics for raw model, market baseline, and blend.

    best_alpha_per_fold is DIAGNOSTIC ONLY — not production proof.
    """
    folds = make_time_aware_folds(rows, n_splits=n_splits)
    results: list[FoldStabilityRow] = []

    for i, (_, test) in enumerate(folds):
        fold_id = f"fold_{i + 1}"
        model_p = [r.model_home_prob for r in test]
        market_p = [r.market_home_prob_no_vig for r in test]
        labels = [r.home_win for r in test]
        blend_p = _blend_probs(model_p, market_p, alpha)

        raw_b = brier_score(model_p, labels)
        mkt_b = brier_score(market_p, labels)
        blend_b = brier_score(blend_p, labels)

        raw_bss_v = brier_skill_score(raw_b, mkt_b) or 0.0
        blend_bss_v = brier_skill_score(blend_b, mkt_b) or 0.0
        raw_ece_v = expected_calibration_error(model_p, labels)["ece"]
        blend_ece_v = expected_calibration_error(blend_p, labels)["ece"]

        # Best alpha per fold (diagnostic only)
        best_a = alpha
        best_b = blend_b
        for a in _BLEND_ALPHAS:
            bp = _blend_probs(model_p, market_p, a)
            bb = brier_score(bp, labels)
            if bb < best_b:
                best_b = bb
                best_a = a

        results.append(FoldStabilityRow(
            fold_id=fold_id,
            n=len(test),
            date_start=test[0].game_date,
            date_end=test[-1].game_date,
            raw_brier=round(raw_b, 6),
            market_brier=round(mkt_b, 6),
            blend_brier=round(blend_b, 6),
            raw_bss=round(raw_bss_v, 6),
            blend_bss=round(blend_bss_v, 6),
            raw_ece=round(raw_ece_v, 6),
            blend_ece=round(blend_ece_v, 6),
            best_alpha_per_fold=best_a,
            best_alpha_brier=round(best_b, 6),
            diagnostic_only=True,
        ))

    return results


def _fold_stability_label(fold_results: list[FoldStabilityRow]) -> str:
    """
    Classify overall fold stability of blend_bss across folds.

    STABLE   : >= 80% of folds have blend_bss >= 0
    MIXED    : 40–80% of folds have blend_bss >= 0
    UNSTABLE : < 40% of folds have blend_bss >= 0
    """
    if not fold_results:
        return "UNSTABLE"
    pos = sum(1 for f in fold_results if f.blend_bss >= 0)
    ratio = pos / len(fold_results)
    if ratio >= 0.8:
        return "STABLE"
    if ratio >= 0.4:
        return "MIXED"
    return "UNSTABLE"


# ─────────────────────────────────────────────────────────────────────────────
# §5  Bootstrap CI
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_delta_brier(
    model_probs: list[float],
    market_probs: list[float],
    labels: list[int],
    label: str,
    n_bootstrap: int = _N_BOOTSTRAP,
    seed: int = _BOOTSTRAP_SEED,
) -> BootstrapResult:
    """
    Bootstrap 95% CI for delta Brier = model_brier - market_brier.

    Negative delta means the model is BETTER than market.
    """
    rng = random.Random(seed)
    n = len(labels)
    deltas: list[float] = []

    for _ in range(n_bootstrap):
        indices = [rng.randint(0, n - 1) for _ in range(n)]
        mp = [model_probs[i] for i in indices]
        kp = [market_probs[i] for i in indices]
        lb = [labels[i] for i in indices]
        delta = brier_score(mp, lb) - brier_score(kp, lb)
        deltas.append(delta)

    deltas.sort()
    ci_lower = deltas[int((1 - _CI_LEVEL) / 2 * n_bootstrap)]
    ci_upper = deltas[int((1 - (1 - _CI_LEVEL) / 2) * n_bootstrap)]
    mean_delta = sum(deltas) / len(deltas)
    prob_improve = sum(1 for d in deltas if d < 0) / n_bootstrap

    # CI crossing 0 → NOT_SIGNIFICANT
    significant = (ci_upper < 0) or (ci_lower > 0)
    sig_label = "SIGNIFICANT" if significant else "NOT_SIGNIFICANT"

    return BootstrapResult(
        label=label,
        n_samples=n,
        n_bootstrap=n_bootstrap,
        mean_delta_brier=round(mean_delta, 6),
        ci_lower=round(ci_lower, 6),
        ci_upper=round(ci_upper, 6),
        prob_improvement=round(prob_improve, 4),
        significant=significant,
        significance_label=sig_label,
    )


def run_bootstrap(
    rows: list[PredictionRow],
    alpha: float = FIXED_ALPHA,
    n_bootstrap: int = _N_BOOTSTRAP,
) -> tuple[BootstrapResult, BootstrapResult]:
    """
    Run bootstrap for (raw_vs_market, blend_vs_market).
    Returns both BootstrapResult objects.
    """
    rows = _sort_rows(rows)
    model_p = [r.model_home_prob for r in rows]
    market_p = [r.market_home_prob_no_vig for r in rows]
    labels = [r.home_win for r in rows]
    blend_p = _blend_probs(model_p, market_p, alpha)

    raw_bs = _bootstrap_delta_brier(
        model_p, market_p, labels,
        label="raw_vs_market",
        n_bootstrap=n_bootstrap,
    )
    blend_bs = _bootstrap_delta_brier(
        blend_p, market_p, labels,
        label="blend_vs_market",
        n_bootstrap=n_bootstrap,
    )
    return raw_bs, blend_bs


# ─────────────────────────────────────────────────────────────────────────────
# §6  Segment-level model value analysis
# ─────────────────────────────────────────────────────────────────────────────

def _segment_metrics(
    rows: list[PredictionRow],
    seg_type: str,
    seg_label: str,
    alpha: float,
) -> SegmentResult:
    """Compute metrics for a single segment slice."""
    model_p = [r.model_home_prob for r in rows]
    market_p = [r.market_home_prob_no_vig for r in rows]
    labels = [r.home_win for r in rows]
    blend_p = _blend_probs(model_p, market_p, alpha)

    raw_b = brier_score(model_p, labels)
    mkt_b = brier_score(market_p, labels)
    blend_b = brier_score(blend_p, labels)

    raw_bss_v = brier_skill_score(raw_b, mkt_b) or 0.0
    blend_bss_v = brier_skill_score(blend_b, mkt_b) or 0.0
    raw_ece_v = expected_calibration_error(model_p, labels)["ece"]
    blend_ece_v = expected_calibration_error(blend_p, labels)["ece"]

    val_class = _value_class(raw_bss_v, blend_bss_v, len(rows))

    return SegmentResult(
        segment_type=seg_type,
        segment_label=seg_label,
        n=len(rows),
        raw_brier=round(raw_b, 6),
        market_brier=round(mkt_b, 6),
        blend_brier=round(blend_b, 6),
        raw_bss=round(raw_bss_v, 6),
        blend_bss=round(blend_bss_v, 6),
        raw_ece=round(raw_ece_v, 6),
        blend_ece=round(blend_ece_v, 6),
        value_classification=val_class,
    )


def analyse_segments(
    rows: list[PredictionRow],
    alpha: float = FIXED_ALPHA,
) -> list[SegmentResult]:
    """
    Segment-level model value analysis across 4 segment types:
      - month
      - odds_bucket    (market_home_prob_no_vig ranges)
      - confidence_bucket  (|model_prob - 0.5| ranges)
      - disagreement_bucket (|model_prob - market_prob| ranges)
    """
    results: list[SegmentResult] = []

    # ── Month ────────────────────────────────────────────────────────────────
    from collections import defaultdict
    month_groups: dict[str, list[PredictionRow]] = defaultdict(list)
    for r in rows:
        month_groups[r.game_date[:7]].append(r)
    for m, grp in sorted(month_groups.items()):
        if len(grp) >= _MIN_FOLD_N:
            results.append(_segment_metrics(grp, "month", m, alpha))

    # ── Odds bucket ──────────────────────────────────────────────────────────
    odds_buckets = {
        "heavy_away_fav": lambda r: r.market_home_prob_no_vig < 0.40,
        "slight_away_fav": lambda r: 0.40 <= r.market_home_prob_no_vig < 0.48,
        "pick_em":         lambda r: 0.48 <= r.market_home_prob_no_vig <= 0.52,
        "slight_home_fav": lambda r: 0.52 < r.market_home_prob_no_vig <= 0.60,
        "heavy_home_fav":  lambda r: r.market_home_prob_no_vig > 0.60,
    }
    for label, pred in odds_buckets.items():
        grp = [r for r in rows if pred(r)]
        if len(grp) >= _MIN_FOLD_N:
            results.append(_segment_metrics(grp, "odds_bucket", label, alpha))

    # ── Confidence bucket ─────────────────────────────────────────────────────
    conf_buckets = {
        "low_conf":    lambda r: abs(r.model_home_prob - 0.5) < 0.05,
        "medium_conf": lambda r: 0.05 <= abs(r.model_home_prob - 0.5) < 0.15,
        "high_conf":   lambda r: abs(r.model_home_prob - 0.5) >= 0.15,
    }
    for label, pred in conf_buckets.items():
        grp = [r for r in rows if pred(r)]
        if len(grp) >= _MIN_FOLD_N:
            results.append(_segment_metrics(grp, "confidence_bucket", label, alpha))

    # ── Disagreement bucket ───────────────────────────────────────────────────
    disagree_buckets = {
        "low_disagree":    lambda r: abs(r.model_home_prob - r.market_home_prob_no_vig) < 0.03,
        "medium_disagree": lambda r: 0.03 <= abs(r.model_home_prob - r.market_home_prob_no_vig) < 0.10,
        "high_disagree":   lambda r: abs(r.model_home_prob - r.market_home_prob_no_vig) >= 0.10,
    }
    for label, pred in disagree_buckets.items():
        grp = [r for r in rows if pred(r)]
        if len(grp) >= _MIN_FOLD_N:
            results.append(_segment_metrics(grp, "disagreement_bucket", label, alpha))

    return results


def _segment_value_summary(seg_results: list[SegmentResult]) -> dict[str, str]:
    """Best value classification per segment_type."""
    summary: dict[str, str] = {}
    _rank = {"NO_VALUE": 0, "WEAK_VALUE": 1, "CONDITIONAL_VALUE": 2, "STABLE_VALUE": 3}
    for sr in seg_results:
        cur = summary.get(sr.segment_type, "NO_VALUE")
        if _rank.get(sr.value_classification, 0) > _rank.get(cur, 0):
            summary[sr.segment_type] = sr.value_classification
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# §7  Gate recommendation
# ─────────────────────────────────────────────────────────────────────────────

def recommend_gate(
    fold_results: list[FoldStabilityRow],
    bootstrap_raw: BootstrapResult,
    bootstrap_blend: BootstrapResult,
    seg_results: list[SegmentResult],
) -> GateRecommendation:
    """
    Determine gate recommendation.

    HARD RULES:
      - Never create CANDIDATE_PATCH in this function.
      - best-per-fold alpha is diagnostic only — never used here.
      - bootstrap CI crossing 0 → NOT_SIGNIFICANT → cannot recommend PATCH_GATE_RECHECK.
    """
    stability_label = _fold_stability_label(fold_results)
    fold_stable = stability_label == "STABLE"
    bootstrap_sig = bootstrap_blend.significant
    seg_summary = _segment_value_summary(seg_results)
    has_stable_seg = any(v == "STABLE_VALUE" for v in seg_summary.values())
    has_conditional_seg = any(v in ("CONDITIONAL_VALUE", "STABLE_VALUE") for v in seg_summary.values())

    reasoning: list[str] = [
        f"Fold stability: {stability_label} ({sum(1 for f in fold_results if f.blend_bss >= 0)}/{len(fold_results)} folds with blend_bss >= 0)",
        f"Bootstrap blend_vs_market: {bootstrap_blend.significance_label} "
        f"(CI [{bootstrap_blend.ci_lower:+.4f}, {bootstrap_blend.ci_upper:+.4f}], "
        f"p_improve={bootstrap_blend.prob_improvement:.1%})",
        f"Segment value summary: {seg_summary}",
    ]

    # Determine recommendation
    if fold_stable and bootstrap_sig and has_stable_seg:
        recommendation = "PATCH_GATE_RECHECK"
        reasoning.append(
            "All three gates satisfied: fold-stable, bootstrap significant, "
            "at least one segment STABLE_VALUE → eligible for patch gate recheck."
        )
    elif not bootstrap_sig and not fold_stable:
        recommendation = "COLLECT_MORE_DATA"
        reasoning.append(
            "Bootstrap CI crosses 0 (NOT_SIGNIFICANT) and folds are unstable → "
            "need more data before any conclusion."
        )
    elif not bootstrap_sig and fold_stable:
        recommendation = "MARKET_BLEND_PAPER_ONLY"
        reasoning.append(
            "Folds stable but bootstrap CI crosses 0 (NOT_SIGNIFICANT) → "
            "market_blend can be tracked in paper-trading only, not production."
        )
    elif has_conditional_seg and not fold_stable:
        recommendation = "FEATURE_REPAIR_INVESTIGATION"
        reasoning.append(
            "Conditional value exists in some segments but folds are unstable → "
            "investigate feature quality to find source of conditional value."
        )
    elif has_conditional_seg:
        recommendation = "MARKET_BLEND_PAPER_ONLY"
        reasoning.append(
            "Conditional segment value found; bootstrap significant but fold stability mixed → "
            "market_blend paper-only until feature investigation clarifies source."
        )
    else:
        recommendation = "HOLD"
        reasoning.append(
            "No reliable signal detected across folds, bootstrap, or segments → HOLD."
        )

    return GateRecommendation(
        recommendation=recommendation,
        reasoning=reasoning,
        candidate_patch_created=False,
        bootstrap_significant=bootstrap_sig,
        fold_stable=fold_stable,
        has_stable_value_segment=has_stable_seg,
    )


# ─────────────────────────────────────────────────────────────────────────────
# §8  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_phase43_audit(
    rows: list[PredictionRow],
    n_splits: int = 5,
    alpha: float = FIXED_ALPHA,
    n_bootstrap: int = _N_BOOTSTRAP,
    input_path: str = "",
) -> Phase43AuditReport:
    """
    Run the complete Phase 43 model value & market blend stability audit.

    Does NOT modify any production file.
    Does NOT create CANDIDATE_PATCH.
    """
    report = Phase43AuditReport(
        input_path=input_path,
        row_count=len(rows),
        n_splits=n_splits,
        fixed_alpha=alpha,
        n_bootstrap=n_bootstrap,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )

    if len(rows) < _MIN_FOLD_N * (n_splits + 1):
        report.notes.append(f"INSUFFICIENT_DATA: need >= {_MIN_FOLD_N * (n_splits + 1)} rows, got {len(rows)}")
        report.gate = GateRecommendation(recommendation="HOLD", reasoning=["Insufficient data."])
        return report

    rows_sorted = _sort_rows(rows)

    # ── Overall metrics ───────────────────────────────────────────────────────
    model_p = [r.model_home_prob for r in rows_sorted]
    market_p = [r.market_home_prob_no_vig for r in rows_sorted]
    labels = [r.home_win for r in rows_sorted]
    blend_p = _blend_probs(model_p, market_p, alpha)

    report.overall_raw_brier = round(brier_score(model_p, labels), 6)
    report.overall_market_brier = round(brier_score(market_p, labels), 6)
    report.overall_blend_brier = round(brier_score(blend_p, labels), 6)
    report.overall_raw_bss = round(brier_skill_score(report.overall_raw_brier, report.overall_market_brier) or 0.0, 6)
    report.overall_blend_bss = round(brier_skill_score(report.overall_blend_brier, report.overall_market_brier) or 0.0, 6)
    report.overall_raw_ece = round(expected_calibration_error(model_p, labels)["ece"], 6)
    report.overall_blend_ece = round(expected_calibration_error(blend_p, labels)["ece"], 6)

    # ── Fold stability ────────────────────────────────────────────────────────
    report.fold_results = compute_fold_stability(rows_sorted, n_splits=n_splits, alpha=alpha)
    report.folds_with_positive_blend_bss = sum(1 for f in report.fold_results if f.blend_bss >= 0)
    report.folds_with_positive_raw_bss = sum(1 for f in report.fold_results if f.raw_bss >= 0)
    report.fold_stability_label = _fold_stability_label(report.fold_results)

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    bs_raw, bs_blend = run_bootstrap(rows_sorted, alpha=alpha, n_bootstrap=n_bootstrap)
    report.bootstrap_raw_vs_market = bs_raw
    report.bootstrap_blend_vs_market = bs_blend

    # ── Segment analysis ──────────────────────────────────────────────────────
    report.segment_results = analyse_segments(rows_sorted, alpha=alpha)
    report.segment_value_summary = _segment_value_summary(report.segment_results)

    # ── Gate recommendation ───────────────────────────────────────────────────
    report.gate = recommend_gate(
        report.fold_results,
        bs_raw,
        bs_blend,
        report.segment_results,
    )

    logger.info(
        "[Phase43] gate=%s | fold=%s | bootstrap_blend=%s | "
        "overall_raw_bss=%+.4f | overall_blend_bss=%+.4f",
        report.gate.recommendation,
        report.fold_stability_label,
        bs_blend.significance_label,
        report.overall_raw_bss,
        report.overall_blend_bss,
    )

    return report
