"""
orchestrator/phase53_sp_coefficient_calibration.py
====================================================
Phase 53 — SP Feature Coefficient Calibration Audit

背景：
  Phase 52A gate = FEATURE_REPAIR_NOT_EFFECTIVE（heavy_favorite ECE 輕微惡化 +0.000425）。
  本模組對 Phase52 的 sp_fip_delta adjustment rule 做 offline coefficient calibration audit，
  找出更保守、更穩定、不傷害 heavy_favorite ECE 的係數設定。

目前 Phase50/52 adjustment rule（scale=1.00x）：
  fip_adj = tanh(delta * 0.5) * 0.003

本模組測試不同 scale multiplier：
  scale ∈ [0.00, 0.25, 0.50, 0.75, 1.00, 1.25]
  即：fip_adj = tanh(delta * 0.5) * 0.003 * scale

Hard Rules（絕不違反）：
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - diagnostic_only = True（best coefficient 不可 productionize）
  - 不讀取 post-game leakage（home_win 僅用於 offline 評估，不用於單場調整）
  - 不重新訓練模型、不 ensemble
  - gate NEVER == "PATCH"
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Hard Constants ───────────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False      # NEVER change
PRODUCTION_MODIFIED: bool = False          # NEVER change
DIAGNOSTIC_ONLY: bool = True              # best coefficient 不可 productionize

# ─── Gate Labels ──────────────────────────────────────────────────────────────
FEATURE_COEFFICIENT_PAPER_ONLY: str = "FEATURE_COEFFICIENT_PAPER_ONLY"
FEATURE_COEFFICIENT_NOT_SAFE: str = "FEATURE_COEFFICIENT_NOT_SAFE"

# ─── Phase53 Module Constants ─────────────────────────────────────────────────
PHASE53_VERSION: str = "phase53_sp_coefficient_calibration_v1"

# 預設 scale grid
DEFAULT_SCALE_GRID: list[float] = [0.00, 0.25, 0.50, 0.75, 1.00, 1.25]

# 必做 segment keys（與 Phase52 保持一致）
REQUIRED_SEGMENTS: list[str] = [
    "overall",
    "month:2025-04",
    "month:2025-05",
    "month:2025-06",
    "month:2025-07",
    "odds_bucket:heavy_favorite",
    "odds_bucket:mid",
    "confidence:high_confidence",
    "confidence:low_confidence",
    "disagreement:high",
    "disagreement:low",
]

# ─── Adjustment Rule Constants（與 Phase50 一致）───────────────────────────────
_FIP_DELTA_BASE_SCALE: float = 0.003       # Phase50/52 baseline coefficient
_MAX_TOTAL_ADJUSTMENT: float = 0.025       # cap per game（不隨 scale 改變）
_PROB_CLAMP_LO: float = 0.01
_PROB_CLAMP_HI: float = 0.99

# Park-factor（與 Phase50 保持一致，不作 calibration 對象）
_PARK_HIGH_THRESHOLD: float = 1.10
_PARK_MED_THRESHOLD: float = 1.05
_PARK_HIGH_SCALE: float = 0.008
_PARK_MED_SCALE: float = 0.004
_PARK_PROB_THRESHOLD: float = 0.60

# Early-season（與 Phase50 保持一致，不作 calibration 對象）
_EARLY_SEASON_THRESHOLD: float = 0.20
_EARLY_SEASON_SHRINK_RATE: float = 0.04

# Safe coefficient selection 條件
_SAFE_MIN_ADJUSTED_RATE: float = 0.30      # adjusted_rate 不低於 30%
_SAFE_MAX_ABS_ADJUSTMENT: float = 0.025   # max_abs_adjustment 上限

# 最小 segment 樣本數
_MIN_SEGMENT_N: int = 30


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GridSearchEntry:
    """Single coefficient scale evaluation result."""

    # Scale multiplier (0.00 = baseline / no SP adjustment)
    coefficient_scale: float

    # Effective coefficient = _FIP_DELTA_BASE_SCALE * scale
    effective_fip_scale: float

    # Adjustment stats
    adjusted_rows: int
    adjusted_rate: float
    mean_abs_adjustment: float
    max_abs_adjustment: float

    # Overall metrics
    overall_brier: float | None
    overall_bss: float | None
    overall_ece: float | None

    # Segment metrics (subset required by spec)
    heavy_favorite_bss: float | None
    heavy_favorite_ece: float | None
    high_confidence_bss: float | None
    high_confidence_ece: float | None
    month_2025_04_bss: float | None
    month_2025_04_ece: float | None
    disagreement_high_bss: float | None
    disagreement_high_ece: float | None

    # Diagnostic flag
    diagnostic_only: bool = True
    candidate_patch_created: bool = False
    production_modified: bool = False


@dataclass
class SegmentDelta:
    """Segment-level comparison between baseline and candidate coefficient."""

    segment: str
    n: int
    baseline_bss: float | None
    candidate_bss: float | None
    delta_bss: float | None
    baseline_ece: float | None
    candidate_ece: float | None
    delta_ece: float | None
    label: str  # IMPROVED / DEGRADED / UNCHANGED


@dataclass
class Phase53CalibrationResult:
    """Full Phase 53 calibration audit result."""

    # Grid results
    coefficient_grid_results: list[GridSearchEntry]

    # Best coefficient selections
    best_by_overall_bss: float | None
    best_by_heavy_favorite_ece: float | None
    best_safe_coefficient: float | None

    # Gate
    gate: str
    gate_rationale: str

    # Segment comparison table for safe/best coefficient
    segment_comparison: list[SegmentDelta]

    # Baseline reference metrics
    baseline_brier: float | None
    baseline_bss: float | None
    baseline_ece: float | None
    baseline_n: int

    # Phase52 reference metrics (scale=1.00)
    phase52_brier: float | None
    phase52_bss: float | None
    phase52_ece: float | None

    # Hard-rule invariants
    diagnostic_only: bool = True
    candidate_patch_created: bool = False
    production_modified: bool = False

    # Run metadata
    phase53_version: str = PHASE53_VERSION
    run_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    audit_hash: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Adjustment logic
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_scaled_adjustment(
    base_prob: float,
    p0_features: dict[str, Any],
    scale: float,
) -> tuple[float, bool]:
    """
    Apply full P0 feature injection with scaled FIP coefficient.

    Returns (adjusted_prob, was_adjusted).
    Park-run and early-season adjustments are UNCHANGED (not calibration targets).
    Only sp_fip_delta coefficient is scaled.
    """
    p = float(base_prob)

    # ── F-004: season_game_index (unchanged) ──────────────────────────────────
    season_adj = 0.0
    if p0_features.get("season_game_index_available"):
        sgi = float(p0_features.get("season_game_index", 0.5))
        if sgi < _EARLY_SEASON_THRESHOLD:
            dist_factor = (_EARLY_SEASON_THRESHOLD - sgi) / _EARLY_SEASON_THRESHOLD
            season_adj = (0.5 - p) * _EARLY_SEASON_SHRINK_RATE * dist_factor

    # ── F-002: park_run_factor (unchanged) ────────────────────────────────────
    park_adj = 0.0
    if p0_features.get("park_factor_available"):
        prf = float(p0_features.get("park_run_factor", 1.0))
        if prf > _PARK_HIGH_THRESHOLD and p > _PARK_PROB_THRESHOLD:
            park_adj = -_PARK_HIGH_SCALE * (p - _PARK_PROB_THRESHOLD) / 0.4
        elif prf > _PARK_MED_THRESHOLD and p > _PARK_PROB_THRESHOLD:
            park_adj = -_PARK_MED_SCALE * (p - _PARK_PROB_THRESHOLD) / 0.4

    # ── F-001: sp_fip_delta (SCALED) ──────────────────────────────────────────
    fip_adj = 0.0
    if p0_features.get("sp_fip_delta_available"):
        delta = float(p0_features.get("sp_fip_delta", 0.0))
        fip_adj = math.tanh(delta * 0.5) * _FIP_DELTA_BASE_SCALE * scale

    # ── Apply cap & clamp ─────────────────────────────────────────────────────
    raw_total = season_adj + park_adj + fip_adj
    capped = max(-_MAX_TOTAL_ADJUSTMENT, min(_MAX_TOTAL_ADJUSTMENT, raw_total))
    adjusted = max(_PROB_CLAMP_LO, min(_PROB_CLAMP_HI, p + capped))

    was_adjusted = abs(adjusted - p) > 1e-9
    return adjusted, was_adjusted


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Metrics computation (delegates to SSOT)
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_metrics(probs: list[float], labels: list[float]) -> dict[str, Any]:
    """Compute Brier / BSS / ECE.  BSS baseline = coin-flip = 0.25."""
    from wbc_backend.evaluation.metrics import (
        brier_score,
        brier_skill_score,
        expected_calibration_error,
    )

    valid = [(p, o) for p, o in zip(probs, labels) if o in (0.0, 1.0)]
    if len(valid) < _MIN_SEGMENT_N:
        return {"n": len(valid), "brier": None, "bss": None, "ece": None}

    ps_list = [v[0] for v in valid]
    os_list = [v[1] for v in valid]

    bs = brier_score(ps_list, os_list)
    bss_val = brier_skill_score(bs, 0.25)
    ece_result = expected_calibration_error(ps_list, os_list)
    ece_val = ece_result["ece"] if isinstance(ece_result, dict) else float(ece_result)

    return {
        "n": len(valid),
        "brier": round(bs, 6),
        "bss": round(bss_val, 6) if bss_val is not None else None,
        "ece": round(ece_val, 6),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Segmentation
# ═══════════════════════════════════════════════════════════════════════════════

def _segment_rows(rows: list[dict]) -> dict[str, list[dict]]:
    """
    Partition rows into named segments.
    Each segment entry has keys: prob, home_win, market_prob.
    """
    segments: dict[str, list[dict]] = {seg: [] for seg in REQUIRED_SEGMENTS}
    segments["overall"] = list(rows)  # all rows

    for r in rows:
        gd = r.get("game_date", "")[:7]
        seg_key = f"month:{gd}"
        if seg_key in segments:
            segments[seg_key].append(r)

        mkt = float(r.get("market_home_prob_no_vig", 0.5))
        if mkt > 0.65 or mkt < 0.35:
            segments["odds_bucket:heavy_favorite"].append(r)
        elif 0.45 <= mkt <= 0.55:
            segments["odds_bucket:mid"].append(r)

        mdl = float(r.get("prob", 0.5))
        conf = abs(mdl - 0.5)
        if conf > 0.15:
            segments["confidence:high_confidence"].append(r)
        elif conf < 0.08:
            segments["confidence:low_confidence"].append(r)

        disagree = abs(mdl - mkt)
        if disagree > 0.10:
            segments["disagreement:high"].append(r)
        elif disagree < 0.03:
            segments["disagreement:low"].append(r)

    return segments


def _segment_metrics_table(
    rows: list[dict],
) -> dict[str, dict[str, Any]]:
    """Compute metrics for all required segments."""
    segs = _segment_rows(rows)
    result: dict[str, dict] = {}
    for seg_name, seg_rows in segs.items():
        probs = [float(r["prob"]) for r in seg_rows]
        labels = [float(r["home_win"]) for r in seg_rows]
        result[seg_name] = _compute_metrics(probs, labels)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Grid evaluation
# ═══════════════════════════════════════════════════════════════════════════════

def _evaluate_scale(
    context_rows: list[dict],
    scale: float,
) -> GridSearchEntry:
    """
    Evaluate a single coefficient scale against all context rows.

    Each context_row must have:
      - model_home_prob: float (unadjusted, = baseline)
      - home_win: float (0.0 or 1.0)
      - market_home_prob_no_vig: float
      - game_date: str
      - p0_features: dict (contains sp_fip_delta etc.)
    """
    adjusted_probs: list[float] = []
    adjusted_count = 0
    abs_adjustments: list[float] = []

    rows_for_metrics: list[dict] = []

    for r in context_rows:
        base_prob = float(r.get("model_home_prob", 0.5))
        p0_features = r.get("p0_features", {})
        home_win = float(r.get("home_win", -1.0))

        adj_prob, was_adj = _apply_scaled_adjustment(base_prob, p0_features, scale)
        abs_adj = abs(adj_prob - base_prob)

        if was_adj:
            adjusted_count += 1
        abs_adjustments.append(abs_adj)
        adjusted_probs.append(adj_prob)

        rows_for_metrics.append({
            "prob": adj_prob,
            "home_win": home_win,
            "market_home_prob_no_vig": r.get("market_home_prob_no_vig", 0.5),
            "game_date": r.get("game_date", ""),
        })

    total = len(context_rows)
    adjusted_rate = adjusted_count / total if total > 0 else 0.0
    mean_abs = sum(abs_adjustments) / len(abs_adjustments) if abs_adjustments else 0.0
    max_abs = max(abs_adjustments) if abs_adjustments else 0.0

    # Overall metrics
    all_probs = [r["prob"] for r in rows_for_metrics]
    all_labels = [r["home_win"] for r in rows_for_metrics]
    overall = _compute_metrics(all_probs, all_labels)

    # Segment metrics
    segs = _segment_metrics_table(rows_for_metrics)

    hf = segs.get("odds_bucket:heavy_favorite", {})
    hc = segs.get("confidence:high_confidence", {})
    apr = segs.get("month:2025-04", {})
    dh = segs.get("disagreement:high", {})

    return GridSearchEntry(
        coefficient_scale=round(scale, 4),
        effective_fip_scale=round(_FIP_DELTA_BASE_SCALE * scale, 6),
        adjusted_rows=adjusted_count,
        adjusted_rate=round(adjusted_rate, 6),
        mean_abs_adjustment=round(mean_abs, 6),
        max_abs_adjustment=round(max_abs, 6),
        overall_brier=overall.get("brier"),
        overall_bss=overall.get("bss"),
        overall_ece=overall.get("ece"),
        heavy_favorite_bss=hf.get("bss"),
        heavy_favorite_ece=hf.get("ece"),
        high_confidence_bss=hc.get("bss"),
        high_confidence_ece=hc.get("ece"),
        month_2025_04_bss=apr.get("bss"),
        month_2025_04_ece=apr.get("ece"),
        disagreement_high_bss=dh.get("bss"),
        disagreement_high_ece=dh.get("ece"),
        diagnostic_only=True,
        candidate_patch_created=False,
        production_modified=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Safe coefficient selection
# ═══════════════════════════════════════════════════════════════════════════════

def _select_safe_coefficient(
    grid_results: list[GridSearchEntry],
    baseline_bss: float | None,
    baseline_ece: float | None,
    baseline_hf_ece: float | None,
    baseline_hc_bss: float | None,
    baseline_apr_bss: float | None,
) -> tuple[float | None, str, str]:
    """
    Select safe coefficient per spec:

    Conditions (ALL must be satisfied):
      1. overall BSS >= baseline BSS
      2. overall ECE <= baseline ECE
      3. heavy_favorite ECE <= baseline heavy_favorite ECE   ← gate failure point in Phase52
      4. high_confidence BSS 不惡化（>= baseline_hc_bss - 0.001 tolerance）
      5. month:2025-04 BSS 不惡化（>= baseline_apr_bss - 0.001 tolerance）
      6. adjusted_rate >= 30%
      7. max_abs_adjustment <= 0.025

    Returns (safe_scale, gate, rationale).
    """
    _b_bss = baseline_bss or 0.0
    _b_ece = baseline_ece or 1.0
    _b_hf_ece = baseline_hf_ece or 1.0
    _b_hc_bss = baseline_hc_bss if baseline_hc_bss is not None else -999.0
    _b_apr_bss = baseline_apr_bss if baseline_apr_bss is not None else -999.0

    candidates: list[tuple[float, GridSearchEntry]] = []

    for entry in grid_results:
        if entry.coefficient_scale == 0.0:
            continue  # skip pure baseline (trivially passes but meaningless)

        # Condition 1: overall BSS >= baseline
        if entry.overall_bss is None or entry.overall_bss < _b_bss:
            continue

        # Condition 2: overall ECE <= baseline
        if entry.overall_ece is None or entry.overall_ece > _b_ece:
            continue

        # Condition 3: heavy_favorite ECE <= baseline (THIS was Phase52 gate failure)
        if entry.heavy_favorite_ece is None or entry.heavy_favorite_ece > _b_hf_ece:
            continue

        # Condition 4: high_confidence BSS 不惡化
        if entry.high_confidence_bss is not None:
            if entry.high_confidence_bss < _b_hc_bss - 0.001:
                continue

        # Condition 5: month:2025-04 BSS 不惡化
        if entry.month_2025_04_bss is not None:
            if entry.month_2025_04_bss < _b_apr_bss - 0.001:
                continue

        # Condition 6: adjusted_rate >= 30%
        if entry.adjusted_rate < _SAFE_MIN_ADJUSTED_RATE:
            continue

        # Condition 7: max_abs_adjustment <= 0.025
        if entry.max_abs_adjustment > _SAFE_MAX_ABS_ADJUSTMENT:
            continue

        candidates.append((entry.coefficient_scale, entry))

    if not candidates:
        rationale = (
            "無係數同時滿足 heavy_favorite ECE <= baseline 且 overall BSS >= baseline。"
            "建議 Phase54 — SP Feature Functional Form Redesign。"
        )
        return None, FEATURE_COEFFICIENT_NOT_SAFE, rationale

    # 選出 heavy_favorite ECE 最小的候選（最安全）
    best_scale, best_entry = min(candidates, key=lambda x: (x[1].heavy_favorite_ece or 999.0))

    hf_ece_delta = (best_entry.heavy_favorite_ece or 0.0) - _b_hf_ece
    bss_delta = (best_entry.overall_bss or 0.0) - _b_bss

    rationale = (
        f"scale={best_scale:.2f} 滿足全部 7 項安全條件："
        f" overall BSS delta={bss_delta:+.6f},"
        f" overall ECE delta={(best_entry.overall_ece or 0.0) - _b_ece:+.6f},"
        f" heavy_favorite ECE delta={hf_ece_delta:+.6f}（改善或持平）。"
        f" adjusted_rate={best_entry.adjusted_rate:.1%},"
        f" max_abs_adj={best_entry.max_abs_adjustment:.6f}。"
        f" 本係數為 diagnostic_only，不可直接 productionize。"
    )
    return best_scale, FEATURE_COEFFICIENT_PAPER_ONLY, rationale


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  Segment comparison table builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_segment_comparison(
    context_rows: list[dict],
    safe_scale: float | None,
    baseline_seg: dict[str, dict],
) -> list[SegmentDelta]:
    """
    Build segment comparison between baseline and safe_scale (or best candidate).
    """
    # If no safe coefficient, use scale=0.75 as diagnostic best candidate
    eval_scale = safe_scale if safe_scale is not None else 0.75

    rows_for_metrics: list[dict] = []
    for r in context_rows:
        base_prob = float(r.get("model_home_prob", 0.5))
        p0_features = r.get("p0_features", {})
        adj_prob, _ = _apply_scaled_adjustment(base_prob, p0_features, eval_scale)
        rows_for_metrics.append({
            "prob": adj_prob,
            "home_win": float(r.get("home_win", -1.0)),
            "market_home_prob_no_vig": r.get("market_home_prob_no_vig", 0.5),
            "game_date": r.get("game_date", ""),
        })

    candidate_seg = _segment_metrics_table(rows_for_metrics)

    deltas: list[SegmentDelta] = []
    for seg in REQUIRED_SEGMENTS:
        b = baseline_seg.get(seg, {})
        c = candidate_seg.get(seg, {})

        b_bss = b.get("bss")
        c_bss = c.get("bss")
        b_ece = b.get("ece")
        c_ece = c.get("ece")

        d_bss = round(c_bss - b_bss, 6) if (c_bss is not None and b_bss is not None) else None
        d_ece = round(c_ece - b_ece, 6) if (c_ece is not None and b_ece is not None) else None

        # Label: IMPROVED if BSS↑ and ECE↓, DEGRADED if BSS↓ or ECE↑ meaningfully
        if d_bss is None or d_ece is None:
            label = "UNCHANGED"
        elif d_bss > 0.0001 and d_ece < -0.0001:
            label = "IMPROVED"
        elif d_bss < -0.001 or d_ece > 0.001:
            label = "DEGRADED"
        else:
            label = "UNCHANGED"

        deltas.append(SegmentDelta(
            segment=seg,
            n=c.get("n", 0),
            baseline_bss=b_bss,
            candidate_bss=c_bss,
            delta_bss=d_bss,
            baseline_ece=b_ece,
            candidate_ece=c_ece,
            delta_ece=d_ece,
            label=label,
        ))

    return deltas


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  Main calibration runner
# ═══════════════════════════════════════════════════════════════════════════════

def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _build_baseline_rows(baseline_path: Path) -> list[dict]:
    """Load baseline JSONL — provides unadjusted model_home_prob."""
    return _load_jsonl(baseline_path)


def _build_context_rows(context_path: Path) -> list[dict]:
    """
    Load phase52_sp_context JSONL.
    These rows have:
      - model_home_prob: same as baseline (unadjusted)
      - home_win: outcome
      - market_home_prob_no_vig: market odds
      - p0_features: dict with sp_fip_delta, park_run_factor, season_game_index, etc.
    """
    return _load_jsonl(context_path)


def _build_baseline_seg_from_rows(context_rows: list[dict]) -> dict[str, dict]:
    """
    Compute baseline (scale=0.00) segment metrics from context rows.
    Uses model_home_prob as-is (unadjusted).
    """
    rows_for_metrics = [
        {
            "prob": float(r.get("model_home_prob", 0.5)),
            "home_win": float(r.get("home_win", -1.0)),
            "market_home_prob_no_vig": r.get("market_home_prob_no_vig", 0.5),
            "game_date": r.get("game_date", ""),
        }
        for r in context_rows
    ]
    return _segment_metrics_table(rows_for_metrics)


def run_calibration(
    baseline_path: Path,
    context_path: Path,
    scale_grid: list[float] | None = None,
) -> Phase53CalibrationResult:
    """
    Run Phase 53 SP coefficient calibration audit.

    Args:
        baseline_path: Path to mlb_2025_per_game_predictions.jsonl
        context_path:  Path to mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl
        scale_grid:    List of scale multipliers. Defaults to DEFAULT_SCALE_GRID.

    Returns:
        Phase53CalibrationResult with full audit.

    Hard rules:
        - CANDIDATE_PATCH_CREATED = False always
        - PRODUCTION_MODIFIED = False always
        - diagnostic_only = True always
    """
    if scale_grid is None:
        scale_grid = DEFAULT_SCALE_GRID

    logger.info("Phase 53 calibration: loading context rows from %s", context_path)
    context_rows = _build_context_rows(context_path)
    logger.info("Loaded %d context rows", len(context_rows))

    # ── Baseline metrics (scale=0.00 = unadjusted model_home_prob) ────────────
    baseline_rows_for_metrics = [
        {
            "prob": float(r.get("model_home_prob", 0.5)),
            "home_win": float(r.get("home_win", -1.0)),
            "market_home_prob_no_vig": r.get("market_home_prob_no_vig", 0.5),
            "game_date": r.get("game_date", ""),
        }
        for r in context_rows
    ]
    all_base_probs = [r["prob"] for r in baseline_rows_for_metrics]
    all_base_labels = [r["home_win"] for r in baseline_rows_for_metrics]
    baseline_overall = _compute_metrics(all_base_probs, all_base_labels)
    baseline_seg = _segment_metrics_table(baseline_rows_for_metrics)

    logger.info(
        "Baseline: n=%d, BSS=%.6f, ECE=%.6f",
        baseline_overall.get("n", 0),
        baseline_overall.get("bss") or 0.0,
        baseline_overall.get("ece") or 0.0,
    )

    # ── Grid search ───────────────────────────────────────────────────────────
    grid_results: list[GridSearchEntry] = []
    for scale in scale_grid:
        logger.info("Evaluating scale=%.2f (effective_coeff=%.6f)", scale, _FIP_DELTA_BASE_SCALE * scale)
        entry = _evaluate_scale(context_rows, scale)
        grid_results.append(entry)
        logger.info(
            "  scale=%.2f: adjusted=%d (%.1f%%), BSS=%.6f, ECE=%.6f, HF_ECE=%.6f",
            scale,
            entry.adjusted_rows,
            entry.adjusted_rate * 100,
            entry.overall_bss or 0.0,
            entry.overall_ece or 0.0,
            entry.heavy_favorite_ece or 0.0,
        )

    # ── Best by overall BSS ───────────────────────────────────────────────────
    valid_bss = [e for e in grid_results if e.overall_bss is not None]
    best_by_overall_bss: float | None = None
    if valid_bss:
        best_bss_entry = max(valid_bss, key=lambda e: e.overall_bss or -999.0)
        best_by_overall_bss = best_bss_entry.coefficient_scale

    # ── Best by heavy_favorite ECE ────────────────────────────────────────────
    valid_hf = [e for e in grid_results if e.heavy_favorite_ece is not None]
    best_by_hf_ece: float | None = None
    if valid_hf:
        best_hf_entry = min(valid_hf, key=lambda e: e.heavy_favorite_ece or 999.0)
        best_by_hf_ece = best_hf_entry.coefficient_scale

    # ── Safe coefficient selection ────────────────────────────────────────────
    baseline_hf_ece = (baseline_seg.get("odds_bucket:heavy_favorite") or {}).get("ece")
    baseline_hc_bss = (baseline_seg.get("confidence:high_confidence") or {}).get("bss")
    baseline_apr_bss = (baseline_seg.get("month:2025-04") or {}).get("bss")

    safe_scale, gate, gate_rationale = _select_safe_coefficient(
        grid_results=grid_results,
        baseline_bss=baseline_overall.get("bss"),
        baseline_ece=baseline_overall.get("ece"),
        baseline_hf_ece=baseline_hf_ece,
        baseline_hc_bss=baseline_hc_bss,
        baseline_apr_bss=baseline_apr_bss,
    )

    logger.info("Gate: %s | safe_coefficient: %s", gate, safe_scale)

    # ── Phase52 reference metrics (scale=1.00) ────────────────────────────────
    p52_entry = next((e for e in grid_results if abs(e.coefficient_scale - 1.00) < 1e-6), None)
    p52_brier = p52_entry.overall_brier if p52_entry else None
    p52_bss = p52_entry.overall_bss if p52_entry else None
    p52_ece = p52_entry.overall_ece if p52_entry else None

    # ── Segment comparison for safe / best candidate ──────────────────────────
    segment_comparison = _build_segment_comparison(
        context_rows=context_rows,
        safe_scale=safe_scale,
        baseline_seg=baseline_seg,
    )

    # ── Audit hash ────────────────────────────────────────────────────────────
    hash_src = json.dumps(
        {
            "scale_grid": scale_grid,
            "baseline_n": baseline_overall.get("n", 0),
            "gate": gate,
            "safe_scale": safe_scale,
        },
        sort_keys=True,
    )
    audit_hash = hashlib.sha256(hash_src.encode()).hexdigest()[:16]

    return Phase53CalibrationResult(
        coefficient_grid_results=grid_results,
        best_by_overall_bss=best_by_overall_bss,
        best_by_heavy_favorite_ece=best_by_hf_ece,
        best_safe_coefficient=safe_scale,
        gate=gate,
        gate_rationale=gate_rationale,
        segment_comparison=segment_comparison,
        baseline_brier=baseline_overall.get("brier"),
        baseline_bss=baseline_overall.get("bss"),
        baseline_ece=baseline_overall.get("ece"),
        baseline_n=baseline_overall.get("n", 0),
        phase52_brier=p52_brier,
        phase52_bss=p52_bss,
        phase52_ece=p52_ece,
        diagnostic_only=True,
        candidate_patch_created=False,
        production_modified=False,
        phase53_version=PHASE53_VERSION,
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        audit_hash=audit_hash,
    )
