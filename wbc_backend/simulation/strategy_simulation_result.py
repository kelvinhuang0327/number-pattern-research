"""
wbc_backend/simulation/strategy_simulation_result.py

Typed dataclass contract for strategy simulation results.

Hard invariants:
- paper_only must remain True.
- sample_size, bet_count, skipped_count must be >= 0.
- gate_status must be in VALID_GATE_STATUSES.
- If sample_size < 30, gate_status must not be PASS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

VALID_GATE_STATUSES: frozenset[str] = frozenset({
    "PASS",
    "BLOCKED_NEGATIVE_BSS",
    "BLOCKED_HIGH_ECE",
    "BLOCKED_LOW_SAMPLE",
    "BLOCKED_NO_MARKET_DATA",
    "BLOCKED_NO_RESULTS",
    "PAPER_ONLY",
})

_MIN_SAMPLE_FOR_PASS = 30


@dataclass
class StrategySimulationResult:
    """Canonical typed contract for a completed strategy simulation run."""

    simulation_id: str
    strategy_name: str
    date_start: str
    date_end: str
    sample_size: int
    bet_count: int
    skipped_count: int
    gate_status: Literal[
        "PASS",
        "BLOCKED_NEGATIVE_BSS",
        "BLOCKED_HIGH_ECE",
        "BLOCKED_LOW_SAMPLE",
        "BLOCKED_NO_MARKET_DATA",
        "BLOCKED_NO_RESULTS",
        "PAPER_ONLY",
    ]
    generated_at_utc: datetime
    avg_model_prob: float | None = None
    avg_market_prob: float | None = None
    brier_model: float | None = None
    brier_market: float | None = None
    brier_skill_score: float | None = None
    ece: float | None = None
    roi_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_proxy: float | None = None
    avg_edge_pct: float | None = None
    avg_kelly_fraction: float | None = None
    gate_reasons: list[str] = field(default_factory=list)
    paper_only: bool = True
    source_trace: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError(
                "StrategySimulationResult.paper_only must remain True. "
                "Production mode is not permitted in simulation spine."
            )
        if self.gate_status not in VALID_GATE_STATUSES:
            raise ValueError(
                f"gate_status '{self.gate_status}' is not in VALID_GATE_STATUSES: "
                f"{sorted(VALID_GATE_STATUSES)}"
            )
        if self.sample_size < 0:
            raise ValueError(f"sample_size must be >= 0, got {self.sample_size}")
        if self.bet_count < 0:
            raise ValueError(f"bet_count must be >= 0, got {self.bet_count}")
        if self.skipped_count < 0:
            raise ValueError(f"skipped_count must be >= 0, got {self.skipped_count}")
        if self.sample_size < _MIN_SAMPLE_FOR_PASS and self.gate_status == "PASS":
            raise ValueError(
                f"gate_status cannot be PASS when sample_size ({self.sample_size}) "
                f"< {_MIN_SAMPLE_FOR_PASS}. Minimum required for a PASS gate is "
                f"{_MIN_SAMPLE_FOR_PASS} samples."
            )

    def to_dict(self) -> dict:
        """Serialize to a plain dict (datetimes as ISO-8601 strings)."""
        return {
            "simulation_id": self.simulation_id,
            "strategy_name": self.strategy_name,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "sample_size": self.sample_size,
            "bet_count": self.bet_count,
            "skipped_count": self.skipped_count,
            "avg_model_prob": self.avg_model_prob,
            "avg_market_prob": self.avg_market_prob,
            "brier_model": self.brier_model,
            "brier_market": self.brier_market,
            "brier_skill_score": self.brier_skill_score,
            "ece": self.ece,
            "roi_pct": self.roi_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_proxy": self.sharpe_proxy,
            "avg_edge_pct": self.avg_edge_pct,
            "avg_kelly_fraction": self.avg_kelly_fraction,
            "gate_status": self.gate_status,
            "gate_reasons": self.gate_reasons,
            "paper_only": self.paper_only,
            "generated_at_utc": self.generated_at_utc.isoformat()
            if isinstance(self.generated_at_utc, datetime)
            else str(self.generated_at_utc),
            "source_trace": self.source_trace,
        }

    def to_jsonl_line(self) -> str:
        """Serialize to a single JSON line (no trailing newline)."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
