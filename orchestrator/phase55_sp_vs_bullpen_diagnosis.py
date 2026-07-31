"""
orchestrator/phase55_sp_vs_bullpen_diagnosis.py
================================================
Phase 55 — SP Functional Form Redesign vs Bullpen Feature Investigation

背景：
  Phase 54 gate = FEATURE_REPAIR_STILL_WEAK
  - safe_coefficient_scale=0.25, effective=0.00075
  - Phase45 failure_segments=6
  - heavy_fav_ece_no_longer_failure=False
  - high_conf_improved=False

本階段診斷 Phase54 失敗原因：
  A. SP functional form 錯誤或太弱
  B. SP feature 本身不夠，缺 bullpen / late-game 狀態特徵
  C. 目前樣本不足，signal 不穩定

本 Phase 只做 diagnosis / blueprint：
  - 不進 production、不改模型、不建立 candidate patch
  - 不寫 production JSONL
  - 比較 6 種 SP functional forms 的 offline metrics

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - gate / conclusion NEVER == "PATCH" or "PATCH_GATE_RECHECK"
  - No look-ahead leakage
  - No re-training, no ensemble
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# § 0  Constants
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False      # NEVER change
PRODUCTION_MODIFIED: bool = False          # NEVER change
DIAGNOSTIC_ONLY: bool = True               # NEVER change

PHASE55_VERSION: str = "phase55_sp_vs_bullpen_diagnosis_v1"

# ─── Conclusion Labels ────────────────────────────────────────────────────────
SP_FUNCTIONAL_FORM_REDESIGN: str = "SP_FUNCTIONAL_FORM_REDESIGN"
BULLPEN_FEATURE_INVESTIGATION: str = "BULLPEN_FEATURE_INVESTIGATION"
COLLECT_MORE_DATA: str = "COLLECT_MORE_DATA"

_VALID_CONCLUSIONS: frozenset[str] = frozenset({
    SP_FUNCTIONAL_FORM_REDESIGN,
    BULLPEN_FEATURE_INVESTIGATION,
    COLLECT_MORE_DATA,
})

# ─── Functional form names ────────────────────────────────────────────────────
FORM_TANH_CURRENT: str = "tanh_current"
FORM_TANH_STRONGER: str = "tanh_stronger"
FORM_LINEAR_CAPPED: str = "linear_capped"
FORM_SIGN_ONLY: str = "sign_only"
FORM_BUCKETED_DELTA: str = "bucketed_delta"
FORM_SHRINK_TO_MARKET: str = "shrink_to_market"

ALL_FORM_NAMES: list[str] = [
    FORM_TANH_CURRENT,
    FORM_TANH_STRONGER,
    FORM_LINEAR_CAPPED,
    FORM_SIGN_ONLY,
    FORM_BUCKETED_DELTA,
    FORM_SHRINK_TO_MARKET,
]

# ─── Recommended bullpen features ─────────────────────────────────────────────
RECOMMENDED_BULLPEN_FEATURES: list[str] = [
    "bullpen_fatigue_3d",
    "bullpen_fatigue_7d",
    "reliever_back_to_back_count",
    "bullpen_recent_era_proxy",
    "late_game_leverage_usage_proxy",
]

# ─── Algorithm thresholds ─────────────────────────────────────────────────────
_COIN_FLIP_BRIER: float = 0.25
_MIN_SEGMENT_N: int = 30
_FAILURE_BSS_THRESHOLD: float = -0.01
_ECE_DETERIORATION_MARGIN: float = 0.01
_PROB_LO: float = 0.01
_PROB_HI: float = 0.99

# Phase54 persisted evidence
_PHASE54_FAILURE_COUNT: int = 6
_PHASE54_OVERALL_BSS: float = 0.002174
_PHASE54_HEAVY_FAV_ECE_UNRESOLVED: bool = True  # heavy_fav_ece_no_longer_failure=False

# Decision thresholds
_CLEAR_FAILURE_REDUCTION: int = 2    # failure_count must drop by >= 2 to qualify for SP_FUNCTIONAL_FORM_REDESIGN
_BULLPEN_SCORE_THRESHOLD: float = 0.60


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SegmentMetrics55:
    """Per-segment metrics for one functional form evaluation."""
    segment_key: str
    n: int
    model_bss: Optional[float]
    model_ece: Optional[float]
    market_bss: Optional[float]
    market_ece: Optional[float]
    is_failure: bool = False


@dataclass
class FunctionalFormResult:
    """Offline diagnostic result for one SP functional form."""
    form_name: str = ""
    # Adjustment stats
    adjusted_rows: int = 0
    adjusted_rate: float = 0.0
    mean_abs_adjustment: float = 0.0
    max_abs_adjustment: float = 0.0
    # Overall metrics
    overall_bss: Optional[float] = None
    overall_ece: Optional[float] = None
    # Key segment metrics
    heavy_fav_ece: Optional[float] = None
    high_conf_bss: Optional[float] = None
    month_2025_04_bss: Optional[float] = None
    # Failure segment count
    failure_segment_count: int = 0
    # Full segment details
    segment_details: list[SegmentMetrics55] = field(default_factory=list)
    # Hard rules (always enforced)
    diagnostic_only: bool = True
    candidate_patch_created: bool = False
    production_modified: bool = False


@dataclass
class BullpenDiagnosis:
    """Bullpen missing-feature diagnosis."""
    bullpen_missing_score: float = 0.0      # 0.0 – 1.0
    evidence: list[str] = field(default_factory=list)
    recommended_features: list[str] = field(default_factory=list)
    failure_pattern: str = "DIFFUSE"        # HEAVY_FAVORITE_CONCENTRATED | HIGH_CONFIDENCE_CONCENTRATED | MIXED | DIFFUSE
    bullpen_feature_likely_missing: bool = False


@dataclass
class Phase55DiagnosisResult:
    """Complete Phase 55 SP vs Bullpen Diagnosis result."""
    # Config
    phase55_version: str = PHASE55_VERSION
    run_timestamp: str = ""
    audit_hash: str = ""
    # Phase54 context
    phase54_failure_count: int = _PHASE54_FAILURE_COUNT
    phase54_failure_segments: list[str] = field(default_factory=list)
    # Functional form results
    functional_form_results: list[FunctionalFormResult] = field(default_factory=list)
    best_form_name: Optional[str] = None
    best_form_failure_count: Optional[int] = None
    # Bullpen diagnosis
    bullpen_diagnosis: BullpenDiagnosis = field(default_factory=BullpenDiagnosis)
    # Decision
    conclusion: str = COLLECT_MORE_DATA
    conclusion_rationale: str = ""
    recommended_phase56_tasks: list[str] = field(default_factory=list)
    # Hard rules
    candidate_patch_created: bool = False
    production_modified: bool = False
    diagnostic_only: bool = True

    def __post_init__(self) -> None:
        assert not self.candidate_patch_created, (
            "INVARIANT VIOLATION: candidate_patch_created must be False"
        )
        assert not self.production_modified, (
            "INVARIANT VIOLATION: production_modified must be False"
        )
        assert self.diagnostic_only, (
            "INVARIANT VIOLATION: diagnostic_only must be True"
        )
        assert self.conclusion in _VALID_CONCLUSIONS, (
            f"INVARIANT VIOLATION: invalid conclusion {self.conclusion!r}. "
            f"Must be one of: {sorted(_VALID_CONCLUSIONS)}"
        )
        bd = self.bullpen_diagnosis
        assert 0.0 <= bd.bullpen_missing_score <= 1.0, (
            f"INVARIANT VIOLATION: bullpen_missing_score={bd.bullpen_missing_score} "
            f"must be in [0, 1]"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Functional Form Implementations
# ═══════════════════════════════════════════════════════════════════════════════
# sp_fip_delta = away_sp_fip - home_sp_fip
#   delta > 0 → away SP worse → home team has SP edge → positive adjustment
#   delta < 0 → home SP worse → away team has SP edge → negative adjustment
# ─────────────────────────────────────────────────────────────────────────────

def _clamp_prob(p: float) -> float:
    return max(_PROB_LO, min(_PROB_HI, p))


def _apply_tanh_current(base_prob: float, p0: dict, market_prob: float) -> float:
    """tanh(delta * 0.5) * 0.003 * 0.25  — Phase54 safe coefficient."""
    fip_adj = 0.0
    if p0.get("sp_fip_delta_available"):
        delta = float(p0.get("sp_fip_delta", 0.0))
        fip_adj = math.tanh(delta * 0.5) * 0.003 * 0.25
    return _clamp_prob(base_prob + fip_adj)


def _apply_tanh_stronger(base_prob: float, p0: dict, market_prob: float) -> float:
    """tanh(delta * 0.5) * 0.003 * 0.50  — 2× the safe coefficient."""
    fip_adj = 0.0
    if p0.get("sp_fip_delta_available"):
        delta = float(p0.get("sp_fip_delta", 0.0))
        fip_adj = math.tanh(delta * 0.5) * 0.003 * 0.50
    return _clamp_prob(base_prob + fip_adj)


def _apply_linear_capped(base_prob: float, p0: dict, market_prob: float) -> float:
    """delta * 0.0005 capped at ±0.008  — linear form."""
    fip_adj = 0.0
    if p0.get("sp_fip_delta_available"):
        delta = float(p0.get("sp_fip_delta", 0.0))
        fip_adj = max(-0.008, min(0.008, delta * 0.0005))
    return _clamp_prob(base_prob + fip_adj)


def _apply_sign_only(base_prob: float, p0: dict, market_prob: float) -> float:
    """±0.001 if |delta| > 1.0  — sign-only form."""
    fip_adj = 0.0
    if p0.get("sp_fip_delta_available"):
        delta = float(p0.get("sp_fip_delta", 0.0))
        if abs(delta) > 1.0:
            fip_adj = math.copysign(0.001, delta)
    return _clamp_prob(base_prob + fip_adj)


def _apply_bucketed_delta(base_prob: float, p0: dict, market_prob: float) -> float:
    """5-bucket SP advantage: large / small home or away edge, neutral."""
    fip_adj = 0.0
    if p0.get("sp_fip_delta_available"):
        delta = float(p0.get("sp_fip_delta", 0.0))
        if delta >= 1.5:           # large away SP edge → home advantage
            fip_adj = 0.003
        elif delta >= 0.5:         # small away SP edge → home advantage
            fip_adj = 0.001
        elif delta > -0.5:         # neutral
            fip_adj = 0.0
        elif delta > -1.5:         # small home SP edge → away advantage
            fip_adj = -0.001
        else:                      # large home SP edge → away advantage
            fip_adj = -0.003
    return _clamp_prob(base_prob + fip_adj)


def _apply_shrink_to_market(base_prob: float, p0: dict, market_prob: float) -> float:
    """tanh_current but shrink SP adjustment by 50% for high-confidence predictions."""
    fip_adj = 0.0
    if p0.get("sp_fip_delta_available"):
        delta = float(p0.get("sp_fip_delta", 0.0))
        fip_adj = math.tanh(delta * 0.5) * 0.003 * 0.25
        if abs(base_prob - 0.5) >= 0.15:   # high confidence → shrink
            fip_adj *= 0.5
    return _clamp_prob(base_prob + fip_adj)


# Form function registry
_FORM_FNS: dict[str, Callable[[float, dict, float], float]] = {
    FORM_TANH_CURRENT: _apply_tanh_current,
    FORM_TANH_STRONGER: _apply_tanh_stronger,
    FORM_LINEAR_CAPPED: _apply_linear_capped,
    FORM_SIGN_ONLY: _apply_sign_only,
    FORM_BUCKETED_DELTA: _apply_bucketed_delta,
    FORM_SHRINK_TO_MARKET: _apply_shrink_to_market,
}


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Segment Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _odds_bucket(market_prob: float) -> str:
    if market_prob >= 0.65:
        return "heavy_favorite"
    if market_prob >= 0.45:
        return "mid"
    return "underdog"


def _confidence_bucket(model_prob: float) -> str:
    dist = abs(model_prob - 0.5)
    if dist >= 0.10:
        return "high_confidence"
    if dist >= 0.05:
        return "mid_confidence"
    return "low_confidence"


def _disagree_bucket(model_prob: float, market_prob: float) -> str:
    gap = abs(model_prob - market_prob)
    if gap >= 0.10:
        return "high"
    if gap >= 0.05:
        return "medium"
    return "low"


def _month_key(game_date: str) -> str:
    """Extract 'month:YYYY-MM' from game_date string."""
    return f"month:{game_date[:7]}" if len(game_date) >= 7 else "month:unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Metrics Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_brier_skill_score(bs: float) -> Optional[float]:
    result = brier_skill_score(bs, _COIN_FLIP_BRIER)
    if result is None or math.isnan(result):
        return None
    return round(result, 6)


def _safe_ece(probs: list[float], labels: list[int]) -> float:
    result = expected_calibration_error(probs, labels)
    if isinstance(result, dict):
        return round(result["ece"], 6)
    return round(float(result), 6)


def _compute_segment_metrics(
    probs: list[float],
    labels: list[int],
    market_probs: list[float],
) -> dict[str, Any]:
    """Compute BSS and ECE for a segment. Returns None metrics if n < _MIN_SEGMENT_N."""
    n = len(probs)
    if n < _MIN_SEGMENT_N:
        return {
            "n": n,
            "model_bss": None,
            "model_ece": None,
            "market_bss": None,
            "market_ece": None,
        }

    bs_model = brier_score(probs, labels)
    bs_market = brier_score(market_probs, labels)

    return {
        "n": n,
        "model_bss": _safe_brier_skill_score(bs_model),
        "model_ece": _safe_ece(probs, labels),
        "market_bss": _safe_brier_skill_score(bs_market),
        "market_ece": _safe_ece(market_probs, labels),
    }


def _is_failure(m: dict) -> bool:
    """
    Is a segment failing?
    BSS < -0.01  OR  model_ece > market_ece + 0.01
    Returns False if n too small (metrics are None).
    """
    if m.get("model_bss") is None:
        return False
    if m["model_bss"] < _FAILURE_BSS_THRESHOLD:
        return True
    if (m.get("model_ece") is not None and
            m.get("market_ece") is not None and
            m["model_ece"] > m["market_ece"] + _ECE_DETERIORATION_MARGIN):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Form Evaluation
# ═══════════════════════════════════════════════════════════════════════════════

def _evaluate_form(
    form_name: str,
    form_fn: Callable[[float, dict, float], float],
    context_rows: list[dict],
) -> FunctionalFormResult:
    """
    Apply a functional form to all context rows and compute offline metrics.
    No files are written. Returns FunctionalFormResult with diagnostic_only=True.
    """
    # Accumulators
    adj_count = 0
    abs_adjustments: list[float] = []

    # Per-row outputs
    adj_probs: list[float] = []
    mkt_probs: list[float] = []
    labels: list[int] = []
    game_dates: list[str] = []

    for row in context_rows:
        base_p = float(row.get("model_home_prob", 0.5))
        mkt_p = float(row.get("market_home_prob_no_vig", 0.5))
        hw = int(row.get("home_win", 0))
        p0 = row.get("p0_features", {})
        gd = str(row.get("game_date", ""))

        adj_p = form_fn(base_p, p0, mkt_p)
        abs_adj = abs(adj_p - base_p)
        if abs_adj > 1e-9:
            adj_count += 1
            abs_adjustments.append(abs_adj)

        adj_probs.append(adj_p)
        mkt_probs.append(mkt_p)
        labels.append(hw)
        game_dates.append(gd)

    n = len(context_rows)
    adj_rate = adj_count / n if n > 0 else 0.0
    mean_abs = (sum(abs_adjustments) / len(abs_adjustments)) if abs_adjustments else 0.0
    max_abs = max(abs_adjustments) if abs_adjustments else 0.0

    # Build segment buckets
    seg_data: dict[str, tuple[list[float], list[int], list[float]]] = {}

    def _add(key: str, p: float, lbl: int, m: float) -> None:
        if key not in seg_data:
            seg_data[key] = ([], [], [])
        seg_data[key][0].append(p)
        seg_data[key][1].append(lbl)
        seg_data[key][2].append(m)

    for adj_p, mkt_p, lbl, gd in zip(adj_probs, mkt_probs, labels, game_dates):
        _add("overall", adj_p, lbl, mkt_p)
        _add(f"odds_bucket:{_odds_bucket(mkt_p)}", adj_p, lbl, mkt_p)
        _add(f"confidence:{_confidence_bucket(adj_p)}", adj_p, lbl, mkt_p)
        _add(f"disagreement:{_disagree_bucket(adj_p, mkt_p)}", adj_p, lbl, mkt_p)
        mk = _month_key(gd)
        if mk != "month:unknown":
            _add(mk, adj_p, lbl, mkt_p)

    # Compute metrics per segment
    segment_details: list[SegmentMetrics55] = []
    failure_count = 0

    # Ensure we always cover the key month segments even if empty
    key_months = ["month:2025-04", "month:2025-05", "month:2025-06", "month:2025-07"]
    for km in key_months:
        if km not in seg_data:
            seg_data[km] = ([], [], [])

    overall_bss: Optional[float] = None
    overall_ece: Optional[float] = None
    heavy_fav_ece: Optional[float] = None
    high_conf_bss: Optional[float] = None
    month_04_bss: Optional[float] = None

    for seg_key in sorted(seg_data.keys()):
        ps, ls, ms = seg_data[seg_key]
        m = _compute_segment_metrics(ps, ls, ms)
        is_fail = _is_failure(m) if seg_key != "overall" else False
        if is_fail:
            failure_count += 1

        segment_details.append(SegmentMetrics55(
            segment_key=seg_key,
            n=m["n"],
            model_bss=m["model_bss"],
            model_ece=m["model_ece"],
            market_bss=m["market_bss"],
            market_ece=m["market_ece"],
            is_failure=is_fail,
        ))

        if seg_key == "overall":
            overall_bss = m["model_bss"]
            overall_ece = m["model_ece"]
        elif seg_key == "odds_bucket:heavy_favorite":
            heavy_fav_ece = m["model_ece"]
        elif seg_key == "confidence:high_confidence":
            high_conf_bss = m["model_bss"]
        elif seg_key == "month:2025-04":
            month_04_bss = m["model_bss"]

    return FunctionalFormResult(
        form_name=form_name,
        adjusted_rows=adj_count,
        adjusted_rate=round(adj_rate, 4),
        mean_abs_adjustment=round(mean_abs, 8),
        max_abs_adjustment=round(max_abs, 8),
        overall_bss=overall_bss,
        overall_ece=overall_ece,
        heavy_fav_ece=heavy_fav_ece,
        high_conf_bss=high_conf_bss,
        month_2025_04_bss=month_04_bss,
        failure_segment_count=failure_count,
        segment_details=segment_details,
        diagnostic_only=True,
        candidate_patch_created=False,
        production_modified=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Bullpen Missing-Feature Diagnosis
# ═══════════════════════════════════════════════════════════════════════════════

def _score_bullpen_missing(
    phase54_failure_segs: list[str],
    form_results: list[FunctionalFormResult],
) -> BullpenDiagnosis:
    """
    Score the likelihood that missing bullpen features explain Phase54 failures.

    Scoring rubric:
      +0.25  heavy_favorite in failures (late-game leverage → bullpen)
      +0.25  high_confidence in failures (model over-confident, missing state)
      +0.20  month:2025-04 or month:2025-06 in failures (seasonal bullpen patterns)
      +0.15  disagreement:high in failures (market incorporates bullpen info)
      +0.15  no SP form can fix heavy_fav or high_conf failures
      = cap 1.0
    """
    score = 0.0
    evidence: list[str] = []

    hf_fail = any("heavy_favorite" in f for f in phase54_failure_segs)
    hc_fail = any("high_confidence" in f for f in phase54_failure_segs)
    month_fails = [f for f in phase54_failure_segs if f.startswith("month:")]
    dh_fail = any("disagreement:high" in f for f in phase54_failure_segs)

    if hf_fail:
        score += 0.25
        evidence.append(
            "heavy_favorite segment failing: late-inning lead protection driven by bullpen leverage"
        )

    if hc_fail:
        score += 0.25
        evidence.append(
            "high_confidence segment failing: model over-confident when missing bullpen fatigue state"
        )

    if any("2025-04" in f or "2025-06" in f for f in month_fails):
        score += 0.20
        evidence.append(
            f"Monthly failures ({[f for f in month_fails if '2025-04' in f or '2025-06' in f]}): "
            "seasonal bullpen usage patterns likely differ"
        )

    if dh_fail:
        score += 0.15
        evidence.append(
            "disagreement:high failures: market likely incorporating bullpen availability info model lacks"
        )

    # Check if no form can fix heavy_fav or high_conf (non-trivially)
    phase54_ref_fail_count = _PHASE54_FAILURE_COUNT
    hf_fixable = any(
        r.failure_segment_count < phase54_ref_fail_count - 1
        for r in form_results
    )
    hc_fixable = any(
        (r.high_conf_bss is not None and r.high_conf_bss >= 0.0
         and r.failure_segment_count < phase54_ref_fail_count - 1)
        for r in form_results
    )
    if not hf_fixable and not hc_fixable:
        score += 0.15
        evidence.append(
            "No SP functional form meaningfully reduces failure segments or fixes "
            "heavy_favorite/high_confidence: structural feature gap likely"
        )

    score = min(1.0, round(score, 4))

    # Failure pattern
    if hf_fail and hc_fail:
        pattern = "MIXED"
    elif hf_fail:
        pattern = "HEAVY_FAVORITE_CONCENTRATED"
    elif hc_fail:
        pattern = "HIGH_CONFIDENCE_CONCENTRATED"
    else:
        pattern = "DIFFUSE"

    return BullpenDiagnosis(
        bullpen_missing_score=score,
        evidence=evidence,
        recommended_features=list(RECOMMENDED_BULLPEN_FEATURES),
        failure_pattern=pattern,
        bullpen_feature_likely_missing=(score >= _BULLPEN_SCORE_THRESHOLD),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Decision Framework
# ═══════════════════════════════════════════════════════════════════════════════

def _decide_conclusion(
    form_results: list[FunctionalFormResult],
    bullpen_diag: BullpenDiagnosis,
    phase54_failure_count: int,
    tanh_current_result: FunctionalFormResult,
) -> tuple[str, str, list[str]]:
    """
    Returns (conclusion, rationale, recommended_phase56_tasks).

    Priority:
    1. SP_FUNCTIONAL_FORM_REDESIGN  — if any form clearly reduces failures
    2. BULLPEN_FEATURE_INVESTIGATION — if bullpen_missing_score >= 0.60 and overall improves
    3. COLLECT_MORE_DATA            — fallback
    """
    # Find form with fewest failures
    best = min(form_results, key=lambda r: r.failure_segment_count)

    # Baseline references from tanh_current
    ref_fail = phase54_failure_count
    ref_overall_bss = tanh_current_result.overall_bss or 0.0
    ref_hf_ece = tanh_current_result.heavy_fav_ece
    ref_hc_bss = tanh_current_result.high_conf_bss

    # Check if any form "clearly better": reduces failures AND doesn't degrade key segments
    def _is_clearly_better(r: FunctionalFormResult) -> bool:
        if r.failure_segment_count > ref_fail - _CLEAR_FAILURE_REDUCTION:
            return False   # not enough failure reduction
        # must not degrade overall BSS
        if (r.overall_bss is not None and
                r.overall_bss < ref_overall_bss - 0.0005):
            return False
        # must not degrade heavy_fav ECE by more than tolerance
        if (ref_hf_ece is not None and r.heavy_fav_ece is not None and
                r.heavy_fav_ece > ref_hf_ece + 0.001):
            return False
        # must not degrade high_conf BSS by more than tolerance
        if (ref_hc_bss is not None and r.high_conf_bss is not None and
                r.high_conf_bss < ref_hc_bss - 0.001):
            return False
        return True

    clearly_better_forms = [r for r in form_results if _is_clearly_better(r)]

    if clearly_better_forms:
        champion = min(clearly_better_forms, key=lambda r: r.failure_segment_count)
        phase56_tasks = [
            f"Phase 56A: Implement '{champion.form_name}' as redesigned SP functional form",
            "Phase 56B: Re-run Phase43/44/45 full stability audit with redesigned form",
            f"Verify heavy_favorite ECE does not worsen vs Phase54 ref={ref_hf_ece}",
            f"Verify high_confidence BSS >= Phase54 ref={ref_hc_bss}",
            "Run bootstrap significance test (n_bootstrap >= 1000) for redesigned form",
            "Write Phase56 candidate patch blueprint (NOT production patch)",
        ]
        rationale = (
            f"Form '{champion.form_name}' reduces failure segments from "
            f"{ref_fail} → {champion.failure_segment_count} "
            f"(Δ={ref_fail - champion.failure_segment_count:+d}) "
            f"without degrading overall_bss or heavy_fav_ece."
        )
        return SP_FUNCTIONAL_FORM_REDESIGN, rationale, phase56_tasks

    # Check bullpen missing
    any_overall_improve = any(
        r.overall_bss is not None and r.overall_bss > ref_overall_bss
        for r in form_results
    )

    if bullpen_diag.bullpen_feature_likely_missing and any_overall_improve:
        phase56_tasks = [
            f"Phase 56A: Investigate and prototype: {', '.join(RECOMMENDED_BULLPEN_FEATURES)}",
            "Phase 56B: Design bullpen fatigue proxy from MLB historical relief pitcher usage data",
            "Phase 56C: Build phase56_bullpen_feature_builder.py",
            "Phase 56D: Backfill bullpen features for full 2025 MLB season (2,025 games)",
            "Phase 56E: Run Phase43/44/45 audit with bullpen features injected",
            "Phase 56F: Verify heavy_favorite ECE improves with bullpen features",
            "Phase 56G: If significant → write Phase57 candidate patch blueprint",
        ]
        rationale = (
            f"bullpen_missing_score={bullpen_diag.bullpen_missing_score:.4f} >= {_BULLPEN_SCORE_THRESHOLD}; "
            f"failure_pattern={bullpen_diag.failure_pattern}; "
            f"no SP form resolves heavy_favorite/high_confidence failures "
            f"but overall BSS can improve. Bullpen features recommended."
        )
        return BULLPEN_FEATURE_INVESTIGATION, rationale, phase56_tasks

    # Fallback: collect more data
    phase56_tasks = [
        "Continue paper-only tracking for 500+ additional games",
        "Re-run Phase43 bootstrap with larger n to assess significance",
        "Monitor failure segment trend across next 2 months",
        "Re-evaluate SP functional form after additional data collection",
        "Consider data enrichment: collect actual pitcher usage logs for FIP validation",
    ]
    rationale = (
        f"No SP form clearly reduces failures; "
        f"bullpen_missing_score={bullpen_diag.bullpen_missing_score:.4f} < {_BULLPEN_SCORE_THRESHOLD}. "
        f"Signal is too weak to distinguish SP form error from bullpen missing feature. "
        f"Collect more data."
    )
    return COLLECT_MORE_DATA, rationale, phase56_tasks


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  I/O Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _load_raw_rows(path: Path) -> list[dict]:
    """Load a JSONL file as a list of raw dicts."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_phase54_failure_segs(phase54_report_path: Optional[Path]) -> list[str]:
    """
    Load Phase54 failure segment list from the Phase54 JSON report.
    Falls back to hardcoded known values if report is unavailable.
    """
    if phase54_report_path and phase54_report_path.exists():
        with open(phase54_report_path, encoding="utf-8") as f:
            report = json.load(f)
        segs = report.get("phase45_summary", {}).get("failure_segments", [])
        if segs:
            logger.info("Phase54 failure segments loaded from report: %s", segs)
            return segs

    # Fallback: use known Phase54 results (from real run 2026-05-05)
    logger.warning(
        "Phase54 report not found or empty; using hardcoded Phase54 failure segments"
    )
    return [
        "odds_bucket:heavy_favorite",
        "odds_bucket:underdog",
        "confidence:high_confidence",
        "confidence:low_confidence",
        "disagreement:high",
        "disagreement:low",
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  Audit Hash
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_audit_hash(
    n_rows: int,
    bullpen_score: float,
    conclusion: str,
    run_ts: str,
) -> str:
    parts = "|".join([
        str(n_rows),
        f"{bullpen_score:.6f}",
        conclusion,
        run_ts,
    ])
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase55_diagnosis(
    context_path: Path,
    baseline_path: Optional[Path] = None,
    phase54_path: Optional[Path] = None,
    phase54_report_path: Optional[Path] = None,
) -> Phase55DiagnosisResult:
    """
    Run Phase 55 SP vs Bullpen diagnosis.

    Steps:
    1. Load Phase52 context rows (with p0_features)
    2. Load Phase54 failure segments (from JSON report or fallback)
    3. Evaluate all 6 SP functional forms
    4. Score bullpen missing features
    5. Decide conclusion
    6. Build and return Phase55DiagnosisResult

    Hard rules enforced:
      - No production files written
      - candidate_patch_created = False
      - production_modified = False
      - diagnostic_only = True
      - conclusion in _VALID_CONCLUSIONS
    """
    run_ts = datetime.now(timezone.utc).isoformat()
    logger.info("Phase 55 starting — SP vs Bullpen Functional Form Diagnosis")

    # Step 1: Load context rows
    logger.info("Step 1: Loading Phase52 context rows from %s", context_path)
    context_rows = _load_raw_rows(context_path)
    n = len(context_rows)
    logger.info("Loaded %d context rows", n)

    # Step 2: Load Phase54 failure segments
    logger.info("Step 2: Loading Phase54 failure segments")
    phase54_failure_segs = _load_phase54_failure_segs(phase54_report_path)
    logger.info("Phase54 failure segments (%d): %s", len(phase54_failure_segs), phase54_failure_segs)

    # Step 3: Evaluate each functional form
    logger.info("Step 3: Evaluating %d functional forms on %d rows", len(ALL_FORM_NAMES), n)
    form_results: list[FunctionalFormResult] = []
    tanh_current_result: Optional[FunctionalFormResult] = None

    for form_name in ALL_FORM_NAMES:
        fn = _FORM_FNS[form_name]
        logger.info("  Evaluating: %s", form_name)
        fr = _evaluate_form(form_name, fn, context_rows)
        form_results.append(fr)
        if form_name == FORM_TANH_CURRENT:
            tanh_current_result = fr
        logger.info(
            "    %s: adj_rows=%d (%.1f%%), failure_count=%d, "
            "overall_bss=%s, heavy_fav_ece=%s, high_conf_bss=%s",
            form_name,
            fr.adjusted_rows,
            fr.adjusted_rate * 100,
            fr.failure_segment_count,
            f"{fr.overall_bss:.6f}" if fr.overall_bss is not None else "N/A",
            f"{fr.heavy_fav_ece:.6f}" if fr.heavy_fav_ece is not None else "N/A",
            f"{fr.high_conf_bss:.6f}" if fr.high_conf_bss is not None else "N/A",
        )

    if tanh_current_result is None:
        tanh_current_result = form_results[0]

    # Step 4: Bullpen missing-feature diagnosis
    logger.info("Step 4: Bullpen missing-feature diagnosis")
    bullpen_diag = _score_bullpen_missing(phase54_failure_segs, form_results)
    logger.info(
        "  bullpen_missing_score=%.4f, likely_missing=%s, pattern=%s",
        bullpen_diag.bullpen_missing_score,
        bullpen_diag.bullpen_feature_likely_missing,
        bullpen_diag.failure_pattern,
    )

    # Step 5: Decision framework
    logger.info("Step 5: Decision framework")
    conclusion, rationale, phase56_tasks = _decide_conclusion(
        form_results, bullpen_diag, _PHASE54_FAILURE_COUNT, tanh_current_result
    )
    logger.info("  conclusion=%s", conclusion)

    # Best form by failure count
    best_form = min(form_results, key=lambda r: r.failure_segment_count)

    # Audit hash
    audit_hash = _compute_audit_hash(n, bullpen_diag.bullpen_missing_score, conclusion, run_ts)
    logger.info(
        "Phase 55 complete — conclusion=%s | bullpen_score=%.4f | "
        "best_form=%s (failures=%d) | audit_hash=%s",
        conclusion,
        bullpen_diag.bullpen_missing_score,
        best_form.form_name,
        best_form.failure_segment_count,
        audit_hash,
    )

    return Phase55DiagnosisResult(
        phase55_version=PHASE55_VERSION,
        run_timestamp=run_ts,
        audit_hash=audit_hash,
        phase54_failure_count=_PHASE54_FAILURE_COUNT,
        phase54_failure_segments=phase54_failure_segs,
        functional_form_results=form_results,
        best_form_name=best_form.form_name,
        best_form_failure_count=best_form.failure_segment_count,
        bullpen_diagnosis=bullpen_diag,
        conclusion=conclusion,
        conclusion_rationale=rationale,
        recommended_phase56_tasks=phase56_tasks,
        candidate_patch_created=False,
        production_modified=False,
        diagnostic_only=True,
    )
