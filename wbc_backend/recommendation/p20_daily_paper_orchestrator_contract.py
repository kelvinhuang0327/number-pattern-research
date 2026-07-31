"""
wbc_backend/recommendation/p20_daily_paper_orchestrator_contract.py

P20 Daily PAPER MLB Recommendation Orchestrator — frozen contract definitions.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Gate decision constants
# ---------------------------------------------------------------------------

P20_DAILY_PAPER_ORCHESTRATOR_READY = "P20_DAILY_PAPER_ORCHESTRATOR_READY"
P20_BLOCKED_P16_6_NOT_READY = "P20_BLOCKED_P16_6_NOT_READY"
P20_BLOCKED_P19_NOT_READY = "P20_BLOCKED_P19_NOT_READY"
P20_BLOCKED_P17_REPLAY_NOT_READY = "P20_BLOCKED_P17_REPLAY_NOT_READY"
P20_BLOCKED_CONTRACT_VIOLATION = "P20_BLOCKED_CONTRACT_VIOLATION"
P20_FAIL_INPUT_MISSING = "P20_FAIL_INPUT_MISSING"
P20_FAIL_NON_DETERMINISTIC = "P20_FAIL_NON_DETERMINISTIC"

# ---------------------------------------------------------------------------
# Step name constants
# ---------------------------------------------------------------------------

STEP_P16_6_RECOMMENDATION_GATE = "P16_6_RECOMMENDATION_GATE"
STEP_P19_IDENTITY_JOIN_REPAIR = "P19_IDENTITY_JOIN_REPAIR"
STEP_P17_REPLAY_WITH_P19_IDENTITY = "P17_REPLAY_WITH_P19_IDENTITY"
STEP_P20_DAILY_SUMMARY = "P20_DAILY_SUMMARY"

REQUIRED_STEP_NAMES = [
    STEP_P16_6_RECOMMENDATION_GATE,
    STEP_P19_IDENTITY_JOIN_REPAIR,
    STEP_P17_REPLAY_WITH_P19_IDENTITY,
    STEP_P20_DAILY_SUMMARY,
]

# Expected upstream gate values
EXPECTED_P16_6_GATE = "P16_6_PAPER_RECOMMENDATION_GATE_READY"
EXPECTED_P19_GATE = "P19_IDENTITY_JOIN_REPAIR_READY"
EXPECTED_P17_REPLAY_GATE = "P17_PAPER_LEDGER_READY"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P20PipelineStepResult:
    """Result of a single pipeline step."""

    step_name: str
    gate_decision: str
    passed: bool
    artifact_paths: tuple[str, ...] = field(default_factory=tuple)
    error_message: Optional[str] = None


@dataclass(frozen=True)
class P20ArtifactManifest:
    """Manifest of all artifacts produced / consumed in a P20 daily run."""

    run_date: str
    artifacts: tuple[dict, ...] = field(default_factory=tuple)
    total_artifacts: int = 0
    required_artifacts_present: int = 0
    required_artifacts_missing: int = 0
    manifest_sha256: str = ""
    paper_only: bool = True
    production_ready: bool = False


@dataclass(frozen=True)
class P20DailyPaperRunSummary:
    """Aggregated daily paper run summary — all required fields."""

    run_date: str
    p20_gate: str

    # Upstream gate sources
    source_p16_6_gate: str
    source_p19_gate: str
    source_p17_replay_gate: str

    # Row counts
    n_input_rows: int
    n_recommended_rows: int
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int

    # Identity join
    settlement_join_method: str
    game_id_coverage: float

    # PnL
    total_stake_units: float
    total_pnl_units: float
    roi_units: float
    hit_rate: float

    # Risk
    max_drawdown_pct: float
    sharpe_ratio: float

    # Safety invariants
    paper_only: bool
    production_ready: bool

    # Artifact tracking
    generated_artifact_count: int

    # Optional extras
    avg_edge: float = 0.0
    avg_odds_decimal: float = 0.0
    bankroll_units: float = 100.0
    script_version: str = "P20_DAILY_PAPER_ORCHESTRATOR_V1"
    generated_at: str = ""


@dataclass(frozen=True)
class P20DailyPaperGateResult:
    """Final gate output for P20 daily paper orchestrator."""

    run_date: str
    p20_gate: str
    paper_only: bool
    production_ready: bool
    n_recommended_rows: int
    n_active_paper_entries: int
    n_settled_win: int
    n_settled_loss: int
    n_unsettled: int
    roi_units: float
    hit_rate: float
    settlement_join_method: str
    game_id_coverage: float
    step_results: tuple[P20PipelineStepResult, ...] = field(default_factory=tuple)
    error_message: Optional[str] = None
    script_version: str = "P20_DAILY_PAPER_ORCHESTRATOR_V1"
    generated_at: str = ""
