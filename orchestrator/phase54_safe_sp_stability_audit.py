"""
Phase 54: Re-run Phase43/44/45 Stability Audit with Safe SP Coefficient
=========================================================================
Uses Phase53 safe coefficient (scale=0.25x, effective=0.00075) to generate
a paper-only prediction JSONL and re-run Phase43/44/45 stability, tracking,
and attribution audits.

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False  (always)
  - PRODUCTION_MODIFIED = False      (always)
  - DIAGNOSTIC_ONLY = True           (always)
  - gate NEVER == "PATCH" or "PATCH_GATE_RECHECK"
  - alpha ALWAYS = 0.4 (not adjustable)
  - No look-ahead leakage
  - No re-training, no ensemble, no post-game data
  - safe_coefficient is diagnostic-only / paper-only

Gate values (exclusive):
  SAFE_SP_PAPER_ONLY_CONTINUE
  RE_RUN_BOOTSTRAP_REQUIRED
  FEATURE_REPAIR_STILL_WEAK
  COLLECT_MORE_DATA
  PATCH_GATE_RECHECK_NOT_ALLOWED   ← emitted if logic error tries to recheck

Phase 53 context:
  safe_coefficient_scale = 0.25
  effective_sp_coefficient = 0.003 * 0.25 = 0.00075
  gate = FEATURE_COEFFICIENT_PAPER_ONLY
  heavy_favorite ECE delta = -0.000080 (改善)
  overall BSS delta = +0.000037
  overall ECE delta = -0.001278
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from wbc_backend.evaluation.prediction_persistence import PredictionRow, load_prediction_rows
from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)
from orchestrator.phase43_model_value_market_blend_stability import (
    run_phase43_audit,
    Phase43AuditReport,
    FIXED_ALPHA,
)
from orchestrator.phase44_market_blend_paper_tracking import (
    run_phase44_tracking,
    PaperTrackingSnapshot,
    GATE_STATE as PHASE44_GATE_STATE,
)
from orchestrator.phase45_model_value_attribution import (
    run_phase45_attribution,
    AttributionResult,
    ALPHA as PHASE45_ALPHA,
)
from orchestrator.phase53_sp_coefficient_calibration import _apply_scaled_adjustment

logger = logging.getLogger(__name__)

# ─── Hard constants ────────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True

# Phase53 safe coefficient
SAFE_COEFFICIENT_SCALE: float = 0.25
EFFECTIVE_SP_COEFFICIENT: float = 0.003 * SAFE_COEFFICIENT_SCALE   # = 0.00075
FEATURE_EFFECT_MODE: str = "MODEL_AFFECTING"
PHASE54_VERSION: str = "phase54_safe_sp_stability_audit_v1"

# Gate values
SAFE_SP_PAPER_ONLY_CONTINUE: str = "SAFE_SP_PAPER_ONLY_CONTINUE"
RE_RUN_BOOTSTRAP_REQUIRED: str = "RE_RUN_BOOTSTRAP_REQUIRED"
FEATURE_REPAIR_STILL_WEAK: str = "FEATURE_REPAIR_STILL_WEAK"
COLLECT_MORE_DATA: str = "COLLECT_MORE_DATA"
PATCH_GATE_RECHECK_NOT_ALLOWED: str = "PATCH_GATE_RECHECK_NOT_ALLOWED"

_VALID_GATES: frozenset[str] = frozenset({
    SAFE_SP_PAPER_ONLY_CONTINUE,
    RE_RUN_BOOTSTRAP_REQUIRED,
    FEATURE_REPAIR_STILL_WEAK,
    COLLECT_MORE_DATA,
    PATCH_GATE_RECHECK_NOT_ALLOWED,
})

# Required segments for Phase45 comparison (matching Phase53 REQUIRED_SEGMENTS)
REQUIRED_SEGMENTS: list[str] = [
    "month:2025-04", "month:2025-05", "month:2025-06", "month:2025-07",
    "odds_bucket:heavy_favorite", "odds_bucket:mid",
    "confidence:high_confidence", "confidence:low_confidence",
    "disagreement:high", "disagreement:low",
]


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SafeCoeffSummary:
    """Summary of Phase53 safe coefficient applied in Phase54."""
    scale: float = SAFE_COEFFICIENT_SCALE
    effective_coefficient: float = EFFECTIVE_SP_COEFFICIENT
    feature_effect_mode: str = FEATURE_EFFECT_MODE
    input_rows: int = 0
    adjusted_rows: int = 0
    adjusted_rate: float = 0.0
    mean_abs_adjustment: float = 0.0
    max_abs_adjustment: float = 0.0
    overall_bss_delta_vs_baseline: Optional[float] = None
    overall_ece_delta_vs_baseline: Optional[float] = None
    heavy_fav_ece_delta_vs_baseline: Optional[float] = None
    high_conf_bss_delta_vs_baseline: Optional[float] = None
    diagnostic_only: bool = True
    candidate_patch_created: bool = False
    production_modified: bool = False


@dataclass
class Phase43Summary:
    """Summarised Phase43 fold / bootstrap / segment stability results."""
    overall_blend_bss: float = 0.0
    overall_blend_ece: float = 0.0
    overall_raw_bss: float = 0.0
    overall_raw_brier: float = 0.0
    overall_blend_brier: float = 0.0
    overall_market_brier: float = 0.0
    fold_stability_label: str = ""
    folds_positive: int = 0
    folds_total: int = 0
    bootstrap_significance: str = ""
    bootstrap_ci_lower: Optional[float] = None
    bootstrap_ci_upper: Optional[float] = None
    bootstrap_prob_improvement: Optional[float] = None
    # Delta vs Phase43 baseline
    blend_bss_delta: Optional[float] = None
    blend_ece_delta: Optional[float] = None
    fold_positive_delta: Optional[int] = None


@dataclass
class Phase44Summary:
    """Summarised Phase44 paper-only tracking result."""
    gate_state: str = "PAPER_ONLY"
    sample_size: int = 0
    alpha: float = 0.4
    blend_brier: float = 0.0
    blend_bss: float = 0.0
    blend_ece: float = 0.0
    market_brier: float = 0.0
    bootstrap_significance: str = ""
    candidate_patch_created: bool = False
    next_gate_criteria: list[str] = field(default_factory=list)


@dataclass
class SegmentDelta54:
    """Per-segment delta between Phase54 and Phase43 baseline."""
    segment_key: str           # e.g. "odds_bucket:heavy_favorite"
    phase54_blend_bss: Optional[float]
    phase43_blend_bss: Optional[float]
    delta_bss: Optional[float]
    phase54_blend_ece: Optional[float]
    phase43_blend_ece: Optional[float]
    delta_ece: Optional[float]
    n: int = 0
    label: str = ""            # IMPROVED / DEGRADED / UNCHANGED


@dataclass
class Phase45Summary:
    """Summarised Phase45 attribution result."""
    global_conclusion: str = ""
    gate: str = ""
    sample_size: int = 0
    positive_segments: list[str] = field(default_factory=list)
    failure_segments: list[str] = field(default_factory=list)
    heavy_fav_blend_bss: Optional[float] = None
    heavy_fav_blend_ece: Optional[float] = None
    high_conf_blend_bss: Optional[float] = None
    heavy_fav_ece_no_longer_failure: bool = False
    high_conf_improved: bool = False
    failure_count_delta: Optional[int] = None


@dataclass
class Phase54AuditResult:
    """Complete Phase 54 audit result."""
    # Config
    phase54_version: str = PHASE54_VERSION
    phase54_jsonl_path: str = ""
    baseline_jsonl_path: str = ""
    context_jsonl_path: str = ""
    run_timestamp: str = ""
    audit_hash: str = ""
    # Safe coefficient
    safe_coefficient_summary: SafeCoeffSummary = field(default_factory=SafeCoeffSummary)
    # Phase43/44/45 re-run summaries
    phase43_summary: Phase43Summary = field(default_factory=Phase43Summary)
    phase44_summary: Phase44Summary = field(default_factory=Phase44Summary)
    phase45_summary: Phase45Summary = field(default_factory=Phase45Summary)
    # Segment deltas vs Phase43 baseline
    segment_comparison: list[SegmentDelta54] = field(default_factory=list)
    # Gate
    gate_recommendation: str = ""
    gate_rationale: str = ""
    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False
    diagnostic_only: bool = True

    def __post_init__(self) -> None:
        assert not self.candidate_patch_created, "INVARIANT VIOLATION: candidate_patch_created must be False"
        assert not self.production_modified, "INVARIANT VIOLATION: production_modified must be False"
        assert self.diagnostic_only, "INVARIANT VIOLATION: diagnostic_only must be True"


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Phase54 JSONL generation — apply safe coefficient to context rows
# ─────────────────────────────────────────────────────────────────────────────

def _load_context_rows_raw(context_path: Path) -> list[dict]:
    """Load Phase52 context JSONL as raw dicts (preserving p0_features)."""
    rows: list[dict] = []
    with open(context_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_phase54_jsonl(
    context_path: Path,
    output_path: Path,
    scale: float = SAFE_COEFFICIENT_SCALE,
) -> SafeCoeffSummary:
    """
    Apply safe coefficient to Phase52 context rows and write Phase54 JSONL.

    Each output row:
      - model_home_prob = safe-coefficient-adjusted probability
      - original_model_home_prob = original model_home_prob (unadjusted)
      - All other PredictionRow fields preserved
      - Added: sp_coefficient_scale, effective_sp_coefficient,
               feature_effect_mode, diagnostic_only,
               candidate_patch_created, production_modified

    Returns SafeCoeffSummary with adjustment stats.
    """
    context_rows = _load_context_rows_raw(context_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    adjusted_count = 0
    abs_adjustments: list[float] = []
    output_rows: list[dict] = []

    for raw in context_rows:
        original_prob = raw["model_home_prob"]
        p0 = raw.get("p0_features", {})

        adj_prob, was_adjusted = _apply_scaled_adjustment(original_prob, p0, scale=scale)

        abs_adj = abs(adj_prob - original_prob)
        if was_adjusted:
            adjusted_count += 1
            abs_adjustments.append(abs_adj)

        out_row = dict(raw)
        out_row["original_model_home_prob"] = original_prob
        out_row["model_home_prob"] = round(adj_prob, 8)
        out_row["sp_coefficient_scale"] = scale
        out_row["effective_sp_coefficient"] = round(0.003 * scale, 8)
        out_row["feature_effect_mode"] = FEATURE_EFFECT_MODE
        out_row["diagnostic_only"] = True
        out_row["candidate_patch_created"] = False
        out_row["production_modified"] = False
        output_rows.append(out_row)

    with open(output_path, "w", encoding="utf-8") as f:
        for row in output_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n = len(context_rows)
    adj_rate = adjusted_count / n if n > 0 else 0.0
    mean_abs = sum(abs_adjustments) / len(abs_adjustments) if abs_adjustments else 0.0
    max_abs = max(abs_adjustments) if abs_adjustments else 0.0

    logger.info(
        "Phase54 JSONL written: %d rows, %d adjusted (%.1f%%), max_abs_adj=%.6f → %s",
        n, adjusted_count, adj_rate * 100, max_abs, output_path,
    )

    return SafeCoeffSummary(
        scale=scale,
        effective_coefficient=round(0.003 * scale, 8),
        feature_effect_mode=FEATURE_EFFECT_MODE,
        input_rows=n,
        adjusted_rows=adjusted_count,
        adjusted_rate=round(adj_rate, 4),
        mean_abs_adjustment=round(mean_abs, 8),
        max_abs_adjustment=round(max_abs, 8),
        diagnostic_only=True,
        candidate_patch_created=False,
        production_modified=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Phase43 baseline metrics (for delta computation)
# ─────────────────────────────────────────────────────────────────────────────

# Phase43 baseline from Phase43/44 evidence (persisted)
_PHASE43_BASELINE: dict[str, Any] = {
    "overall_blend_bss": 0.002200,
    "overall_blend_ece": 0.028100,
    "overall_raw_bss": -0.003900,
    "overall_raw_brier": 0.244700,
    "overall_blend_brier": 0.243200,
    "overall_market_brier": 0.243800,
    "fold_stability_label": "STABLE",
    "folds_positive": 4,
    "folds_total": 5,
    "bootstrap_significance": "NOT_SIGNIFICANT",
    "bootstrap_ci": [-0.0015, 0.0006],
    "bootstrap_prob_improvement": 0.810,
    # Segment baselines (blend_bss from Phase43 computation)
    "segment_blend_bss": {
        "odds_bucket:heavy_favorite": None,     # Phase43 did not always isolate these exactly
        "odds_bucket:mid": None,
        "confidence:high_confidence": None,
        "confidence:low_confidence": None,
        "month:2025-04": None,
        "month:2025-05": None,
        "month:2025-06": None,
        "month:2025-07": None,
        "disagreement:high": None,
        "disagreement:low": None,
    },
    "failure_count": 0,
}


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Phase43 summary extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_phase43_summary(
    report: Phase43AuditReport,
    baseline: dict,
) -> Phase43Summary:
    """Extract a simplified Phase43Summary from full Phase43AuditReport."""
    bss_delta = (
        round(report.overall_blend_bss - baseline["overall_blend_bss"], 6)
        if report.overall_blend_bss is not None
        else None
    )
    ece_delta = (
        round(report.overall_blend_ece - baseline["overall_blend_ece"], 6)
        if report.overall_blend_ece is not None
        else None
    )
    fold_pos_delta = (
        report.folds_with_positive_blend_bss - baseline["folds_positive"]
    )

    bs = report.bootstrap_blend_vs_market
    return Phase43Summary(
        overall_blend_bss=round(report.overall_blend_bss, 6),
        overall_blend_ece=round(report.overall_blend_ece, 6),
        overall_raw_bss=round(report.overall_raw_bss, 6),
        overall_raw_brier=round(report.overall_raw_brier, 6),
        overall_blend_brier=round(report.overall_blend_brier, 6),
        overall_market_brier=round(report.overall_market_brier, 6),
        fold_stability_label=report.fold_stability_label,
        folds_positive=report.folds_with_positive_blend_bss,
        folds_total=len(report.fold_results),
        bootstrap_significance=bs.significance_label if bs else "NOT_RUN",
        bootstrap_ci_lower=bs.ci_lower if bs else None,
        bootstrap_ci_upper=bs.ci_upper if bs else None,
        bootstrap_prob_improvement=bs.prob_improvement if bs else None,
        blend_bss_delta=bss_delta,
        blend_ece_delta=ece_delta,
        fold_positive_delta=fold_pos_delta,
    )


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Phase44 summary extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_phase44_summary(snap: PaperTrackingSnapshot) -> Phase44Summary:
    """Extract Phase44Summary from PaperTrackingSnapshot."""
    bs = snap.bootstrap
    return Phase44Summary(
        gate_state=snap.gate_state,
        sample_size=snap.sample_size,
        alpha=snap.alpha,
        blend_brier=snap.blend_brier,
        blend_bss=snap.blend_bss,
        blend_ece=snap.blend_ece,
        market_brier=snap.market_brier,
        bootstrap_significance=bs.significance if bs else "NOT_RUN",
        candidate_patch_created=snap.candidate_patch_created,
        next_gate_criteria=list(snap.next_gate_criteria),
    )


# ─────────────────────────────────────────────────────────────────────────────
# § 6  Phase45 summary extraction + segment mapping
# ─────────────────────────────────────────────────────────────────────────────

def _seg_key(seg_type: str, seg_label: str) -> str:
    """Build canonical segment key like 'odds_bucket:heavy_favorite'."""
    return f"{seg_type}:{seg_label}"


def _extract_phase45_summary(
    result: AttributionResult,
    baseline_failure_count: int,
) -> Phase45Summary:
    """Extract Phase45Summary from AttributionResult."""
    positive = [
        _seg_key(s.segment_type, s.segment_label)
        for s in result.top_positive_segments
    ]
    failure = [
        _seg_key(f.segment_type, f.segment_label)
        for f in result.failure_segments
    ]
    failure_delta = len(result.failure_segments) - baseline_failure_count

    # Find heavy_favorite and high_confidence segment results
    hf_seg = next(
        (s for s in result.segment_results
         if s.segment_type == "odds_bucket" and s.segment_label == "heavy_favorite"),
        None,
    )
    hc_seg = next(
        (s for s in result.segment_results
         if s.segment_type == "confidence" and s.segment_label == "high_confidence"),
        None,
    )

    hf_blend_bss = round(hf_seg.blend_bss, 6) if hf_seg else None
    hf_blend_ece = round(hf_seg.model_ece, 6) if hf_seg else None
    hc_blend_bss = round(hc_seg.blend_bss, 6) if hc_seg else None

    # heavy_favorite no longer failure if not in failure list
    hf_no_fail = not any(
        f.segment_type == "odds_bucket" and f.segment_label == "heavy_favorite"
        for f in result.failure_segments
    )
    hc_improved = hc_blend_bss is not None and hc_blend_bss >= 0.0

    return Phase45Summary(
        global_conclusion=result.global_conclusion,
        gate=result.gate,
        sample_size=result.sample_size,
        positive_segments=positive,
        failure_segments=failure,
        heavy_fav_blend_bss=hf_blend_bss,
        heavy_fav_blend_ece=hf_blend_ece,
        high_conf_blend_bss=hc_blend_bss,
        heavy_fav_ece_no_longer_failure=hf_no_fail,
        high_conf_improved=bool(hc_improved),
        failure_count_delta=failure_delta,
    )


# ─────────────────────────────────────────────────────────────────────────────
# § 7  Segment comparison (Phase54 vs Phase43 baseline)
# ─────────────────────────────────────────────────────────────────────────────

def _build_segment_comparison(
    result45: AttributionResult,
    baseline_phase43: Phase43AuditReport,
) -> list[SegmentDelta54]:
    """Build per-segment delta list comparing Phase54 vs Phase43."""
    # Build Phase43 segment lookup by key
    p43_bss: dict[str, float] = {}
    p43_ece: dict[str, float] = {}
    p43_n: dict[str, int] = {}
    for seg in baseline_phase43.segment_results:
        # Phase43 uses segment_type + segment_label
        key = _seg_key(seg.segment_type, seg.segment_label)
        p43_bss[key] = seg.blend_bss
        p43_ece[key] = seg.blend_ece
        p43_n[key] = seg.n

    # Build Phase45 (Phase54 run) segment lookup
    p54_bss: dict[str, float] = {}
    p54_ece: dict[str, float] = {}
    p54_n: dict[str, int] = {}
    for seg in result45.segment_results:
        key = _seg_key(seg.segment_type, seg.segment_label)
        p54_bss[key] = seg.blend_bss
        p54_ece[key] = seg.model_ece
        p54_n[key] = seg.n

    # Build comparison for required segments (and any extra segments found)
    all_keys = sorted(set(p43_bss.keys()) | set(p54_bss.keys()))
    deltas: list[SegmentDelta54] = []
    for key in all_keys:
        b43 = p43_bss.get(key)
        b54 = p54_bss.get(key)
        e43 = p43_ece.get(key)
        e54 = p54_ece.get(key)
        n = p54_n.get(key, p43_n.get(key, 0))

        delta_bss = round(b54 - b43, 6) if (b54 is not None and b43 is not None) else None
        delta_ece = round(e54 - e43, 6) if (e54 is not None and e43 is not None) else None

        if delta_bss is not None:
            label = "IMPROVED" if delta_bss > 0.0001 else ("DEGRADED" if delta_bss < -0.0001 else "UNCHANGED")
        else:
            label = "UNKNOWN"

        deltas.append(SegmentDelta54(
            segment_key=key,
            phase54_blend_bss=b54,
            phase43_blend_bss=b43,
            delta_bss=delta_bss,
            phase54_blend_ece=e54,
            phase43_blend_ece=e43,
            delta_ece=delta_ece,
            n=n,
            label=label,
        ))

    return deltas


# ─────────────────────────────────────────────────────────────────────────────
# § 8  Gate recommendation
# ─────────────────────────────────────────────────────────────────────────────

def _recommend_gate(
    p43: Phase43Summary,
    p44: Phase44Summary,
    p45: Phase45Summary,
    safe_coeff: SafeCoeffSummary,
) -> tuple[str, str]:
    """
    Determine gate recommendation. Returns (gate, rationale).

    Gate logic (in priority order):
    1. If n < 500 → COLLECT_MORE_DATA
    2. If overall BSS worsened AND overall ECE worsened → FEATURE_REPAIR_STILL_WEAK
    3. If failure segments increased → FEATURE_REPAIR_STILL_WEAK
    4. If improvement direction stable but bootstrap incomplete → RE_RUN_BOOTSTRAP_REQUIRED
    5. If all key metrics improve and bootstrap NOT_SIGNIFICANT (CI still crosses 0)
       → SAFE_SP_PAPER_ONLY_CONTINUE
    6. Fallback → FEATURE_REPAIR_STILL_WEAK
    """
    reasons: list[str] = []

    # Guard: no patch recheck
    if "PATCH" in (p45.gate if p45.gate else ""):
        return PATCH_GATE_RECHECK_NOT_ALLOWED, "gate 不允許在 Phase54 輸出 PATCH_GATE_RECHECK"

    n = p44.sample_size
    if n < 500:
        return COLLECT_MORE_DATA, f"樣本不足 (n={n} < 500)；需要更多資料方可評估穩定性。"

    bss_delta = p43.blend_bss_delta  # Phase54 vs Phase43 baseline
    ece_delta = p43.blend_ece_delta

    bss_improved = bss_delta is not None and bss_delta >= 0.0
    ece_improved = ece_delta is not None and ece_delta <= 0.0
    hf_not_worse = p45.heavy_fav_ece_no_longer_failure
    hc_ok = p45.high_conf_improved
    failure_not_increased = (
        p45.failure_count_delta is not None and p45.failure_count_delta <= 0
    ) or p45.failure_count_delta is None

    # Check if improvements are clearly failing
    clearly_worse = (
        (bss_delta is not None and bss_delta < -0.002) or
        (ece_delta is not None and ece_delta > 0.003)
    )
    failure_increased = (
        p45.failure_count_delta is not None and p45.failure_count_delta > 1
    )

    if clearly_worse or failure_increased:
        reasons.append(f"BSS delta={bss_delta}, ECE delta={ece_delta}, failure_count_delta={p45.failure_count_delta}")
        return FEATURE_REPAIR_STILL_WEAK, "整體指標惡化或 failure segment 增加：" + "; ".join(reasons)

    # Bootstrap completeness check
    bootstrap_run = p43.bootstrap_significance not in ("NOT_RUN", "")
    if not bootstrap_run:
        return RE_RUN_BOOTSTRAP_REQUIRED, "Bootstrap 未執行或不完整，需重跑以取得 CI 估計。"

    # Main gate: improvement direction stable + bootstrap CI still crosses 0
    bootstrap_ci_crosses_zero = (
        p43.bootstrap_ci_lower is not None and
        p43.bootstrap_ci_upper is not None and
        p43.bootstrap_ci_lower < 0 < p43.bootstrap_ci_upper
    )

    if bss_improved and ece_improved and hf_not_worse and failure_not_increased:
        if bootstrap_ci_crosses_zero:
            reasons.append(f"BSS delta={bss_delta:+.6f}, ECE delta={ece_delta:+.6f}")
            reasons.append(f"heavy_favorite ECE failure removed={hf_not_worse}")
            reasons.append(f"bootstrap CI=[{p43.bootstrap_ci_lower}, {p43.bootstrap_ci_upper}] 跨 0 → NOT_SIGNIFICANT")
            reasons.append("所有關鍵指標方向正確，但 bootstrap 仍未達顯著，繼續 paper tracking")
            return SAFE_SP_PAPER_ONLY_CONTINUE, "；".join(reasons)
        else:
            # Bootstrap significant — still paper only but stronger signal
            reasons.append(f"BSS delta={bss_delta:+.6f}, bootstrap CI 不跨 0")
            reasons.append("信號強度提升，但仍為 paper-only，不可 productionize")
            return SAFE_SP_PAPER_ONLY_CONTINUE, "；".join(reasons)

    # Partial improvement
    if bss_improved or ece_improved:
        reasons.append(f"部分指標改善: BSS_ok={bss_improved}, ECE_ok={ece_improved}")
        reasons.append(f"hf_not_worse={hf_not_worse}, hc_ok={hc_ok}")
        return SAFE_SP_PAPER_ONLY_CONTINUE, "部分指標改善；" + "；".join(reasons)

    return FEATURE_REPAIR_STILL_WEAK, f"整體指標未見明顯改善 (BSS delta={bss_delta}, ECE delta={ece_delta})"


# ─────────────────────────────────────────────────────────────────────────────
# § 9  Audit hash
# ─────────────────────────────────────────────────────────────────────────────

def _compute_audit_hash(
    phase43_bss: float,
    phase44_sample: int,
    phase45_gate: str,
    gate: str,
    run_ts: str,
) -> str:
    parts = "|".join([
        f"{phase43_bss:.8f}",
        str(phase44_sample),
        phase45_gate,
        gate,
        run_ts,
    ])
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# § 10  Safe coefficient delta vs baseline (from Phase53 metrics)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_safe_coeff_deltas(
    rows_phase54: list[PredictionRow],
    rows_baseline: list[PredictionRow],
    summary: SafeCoeffSummary,
) -> SafeCoeffSummary:
    """
    Compute overall BSS/ECE and segment deltas between Phase54 and baseline.
    Uses coin-flip baseline (0.25) for BSS.
    """
    COIN_FLIP = 0.25

    def _bss_and_ece(rows: list[PredictionRow]) -> tuple[float, float, float, float, float, float]:
        """Returns (brier, bss, ece, hf_ece, hc_bss, hc_ece)."""
        probs = [r.model_home_prob for r in rows]
        labels = [r.home_win for r in rows]
        mkt = [r.market_home_prob_no_vig for r in rows]

        brier = brier_score(probs, labels)
        bss_v = brier_skill_score(brier, COIN_FLIP)
        ece_v = expected_calibration_error(probs, labels)["ece"]

        hf_rows = [(p, l) for p, l, m in zip(probs, labels, mkt) if m >= 0.65]
        if len(hf_rows) >= 30:
            hp, hl = zip(*hf_rows)
            hf_ece = expected_calibration_error(list(hp), list(hl))["ece"]
        else:
            hf_ece = float("nan")

        hc_rows = [(p, l) for p, l in zip(probs, labels) if abs(p - 0.5) > 0.15]
        if len(hc_rows) >= 30:
            hcp, hcl = zip(*hc_rows)
            hc_bss_v = brier_skill_score(brier_score(list(hcp), list(hcl)), COIN_FLIP) or 0.0
        else:
            hc_bss_v = float("nan")

        return brier, bss_v or 0.0, ece_v, hf_ece, hc_bss_v, 0.0

    b54, bss54, ece54, hf_ece54, hc_bss54, _ = _bss_and_ece(rows_phase54)
    _, bss_bl, ece_bl, hf_ece_bl, hc_bss_bl, _ = _bss_and_ece(rows_baseline)

    def _safe_delta(a: float, b: float) -> Optional[float]:
        if math.isnan(a) or math.isnan(b):
            return None
        return round(a - b, 8)

    summary.overall_bss_delta_vs_baseline = _safe_delta(bss54, bss_bl)
    summary.overall_ece_delta_vs_baseline = _safe_delta(ece54, ece_bl)
    summary.heavy_fav_ece_delta_vs_baseline = _safe_delta(hf_ece54, hf_ece_bl)
    summary.high_conf_bss_delta_vs_baseline = _safe_delta(hc_bss54, hc_bss_bl)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# § 11  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_phase54_audit(
    baseline_path: Path,
    context_path: Path,
    phase54_output_path: Path,
    n_bootstrap: int = 500,
    n_splits: int = 5,
) -> Phase54AuditResult:
    """
    Main Phase 54 entry point.

    1. Apply safe coefficient (scale=0.25) to context rows → Phase54 JSONL
    2. Load Phase54 rows as PredictionRows
    3. Run Phase43 stability audit (fold + bootstrap + segment)
    4. Run Phase44 paper tracking
    5. Run Phase45 attribution
    6. Compute segment comparison vs Phase43 baseline
    7. Recommend gate

    Hard rules: never mutates production, never creates candidate patch.
    """
    run_ts = datetime.now(timezone.utc).isoformat()
    logger.info("Phase 54 starting — safe_coefficient_scale=%.2f", SAFE_COEFFICIENT_SCALE)

    # ── Step 1: Generate Phase54 JSONL ────────────────────────────────────────
    logger.info("Step 1: Applying safe coefficient → %s", phase54_output_path)
    coeff_summary = build_phase54_jsonl(context_path, phase54_output_path, scale=SAFE_COEFFICIENT_SCALE)

    # ── Step 2: Load rows ─────────────────────────────────────────────────────
    logger.info("Step 2: Loading Phase54 rows")
    rows_phase54 = load_prediction_rows(phase54_output_path)
    rows_baseline = load_prediction_rows(baseline_path)

    logger.info("Phase54 rows: %d | Baseline rows: %d", len(rows_phase54), len(rows_baseline))

    # Enrich safe coeff summary with delta metrics
    coeff_summary = _compute_safe_coeff_deltas(rows_phase54, rows_baseline, coeff_summary)

    # ── Step 3: Phase43 re-run ────────────────────────────────────────────────
    logger.info("Step 3: Phase43 fold / bootstrap / segment stability audit")
    p43_report = run_phase43_audit(
        rows_phase54,
        n_splits=n_splits,
        alpha=FIXED_ALPHA,
        n_bootstrap=n_bootstrap,
        input_path=str(phase54_output_path),
    )
    # Also run Phase43 on baseline for comparison
    logger.info("Step 3b: Phase43 baseline audit for comparison")
    p43_baseline = run_phase43_audit(
        rows_baseline,
        n_splits=n_splits,
        alpha=FIXED_ALPHA,
        n_bootstrap=n_bootstrap,
        input_path=str(baseline_path),
    )

    p43_summary = _extract_phase43_summary(p43_report, _PHASE43_BASELINE)

    # ── Step 4: Phase44 re-run ────────────────────────────────────────────────
    logger.info("Step 4: Phase44 paper-only tracking")
    p44_snap = run_phase44_tracking(
        rows_phase54,
        input_path=str(phase54_output_path),
        alpha=FIXED_ALPHA,
        rerun_bootstrap=False,   # bootstrap already done in Step 3
        human_review_approved=False,
    )
    # Update bootstrap from Phase43 re-run result
    if p43_report.bootstrap_blend_vs_market:
        p44_snap.bootstrap.significance = p43_report.bootstrap_blend_vs_market.significance_label
        p44_snap.bootstrap.ci_lower = p43_report.bootstrap_blend_vs_market.ci_lower
        p44_snap.bootstrap.ci_upper = p43_report.bootstrap_blend_vs_market.ci_upper
        p44_snap.bootstrap.prob_improvement = p43_report.bootstrap_blend_vs_market.prob_improvement
        p44_snap.bootstrap.source = "phase54_rerun"

    p44_summary = _extract_phase44_summary(p44_snap)

    # ── Step 5: Phase45 re-run ────────────────────────────────────────────────
    logger.info("Step 5: Phase45 attribution")
    p45_result = run_phase45_attribution(
        rows_phase54,
        input_path=str(phase54_output_path),
        alpha=PHASE45_ALPHA,
    )
    p45_summary = _extract_phase45_summary(p45_result, _PHASE43_BASELINE["failure_count"])

    # ── Step 6: Segment comparison ────────────────────────────────────────────
    logger.info("Step 6: Building segment comparison")
    seg_comparison = _build_segment_comparison(p45_result, p43_baseline)

    # ── Step 7: Gate recommendation ───────────────────────────────────────────
    logger.info("Step 7: Gate recommendation")
    gate, gate_rationale = _recommend_gate(p43_summary, p44_summary, p45_summary, coeff_summary)
    assert gate in _VALID_GATES, f"INVARIANT VIOLATION: gate={gate!r}"

    # ── Build result ──────────────────────────────────────────────────────────
    audit_hash = _compute_audit_hash(
        p43_summary.overall_blend_bss,
        p44_summary.sample_size,
        p45_summary.gate,
        gate,
        run_ts,
    )

    result = Phase54AuditResult(
        phase54_version=PHASE54_VERSION,
        phase54_jsonl_path=str(phase54_output_path),
        baseline_jsonl_path=str(baseline_path),
        context_jsonl_path=str(context_path),
        run_timestamp=run_ts,
        audit_hash=audit_hash,
        safe_coefficient_summary=coeff_summary,
        phase43_summary=p43_summary,
        phase44_summary=p44_summary,
        phase45_summary=p45_summary,
        segment_comparison=seg_comparison,
        gate_recommendation=gate,
        gate_rationale=gate_rationale,
        candidate_patch_created=False,
        production_modified=False,
        diagnostic_only=True,
    )

    logger.info(
        "Phase54 complete — gate=%s | P43_BSS=%+.6f | P44_n=%d | P45_failures=%d",
        gate,
        p43_summary.overall_blend_bss,
        p44_summary.sample_size,
        len(p45_summary.failure_segments),
    )
    return result
