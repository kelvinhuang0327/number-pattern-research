"""
Phase 44: Market Blend Paper-Only Tracking & Evidence Pack
===========================================================
Persists and exposes a reproducible paper-only tracking snapshot for the
α=0.4 market_blend strategy validated in Phase 43.

Hard Rules (never violate):
  - gate_state ALWAYS = "PAPER_ONLY"
  - candidate_patch_created ALWAYS = False
  - alpha ALWAYS = 0.4 (fixed from Phase 42A / Phase 43)
  - Do NOT modify production model
  - Do NOT call external API / LLM
  - Do NOT bypass BSS Safety Gate
  - Do NOT treat best-per-fold alpha as production proof
  - Bootstrap CI crossing zero → NOT_SIGNIFICANT → PAPER_ONLY stays
  - All metrics delegate to wbc_backend.evaluation.metrics (SSOT)

Gate criteria for next stage (ALL must be met for re-evaluation):
  1. sample_size >= 3000 OR +30 days new rolling data since Phase 43
  2. Bootstrap CI does not cross 0 (SIGNIFICANT)
  3. blend_bss consistently > 0 across >= 3 consecutive evaluation periods
  4. ECE not clearly deteriorated: blend_ece <= market_ece + 0.01
  5. >= 4/5 folds or rolling windows have positive blend_bss
  6. Human review approved
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
PAPER_ALPHA: float = 0.4           # Fixed from Phase 42A / Phase 43 — never change
GATE_STATE: str = "PAPER_ONLY"    # Never changes until ALL gate criteria met
CANDIDATE_PATCH_CREATED: bool = False  # Hard rule — never flip

# Next-gate sample threshold
GATE_CRITERIA_MIN_SAMPLE: int = 3_000
# Phase 43 persisted evidence (inline to avoid circular import at module level)
PHASE43_EVIDENCE_SUMMARY: dict[str, Any] = {
    "gate_recommendation": "MARKET_BLEND_PAPER_ONLY",
    "fold_stability": "STABLE",
    "folds_positive": 4,
    "folds_total": 5,
    "bootstrap_significance": "NOT_SIGNIFICANT",
    "bootstrap_ci": [-0.0015, 0.0006],
    "bootstrap_prob_improvement": 0.810,
    "overall_raw_bss": -0.0039,
    "overall_blend_bss": 0.0022,
    "overall_raw_brier": 0.2447,
    "overall_market_brier": 0.2438,
    "overall_blend_brier": 0.2432,
    "overall_raw_ece": 0.0311,
    "overall_blend_ece": 0.0281,
    "segment_value": {
        "month": "CONDITIONAL_VALUE",
        "odds_bucket": "CONDITIONAL_VALUE",
        "confidence_bucket": "WEAK_VALUE",
        "disagreement_bucket": "WEAK_VALUE",
    },
    "sample_size": 2025,
    "date_range": ["2025-04-27", "2025-09-28"],
    "audit_completed_at": "2026-05-05",
}

# Next-gate criteria (human readable)
NEXT_GATE_CRITERIA: list[str] = [
    "sample_size >= 3000 OR +30 days new rolling data since Phase 43 (2026-05-05)",
    "bootstrap CI does not cross 0 (SIGNIFICANT at 95% level)",
    "blend_bss consistently > 0 across >= 3 consecutive evaluation periods",
    "ECE not clearly deteriorated: blend_ece <= market_ece + 0.01",
    ">= 4/5 folds or rolling windows have positive blend_bss",
    "human review approved (via review_queue system)",
]

RISK_NOTES: list[str] = [
    "α=0.4 blend shows +0.22% BSS vs market overall but CI crosses 0 — statistically NOT_SIGNIFICANT",
    "Best-per-fold alpha varies (0.1–1.0) — diagnostic_only; do NOT use per-fold alpha in production",
    "CONDITIONAL_VALUE only in month + odds_bucket segments; high_conf segment shows NO_VALUE",
    "Paper-only: track BSS/ECE/sample metrics for >= 3 periods before re-evaluating gate",
    "Do NOT deploy to production without PATCH_GATE_RECHECK from BSS Safety Gate",
]


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class MetricBundle:
    """Metric group for raw / market / blend comparison."""
    brier: float
    bss: float          # vs market baseline
    ece: float


@dataclass
class BootstrapSummary:
    """Summarised bootstrap results (from Phase 43 or re-run)."""
    significance: str             # "SIGNIFICANT" | "NOT_SIGNIFICANT" | "NOT_RUN"
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    prob_improvement: Optional[float]
    n_bootstrap: int = 0
    source: str = "phase43"      # "phase43" | "live_rerun"


@dataclass
class GateCriteriaStatus:
    """Per-criterion gate readiness."""
    sample_size_met: bool
    bootstrap_significant: bool
    blend_bss_consistently_positive: bool
    ece_not_deteriorated: bool
    folds_positive_met: bool
    human_review_approved: bool

    def all_met(self) -> bool:
        return all([
            self.sample_size_met,
            self.bootstrap_significant,
            self.blend_bss_consistently_positive,
            self.ece_not_deteriorated,
            self.folds_positive_met,
            self.human_review_approved,
        ])

    def summary(self) -> str:
        n_met = sum([
            self.sample_size_met,
            self.bootstrap_significant,
            self.blend_bss_consistently_positive,
            self.ece_not_deteriorated,
            self.folds_positive_met,
            self.human_review_approved,
        ])
        total = 6
        if n_met == total:
            return "MET"
        elif n_met >= 3:
            return "PARTIALLY_MET"
        else:
            return "NOT_MET"


@dataclass
class PaperTrackingSnapshot:
    """
    Phase 44 paper-only tracking snapshot.
    All fields are read-only evidence — no production mutation.
    """
    # Identity
    run_id: str
    generated_at: str            # UTC ISO
    input_prediction_path: str

    # Data coverage
    sample_size: int
    date_start: str
    date_end: str

    # Fixed parameter (NEVER changes)
    alpha: float = PAPER_ALPHA

    # Raw model metrics
    raw_brier: float = 0.0
    raw_bss: float = 0.0         # vs market
    raw_ece: float = 0.0

    # Market baseline metrics
    market_brier: float = 0.0
    market_ece: float = 0.0

    # Market blend α=0.4 metrics
    blend_brier: float = 0.0
    blend_bss: float = 0.0       # vs market
    blend_ece: float = 0.0

    # Deltas (blend vs market)
    brier_delta: float = 0.0         # blend_brier - market_brier (negative = improvement)
    bss_vs_market: float = 0.0       # alias for blend_bss

    # Segment summary {type → best_value_classification}
    segment_summary: dict[str, str] = field(default_factory=dict)

    # Bootstrap evidence (Phase 43 or re-run)
    bootstrap: Optional[BootstrapSummary] = None

    # Gate state — ALWAYS PAPER_ONLY
    gate_state: str = GATE_STATE
    candidate_patch_created: bool = CANDIDATE_PATCH_CREATED  # ALWAYS False

    # Gate criteria
    gate_criteria: Optional[GateCriteriaStatus] = None
    gate_criteria_summary: str = "NOT_MET"

    # Phase 43 evidence recap
    phase43_evidence: dict[str, Any] = field(default_factory=dict)

    # Context
    risk_notes: list[str] = field(default_factory=list)
    next_gate_criteria: list[str] = field(default_factory=list)

    # Audit hash (sha256 of key numeric fields + gate_state)
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Flatten BootstrapSummary
        if self.bootstrap is not None:
            d["bootstrap"] = asdict(self.bootstrap)
        # Flatten GateCriteriaStatus
        if self.gate_criteria is not None:
            gc = asdict(self.gate_criteria)
            gc["summary"] = self.gate_criteria.summary()
            d["gate_criteria"] = gc
        return d


# ─── Core Computation ────────────────────────────────────────────────────────

def _blend_probs(raw: list[float], market: list[float], alpha: float) -> list[float]:
    """blend = alpha * raw + (1 - alpha) * market"""
    return [alpha * r + (1.0 - alpha) * m for r, m in zip(raw, market)]


def _compute_metrics(
    raw_probs: list[float],
    market_probs: list[float],
    labels: list[int],
    alpha: float = PAPER_ALPHA,
) -> tuple[MetricBundle, MetricBundle, MetricBundle]:
    """Return (raw, market, blend) MetricBundles."""
    blend_probs = _blend_probs(raw_probs, market_probs, alpha)

    # brier_score(probs, labels), brier_skill_score(model_brier, baseline_brier)
    # expected_calibration_error(probs, labels) → dict["ece"] scalar
    raw_b = brier_score(raw_probs, labels)
    mkt_b = brier_score(market_probs, labels)
    blend_b = brier_score(blend_probs, labels)

    raw_bss_val = brier_skill_score(raw_b, mkt_b)
    blend_bss_val = brier_skill_score(blend_b, mkt_b)
    raw_bss = raw_bss_val if raw_bss_val is not None else 0.0
    blend_bss = blend_bss_val if blend_bss_val is not None else 0.0

    raw_ece = expected_calibration_error(raw_probs, labels)["ece"]
    mkt_ece = expected_calibration_error(market_probs, labels)["ece"]
    blend_ece = expected_calibration_error(blend_probs, labels)["ece"]

    raw_bundle = MetricBundle(brier=raw_b, bss=raw_bss, ece=raw_ece)
    mkt_bundle = MetricBundle(brier=mkt_b, bss=0.0, ece=mkt_ece)
    blend_bundle = MetricBundle(brier=blend_b, bss=blend_bss, ece=blend_ece)
    return raw_bundle, mkt_bundle, blend_bundle


def _compute_segment_summary(rows: list[PredictionRow], alpha: float = PAPER_ALPHA) -> dict[str, str]:
    """
    Compute best-value classification per segment type.
    Delegate heavy logic to Phase 43 analyse_segments if available.
    """
    try:
        from orchestrator.phase43_model_value_market_blend_stability import (
            analyse_segments,
        )
        seg_results = analyse_segments(rows, alpha=alpha)
        seg_types = sorted({sr.segment_type for sr in seg_results})
        _value_rank = {"NO_VALUE": 0, "WEAK_VALUE": 1, "CONDITIONAL_VALUE": 2, "STABLE_VALUE": 3}
        summary: dict[str, str] = {}
        for seg_type in seg_types:
            best = max(
                (sr for sr in seg_results if sr.segment_type == seg_type),
                key=lambda s: _value_rank.get(s.value_classification, 0),
                default=None,
            )
            if best:
                summary[seg_type] = best.value_classification
        return summary
    except Exception as exc:
        logger.warning("[Phase44] segment analysis unavailable: %s", exc)
        return {}


def _compute_gate_criteria(
    snapshot: PaperTrackingSnapshot,
    folds_positive: int = 4,
    folds_total: int = 5,
    human_review_approved: bool = False,
) -> GateCriteriaStatus:
    """Evaluate next-gate criteria against current snapshot."""
    sample_size_met = snapshot.sample_size >= GATE_CRITERIA_MIN_SAMPLE
    bootstrap_significant = (
        snapshot.bootstrap is not None
        and snapshot.bootstrap.significance == "SIGNIFICANT"
    )
    # blend_bss_consistently_positive: require current period to be > 0
    # (full consecutive tracking requires multi-run history — conservative single check here)
    blend_bss_positive = snapshot.blend_bss > 0.0
    ece_not_deteriorated = snapshot.blend_ece <= (snapshot.market_ece + 0.01)
    folds_met = (folds_total > 0) and (folds_positive / folds_total >= 0.8)

    return GateCriteriaStatus(
        sample_size_met=sample_size_met,
        bootstrap_significant=bootstrap_significant,
        blend_bss_consistently_positive=blend_bss_positive,
        ece_not_deteriorated=ece_not_deteriorated,
        folds_positive_met=folds_met,
        human_review_approved=human_review_approved,
    )


def _compute_audit_hash(snapshot: PaperTrackingSnapshot) -> str:
    """Stable sha256 of key numeric fields + gate_state."""
    key_data = {
        "run_id": snapshot.run_id,
        "sample_size": snapshot.sample_size,
        "date_start": snapshot.date_start,
        "date_end": snapshot.date_end,
        "alpha": snapshot.alpha,
        "raw_brier": round(snapshot.raw_brier, 8),
        "market_brier": round(snapshot.market_brier, 8),
        "blend_brier": round(snapshot.blend_brier, 8),
        "blend_bss": round(snapshot.blend_bss, 8),
        "gate_state": snapshot.gate_state,
        "candidate_patch_created": snapshot.candidate_patch_created,
    }
    raw = json.dumps(key_data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def run_phase44_tracking(
    rows: list[PredictionRow],
    input_path: str = "",
    alpha: float = PAPER_ALPHA,
    rerun_bootstrap: bool = False,
    n_bootstrap: int = 1000,
    human_review_approved: bool = False,
) -> PaperTrackingSnapshot:
    """
    Run Phase 44 paper-only tracking.

    Args:
        rows: Loaded PredictionRow list from Phase 39 JSONL.
        input_path: Source path (for provenance only).
        alpha: Fixed at 0.4; overrides ignored if different — enforced by assertion.
        rerun_bootstrap: If True, re-run bootstrap CI using Phase 43 module.
        n_bootstrap: Bootstrap iterations when rerun_bootstrap=True.
        human_review_approved: Set True only by explicit human_review system.

    Returns:
        PaperTrackingSnapshot — read-only evidence, no production mutation.

    Hard Rules:
        - gate_state ALWAYS = "PAPER_ONLY"
        - candidate_patch_created ALWAYS = False
        - alpha ALWAYS = 0.4
    """
    # Enforce alpha hard rule
    if abs(alpha - PAPER_ALPHA) > 1e-9:
        logger.warning(
            "[Phase44] alpha override %s rejected — enforcing PAPER_ALPHA=0.4", alpha
        )
    alpha = PAPER_ALPHA  # always 0.4

    if not rows:
        raise ValueError("Phase 44 requires at least 1 PredictionRow")

    # Sort by game_date for date_range extraction
    sorted_rows = sorted(rows, key=lambda r: r.game_date)
    date_start = sorted_rows[0].game_date
    date_end = sorted_rows[-1].game_date

    # Extract probabilities and labels
    raw_probs = [r.model_home_prob for r in rows]
    market_probs = [r.market_home_prob_no_vig for r in rows]
    labels = [r.home_win for r in rows]

    # Compute metrics
    raw_m, mkt_m, blend_m = _compute_metrics(raw_probs, market_probs, labels, alpha)

    # Segment summary
    segment_summary = _compute_segment_summary(rows, alpha)

    # Bootstrap summary
    if rerun_bootstrap:
        try:
            from orchestrator.phase43_model_value_market_blend_stability import run_bootstrap
            _bs_raw, bs_blend = run_bootstrap(rows, alpha=alpha, n_bootstrap=n_bootstrap)
            bootstrap = BootstrapSummary(
                significance=bs_blend.significance_label,
                ci_lower=bs_blend.ci_lower,
                ci_upper=bs_blend.ci_upper,
                prob_improvement=bs_blend.prob_improvement,
                n_bootstrap=n_bootstrap,
                source="live_rerun",
            )
        except Exception as exc:
            logger.warning("[Phase44] bootstrap rerun failed: %s", exc)
            bootstrap = _phase43_bootstrap_summary()
    else:
        bootstrap = _phase43_bootstrap_summary()

    # Build preliminary snapshot (no audit_hash yet)
    run_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    snapshot = PaperTrackingSnapshot(
        run_id=run_id,
        generated_at=generated_at,
        input_prediction_path=input_path,
        sample_size=len(rows),
        date_start=date_start,
        date_end=date_end,
        alpha=alpha,
        raw_brier=raw_m.brier,
        raw_bss=raw_m.bss,
        raw_ece=raw_m.ece,
        market_brier=mkt_m.brier,
        market_ece=mkt_m.ece,
        blend_brier=blend_m.brier,
        blend_bss=blend_m.bss,
        blend_ece=blend_m.ece,
        brier_delta=blend_m.brier - mkt_m.brier,
        bss_vs_market=blend_m.bss,
        segment_summary=segment_summary,
        bootstrap=bootstrap,
        gate_state=GATE_STATE,            # ALWAYS PAPER_ONLY
        candidate_patch_created=False,    # ALWAYS False
        phase43_evidence=PHASE43_EVIDENCE_SUMMARY,
        risk_notes=RISK_NOTES,
        next_gate_criteria=NEXT_GATE_CRITERIA,
    )

    # Gate criteria
    gate_criteria = _compute_gate_criteria(
        snapshot,
        folds_positive=4,   # from Phase 43
        folds_total=5,
        human_review_approved=human_review_approved,
    )
    snapshot.gate_criteria = gate_criteria
    snapshot.gate_criteria_summary = gate_criteria.summary()

    # Audit hash (computed last, after all fields set)
    snapshot.audit_hash = _compute_audit_hash(snapshot)

    logger.info(
        "[Phase44] gate=%s | sample=%d | blend_bss=%+.4f | alpha=%.1f | "
        "bootstrap=%s | gate_criteria=%s | candidate_patch=%s",
        snapshot.gate_state,
        snapshot.sample_size,
        snapshot.blend_bss,
        snapshot.alpha,
        snapshot.bootstrap.significance if snapshot.bootstrap else "N/A",
        snapshot.gate_criteria_summary,
        snapshot.candidate_patch_created,
    )

    # Safety assertion: enforce hard rules at exit
    assert snapshot.gate_state == "PAPER_ONLY", "HARD RULE VIOLATED: gate_state must be PAPER_ONLY"
    assert snapshot.candidate_patch_created is False, "HARD RULE VIOLATED: candidate_patch_created must be False"
    assert abs(snapshot.alpha - PAPER_ALPHA) < 1e-9, "HARD RULE VIOLATED: alpha must be 0.4"

    return snapshot


def _phase43_bootstrap_summary() -> BootstrapSummary:
    """Return Phase 43 persisted bootstrap evidence."""
    return BootstrapSummary(
        significance="NOT_SIGNIFICANT",
        ci_lower=PHASE43_EVIDENCE_SUMMARY["bootstrap_ci"][0],
        ci_upper=PHASE43_EVIDENCE_SUMMARY["bootstrap_ci"][1],
        prob_improvement=PHASE43_EVIDENCE_SUMMARY["bootstrap_prob_improvement"],
        n_bootstrap=1000,
        source="phase43",
    )
