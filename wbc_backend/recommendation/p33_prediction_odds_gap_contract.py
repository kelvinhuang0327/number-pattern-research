"""
P33 Prediction/Odds Gap Contract
=================================
Defines all frozen gate constants, source-status constants, required joined
input field specifications, and the canonical dataclasses used throughout the
P33 2024 Prediction/Odds Gap Analysis pipeline.

PAPER_ONLY — No live odds, no production bets, no fabrication of missing data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Safety Guards
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

# ---------------------------------------------------------------------------
# Gate Constants  (frozen strings — never mutate at runtime)
# ---------------------------------------------------------------------------
P33_PREDICTION_ODDS_GAP_PLAN_READY: str = "P33_PREDICTION_ODDS_GAP_PLAN_READY"
P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE: str = "P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE"
P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE: str = (
    "P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE"
)
P33_BLOCKED_LICENSE_PROVENANCE_UNSAFE: str = (
    "P33_BLOCKED_LICENSE_PROVENANCE_UNSAFE"
)
P33_BLOCKED_SCHEMA_GAP: str = "P33_BLOCKED_SCHEMA_GAP"
P33_BLOCKED_CONTRACT_VIOLATION: str = "P33_BLOCKED_CONTRACT_VIOLATION"
P33_FAIL_INPUT_MISSING: str = "P33_FAIL_INPUT_MISSING"
P33_FAIL_NON_DETERMINISTIC: str = "P33_FAIL_NON_DETERMINISTIC"

# Ordered list of expected gate values for downstream pipeline checks
ALL_P33_GATE_VALUES: List[str] = [
    P33_PREDICTION_ODDS_GAP_PLAN_READY,
    P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE,
    P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
    P33_BLOCKED_LICENSE_PROVENANCE_UNSAFE,
    P33_BLOCKED_SCHEMA_GAP,
    P33_BLOCKED_CONTRACT_VIOLATION,
    P33_FAIL_INPUT_MISSING,
    P33_FAIL_NON_DETERMINISTIC,
]

# ---------------------------------------------------------------------------
# Source Status Constants
# ---------------------------------------------------------------------------
SOURCE_READY: str = "SOURCE_READY"
SOURCE_PARTIAL: str = "SOURCE_PARTIAL"
SOURCE_MISSING: str = "SOURCE_MISSING"
SOURCE_BLOCKED_LICENSE: str = "SOURCE_BLOCKED_LICENSE"
SOURCE_BLOCKED_SCHEMA: str = "SOURCE_BLOCKED_SCHEMA"
SOURCE_UNKNOWN: str = "SOURCE_UNKNOWN"

ALL_SOURCE_STATUSES: List[str] = [
    SOURCE_READY,
    SOURCE_PARTIAL,
    SOURCE_MISSING,
    SOURCE_BLOCKED_LICENSE,
    SOURCE_BLOCKED_SCHEMA,
    SOURCE_UNKNOWN,
]

# ---------------------------------------------------------------------------
# Required Joined Input Field Specification
# ---------------------------------------------------------------------------
REQUIRED_JOINED_INPUT_FIELDS: List[str] = [
    "game_id",
    "game_date",
    "home_team",
    "away_team",
    "y_true_home_win",
    "p_model",
    "p_oof",
    "p_market",
    "odds_decimal",
    "source_prediction_ref",
    "source_odds_ref",
    "paper_only",
    "production_ready",
]

# Fields whose presence in a joined input frame indicates potential data leakage.
# The auditor will block any frame containing columns that start with these prefixes.
FORBIDDEN_LEAKAGE_PREFIXES: List[str] = [
    "future_",
    "postseason_",
    "final_",
    "actual_outcome",
    "result_",
]

# Columns from known 2025/2026 datasets that must NOT be copied into 2024 input
FORBIDDEN_CROSSYEAR_COLUMNS: List[str] = [
    "season_2025",
    "season_2026",
    "dry_run_2026",
    "prediction_time_utc_2026",
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P33RequiredJoinedInputSpec:
    """
    The canonical specification for a valid 2024 joined input frame.
    Immutable — used as a reference document throughout the pipeline.
    """

    required_fields: tuple = tuple(REQUIRED_JOINED_INPUT_FIELDS)
    season: int = 2024
    paper_only: bool = True
    production_ready: bool = False
    description: str = (
        "2024 MLB joined input frame: game identity + outcomes + "
        "pre-game model predictions + pre-closing market odds. "
        "No future data. No fabrication."
    )


@dataclass(frozen=True)
class P33PredictionSourceCandidate:
    """
    Represents a single candidate file/path that might contain 2024 prediction
    data (model probabilities, OOF predictions, etc.).
    """

    candidate_id: str
    file_path: str
    detected_season: Optional[int]
    has_game_id_column: bool
    has_p_model_column: bool
    has_p_oof_column: bool
    detected_columns: tuple
    row_count: int
    status: str  # one of ALL_SOURCE_STATUSES
    blocker_reason: str
    is_dry_run: bool
    is_paper_only: bool
    year_verified: bool


@dataclass(frozen=True)
class P33OddsSourceCandidate:
    """
    Represents a single candidate file/path that might contain 2024 market
    odds (moneylines, closing odds, etc.).
    """

    candidate_id: str
    file_path: str
    detected_season: Optional[int]
    has_game_id_column: bool
    has_moneyline_column: bool
    has_closing_odds_column: bool
    detected_columns: tuple
    row_count: int
    status: str  # one of ALL_SOURCE_STATUSES
    blocker_reason: str
    sportsbook_reference: str
    year_verified: bool


@dataclass
class P33SourceGapSummary:
    """
    Aggregated result of scanning all known data directories for 2024
    prediction and odds sources.
    """

    season: int = 2024
    prediction_candidates_found: int = 0
    odds_candidates_found: int = 0
    prediction_ready_count: int = 0
    odds_ready_count: int = 0
    prediction_blocked_count: int = 0
    odds_blocked_count: int = 0
    prediction_missing: bool = True
    odds_missing: bool = True
    prediction_gap_reason: str = ""
    odds_gap_reason: str = ""
    prediction_candidates: List[P33PredictionSourceCandidate] = field(
        default_factory=list
    )
    odds_candidates: List[P33OddsSourceCandidate] = field(default_factory=list)
    scanned_paths: List[str] = field(default_factory=list)
    paper_only: bool = True
    production_ready: bool = False


@dataclass
class P33GateResult:
    """
    Final gate result emitted by the P33 pipeline. Persisted to disk as
    p33_gate_result.json.
    """

    gate: str
    season: int = 2024
    prediction_gap_blocked: bool = False
    odds_gap_blocked: bool = False
    schema_gap_blocked: bool = False
    license_blocked: bool = False
    blocker_reason: str = ""
    artifacts: List[str] = field(default_factory=list)
    paper_only: bool = True
    production_ready: bool = False
    next_phase: str = "P34_DUAL_SOURCE_ACQUISITION_PLAN"
