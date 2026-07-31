"""
wbc_backend/recommendation/p29_density_expansion_contract.py

P29 Source Coverage Density Expansion — frozen dataclasses, gate constants,
and audit status constants.

All dataclasses enforce paper_only=True and production_ready=False.
This module is research-only. No production deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Tuple

# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

P29_DENSITY_EXPANSION_PLAN_READY: str = "P29_DENSITY_EXPANSION_PLAN_READY"
P29_BLOCKED_NO_SAFE_EXPANSION_PATH: str = "P29_BLOCKED_NO_SAFE_EXPANSION_PATH"
P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT: str = "P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT"
P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY: str = "P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY"
P29_BLOCKED_CONTRACT_VIOLATION: str = "P29_BLOCKED_CONTRACT_VIOLATION"
P29_FAIL_INPUT_MISSING: str = "P29_FAIL_INPUT_MISSING"
P29_FAIL_NON_DETERMINISTIC: str = "P29_FAIL_NON_DETERMINISTIC"

_VALID_P29_GATES: FrozenSet[str] = frozenset({
    P29_DENSITY_EXPANSION_PLAN_READY,
    P29_BLOCKED_NO_SAFE_EXPANSION_PATH,
    P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT,
    P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
    P29_BLOCKED_CONTRACT_VIOLATION,
    P29_FAIL_INPUT_MISSING,
    P29_FAIL_NON_DETERMINISTIC,
})

# ---------------------------------------------------------------------------
# Audit status constants
# ---------------------------------------------------------------------------

DENSITY_EXPANSION_PLAN_FEASIBLE: str = "DENSITY_EXPANSION_PLAN_FEASIBLE"
DENSITY_EXPANSION_SOURCE_PATH_FOUND: str = "DENSITY_EXPANSION_SOURCE_PATH_FOUND"
DENSITY_EXPANSION_POLICY_PATH_RISKY: str = "DENSITY_EXPANSION_POLICY_PATH_RISKY"
DENSITY_EXPANSION_NO_PATH_FOUND: str = "DENSITY_EXPANSION_NO_PATH_FOUND"
DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE: str = "DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE"

_VALID_DENSITY_STATUSES: FrozenSet[str] = frozenset({
    DENSITY_EXPANSION_PLAN_FEASIBLE,
    DENSITY_EXPANSION_SOURCE_PATH_FOUND,
    DENSITY_EXPANSION_POLICY_PATH_RISKY,
    DENSITY_EXPANSION_NO_PATH_FOUND,
    DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
})

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

TARGET_ACTIVE_ENTRIES_DEFAULT: int = 1500
CURRENT_ACTIVE_ENTRIES_P28: int = 324
CURRENT_POLICY_ID_P28: str = "e0p0500_s0p0025_k0p10_o2p50"

# Policy sensitivity risk flags
MAX_ODDS_FOR_SAFE_EXPANSION: float = 4.00
MIN_EDGE_SAFE_EXPANSION: float = 0.02


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P29DensityDiagnosis:
    """Snapshot of current density problem diagnosis."""

    current_active_entries: int
    target_active_entries: int
    density_gap: int
    current_active_per_day: float
    target_active_per_day: float
    total_source_rows: int
    active_conversion_rate: float  # active / total_source_rows
    n_blocked_edge: int
    n_blocked_odds: int
    n_blocked_unknown: int
    n_dates_zero_active: int
    n_dates_sparse_active: int
    primary_blocker: str   # "edge_threshold" | "odds_cap" | "no_source_rows" | "unknown"
    diagnosis_note: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P29DensityDiagnosis: paper_only must be True")
        if self.production_ready:
            raise ValueError("P29DensityDiagnosis: production_ready must be False")


@dataclass(frozen=True)
class P29PolicySensitivityCandidate:
    """Single policy candidate from sensitivity grid exploration."""

    policy_id: str
    edge_threshold: float
    odds_decimal_max: float
    max_stake_cap: float
    kelly_fraction: float
    n_active_entries: int
    active_entry_lift_vs_current: int
    estimated_total_stake_units: float
    hit_rate: float
    roi_units: float
    max_drawdown_pct: float
    gate_reason_counts: str   # JSON string of counts dict
    risk_flags: str           # comma-separated risk flag labels
    is_deployment_ready: bool   # always False for exploratory candidates
    exploratory_only: bool      # always True
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P29PolicySensitivityCandidate: paper_only must be True")
        if self.production_ready:
            raise ValueError("P29PolicySensitivityCandidate: production_ready must be False")
        if self.is_deployment_ready:
            raise ValueError("P29PolicySensitivityCandidate: is_deployment_ready must be False")
        if not self.exploratory_only:
            raise ValueError("P29PolicySensitivityCandidate: exploratory_only must be True")


@dataclass(frozen=True)
class P29SourceCoverageCandidate:
    """A candidate additional source for data coverage expansion."""

    source_path: str
    source_type: str        # "additional_season" | "alternate_odds" | "wider_date_range" | "oof_predictions"
    date_range_start: str
    date_range_end: str
    estimated_new_rows: int
    has_required_columns: bool
    has_y_true: bool
    has_game_id: bool
    has_odds: bool
    coverage_note: str
    is_safe_to_use: bool    # False if provenance unknown
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P29SourceCoverageCandidate: paper_only must be True")
        if self.production_ready:
            raise ValueError("P29SourceCoverageCandidate: production_ready must be False")


@dataclass(frozen=True)
class P29DensityExpansionPlan:
    """Aggregated P29 expansion plan."""

    current_active_entries: int
    target_active_entries: int
    density_gap: int
    current_active_per_day: float
    target_active_per_day: float
    available_true_date_rows: int
    current_policy_id: str
    policy_thresholds_tested: int
    best_policy_candidate_id: str
    best_policy_candidate_active_entries: int
    source_expansion_estimated_entries: int
    n_source_candidates_found: int
    n_source_candidates_safe: int
    recommended_next_action: str
    expansion_feasibility_note: str
    paper_only: bool
    production_ready: bool
    audit_status: str
    p29_gate: str

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P29DensityExpansionPlan: paper_only must be True")
        if self.production_ready:
            raise ValueError("P29DensityExpansionPlan: production_ready must be False")
        if self.p29_gate not in _VALID_P29_GATES:
            raise ValueError(f"P29DensityExpansionPlan: invalid p29_gate={self.p29_gate!r}")
        if self.audit_status not in _VALID_DENSITY_STATUSES:
            raise ValueError(f"P29DensityExpansionPlan: invalid audit_status={self.audit_status!r}")


@dataclass(frozen=True)
class P29DensityExpansionGateResult:
    """Final gate result for P29 density expansion planning."""

    p29_gate: str
    current_active_entries: int
    target_active_entries: int
    density_gap: int
    best_policy_candidate_active_entries: int
    source_expansion_estimated_entries: int
    recommended_next_action: str
    audit_status: str
    blocker_reason: str
    paper_only: bool
    production_ready: bool

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("P29DensityExpansionGateResult: paper_only must be True")
        if self.production_ready:
            raise ValueError("P29DensityExpansionGateResult: production_ready must be False")
        if self.p29_gate not in _VALID_P29_GATES:
            raise ValueError(f"P29DensityExpansionGateResult: invalid p29_gate={self.p29_gate!r}")
        if self.audit_status not in _VALID_DENSITY_STATUSES:
            raise ValueError(f"P29DensityExpansionGateResult: invalid audit_status={self.audit_status!r}")
