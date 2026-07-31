"""
wbc_backend/features/mlb_p0_feature_injection.py
=================================================
Phase 50 — P0 Feature Injection Adapter.

功能：
  apply_p0_feature_adjustment(base_model_prob, p0_features) -> AdjustmentResult

規則（保守 deterministic，不重新訓練模型）：

1. season_game_index (F-004)
   若 season_game_index_available 且 season_game_index < 0.20：
     early-season 不確定性高，往 0.5 收縮（降低過度信心）。
     adjustment = (0.5 - p) * EARLY_SEASON_SHRINK_RATE

2. park_run_factor (F-002)
   若 park_factor_available 且 park_run_factor > 1.05：
     hitter-friendly 球場，home team 若已被 model 看高（p > 0.60），
     輕微降低過度信心（park 效應已被市場反映但 model 未充分折扣）。
     若 park_run_factor > 1.10，微調幅度加大。

3. sp_fip_delta (F-001)
   若 sp_fip_delta_available：
     away_sp_fip - home_sp_fip
     若 delta > 0 (home SP 優於 away SP)：小幅加強 home win prob
     若 delta < 0 (away SP 優於 home SP)：小幅降低 home win prob
   若 sp_fip_delta_available = False：不調整。

硬性限制：
- 單場最大 ±0.025 total adjustment
- adjusted_prob clamp 在 [0.01, 0.99]
- 不讀取 home_win / final_score / result / closing_odds_after_game
- candidate_patch_created = False（永遠）
- production_modified = False（永遠）
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

# ─── Hard-rule invariants ─────────────────────────────────────────────────────
CANDIDATE_PATCH_CREATED: bool = False
PRODUCTION_MODIFIED: bool = False
FEATURE_VERSION: str = "phase50_p0_injected_v1"

# ─── Adjustment constants ─────────────────────────────────────────────────────
_MAX_TOTAL_ADJUSTMENT: float = 0.025          # cap per game
MAX_PER_FEATURE_ADJUSTMENT: float = 0.015    # soft per-feature cap (informational)
_PROB_CLAMP_LO: float = 0.01
_PROB_CLAMP_HI: float = 0.99

# Early-season shrinkage
_EARLY_SEASON_THRESHOLD: float = 0.20        # first 20% of season
_EARLY_SEASON_SHRINK_RATE: float = 0.04      # 4% of distance from 0.5

# Park-factor adjustment
_PARK_HIGH_THRESHOLD: float = 1.10           # e.g. Colorado
_PARK_MED_THRESHOLD: float  = 1.05           # moderate hitter-friendly
_PARK_HIGH_SCALE: float     = 0.008          # high park, strong discount
_PARK_MED_SCALE: float      = 0.004          # moderate park discount
_PARK_PROB_THRESHOLD: float = 0.60           # only apply if model is overconfident

# SP FIP delta adjustment
_FIP_DELTA_SCALE: float     = 0.003          # per 1 FIP point of advantage

# Forbidden fields — must never be read
_FORBIDDEN_FIELDS: frozenset[str] = frozenset({
    "home_win", "final_score", "home_score", "away_score",
    "result", "closing_odds_after_game", "post_game_stats",
})


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Adjustment Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AdjustmentResult:
    """Result of apply_p0_feature_adjustment()."""

    # Original (pre-adjustment) probability
    original_model_home_prob: float

    # Post-adjustment probability (clamped to [0.01, 0.99])
    adjusted_model_home_prob: float

    # Component-level breakdown
    season_index_adjustment: float = 0.0
    park_run_adjustment: float     = 0.0
    sp_fip_adjustment: float       = 0.0

    # Total before cap
    raw_total_adjustment: float = 0.0

    # After cap
    capped_total_adjustment: float = 0.0

    # Whether cap was applied
    cap_applied: bool = False

    # Human-readable reason tags
    adjustment_reason: list[str] = field(default_factory=list)

    # Structured component dict (for JSONL serialisation)
    adjustment_components: dict[str, Any] = field(default_factory=dict)

    # Was this row actually adjusted?
    was_adjusted: bool = False

    # Hard-rule invariants (always False)
    candidate_patch_created: bool = False
    production_modified: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Core adjustment logic
# ═══════════════════════════════════════════════════════════════════════════════

def apply_p0_feature_adjustment(
    base_model_prob: float,
    p0_features: dict[str, Any],
) -> AdjustmentResult:
    """
    Apply Phase 50 P0 feature adjustments to base_model_prob.

    Args:
        base_model_prob: 原始模型 home win 機率，範圍 [0, 1]。
        p0_features: Phase48 P0 feature dict (from JSONL p0_features key).
                     Must NOT contain or read forbidden fields.

    Returns:
        AdjustmentResult with all adjustment details.

    Hard rules:
        - Never reads forbidden fields (home_win, final_score, etc.)
        - cap: ±0.025 max total
        - clamp: adjusted ∈ [0.01, 0.99]
        - candidate_patch_created = False always
        - production_modified = False always
    """
    # Leakage guard — ensure p0_features doesn't expose forbidden fields
    for fld in _FORBIDDEN_FIELDS:
        if fld in p0_features:
            raise ValueError(
                f"Leakage guard: forbidden field '{fld}' found in p0_features. "
                "Phase 50 injection adapter must not access post-game information."
            )

    p = float(base_model_prob)
    reasons: list[str] = []
    components: dict[str, Any] = {
        "season_index_adjustment": 0.0,
        "park_run_adjustment": 0.0,
        "sp_fip_adjustment": 0.0,
        "season_index_available": False,
        "park_factor_available": False,
        "sp_fip_delta_available": False,
    }

    # ── F-004: season_game_index ──────────────────────────────────────────────
    season_adj = 0.0
    season_available = bool(p0_features.get("season_game_index_available", False))
    components["season_index_available"] = season_available
    if season_available:
        sgi = float(p0_features.get("season_game_index", 0.5))
        components["season_game_index"] = sgi
        if sgi < _EARLY_SEASON_THRESHOLD:
            # Shrink toward 0.5 proportional to distance below threshold:
            # the earlier in the season, the stronger the uncertainty discount.
            distance_factor = (_EARLY_SEASON_THRESHOLD - sgi) / _EARLY_SEASON_THRESHOLD
            season_adj = (0.5 - p) * _EARLY_SEASON_SHRINK_RATE * distance_factor
            reasons.append(
                f"early_season_shrink(sgi={sgi:.3f}, adj={season_adj:+.4f})"
            )
    components["season_index_adjustment"] = round(season_adj, 6)

    # ── F-002: park_run_factor ────────────────────────────────────────────────
    park_adj = 0.0
    park_available = bool(p0_features.get("park_factor_available", False))
    components["park_factor_available"] = park_available
    if park_available:
        prf = float(p0_features.get("park_run_factor", 1.0))
        components["park_run_factor"] = prf
        if prf > _PARK_HIGH_THRESHOLD and p > _PARK_PROB_THRESHOLD:
            # High hitter-friendly park + model over-confident on home team
            park_adj = -1.0 * _PARK_HIGH_SCALE * (p - _PARK_PROB_THRESHOLD) / 0.4
            reasons.append(
                f"park_factor_high(prf={prf:.3f}, adj={park_adj:+.4f})"
            )
        elif prf > _PARK_MED_THRESHOLD and p > _PARK_PROB_THRESHOLD:
            park_adj = -1.0 * _PARK_MED_SCALE * (p - _PARK_PROB_THRESHOLD) / 0.4
            reasons.append(
                f"park_factor_med(prf={prf:.3f}, adj={park_adj:+.4f})"
            )
    components["park_run_adjustment"] = round(park_adj, 6)

    # ── F-001: sp_fip_delta ───────────────────────────────────────────────────
    fip_adj = 0.0
    sp_fip_available = bool(p0_features.get("sp_fip_delta_available", False))
    components["sp_fip_delta_available"] = sp_fip_available
    if sp_fip_available:
        # sp_fip_delta = away_sp_fip - home_sp_fip
        # Positive delta: home SP is better → increase home prob
        # Negative delta: away SP is better → decrease home prob
        delta = float(p0_features.get("sp_fip_delta", 0.0))
        components["sp_fip_delta"] = delta
        fip_adj = math.tanh(delta * 0.5) * _FIP_DELTA_SCALE
        if abs(fip_adj) > 1e-6:
            reasons.append(
                f"sp_fip_delta(delta={delta:+.3f}, adj={fip_adj:+.4f})"
            )
    components["sp_fip_adjustment"] = round(fip_adj, 6)

    # ── Apply cap ─────────────────────────────────────────────────────────────
    raw_total = season_adj + park_adj + fip_adj
    capped_total = max(-_MAX_TOTAL_ADJUSTMENT, min(_MAX_TOTAL_ADJUSTMENT, raw_total))
    cap_applied = abs(capped_total - raw_total) > 1e-9

    adjusted = p + capped_total
    adjusted = max(_PROB_CLAMP_LO, min(_PROB_CLAMP_HI, adjusted))

    was_adjusted = abs(adjusted - p) > 1e-9
    if cap_applied:
        reasons.append(f"cap_applied(raw={raw_total:+.4f}→capped={capped_total:+.4f})")

    components.update({
        "raw_total_adjustment": round(raw_total, 6),
        "capped_total_adjustment": round(capped_total, 6),
        "cap_applied": cap_applied,
        "was_adjusted": was_adjusted,
    })

    return AdjustmentResult(
        original_model_home_prob=round(p, 8),
        adjusted_model_home_prob=round(adjusted, 8),
        season_index_adjustment=round(season_adj, 6),
        park_run_adjustment=round(park_adj, 6),
        sp_fip_adjustment=round(fip_adj, 6),
        raw_total_adjustment=round(raw_total, 6),
        capped_total_adjustment=round(capped_total, 6),
        cap_applied=cap_applied,
        adjustment_reason=reasons,
        adjustment_components=components,
        was_adjusted=was_adjusted,
        candidate_patch_created=False,
        production_modified=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Build phase50 JSONL row
# ═══════════════════════════════════════════════════════════════════════════════

def build_phase50_row(
    phase48_row: dict[str, Any],
    adjustment: AdjustmentResult,
) -> dict[str, Any]:
    """
    Merge phase48 row + P0 adjustment into a phase50 JSONL row.

    The output row:
    - Inherits all non-model fields from phase48_row
    - Sets model_home_prob = adjustment.adjusted_model_home_prob
    - Adds original_model_home_prob
    - Adds p0_feature_adjustment block
    - Sets feature_effect_mode = MODEL_AFFECTING
    - Sets feature_version = FEATURE_VERSION
    - Sets candidate_patch_created = False
    - Sets production_modified = False
    """
    row = {k: v for k, v in phase48_row.items()}  # shallow copy

    # Overwrite model prob
    row["original_model_home_prob"] = adjustment.original_model_home_prob
    row["model_home_prob"] = adjustment.adjusted_model_home_prob

    # Injection metadata
    row["feature_version"] = FEATURE_VERSION
    row["feature_effect_mode"] = "MODEL_AFFECTING"
    row["candidate_patch_created"] = False
    row["production_modified"] = False

    # Adjustment block
    row["p0_feature_adjustment"] = {
        "feature_version": FEATURE_VERSION,
        "candidate_patch_created": False,
        "production_modified": False,
        "original_model_home_prob": adjustment.original_model_home_prob,
        "adjusted_model_home_prob": adjustment.adjusted_model_home_prob,
        "season_index_adjustment": adjustment.season_index_adjustment,
        "park_run_adjustment": adjustment.park_run_adjustment,
        "sp_fip_adjustment": adjustment.sp_fip_adjustment,
        "raw_total_adjustment": adjustment.raw_total_adjustment,
        "capped_total_adjustment": adjustment.capped_total_adjustment,
        "cap_applied": adjustment.cap_applied,
        "was_adjusted": adjustment.was_adjusted,
        "adjustment_reason": adjustment.adjustment_reason,
        "adjustment_components": adjustment.adjustment_components,
    }

    return row


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Batch injection runner
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class InjectionSummary:
    """Summary statistics from a batch injection run."""
    rows_total: int
    rows_adjusted: int
    rows_unchanged: int
    adjusted_rate: float
    mean_abs_adjustment: float
    max_abs_adjustment: float
    original_adjusted_correlation: float
    early_season_triggered: int
    park_factor_triggered: int
    sp_fip_triggered: int
    cap_applied_count: int
    candidate_patch_created: bool = False
    production_modified: bool = False
    feature_version: str = FEATURE_VERSION


def run_batch_injection(
    phase48_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], InjectionSummary]:
    """
    Apply P0 feature injection to all rows from Phase 48 JSONL.

    Returns:
        (phase50_rows, summary)

    Raises:
        ValueError: if a row contains forbidden fields in p0_features.
    """
    phase50_rows: list[dict[str, Any]] = []
    adjustments: list[AdjustmentResult] = []

    for row in phase48_rows:
        p0 = row.get("p0_features", {})
        base_prob = float(row.get("model_home_prob", 0.5))

        adj = apply_p0_feature_adjustment(base_prob, p0)
        p50_row = build_phase50_row(row, adj)
        phase50_rows.append(p50_row)
        adjustments.append(adj)

    # ── Summary statistics ────────────────────────────────────────────────────
    n = len(adjustments)
    if n == 0:
        return [], InjectionSummary(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0)

    adjusted_flags = [a.was_adjusted for a in adjustments]
    n_adj = sum(adjusted_flags)

    abs_adjs = [abs(a.capped_total_adjustment) for a in adjustments]
    mean_abs = float(sum(abs_adjs) / n)
    max_abs = float(max(abs_adjs))

    # Pearson correlation between original and adjusted probs
    orig = [a.original_model_home_prob for a in adjustments]
    adj_probs = [a.adjusted_model_home_prob for a in adjustments]
    corr = _pearson_corr(orig, adj_probs)

    early_season_triggered = sum(1 for a in adjustments if abs(a.season_index_adjustment) > 1e-9)
    park_factor_triggered  = sum(1 for a in adjustments if abs(a.park_run_adjustment) > 1e-9)
    sp_fip_triggered       = sum(1 for a in adjustments if abs(a.sp_fip_adjustment) > 1e-9)
    cap_applied_count      = sum(1 for a in adjustments if a.cap_applied)

    summary = InjectionSummary(
        rows_total=n,
        rows_adjusted=n_adj,
        rows_unchanged=n - n_adj,
        adjusted_rate=round(n_adj / n, 6),
        mean_abs_adjustment=round(mean_abs, 6),
        max_abs_adjustment=round(max_abs, 6),
        original_adjusted_correlation=round(corr, 6),
        early_season_triggered=early_season_triggered,
        park_factor_triggered=park_factor_triggered,
        sp_fip_triggered=sp_fip_triggered,
        cap_applied_count=cap_applied_count,
        candidate_patch_created=False,
        production_modified=False,
        feature_version=FEATURE_VERSION,
    )
    return phase50_rows, summary


def _pearson_corr(xs: list[float], ys: list[float]) -> float:
    """Simple Pearson correlation coefficient."""
    n = len(xs)
    if n < 2:
        return 1.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x < 1e-12 or den_y < 1e-12:
        return 1.0
    return num / (den_x * den_y)
