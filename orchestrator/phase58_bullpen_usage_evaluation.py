"""
orchestrator/phase58_bullpen_usage_evaluation.py
=================================================
Phase 58 — Bullpen Usage Evaluation Orchestrator

功能：
  比較 baseline JSONL vs Phase58 注入後 JSONL 的統計指標，
  決定 gate recommendation。

Hard Rules (NEVER violate):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - DIAGNOSTIC_ONLY = True
  - gate 只能為以下 4 個之一：
      BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY
      BULLPEN_FEATURE_NOT_EFFECTIVE
      DATA_GAP_REMAINS
      COLLECT_MORE_DATA
  - 所有指標計算委派 wbc_backend.evaluation.metrics (SSOT)

Gate 邏輯：
  1. bullpen_feature_available_rate < 0.80 → DATA_GAP_REMAINS
  2. rate >= 0.80 AND heavy_fav ECE 改善 AND high_conf BSS 未惡化
     AND overall BSS 未惡化 AND failure_count 下降 → BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY
  3. rate >= 0.80 但無改善 → BULLPEN_FEATURE_NOT_EFFECTIVE
  4. 資料不足以判斷（n < 30 或 mixed） → COLLECT_MORE_DATA
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from wbc_backend.evaluation.metrics import (
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    log_loss_score,
)

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
DIAGNOSTIC_ONLY: bool = True
PHASE58_VERSION: str = "phase58_bullpen_usage_evaluation_v1"

# ─── Gate labels (ONLY these 4 are valid) ────────────────────────────────────
BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY: str = "BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY"
BULLPEN_FEATURE_NOT_EFFECTIVE: str = "BULLPEN_FEATURE_NOT_EFFECTIVE"
DATA_GAP_REMAINS: str = "DATA_GAP_REMAINS"
COLLECT_MORE_DATA: str = "COLLECT_MORE_DATA"

_VALID_GATES: frozenset[str] = frozenset({
    BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
    BULLPEN_FEATURE_NOT_EFFECTIVE,
    DATA_GAP_REMAINS,
    COLLECT_MORE_DATA,
})

# ─── Segment classification thresholds ───────────────────────────────────────
_MIN_SEGMENT_N: int = 30
_HEAVY_FAV_THRESHOLD: float = 0.65
_HIGH_CONF_THRESHOLD: float = 0.60
_MID_LO: float = 0.45
_MID_HI: float = 0.65
_BULLPEN_AVAIL_MIN_RATE: float = 0.80


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetricsSnapshot58:
    """Global-level metrics for one JSONL source."""
    source: str  # "baseline" | "phase58_injected" | "market"
    n: int = 0
    brier: float = 0.0
    bss_vs_market: Optional[float] = None
    ece: float = 0.0
    log_loss: float = 0.0


@dataclass
class SegmentMetrics58:
    """Per-segment metrics."""
    segment_key: str
    segment_type: str
    segment_label: str
    n: int = 0
    baseline_bss: float = 0.0
    phase58_bss: float = 0.0
    delta_bss: float = 0.0
    baseline_ece: float = 0.0
    phase58_ece: float = 0.0
    delta_ece: float = 0.0
    is_failure_segment: bool = False
    improvement_label: str = "NOT_EVALUABLE"


@dataclass
class BullpenAvailabilitySummary58:
    """Bullpen feature availability summary for Phase58."""
    total_rows: int = 0
    available_count: int = 0
    availability_rate: float = 0.0
    workload_available_count: int = 0
    workload_available_rate: float = 0.0
    leverage_available_count: int = 0
    leverage_available_rate: float = 0.0
    performance_proxy_available_count: int = 0
    performance_proxy_available_rate: float = 0.0
    fallback_count: int = 0
    model_affecting_count: int = 0
    model_affecting_rate: float = 0.0
    avg_abs_adjustment: float = 0.0
    max_abs_adjustment: float = 0.0
    source_mode: str = "schedule_proxy_fallback"


@dataclass
class Phase58EvaluationResult:
    """
    Full Phase 58 evaluation snapshot.

    Hard invariants:
      - candidate_patch_created is always False
      - production_modified is always False
      - diagnostic_only is always True
      - gate is always in _VALID_GATES
    """
    run_id: str = ""
    generated_at: str = ""
    baseline_path: str = ""
    phase58_injected_path: str = ""
    phase58_version: str = PHASE58_VERSION

    # Metrics
    baseline_metrics: MetricsSnapshot58 = field(
        default_factory=lambda: MetricsSnapshot58("baseline")
    )
    phase58_metrics: MetricsSnapshot58 = field(
        default_factory=lambda: MetricsSnapshot58("phase58_injected")
    )

    # Global deltas (positive BSS delta = improvement)
    delta_brier: float = 0.0           # phase58 - baseline (negative = better)
    delta_bss: float = 0.0             # phase58 - baseline (positive = better)
    delta_ece: float = 0.0             # phase58 - baseline (negative = better)

    # Segment comparison
    segment_metrics: list[SegmentMetrics58] = field(default_factory=list)
    failure_count_baseline: int = 0
    failure_count_phase58: int = 0
    failure_segment_count_delta: int = 0

    # Bullpen availability
    bullpen_availability: BullpenAvailabilitySummary58 = field(
        default_factory=BullpenAvailabilitySummary58
    )

    # Gate
    gate_recommendation: str = DATA_GAP_REMAINS
    gate_rationale: str = ""

    # Hard-rule flags
    candidate_patch_created: bool = False
    production_modified: bool = False
    diagnostic_only: bool = True

    # Audit
    audit_hash: str = ""

    def __post_init__(self) -> None:
        assert not self.candidate_patch_created, "INVARIANT VIOLATION"
        assert not self.production_modified, "INVARIANT VIOLATION"
        assert self.diagnostic_only, "INVARIANT VIOLATION"
        assert self.gate_recommendation in _VALID_GATES, (
            f"GATE VIOLATION: {self.gate_recommendation} not in valid gates"
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Data loading & classification
# ═══════════════════════════════════════════════════════════════════════════════

def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    logger.info("JSONL 載入：%d 筆 ← %s", len(rows), path)
    return rows


def _classify_odds_bucket(market_home_prob: float) -> str:
    if market_home_prob > _HEAVY_FAV_THRESHOLD or market_home_prob < (1 - _HEAVY_FAV_THRESHOLD):
        return "heavy_favorite"
    if _MID_LO <= market_home_prob <= _MID_HI:
        return "mid"
    return "light_favorite"


def _classify_confidence(model_prob: float) -> str:
    if model_prob > _HIGH_CONF_THRESHOLD or model_prob < (1 - _HIGH_CONF_THRESHOLD):
        return "high_confidence"
    return "low_confidence"


def _classify_disagreement(model_prob: float, market_prob: float) -> str:
    gap = abs(model_prob - market_prob)
    return "high" if gap > 0.10 else "low"


def _get_segments(row: dict, model_prob: float) -> list[tuple[str, str, str]]:
    segments: list[tuple[str, str, str]] = []
    market_prob = float(row.get("market_home_prob_no_vig", 0.5) or 0.5)
    game_date = str(row.get("game_date", ""))

    if len(game_date) >= 7:
        month = game_date[:7]
        segments.append(("month", month, f"month:{month}"))

    bucket = _classify_odds_bucket(market_prob)
    segments.append(("odds_bucket", bucket, f"odds_bucket:{bucket}"))

    conf = _classify_confidence(model_prob)
    segments.append(("confidence", conf, f"confidence:{conf}"))

    disagree = _classify_disagreement(model_prob, market_prob)
    segments.append(("disagreement", disagree, f"disagreement:{disagree}"))

    return segments


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Metrics computation
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_global_metrics(
    rows: list[dict],
    prob_field: str,
    source: str,
) -> MetricsSnapshot58:
    probs: list[float] = []
    labels: list[float] = []
    market_probs: list[float] = []

    for row in rows:
        prob = row.get(prob_field)
        label = row.get("home_win")
        market = row.get("market_home_prob_no_vig")
        if prob is None or label is None or market is None:
            continue
        try:
            prob_f = float(prob)
            label_f = float(label)
            market_f = float(market)
        except (ValueError, TypeError):
            continue
        if not (0.0 <= prob_f <= 1.0) or label_f not in (0.0, 1.0):
            continue
        probs.append(prob_f)
        labels.append(label_f)
        market_probs.append(market_f)

    if len(probs) < 10:
        return MetricsSnapshot58(source=source, n=len(probs))

    model_brier = brier_score(probs, labels)
    market_brier = brier_score(market_probs, labels)
    bss = brier_skill_score(model_brier, market_brier)
    ece_result = expected_calibration_error(probs, labels)
    ll = log_loss_score(probs, labels)

    return MetricsSnapshot58(
        source=source,
        n=len(probs),
        brier=round(model_brier, 6),
        bss_vs_market=round(bss, 6) if bss is not None else None,
        ece=round(ece_result["ece"], 6),
        log_loss=round(ll, 6),
    )


def _compute_segment_metrics(
    baseline_rows: list[dict],
    phase58_rows: list[dict],
) -> list[SegmentMetrics58]:
    """Compute per-segment BSS and ECE for baseline vs phase58."""
    # Index phase58 rows by game_id
    p58_by_gid: dict[str, dict] = {}
    for row in phase58_rows:
        gid = row.get("game_id", "")
        if gid:
            p58_by_gid[gid] = row

    # Collect data per segment
    # seg_key → {base_probs, base_labels, p58_probs, p58_labels, mkt_probs}
    seg_data: dict[str, dict] = {}

    for base_row in baseline_rows:
        gid = base_row.get("game_id", "")
        base_prob_raw = base_row.get("model_home_prob")
        label_raw = base_row.get("home_win")
        market_raw = base_row.get("market_home_prob_no_vig")

        if base_prob_raw is None or label_raw is None or market_raw is None:
            continue
        try:
            base_p = float(base_prob_raw)
            lbl = float(label_raw)
            mkt = float(market_raw)
        except (ValueError, TypeError):
            continue
        if not (0.0 <= base_p <= 1.0) or lbl not in (0.0, 1.0):
            continue

        # phase58 prob
        p58_row = p58_by_gid.get(gid)
        p58_p: Optional[float] = None
        if p58_row is not None:
            p58_prob_raw = p58_row.get("phase58_model_home_prob") or p58_row.get("model_home_prob")
            try:
                candidate = float(p58_prob_raw)
                if 0.0 <= candidate <= 1.0:
                    p58_p = candidate
            except (ValueError, TypeError):
                pass

        for seg_type, seg_label, seg_key in _get_segments(base_row, base_p):
            if seg_key not in seg_data:
                seg_data[seg_key] = {
                    "seg_type": seg_type,
                    "seg_label": seg_label,
                    "base_probs": [],
                    "labels": [],
                    "p58_probs": [],
                    "mkt_probs": [],
                }
            seg_data[seg_key]["base_probs"].append(base_p)
            seg_data[seg_key]["labels"].append(lbl)
            seg_data[seg_key]["mkt_probs"].append(mkt)
            if p58_p is not None:
                seg_data[seg_key]["p58_probs"].append(p58_p)

    results: list[SegmentMetrics58] = []

    for seg_key, d in seg_data.items():
        n = len(d["base_probs"])
        if n < _MIN_SEGMENT_N:
            continue

        base_brier = brier_score(d["base_probs"], d["labels"])
        mkt_brier = brier_score(d["mkt_probs"], d["labels"])
        base_bss_val = brier_skill_score(base_brier, mkt_brier) or 0.0
        base_ece_val = expected_calibration_error(d["base_probs"], d["labels"])["ece"]

        seg = SegmentMetrics58(
            segment_key=seg_key,
            segment_type=d["seg_type"],
            segment_label=d["seg_label"],
            n=n,
            baseline_bss=round(base_bss_val, 6),
            baseline_ece=round(base_ece_val, 6),
        )

        p58_n = len(d["p58_probs"])
        if p58_n >= _MIN_SEGMENT_N:
            p58_brier = brier_score(d["p58_probs"], d["labels"][:p58_n])
            mkt_brier_p58 = brier_score(d["mkt_probs"][:p58_n], d["labels"][:p58_n])
            p58_bss_val = brier_skill_score(p58_brier, mkt_brier_p58) or 0.0
            p58_ece_val = expected_calibration_error(d["p58_probs"], d["labels"][:p58_n])["ece"]
            delta_bss = round(p58_bss_val - base_bss_val, 6)
            delta_ece = round(p58_ece_val - base_ece_val, 6)
            seg.phase58_bss = round(p58_bss_val, 6)
            seg.phase58_ece = round(p58_ece_val, 6)
            seg.delta_bss = delta_bss
            seg.delta_ece = delta_ece
            if delta_bss > 0.002 or delta_ece < -0.002:
                seg.improvement_label = "IMPROVED"
            elif delta_bss < -0.005 or delta_ece > 0.005:
                seg.improvement_label = "REGRESSED"
            else:
                seg.improvement_label = "NEUTRAL"
        else:
            seg.improvement_label = "NOT_EVALUABLE"

        results.append(seg)

    return results


def _count_failure_segments(
    segment_metrics: list[SegmentMetrics58],
    threshold_bss: float = -0.01,
) -> int:
    """Count segments with BSS below threshold (i.e., failing segments)."""
    return sum(1 for s in segment_metrics if s.baseline_bss < threshold_bss)


def _count_phase58_failing_segments(
    segment_metrics: list[SegmentMetrics58],
    threshold_bss: float = -0.01,
) -> int:
    return sum(1 for s in segment_metrics if s.phase58_bss < threshold_bss and s.n >= _MIN_SEGMENT_N)


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Availability analysis
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_availability(rows: list[dict]) -> BullpenAvailabilitySummary58:
    total = len(rows)
    available_count = sum(1 for r in rows if r.get("phase58_bullpen_feature_available", False))
    workload_count = sum(1 for r in rows if r.get("workload_available", False))
    leverage_count = sum(1 for r in rows if r.get("leverage_available", False))
    perf_count = sum(1 for r in rows if r.get("performance_proxy_available", False))
    fallback_count = total - available_count

    # Count rows with non-zero adjustment
    adjustments = []
    for r in rows:
        adj = r.get("phase58_bullpen_adjustment", 0.0)
        if adj is not None:
            adjustments.append(abs(float(adj)))

    model_affecting_count = sum(1 for a in adjustments if a > 1e-9)
    avg_abs = sum(adjustments) / len(adjustments) if adjustments else 0.0
    max_abs = max(adjustments) if adjustments else 0.0

    return BullpenAvailabilitySummary58(
        total_rows=total,
        available_count=available_count,
        availability_rate=round(available_count / max(1, total), 4),
        workload_available_count=workload_count,
        workload_available_rate=round(workload_count / max(1, total), 4),
        leverage_available_count=leverage_count,
        leverage_available_rate=round(leverage_count / max(1, total), 4),
        performance_proxy_available_count=perf_count,
        performance_proxy_available_rate=round(perf_count / max(1, total), 4),
        fallback_count=fallback_count,
        model_affecting_count=model_affecting_count,
        model_affecting_rate=round(model_affecting_count / max(1, total), 4),
        avg_abs_adjustment=round(avg_abs, 6),
        max_abs_adjustment=round(max_abs, 6),
        source_mode="schedule_proxy_fallback",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Gate logic
# ═══════════════════════════════════════════════════════════════════════════════

def _determine_gate(
    availability: BullpenAvailabilitySummary58,
    baseline_metrics: MetricsSnapshot58,
    phase58_metrics: MetricsSnapshot58,
    segment_metrics: list[SegmentMetrics58],
    failure_count_baseline: int,
    failure_count_phase58: int,
) -> tuple[str, str]:
    """
    Determine gate recommendation.

    Returns:
        (gate, rationale)
    """
    # Rule 1: availability gate
    if availability.availability_rate < _BULLPEN_AVAIL_MIN_RATE:
        return (
            DATA_GAP_REMAINS,
            f"bullpen_feature_available_rate={availability.availability_rate:.1%} < 80%. "
            "Insufficient coverage for evaluation."
        )

    # Minimum sample check
    if baseline_metrics.n < 100 or phase58_metrics.n < 100:
        return (
            COLLECT_MORE_DATA,
            f"Insufficient rows: baseline n={baseline_metrics.n}, phase58 n={phase58_metrics.n}. "
            "Need >= 100 for meaningful evaluation."
        )

    # Extract segment-level metrics for critical segments
    heavy_fav_segs = [s for s in segment_metrics if "heavy_favorite" in s.segment_key]
    high_conf_segs = [s for s in segment_metrics if "high_confidence" in s.segment_key]

    heavy_fav_ece_delta = (
        sum(s.delta_ece for s in heavy_fav_segs) / len(heavy_fav_segs)
        if heavy_fav_segs else 0.0
    )
    high_conf_bss_delta = (
        sum(s.delta_bss for s in high_conf_segs) / len(high_conf_segs)
        if high_conf_segs else 0.0
    )

    overall_bss_delta = 0.0
    if baseline_metrics.bss_vs_market is not None and phase58_metrics.bss_vs_market is not None:
        overall_bss_delta = phase58_metrics.bss_vs_market - baseline_metrics.bss_vs_market

    failure_delta = failure_count_phase58 - failure_count_baseline  # negative = improvement

    # Rule 2: effective
    ece_improved = heavy_fav_ece_delta < -0.002   # lower ECE = better
    bss_not_worsened = overall_bss_delta >= -0.002
    high_conf_bss_ok = high_conf_bss_delta >= -0.005
    failure_improved = failure_delta <= 0

    if (
        ece_improved
        and bss_not_worsened
        and high_conf_bss_ok
        and failure_improved
    ):
        return (
            BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
            f"heavy_fav ECE delta={heavy_fav_ece_delta:.4f} (improved), "
            f"overall BSS delta={overall_bss_delta:.4f} (not worsened), "
            f"failure_delta={failure_delta} (improved or neutral)."
        )

    # Rule 3: insufficient mixed signals
    if not ece_improved and not (overall_bss_delta > 0.005):
        # Clear no-improvement
        return (
            BULLPEN_FEATURE_NOT_EFFECTIVE,
            f"No meaningful improvement detected. "
            f"heavy_fav ECE delta={heavy_fav_ece_delta:.4f}, "
            f"overall BSS delta={overall_bss_delta:.4f}. "
            "Proxy workload data insufficient to produce reliable signal."
        )

    # Rule 4: mixed results
    return (
        COLLECT_MORE_DATA,
        f"Mixed results. ECE delta={heavy_fav_ece_delta:.4f}, "
        f"BSS delta={overall_bss_delta:.4f}, "
        f"failure_delta={failure_delta}. "
        "Collect real boxscore data for stronger evaluation."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Main evaluation function
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase58_evaluation(
    baseline_path: Path,
    phase58_injected_path: Path,
) -> Phase58EvaluationResult:
    """
    執行 Phase58 bullpen usage evaluation。

    Args:
        baseline_path: 原始 baseline JSONL（model_home_prob 欄位）
        phase58_injected_path: Phase58 注入後 JSONL（phase58_model_home_prob 欄位）

    Returns:
        Phase58EvaluationResult
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED

    run_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc).isoformat()

    logger.info("Phase58 evaluation 開始 (run_id=%s)", run_id)
    logger.info("Baseline: %s", baseline_path)
    logger.info("Phase58: %s", phase58_injected_path)

    baseline_rows = _load_jsonl(baseline_path)
    phase58_rows = _load_jsonl(phase58_injected_path)

    # ── Global metrics ────────────────────────────────────────────────────────
    baseline_metrics = _compute_global_metrics(
        baseline_rows, "model_home_prob", "baseline"
    )
    # Phase58 injected: prefer phase58_model_home_prob, fallback to model_home_prob
    for row in phase58_rows:
        if "phase58_model_home_prob" not in row or row["phase58_model_home_prob"] is None:
            row["_eval_prob"] = row.get("model_home_prob", 0.5)
        else:
            row["_eval_prob"] = row["phase58_model_home_prob"]

    phase58_metrics = _compute_global_metrics(
        phase58_rows, "_eval_prob", "phase58_injected"
    )

    # ── Availability analysis ─────────────────────────────────────────────────
    availability = _analyze_availability(phase58_rows)

    # ── Segment metrics ───────────────────────────────────────────────────────
    # Add _eval_prob to phase58 rows for segment metrics
    segment_metrics = _compute_segment_metrics(baseline_rows, phase58_rows)

    # Failure segment counts
    failure_count_baseline = _count_failure_segments(segment_metrics)
    failure_count_phase58 = _count_phase58_failing_segments(segment_metrics)
    failure_segment_count_delta = failure_count_phase58 - failure_count_baseline

    # ── Gate ──────────────────────────────────────────────────────────────────
    gate, rationale = _determine_gate(
        availability,
        baseline_metrics,
        phase58_metrics,
        segment_metrics,
        failure_count_baseline,
        failure_count_phase58,
    )
    logger.info("Gate: %s — %s", gate, rationale)

    # ── Deltas ────────────────────────────────────────────────────────────────
    delta_brier = round(phase58_metrics.brier - baseline_metrics.brier, 6)
    delta_bss = 0.0
    if (baseline_metrics.bss_vs_market is not None
            and phase58_metrics.bss_vs_market is not None):
        delta_bss = round(
            phase58_metrics.bss_vs_market - baseline_metrics.bss_vs_market, 6
        )
    delta_ece = round(phase58_metrics.ece - baseline_metrics.ece, 6)

    # ── Audit hash ────────────────────────────────────────────────────────────
    hash_input = "|".join([
        run_id,
        str(baseline_metrics.n),
        str(phase58_metrics.n),
        gate,
        str(availability.availability_rate),
    ])
    audit_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    result = Phase58EvaluationResult(
        run_id=run_id,
        generated_at=generated_at,
        baseline_path=str(baseline_path),
        phase58_injected_path=str(phase58_injected_path),
        baseline_metrics=baseline_metrics,
        phase58_metrics=phase58_metrics,
        delta_brier=delta_brier,
        delta_bss=delta_bss,
        delta_ece=delta_ece,
        segment_metrics=segment_metrics,
        failure_count_baseline=failure_count_baseline,
        failure_count_phase58=failure_count_phase58,
        failure_segment_count_delta=failure_segment_count_delta,
        bullpen_availability=availability,
        gate_recommendation=gate,
        gate_rationale=rationale,
        candidate_patch_created=False,
        production_modified=False,
        diagnostic_only=True,
        audit_hash=audit_hash,
    )

    return result
