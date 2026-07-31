"""
wbc_backend/recommendation/p28_true_date_stability_contract.py

P28 True-Date Backfill Performance Stability Audit — Type Definitions and Gate Constants.

Gate policy:
  P28_TRUE_DATE_STABILITY_AUDIT_READY          — audit complete, all checks pass
  P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT         — total_active_entries < min_sample_size
  P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE        — segment ROI std excessively high
  P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT           — max_drawdown_pct > 25%
  P28_BLOCKED_CONTRACT_VIOLATION               — safety policy violation detected
  P28_FAIL_INPUT_MISSING                       — required P27 inputs not found
  P28_FAIL_NON_DETERMINISTIC                   — two runs produce different results

paper_only=True and production_ready=False are ENFORCED at construction time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

P28_TRUE_DATE_STABILITY_AUDIT_READY = "P28_TRUE_DATE_STABILITY_AUDIT_READY"
P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT = "P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT"
P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE = "P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE"
P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT = "P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT"
P28_BLOCKED_CONTRACT_VIOLATION = "P28_BLOCKED_CONTRACT_VIOLATION"
P28_FAIL_INPUT_MISSING = "P28_FAIL_INPUT_MISSING"
P28_FAIL_NON_DETERMINISTIC = "P28_FAIL_NON_DETERMINISTIC"

_VALID_GATES = frozenset({
    P28_TRUE_DATE_STABILITY_AUDIT_READY,
    P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
    P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE,
    P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT,
    P28_BLOCKED_CONTRACT_VIOLATION,
    P28_FAIL_INPUT_MISSING,
    P28_FAIL_NON_DETERMINISTIC,
})

# Audit status strings
STABILITY_ACCEPTABLE_FOR_RESEARCH = "STABILITY_ACCEPTABLE_FOR_RESEARCH"
STABILITY_SAMPLE_SIZE_INSUFFICIENT = "STABILITY_SAMPLE_SIZE_INSUFFICIENT"
STABILITY_SEGMENT_VARIANCE_UNSTABLE = "STABILITY_SEGMENT_VARIANCE_UNSTABLE"
STABILITY_DRAWDOWN_RISK_HIGH = "STABILITY_DRAWDOWN_RISK_HIGH"
STABILITY_REQUIRES_MORE_DATA = "STABILITY_REQUIRES_MORE_DATA"

_VALID_AUDIT_STATUSES = frozenset({
    STABILITY_ACCEPTABLE_FOR_RESEARCH,
    STABILITY_SAMPLE_SIZE_INSUFFICIENT,
    STABILITY_SEGMENT_VARIANCE_UNSTABLE,
    STABILITY_DRAWDOWN_RISK_HIGH,
    STABILITY_REQUIRES_MORE_DATA,
})

# Advisory threshold — research readiness, not engineering failure
MIN_SAMPLE_SIZE_ADVISORY: int = 1500

# Risk thresholds
MAX_DRAWDOWN_PCT_LIMIT: float = 25.0
HIGH_LOSING_STREAK_DAYS: int = 7


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P28DateStabilityProfile:
    """Per-date stability metrics derived from date_results.csv."""
    run_date: str
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    roi_units: float
    hit_rate: float
    total_stake_units: float
    total_pnl_units: float
    is_sparse: bool          # True if n_active_paper_entries == 0
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28DateStabilityProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28DateStabilityProfile: production_ready must be False")


@dataclass(frozen=True)
class P28SegmentStabilityProfile:
    """Per-segment stability metrics derived from segment_results.csv."""
    segment_index: int
    date_start: str
    date_end: str
    total_active_entries: int
    total_settled_win: int
    total_settled_loss: int
    total_stake_units: float
    total_pnl_units: float
    roi_units: float
    hit_rate: float
    is_sparse: bool           # True if total_active_entries < 50
    is_blocked: bool
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28SegmentStabilityProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28SegmentStabilityProfile: production_ready must be False")


@dataclass(frozen=True)
class P28SampleDensityProfile:
    """Summary of sample density across the full backfill range."""
    n_dates_total: int
    n_dates_ready: int
    n_dates_blocked: int
    n_dates_sparse: int
    n_segments: int
    n_segments_sparse: int
    total_active_entries: int
    min_sample_size_advisory: int
    sample_size_pass: bool
    daily_active_min: float
    daily_active_max: float
    daily_active_mean: float
    daily_active_std: float
    sparse_date_list: Tuple[str, ...]
    sparse_segment_list: Tuple[str, ...]
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28SampleDensityProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28SampleDensityProfile: production_ready must be False")


@dataclass(frozen=True)
class P28PerformanceVarianceProfile:
    """Summary of ROI / hit-rate variance across segments and dates."""
    segment_roi_min: float
    segment_roi_max: float
    segment_roi_mean: float
    segment_roi_std: float
    segment_hit_rate_min: float
    segment_hit_rate_max: float
    segment_hit_rate_std: float
    daily_roi_min: float
    daily_roi_max: float
    daily_roi_mean: float
    daily_roi_std: float
    daily_hit_rate_min: float
    daily_hit_rate_max: float
    daily_hit_rate_std: float
    n_positive_roi_segments: int
    n_negative_roi_segments: int
    bootstrap_roi_ci_low_95: float
    bootstrap_roi_ci_high_95: float
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28PerformanceVarianceProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28PerformanceVarianceProfile: production_ready must be False")


@dataclass(frozen=True)
class P28RiskProfile:
    """Risk and drawdown metrics."""
    max_drawdown_units: float
    max_drawdown_pct: float
    max_consecutive_losing_days: int
    total_losing_days: int
    total_winning_days: int
    total_neutral_days: int
    loss_cluster_summary: str     # human-readable note about loss clusters
    drawdown_exceeds_limit: bool  # max_drawdown_pct > MAX_DRAWDOWN_PCT_LIMIT
    high_losing_streak: bool      # max_consecutive_losing_days >= HIGH_LOSING_STREAK_DAYS
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28RiskProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28RiskProfile: production_ready must be False")


@dataclass(frozen=True)
class P28StabilityAuditSummary:
    """Full P28 audit summary combining all analysis dimensions."""
    # Date / segment coverage
    n_dates_total: int
    n_dates_ready: int
    n_dates_blocked: int
    n_segments: int

    # Sample density
    total_active_entries: int
    min_sample_size_advisory: int
    sample_size_pass: bool

    # Performance
    aggregate_roi_units: float
    aggregate_hit_rate: float
    segment_roi_min: float
    segment_roi_max: float
    segment_roi_std: float

    # Daily density
    daily_active_min: float
    daily_active_max: float
    daily_active_std: float

    # Risk
    max_drawdown_units: float
    max_drawdown_pct: float
    max_consecutive_losing_days: int

    # Bootstrap CI
    bootstrap_roi_ci_low_95: float
    bootstrap_roi_ci_high_95: float

    # Policy
    paper_only: bool
    production_ready: bool
    audit_status: str
    blocker_reason: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28StabilityAuditSummary: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28StabilityAuditSummary: production_ready must be False")
        if self.audit_status not in _VALID_AUDIT_STATUSES:
            raise ValueError(
                f"P28StabilityAuditSummary: unknown audit_status '{self.audit_status}'"
            )


@dataclass(frozen=True)
class P28GateResult:
    """Final P28 gate decision with all audit fields attached."""
    p28_gate: str
    n_dates_total: int
    n_dates_ready: int
    n_dates_blocked: int
    n_segments: int
    total_active_entries: int
    min_sample_size_advisory: int
    sample_size_pass: bool
    aggregate_roi_units: float
    aggregate_hit_rate: float
    segment_roi_std: float
    daily_active_std: float
    max_drawdown_units: float
    max_drawdown_pct: float
    max_consecutive_losing_days: int
    bootstrap_roi_ci_low_95: float
    bootstrap_roi_ci_high_95: float
    paper_only: bool
    production_ready: bool
    audit_status: str
    blocker_reason: str
    generated_at: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P28GateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P28GateResult: production_ready must be False")
        if self.p28_gate not in _VALID_GATES:
            raise ValueError(f"P28GateResult: unknown gate '{self.p28_gate}'")
        if self.audit_status not in _VALID_AUDIT_STATUSES:
            raise ValueError(
                f"P28GateResult: unknown audit_status '{self.audit_status}'"
            )
