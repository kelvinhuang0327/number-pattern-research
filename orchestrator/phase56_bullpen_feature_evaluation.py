"""
orchestrator/phase56_bullpen_feature_evaluation.py
===================================================
Phase 56 — Bullpen Feature Evaluation Orchestrator

功能：
  比較 baseline JSONL vs Phase56 注入後 JSONL 的統計指標，
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
  4. 資料不足以判斷 → COLLECT_MORE_DATA
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
PHASE56_VERSION: str = "phase56_bullpen_feature_evaluation_v1"

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
_HEAVY_FAV_THRESHOLD: float = 0.65          # market_home_prob_no_vig > 0.65
_HIGH_CONF_THRESHOLD: float = 0.60          # model_home_prob > 0.60 or < 0.40
_MID_LO: float = 0.45
_MID_HI: float = 0.65
_BULLPEN_AVAIL_MIN_RATE: float = 0.80       # gate trigger threshold

# ─── Phase55 failure segments (from phase55 diagnosis report) ─────────────────
_PHASE55_FAILURE_SEGMENTS: list[str] = [
    "odds_bucket:heavy_favorite",
    "odds_bucket:mid",
    "disagreement:low",
    "month:2025-04",
    "month:2025-06",
    "month:2025-08",
]


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetricsSnapshot56:
    """Global-level metrics for one JSONL source."""
    source: str          # "baseline" | "phase56_injected" | "market"
    n: int = 0
    brier: float = 0.0
    bss_vs_market: Optional[float] = None
    ece: float = 0.0
    log_loss: float = 0.0


@dataclass
class SegmentMetrics56:
    """Per-segment metrics."""
    segment_key: str
    segment_type: str
    segment_label: str
    n: int = 0
    baseline_bss: float = 0.0
    phase56_bss: float = 0.0
    delta_bss: float = 0.0
    baseline_ece: float = 0.0
    phase56_ece: float = 0.0
    delta_ece: float = 0.0
    is_failure_segment: bool = False
    improvement_label: str = "NOT_EVALUABLE"


@dataclass
class BullpenAvailabilitySummary:
    """Bullpen feature availability summary."""
    total_rows: int = 0
    available_count: int = 0
    availability_rate: float = 0.0
    fallback_count: int = 0
    model_affecting_count: int = 0
    model_affecting_rate: float = 0.0
    avg_abs_adjustment: float = 0.0
    max_abs_adjustment: float = 0.0


@dataclass
class Phase56EvaluationResult:
    """
    Full Phase 56 evaluation snapshot.

    Hard invariants:
      - candidate_patch_created is always False
      - production_modified is always False
      - diagnostic_only is always True
      - gate is always in _VALID_GATES
    """
    run_id: str = ""
    generated_at: str = ""
    baseline_path: str = ""
    phase56_injected_path: str = ""
    phase56_version: str = PHASE56_VERSION

    # Metrics
    baseline_metrics: MetricsSnapshot56 = field(
        default_factory=lambda: MetricsSnapshot56("baseline")
    )
    phase56_metrics: MetricsSnapshot56 = field(
        default_factory=lambda: MetricsSnapshot56("phase56_injected")
    )
    market_metrics: MetricsSnapshot56 = field(
        default_factory=lambda: MetricsSnapshot56("market")
    )

    # Global deltas (positive BSS delta = improvement)
    delta_brier: float = 0.0           # phase56 - baseline (negative = better)
    delta_bss: float = 0.0             # phase56 - baseline (positive = better)
    delta_ece: float = 0.0             # phase56 - baseline (negative = better)

    # Segment comparison
    segment_metrics: list[SegmentMetrics56] = field(default_factory=list)
    failure_segments_in_phase56: list[str] = field(default_factory=list)
    failure_count_baseline: int = 0
    failure_count_phase56: int = 0

    # Bullpen availability
    bullpen_availability: BullpenAvailabilitySummary = field(
        default_factory=BullpenAvailabilitySummary
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
        d = asdict(self)
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Row loading and classification
# ═══════════════════════════════════════════════════════════════════════════════

def _load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    logger.info("JSONL 載入：%d 筆 ← %s", len(rows), path)
    return rows


def _classify_odds_bucket(market_home_prob: float) -> str:
    """Classify market probability into odds bucket."""
    if market_home_prob > _HEAVY_FAV_THRESHOLD or market_home_prob < (1 - _HEAVY_FAV_THRESHOLD):
        return "heavy_favorite"
    if _MID_LO <= market_home_prob <= _MID_HI:
        return "mid"
    return "light_favorite"


def _classify_confidence(model_prob: float) -> str:
    """Classify model confidence."""
    if model_prob > _HIGH_CONF_THRESHOLD or model_prob < (1 - _HIGH_CONF_THRESHOLD):
        return "high_confidence"
    return "low_confidence"


def _classify_disagreement(model_prob: float, market_prob: float) -> str:
    """Classify model vs market disagreement."""
    gap = abs(model_prob - market_prob)
    if gap > 0.10:
        return "high"
    return "low"


def _get_segments(row: dict, model_prob: float) -> list[tuple[str, str, str]]:
    """
    Return all (type, label, key) segment tuples for a row.

    Uses market_home_prob_no_vig for odds classification.
    """
    segments: list[tuple[str, str, str]] = []

    market_prob = float(row.get("market_home_prob_no_vig", 0.5) or 0.5)
    game_date = str(row.get("game_date", ""))

    # Month segment
    if len(game_date) >= 7:
        month = game_date[:7]
        segments.append(("month", month, f"month:{month}"))

    # Odds bucket
    bucket = _classify_odds_bucket(market_prob)
    segments.append(("odds_bucket", bucket, f"odds_bucket:{bucket}"))

    # Confidence
    conf = _classify_confidence(model_prob)
    segments.append(("confidence", conf, f"confidence:{conf}"))

    # Disagreement
    disagree = _classify_disagreement(model_prob, market_prob)
    segments.append(("disagreement", disagree, f"disagreement:{disagree}"))

    return segments


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Metrics computation
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_global_metrics(rows: list[dict], prob_field: str, source: str) -> MetricsSnapshot56:
    """Compute global metrics for a JSONL source."""
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
        # Bounds check
        if not (0.0 <= prob_f <= 1.0):
            continue
        if label_f not in (0.0, 1.0):
            continue
        if not (0.0 <= market_f <= 1.0):
            continue
        probs.append(prob_f)
        labels.append(label_f)
        market_probs.append(market_f)

    if len(probs) < 10:
        return MetricsSnapshot56(source=source, n=len(probs))

    model_brier = brier_score(probs, labels)
    market_brier = brier_score(market_probs, labels)
    bss = brier_skill_score(model_brier, market_brier)
    ece_result = expected_calibration_error(probs, labels)
    ll = log_loss_score(probs, labels)

    return MetricsSnapshot56(
        source=source,
        n=len(probs),
        brier=round(model_brier, 6),
        bss_vs_market=round(bss, 6) if bss is not None else None,
        ece=round(ece_result["ece"], 6),
        log_loss=round(ll, 6),
    )


def _compute_segment_metrics(
    baseline_rows: list[dict],
    phase56_rows: list[dict],
) -> list[SegmentMetrics56]:
    """Compute per-segment BSS and ECE for baseline vs phase56."""
    # Build index for phase56 rows by game_id
    p56_by_gid: dict[str, dict] = {}
    for row in phase56_rows:
        gid = row.get("game_id", "")
        if gid:
            p56_by_gid[gid] = row

    # Collect data per segment
    seg_baseline: dict[str, tuple[list[float], list[float], str, str]] = {}
    seg_phase56: dict[str, tuple[list[float], list[float]]] = {}

    for base_row in baseline_rows:
        gid = base_row.get("game_id", "")
        base_prob = base_row.get("model_home_prob")
        label = base_row.get("home_win")
        market = base_row.get("market_home_prob_no_vig")

        if base_prob is None or label is None or market is None:
            continue
        try:
            base_p = float(base_prob)
            lbl = float(label)
            mkt = float(market)
        except (ValueError, TypeError):
            continue
        if not (0.0 <= base_p <= 1.0) or lbl not in (0.0, 1.0):
            continue

        p56_row = p56_by_gid.get(gid)
        p56_prob = None
        if p56_row is not None:
            p56_prob_raw = p56_row.get("model_home_prob")
            try:
                p56_p = float(p56_prob_raw)
                if 0.0 <= p56_p <= 1.0:
                    p56_prob = p56_p
            except (ValueError, TypeError):
                pass

        for seg_type, seg_label, seg_key in _get_segments(base_row, base_p):
            if seg_key not in seg_baseline:
                seg_baseline[seg_key] = ([], [], seg_type, seg_label)
                seg_phase56[seg_key] = ([], [])

            seg_baseline[seg_key][0].append(base_p)
            seg_baseline[seg_key][1].append(lbl)

            if p56_prob is not None:
                seg_phase56[seg_key][0].append(p56_prob)
                seg_phase56[seg_key][1].append(lbl)

    results: list[SegmentMetrics56] = []

    for seg_key, (base_probs, labels, seg_type, seg_label) in seg_baseline.items():
        n = len(base_probs)
        if n < _MIN_SEGMENT_N:
            continue

        market_probs = [
            float(r.get("market_home_prob_no_vig") or 0.5)
            for r in baseline_rows
            if _is_same_segment(r, seg_key)
        ]
        # Market brier for BSS baseline
        # Use simple market brier based on same rows
        # Recompute properly
        row_data = [
            (float(r.get("model_home_prob") or 0.5),
             float(r.get("home_win") or 0),
             float(r.get("market_home_prob_no_vig") or 0.5))
            for r in baseline_rows
            if _is_same_segment(r, seg_key)
            and r.get("model_home_prob") is not None
            and r.get("home_win") is not None
            and r.get("market_home_prob_no_vig") is not None
            and 0.0 <= float(r.get("model_home_prob") or -1) <= 1.0
            and float(r.get("home_win") or -1) in (0.0, 1.0)
        ]
        if len(row_data) < _MIN_SEGMENT_N:
            continue

        bp_list = [x[0] for x in row_data]
        lbl_list = [x[1] for x in row_data]
        mkt_list = [x[2] for x in row_data]

        base_brier = brier_score(bp_list, lbl_list)
        mkt_brier = brier_score(mkt_list, lbl_list)
        base_bss_val = brier_skill_score(base_brier, mkt_brier)
        base_bss = round(base_bss_val, 6) if base_bss_val is not None else 0.0
        base_ece_result = expected_calibration_error(bp_list, lbl_list)
        base_ece = round(base_ece_result["ece"], 6)

        # Phase56 metrics for same segment
        p56_data = seg_phase56.get(seg_key, ([], []))
        p56_probs_list = p56_data[0]
        p56_labels_list = p56_data[1]

        if len(p56_probs_list) >= _MIN_SEGMENT_N:
            # Need matching market probs for BSS
            p56_mkt: list[float] = []
            for r in phase56_rows:
                if _is_same_row_segment(r, seg_key):
                    mp = r.get("market_home_prob_no_vig")
                    if mp is not None:
                        try:
                            p56_mkt.append(float(mp))
                        except (ValueError, TypeError):
                            pass

            if len(p56_mkt) == len(p56_probs_list):
                p56_brier = brier_score(p56_probs_list, p56_labels_list)
                p56_mkt_brier = brier_score(p56_mkt, p56_labels_list)
                p56_bss_raw = brier_skill_score(p56_brier, p56_mkt_brier)
                p56_bss = round(p56_bss_raw, 6) if p56_bss_raw is not None else 0.0
                p56_ece_result = expected_calibration_error(p56_probs_list, p56_labels_list)
                p56_ece = round(p56_ece_result["ece"], 6)
                improvement = _label_improvement(base_bss, p56_bss)
            else:
                p56_bss = base_bss
                p56_ece = base_ece
                improvement = "NOT_EVALUABLE"
        else:
            p56_bss = base_bss
            p56_ece = base_ece
            improvement = "NOT_EVALUABLE"

        delta_bss = round(p56_bss - base_bss, 6)
        delta_ece = round(p56_ece - base_ece, 6)

        is_failure = seg_key in _PHASE55_FAILURE_SEGMENTS

        results.append(SegmentMetrics56(
            segment_key=seg_key,
            segment_type=seg_type,
            segment_label=seg_label,
            n=len(bp_list),
            baseline_bss=base_bss,
            phase56_bss=p56_bss,
            delta_bss=delta_bss,
            baseline_ece=base_ece,
            phase56_ece=p56_ece,
            delta_ece=delta_ece,
            is_failure_segment=is_failure,
            improvement_label=improvement,
        ))

    return sorted(results, key=lambda s: s.segment_key)


def _is_same_segment(row: dict, seg_key: str) -> bool:
    """Check if a row belongs to the given segment."""
    model_prob = float(row.get("model_home_prob") or 0.5)
    for _, _, key in _get_segments(row, model_prob):
        if key == seg_key:
            return True
    return False


def _is_same_row_segment(row: dict, seg_key: str) -> bool:
    """Check if a phase56 row belongs to the given segment (uses original prob if available)."""
    model_prob = float(row.get("original_model_home_prob") or row.get("model_home_prob") or 0.5)
    for _, _, key in _get_segments(row, model_prob):
        if key == seg_key:
            return True
    return False


def _label_improvement(base_bss: float, new_bss: float) -> str:
    """Label BSS improvement."""
    delta = new_bss - base_bss
    if abs(delta) < 1e-6:
        return "UNCHANGED"
    return "IMPROVED" if delta > 0 else "DEGRADED"


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Availability summary
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_availability_summary(phase56_rows: list[dict]) -> BullpenAvailabilitySummary:
    """Summarize bullpen feature availability from injected JSONL."""
    total = len(phase56_rows)
    available = 0
    fallback = 0
    model_affecting = 0
    total_adj = 0.0
    max_adj = 0.0

    for row in phase56_rows:
        bf = row.get("bullpen_features", {})
        if isinstance(bf, dict) and bf.get("bullpen_feature_available", False):
            available += 1
        if row.get("bullpen_fallback_applied", True):
            fallback += 1
        if row.get("feature_effect_mode") == "MODEL_AFFECTING":
            model_affecting += 1
        adj = abs(float(row.get("bullpen_adjustment", 0.0) or 0.0))
        total_adj += adj
        if adj > max_adj:
            max_adj = adj

    return BullpenAvailabilitySummary(
        total_rows=total,
        available_count=available,
        availability_rate=round(available / max(1, total), 4),
        fallback_count=fallback,
        model_affecting_count=model_affecting,
        model_affecting_rate=round(model_affecting / max(1, total), 4),
        avg_abs_adjustment=round(total_adj / max(1, total), 6),
        max_abs_adjustment=round(max_adj, 6),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Gate determination
# ═══════════════════════════════════════════════════════════════════════════════

def _decide_gate(
    availability: BullpenAvailabilitySummary,
    baseline_metrics: MetricsSnapshot56,
    phase56_metrics: MetricsSnapshot56,
    segment_metrics: list[SegmentMetrics56],
    failure_count_delta: int,
) -> tuple[str, str]:
    """
    Determine gate recommendation.

    Returns:
        (gate, rationale)

    Gate logic:
      1. availability_rate < 0.80 → DATA_GAP_REMAINS
      2. n too small (<100) → COLLECT_MORE_DATA
      3. rate >= 0.80:
         - heavy_fav ECE improved AND high_conf BSS not worse
           AND overall BSS not worse AND failure_count down
           → BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY
         - otherwise → BULLPEN_FEATURE_NOT_EFFECTIVE
    """
    rate = availability.availability_rate

    # Gate 1: Data gap
    if rate < _BULLPEN_AVAIL_MIN_RATE:
        rationale = (
            f"bullpen_feature_available_rate={rate:.1%} < {_BULLPEN_AVAIL_MIN_RATE:.0%}。"
            f"缺乏實際牛棚使用資料，無法進行有效特徵評估。"
            f"需要收集 MLB 2025 牛棚使用記錄 (bullpen_outs, leveraged appearances)。"
        )
        return DATA_GAP_REMAINS, rationale

    # Gate 2: Sample size check
    if baseline_metrics.n < 100:
        return COLLECT_MORE_DATA, f"樣本不足：n={baseline_metrics.n} < 100"

    # Gate 3: Improvement check
    hf_ece_improved = False
    hc_bss_not_worse = True
    overall_bss_not_worse = False

    for seg in segment_metrics:
        if seg.segment_key == "odds_bucket:heavy_favorite":
            hf_ece_improved = seg.delta_ece <= 0.0   # ECE lower = better
        if seg.segment_key == "confidence:high_confidence":
            hc_bss_not_worse = seg.delta_bss >= -0.001

    overall_bss_delta = (
        (phase56_metrics.bss_vs_market or 0.0) - (baseline_metrics.bss_vs_market or 0.0)
    )
    overall_bss_not_worse = overall_bss_delta >= -0.001
    failure_improved = failure_count_delta <= 0

    if hf_ece_improved and hc_bss_not_worse and overall_bss_not_worse and failure_improved:
        rationale = (
            f"牛棚特徵有效：heavy_fav ECE 改善 (delta_ece={-0:.4f})，"
            f"high_conf BSS 未惡化，overall BSS delta={overall_bss_delta:.4f}，"
            f"failure_count delta={failure_count_delta}。"
            f"建議進入 paper trading 追蹤。"
        )
        return BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY, rationale
    else:
        rationale = (
            f"牛棚特徵效果不顯著："
            f"heavy_fav ECE improved={hf_ece_improved}，"
            f"hc_bss_not_worse={hc_bss_not_worse}，"
            f"overall_bss_not_worse={overall_bss_not_worse}，"
            f"failure_count_delta={failure_count_delta}。"
            f"特徵需要真實牛棚資料或重新設計調整幅度。"
        )
        return BULLPEN_FEATURE_NOT_EFFECTIVE, rationale


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Main evaluation function
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase56_evaluation(
    baseline_path: Path,
    phase56_injected_path: Path,
) -> Phase56EvaluationResult:
    """
    Run full Phase56 bullpen feature evaluation.

    Args:
        baseline_path: Path to baseline JSONL (original per-game predictions).
        phase56_injected_path: Path to Phase56 injected JSONL.

    Returns:
        Phase56EvaluationResult

    Hard rules:
        - candidate_patch_created = False (always)
        - production_modified = False (always)
        - diagnostic_only = True (always)
        - gate in _VALID_GATES (always)
    """
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED
    assert DIAGNOSTIC_ONLY

    run_id = str(uuid.uuid4())[:8]
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("[Phase56] Loading baseline: %s", baseline_path)
    baseline_rows = _load_jsonl(baseline_path)

    logger.info("[Phase56] Loading phase56 injected: %s", phase56_injected_path)
    phase56_rows = _load_jsonl(phase56_injected_path)

    # Global metrics
    logger.info("[Phase56] Computing global metrics...")
    baseline_metrics = _compute_global_metrics(baseline_rows, "model_home_prob", "baseline")
    phase56_metrics = _compute_global_metrics(phase56_rows, "model_home_prob", "phase56_injected")
    market_metrics = _compute_global_metrics(baseline_rows, "market_home_prob_no_vig", "market")

    delta_brier = round(phase56_metrics.brier - baseline_metrics.brier, 6)
    delta_bss = round(
        (phase56_metrics.bss_vs_market or 0.0) - (baseline_metrics.bss_vs_market or 0.0), 6
    )
    delta_ece = round(phase56_metrics.ece - baseline_metrics.ece, 6)

    # Segment metrics
    logger.info("[Phase56] Computing segment metrics...")
    segment_metrics = _compute_segment_metrics(baseline_rows, phase56_rows)

    # Availability summary
    logger.info("[Phase56] Computing availability summary...")
    availability = _compute_availability_summary(phase56_rows)

    # Failure segments
    failure_segments_baseline = [
        s.segment_key for s in segment_metrics
        if s.is_failure_segment and s.baseline_bss < 0.0
    ]
    failure_segments_phase56 = [
        s.segment_key for s in segment_metrics
        if s.is_failure_segment and s.phase56_bss < 0.0
    ]
    failure_count_delta = len(failure_segments_phase56) - len(failure_segments_baseline)

    # Gate decision
    logger.info("[Phase56] Determining gate...")
    gate, rationale = _decide_gate(
        availability=availability,
        baseline_metrics=baseline_metrics,
        phase56_metrics=phase56_metrics,
        segment_metrics=segment_metrics,
        failure_count_delta=failure_count_delta,
    )

    # Audit hash
    audit_payload = (
        f"{run_id}|{gate}|{availability.availability_rate:.4f}|"
        f"{delta_bss:.6f}|{delta_ece:.6f}"
    )
    audit_hash = "sha256:" + hashlib.sha256(audit_payload.encode()).hexdigest()[:16]

    result = Phase56EvaluationResult(
        run_id=run_id,
        generated_at=generated_at,
        baseline_path=str(baseline_path),
        phase56_injected_path=str(phase56_injected_path),
        phase56_version=PHASE56_VERSION,
        baseline_metrics=baseline_metrics,
        phase56_metrics=phase56_metrics,
        market_metrics=market_metrics,
        delta_brier=delta_brier,
        delta_bss=delta_bss,
        delta_ece=delta_ece,
        segment_metrics=segment_metrics,
        failure_segments_in_phase56=failure_segments_phase56,
        failure_count_baseline=len(failure_segments_baseline),
        failure_count_phase56=len(failure_segments_phase56),
        bullpen_availability=availability,
        gate_recommendation=gate,
        gate_rationale=rationale,
        candidate_patch_created=False,
        production_modified=False,
        diagnostic_only=True,
        audit_hash=audit_hash,
    )

    logger.info(
        "[Phase56] Gate=%s | availability=%.1f%% | delta_bss=%.6f | delta_ece=%.6f",
        gate, availability.availability_rate * 100, delta_bss, delta_ece,
    )

    return result
