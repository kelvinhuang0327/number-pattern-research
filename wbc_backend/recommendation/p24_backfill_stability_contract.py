"""
wbc_backend/recommendation/p24_backfill_stability_contract.py

P24 Backfill Performance Stability Audit — frozen dataclass contracts.

All dataclasses enforce paper_only=True and production_ready=False via
__post_init__ safety guards.

Audit findings:
- Detects duplicate source replay across dates
- Measures per-date ROI / hit-rate variance
- Determines whether backfill is genuine multi-date evidence

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Gate decisions
# ---------------------------------------------------------------------------

P24_BACKFILL_STABILITY_AUDIT_READY = "P24_BACKFILL_STABILITY_AUDIT_READY"
P24_BLOCKED_DUPLICATE_SOURCE_REPLAY = "P24_BLOCKED_DUPLICATE_SOURCE_REPLAY"
P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES = (
    "P24_BLOCKED_INSUFFICIENT_INDEPENDENT_DATES"
)
P24_BLOCKED_CONTRACT_VIOLATION = "P24_BLOCKED_CONTRACT_VIOLATION"
P24_FAIL_INPUT_MISSING = "P24_FAIL_INPUT_MISSING"
P24_FAIL_NON_DETERMINISTIC = "P24_FAIL_NON_DETERMINISTIC"

# ---------------------------------------------------------------------------
# Audit status values
# ---------------------------------------------------------------------------

STABILITY_ACCEPTABLE = "STABILITY_ACCEPTABLE"
STABILITY_DUPLICATE_SOURCE_SUSPECTED = "STABILITY_DUPLICATE_SOURCE_SUSPECTED"
STABILITY_INSUFFICIENT_VARIANCE = "STABILITY_INSUFFICIENT_VARIANCE"
STABILITY_INSUFFICIENT_INDEPENDENT_DATES = (
    "STABILITY_INSUFFICIENT_INDEPENDENT_DATES"
)
STABILITY_SOURCE_INTEGRITY_BLOCKED = "STABILITY_SOURCE_INTEGRITY_BLOCKED"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

MIN_INDEPENDENT_SOURCE_DATES = 2
DUPLICATE_SOURCE_MAJORITY_THRESHOLD = 0.5  # >50% dates in duplicate group → block


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P24DatePerformanceProfile:
    """Per-date performance metrics extracted from P23 results."""

    run_date: str
    n_active_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int
    total_stake_units: float
    total_pnl_units: float
    roi_units: float
    hit_rate: float
    game_id_coverage: float
    source_hash_content: str  # sha256 excl. run_date column
    game_id_set_hash: str     # sha256 of sorted game_id list
    game_date_range_str: str  # "YYYY-MM-DD:YYYY-MM-DD" from source
    run_date_matches_game_date: bool
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P24DatePerformanceProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError(
                "P24DatePerformanceProfile: production_ready must be False"
            )


@dataclass(frozen=True)
class P24DuplicateSourceFinding:
    """Documents a group of dates sharing identical source content."""

    group_id: int
    content_hash: str
    game_id_set_hash: str
    dates_in_group: tuple  # tuple of run_date strings
    n_dates: int
    representative_game_date_range: str
    is_date_mismatch: bool  # game_date != run_date for all dates in group
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P24DuplicateSourceFinding: paper_only must be True")
        if self.production_ready:
            raise ValueError(
                "P24DuplicateSourceFinding: production_ready must be False"
            )


@dataclass(frozen=True)
class P24SourceIntegrityProfile:
    """Source integrity audit summary across all dates."""

    n_dates_audited: int
    n_independent_source_dates: int
    n_duplicate_source_groups: int
    source_hash_unique_count: int
    source_hash_duplicate_count: int
    game_id_set_unique_count: int
    all_dates_date_mismatch: bool  # True if game_date != run_date for every date
    any_date_date_mismatch: bool
    duplicate_findings: tuple  # tuple of P24DuplicateSourceFinding
    audit_status: str
    blocker_reason: str
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P24SourceIntegrityProfile: paper_only must be True")
        if self.production_ready:
            raise ValueError(
                "P24SourceIntegrityProfile: production_ready must be False"
            )


@dataclass(frozen=True)
class P24StabilityAuditSummary:
    """Aggregate stability audit summary across all 12 replay dates."""

    date_start: str
    date_end: str
    n_dates_audited: int
    n_independent_source_dates: int
    n_duplicate_source_groups: int
    # Aggregate performance
    aggregate_roi_units: float
    aggregate_hit_rate: float
    total_stake_units: float
    total_pnl_units: float
    # Variance metrics
    roi_std_by_date: float
    roi_min_by_date: float
    roi_max_by_date: float
    hit_rate_std_by_date: float
    hit_rate_min_by_date: float
    hit_rate_max_by_date: float
    active_entry_std_by_date: float
    active_entry_min_by_date: int
    active_entry_max_by_date: int
    # Source integrity
    source_hash_unique_count: int
    source_hash_duplicate_count: int
    all_dates_date_mismatch: bool
    # Audit result
    audit_status: str
    blocker_reason: str
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P24StabilityAuditSummary: paper_only must be True")
        if self.production_ready:
            raise ValueError(
                "P24StabilityAuditSummary: production_ready must be False"
            )


@dataclass(frozen=True)
class P24StabilityGateResult:
    """Final P24 gate decision."""

    p24_gate: str
    audit_status: str
    date_start: str
    date_end: str
    n_dates_audited: int
    n_independent_source_dates: int
    n_duplicate_source_groups: int
    source_hash_unique_count: int
    source_hash_duplicate_count: int
    roi_std_by_date: float
    hit_rate_std_by_date: float
    blocker_reason: str
    recommended_next_action: str
    paper_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P24StabilityGateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError(
                "P24StabilityGateResult: production_ready must be False"
            )
