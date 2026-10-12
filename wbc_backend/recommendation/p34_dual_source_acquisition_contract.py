"""
P34 Dual Source Acquisition Contract
=====================================
Frozen gate constants, option status constants, and canonical dataclasses for the
P34 dual-source acquisition planning phase.

PAPER_ONLY=True  PRODUCTION_READY=False
No live data access. No fabricated odds or predictions. No real bets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Safety guards (immutable module-level constants)
# ---------------------------------------------------------------------------

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

P34_DUAL_SOURCE_ACQUISITION_PLAN_READY: str = "P34_DUAL_SOURCE_ACQUISITION_PLAN_READY"
P34_BLOCKED_NO_SAFE_PREDICTION_PATH: str = "P34_BLOCKED_NO_SAFE_PREDICTION_PATH"
P34_BLOCKED_NO_SAFE_ODDS_PATH: str = "P34_BLOCKED_NO_SAFE_ODDS_PATH"
P34_BLOCKED_LICENSE_PROVENANCE_UNSAFE: str = "P34_BLOCKED_LICENSE_PROVENANCE_UNSAFE"
P34_BLOCKED_CONTRACT_VIOLATION: str = "P34_BLOCKED_CONTRACT_VIOLATION"
P34_FAIL_INPUT_MISSING: str = "P34_FAIL_INPUT_MISSING"
P34_FAIL_NON_DETERMINISTIC: str = "P34_FAIL_NON_DETERMINISTIC"

ALL_P34_GATES: Tuple[str, ...] = (
    P34_DUAL_SOURCE_ACQUISITION_PLAN_READY,
    P34_BLOCKED_NO_SAFE_PREDICTION_PATH,
    P34_BLOCKED_NO_SAFE_ODDS_PATH,
    P34_BLOCKED_LICENSE_PROVENANCE_UNSAFE,
    P34_BLOCKED_CONTRACT_VIOLATION,
    P34_FAIL_INPUT_MISSING,
    P34_FAIL_NON_DETERMINISTIC,
)

# ---------------------------------------------------------------------------
# Acquisition option status constants
# ---------------------------------------------------------------------------

OPTION_READY_FOR_IMPLEMENTATION_PLAN: str = "OPTION_READY_FOR_IMPLEMENTATION_PLAN"
OPTION_REQUIRES_MANUAL_APPROVAL: str = "OPTION_REQUIRES_MANUAL_APPROVAL"
OPTION_REQUIRES_LICENSE_REVIEW: str = "OPTION_REQUIRES_LICENSE_REVIEW"
OPTION_BLOCKED_PROVENANCE: str = "OPTION_BLOCKED_PROVENANCE"
OPTION_BLOCKED_SCHEMA_GAP: str = "OPTION_BLOCKED_SCHEMA_GAP"
OPTION_REJECTED_FAKE_OR_LEAKAGE: str = "OPTION_REJECTED_FAKE_OR_LEAKAGE"

ALL_OPTION_STATUSES: Tuple[str, ...] = (
    OPTION_READY_FOR_IMPLEMENTATION_PLAN,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_BLOCKED_SCHEMA_GAP,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
)

# ---------------------------------------------------------------------------
# Leakage / implementation risk constants
# ---------------------------------------------------------------------------

LEAKAGE_NONE: str = "none"
LEAKAGE_LOW: str = "low"
LEAKAGE_MEDIUM: str = "medium"
LEAKAGE_HIGH: str = "high"
LEAKAGE_CONFIRMED: str = "confirmed"

RISK_LOW: str = "low"
RISK_MEDIUM: str = "medium"
RISK_HIGH: str = "high"

# ---------------------------------------------------------------------------
# Prediction required columns (joined input template)
# ---------------------------------------------------------------------------

PREDICTION_TEMPLATE_COLUMNS: Tuple[str, ...] = (
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "p_oof",
    "model_version",
    "fold_id",
    "source_prediction_ref",
    "generated_without_y_true",
)

# ---------------------------------------------------------------------------
# Odds required columns (joined input template)
# ---------------------------------------------------------------------------

ODDS_TEMPLATE_COLUMNS: Tuple[str, ...] = (
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "p_market",
    "odds_decimal",
    "sportsbook",
    "market_type",
    "closing_timestamp",
    "source_odds_ref",
    "license_ref",
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P34PredictionAcquisitionOption:
    """Describes a single candidate path for acquiring 2024 model predictions."""

    option_id: str
    source_name: str
    source_type: str  # "oof_rebuild" | "external_import" | "blocker"
    acquisition_method: str
    expected_columns: Tuple[str, ...]
    missing_columns: Tuple[str, ...]
    provenance_status: str
    license_status: str
    leakage_risk: str  # none | low | medium | high | confirmed
    implementation_risk: str  # low | medium | high
    estimated_coverage: float  # fraction 0.0–1.0 of 2024 games expected
    paper_only: bool = True
    production_ready: bool = False
    status: str = OPTION_READY_FOR_IMPLEMENTATION_PLAN
    blocker_if_skipped: str = ""
    notes: str = ""


@dataclass(frozen=True)
class P34OddsAcquisitionOption:
    """Describes a single candidate path for acquiring 2024 market closing odds."""

    option_id: str
    source_name: str
    source_type: str  # "licensed_export" | "paid_provider" | "repo_candidate" | "blocker"
    acquisition_method: str
    expected_columns: Tuple[str, ...]
    missing_columns: Tuple[str, ...]
    provenance_status: str
    license_status: str
    leakage_risk: str
    implementation_risk: str
    estimated_coverage: float
    paper_only: bool = True
    production_ready: bool = False
    status: str = OPTION_REQUIRES_LICENSE_REVIEW
    blocker_if_skipped: str = ""
    notes: str = ""


@dataclass
class P34DualSourcePlan:
    """Aggregated plan combining best prediction and odds acquisition paths."""

    prediction_options: List[P34PredictionAcquisitionOption] = field(default_factory=list)
    odds_options: List[P34OddsAcquisitionOption] = field(default_factory=list)
    best_prediction_option_id: str = ""
    best_odds_option_id: str = ""
    prediction_path_status: str = ""
    odds_path_status: str = ""
    paper_only: bool = True
    production_ready: bool = False
    plan_summary: str = ""
    season: int = 2024


@dataclass(frozen=True)
class P34SchemaRequirement:
    """Schema contract for the two import templates (prediction + odds)."""

    season: int
    prediction_columns: Tuple[str, ...]
    odds_columns: Tuple[str, ...]
    paper_only: bool = True
    production_ready: bool = False

    def all_columns(self) -> Tuple[str, ...]:
        return self.prediction_columns + self.odds_columns


@dataclass
class P34GateResult:
    """Final gate decision for P34."""

    gate: str = P34_DUAL_SOURCE_ACQUISITION_PLAN_READY
    prediction_path_status: str = ""
    odds_path_status: str = ""
    license_risk: str = ""
    blocker_reason: str = ""
    paper_only: bool = True
    production_ready: bool = False
    next_phase: str = "P35_DUAL_SOURCE_IMPORT_VALIDATION"
    artifacts: List[str] = field(default_factory=list)
    season: int = 2024
