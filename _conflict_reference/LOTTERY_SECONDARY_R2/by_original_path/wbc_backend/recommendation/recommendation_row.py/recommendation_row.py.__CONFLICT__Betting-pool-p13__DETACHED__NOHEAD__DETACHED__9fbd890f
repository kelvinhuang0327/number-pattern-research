"""MLB → TSL Recommendation Row Contract.

Typed dataclass defining the canonical output of the MLB→TSL paper-only
recommendation pipeline.

PAPER_ONLY = True is the permanent default.  Production enablement (P38) is
still NO_GO — this module must NOT be changed to set paper_only=False without
the full governance gate being cleared.

Usage:
    row = MlbTslRecommendationRow(
        game_id="2026-05-11-LAA-CLE",
        game_start_utc=datetime(..., tzinfo=timezone.utc),
        model_prob_home=0.52,
        model_prob_away=0.48,
        model_ensemble_version="v1-paper",
        tsl_market="moneyline",
        tsl_line=None,
        tsl_side="home",
        tsl_decimal_odds=1.90,
        edge_pct=0.02,
        kelly_fraction=0.02,
        stake_units_paper=0.5,
        gate_status="BLOCKED_PAPER_ONLY",
        gate_reasons=["TSL live source 403 Forbidden"],
        generated_at_utc=datetime.now(timezone.utc),
        source_trace={"mlb": "statsapi.mlb.com", "tsl": "blocked_403"},
    )
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Optional


# Valid gate status values — extend only through governance review.
VALID_GATE_STATUSES = frozenset(
    {
        "PASS",
        "BLOCKED_BRIER",
        "BLOCKED_ECE",
        "BLOCKED_PAPER_ONLY",
        "BLOCKED_TSL_SOURCE",
        "BLOCKED_MLB_SOURCE",
        "BLOCKED_MODEL_VERSION",
        "BLOCKED_KELLY_ZERO",
        "BLOCKED_EDGE_NEGATIVE",
        # P4: simulation gate statuses
        "BLOCKED_SIMULATION_GATE",
        "BLOCKED_NO_SIMULATION",
    }
)


@dataclass
class MlbTslRecommendationRow:
    """Canonical MLB→TSL paper-only recommendation row.

    All instances are paper-only by default.  The ``paper_only`` field must
    remain ``True`` until P38 production-enablement gate is formally cleared.
    """

    # ── Game identity ─────────────────────────────────────────────────────────
    game_id: str
    game_start_utc: datetime

    # ── Model probabilities ───────────────────────────────────────────────────
    model_prob_home: float
    model_prob_away: float
    model_ensemble_version: str

    # ── TSL market ────────────────────────────────────────────────────────────
    tsl_market: Literal["moneyline", "run_line", "total", "f5", "f5_total", "odd_even"]
    tsl_line: Optional[float]
    tsl_side: Literal["home", "away", "over", "under", "odd", "even"]
    tsl_decimal_odds: float

    # ── Edge / Kelly ──────────────────────────────────────────────────────────
    edge_pct: float               # (model_prob - implied_prob), after vig removal
    kelly_fraction: float         # fractional Kelly (capped; 0.0 when no edge)
    stake_units_paper: float      # paper-only stake in units (kelly_fraction * bankroll_units)

    # ── Gate ──────────────────────────────────────────────────────────────────
    gate_status: Literal[
        "PASS",
        "BLOCKED_BRIER",
        "BLOCKED_ECE",
        "BLOCKED_PAPER_ONLY",
        "BLOCKED_TSL_SOURCE",
        "BLOCKED_MLB_SOURCE",
        "BLOCKED_MODEL_VERSION",
        "BLOCKED_KELLY_ZERO",
        "BLOCKED_EDGE_NEGATIVE",
        "BLOCKED_SIMULATION_GATE",
        "BLOCKED_NO_SIMULATION",
    ]
    gate_reasons: list[str] = field(default_factory=list)

    # ── Safety ────────────────────────────────────────────────────────────────
    paper_only: bool = True       # MUST remain True until P38 cleared

    # ── Metadata ─────────────────────────────────────────────────────────────
    generated_at_utc: datetime = field(
        default_factory=lambda: __import__("datetime").datetime.utcnow()
    )
    source_trace: dict = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        # Enforce paper_only invariant — this gate must never be bypassed.
        if not self.paper_only:
            raise ValueError(
                "paper_only must be True — production enablement (P38) is NO_GO. "
                "Remove this guard only after the full governance gate is cleared."
            )
        if self.gate_status not in VALID_GATE_STATUSES:
            raise ValueError(
                f"gate_status '{self.gate_status}' not in VALID_GATE_STATUSES: "
                f"{sorted(VALID_GATE_STATUSES)}"
            )
        if not 0.0 <= self.model_prob_home <= 1.0:
            raise ValueError(f"model_prob_home out of [0,1]: {self.model_prob_home}")
        if not 0.0 <= self.model_prob_away <= 1.0:
            raise ValueError(f"model_prob_away out of [0,1]: {self.model_prob_away}")

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (datetimes → ISO-8601 strings)."""
        d = asdict(self)
        for key in ("game_start_utc", "generated_at_utc"):
            if isinstance(d[key], datetime):
                d[key] = d[key].isoformat()
        return d

    def to_jsonl_line(self) -> str:
        """Return a single JSONL line (no trailing newline)."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
